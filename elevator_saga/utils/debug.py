#!/usr/bin/env python3
"""
Debug utilities for Elevator Saga
调试工具模块
"""

# Global debug flag
_debug_enabled: bool = True


def set_debug_mode(enabled: bool) -> None:
    """启用或禁用调试模式"""
    global _debug_enabled
    _debug_enabled = enabled


def debug_log(message: str) -> None:
    """输出调试信息（如果启用了调试模式）"""
    if _debug_enabled:
        print(f"[DEBUG] {message}", flush=True)


def is_debug_enabled() -> bool:
    """检查是否启用了调试模式"""
    return _debug_enabled
