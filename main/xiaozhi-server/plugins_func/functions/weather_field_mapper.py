"""
气象数据字段映射模块
将语音查询转换为接口参数（biz_type、fields等）
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re
from config.logger import setup_logging

# 尝试导入 cn2an 库（如果可用，使用它进行中文数字转换）
try:
    import cn2an
    CN2AN_AVAILABLE = True
except ImportError:
    CN2AN_AVAILABLE = False
    # 如果 cn2an 不可用，使用简单的中文数字映射
    CHINESE_NUMBER_MAP = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
        '十': 10, '百': 100, '千': 1000, '万': 10000,
        '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5, '陆': 6, '柒': 7, '捌': 8, '玖': 9,
        '拾': 10, '佰': 100, '仟': 1000, '萬': 10000
    }

TAG = __name__
logger = setup_logging()

# 单位转换映射
# 注意：只转换那些在映射表中使用标准单位的（如cm、h）
# "分钟"不转换，因为映射表中使用的是"分钟"（如"1分钟风"），而不是"min"
UNIT_CONVERSION = {
    '厘米': 'cm',
    '公分': 'cm',
    '小时': 'h',
    '时': 'h',
    # '分钟': 'min',  # 不转换，映射表中使用"分钟"（如"1分钟风"）
    # '分': 'min',    # 不转换，避免影响"1分钟风"等匹配
    '秒': 's',
    '米': 'm',
    '毫米': 'mm',
    '千米': 'km',
    '公里': 'km',
}


def chinese_to_arabic(chinese_num: str) -> Optional[int]:
    """
    将中文数字转换为阿拉伯数字
    支持：一、二、三、十、十五、二十、一百、一百六十、三百二十等
    
    优先使用 cn2an 库（如果可用），否则使用简单映射
    
    Args:
        chinese_num: 中文数字字符串
    
    Returns:
        阿拉伯数字，如果转换失败返回None
    """
    if not chinese_num:
        return None
    
    # 如果已经是阿拉伯数字，直接返回
    if chinese_num.isdigit():
        return int(chinese_num)
    
    try:
        # 优先使用 cn2an 库（更可靠）
        if CN2AN_AVAILABLE:
            try:
                result = cn2an.cn2an(chinese_num)
                return int(result) if result is not None else None
            except Exception as e:
                logger.bind(tag=TAG).debug(f"cn2an转换失败，尝试备用方法: {chinese_num}, 错误: {e}")
                # 如果 cn2an 失败，继续使用备用方法
        
        # 备用方法：使用简单映射（当 cn2an 不可用时）
        if not CN2AN_AVAILABLE:
            # 处理简单数字（一、二、三...九）
            if chinese_num in CHINESE_NUMBER_MAP:
                num = CHINESE_NUMBER_MAP[chinese_num]
                if num < 10:
                    return num
                elif num == 10:
                    return 10
            
            # 特殊情况：十、十一...十九
            if chinese_num == "十":
                return 10
            if len(chinese_num) == 2 and chinese_num[0] == "十":
                second_char = chinese_num[1]
                if second_char in CHINESE_NUMBER_MAP:
                    return 10 + CHINESE_NUMBER_MAP[second_char]
            
            # 处理复杂数字（二十、一百、一百六十、三百二十等）
            result = 0
            temp = 0
            
            for i, char in enumerate(chinese_num):
                if char not in CHINESE_NUMBER_MAP:
                    continue
                    
                value = CHINESE_NUMBER_MAP[char]
                
                if value < 10:
                    temp = value
                elif value == 10:
                    if temp == 0:
                        temp = 10
                    else:
                        result += temp * 10
                        temp = 0
                elif value == 100:
                    if temp == 0:
                        temp = 100
                    else:
                        result += temp * 100
                        temp = 0
                elif value == 1000:
                    if temp == 0:
                        temp = 1000
                    else:
                        result += temp * 1000
                        temp = 0
                elif value == 10000:
                    if temp == 0:
                        temp = 10000
                    else:
                        result += temp * 10000
                        temp = 0
            
            result += temp
            if result == 0 and temp > 0:
                result = temp
            
            return result if result > 0 else None
        
        return None
    except Exception as e:
        logger.bind(tag=TAG).debug(f"中文数字转换失败: {chinese_num}, 错误: {e}")
        return None


def normalize_user_input(user_input: str) -> str:
    """
    标准化用户输入，将中文数字和单位转换为标准格式
    
    例如：
    - "五厘米地温" -> "5cm地温"
    - "一百六十厘米地温" -> "160cm地温"
    - "一小时降水量" -> "1h降水量"
    - "5厘米地温" -> "5cm地温"
    - "五厘米地温" -> "5cm地温"
    
    Args:
        user_input: 原始用户输入
    
    Returns:
        标准化后的输入
    """
    normalized = user_input
    
    # 1. 先转换单位（厘米->cm，小时->h等）
    # 注意：按长度从长到短排序，避免"小时"被"时"先匹配
    sorted_units = sorted(UNIT_CONVERSION.items(), key=lambda x: len(x[0]), reverse=True)
    for chinese_unit, standard_unit in sorted_units:
        normalized = normalized.replace(chinese_unit, standard_unit)
    
    # 2. 查找并转换"中文数字+单位"的模式（如"五厘米"、"一百六十厘米"等）
    # 匹配模式：中文数字 + 单位（cm、h等，单位已在第一步转换）
    # 注意：不包括"分钟"，因为映射表中使用"分钟"而不是"min"
    def replace_chinese_num_with_unit(match):
        chinese_num = match.group(1)
        unit = match.group(2)
        arabic_num = chinese_to_arabic(chinese_num)
        if arabic_num is not None:
            return f"{arabic_num}{unit}"
        return match.group(0)  # 如果转换失败，保持原样
    
    # 匹配"中文数字+单位"（如"五cm"、"一百六十cm"）
    # 注意：不包括"min"，因为"分钟"不转换
    pattern = r'([一二三四五六七八九十百千万零壹贰叁肆伍陆柒捌玖拾佰仟萬]+)(cm|h|s|m|mm|km)'
    normalized = re.sub(pattern, replace_chinese_num_with_unit, normalized)
    
    # 3. 特殊处理：中文数字+分钟（如"一分钟"、"十分钟"）
    # 只转换数字部分，保持"分钟"不变
    def replace_chinese_num_with_minute(match):
        chinese_num = match.group(1)
        arabic_num = chinese_to_arabic(chinese_num)
        if arabic_num is not None:
            return f"{arabic_num}分钟"
        return match.group(0)
    
    # 匹配"中文数字+分钟"（如"一分钟"、"十分钟"）
    minute_pattern = r'([一二三四五六七八九十百千万零壹贰叁肆伍陆柒捌玖拾佰仟萬]+)分钟'
    normalized = re.sub(minute_pattern, replace_chinese_num_with_minute, normalized)
    
    logger.bind(tag=TAG).debug(f"输入标准化: '{user_input}' -> '{normalized}'")
    return normalized

# 一级分类到二级分类的映射
PRIMARY_TO_SECONDARY = {
    "气压": ["本站气压", "最高本站气压", "最低本站气压"],
    "温度": ["气温", "最高气温", "最低气温"],
    "湿度": ["相对湿度", "最小相对湿度"],
    "风": ["瞬时风", "1分钟风", "2分钟风", "10分钟风", "最大风", "极大风"],
    "降水": ["1h降水量", "日降水量"],
    "日照": ["日照时数", "日日照时数"],
    "蒸发": ["小时蒸发量", "日蒸发量"],
    "辐射": ["总辐射", "直接辐射", "散射辐射", "反射辐射", "大气长波", "地面长波", 
             "紫外辐射", "紫外A辐射", "紫外B辐射", "光合有效辐射", "净全辐射"],
    "地温": ["地面温度", "最高地面温度", "最低地面温度", "5cm地温", "10cm地温", "15cm地温", "20cm地温", "40cm地温", 
             "80cm地温", "160cm地温", "320cm地温", "红外地温"],
    "草温": ["草面温度", "最高草面温度", "最低草面温度", "雪面温度","最高雪面温度","最低雪面温度"],
    "能见度": ["能见度", "最小能见度"],
    "冻土": ["冻土", "冻土上下限"],
}

# 二级分类的查询模式映射
# 格式：{
#   "二级分类": [
#     {
#       "field": "字段标识",
#       "biz_type": "REAL_TIME/WEATHER",
#       "time_keywords": ["时间关键词列表"],  # 用于匹配用户输入中的时间词
#       "extreme_keywords": ["极值关键词列表"],  # 用于匹配用户输入中的极值词（最高、最低等）
#       "required_time": bool  # 是否必须包含时间关键词（如果为False，则无时间限定也匹配）
#     }
#   ]
# }
SECONDARY_QUERY_PATTERNS = {
    # 气压
    "本站气压": [
        {
            "field": "PRESA",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,  # 无时间限定也匹配
        },
        {
            "field": "PRESA_hhmax",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最高"],
            "required_time": False,  # 无时间限定也匹配
        },
        {
            "field": "PRESA_hhmin",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最低"],
            "required_time": False,  # 无时间限定也匹配
        },
    ],
    
    # 温度
    "气温": [
        {
            "field": "TEMPA",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
        },
        {
            "field": "TEMPA_ddmax",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最高"],
            "required_time": False,
        },
        {
            "field": "TEMPA_ddmin",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最低"],
            "required_time": False,
    },
    ],
    
    # 湿度
    "相对湿度": [
        {
            "field": "HUMIA",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
        },
        {
            "field": "HUMIA_hhmin",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最小"],
            "required_time": False,
        },
    ],
    
    # 风
    "瞬时风": [
        {
            "field": "WSPDA",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "1分钟风": [
        {
            "field": "WSPDB",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "2分钟风": [
        {
            "field": "WSPDC",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "10分钟风": [
        {
            "field": "WSPDD",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
        },
    ],
    "最大风": [
        {
            "field": "WSPDD_hhmax",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最大"],
            "required_time": False,
    },
    ],
    "极大风": [
        {
            "field": "WSPDE_hhmax",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["极大"],
            "required_time": False,
    },
    ],
    
    # 降水
    "1h降水量": [
        {
            "field": "PRECA_p1accu",
            "biz_type": "REAL_TIME",
            "time_keywords": ["1小时", "1h", "一小时"],
            "extreme_keywords": [],
            "required_time": True,
    },
    ],
    "日降水量": [
        {
            "field": "PRECA_p24accu",
            "biz_type": "WEATHER",
            "time_keywords": ["日"],
            "extreme_keywords": [],
            "required_time": True,
    },
    ],
    
    # 日照
    "日照时数": [
        {
            "field": "SUNDA_ddaccu",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "日日照时数": [
        {
            "field": "SUNDA_ddaccu",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    
    # 蒸发
    "小时蒸发量": [
        {
            "field": "EVAPB",
            "biz_type": "REAL_TIME",
            "time_keywords": ["1小时", "1h", "一小时"],
            "extreme_keywords": [],
            "required_time": True,
    },
    ],
    "日蒸发量": [
        {
            "field": "EVAPB_ddaccua",
            "biz_type": "WEATHER",
            "time_keywords": ["日"],
            "extreme_keywords": [],
            "required_time": True,
    },
    ],
    
    # 辐射
    "总辐射": [
        {
            "field": "SGRAA",
            "biz_type": "REAL_TIME",
            "time_keywords": [],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "直接辐射": [
        {
            "field": "SDRAA",
            "biz_type": "REAL_TIME",
            "time_keywords": [],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "散射辐射": [
        {
            "field": "SSRAA",
            "biz_type": "REAL_TIME",
            "time_keywords": [],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "反射辐射": [
        {
            "field": "SRRAA",
            "biz_type": "REAL_TIME",
            "time_keywords": [],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "大气长波": [
        {
            "field": "LSRAA",
            "biz_type": "REAL_TIME",
            "time_keywords": [],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "地面长波": [
        {
            "field": "LERAA",
            "biz_type": "REAL_TIME",
            "time_keywords": [],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "紫外辐射": [
        {
            "field": "UVRAD",
            "biz_type": "REAL_TIME",
            "time_keywords": [],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "紫外A辐射": [
        {
            "field": "UVRAA",
            "biz_type": "REAL_TIME",
            "time_keywords": [],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "紫外B辐射": [
        {
            "field": "UVRAB",
            "biz_type": "REAL_TIME",
            "time_keywords": [],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "光合有效辐射": [
        {
            "field": "ACRAA",
            "biz_type": "REAL_TIME",
            "time_keywords": [],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "净全辐射": [
        {
            "field": "NERAA",
            "biz_type": "REAL_TIME",
            "time_keywords": [],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    
    # 地温
    "地面温度": [
        {
            "field": "STEMB",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
        },
        {
            "field": "STEMB_hhmax",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最高"],
            "required_time": False,
        },
        {
            "field": "STEMB_hhmin",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最低"],
            "required_time": False,
    },
    ],
    "5cm地温": [
        {
            "field": "STEMC",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "10cm地温": [
        {
            "field": "STEMD",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "15cm地温": [
        {
            "field": "STEME",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "20cm地温": [
        {
            "field": "STEMF",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "40cm地温": [
        {
            "field": "STEMG",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "80cm地温": [
        {
            "field": "STEMH",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "160cm地温": [
        {
            "field": "STEMI",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "320cm地温": [
        {
            "field": "STEMJ",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "红外地温": [
        {
            "field": "STEMB",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    
    # 草温
    "草面温度": [
        {
            "field": "STEMA",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
        },
        {
            "field": "STEMA_hhmax",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最高"],
            "required_time": False,
        },
        {
            "field": "STEMA_hhmin",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最低"],
            "required_time": False,
    },
    ],
    "雪面温度": [
        {
            "field": "STEMA",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在"],
            "extreme_keywords": [],
            "required_time": False,
        },
        {
            "field": "STEMA_hhmax",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最高"],
            "required_time": False,
        },
        {
            "field": "STEMA_hhmin",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最低"],
            "required_time": False,
        },
    ],
    
    # 能见度
    "能见度": [
        {
            "field": "VISIB",
            "biz_type": "REAL_TIME",
            "time_keywords": ["当前", "现在", "10分钟平均"],
            "extreme_keywords": [],
            "required_time": False,
        },
        {
            "field": "VISIB_hhmin",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最小"],
            "required_time": False,
    },
    ],
    "最小能见度": [
        {
            "field": "VISIB_hhmin",
            "biz_type": "WEATHER",
            "time_keywords": ["今天"],
            "extreme_keywords": ["最小"],
            "required_time": False,
    },
    ],
    
    # 冻土
    "冻土": [
        {
            "field": "FROSA",
            "biz_type": "WEATHER",
            "time_keywords": ["现在", "今天"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
    "冻土上下限": [
        {
            "field": "FROSA",
            "biz_type": "WEATHER",
            "time_keywords": ["现在", "今天"],
            "extreme_keywords": [],
            "required_time": False,
    },
    ],
}

# 用户输入关键词到二级分类的映射（支持别名）
USER_INPUT_TO_SECONDARY = {
    # 气压
    "最高本站气压": "本站气压",  # 映射到基础分类，通过查询模式匹配
    "最低本站气压": "本站气压",  # 映射到基础分类，通过查询模式匹配
    "气压": "本站气压",
    "本站气压": "本站气压",
    
    # 温度
    "最高气温": "气温",  # 映射到基础分类，通过查询模式匹配
    "最低气温": "气温",  # 映射到基础分类，通过查询模式匹配
    "温度": "气温",
    "气温": "气温",
    
    # 湿度
    "最小相对湿度": "相对湿度",  # 映射到基础分类，通过查询模式匹配
    "湿度": "相对湿度",
    "相对湿度": "相对湿度",
    
    # 风
    "极大风速": "极大风",  # 优先匹配组合词
    "最大风速": "最大风",  # 优先匹配组合词
    "风速": "瞬时风",  # 默认映射到瞬时风
    "瞬时风": "瞬时风",
    "1分钟平均风": "1分钟风",  # 支持"平均"的说法
    "2分钟平均风": "2分钟风",  # 支持"平均"的说法
    "10分钟平均风": "10分钟风",  # 支持"平均"的说法
    "1分钟风": "1分钟风",
    "2分钟风": "2分钟风",
    "10分钟风": "10分钟风",
    "最大风": "最大风",
    "极大风": "极大风",
    
    # 降水（不直接映射，通过一级分类匹配所有可能的二级分类）
    "1h降水量": "1h降水量",
    "1小时降水量": "1h降水量",
    "日降水量": "日降水量",
    
    # 日照
    "日照": "日照时数",
    "日照时数": "日照时数",
    "日日照时数": "日日照时数",
    
    # 蒸发（不直接映射，通过一级分类匹配所有可能的二级分类）
    "小时蒸发量": "小时蒸发量",
    "1小时蒸发量": "小时蒸发量",
    "日蒸发量": "日蒸发量",
    
    # 辐射
    "总辐射": "总辐射",
    "直接辐射": "直接辐射",
    "散射辐射": "散射辐射",
    "反射辐射": "反射辐射",
    "大气长波": "大气长波",
    "地面长波": "地面长波",
    "紫外": "紫外辐射",
    "紫外辐射": "紫外辐射",
    "紫外A": "紫外A辐射",
    "紫外A辐射": "紫外A辐射",
    "紫外B": "紫外B辐射",
    "紫外B辐射": "紫外B辐射",
    "光合有效辐射": "光合有效辐射",
    "净全辐射": "净全辐射",
    
    # 地温
    "最高地面温度": "地面温度",  # 映射到地面温度，通过查询模式匹配
    "最低地面温度": "地面温度",  # 映射到地面温度，通过查询模式匹配
    "地面温度": "地面温度",
    "5cm地温": "5cm地温",
    "5厘米地温": "5cm地温",
    "10cm地温": "10cm地温",
    "10厘米地温": "10cm地温",
    "15cm地温": "15cm地温",
    "15厘米地温": "15cm地温",
    "20cm地温": "20cm地温",
    "20厘米地温": "20cm地温",
    "40cm地温": "40cm地温",
    "40厘米地温": "40cm地温",
    "80cm地温": "80cm地温",
    "80厘米地温": "80cm地温",
    "160cm地温": "160cm地温",
    "160厘米地温": "160cm地温",
    "320cm地温": "320cm地温",
    "320厘米地温": "320cm地温",
    "红外地温": "红外地温",
    
    # 草温
    "最高草面温度": "草面温度",  # 映射到草面温度，通过查询模式匹配
    "最低草面温度": "草面温度",  
    "草面温度": "草面温度",
    "雪面温度": "雪面温度",
    "最高雪面温度": "雪面温度",  
    "最低雪面温度": "雪面温度",
    "雪面": "雪面温度",  # 支持只输入"雪面"
    
    # 能见度
    "能见度": "能见度",
    "最小能见度": "最小能见度",
    
    # 冻土
    "冻土": "冻土",
    "冻土上下限": "冻土上下限",
}


def find_secondary_category(user_input: str) -> Optional[List[str]]:
    """
    从用户输入中识别二级分类
    
    Args:
        user_input: 用户输入文本
    
    Returns:
        可能的二级分类列表，如果找不到返回None
    """
    # 先标准化输入（转换中文数字和单位）
    normalized_input = normalize_user_input(user_input)
    user_input_lower = normalized_input.lower()
    
    # 按长度从长到短排序，优先匹配更具体的词
    sorted_keys = sorted(USER_INPUT_TO_SECONDARY.keys(), key=len, reverse=True)
    
    # 改进匹配逻辑：优先匹配更长的、更具体的词
    # 对于包含字母的key（如"紫外A"），需要确保大小写不敏感匹配
    for key in sorted_keys:
        key_lower = key.lower()
        # 使用精确匹配，避免子串误匹配
        # 例如："紫外A辐射"应该匹配"紫外A辐射"，而不是"紫外辐射"
        if key_lower in user_input_lower:
            # 进一步检查：如果key包含字母（如"紫外A"），确保匹配的是完整的词
            # 避免"紫外A辐射"被"紫外辐射"误匹配
            # 由于已经按长度排序，更长的词会先匹配，所以这里直接返回即可
            secondary = USER_INPUT_TO_SECONDARY[key]
            logger.bind(tag=TAG).debug(f"匹配到二级分类: {key} -> {secondary} (原始输入: {user_input})")
            return [secondary]
    
    # 如果直接匹配不到，尝试通过一级分类查找
    for primary, secondaries in PRIMARY_TO_SECONDARY.items():
        if primary in user_input_lower:
            # 返回所有可能的二级分类
            if secondaries:
                logger.bind(tag=TAG).debug(f"通过一级分类匹配: {primary} -> {secondaries} (原始输入: {user_input})")
                return secondaries
    
    return None


def match_query_pattern(secondary: str, user_input: str) -> Optional[Dict]:
    """
    匹配查询模式
    
    Args:
        secondary: 二级分类
        user_input: 用户输入文本
    
    Returns:
        匹配的查询模式字典，包含field和biz_type，如果找不到返回None
    """
    patterns = SECONDARY_QUERY_PATTERNS.get(secondary)
    if not patterns:
        logger.bind(tag=TAG).warning(f"未找到二级分类的查询模式: {secondary}")
        return None
    
    # 先标准化输入（转换中文数字和单位）
    normalized_input = normalize_user_input(user_input)
    user_input_lower = normalized_input.lower()
    
    # 提取用户输入中的时间关键词和极值关键词
    time_keywords_found = []
    extreme_keywords_found = []
    
    # 检查所有可能的时间关键词（包括中文和英文单位）
    all_time_keywords = ["当前", "现在", "今天", "日", "1小时", "1h", "一小时", "10分钟平均"]
    for kw in all_time_keywords:
        # 标准化关键词后再匹配
        normalized_kw = normalize_user_input(kw)
        if normalized_kw in user_input_lower or kw in user_input_lower:
            time_keywords_found.append(normalized_kw if normalized_kw != kw else kw)
    
    # 检查所有可能的极值关键词
    all_extreme_keywords = ["最高", "最低", "最大", "最小", "极大"]
    for kw in all_extreme_keywords:
        if kw in user_input_lower:
            extreme_keywords_found.append(kw)
    
    # 尝试匹配每个模式
    best_match = None
    best_score = -1
    
    for pattern in patterns:
        score = 0
        
        # 检查极值关键词匹配
        pattern_extreme = pattern.get("extreme_keywords", [])
        if pattern_extreme:
            # 如果模式需要极值关键词，用户输入必须包含
            if not extreme_keywords_found:
                continue
            if any(ekw in pattern_extreme for ekw in extreme_keywords_found):
                score += 10
            else:
                continue
        else:
            # 如果模式不需要极值关键词，用户输入也不应该有
            if extreme_keywords_found:
                continue
        
        # 检查时间关键词匹配
        pattern_time = pattern.get("time_keywords", [])
        required_time = pattern.get("required_time", False)
        
        if pattern_time:
            # 模式有时间关键词要求
            if time_keywords_found:
                # 用户输入包含时间关键词，检查是否匹配
                if any(tkw in pattern_time for tkw in time_keywords_found):
                    score += 5
                elif not required_time:
                    # 不要求时间关键词，但用户提供了，可能不匹配
                    score += 1
            else:
                # 用户输入没有时间关键词
                if required_time:
                    # 模式要求时间关键词，但用户没有提供
                    continue
                else:
                    # 模式不要求时间关键词，匹配（无时间限定）
                    score += 3
        else:
            # 模式没有时间关键词要求
            if not time_keywords_found:
                score += 3
            else:
                score += 1
        
        if score > best_score:
            best_score = score
            best_match = pattern
    
    if best_match:
        logger.bind(tag=TAG).debug(f"匹配到查询模式: {secondary} -> {best_match['field']}, {best_match['biz_type']}")
        return best_match
    
    logger.bind(tag=TAG).warning(f"未找到匹配的查询模式: {secondary}, user_input={user_input}")
    return None


def get_field_code(element: str, time_query: str = None) -> Optional[Tuple[str, str]]:
    """
    获取字段代码和业务类型（基于语音查询项核心描述匹配）
    
    Args:
        element: 气象要素（如"温度"、"本站气压"）
        time_query: 时间查询表达式（如"现在"、"今天最高"），可选，如果为None则从element中提取
    
    Returns:
        (field_code, biz_type) 元组，如果找不到返回None
    """
    # 合并element和time_query
    if time_query:
        full_query = element + " " + time_query
    else:
        full_query = element
    
    # 注意：find_secondary_category 内部会调用 normalize_user_input 进行标准化
    # 查找二级分类（可能返回多个候选）
    secondaries = find_secondary_category(full_query)
    if not secondaries:
        logger.bind(tag=TAG).warning(f"未找到二级分类: {full_query}")
        return None
    
    # 尝试匹配每个二级分类，找到最佳匹配
    best_pattern = None
    best_score = -1
    
    for secondary in secondaries:
        pattern = match_query_pattern(secondary, full_query)
        if pattern:
            # 计算匹配分数（简单评分：有极值关键词匹配得高分，有时间关键词匹配得中分）
            score = 0
            user_input_lower = full_query.lower()
            
            # 检查极值关键词
            pattern_extreme = pattern.get("extreme_keywords", [])
            if pattern_extreme:
                if any(ekw in user_input_lower for ekw in pattern_extreme):
                    score += 10
            
            # 检查时间关键词
            pattern_time = pattern.get("time_keywords", [])
            if pattern_time:
                if any(tkw in user_input_lower for tkw in pattern_time):
                    score += 5
            
            if score > best_score:
                best_score = score
                best_pattern = pattern
    
    if best_pattern:
        return (best_pattern["field"], best_pattern["biz_type"])
    
    logger.bind(tag=TAG).warning(f"未找到匹配的查询模式: {full_query}")
    return None


def build_api_request_params(
    element: str, 
    time_query: str = None, 
    push_browser: bool = False
) -> Dict:
    """
    构建接口请求参数（旧接口，保留以兼容）
    
    Args:
        element: 气象要素
        time_query: 时间查询表达式
        push_browser: 是否推送浏览器
    
    Returns:
        接口请求参数字典，如果失败返回None
    """
    # 获取field代码和biz_type
    result = get_field_code(element, time_query)
    if not result:
        logger.bind(tag=TAG).warning(f"无法获取字段代码: element={element}, time_query={time_query}")
        return None
    
    field_code, biz_type = result
    
    # 生成req_id
    req_id = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # 构建params
    params = {
        "fields": [field_code]
    }
    
    if biz_type == "REAL_TIME":
        # 实时查询：需要begin_time和end_time
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        params["begin_time"] = time_str
        params["end_time"] = time_str
    else:
        # 日度查询：需要date
        now = datetime.now()
        params["date"] = now.strftime("%Y-%m-%d")
    
    # 构建完整请求
    request = {
        "biz_type": biz_type,
        "req_id": req_id,
        "params": params,
        "push_browser": push_browser
    }
    
    logger.bind(tag=TAG).debug(f"构建请求: {request}")
    return request


def build_api_request_from_user_input(
    user_input: str,
    push_browser: bool = False
) -> Optional[Dict]:
    """
    从完整用户输入构建接口请求参数（方案2：统一处理）
    
    接收完整用户输入，由weather_field_mapper进行精确匹配：
    - 识别气象实体名词（如"极大风"、"最高温度"等）
    - 提取时间信息
    - 映射到对应的field和biz_type
    
    Args:
        user_input: 完整用户输入文本（如"极大风是多少"、"今天最高温度"）
        push_browser: 是否推送浏览器
    
    Returns:
        接口请求参数字典，如果失败返回None
    """
    if not user_input or not user_input.strip():
        logger.bind(tag=TAG).warning("用户输入为空")
        return None
    
    user_input = user_input.strip()
    logger.bind(tag=TAG).debug(f"处理用户输入: {user_input}")
    
    # 查找二级分类（可能返回多个候选）
    secondaries = find_secondary_category(user_input)
    if not secondaries:
        logger.bind(tag=TAG).warning(f"未找到二级分类: {user_input}")
        return None
    
    # 尝试匹配每个二级分类，找到最佳匹配
    best_pattern = None
    best_score = -1
    best_secondary = None
    
    for secondary in secondaries:
        pattern = match_query_pattern(secondary, user_input)
        if pattern:
            # 计算匹配分数（简单评分：有极值关键词匹配得高分，有时间关键词匹配得中分）
            score = 0
            user_input_lower = user_input.lower()
            
            # 检查极值关键词
            pattern_extreme = pattern.get("extreme_keywords", [])
            if pattern_extreme:
                if any(ekw in user_input_lower for ekw in pattern_extreme):
                    score += 10
            
            # 检查时间关键词
            pattern_time = pattern.get("time_keywords", [])
            if pattern_time:
                if any(tkw in user_input_lower for tkw in pattern_time):
                    score += 5
            
            # 如果模式不要求时间关键词，且用户输入也没有时间关键词，给基础分
            if not pattern_time and not any(tkw in user_input_lower for tkw in ["当前", "现在", "今天", "昨天", "日", "1小时", "1h"]):
                score += 3
            
            if score > best_score:
                best_score = score
                best_pattern = pattern
                best_secondary = secondary
    
    if not best_pattern:
        logger.bind(tag=TAG).warning(f"未找到匹配的查询模式: {user_input}")
        return None
    
    field_code = best_pattern["field"]
    biz_type = best_pattern["biz_type"]
    
    logger.bind(tag=TAG).info(f"匹配成功: {user_input} -> {best_secondary} -> {field_code} ({biz_type})")
    
    # 生成req_id
    req_id = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # 构建params
    params = {
        "fields": [field_code]
    }
    
    if biz_type == "REAL_TIME":
        # 实时查询：需要begin_time和end_time
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        params["begin_time"] = time_str
        params["end_time"] = time_str
    else:
        # 日度查询：需要date
        now = datetime.now()
        params["date"] = now.strftime("%Y-%m-%d")
    
    # 构建完整请求
    request = {
        "biz_type": biz_type,
        "req_id": req_id,
        "params": params,
        "push_browser": push_browser
    }
    
    logger.bind(tag=TAG).debug(f"构建请求: {request}")
    return request
