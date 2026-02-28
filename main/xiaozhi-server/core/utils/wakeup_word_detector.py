"""
唤醒词检测器
用于检测用户语音中是否包含唤醒词，并管理唤醒状态
"""
from typing import Tuple, Optional
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class WakeupWordDetector:
    """唤醒词检测器"""
    
    def __init__(self, config: dict):
        """
        初始化唤醒词检测器
        
        Args:
            config: 唤醒词配置字典，包含：
                - enabled: 是否启用唤醒词功能
                - name: AI的名称（用于生成"你好xx"格式的唤醒词）
                - case_sensitive: 是否区分大小写
                - partial_match: 是否支持部分匹配
        """
        self.enabled = config.get("enabled", False)
        self.ai_name = config.get("name", "小智")  # AI的名称，用于生成唤醒词
        self.case_sensitive = config.get("case_sensitive", False)
        self.partial_match = config.get("partial_match", True)
        
        # 生成唤醒词列表（支持多种格式）
        self.wakeup_words = self._generate_wakeup_words()
        
        if self.enabled:
            logger.bind(tag=TAG).info(
                f"唤醒词检测器已启用，AI名称: {self.ai_name}，唤醒词: {self.wakeup_words}"
            )
        else:
            logger.bind(tag=TAG).info("唤醒词检测器未启用")
    
    def _generate_wakeup_words(self) -> list:
        """
        生成唤醒词列表
        
        根据AI名称生成"你好xx"格式的唤醒词
        例如：如果name是"小智"，则生成["你好小智", "你好 小智"]等
        """
        if not self.ai_name:
            return []
        
        words = []
        # 基本格式：你好xx
        words.append(f"你好{self.ai_name}")
        # 带空格格式：你好 xx
        words.append(f"你好 {self.ai_name}")
        # 带逗号格式：你好，xx
        words.append(f"你好，{self.ai_name}")
        # 带感叹号格式：你好xx！
        words.append(f"你好{self.ai_name}！")
        
        return words
    
    def check_wakeup_word(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        检查文本是否包含唤醒词
        
        Args:
            text: 待检测的文本
        
        Returns:
            (是否检测到唤醒词, 匹配的唤醒词)
        """
        if not self.enabled or not text or not text.strip():
            return False, None
        
        # 预处理文本
        check_text = text.strip()
        if not self.case_sensitive:
            check_text = check_text.lower()
        
        # 检查每个唤醒词
        for word in self.wakeup_words:
            check_word = word.strip()
            if not self.case_sensitive:
                check_word = check_word.lower()
            
            if self.partial_match:
                # 部分匹配：文本中包含唤醒词即可
                if check_word in check_text:
                    logger.bind(tag=TAG).debug(f"检测到唤醒词（部分匹配）: {word} 在文本: {text}")
                    return True, word
            else:
                # 完全匹配：文本必须等于唤醒词
                if check_text == check_word:
                    logger.bind(tag=TAG).debug(f"检测到唤醒词（完全匹配）: {word}")
                    return True, word
        
        return False, None
    
    def get_greeting_message(self) -> str:
        """
        获取唤醒后的问候语（仅语音唤醒时使用）
        
        Returns:
            固定问候语："您好，请问有什么可以帮助您的？"
        """
        return "您好，请问有什么可以帮助您的？"
    
    def update_config(self, config: dict):
        """
        更新配置（用于运行时配置更新）
        
        Args:
            config: 新的配置字典
        """
        self.enabled = config.get("enabled", False)
        old_name = self.ai_name
        self.ai_name = config.get("name", "小智")
        self.case_sensitive = config.get("case_sensitive", False)
        self.partial_match = config.get("partial_match", True)
        
        # 如果名称改变，重新生成唤醒词
        if old_name != self.ai_name:
            self.wakeup_words = self._generate_wakeup_words()
            logger.bind(tag=TAG).info(
                f"唤醒词配置已更新，AI名称: {self.ai_name}，唤醒词: {self.wakeup_words}"
            )

