"""
GRPC客户端封装
目前使用模拟数据（从SQLite读取），返回符合接口文档格式
后续切换为真实GRPC调用
"""
import json
import os
from datetime import datetime
from typing import Dict, Optional
from config.logger import setup_logging
from .weather_data_service import query_weather_data

TAG = __name__
logger = setup_logging()

# 公司GRPC接口地址（后续使用）
GRPC_SERVER_URL = "10.10.3.231/share-api/data-query"

# 是否使用真实API（配置项，后续可通过配置文件控制）
USE_REAL_API = False

# 请求响应保存目录
API_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "api_logs")
os.makedirs(API_LOG_DIR, exist_ok=True)


def _save_request_to_file(request_body: Dict, req_id: str):
    """
    保存请求体到文件
    
    Args:
        request_body: 请求体字典
        req_id: 请求ID
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"request_{req_id}_{timestamp}.json"
        filepath = os.path.join(API_LOG_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(request_body, f, ensure_ascii=False, indent=2)
        
        logger.bind(tag=TAG).info(f"请求体已保存到: {filepath}")
    except Exception as e:
        logger.bind(tag=TAG).error(f"保存请求体失败: {e}")


def _save_response_to_file(response_body: Dict, req_id: str):
    """
    保存响应体到文件
    
    Args:
        response_body: 响应体字典
        req_id: 请求ID
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"response_{req_id}_{timestamp}.json"
        filepath = os.path.join(API_LOG_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(response_body, f, ensure_ascii=False, indent=2)
        
        logger.bind(tag=TAG).info(f"响应体已保存到: {filepath}")
    except Exception as e:
        logger.bind(tag=TAG).error(f"保存响应体失败: {e}")


def call_weather_api(
    biz_type: str,
    params: Dict,
    req_id: str,
    push_browser: bool = False
) -> Dict:
    """
    调用气象数据查询接口
    
    Args:
        biz_type: 业务类型（REAL_TIME 或 WEATHER）
        params: 参数字典
        req_id: 请求ID
        push_browser: 是否推送浏览器
    
    Returns:
        符合接口文档格式的响应字典
    """
    # 构建完整请求体
    request_body = {
        "biz_type": biz_type,
        "req_id": req_id,
        "params": params,
        "push_browser": push_browser
    }
    
    # 保存请求体到文件
    _save_request_to_file(request_body, req_id)
    
    if USE_REAL_API:
        # 后续实现：调用真实GRPC接口
        response = _call_real_grpc_api(biz_type, params, req_id, push_browser)
    else:
        # 当前：使用模拟数据（从SQLite读取）
        response = query_weather_data(biz_type, params, req_id, push_browser)
    
    # 保存响应体到文件
    _save_response_to_file(response, req_id)
    
    return response


def _call_real_grpc_api(
    biz_type: str,
    params: Dict,
    req_id: str,
    push_browser: bool = False
) -> Dict:
    """
    调用真实GRPC接口（后续实现）
    
    Args:
        biz_type: 业务类型
        params: 参数字典
        req_id: 请求ID
        push_browser: 是否推送浏览器
    
    Returns:
        接口响应字典
    """
    # TODO: 实现真实GRPC调用
    # 1. 建立GRPC连接
    # 2. 构建请求
    # 3. 发送请求
    # 4. 解析响应
    # 5. 返回标准格式
    
    logger.bind(tag=TAG).info("调用真实GRPC接口（待实现）")
    
    # 临时返回错误
    return {
        "code": 500,
        "message": "真实API调用功能待实现",
        "data": {"req_id": req_id}
    }


def call_page_redirect_api(
    target_page: str,
    req_id: str
) -> Dict:
    """
    调用页面跳转接口
    
    Args:
        target_page: 目标页面枚举值
        req_id: 请求ID
    
    Returns:
        接口响应字典
    """
    # TODO: 实现页面跳转接口调用
    logger.bind(tag=TAG).info(f"页面跳转: {target_page}")
    
    return {
        "code": 200,
        "message": target_page,
        "req_id": req_id
    }

