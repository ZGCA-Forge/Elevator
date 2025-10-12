#!/usr/bin/env python3
"""
作业运行入口
"""
import os

from assignment.baseline_controller import GreedyNearestController


def main() -> None:
    debug_env = os.environ.get("ASSIGNMENT_DEBUG", "").lower()
    debug_enabled = debug_env in {"1", "true", "yes", "on"}
    controller = GreedyNearestController(debug=debug_enabled)
    controller.start()


if __name__ == "__main__":
    main()
