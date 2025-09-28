#!/usr/bin/env python3
"""
公交车式电梯调度算法示例
电梯像公交车一样运营，按固定路线循环停靠每一层
"""
from typing import Dict, List

from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import SimulationEvent


class ElevatorBusController(ElevatorController):
    """
    公交车式电梯调度算法
    电梯像公交车一样按固定路线循环运行，在每层都停
    """

    def __init__(self, server_url: str = "http://127.0.0.1:8000", debug: bool = False):
        """初始化控制器"""
        super().__init__(server_url, debug)
        self.elevator_directions: Dict[int, str] = {}  # 记录每个电梯的当前方向
        self.max_floor = 0  # 最大楼层数

    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        """初始化公交车式电梯算法"""
        print("🚌 公交车式电梯算法初始化")
        print(f"   管理 {len(elevators)} 部电梯")
        print(f"   服务 {len(floors)} 层楼")

        # 获取最大楼层数
        self.max_floor = len(floors) - 1

        # 初始化每个电梯的方向 - 开始都向上
        for elevator in elevators:
            self.elevator_directions[elevator.id] = "up"

        # 简单的初始分布 - 均匀分散到不同楼层
        for i, elevator in enumerate(elevators):
            # 计算目标楼层 - 均匀分布在不同楼层
            target_floor = (i * (len(floors) - 1)) // len(elevators)

            # 立刻移动到目标位置并开始循环
            elevator.go_to_floor(target_floor, immediate=True)

            print(f"   🚌 电梯{elevator.id} -> {target_floor}楼 (开始公交循环)")

    def on_event_execute_start(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        """事件执行前的回调"""
        print(f"⏰ Tick {tick}: 即将处理 {len(events)} 个事件", end="")
        for i in elevators:
            print(f"电梯{i.id}[{i.target_floor_direction.value}] 位置{i.current_floor_float}/{i.target_floor}, ", end="")
        print()

    def on_event_execute_end(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        """事件执行后的回调"""
        # print(f"✅ Tick {tick}: 已处理 {len(events)} 个事件")
        pass

    def on_passenger_call(self, floor: ProxyFloor, direction: str) -> None:
        """
        乘客呼叫时的回调
        公交车模式下，电梯已经在循环运行，无需特别响应呼叫
        """
        print(f"📞 楼层 {floor.floor} 有乘客呼叫 ({direction}) - 公交车将按既定路线服务")

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        """
        电梯空闲时的回调
        让空闲的电梯继续执行公交车循环路线
        """
        print(f"⏸️ 电梯 {elevator.id} 空闲，继续公交循环")

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        """
        电梯停靠时的回调
        公交车模式下，在每一层都停下，然后继续下一站
        """
        print(f"🛑 电梯 {elevator.id} 停靠在 {floor.floor} 楼")

        # 设置指示器让乘客知道电梯的行进方向
        current_direction = self.elevator_directions.get(elevator.id, "up")
        if current_direction == "up":
            elevator.set_up_indicator(True)
            elevator.set_down_indicator(False)
        else:
            elevator.set_up_indicator(False)
            elevator.set_down_indicator(True)

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        """
        乘客上车时的回调
        打印乘客上车信息
        """
        print(f"⬆️ 乘客 {passenger.id} 上车 - 电梯 {elevator.id} - 楼层 {elevator.current_floor} - 目标楼层: {passenger.destination}")

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        """
        乘客下车时的回调
        打印乘客下车信息
        """
        print(f"⬇️ 乘客 {passenger.id} 在 {floor.floor} 楼下车 - 电梯 {elevator.id}")

    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """
        电梯经过楼层时的回调
        打印经过楼层的信息
        """
        print(f"🔄 电梯 {elevator.id} 经过 {floor.floor} 楼 (方向: {direction})")

    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """
        电梯即将到达时的回调 (START_DOWN事件)
        电梯开始减速，即将到达目标楼层
        """
        print(f"🎯 电梯 {elevator.id} 即将到达 {floor.floor} 楼 (方向: {direction})")


if __name__ == "__main__":
    algorithm = ElevatorBusController(debug=True)
    algorithm.start()
