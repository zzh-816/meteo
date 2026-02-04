"""
气象数据字段映射模块
将语音查询转换为接口参数（biz_type、fields等）
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

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
            "time_keywords": ["1小时", "1h"],
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
            "time_keywords": ["1小时", "1h"],
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
    user_input_lower = user_input.lower()
    
    # 按长度从长到短排序，优先匹配更具体的词
    sorted_keys = sorted(USER_INPUT_TO_SECONDARY.keys(), key=len, reverse=True)
    
    for key in sorted_keys:
        if key in user_input_lower:
            secondary = USER_INPUT_TO_SECONDARY[key]
            logger.bind(tag=TAG).debug(f"匹配到二级分类: {key} -> {secondary}")
            return [secondary]
    
    # 如果直接匹配不到，尝试通过一级分类查找
    for primary, secondaries in PRIMARY_TO_SECONDARY.items():
        if primary in user_input_lower:
            # 返回所有可能的二级分类
            if secondaries:
                logger.bind(tag=TAG).debug(f"通过一级分类匹配: {primary} -> {secondaries}")
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
    
    user_input_lower = user_input.lower()
    
    # 提取用户输入中的时间关键词和极值关键词
    time_keywords_found = []
    extreme_keywords_found = []
    
    # 检查所有可能的时间关键词
    all_time_keywords = ["当前", "现在", "今天", "日", "1小时", "1h", "10分钟平均"]
    for kw in all_time_keywords:
        if kw in user_input_lower:
            time_keywords_found.append(kw)
    
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
