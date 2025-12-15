"""日志工具"""

import logging
from pathlib import Path

from rich.logging import RichHandler


def setup_logger(log_file: str = "netease_copy.log", level: int = logging.INFO):
    """
    设置日志器

    Args:
        log_file: 日志文件路径
        level: 日志级别
    """
    # 创建日志目录
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 配置根日志器
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_time=True, show_path=False)],
    )

    # 添加文件处理器
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logging.getLogger().addHandler(file_handler)

    # 降低 httpx 日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
