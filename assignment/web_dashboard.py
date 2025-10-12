#!/usr/bin/env python3
"""
简单的电梯状态 Web 可视化面板

通过 Flask 提供一个轻量级页面，定期查询模拟器状态并展示：
1. 当前 tick 与关键指标
2. 每部电梯的楼层、目标、乘客数量
3. 各楼层等待人数
"""
from __future__ import annotations

import atexit
import os
import subprocess
import sys
import threading
from typing import Dict, List, Optional, Tuple

from flask import Flask, jsonify, send_from_directory
import logging

from elevator_saga.client.api_client import ElevatorAPIClient
from elevator_saga.core.models import PassengerStatus

app = Flask(__name__, static_folder=None)

_controller_lock = threading.Lock()
_controller_process: Optional[subprocess.Popen[bytes]] = None


def _create_api_client() -> ElevatorAPIClient:
    """创建新的 API 客户端实例，避免缓存状态带来的过期数据"""
    return ElevatorAPIClient("http://127.0.0.1:8000", verbose=False)


def _controller_running() -> bool:
    """检查调度算法是否正在运行"""
    global _controller_process
    if _controller_process is None:
        return False
    if _controller_process.poll() is not None:
        # 进程已经退出，清理引用
        _controller_process = None
        return False
    return True


def _start_controller() -> Tuple[bool, str]:
    """启动调度算法进程"""
    global _controller_process
    with _controller_lock:
        if _controller_running():
            return False, "调度算法正在运行，无需重复启动"
        client = _create_api_client()
        try:
            client.reset()
        except Exception as exc:  # pragma: no cover
            app.logger.warning("重置模拟器失败: %s", exc)
        env = os.environ.copy()
        try:
            process = subprocess.Popen([sys.executable, "-m", "assignment.main"], env=env)
            _controller_process = process
            app.logger.info("调度算法已启动，PID=%s", process.pid)
            return True, "调度算法已启动"
        except Exception as exc:  # pragma: no cover - 启动失败极少发生
            app.logger.exception("启动调度算法失败: %s", exc)
            return False, f"启动调度算法失败: {exc}"


def _stop_controller(force: bool = False) -> Tuple[bool, str]:
    """停止调度算法进程"""
    global _controller_process
    with _controller_lock:
        if not _controller_running():
            return False, "调度算法未在运行"
        assert _controller_process is not None  # for mypy/pylance
        try:
            _controller_process.terminate()
            _controller_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if force:
                _controller_process.kill()
            else:
                return False, "调度算法停止超时，请稍后重试"
        finally:
            app.logger.info("调度算法已停止")
            _controller_process = None
        return True, "调度算法已停止"


def _collect_state() -> Dict[str, object]:
    """从模拟器获取当前状态并提取关键信息"""
    client = _create_api_client()
    state = client.get_state(force_reload=True)
    elevators: List[Dict[str, object]] = []
    for elevator in state.elevators:
        elevators.append(
            {
                "id": elevator.id,
                "current": elevator.current_floor_float,
                "target": elevator.target_floor,
                "status": elevator.run_status.value,
                "direction": elevator.target_floor_direction.value,
                "passenger_count": len(elevator.passengers),
                "pressed_floors": elevator.pressed_floors,
                "load_factor": round(elevator.load_factor, 2),
            }
        )

    floors: List[Dict[str, object]] = []
    for floor in state.floors:
        floors.append(
            {
                "floor": floor.floor,
                "up_waiting": len(floor.up_queue),
                "down_waiting": len(floor.down_queue),
                "total": floor.total_waiting,
            }
        )

    passengers = list(state.passengers.values())
    completed = [psg for psg in passengers if psg.status == PassengerStatus.COMPLETED]

    def _current_floor_wait(psg: object) -> float:
        if psg.status == PassengerStatus.WAITING:
            return max(state.tick - psg.arrive_tick, 0)
        if psg.status == PassengerStatus.IN_ELEVATOR:
            return max(psg.pickup_tick - psg.arrive_tick, 0)
        return max(psg.floor_wait_time, 0)

    def _current_arrival_wait(psg: object) -> float:
        if psg.status == PassengerStatus.WAITING:
            return max(state.tick - psg.arrive_tick, 0)
        if psg.status == PassengerStatus.IN_ELEVATOR:
            return max(state.tick - psg.arrive_tick, 0)
        return max(psg.arrival_wait_time, 0)

    floor_waits = [_current_floor_wait(psg) for psg in passengers]
    arrival_waits = [_current_arrival_wait(psg) for psg in passengers]

    def _average(values: List[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    def _percentile(values: List[float], percentile: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * percentile
        f = int(k)
        c = min(f + 1, len(sorted_vals) - 1)
        if f == c:
            return round(sorted_vals[f], 2)
        d0 = sorted_vals[f] * (c - k)
        d1 = sorted_vals[c] * (k - f)
        return round(d0 + d1, 2)

    metrics = {
        "total_passengers": len(passengers),
        "completed_passengers": len(completed),
        "average_floor_wait_time": _average(floor_waits),
        "p95_floor_wait_time": _percentile(floor_waits, 0.95),
        "average_arrival_wait_time": _average(arrival_waits),
        "p95_arrival_wait_time": _percentile(arrival_waits, 0.95),
    }

    return {
        "tick": state.tick,
        "elevators": elevators,
        "floors": floors,
        "metrics": metrics,
        "controller_running": _controller_running(),
    }


@app.route("/dashboard/state")
def dashboard_state() -> object:
    """返回可视化需要的关键信息"""
    snapshot = _collect_state()
    return jsonify(snapshot)


@app.route("/dashboard/start", methods=["POST"])
def dashboard_start() -> object:
    """启动调度算法"""
    success, message = _start_controller()
    status_code = 200 if success else 409
    return jsonify({"success": success, "message": message, "controller_running": _controller_running()}), status_code


@app.route("/dashboard/stop", methods=["POST"])
def dashboard_stop() -> object:
    """停止调度算法"""
    success, message = _stop_controller()
    status_code = 200 if success else 409
    return jsonify({"success": success, "message": message, "controller_running": _controller_running()}), status_code


@app.route("/")
def dashboard_root() -> object:
    """返回静态页面"""
    static_dir = os.path.join(os.path.dirname(__file__), "web_static")
    return send_from_directory(static_dir, "index.html")


@app.route("/static/<path:path>")
def dashboard_static(path: str) -> object:
    static_dir = os.path.join(os.path.dirname(__file__), "web_static")
    return send_from_directory(static_dir, path)


def _atexit_cleanup() -> None:
    try:
        _stop_controller(force=True)
    except Exception:
        pass


atexit.register(_atexit_cleanup)


def main() -> None:
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host="127.0.0.1", port=8050, debug=False, threaded=True)


if __name__ == "__main__":
    main()
