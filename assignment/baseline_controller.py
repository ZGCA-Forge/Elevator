#!/usr/bin/env python3
"""
首版调度算法：基于最近楼层的贪心派梯策略

核心策略：
1. 记录所有等待乘客的呼叫（按乘客维度去重）
2. 电梯若有乘客，则优先送达车内乘客的最近目的地
3. 电梯空载时，选择与当前楼层距离最近、尚未被其他电梯抢占的呼叫
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from pprint import pprint

from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import Direction, SimulationEvent


@dataclass
class PendingRequest:
    """存储一名等待乘客的调度请求"""

    passenger_id: int
    origin: int
    destination: int
    direction: Direction
    arrive_tick: int
    assigned_elevator: Optional[int] = None

    def priority_key(self, reference_floor: int) -> Tuple[int, int]:
        """根据参考楼层计算优先级键值"""
        return abs(self.origin - reference_floor), self.origin


class GreedyNearestController(ElevatorController):
    """
    最近楼层优先的贪心调度器

    简要思路：
    - 使用 passenger_id 去重，避免重复响应同一名乘客的上下行事件
    - 电梯完成停靠后会立即尝试分配下一目标楼层
    - 当楼内等待乘客为空时，电梯回到首层待命
    """

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8000",
        debug: bool = False,
        tick_delay: Optional[float] = None,
    ):
        super().__init__(server_url, debug)
        self.waiting_requests: Dict[int, PendingRequest] = {}
        self.last_known_tick: int = 0
        self.dispatch_history: Dict[int, List[int]] = {}
        self.default_idle_floor: int = 0
        # 从环境变量读取 tick 间隔，默认 0.2s 便于可视化观察
        if tick_delay is not None:
            self.tick_delay = tick_delay
        else:
            env_value = os.environ.get("ASSIGNMENT_TICK_DELAY", "0.2")
            try:
                self.tick_delay = max(0.0, float(env_value))
            except ValueError:
                self.tick_delay = 0.2

    # ========= 生命周期回调 ========= #
    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        self.waiting_requests.clear()
        self.dispatch_history = {e.id: [] for e in elevators}
        if floors:
            self.default_idle_floor = floors[0].floor
        print(f"初始化完成：{len(elevators)} 部电梯，服务楼层 {len(floors)} 层")

    def on_event_execute_start(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        self.last_known_tick = tick
        if self.debug:
            joined = ", ".join(event.type.value for event in events)
            print(f"[Tick {tick}] 事件：{joined}")

    def on_event_execute_end(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        # 通过短暂休眠让可视化界面有足够时间采样状态
        if self.tick_delay > 0:
            time.sleep(self.tick_delay)

    # ========= 自定义运行循环，避免自动重置 ========= #
    def _run_event_driven_simulation(self) -> None:  # type: ignore[override]
        try:
            state = self.api_client.get_state()
            if state.tick > 0:
                self.api_client.reset()
                time.sleep(0.3)
                state = self.api_client.get_state()
            self._update_wrappers(state, init=True)
            self._update_traffic_info()
            refresh_attempts = 0
            while self.current_traffic_max_tick == 0 and refresh_attempts < 3:
                print("模拟器接收到的最大tick时间为0，尝试请求下一轮测试...")
                if not self.api_client.next_traffic_round(full_reset=True):
                    break
                time.sleep(0.3)
                state = self.api_client.get_state(force_reload=True)
                self._update_wrappers(state)
                self._update_traffic_info()
                refresh_attempts += 1
            if self.current_traffic_max_tick == 0:
                print("未获取到可用测试案例，请稍后重试。")
                return

            self._internal_init(self.elevators, self.floors)
            self.api_client.mark_tick_processed()

            while self.is_running:
                if self.current_tick >= self.current_traffic_max_tick:
                    break

                step_response = self.api_client.step(1)
                self.current_tick = step_response.tick
                events = step_response.events

                state = self.api_client.get_state()
                self._update_wrappers(state)

                self.on_event_execute_start(self.current_tick, events, self.elevators, self.floors)

                if events:
                    for event in events:
                        self._handle_single_event(event)

                state = self.api_client.get_state()
                self._update_wrappers(state)

                self.on_event_execute_end(self.current_tick, events, self.elevators, self.floors)
                self.api_client.mark_tick_processed()

                if self.current_tick >= self.current_traffic_max_tick:
                    pprint(state.metrics.to_dict())
                    break

        except Exception as exc:
            print(f"模拟运行错误: {exc}")
            raise

    # ========= 事件回调 ========= #
    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        if passenger.id not in self.waiting_requests:
            request = PendingRequest(
                passenger_id=passenger.id,
                origin=floor.floor,
                destination=passenger.destination,
                direction=passenger.travel_direction,
                arrive_tick=passenger.arrive_tick,
            )
            self.waiting_requests[passenger.id] = request
            if self.debug:
                print(f"记录呼叫：乘客 {passenger.id} @F{floor.floor} -> F{passenger.destination}")
        self._wake_idle_elevators()

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        self._assign_next_target(elevator)

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        self._assign_next_target(elevator)

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        self.waiting_requests.pop(passenger.id, None)
        if self.debug:
            print(f"乘客 {passenger.id} 已乘坐电梯 {elevator.id}")

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        if self.debug:
            wait = self.last_known_tick - passenger.arrive_tick
            print(f"乘客 {passenger.id} 在 F{floor.floor} 下梯，总等待 {wait} tick")

    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        pass

    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        pass

    # ========= 内部调度逻辑 ========= #
    def _wake_idle_elevators(self) -> None:
        """有新需求时唤醒空闲电梯"""
        for elevator in self.elevators:
            if elevator.run_status.name.lower() == "stopped" and not elevator.passengers:
                self._assign_next_target(elevator)

    def _assign_next_target(self, elevator: ProxyElevator) -> None:
        """为指定电梯选择下一目标楼层"""
        target = self._pick_next_destination(elevator)
        if target is None:
            if (
                elevator.current_floor != self.default_idle_floor
                and not elevator.passengers
                and not self.waiting_requests
            ):
                elevator.go_to_floor(self.default_idle_floor)
            return
        already_scheduled = self.dispatch_history[elevator.id][-1:] == [target]
        if already_scheduled and elevator.target_floor == target:
            return
        if elevator.go_to_floor(target):
            self.dispatch_history[elevator.id].append(target)
            if self.debug:
                print(f"电梯 {elevator.id} -> 目标楼层 F{target}")

    def _pick_next_destination(self, elevator: ProxyElevator) -> Optional[int]:
        """计算电梯的下一目标楼层"""
        pressed = elevator.pressed_floors
        if pressed:
            pressed.sort(key=lambda floor: abs(floor - elevator.current_floor))
            return pressed[0]
        candidate = self._choose_waiting_request(elevator)
        if candidate:
            request = candidate
            request.assigned_elevator = elevator.id
            return request.origin
        return None

    def _choose_waiting_request(self, elevator: ProxyElevator) -> Optional[PendingRequest]:
        """
        从等待队列中挑选最合适的乘客
        策略：优先选择距离最近、尚未被其他电梯抢占的呼叫；如无可用请求，则尝试接过超时太久的请求
        """
        unclaimed = [req for req in self.waiting_requests.values() if req.assigned_elevator in (None, elevator.id)]
        if not unclaimed:
            return None
        unclaimed.sort(key=lambda req: (req.priority_key(elevator.current_floor), req.arrive_tick))
        return unclaimed[0]
