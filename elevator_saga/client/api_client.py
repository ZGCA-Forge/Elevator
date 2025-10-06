#!/usr/bin/env python3
"""
Unified API Client for Elevator Saga
使用统一数据模型的客户端API封装
"""
import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from elevator_saga.core.models import (
    ElevatorState,
    FloorState,
    GoToFloorCommand,
    PassengerInfo,
    PerformanceMetrics,
    SimulationEvent,
    SimulationState,
    StepResponse,
)
from elevator_saga.utils.debug import debug_log


class ElevatorAPIClient:
    """统一的电梯API客户端"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        # 缓存相关字段
        self._cached_state: Optional[SimulationState] = None
        self._cached_tick: int = -1
        self._tick_processed: bool = False  # 标记当前tick是否已处理完成
        debug_log(f"API Client initialized for {self.base_url}")

    def get_state(self, force_reload: bool = False) -> SimulationState:
        """获取模拟状态

        Args:
            force_reload: 是否强制重新加载，忽略缓存
        """
        # 如果不强制重载且缓存有效（当前tick未处理完成），返回缓存
        if not force_reload and self._cached_state is not None and not self._tick_processed:
            return self._cached_state

        # debug_log(f"Fetching new state (force_reload={force_reload}, tick_processed={self._tick_processed})")
        response_data = self._send_get_request("/api/state")
        if "error" not in response_data:
            # 直接使用服务端返回的真实数据创建SimulationState
            elevators = [ElevatorState.from_dict(e) for e in response_data.get("elevators", [])]
            floors = [FloorState.from_dict(f) for f in response_data.get("floors", [])]

            # 使用服务端返回的passengers和metrics数据
            passengers_data = response_data.get("passengers", {})
            if isinstance(passengers_data, dict) and "completed" in passengers_data:
                # 如果是PassengerSummary格式，则创建空的passengers字典
                passengers: Dict[int, PassengerInfo] = {}
            else:
                # 如果是真实的passengers数据，则转换
                passengers = {
                    int(k): PassengerInfo.from_dict(v) for k, v in passengers_data.items() if isinstance(v, dict)
                }

            # 使用服务端返回的metrics数据
            metrics_data = response_data.get("metrics", {})
            if metrics_data:
                # 直接从字典创建PerformanceMetrics对象
                metrics = PerformanceMetrics.from_dict(metrics_data)
            else:
                metrics = PerformanceMetrics()

            simulation_state = SimulationState(
                tick=response_data.get("tick", 0),
                elevators=elevators,
                floors=floors,
                passengers=passengers,
                metrics=metrics,
                events=[],
            )

            # 更新缓存
            self._cached_state = simulation_state
            self._cached_tick = simulation_state.tick
            self._tick_processed = False  # 重置处理标志，表示新tick开始

            return simulation_state
        else:
            raise RuntimeError(f"Failed to get state: {response_data.get('error')}")

    def mark_tick_processed(self) -> None:
        """标记当前tick处理完成，使缓存在下次get_state时失效"""
        self._tick_processed = True

    def step(self, ticks: int = 1) -> StepResponse:
        """执行步进"""
        response_data = self._send_post_request("/api/step", {"ticks": ticks})

        if "error" not in response_data:
            # 使用服务端返回的真实数据
            events_data = response_data.get("events", [])
            events = []
            for event_data in events_data:
                # 手动转换type字段从字符串到EventType枚举
                event_dict = event_data.copy()
                if "type" in event_dict and isinstance(event_dict["type"], str):
                    # 尝试将字符串转换为EventType枚举
                    try:
                        from elevator_saga.core.models import EventType

                        event_dict["type"] = EventType(event_dict["type"])
                    except ValueError:
                        debug_log(f"Unknown event type: {event_dict['type']}")
                        continue
                events.append(SimulationEvent.from_dict(event_dict))

            step_response = StepResponse(
                success=True,
                tick=response_data.get("tick", 0),
                events=events,
            )

            # debug_log(f"Step response: tick={step_response.tick}, events={len(events)}")
            return step_response
        else:
            raise RuntimeError(f"Step failed: {response_data.get('error')}")

    def send_elevator_command(self, command: GoToFloorCommand) -> bool:
        """发送电梯命令"""
        endpoint = self._get_elevator_endpoint(command)
        debug_log(
            f"Sending elevator command: {command.command_type} to elevator {command.elevator_id} To:F{command.floor}"
        )

        response_data = self._send_post_request(endpoint, command.parameters)

        if response_data.get("success"):
            return bool(response_data["success"])
        else:
            raise RuntimeError(f"Command failed: {response_data.get('error_message')}")

    def go_to_floor(self, elevator_id: int, floor: int, immediate: bool = False) -> bool:
        """电梯前往指定楼层"""
        command = GoToFloorCommand(elevator_id=elevator_id, floor=floor, immediate=immediate)

        try:
            response = self.send_elevator_command(command)
            return response
        except Exception as e:
            debug_log(f"Go to floor failed: {e}")
            return False

    def _get_elevator_endpoint(self, command: GoToFloorCommand) -> str:
        """获取电梯命令端点"""
        base = f"/api/elevators/{command.elevator_id}"

        if isinstance(command, GoToFloorCommand):
            return f"{base}/go_to_floor"

    def _send_get_request(self, endpoint: str) -> Dict[str, Any]:
        """发送GET请求"""
        url = f"{self.base_url}{endpoint}"
        # debug_log(f"GET {url}")

        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                data: Dict[str, Any] = json.loads(response.read().decode("utf-8"))
                # debug_log(f"GET {url} -> {response.status}")
                return data
        except urllib.error.URLError as e:
            raise RuntimeError(f"GET {url} failed: {e}")

    def reset(self) -> bool:
        """重置模拟"""
        try:
            response_data = self._send_post_request("/api/reset", {})
            success = bool(response_data.get("success", False))
            if success:
                # 清空缓存，因为状态已重置
                self._cached_state = None
                self._cached_tick = -1
                self._tick_processed = False
                debug_log("Cache cleared after reset")
            return success
        except Exception as e:
            debug_log(f"Reset failed: {e}")
            return False

    def next_traffic_round(self, full_reset: bool = False) -> bool:
        """切换到下一个流量文件"""
        try:
            response_data = self._send_post_request("/api/traffic/next", {"full_reset": full_reset})
            success = bool(response_data.get("success", False))
            if success:
                # 清空缓存，因为流量文件已切换，状态会改变
                self._cached_state = None
                self._cached_tick = -1
                self._tick_processed = False
                debug_log("Cache cleared after traffic round switch")
            return success
        except Exception as e:
            debug_log(f"Next traffic round failed: {e}")
            return False

    def get_traffic_info(self) -> Optional[Dict[str, Any]]:
        """获取当前流量文件信息"""
        try:
            response_data = self._send_get_request("/api/traffic/info")
            if "error" not in response_data:
                return response_data
            else:
                debug_log(f"Get traffic info failed: {response_data.get('error')}")
                return None
        except Exception as e:
            debug_log(f"Get traffic info failed: {e}")
            return None

    def _send_post_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """发送POST请求"""
        url = f"{self.base_url}{endpoint}"
        request_body = json.dumps(data).encode("utf-8")

        # debug_log(f"POST {url} with data: {data}")

        req = urllib.request.Request(url, data=request_body, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=600) as response:
                response_data: Dict[str, Any] = json.loads(response.read().decode("utf-8"))
                # debug_log(f"POST {url} -> {response.status}")
                return response_data
        except urllib.error.URLError as e:
            raise RuntimeError(f"POST {url} failed: {e}")
