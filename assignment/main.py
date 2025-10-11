#!/usr/bin/env python3
"""
作业运行入口
"""
from assignment.baseline_controller import GreedyNearestController


def main() -> None:
    controller = GreedyNearestController(debug=True)
    controller.start()


if __name__ == "__main__":
    main()

