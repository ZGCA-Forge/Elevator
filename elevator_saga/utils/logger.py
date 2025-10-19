#!/usr/bin/env python3
"""
Unified logging system for Elevator Saga
统一的日志系统 - 支持多级别、带颜色的日志输出
"""
import os
import sys
from enum import Enum
from typing import Optional


class LogLevel(Enum):
    """日志级别枚举"""

    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3

    @classmethod
    def from_string(cls, level_str: str) -> "LogLevel":
        """从字符串转换为日志级别"""
        level_map = {
            "DEBUG": cls.DEBUG,
            "INFO": cls.INFO,
            "WARNING": cls.WARNING,
            "ERROR": cls.ERROR,
        }
        return level_map.get(level_str.upper(), cls.DEBUG)


class Color:
    """ANSI颜色代码"""

    # 基础颜色
    RESET = "\033[0m"
    BOLD = "\033[1m"

    # 前景色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # 亮色
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


class Logger:
    """统一日志记录器"""

    def __init__(self, name: str = "ElevatorSaga", min_level: LogLevel = LogLevel.INFO, use_color: bool = True):
        """
        初始化日志记录器

        Args:
            name: 日志记录器名称
            min_level: 最低日志级别
            use_color: 是否使用颜色
        """
        self.name = name
        self.min_level = min_level
        self.use_color = use_color and sys.stdout.isatty()

        # 日志级别对应的颜色
        self.level_colors = {
            LogLevel.DEBUG: Color.BRIGHT_BLACK,
            LogLevel.INFO: Color.BRIGHT_CYAN,
            LogLevel.WARNING: Color.BRIGHT_YELLOW,
            LogLevel.ERROR: Color.BRIGHT_RED,
        }

        # 日志级别对应的标签
        self.level_labels = {
            LogLevel.DEBUG: "DEBUG",
            LogLevel.INFO: "INFO",
            LogLevel.WARNING: "WARNING",
            LogLevel.ERROR: "ERROR",
        }

    def _format_message(self, level: LogLevel, message: str, prefix: Optional[str] = None) -> str:
        """
        格式化日志消息

        Args:
            level: 日志级别
            message: 消息内容
            prefix: 可选的前缀（如模块名）

        Returns:
            格式化后的消息
        """
        level_label = self.level_labels[level]

        if self.use_color:
            color = self.level_colors[level]
            level_str = f"{color}{level_label:8}{Color.RESET}"
        else:
            level_str = f"{level_label:8}"

        if prefix:
            prefix_str = f"[{prefix}] "
        else:
            prefix_str = ""

        return f"{level_str} {prefix_str}{message}"

    def _log(self, level: LogLevel, message: str, prefix: Optional[str] = None) -> None:
        """
        记录日志

        Args:
            level: 日志级别
            message: 消息内容
            prefix: 可选的前缀
        """
        if level.value < self.min_level.value:
            return

        formatted = self._format_message(level, message, prefix)
        print(formatted, flush=True)

    def debug(self, message: str, prefix: Optional[str] = None) -> None:
        """记录DEBUG级别日志"""
        self._log(LogLevel.DEBUG, message, prefix)

    def info(self, message: str, prefix: Optional[str] = None) -> None:
        """记录INFO级别日志"""
        self._log(LogLevel.INFO, message, prefix)

    def warning(self, message: str, prefix: Optional[str] = None) -> None:
        """记录WARNING级别日志"""
        self._log(LogLevel.WARNING, message, prefix)

    def error(self, message: str, prefix: Optional[str] = None) -> None:
        """记录ERROR级别日志"""
        self._log(LogLevel.ERROR, message, prefix)

    def set_level(self, level: LogLevel) -> None:
        """设置最低日志级别"""
        self.min_level = level


# 全局日志记录器实例
_global_logger: Optional[Logger] = None


def _get_default_log_level() -> LogLevel:
    """从环境变量获取默认日志级别，默认为DEBUG"""
    env_level = os.environ.get("ELEVATOR_LOG_LEVEL", "DEBUG")
    return LogLevel.from_string(env_level)


def get_logger(name: str = "ElevatorSaga", min_level: Optional[LogLevel] = None) -> Logger:
    """
    获取全局日志记录器

    Args:
        name: 日志记录器名称
        min_level: 最低日志级别，如果为None则从环境变量读取（默认DEBUG）

    Returns:
        Logger实例
    """
    global _global_logger
    if _global_logger is None:
        if min_level is None:
            min_level = _get_default_log_level()
        _global_logger = Logger(name, min_level)
    return _global_logger


def set_log_level(level: LogLevel) -> None:
    """设置全局日志级别"""
    logger = get_logger()
    logger.set_level(level)


# 便捷函数
def debug(message: str, prefix: Optional[str] = None) -> None:
    """记录DEBUG日志"""
    get_logger().debug(message, prefix)


def info(message: str, prefix: Optional[str] = None) -> None:
    """记录INFO日志"""
    get_logger().info(message, prefix)


def warning(message: str, prefix: Optional[str] = None) -> None:
    """记录WARNING日志"""
    get_logger().warning(message, prefix)


def error(message: str, prefix: Optional[str] = None) -> None:
    """记录ERROR日志"""
    get_logger().error(message, prefix)
