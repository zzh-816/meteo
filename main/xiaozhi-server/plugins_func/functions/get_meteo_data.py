"""
气象数据查询插件 - 离线版
用于查询本地气象监测设备的实时数据
支持时间查询：昨天、今天、具体时间点等
"""
import sqlite3
import os
import sys
import json
import threading
from datetime import datetime, timedelta
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

# 尝试导入dateparser，如果没有则使用简单的时间解析
try:
    import dateparser
    HAS_DATEPARSER = True
except ImportError:
    HAS_DATEPARSER = False
    print("警告: 未安装dateparser库，时间解析功能受限。建议安装: pip install dateparser")

TAG = __name__
logger = setup_logging()

# 数据库路径 - 支持打包后的共享目录
def get_db_path():
    """获取数据库路径，支持开发环境和打包环境"""
    # 检查是否是打包后的环境
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，使用 EXE 所在目录的上级 data 目录（共享）
        exe_dir = os.path.dirname(sys.executable)
        # 向上找到 dist 目录
        parent_dir = os.path.dirname(exe_dir)
        shared_db = os.path.join(parent_dir, "data", "meteo_data.db")
        if os.path.exists(os.path.dirname(shared_db)):
            return shared_db
        # 备选：使用 _internal 目录下的数据库
        internal_db = os.path.join(exe_dir, "_internal", "data", "meteo_data.db")
        return internal_db
    else:
        # 开发环境
        return os.path.join(os.path.dirname(__file__), "..", "..", "data", "meteo_data.db")

DB_PATH = get_db_path()

# 气象要素中英文映射
# 气象要素字段代码到名称和单位的映射
# 作用：根据field_code（可能带后缀如WSPDD_hhmax）查找对应的中文名称和单位，用于构建给LLM的提示词

METEO_UNIT_DICT = {
    # 温度
    "TEMPA": "℃",
    
    # 湿度
    "HUMIA": "%",
    
    # 气压
    "PRESA": "hPa",
    
    # 风
    "WSPDA": "m/s",
    "WSPDB": "m/s",
    "WSPDC": "m/s",
    "WSPDD": "m/s",
    "WSPDE": "m/s",
    
    # 降水
    "PRECA": "mm",
    
    # 日照
    "SUNDA": "小时",
    
    # 蒸发
    "EVAPB": "mm",
    
    # 辐射
    "SGRAA": "W/m²",
    "SDRAA": "W/m²",
    "SSRAA": "W/m²",
    "SRRAA": "W/m²",
    "LSRAA": "W/m²",
    "LERAA": "W/m²",
    "UVRAD": "W/m²",
    "UVRAA": "W/m²",
    "UVRAB": "W/m²",
    "ACRAA": "W/m²",
    "NERAA": "W/m²",
    
    # 地温
    "STEMA": "℃",
    "STEMB": "℃",
    "STEMC": "℃",
    "STEMD": "℃",
    "STEME": "℃",
    "STEMF": "℃",
    "STEMG": "℃",
    "STEMH": "℃",
    "STEMI": "℃",
    "STEMJ": "℃",
    
    # 能见度
    "VISIB": "m",
    
    # 冻土
    "FROSA": "cm",
}

# 简单的名称映射（仅用于旧代码兼容）
METEO_NAME_DICT = {
    "TEMPA": "气温",
    "HUMIA": "相对湿度",
    "PRESA": "本站气压",
    "WSPDA": "瞬时风速",
    "WSPDB": "1分钟平均风速",
    "WSPDC": "2分钟平均风速",
    "WSPDD": "10分钟平均风速",
    "WSPDE": "极大风速",
    "PRECA": "降水量",
    "SUNDA": "日照时数",
    "EVAPB": "蒸发量",
    "SGRAA": "总辐射",
    "SDRAA": "直接辐射",
    "SSRAA": "散射辐射",
    "SRRAA": "反射辐射",
    "LSRAA": "大气长波辐射",
    "LERAA": "地面长波辐射",
    "UVRAD": "紫外辐射",
    "UVRAA": "紫外A辐射",
    "UVRAB": "紫外B辐射",
    "ACRAA": "光合有效辐射",
    "NERAA": "净全辐射",
    "STEMA": "草面温度",
    "STEMB": "地面温度",
    "STEMC": "5cm地温",
    "STEMD": "10cm地温",
    "STEME": "15cm地温",
    "STEMF": "20cm地温",
    "STEMG": "40cm地温",
    "STEMH": "80cm地温",
    "STEMI": "160cm地温",
    "STEMJ": "320cm地温",
    "VISIB": "能见度",
    "FROSA": "冻土",
}

# 质控码说明
QC_CODE = {
    0: "正常",
    1: "可疑",
    2: "错误",
    9: "缺测",
}

# 线程锁
_db_lock = threading.Lock()


def init_database():
    """初始化数据库"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meteo_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id TEXT,
                element_code TEXT,
                value REAL,
                qc_code INTEGER,
                obs_time TEXT,
                update_time TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_element ON meteo_data(element_code)")
        conn.commit()


def parse_meteo_string(data_string: str) -> dict:
    """解析气象数据字符串"""
    parts = data_string.split(",")
    if len(parts) < 7:
        return {}
    
    station_id = parts[2]  # SH001
    obs_time = parts[6]    # 20251125144200
    
    result = {"station_id": station_id, "obs_time": obs_time, "elements": {}}
    
    # 从第7个元素开始，每3个一组 [名称, 值, 质控码]
    i = 7
    while i + 2 < len(parts):
        code = parts[i]
        value = parts[i + 1]
        qc = parts[i + 2]
        
        if code in METEO_UNIT_DICT and value != "/" and value != "":
            try:
                result["elements"][code] = {
                    "value": float(value),
                    "qc_code": int(qc) if qc.isdigit() else 0
                }
            except ValueError:
                pass
        i += 3
    
    return result


def save_meteo_data(data: dict):
    """保存气象数据到数据库"""
    with _db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for code, elem in data.get("elements", {}).items():
                # 使用 REPLACE 更新最新数据
                conn.execute("""
                    INSERT OR REPLACE INTO meteo_data 
                    (station_id, element_code, value, qc_code, obs_time, update_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (data["station_id"], code, elem["value"], elem["qc_code"], 
                      data["obs_time"], now))
            conn.commit()


def get_latest_element(element_code: str) -> dict:
    """获取最新的某个气象要素数据"""
    init_database()
    with _db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                SELECT value, qc_code, obs_time, update_time
                FROM meteo_data
                WHERE element_code = ?
                ORDER BY update_time DESC LIMIT 1
            """, (element_code,))
            row = cursor.fetchone()
            if row:
                return {"value": row[0], "qc_code": row[1], "obs_time": row[2], "update_time": row[3]}
    return None


def get_element_by_time(element_code: str, target_time: datetime, tolerance_hours=1) -> dict:
    """
    获取指定时间点的气象要素数据

    Args:
        element_code: 要素代码
        target_time: 目标时间
        tolerance_hours: 容差时间（小时），在目标时间前后tolerance_hours小时内查找最接近的数据

    Returns:
        数据字典或None
    """
    init_database()
    with _db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            # 计算时间范围
            time_start = (target_time - timedelta(hours=tolerance_hours)).strftime("%Y-%m-%d %H:%M:%S")
            time_end = (target_time + timedelta(hours=tolerance_hours)).strftime("%Y-%m-%d %H:%M:%S")
            target_time_str = target_time.strftime("%Y-%m-%d %H:%M:%S")

            # 查找时间范围内最接近的数据
            cursor = conn.execute("""
                SELECT value, qc_code, obs_time, update_time,
                       ABS(JULIANDAY(obs_time) - JULIANDAY(?)) as time_diff
                FROM meteo_data
                WHERE element_code = ?
                  AND obs_time BETWEEN ? AND ?
                ORDER BY time_diff ASC
                LIMIT 1
            """, (target_time_str, element_code, time_start, time_end))

            row = cursor.fetchone()
            if row:
                return {
                    "value": row[0],
                    "qc_code": row[1],
                    "obs_time": row[2],
                    "update_time": row[3],
                    "time_diff_hours": row[4] * 24  # 转换为小时
                }
    return None


def parse_time_expression(text: str) -> datetime:
    """
    解析时间表达式（增强版，支持复杂中文时间）

    Args:
        text: 用户输入的文本

    Returns:
        解析出的datetime对象，如果解析失败返回None
    """
    import re

    now = datetime.now()
    text = text.strip()

    # 1. 提取基准日期（今天、昨天、前天、具体日期）
    base_date = None

    # 今天/现在
    if "今天" in text or "今日" in text or "现在" in text or "当前" in text:
        base_date = now

    # 昨天
    elif "昨天" in text or "昨日" in text:
        base_date = now - timedelta(days=1)

    # 前天
    elif "前天" in text:
        base_date = now - timedelta(days=2)

    # N天前
    elif re.search(r'(\d+)\s*天前', text):
        match = re.search(r'(\d+)\s*天前', text)
        days = int(match.group(1))
        base_date = now - timedelta(days=days)

    # N小时前（直接返回）
    elif re.search(r'(\d+)\s*小时前', text):
        match = re.search(r'(\d+)\s*小时前', text)
        hours = int(match.group(1))
        return now - timedelta(hours=hours)

    # 具体日期：12月10号、12月10日、12-10
    elif re.search(r'(\d+)\s*月\s*(\d+)\s*[号日]?', text):
        match = re.search(r'(\d+)\s*月\s*(\d+)\s*[号日]?', text)
        month = int(match.group(1))
        day = int(match.group(2))
        year = now.year
        # 如果月份大于当前月份，说明是去年
        if month > now.month:
            year -= 1
        try:
            base_date = datetime(year, month, day)
        except ValueError:
            return None

    # 上周X
    elif "上周" in text or "上星期" in text:
        weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
        for cn, num in weekday_map.items():
            if cn in text:
                days_ago = (now.weekday() - num) % 7 + 7
                base_date = now - timedelta(days=days_ago)
                break
        if base_date is None:
            base_date = now - timedelta(days=7)

    # 如果没有找到基准日期，尝试用dateparser
    if base_date is None and HAS_DATEPARSER:
        parsed = dateparser.parse(
            text,
            languages=['zh'],
            settings={
                'TIMEZONE': 'Asia/Shanghai',
                'RETURN_AS_TIMEZONE_AWARE': False,
                'PREFER_DATES_FROM': 'past'
            }
        )
        if parsed:
            return parsed
        return None

    if base_date is None:
        return None

    # 2. 提取具体时间（小时）
    hour = None
    minute = 0

    # 时间段映射
    time_period_map = {
        "凌晨": 4, "早上": 8, "早晨": 8, "上午": 10,
        "中午": 12, "下午": 15, "傍晚": 18, "晚上": 20, "夜里": 22
    }

    # 先检查是否有具体小时数
    # 匹配：3点、15点、三点
    hour_match = re.search(r'(\d+)\s*[点时]', text)
    if hour_match:
        hour = int(hour_match.group(1))
        # 如果有"下午"且小时<12，需要+12
        if ("下午" in text or "晚上" in text or "傍晚" in text) and hour < 12:
            hour += 12
    else:
        # 没有具体小时，检查时间段
        for period, default_hour in time_period_map.items():
            if period in text:
                hour = default_hour
                break

    # 3. 组合日期和时间
    if hour is not None:
        try:
            result = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return result
        except ValueError:
            return None
    else:
        # 只有日期，没有具体时间，返回当天的当前时刻
        return base_date.replace(hour=now.hour, minute=now.minute, second=0, microsecond=0)


# Function Call 描述
GET_METEO_DATA_DESC = {
    "type": "function",
    "function": {
        "name": "get_meteo_data",
        "description": "查询气象监测站的数据，支持实时和历史数据查询。用户问温度、湿度、风速、气压等，或询问某个时间点的气象数据时调用此函数。",
        "parameters": {
            "type": "object",
            "properties": {
                "element": {
                    "type": "string",
                    "description": "要查询的气象要素，可选：温度、湿度、气压、风速、风向、降水量、能见度、紫外线",
                },
                "time_query": {
                    "type": "string",
                    "description": "时间查询表达式，如：现在、今天、昨天、昨天下午3点、12月10号中午等。如果不指定则查询最新数据。",
                }
            },
            "required": ["element"],
        },
    },
}

# 用户输入到要素代码的映射
# 注意：长的关键词要放在前面，避免被短的先匹配
USER_INPUT_MAP = {
    "温度": "TEMPA", "气温": "TEMPA", "多少度": "TEMPA",
    "湿度": "HUMIA", "相对湿度": "HUMIA",
    "气压": "PRESA", "大气压": "PRESA",
    "风向": "WDIRA",  # 风向必须在"风"之前
    "风速": "WSPDA", "风": "WSPDA",
    "降水量": "PRECA", "降水": "PRECA", "雨量": "PRECA",  # 降水量在降水之前
    "能见度": "VISIA",
    "紫外线": "UVRAA",
}


@register_function("get_meteo_data", GET_METEO_DATA_DESC, ToolType.SYSTEM_CTL)
def get_meteo_data(conn, element: str = None, time_query: str = None):
    """
    查询气象数据的主函数（使用新的接口服务层）
    
    方案2：从conn.dialogue获取完整用户输入，由weather_field_mapper进行精确匹配

    Args:
        conn: 连接对象
        element: 气象要素（已废弃，保留以兼容旧代码）
        time_query: 时间查询表达式（已废弃，保留以兼容旧代码）
    """
    try:
        # 导入新的服务层模块
        from .weather_field_mapper import build_api_request_from_user_input
        from .weather_grpc_client import call_weather_api
        
        # 从conn.dialogue获取最新用户输入
        user_input = None
        if hasattr(conn, 'dialogue') and conn.dialogue:
            # 从后往前查找最新的用户消息
            for msg in reversed(conn.dialogue.dialogue):
                if msg.role == "user" and msg.content:
                    user_input = msg.content
                    break
        
        if not user_input:
            logger.bind(tag=TAG).warning("无法从dialogue获取用户输入，尝试使用element参数")
            # 如果无法获取用户输入，尝试使用element参数（向后兼容）
            if element:
                user_input = element
                if time_query:
                    user_input = f"{element} {time_query}"
            else:
                msg = "抱歉，无法获取您的查询内容，请重新提问"
                return ActionResponse(Action.RESPONSE, msg, msg)
        
        logger.bind(tag=TAG).info(f"用户输入: {user_input}")
        
        # 使用完整用户输入构建接口请求参数
        request = build_api_request_from_user_input(user_input, push_browser=False)
        
        if not request:
            msg = f"抱歉，无法识别您的查询：{user_input}，请检查查询要素是否正确"
            return ActionResponse(Action.RESPONSE, msg, msg)
        
        logger.bind(tag=TAG).info(f"构建请求参数: biz_type={request['biz_type']}, fields={request['params']['fields']}")
        
        # 调用接口（目前使用模拟数据，后续可切换为真实API）
        api_response = call_weather_api(
            biz_type=request["biz_type"],
            params=request["params"],
            req_id=request["req_id"],
            push_browser=request.get("push_browser", False)
        )
        
        # 处理接口响应 - 直接使用模板回复，不再调用LLM
        field_code = request["params"]["fields"][0]
        
        # 从API响应中提取数据值
        data_value = None
        if isinstance(api_response, dict):
            data = api_response.get("data", {})
            # data中可能直接包含field_code作为key，或者有其他格式
            if field_code in data:
                data_value = data[field_code]
            else:
                # 尝试提取第一个数值
                for key, value in data.items():
                    if key != "req_id" and value is not None:
                        try:
                            data_value = float(value)
                            break
                        except (ValueError, TypeError):
                            pass
        
        # 根据field_code获取单位（提取基础代码）
        base_field_code = field_code.split("_")[0] if "_" in field_code else field_code
        element_unit = METEO_UNIT_DICT.get(base_field_code, "")
        
        if not element_unit:
            logger.bind(tag=TAG).warning(f"未找到字段代码单位映射: {field_code} (基础代码: {base_field_code})")
        
        # 直接使用模板回复，不再调用LLM
        if data_value is not None:
            # 使用模板回复格式
            response_text = f"为您查询到的数据为{data_value} {element_unit}"
            logger.bind(tag=TAG).info(f"使用模板回复: {response_text}")
            return ActionResponse(
                Action.RESPONSE,
                result=response_text,
                response=response_text
            )
        else:
            # 未获取到数据的情况
            response_text = "抱歉，未获取到有效数据"
            logger.bind(tag=TAG).warning("未获取到有效数据")
            return ActionResponse(
                Action.RESPONSE,
                result=response_text,
                response=response_text
            )
    
    except ImportError as e:
        # 如果新模块导入失败，回退到旧逻辑
        logger.bind(tag=TAG).warning(f"新服务层模块导入失败，使用旧逻辑: {e}")
        return _get_meteo_data_legacy(conn, element, time_query)
    except Exception as e:
        logger.bind(tag=TAG).error(f"查询气象数据失败: {e}")
        import traceback
        logger.bind(tag=TAG).error(traceback.format_exc())
        msg = f"查询气象数据时发生错误，请稍后重试"
        return ActionResponse(Action.RESPONSE, msg, msg)


def _get_meteo_data_legacy(conn, element: str, time_query: str = None):
    """
    旧版查询逻辑（作为备用）
    """
    # 将用户输入映射到要素代码
    element_code = None
    sorted_keys = sorted(USER_INPUT_MAP.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in element:
            element_code = USER_INPUT_MAP[key]
            logger.bind(tag=TAG).info(f"匹配到要素: {key} -> {element_code}")
            break

    if not element_code:
        msg = "抱歉，不支持查询" + element + "，目前支持查询：温度、湿度、气压、风速、风向、降水量、能见度、紫外线"
        return ActionResponse(Action.RESPONSE, msg, msg)

    # 获取要素信息（用于旧代码兼容）
    elem_info = {
        "name": METEO_NAME_DICT.get(element_code, element_code),
        "unit": METEO_UNIT_DICT.get(element_code, "")
    }

    # 如果有时间查询，解析时间
    if time_query:
        logger.bind(tag=TAG).info(f"时间查询: {time_query}")

        # 解析时间表达式
        target_time = parse_time_expression(time_query)

        if target_time is None:
            # 时间解析失败，返回None让LLM处理
            logger.bind(tag=TAG).warning(f"时间解析失败: {time_query}")
            return None

        logger.bind(tag=TAG).info(f"解析时间: {target_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 查询指定时间的数据
        data = get_element_by_time(element_code, target_time, tolerance_hours=2)

        if not data:
            msg = f"抱歉，没有找到{target_time.strftime('%Y年%m月%d日 %H点')}左右的{elem_info['name']}数据"
            return ActionResponse(Action.RESPONSE, msg, msg)

        # 构建回复（包含时间信息）
        qc_status = QC_CODE.get(data["qc_code"], "未知")
        obs_time_obj = datetime.strptime(data["obs_time"], "%Y-%m-%d %H:%M:%S")
        time_desc = obs_time_obj.strftime("%Y年%m月%d日 %H点")

        response = f"{time_desc}的{elem_info['name']}为 {data['value']} {elem_info['unit']}，数据状态：{qc_status}"

    else:
        # 查询最新数据
        data = get_latest_element(element_code)

        if not data:
            elem_name = METEO_NAME_DICT.get(element_code, element_code)
            msg = "暂无" + elem_name + "数据，请确认数据采集程序是否正常运行"
            return ActionResponse(Action.RESPONSE, msg, msg)

        # 构建回复
        qc_status = QC_CODE.get(data["qc_code"], "未知")
        response = f"当前{elem_info['name']}为 {data['value']} {elem_info['unit']}，数据状态：{qc_status}"

    return ActionResponse(Action.RESPONSE, response, response)


# 初始化数据库
init_database()

