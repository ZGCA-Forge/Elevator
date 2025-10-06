#!/usr/bin/env python3
"""
Elevator simulation server - tick-based discrete event simulation
Provides HTTP API for controlling elevators and advancing simulation time
"""
import argparse
import json
import os.path
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from flask import Flask, Response, request

from elevator_saga.core.models import (
    Direction,
    ElevatorState,
    ElevatorStatus,
    EventType,
    FloorState,
    PassengerInfo,
    PassengerStatus,
    PerformanceMetrics,
    SerializableModel,
    SimulationEvent,
    SimulationState,
    TrafficEntry,
    create_empty_simulation_state,
)

# Global debug flag for server
_SERVER_DEBUG_MODE = False


def set_server_debug_mode(enabled: bool) -> None:
    """Enable or disable server debug logging"""
    global _SERVER_DEBUG_MODE
    globals()["_SERVER_DEBUG_MODE"] = enabled


def server_debug_log(message: str) -> None:
    """Print server debug message if debug mode is enabled"""
    if _SERVER_DEBUG_MODE:
        print(f"[SERVER-DEBUG] {message}", flush=True)


class CustomJSONEncoder(json.JSONEncoder):
    """
    自定义JSON编码器，处理Enum和其他特殊类型的序列化
    """

    def default(self, o: Any) -> Any:
        """
        重写默认序列化方法，处理特殊类型

        Args:
            o: 要序列化的对象

        Returns:
            序列化后的值
        """
        if isinstance(o, Enum):
            return o.value
        elif hasattr(o, "to_dict"):
            # 如果对象有to_dict方法，使用它
            return o.to_dict()
        else:
            # 调用父类的默认处理
            return super().default(o)


def json_response(data: Any, status: int = 200) -> Response | tuple[Response, int]:
    """
    创建JSON响应，使用自定义编码器处理Enum等特殊类型

    Args:
        data: 要序列化的数据
        status: HTTP状态码

    Returns:
        Flask Response对象，或者Response和状态码的元组（当状态码不是200时）
    """
    json_str = json.dumps(data, cls=CustomJSONEncoder, ensure_ascii=False)
    response = Response(json_str, status=status, mimetype="application/json")
    if status == 200:
        return response
    else:
        return response, status


@dataclass
class PassengerSummary(SerializableModel):
    """乘客摘要"""

    completed: int
    waiting: int
    in_transit: int
    total: int


@dataclass
class SimulationStateResponse(SerializableModel):
    """模拟状态响应"""

    tick: int
    elevators: List[ElevatorState]
    floors: List[FloorState]
    passengers: Dict[int, PassengerInfo]
    metrics: PerformanceMetrics


class ElevatorSimulation:
    traffic_queue: List[TrafficEntry]  # type: ignore
    next_passenger_id: int
    max_duration_ticks: int

    def __init__(self, traffic_dir: str, _init_only: bool = False):
        if _init_only:
            return
        self.lock = threading.Lock()
        self.traffic_dir = Path(traffic_dir)
        self.current_traffic_index = 0
        self.traffic_files: List[Path] = []
        self.state: SimulationState = create_empty_simulation_state(2, 1, 1)
        self._load_traffic_files()

    @property
    def tick(self) -> int:
        """当前tick"""
        return self.state.tick

    @property
    def elevators(self) -> List[ElevatorState]:
        """电梯列表"""
        return self.state.elevators

    @property
    def floors(self) -> List[FloorState]:
        """楼层列表"""
        return self.state.floors

    @property
    def passengers(self) -> Dict[int, PassengerInfo]:
        """乘客字典"""
        return self.state.passengers

    def _load_traffic_files(self) -> None:
        """扫描traffic目录，加载所有json文件列表"""
        # 查找所有json文件
        for file_path in self.traffic_dir.glob("*.json"):
            if file_path.is_file():
                self.traffic_files.append(file_path)
        # 按文件名排序
        self.traffic_files.sort()
        server_debug_log(f"Found {len(self.traffic_files)} traffic files: {[f.name for f in self.traffic_files]}")
        # 如果有文件，加载第一个
        if self.traffic_files:
            self.load_current_traffic()

    def load_current_traffic(self) -> None:
        """加载当前索引对应的流量文件"""
        if not self.traffic_files:
            server_debug_log("No traffic files available")
            return

        if self.current_traffic_index >= len(self.traffic_files):
            server_debug_log(f"Traffic index {self.current_traffic_index} out of range")
            return

        traffic_file = self.traffic_files[self.current_traffic_index]
        server_debug_log(f"Loading traffic from {traffic_file.name}")
        try:
            with open(traffic_file, "r", encoding="utf-8") as f:
                file_data = json.load(f)
            building_config = file_data["building"]
            server_debug_log(f"Building config: {building_config}")
            self.state = create_empty_simulation_state(
                building_config["elevators"], building_config["floors"], building_config["elevator_capacity"]
            )
            self.reset()
            self.max_duration_ticks = building_config["duration"]
            traffic_data: list[Dict[str, Any]] = file_data["traffic"]
            traffic_data.sort(key=lambda t: cast(int, t["tick"]))
            for entry in traffic_data:
                traffic_entry = TrafficEntry(
                    id=self.next_passenger_id,
                    origin=entry["origin"],
                    destination=entry["destination"],
                    tick=entry["tick"],
                )
                self.traffic_queue.append(traffic_entry)
                self.next_passenger_id += 1

        except Exception as e:
            server_debug_log(f"Error loading traffic file {traffic_file}: {e}")

    def next_traffic_round(self, full_reset: bool = False) -> bool:
        """切换到下一个流量文件，返回是否成功切换"""
        if not self.traffic_files:
            return False

        # 检查是否还有下一个文件
        next_index = self.current_traffic_index + 1
        if next_index >= len(self.traffic_files):
            if full_reset:
                self.current_traffic_index = -1
                return self.next_traffic_round()
            return False  # 没有更多测试案例，停止模拟

        self.current_traffic_index = next_index
        self.load_current_traffic()  # 加载新的流量文件
        return True

    def load_traffic(self, traffic_file: str) -> None:
        """Load passenger traffic from JSON file using unified data models"""
        with open(traffic_file, "r") as f:
            traffic_data = json.load(f)

        server_debug_log(f"Loading traffic from {traffic_file}, {len(traffic_data)} entries")

        self.traffic_queue: List[TrafficEntry] = []  # type: ignore[reportRedeclaration]
        for entry in traffic_data:
            # Create TrafficEntry from JSON data
            traffic_entry = TrafficEntry(
                id=entry.get("id", self.next_passenger_id),
                origin=entry["origin"],
                destination=entry["destination"],
                tick=entry["tick"],
            )
            self.traffic_queue.append(traffic_entry)
            self.next_passenger_id = max(self.next_passenger_id, traffic_entry.id + 1)

        # Sort by arrival time
        self.traffic_queue.sort(key=lambda p: p.tick)
        server_debug_log(f"Traffic loaded and sorted, next passenger ID: {self.next_passenger_id}")

    def _emit_event(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """Emit an event to be sent to clients using unified data models"""
        self.state.add_event(event_type, data)
        server_debug_log(f"Event emitted: {event_type.value} with data {data}")

    def step(self, num_ticks: int = 1) -> List[SimulationEvent]:
        with self.lock:
            new_events: List[SimulationEvent] = []
            for _ in range(num_ticks):
                self.state.tick += 1
                # server_debug_log(f"Processing tick {self.tick}")  # currently one tick per step
                tick_events = self._process_tick()
                new_events.extend(tick_events)
                # server_debug_log(f"Tick {self.tick} completed - Generated {len(tick_events)} events")  # currently one tick per step

                # 如果到达最大时长，强制完成剩余乘客
                if self.tick >= self.max_duration_ticks:
                    completed_count = self.force_complete_remaining_passengers()
                    if completed_count > 0:
                        server_debug_log(f"模拟结束，强制完成了 {completed_count} 个乘客")

            server_debug_log(f"Step completed - Final tick: {self.tick}, Total events: {len(new_events)}")
            return new_events

    def _process_tick(self) -> List[SimulationEvent]:
        """
        Process one simulation tick
        每个tick先发生事件，再发生动作
        """
        events_start = len(self.state.events)
        self._update_elevator_status()

        # 1. Add new passengers from traffic queue
        self._process_arrivals()

        # 2. Move elevators
        self._move_elevators()

        # 3. Process elevator stops and passenger boarding/alighting
        self._process_elevator_stops()

        # Return events generated this tick
        return self.state.events[events_start:]

    def _process_passenger_in(self, elevator: ElevatorState) -> None:
        current_floor = elevator.current_floor
        # 处于Stopped状态，方向也已经清空，说明没有调度。
        floor = self.floors[current_floor]
        passengers_to_board: List[int] = []
        available_capacity = elevator.max_capacity - len(elevator.passengers)
        # Board passengers going up (if up indicator is on or no direction set)
        if elevator.target_floor_direction == Direction.UP:
            passengers_to_board.extend(floor.up_queue[:available_capacity])
            floor.up_queue = floor.up_queue[available_capacity:]

        # Board passengers going down (if down indicator is on or no direction set)
        if elevator.target_floor_direction == Direction.DOWN:
            passengers_to_board.extend(floor.down_queue[:available_capacity])
            floor.down_queue = floor.down_queue[available_capacity:]

        # Process boarding
        for passenger_id in passengers_to_board:
            passenger = self.passengers[passenger_id]
            passenger.pickup_tick = self.tick
            passenger.elevator_id = elevator.id
            elevator.passengers.append(passenger_id)
            self._emit_event(
                EventType.PASSENGER_BOARD,
                {"elevator": elevator.id, "floor": current_floor, "passenger": passenger_id},
            )

    def _update_elevator_status(self) -> None:
        """更新电梯运行状态"""
        for elevator in self.elevators:
            current_floor = elevator.position.current_floor
            target_floor = elevator.target_floor
            old_status = elevator.run_status.value
            # 没有移动方向，说明电梯已经到达目标楼层
            if elevator.target_floor_direction == Direction.STOPPED:
                if elevator.next_target_floor is not None:
                    self._set_elevator_target_floor(elevator, elevator.next_target_floor)

                    self._process_passenger_in(elevator)
                    elevator.next_target_floor = None
                else:
                    continue
            # 有移动方向，但是需要启动了
            if elevator.run_status == ElevatorStatus.STOPPED:
                # 从停止状态启动 - 注意：START_UP表示启动加速状态，不表示方向
                # 实际移动方向由target_floor_direction决定
                elevator.run_status = ElevatorStatus.START_UP
            # 从启动状态切换到匀速
            elif elevator.run_status == ElevatorStatus.START_UP:
                # 从启动状态切换到匀速
                elevator.run_status = ElevatorStatus.CONSTANT_SPEED
            server_debug_log(
                f"电梯{elevator.id} 状态:{old_status}->{elevator.run_status.value} 方向:{elevator.target_floor_direction.value} "
                f"位置:{elevator.position.current_floor_float:.1f} 目标:{target_floor}"
            )
        # START_DOWN状态会在到达目标时在_move_elevators中切换为STOPPED

    def _process_arrivals(self) -> None:  # OK
        """Process new passenger arrivals"""
        while self.traffic_queue and self.traffic_queue[0].tick <= self.tick:
            traffic_entry = self.traffic_queue.pop(0)
            passenger = PassengerInfo(
                id=traffic_entry.id,
                origin=traffic_entry.origin,
                destination=traffic_entry.destination,
                arrive_tick=self.tick,
            )
            assert traffic_entry.origin != traffic_entry.destination, f"乘客{passenger.id}目的地和起始地{traffic_entry.origin}重复"
            self.passengers[passenger.id] = passenger
            server_debug_log(f"乘客 {passenger.id:4}： 创建 | {passenger}")
            if passenger.destination > passenger.origin:
                self.floors[passenger.origin].up_queue.append(passenger.id)
                self._emit_event(EventType.UP_BUTTON_PRESSED, {"floor": passenger.origin, "passenger": passenger.id})
            else:
                self.floors[passenger.origin].down_queue.append(passenger.id)
                self._emit_event(EventType.DOWN_BUTTON_PRESSED, {"floor": passenger.origin, "passenger": passenger.id})

    def _move_elevators(self) -> None:
        """
        Move all elevators towards their destinations with acceleration/deceleration
        上一步已经处理了当前电梯的状态，这里只做移动
        """
        for elevator in self.elevators:
            target_floor = elevator.target_floor
            new_floor = old_floor = elevator.position.current_floor
            # 获取移动速度
            movement_speed = 0
            if elevator.run_status == ElevatorStatus.START_UP:
                movement_speed = 1
            elif elevator.run_status == ElevatorStatus.START_DOWN:
                movement_speed = 1
            elif elevator.run_status == ElevatorStatus.CONSTANT_SPEED:
                movement_speed = 2
            if movement_speed == 0:
                continue

            # 根据状态和方向调整移动距离
            elevator.last_tick_direction = elevator.target_floor_direction
            if elevator.target_floor_direction == Direction.UP:
                new_floor = elevator.position.floor_up_position_add(movement_speed)
            elif elevator.target_floor_direction == Direction.DOWN:
                new_floor = elevator.position.floor_up_position_add(-movement_speed)
            else:
                # 之前的状态已经是到站了，清空上一次到站的方向
                pass

            # 移动后检测是否即将到站，从匀速状态切换到减速
            if elevator.run_status == ElevatorStatus.CONSTANT_SPEED:
                # 检查是否需要开始减速，这里加速减速设置路程为1，匀速路程为2，这样能够保证不会匀速恰好到达，必须加减速
                # 如果速度超出，则预期的逻辑是，恰好到达/超出0等，会强制触发start_down，多走一次才能stop，目前没有实现这部分逻辑
                if self._should_start_deceleration(elevator):
                    elevator.run_status = ElevatorStatus.START_DOWN
                    # 发送电梯即将经过某层楼事件
                if self._near_next_stop(elevator):
                    self._emit_event(
                        EventType.ELEVATOR_APPROACHING,
                        {
                            "elevator": elevator.id,
                            "floor": int(round(elevator.position.current_floor_float)),
                            "direction": elevator.target_floor_direction.value,
                        },
                    )

            # 处理楼层变化事件
            if old_floor != new_floor:
                if new_floor != target_floor:
                    self._emit_event(
                        EventType.PASSING_FLOOR,
                        {
                            "elevator": elevator.id,
                            "floor": new_floor,
                            "direction": elevator.target_floor_direction.value,
                        },
                    )

            # 检查是否到达目标楼层
            if target_floor == new_floor and elevator.position.floor_up_position == 0:
                elevator.run_status = ElevatorStatus.STOPPED
                # 刚进入Stopped状态，可以通过last_direction识别
                self._emit_event(
                    EventType.STOPPED_AT_FLOOR, {"elevator": elevator.id, "floor": new_floor, "reason": "move_reached"}
                )
            # elevator.energy_consumed += abs(direction * elevator.speed_pre_tick) * 0.5

    def _process_elevator_stops(self) -> None:
        """
        处理Stopped电梯，上下客，新target处理等。
        """
        for elevator in self.elevators:
            current_floor = elevator.current_floor
            # 处于Stopped状态，方向也已经清空，说明没有调度。
            if elevator.last_tick_direction == Direction.STOPPED:
                self._emit_event(EventType.IDLE, {"elevator": elevator.id, "floor": current_floor})
                continue
            # 其他处于STOPPED状态，刚进入stop，到站要进行上下客
            if not elevator.run_status == ElevatorStatus.STOPPED:
                continue

            # Let passengers alight
            passengers_to_remove: List[int] = []
            for passenger_id in elevator.passengers:
                passenger = self.passengers[passenger_id]
                if passenger.destination == current_floor:
                    passenger.dropoff_tick = self.tick
                    passengers_to_remove.append(passenger_id)

            # Remove passengers who alighted
            for passenger_id in passengers_to_remove:
                elevator.passengers.remove(passenger_id)
                self._emit_event(
                    EventType.PASSENGER_ALIGHT,
                    {"elevator": elevator.id, "floor": current_floor, "passenger": passenger_id},
                )
            # Board waiting passengers (if indicators allow)
            if elevator.next_target_floor is not None:
                self._set_elevator_target_floor(elevator, elevator.next_target_floor)
                elevator.next_target_floor = None

    def _set_elevator_target_floor(self, elevator: ElevatorState, floor: int) -> None:
        """
        同一个tick内提示
        [SERVER-DEBUG] 电梯 E0 下一目的地设定为 F1
        [SERVER-DEBUG] 电梯 E0 被设定为前往 F1
        说明电梯处于stop状态，这个tick直接采用下一个目的地运行了
        """
        original_target_floor = elevator.target_floor
        elevator.position.target_floor = floor
        server_debug_log(f"电梯 E{elevator.id} 被设定为前往 F{floor}")
        new_target_floor_should_accel = self._should_start_deceleration(elevator)
        if not new_target_floor_should_accel:
            if elevator.run_status == ElevatorStatus.START_DOWN:  # 不应该加速但是加了
                elevator.run_status = ElevatorStatus.CONSTANT_SPEED
                server_debug_log(f"电梯 E{elevator.id} 被设定为匀速")
        elif new_target_floor_should_accel:
            if elevator.run_status == ElevatorStatus.CONSTANT_SPEED:  # 应该减速了，但是之前是匀速
                elevator.run_status = ElevatorStatus.START_DOWN
                server_debug_log(f"电梯 E{elevator.id} 被设定为减速")
        if elevator.current_floor != floor or elevator.position.floor_up_position != 0:
            old_status = elevator.run_status.value
            server_debug_log(f"电梯{elevator.id} 状态:{old_status}->{elevator.run_status.value}")

    def _calculate_distance_to_target(self, elevator: ElevatorState) -> float:
        """计算到目标楼层的距离（以floor_up_position为单位）"""
        current_pos = elevator.position.current_floor * 10 + elevator.position.floor_up_position
        target_pos = elevator.target_floor * 10
        return abs(target_pos - current_pos)

    def _calculate_distance_to_near_stop(self, elevator: ElevatorState) -> float:
        """计算到最近楼层的距离（以floor_up_position为单位）"""
        if elevator.position.floor_up_position < 0:
            return 10 + elevator.position.floor_up_position
        elif elevator.position.floor_up_position > 0:
            return 10 - elevator.position.floor_up_position
        else:
            return 0

    def _should_start_deceleration(self, elevator: ElevatorState) -> bool:
        """判断是否应该开始减速
        减速需要1个tick（移动1个位置单位），所以当距离目标<=3时开始减速
        这样可以保证有一个完整的减速周期
        """
        distance = self._calculate_distance_to_target(elevator)
        return distance == 1

    def _near_next_stop(self, elevator: ElevatorState) -> bool:
        distance = self._calculate_distance_to_near_stop(elevator)
        return distance == 1

    def elevator_go_to_floor(self, elevator_id: int, floor: int, immediate: bool = False) -> None:
        """
        设置电梯去向，是生命周期开始，分配目的地
        """
        if 0 <= elevator_id < len(self.elevators) and 0 <= floor < len(self.floors):
            elevator = self.elevators[elevator_id]
            if immediate:
                self._set_elevator_target_floor(elevator, floor)
            else:
                elevator.next_target_floor = floor
                server_debug_log(f"电梯 E{elevator_id} 下一目的地设定为 F{floor}")

    def get_state(self) -> SimulationStateResponse:
        """Get complete simulation state"""
        with self.lock:
            # Calculate metrics
            metrics = self._calculate_metrics()

            return SimulationStateResponse(
                tick=self.tick,
                elevators=self.elevators,
                floors=self.floors,
                passengers=self.passengers,
                metrics=metrics,
            )

    def _calculate_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics"""
        # 直接从state中筛选已完成的乘客
        completed = [p for p in self.state.passengers.values() if p.status == PassengerStatus.COMPLETED]

        total_passengers = len(self.state.passengers)
        if not completed:
            return PerformanceMetrics(
                completed_passengers=0,
                total_passengers=total_passengers,
                average_floor_wait_time=0,
                p95_floor_wait_time=0,
                average_arrival_wait_time=0,
                p95_arrival_wait_time=0,
            )

        floor_wait_times = [float(p.floor_wait_time) for p in completed]
        arrival_wait_times = [float(p.arrival_wait_time) for p in completed]

        def average_excluding_top_percent(data: List[float], exclude_percent: int) -> float:
            """计算排除掉最长的指定百分比后的平均值"""
            if not data:
                return 0.0
            sorted_data = sorted(data)
            # 计算要保留的数据数量（排除掉最长的 exclude_percent）
            keep_count = int(len(sorted_data) * (100 - exclude_percent) / 100)
            if keep_count == 0:
                return 0.0
            # 只保留前 keep_count 个数据，排除最长的部分
            kept_data = sorted_data[:keep_count]
            return sum(kept_data) / len(kept_data)

        return PerformanceMetrics(
            completed_passengers=len(completed),
            total_passengers=total_passengers,
            average_floor_wait_time=sum(floor_wait_times) / len(floor_wait_times) if floor_wait_times else 0,
            p95_floor_wait_time=average_excluding_top_percent(floor_wait_times, 5),
            average_arrival_wait_time=sum(arrival_wait_times) / len(arrival_wait_times) if arrival_wait_times else 0,
            p95_arrival_wait_time=average_excluding_top_percent(arrival_wait_times, 5),
        )

    def get_events(self, since_tick: int = 0) -> List[SimulationEvent]:
        """Get events since specified tick"""
        return [e for e in self.state.events if e.tick > since_tick]

    def get_traffic_info(self) -> Dict[str, Any]:
        return {
            "current_index": self.current_traffic_index,
            "total_files": len(self.traffic_files),
            "max_tick": self.max_duration_ticks,
        }

    def force_complete_remaining_passengers(self) -> int:
        """强制完成所有未完成的乘客，返回完成的乘客数量"""
        completed_count = 0
        current_tick = self.tick
        for passenger in self.state.passengers.values():
            if passenger.dropoff_tick == 0:
                passenger.dropoff_tick = current_tick
            if passenger.pickup_tick == 0:
                passenger.pickup_tick = current_tick
        return completed_count

    def reset(self) -> None:
        """Reset simulation to initial state"""
        with self.lock:
            self.state = create_empty_simulation_state(
                len(self.elevators), len(self.floors), self.elevators[0].max_capacity
            )
            self.traffic_queue: List[TrafficEntry] = []
            self.max_duration_ticks = 0
            self.next_passenger_id = 1


# Global simulation instance for Flask routes
simulation: ElevatorSimulation = ElevatorSimulation("", _init_only=True)

# Create Flask app
app = Flask(__name__)


# Configure CORS
@app.after_request
def after_request(response: Response) -> Response:
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response


@app.route("/api/state", methods=["GET"])
def get_state() -> Response | tuple[Response, int]:
    try:
        state = simulation.get_state()
        return json_response(state)
    except Exception as e:
        return json_response({"error": str(e)}, 500)


@app.route("/api/step", methods=["POST"])
def step_simulation() -> Response | tuple[Response, int]:
    try:
        data: Dict[str, Any] = request.get_json() or {}
        ticks = data.get("ticks", 1)
        # server_debug_log("")
        # server_debug_log(f"HTTP /api/step request ----- ticks: {ticks}")
        events = simulation.step(ticks)
        server_debug_log(f"HTTP /api/step response ----- tick: {simulation.tick}, events: {len(events)}\n")
        return json_response(
            {
                "tick": simulation.tick,
                "events": events,
            }
        )
    except Exception as e:
        return json_response({"error": str(e)}, 500)


@app.route("/api/reset", methods=["POST"])
def reset_simulation() -> Response | tuple[Response, int]:
    try:
        simulation.reset()
        return json_response({"success": True})
    except Exception as e:
        return json_response({"error": str(e)}, 500)


@app.route("/api/elevators/<int:elevator_id>/go_to_floor", methods=["POST"])
def elevator_go_to_floor(elevator_id: int) -> Response | tuple[Response, int]:
    try:
        data: Dict[str, Any] = request.get_json() or {}
        floor = data["floor"]
        immediate = data.get("immediate", False)
        simulation.elevator_go_to_floor(elevator_id, floor, immediate)
        return json_response({"success": True})
    except Exception as e:
        return json_response({"error": str(e)}, 500)


@app.route("/api/traffic/next", methods=["POST"])
def next_traffic_round() -> Response | tuple[Response, int]:
    """切换到下一个流量文件"""
    try:
        full_reset = request.get_json()["full_reset"]
        success = simulation.next_traffic_round(full_reset)
        if success:
            return json_response({"success": True})
        else:
            return json_response({"success": False, "error": "No traffic files available"}, 400)
    except Exception as e:
        return json_response({"error": str(e)}, 500)


@app.route("/api/traffic/info", methods=["GET"])
def get_traffic_info() -> Response | tuple[Response, int]:
    """获取当前流量文件信息"""
    try:
        info = simulation.get_traffic_info()
        return json_response(info)
    except Exception as e:
        return json_response({"error": str(e)}, 500)


def main() -> None:
    global simulation

    parser = argparse.ArgumentParser(description="Elevator Simulation Server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--debug", default=True, action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Enable debug mode if requested
    if args.debug:
        set_server_debug_mode(True)
        server_debug_log("Server debug mode enabled")
        app.config["DEBUG"] = True

    # Create simulation with traffic directory
    simulation = ElevatorSimulation(f"{os.path.join(os.path.dirname(__file__), '..', 'traffic')}")

    # Print traffic status
    print(f"Elevator simulation server running on http://{args.host}:{args.port}")

    try:
        app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down server...")


if __name__ == "__main__":
    main()
