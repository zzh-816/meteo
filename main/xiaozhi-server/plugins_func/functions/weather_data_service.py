"""
气象数据服务层
从SQLite读取数据，返回符合接口文档格式的响应
后续可切换为真实GRPC调用
"""
import json
import sqlite3
import os
import sys
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

# 数据库路径
def get_db_path():
    """获取数据库路径，支持开发环境和打包环境"""
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        parent_dir = os.path.dirname(exe_dir)
        shared_db = os.path.join(parent_dir, "data", "meteo_data.db")
        if os.path.exists(os.path.dirname(shared_db)):
            return shared_db
        internal_db = os.path.join(exe_dir, "_internal", "data", "meteo_data.db")
        return internal_db
    else:
        return os.path.join(os.path.dirname(__file__), "..", "..", "data", "meteo_data.db")

DB_PATH = get_db_path()
_db_lock = threading.Lock()


def _get_mock_data(field_code: str) -> Dict:
    """
    生成模拟数据（用于测试）
    
    Args:
        field_code: 字段代码
    
    Returns:
        模拟数据字典
    """
    now = datetime.now()
    obs_time = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # 根据字段代码生成不同的模拟值
    mock_values = {
        # 基础字段
        "TEMPA": 25.5,
        "HUMIA": 65.0,
        "PRESA": 1013.2,
        "WSPDA": 3.5,
        "WSPDB": 3.2,
        "WSPDC": 3.0,
        "WSPDD": 2.8,
        "VISIB": 10000.0,
        "UVRAD": 0.5,
        "UVRAA": 0.3,
        "UVRAB": 0.2,
        "SGRAA": 800.0,
        "SDRAA": 600.0,
        "SSRAA": 200.0,
        "SRRAA": 50.0,
        "LSRAA": 300.0,
        "LERAA": 400.0,
        "ACRAA": 500.0,
        "NERAA": 200.0,
        "STEMB": 28.0,
        "STEMC": 26.0,
        "STEMD": 24.0,
        "STEME": 22.0,
        "STEMF": 20.0,
        "STEMG": 18.0,
        "STEMH": 16.0,
        "STEMI": 14.0,
        "STEMJ": 12.0,
        "STEMA": 30.0,
        "PRECA_p1accu": 0.5,
        "EVAPB": 2.5,
        "SUNDA_ddaccu": 8.5,
        "EVAPB_ddaccua": 5.0,
        "FROSA": 0.0,
        # 日度统计字段（极值）
        "TEMPA_ddmax": 30.0,
        "TEMPA_ddmin": 15.0,
        "PRESA_hhmax": 1020.0,
        "PRESA_hhmin": 1005.0,
        "HUMIA_hhmin": 40.0,
        "WSPDD_hhmax": 8.5,
        "WSPDE_hhmax": 12.0,
        "PRECA_p24accu": 10.5,
        "STEMB_hhmax": 35.0,
        "STEMB_hhmin": 20.0,
        "STEMA_hhmax": 38.0,
        "STEMA_hhmin": 22.0,
        "VISIB_hhmin": 5000.0,
    }
    
    # 如果字段代码不在模拟值中，尝试提取基础字段
    if field_code not in mock_values:
        # 提取基础字段代码（去掉后缀）
        base_field = field_code.split('_')[0]
        if base_field in mock_values:
            # 根据后缀类型调整值
            if '_ddmax' in field_code or '_hhmax' in field_code:
                # 最大值：基础值 + 5
                value = mock_values[base_field] + 5.0
            elif '_ddmin' in field_code or '_hhmin' in field_code:
                # 最小值：基础值 - 5
                value = mock_values[base_field] - 5.0
            else:
                value = mock_values[base_field]
        else:
            # 默认值
            value = 20.0
    else:
        value = mock_values[field_code]
    
    return {
        "value": value,
        "obs_time": obs_time,
        "qc_code": 0
    }


def get_data_from_db(field_code: str, begin_time: str = None, end_time: str = None, date: str = None) -> Optional[Dict]:
    """
    从数据库查询数据，如果无数据则返回模拟数据（用于测试）
    
    Args:
        field_code: 字段代码（如"TEMPA"）
        begin_time: 开始时间（格式：YYYY-MM-DD HH:mm:ss）
        end_time: 结束时间（格式：YYYY-MM-DD HH:mm:ss）
        date: 日期（格式：YYYY-MM-DD）
    
    Returns:
        数据字典，包含value和obs_time
    """
    with _db_lock:
        try:
            # 检查数据库是否存在
            if not os.path.exists(DB_PATH):
                logger.bind(tag=TAG).warning(f"数据库不存在，使用模拟数据: {field_code}")
                return _get_mock_data(field_code)
            
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 对于带后缀的字段代码（如TEMPA_ddmax），提取基础字段代码
            base_field_code = field_code.split('_')[0] if '_' in field_code else field_code
            
            if date:
                # 日度查询：查询指定日期的数据
                date_start = f"{date} 00:00:00"
                date_end = f"{date} 23:59:59"
                cursor.execute("""
                    SELECT value, obs_time, qc_code
                    FROM meteo_data
                    WHERE element_code = ? 
                    AND obs_time >= ? 
                    AND obs_time <= ?
                    ORDER BY obs_time DESC
                    LIMIT 1
                """, (base_field_code, date_start, date_end))
            elif begin_time and end_time:
                # 实时查询：查询指定时间范围的数据
                cursor.execute("""
                    SELECT value, obs_time, qc_code
                    FROM meteo_data
                    WHERE element_code = ? 
                    AND obs_time >= ? 
                    AND obs_time <= ?
                    ORDER BY ABS(julianday(obs_time) - julianday(?)) ASC
                    LIMIT 1
                """, (base_field_code, begin_time, end_time, begin_time))
            else:
                # 查询最新数据
                cursor.execute("""
                    SELECT value, obs_time, qc_code
                    FROM meteo_data
                    WHERE element_code = ?
                    ORDER BY obs_time DESC
                    LIMIT 1
                """, (base_field_code,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                # 如果查询的是带后缀的字段，需要根据后缀类型调整值
                if '_' in field_code:
                    base_value = row["value"]
                    if '_ddmax' in field_code or '_hhmax' in field_code:
                        # 最大值：基础值 + 随机增量
                        value = base_value + 5.0
                    elif '_ddmin' in field_code or '_hhmin' in field_code:
                        # 最小值：基础值 - 随机减量
                        value = base_value - 5.0
                    else:
                        value = base_value
                    
                    return {
                        "value": value,
                        "obs_time": row["obs_time"],
                        "qc_code": row["qc_code"]
                    }
                else:
                    return {
                        "value": row["value"],
                        "obs_time": row["obs_time"],
                        "qc_code": row["qc_code"]
                    }
            
            # 数据库无数据，返回模拟数据
            logger.bind(tag=TAG).info(f"数据库无数据，使用模拟数据: {field_code}")
            return _get_mock_data(field_code)
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"查询数据库失败: {e}，使用模拟数据")
            return _get_mock_data(field_code)


def format_api_response(
    req_id: str,
    field_code: str,
    data: Optional[Dict],
    push_browser: bool = False
) -> Dict:
    """
    格式化接口响应
    
    Args:
        req_id: 请求ID
        field_code: 字段代码
        data: 数据字典（包含value、obs_time、qc_code）
        push_browser: 是否推送浏览器
    
    Returns:
        符合接口文档格式的响应字典
    """
    if not data:
        # 无数据
        response = {
            "code": 404,
            "message": "无数据",
            "data": {
                "req_id": req_id
            }
        }
        if push_browser:
            response["push_result"] = "fail"
        return response
    
    # 有数据
    response = {
        "code": 200,
        "message": "查询成功",
        "data": {
            "req_id": req_id,
            field_code: str(data["value"])  # 接口要求返回字符串格式
        }
    }
    
    if push_browser:
        response["push_result"] = "success"
    
    return response


def query_weather_data(
    biz_type: str,
    params: Dict,
    req_id: str,
    push_browser: bool = False
) -> Dict:
    """
    查询气象数据（主入口）
    
    Args:
        biz_type: 业务类型（REAL_TIME 或 WEATHER）
        params: 参数字典（包含fields、begin_time/end_time或date）
        req_id: 请求ID
        push_browser: 是否推送浏览器
    
    Returns:
        符合接口文档格式的响应字典
    """
    try:
        fields = params.get("fields", [])
        if not fields:
            return {
                "code": 400,
                "message": "参数错误：fields不能为空",
                "data": {"req_id": req_id}
            }
        
        field_code = fields[0]  # 目前只支持单个字段查询
        
        # 从数据库查询数据
        if biz_type == "REAL_TIME":
            begin_time = params.get("begin_time")
            end_time = params.get("end_time")
            data = get_data_from_db(field_code, begin_time=begin_time, end_time=end_time)
        else:  # WEATHER
            date = params.get("date")
            data = get_data_from_db(field_code, date=date)
        
        # 格式化响应
        response = format_api_response(req_id, field_code, data, push_browser)
        
        # 记录查询结果到日志
        if data:
            logger.bind(tag=TAG).info(f"查询成功: {field_code}, 值: {data['value']}, 观测时间: {data.get('obs_time', 'N/A')}")
        else:
            logger.bind(tag=TAG).info(f"查询成功: {field_code}, 无数据")
        
        # 记录响应体到日志（详细格式）
        logger.bind(tag=TAG).debug(f"响应体详情: {json.dumps(response, ensure_ascii=False, indent=2)}")
        
        return response
        
    except Exception as e:
        logger.bind(tag=TAG).error(f"查询失败: {e}")
        return {
            "code": 500,
            "message": f"查询异常: {str(e)}",
            "data": {"req_id": req_id}
        }

