#!/usr/bin/env python3
"""
Unified API Client for Elevator Saga
使用统一数据模型的客户端API封装
"""
import json
import os
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
from elevator_saga.utils.logger import debug, error, info, warning


class ElevatorAPIClient:
    """统一的电梯API客户端"""

    def __init__(self, base_url: str, client_type: str = "algorithm"):
        self.base_url = base_url.rstrip("/")
        # 客户端身份相关
        self.client_type = client_type
        self.client_id: Optional[str] = None
        # 缓存相关字段
        self._cached_state: Optional[SimulationState] = None
        self._cached_tick: int = -1
        self._tick_processed: bool = False  # 标记当前tick是否已处理完成
        debug(f"API Client initialized for {self.base_url} with type {self.client_type}", prefix="CLIENT")

        # 尝试自动注册
        self._auto_register()

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
        # 携带当前tick信息，用于优先级队列控制
        # 如果没有缓存的state，先获取一次
        if self._cached_state is None:
            self.get_state(force_reload=True)

        request_data = {"ticks": ticks}
        if self._cached_state is not None:
            request_data["current_tick"] = self._cached_state.tick

        response_data = self._send_post_request("/api/step", request_data)

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
                        warning(f"Unknown event type: {event_dict['type']}", prefix="CLIENT")
                        continue
                events.append(SimulationEvent.from_dict(event_dict))

            step_response = StepResponse(
                success=True,
                tick=response_data.get("tick", 0),
                events=events,
            )

            # 更新缓存的tick（保持其他状态不变，只更新tick）
            if self._cached_state is not None:
                self._cached_state.tick = step_response.tick

            # debug_log(f"Step response: tick={step_response.tick}, events={len(events)}")
            return step_response
        else:
            raise RuntimeError(f"Step failed: {response_data.get('error')}")

    def send_elevator_command(self, command: GoToFloorCommand) -> bool:
        """发送电梯命令"""
        # 客户端拦截：检查是否有权限发送控制命令
        if not self._can_send_command():
            warning(
                f"Client type '{self.client_type}' cannot send control commands. "
                f"Command ignored: {command.command_type} elevator {command.elevator_id} to floor {command.floor}",
                prefix="CLIENT",
            )
            # 不抛出错误，直接返回True（但实际未执行）
            return True

        endpoint = self._get_elevator_endpoint(command)
        debug(
            f"Sending elevator command: {command.command_type} to elevator {command.elevator_id} To:F{command.floor}",
            prefix="CLIENT",
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
            error(f"Go to floor failed: {e}", prefix="CLIENT")
            return False

    def _get_elevator_endpoint(self, command: GoToFloorCommand) -> str:
        """获取电梯命令端点"""
        base = f"/api/elevators/{command.elevator_id}"

        if isinstance(command, GoToFloorCommand):
            return f"{base}/go_to_floor"

    def _auto_register(self) -> None:
        """自动注册客户端"""
        try:
            # 从环境变量读取客户端类型（如果有的话）
            env_client_type = os.environ.get("ELEVATOR_CLIENT_TYPE")
            if env_client_type:
                self.client_type = env_client_type
                debug(f"Client type from environment: {self.client_type}", prefix="CLIENT")

            # 直接发送注册请求（不使用_send_post_request以避免循环依赖）
            url = f"{self.base_url}/api/client/register"
            request_body = json.dumps({}).encode("utf-8")
            headers = {"Content-Type": "application/json", "X-Client-Type": self.client_type}
            req = urllib.request.Request(url, data=request_body, headers=headers)

            with urllib.request.urlopen(req, timeout=60) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                if response_data.get("success"):
                    self.client_id = response_data.get("client_id")
                    info(f"Client registered successfully with ID: {self.client_id}", prefix="CLIENT")
                else:
                    warning(f"Client registration failed: {response_data.get('error')}", prefix="CLIENT")
        except Exception as e:
            error(f"Auto registration failed: {e}", prefix="CLIENT")

    def _can_send_command(self) -> bool:
        """检查客户端是否可以发送控制命令

        Returns:
            True: 如果是算法客户端或未注册客户端
            False: 如果是GUI客户端
        """
        # 算法客户端可以发送命令
        if self.client_type.lower() == "algorithm":
            return True
        # 未注册的客户端也可以发送命令（向后兼容）
        if self.client_id is None:
            return True
        # GUI客户端不能发送命令
        if self.client_type.lower() == "gui":
            return False
        # 其他未知类型，默认允许（向后兼容）
        return True

    def _get_request_headers(self) -> Dict[str, str]:
        """获取请求头，包含客户端身份信息"""
        headers = {"Content-Type": "application/json"}
        if self.client_id:
            headers["X-Client-ID"] = self.client_id
        headers["X-Client-Type"] = self.client_type
        return headers

    def _send_get_request(self, endpoint: str) -> Dict[str, Any]:
        """发送GET请求"""
        url = f"{self.base_url}{endpoint}"
        # todo: 全部更改为post
        # debug_log(f"GET {url}")

        try:
            headers = self._get_request_headers()
            # 对于GET请求，只添加客户端标识头
            req = urllib.request.Request(url, headers={k: v for k, v in headers.items() if k != "Content-Type"})
            with urllib.request.urlopen(req, timeout=60) as response:
                data: Dict[str, Any] = json.loads(response.read().decode("utf-8"))
                # debug_log(f"GET {url} -> {response.status}")
                return data
        except urllib.error.URLError as e:
            raise RuntimeError(f"GET {url} failed: {e}")

    def reset(self) -> bool:
        """重置模拟并重新注册客户端"""
        try:
            response_data = self._send_post_request("/api/reset", {})
            success = bool(response_data.get("success", False))
            if success:
                # 清空缓存，因为状态已重置
                self._cached_state = None
                self._cached_tick = -1
                self._tick_processed = False
                debug("Cache cleared after reset", prefix="CLIENT")

                # 重新注册客户端（因为服务器已清除客户端记录）
                self._auto_register()
                debug("Client re-registered after reset", prefix="CLIENT")
            return success
        except Exception as e:
            error(f"Reset failed: {e}", prefix="CLIENT")
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
                debug("Cache cleared after traffic round switch", prefix="CLIENT")
            return success
        except Exception as e:
            error(f"Next traffic round failed: {e}", prefix="CLIENT")
            return False

    def get_traffic_info(self) -> Optional[Dict[str, Any]]:
        """获取当前流量文件信息"""
        try:
            response_data = self._send_get_request("/api/traffic/info")
            if "error" not in response_data:
                return response_data
            else:
                warning(f"Get traffic info failed: {response_data.get('error')}", prefix="CLIENT")
                return None
        except Exception as e:
            error(f"Get traffic info failed: {e}", prefix="CLIENT")
            return None

    def _send_post_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """发送POST请求"""
        url = f"{self.base_url}{endpoint}"
        request_body = json.dumps(data).encode("utf-8")

        # debug_log(f"POST {url} with data: {data}")

        headers = self._get_request_headers()
        req = urllib.request.Request(url, data=request_body, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=600) as response:
                response_data: Dict[str, Any] = json.loads(response.read().decode("utf-8"))
                # debug_log(f"POST {url} -> {response.status}")
                return response_data
        except urllib.error.URLError as e:
            raise RuntimeError(f"POST {url} failed: {e}")
