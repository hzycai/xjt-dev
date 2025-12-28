import sys
import os
from enum import Enum
from loguru import logger

_logger = None
class AuthState(Enum):
    UNREGISTERED = 0
    SUCCESS = 1
    FAILED = 2
    UNBIND = 3
    FOBBIDDEN = 4   

class AudioReplaceType(Enum):
    SILENCE = 0
    BEEP = 1


def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable) if not hasattr(sys, '_MEIPASS') else sys._MEIPASS
        relative_path = relative_path.replace('/', '\\')
        return f"{base_dir}\\{relative_path}"
    else:
        # 开发环境
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    
        return os.path.join(base_dir, relative_path)
def setup_logging():
    """从配置文件中读取日志配置，并设置日志输出格式和级别"""
 
    log_format_file = "{time:YYYY-MM-DD HH:mm:ss}  - {name} - {level}  - {message}"
    log_level= "DEBUG"
    log_file = "server.log"
    # 输出到文件
    logger.add(resource_path(log_file), format=log_format_file, level=log_level)

    return logger

def get_logger():
    """
    获取 logger 对象，如果尚未创建则调用 setup_logging 创建
    """
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger

def load_sensitive_words():
    """Load sensitive words from file"""
    log = get_logger()
    sensitive_set = set()
    sen_words_file_path = resource_path("config/sensitive_words.txt")
    print(f"sen_words_file_path==>{sen_words_file_path}")
    try:
        # Try to load sensitive words from external file
        with open(sen_words_file_path, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word:  # Ignore empty lines
                    sensitive_set.add(word)
        log.info(f"Loaded {len(sensitive_set)} sensitive words from file: {sen_words_file_path}")
    except FileNotFoundError:
        # If file doesn't exist, use default sensitive words
        log.error("sensitive_words.txt not found, using default sensitive words")
        return None
    except Exception as e:
        log.error(f"Error loading sensitive words: {e}")
        # Use default sensitive words in case of error
        return None
    return sensitive_set
