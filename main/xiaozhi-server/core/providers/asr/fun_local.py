import time
import os
import sys
import io
import psutil
from config.logger import setup_logging
from config.config_loader import get_internal_dir
from typing import Optional, Tuple, List
from core.providers.asr.base import ASRProviderBase
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
import shutil
from core.providers.asr.dto.dto import InterfaceType

TAG = __name__
logger = setup_logging()

MAX_RETRIES = 2
RETRY_DELAY = 1  # 重试延迟（秒）


# 捕获标准输出
class CaptureOutput:
    def __enter__(self):
        self._output = io.StringIO()
        self._original_stdout = sys.stdout
        sys.stdout = self._output

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self._original_stdout
        self.output = self._output.getvalue()
        self._output.close()

        # 将捕获到的内容通过 logger 输出
        if self.output:
            logger.bind(tag=TAG).info(self.output.strip())


class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        
        # 内存检测，要求大于2G
        min_mem_bytes = 2 * 1024 * 1024 * 1024
        total_mem = psutil.virtual_memory().total
        if total_mem < min_mem_bytes:
            logger.bind(tag=TAG).error(f"可用内存不足2G，当前仅有 {total_mem / (1024*1024):.2f} MB，可能无法启动FunASR")
        
        self.interface_type = InterfaceType.LOCAL
        
        # 处理模型目录路径
        model_dir = config.get("model_dir")
        # 判断是模型名称（如paraformer-zh）还是本地路径
        # 如果是模型名称，直接使用；如果是路径，需要拼接内部目录
        if model_dir:
            # 检查是否是ModelScope模型名称（不包含路径分隔符且不以models/开头）
            if "/" not in model_dir and "\\" not in model_dir and not model_dir.startswith("models/"):
                # 这是模型名称，直接使用（FunASR会自动从ModelScope下载）
                self.model_dir = model_dir
            elif os.path.isabs(model_dir):
                # 绝对路径，直接使用
                self.model_dir = model_dir
            else:
                # 相对路径，拼接内部目录
                internal_dir = get_internal_dir()
                self.model_dir = os.path.join(internal_dir, model_dir)
        else:
            self.model_dir = model_dir
            
        self.output_dir = config.get("output_dir")  # 修正配置键名
        self.delete_audio_file = delete_audio_file

        # 加载热词文件
        hotword_file = config.get("hotword_file", "")
        self.hotwords = None
        if hotword_file:
            # 处理相对路径和绝对路径
            if not os.path.isabs(hotword_file):
                internal_dir = get_internal_dir()
                hotword_path = os.path.join(internal_dir, hotword_file)
            else:
                hotword_path = hotword_file
            
            # 读取热词文件
            if os.path.exists(hotword_path):
                try:
                    with open(hotword_path, 'r', encoding='utf-8') as f:
                        hotwords_list = [line.strip() for line in f if line.strip()]
                        if hotwords_list:
                            # 将"地温"相关词汇放在最前面，并保留重复以增加权重
                            diwen_words = [w for w in hotwords_list if '地温' in w]
                            other_words = [w for w in hotwords_list if '地温' not in w]
                            # 合并：地温相关词汇在前（保留重复），其他在后（去重）
                            seen_other = set()
                            unique_other = []
                            for word in other_words:
                                if word not in seen_other:
                                    seen_other.add(word)
                                    unique_other.append(word)
                            
                            # 地温词汇保留重复，其他词汇去重
                            ordered_hotwords = diwen_words + unique_other
                            
                            # FunASR支持列表格式，优先使用列表
                            self.hotwords = ordered_hotwords
                            # 同时保留字符串格式作为备选（字符串格式会自动去重）
                            unique_hotwords = list(dict.fromkeys(ordered_hotwords))  # 保持顺序的去重
                            self.hotwords_str = ' '.join(unique_hotwords)
                            logger.bind(tag=TAG).info(f"成功加载热词文件: {hotword_path}，共 {len(ordered_hotwords)} 个热词（含重复），{len(unique_hotwords)} 个唯一热词")
                            logger.bind(tag=TAG).debug(f"热词列表（前10个）: {ordered_hotwords[:10]}")
                        else:
                            logger.bind(tag=TAG).warning(f"热词文件为空: {hotword_path}")
                except Exception as e:
                    logger.bind(tag=TAG).error(f"读取热词文件失败: {hotword_path} | 错误: {e}")
            else:
                logger.bind(tag=TAG).warning(f"热词文件不存在: {hotword_path}")

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        with CaptureOutput():
            self.model = AutoModel(
                model=self.model_dir,
                vad_kwargs={"max_single_segment_time": 30000},
                disable_update=True,
                hub="hf",
                # device="cuda:0",  # 启用GPU加速
            )

    async def speech_to_text(
        self, opus_data: List[bytes], session_id: str, audio_format="opus"
    ) -> Tuple[Optional[str], Optional[str]]:
        """语音转文本主处理逻辑"""
        file_path = None
        retry_count = 0

        while retry_count < MAX_RETRIES:
            try:
                # 合并所有opus数据包
                if audio_format == "pcm":
                    pcm_data = opus_data
                else:
                    pcm_data = self.decode_opus(opus_data)

                combined_pcm_data = b"".join(pcm_data)

                # 检查磁盘空间
                if not self.delete_audio_file:
                    free_space = shutil.disk_usage(self.output_dir).free
                    if free_space < len(combined_pcm_data) * 2:  # 预留2倍空间
                        raise OSError("磁盘空间不足")

                # 判断是否保存为WAV文件
                if self.delete_audio_file:
                    pass
                else:
                    file_path = self.save_audio_to_file(pcm_data, session_id)

                # 语音识别
                start_time = time.time()
                # 构建生成参数
                generate_params = {
                    "input": combined_pcm_data,
                    "cache": {},
                    "language": "auto",
                    "use_itn": True,
                    "batch_size_s": 60,
                }
                # 如果配置了热词，添加到参数中
                if self.hotwords:
                    # FunASR的hotword参数支持字符串格式（空格分隔）或列表格式
                    # 根据FunASR文档，字符串格式更通用，优先使用字符串格式
                    if isinstance(self.hotwords, list):
                        # 转换为字符串格式（空格分隔）
                        hotword_str = ' '.join(self.hotwords)
                        generate_params["hotword"] = hotword_str
                        logger.bind(tag=TAG).info(f"使用热词进行识别，热词数量: {len(self.hotwords)}（显示前5个示例: {self.hotwords[:5]}）")
                    else:
                        # 已经是字符串格式
                        generate_params["hotword"] = self.hotwords
                        logger.bind(tag=TAG).info(f"使用热词字符串进行识别: {self.hotwords[:100]}...")
                
                # 记录传入的参数（用于调试）
                if self.hotwords:
                    logger.bind(tag=TAG).debug(f"调用generate参数: {list(generate_params.keys())}, hotword存在: {'hotword' in generate_params}")
                
                result = self.model.generate(**generate_params)
                text = rich_transcription_postprocess(result[0]["text"])
                # 去除识别结果中的空格（SeACo-Paraformer有时会在字符间添加空格）
                text = text.replace(" ", "").replace("  ", "")
                logger.bind(tag=TAG).debug(
                    f"语音识别耗时: {time.time() - start_time:.3f}s | 结果: {text}"
                )
                
                # 如果识别结果包含"低温"但热词中有"地温"，记录警告
                if self.hotwords and "低温" in text and "地温" in str(self.hotwords):
                    logger.bind(tag=TAG).warning(f"识别结果可能错误: '{text}' (热词已配置但可能未生效)")

                return text, file_path

            except OSError as e:
                retry_count += 1
                if retry_count >= MAX_RETRIES:
                    logger.bind(tag=TAG).error(
                        f"语音识别失败（已重试{retry_count}次）: {e}", exc_info=True
                    )
                    return "", file_path
                logger.bind(tag=TAG).warning(
                    f"语音识别失败，正在重试（{retry_count}/{MAX_RETRIES}）: {e}"
                )
                time.sleep(RETRY_DELAY)

            except Exception as e:
                logger.bind(tag=TAG).error(f"语音识别失败: {e}", exc_info=True)
                return "", file_path

            finally:
                # 文件清理逻辑
                if self.delete_audio_file and file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.bind(tag=TAG).debug(f"已删除临时音频文件: {file_path}")
                    except Exception as e:
                        logger.bind(tag=TAG).error(
                            f"文件删除失败: {file_path} | 错误: {e}"
                        )
