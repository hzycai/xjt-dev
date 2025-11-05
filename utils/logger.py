import os
import sys
from loguru import logger

_logger = None
def setup_logging():
    """从配置文件中读取日志配置，并设置日志输出格式和级别"""
 
    log_format = "<green>{time:YYMMDD HH:mm:ss}</green> <level>{level}</level>-<light-green>{message}</light-green>"
    log_format_file = "{time:YYYY-MM-DD HH:mm:ss}  - {name} - {level}  - {message}"
    log_level= "DEBUG"
    log_dir = "tmp"
    log_file = "server.log"
    data_dir = "data"
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    # 配置日志输出
    logger.remove()

    # 输出到控制台
    logger.add(sys.stdout, format=log_format, level=log_level)

    # 输出到文件
    logger.add(os.path.join(log_dir, log_file), format=log_format_file, level=log_level)

    return logger

def get_logger():
    """
    获取 logger 对象，如果尚未创建则调用 setup_logging 创建
    """
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger