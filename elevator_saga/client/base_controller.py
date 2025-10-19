#!/usr/bin/env python3
"""
Elevator Controller Base Class
电梯调度基础控制器类 - 提供面向对象的算法开发接口
"""
import os
import time
from abc import ABC, abstractmethod
from pprint import pprint
from typing import Any, Dict, List

from elevator_saga.client.api_client import ElevatorAPIClient
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import EventType, SimulationEvent, SimulationState

# 避免循环导入，使用运行时导入
from elevator_saga.utils.logger import debug, error, info, warning


class ElevatorController(ABC):
    """
    电梯调度控制器基类

    用户通过继承此类并实现 abstract 方法来创建自己的调度算法
    """

    def __init__(self, server_url: str = "http://127.0.0.1:8000", debug: bool = False, client_type: str = "algorithm"):
        """
        初始化控制器

        Args:
            server_url: 服务器URL
            debug: 是否启用debug模式
            client_type: 客户端类型 ("algorithm" 或 "gui")
        """
        self.server_url = server_url
        self.debug = debug
        self.elevators: List[Any] = []
        self.floors: List[Any] = []
        self.current_tick = 0
        self.is_running = False
        self.current_traffic_max_tick: int = 0
        self.client_type = client_type

        # 初始化API客户端，传递客户端类型
        self.api_client = ElevatorAPIClient(server_url, client_type=client_type)

    @abstractmethod
    def on_init(self, elevators: List[Any], floors: List[Any]) -> None:
        """
        算法初始化方法 - 必须由子类实现

        Args:
            elevators: 电梯列表
            floors: 楼层列表
        """
        pass

    @abstractmethod
    def on_event_execute_start(self, tick: int, events: List[Any], elevators: List[Any], floors: List[Any]) -> None:
        """
        事件执行前的回调 - 必须由子类实现

        Args:
            tick: 当前时间tick
            events: 即将执行的事件列表
            elevators: 电梯列表
            floors: 楼层列表
        """
        pass

    @abstractmethod
    def on_event_execute_end(self, tick: int, events: List[Any], elevators: List[Any], floors: List[Any]) -> None:
        """
        事件执行后的回调 - 必须由子类实现

        Args:
            tick: 当前时间tick
            events: 已执行的事件列表
            elevators: 电梯列表
            floors: 楼层列表
        """
        pass

    def on_start(self) -> None:
        """
        算法启动前的回调 - 可选实现
        """
        info(f"启动 {self.__class__.__name__} 算法", prefix="CONTROLLER")

    def on_stop(self) -> None:
        """
        算法停止后的回调 - 可选实现
        """
        info(f"停止 {self.__class__.__name__} 算法", prefix="CONTROLLER")

    @abstractmethod
    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        """
        乘客呼叫时的回调 - 可选实现

        Args:
            floor: 呼叫楼层代理对象
            direction: 方向 ("up" 或 "down")
        """
        pass

    @abstractmethod
    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        """
        电梯空闲时的回调 - 可选实现

        Args:
            elevator: 空闲的电梯代理对象
        """
        pass

    @abstractmethod
    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        """
        电梯停靠时的回调 - 可选实现

        Args:
            elevator: 停靠的电梯代理对象
            floor: 停靠楼层代理对象
        """
        pass

    @abstractmethod
    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        """
        乘客上梯时的回调 - 可选实现

        Args:
            elevator: 电梯代理对象
            passenger: 乘客代理对象
        """
        pass

    @abstractmethod
    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        """
        乘客下车时的回调 - 可选实现

        Args:
            elevator: 电梯代理对象
            passenger: 乘客代理对象
            floor: 下车楼层代理对象
        """
        pass

    @abstractmethod
    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """
        电梯经过楼层时的回调 - 可选实现

        Args:
            elevator: 电梯代理对象
            floor: 经过的楼层代理对象
            direction: 移动方向
        """
        pass

    @abstractmethod
    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """
        电梯即将到达时的回调 - 可选实现

        Args:
            elevator: 电梯代理对象
            floor: 即将到达的楼层代理对象
            direction: 移动方向
        """
        pass

    # @abstractmethod  为了兼容性暂不强制要求elevator_move必须实现
    def on_elevator_move(
        self, elevator: ProxyElevator, from_position: float, to_position: float, direction: str, status: str
    ) -> None:
        """
        电梯移动时的回调 - 可选实现

        Args:
            elevator: 电梯代理对象
            from_position: 起始位置（浮点数表示楼层）
            to_position: 目标位置（浮点数表示楼层）
            direction: 移动方向
            status: 电梯运行状态
        """
        pass

    def _internal_init(self, elevators: List[Any], floors: List[Any]) -> None:
        """内部初始化方法"""
        self.elevators = elevators
        self.floors = floors
        self.current_tick = 0

        # 调用用户的初始化方法
        self.on_init(elevators, floors)

    def start(self) -> None:
        """
        启动控制器
        """
        self.on_start()
        self.is_running = True

        try:
            self._run_event_driven_simulation()
        except KeyboardInterrupt:
            info("用户中断了算法运行", prefix="CONTROLLER")
        except Exception as e:
            error(f"算法运行出错: {e}", prefix="CONTROLLER")
            raise
        finally:
            self.is_running = False
            self.on_stop()

    def stop(self) -> None:
        """停止控制器"""
        self.is_running = False
        info(f"停止 {self.__class__.__name__}", prefix="CONTROLLER")

    def on_simulation_complete(self, final_state: Dict[str, Any]) -> None:
        """
        模拟完成时的回调 - 可选实现

        Args:
            final_state: 最终状态数据
        """
        pass

    def _run_event_driven_simulation(self) -> None:
        """运行事件驱动的模拟"""
        try:
            # 获取初始状态并初始化，默认从0开始
            try:
                state = self.api_client.get_state()
            except ConnectionResetError as _:  # noqa: F841
                error(f"模拟器可能并没有开启，请检查模拟器是否启动 {self.api_client.base_url}", prefix="CONTROLLER")
                os._exit(1)
            if state.tick > 0:
                warning("模拟器可能已经开始了一次模拟，执行重置...", prefix="CONTROLLER")
                self.api_client.reset()
                time.sleep(0.3)
                return self._run_event_driven_simulation()
            self._update_wrappers(state, init=True)

            # 获取当前流量文件的最大tick数
            self._update_traffic_info()
            if self.current_traffic_max_tick == 0:
                warning("模拟器接收到的最大tick时间为0，可能所有的测试案例已用完，请求重置...", prefix="CONTROLLER")
                self.api_client.next_traffic_round(full_reset=True)
                time.sleep(0.3)
                return self._run_event_driven_simulation()
            # if self.current_tick >= self.current_traffic_max_tick:
            #     return

            self._internal_init(self.elevators, self.floors)
            self.api_client.mark_tick_processed()
            while self.is_running:
                # 检查是否达到最大tick数
                if self.current_tick >= self.current_traffic_max_tick:
                    break

                # 执行一个tick的模拟，从1开始
                step_response = self.api_client.step(1)
                # 更新当前状态
                self.current_tick = step_response.tick
                # 获取事件列表
                events = step_response.events

                # 获取当前状态
                state = self.api_client.get_state()
                self._update_wrappers(state)

                # 事件执行前回调
                self.on_event_execute_start(self.current_tick, events, self.elevators, self.floors)

                # 处理事件
                if events:
                    for event in events:
                        self._handle_single_event(event)

                # 获取更新后的状态
                state = self.api_client.get_state()
                self._update_wrappers(state)

                # 事件执行后回调
                self.on_event_execute_end(self.current_tick, events, self.elevators, self.floors)
                # 标记tick处理完成，使API客户端缓存失效
                self.api_client.mark_tick_processed()
                # 检查是否需要切换流量文件
                if self.current_tick >= self.current_traffic_max_tick:
                    pprint(state.metrics.to_dict())
                    if not self.api_client.next_traffic_round():
                        break
                    # 重置并重新初始化
                    self._reset_and_reinit()

        except Exception as e:
            error(f"模拟运行错误: {e}", prefix="CONTROLLER")
            raise

    def _update_wrappers(self, state: SimulationState, init: bool = False) -> None:
        """更新电梯和楼层代理对象"""
        self.current_tick = state.tick
        # 检查电梯数量是否发生变化，只有变化时才重新创建
        if len(self.elevators) != len(state.elevators):
            if not init:
                raise ValueError(f"Elevator number mismatch: {len(self.elevators)} != {len(state.elevators)}")
            self.elevators = [ProxyElevator(elevator_state.id, self.api_client) for elevator_state in state.elevators]

        # 检查楼层数量是否发生变化，只有变化时才重新创建
        if len(self.floors) != len(state.floors):
            if not init:
                raise ValueError(f"Floor number mismatch: {len(self.floors)} != {len(state.floors)}")
            self.floors = [ProxyFloor(floor_state.floor, self.api_client) for floor_state in state.floors]

    def _update_traffic_info(self) -> None:
        """更新当前流量文件信息"""
        try:
            traffic_info = self.api_client.get_traffic_info()
            if traffic_info:
                self.current_traffic_max_tick = int(traffic_info["max_tick"])
                debug(f"Updated traffic info - max_tick: {self.current_traffic_max_tick}", prefix="CONTROLLER")
            else:
                warning("Failed to get traffic info", prefix="CONTROLLER")
                self.current_traffic_max_tick = 0
        except Exception as e:
            error(f"Error updating traffic info: {e}", prefix="CONTROLLER")
            self.current_traffic_max_tick = 0

    def _handle_single_event(self, event: SimulationEvent) -> None:
        """处理单个事件"""
        if event.type == EventType.UP_BUTTON_PRESSED:
            floor_id = event.data["floor"]
            passenger_id = event.data["passenger"]
            if floor_id is not None:
                floor_proxy = ProxyFloor(floor_id, self.api_client)
                passenger_proxy = ProxyPassenger(passenger_id, self.api_client)
                self.on_passenger_call(passenger_proxy, floor_proxy, "up")

        elif event.type == EventType.DOWN_BUTTON_PRESSED:
            floor_id = event.data["floor"]
            passenger_id = event.data["passenger"]
            if floor_id is not None:
                floor_proxy = ProxyFloor(floor_id, self.api_client)
                passenger_proxy = ProxyPassenger(passenger_id, self.api_client)
                self.on_passenger_call(passenger_proxy, floor_proxy, "down")

        elif event.type == EventType.STOPPED_AT_FLOOR:
            elevator_id = event.data.get("elevator")
            floor_id = event.data["floor"]
            if elevator_id is not None and floor_id is not None:
                elevator_proxy = ProxyElevator(elevator_id, self.api_client)
                floor_proxy = ProxyFloor(floor_id, self.api_client)
                self.on_elevator_stopped(elevator_proxy, floor_proxy)

        elif event.type == EventType.IDLE:
            elevator_id = event.data.get("elevator")
            if elevator_id is not None:
                elevator_proxy = ProxyElevator(elevator_id, self.api_client)
                self.on_elevator_idle(elevator_proxy)

        elif event.type == EventType.PASSING_FLOOR:
            elevator_id = event.data.get("elevator")
            floor_id = event.data["floor"]
            direction = event.data.get("direction")
            if elevator_id is not None and floor_id is not None and direction is not None:
                elevator_proxy = ProxyElevator(elevator_id, self.api_client)
                floor_proxy = ProxyFloor(floor_id, self.api_client)
                self.on_elevator_passing_floor(elevator_proxy, floor_proxy, direction)

        elif event.type == EventType.ELEVATOR_APPROACHING:
            elevator_id = event.data.get("elevator")
            floor_id = event.data["floor"]
            direction = event.data.get("direction")
            if elevator_id is not None and floor_id is not None and direction is not None:
                elevator_proxy = ProxyElevator(elevator_id, self.api_client)
                floor_proxy = ProxyFloor(floor_id, self.api_client)
                self.on_elevator_approaching(elevator_proxy, floor_proxy, direction)

        elif event.type == EventType.PASSENGER_BOARD:
            elevator_id = event.data.get("elevator")
            passenger_id = event.data.get("passenger")
            if elevator_id is not None and passenger_id is not None:
                elevator_proxy = ProxyElevator(elevator_id, self.api_client)
                passenger_proxy = ProxyPassenger(passenger_id, self.api_client)
                self.on_passenger_board(elevator_proxy, passenger_proxy)

        elif event.type == EventType.PASSENGER_ALIGHT:
            elevator_id = event.data.get("elevator")
            passenger_id = event.data.get("passenger")
            floor_id = event.data["floor"]
            if elevator_id is not None and passenger_id is not None and floor_id is not None:
                elevator_proxy = ProxyElevator(elevator_id, self.api_client)
                passenger_proxy = ProxyPassenger(passenger_id, self.api_client)
                floor_proxy = ProxyFloor(floor_id, self.api_client)
                self.on_passenger_alight(elevator_proxy, passenger_proxy, floor_proxy)

        elif event.type == EventType.ELEVATOR_MOVE:
            elevator_id = event.data.get("elevator")
            from_position = event.data.get("from_position")
            to_position = event.data.get("to_position")
            direction = event.data.get("direction")
            status = event.data.get("status")
            if (
                elevator_id is not None
                and from_position is not None
                and to_position is not None
                and direction is not None
                and status is not None
            ):
                elevator_proxy = ProxyElevator(elevator_id, self.api_client)
                self.on_elevator_move(elevator_proxy, from_position, to_position, direction, status)

    def _reset_and_reinit(self) -> None:
        """重置并重新初始化"""
        try:
            # 重置服务器状态
            self.api_client.reset()
            self.current_tick = 0
            # 获取新的初始状态
            state = self.api_client.get_state()
            self._update_wrappers(state)

            # 更新流量信息（切换到新流量文件后需要重新获取最大tick）
            self._update_traffic_info()

            # 重新初始化用户算法
            self._internal_init(self.elevators, self.floors)

        except Exception as e:
            error(f"重置失败: {e}", prefix="CONTROLLER")
            raise
