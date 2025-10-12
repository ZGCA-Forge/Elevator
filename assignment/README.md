# 作业初版说明

## 项目概述

本次结对作业需要实现一个能够接入 `elevator_saga` 模拟器的电梯调度算法。当前仓库提供了官方基础框架，本初版在其基础上补充了一个可运行的调度器，方便后续迭代性能与功能。

## 调度策略简介

- 算法名称：最近楼层优先的贪心派梯策略 `GreedyNearestController`
- 核心思路：
  - 监听乘客呼叫事件，以乘客 ID 为唯一标识管理等待队列；
  - 若电梯已有乘客，优先送达最近的乘客目的地；
  - 电梯空载时，从等待队列中挑选距离当前楼层最近、尚未被其他电梯抢占的呼叫；
  - 当系统无任何等待呼叫时，电梯回到首层待命。

该策略可以高效完成小规模流量的运输任务，便于后续扩展更复杂的调度逻辑（比如方向预测、容量约束、优先级管理等）。

## 关键代码结构

| 路径 | 作用 |
| ---- | ---- |
| `assignment/baseline_controller.py` | 调度核心逻辑，实现 `GreedyNearestController` |
| `assignment/main.py` | 程序入口，启动调度器 |
| `assignment/run_server.py` | 以非调试模式启动模拟器 |
| `assignment/web_dashboard.py` | Web 可视化面板后端 |
| `assignment/web_static/` | 前端静态资源（HTML/CSS/JS） |
| `assignment/__init__.py` | 作业包初始化 |

## 一键启动（推荐）

```bash
chmod +x start.sh
./start.sh
```

- `start.sh` 会自动创建虚拟环境、安装依赖，并依次启动模拟器、算法控制器；
- 默认开启 Web 可视化面板（监听 `http://127.0.0.1:8050`），请在页面点击“启动调度”按钮以开始运行；若不需要面板可使用 `--no-dashboard`（脚本将直接在终端运行调度算法）；
- 调度算法默认以 0.2s/tick 的速度推进，便于在面板中观察状态，可通过环境变量 `ASSIGNMENT_TICK_DELAY=0.0` 调整；
- 每次运行结束后按钮会恢复为“启动调度”，可直接再次点击开始新一轮模拟；
- 若修改了依赖，可以运行 `./start.sh --reinstall` 强制重新安装。

## 手动运行

1. 确认已安装模拟器依赖：

   ```bash
   pip install -e .
   ```

   > 需要先启动模拟器：`python -m elevator_saga.server.simulator`

2. 启动初版调度算法：

   ```bash
   python -m assignment.main
   ```

3. 启动/关闭调度：

   - 默认通过可视化页面里的“启动调度”按钮触发；
   - 如果未启用面板，可直接执行：

   ```bash
   python -m assignment.web_dashboard
   ```

   浏览器访问 `http://127.0.0.1:8050`，点击界面按钮开始/停止调度；调度器运行时终端会输出事件流。

> 进阶控制：
> - 设置 `ASSIGNMENT_DEBUG=1` 可开启详细日志；
> - 设置 `ASSIGNMENT_TICK_DELAY=0.0` 让调度器快速运行（适合批量测试）。

## 后续优化方向

- 加入电梯容量与方向的动态判定，减少无效调度；
- 对高峰期流量进行建模，尝试批量派单或 SJF（Shortest Job First）策略；
- 结合图形化界面展示调度状态，辅助调试；
- 完善测试脚本与指标统计，量化等待时间指标。
