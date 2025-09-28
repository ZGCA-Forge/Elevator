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
    SerializableModel,
    SimulationEvent,
    SimulationState,
    TrafficEntry,
    create_empty_simulation_state,
)

# Global debug flag for server
_SERVER_DEBUG_MODE = False


def set_server_debug_mode(enabled: bool):
    """Enable or disable server debug logging"""
    global _SERVER_DEBUG_MODE
    globals()["_SERVER_DEBUG_MODE"] = enabled


def server_debug_log(message: str):
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
class MetricsResponse(SerializableModel):
    """性能指标响应"""

    done: int
    total: int
    avg_wait: float
    p95_wait: float
    avg_system: float
    p95_system: float
    energy_total: float


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
    metrics: MetricsResponse


class ElevatorSimulation:
    traffic_queue: List[TrafficEntry]
    next_passenger_id: int
    max_duration_ticks: int
    _force_completed: bool

    def __init__(self, traffic_dir: str, _init_only: bool = False):
        if _init_only:
            return
        self.lock = threading.Lock()
        self.traffic_dir = Path(traffic_dir)
        self.current_traffic_index = 0
        self.traffic_files: List[Path] = []
        self.state: SimulationState = create_empty_simulation_state(2, 1, 1)
        self._force_completed = False
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
            with open(traffic_file, "r", encoding="utf-8")as f:
                file_data = json.load(f)
            building_config = file_data["building"]
            server_debug_log(f"Building config: {building_config}")
            self.state = create_empty_simulation_state(
                building_config["elevators"], building_config["floors"], building_config["elevator_capacity"]
            )
            self.reset()
            self.max_duration_ticks = building_config["duration"]
            self._force_completed = False  # 重置强制完成标志
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

    def next_traffic_round(self) -> bool:
        """切换到下一个流量文件，返回是否成功切换"""
        if not self.traffic_files:
            return False

        # 检查是否还有下一个文件
        next_index = self.current_traffic_index + 1
        if next_index >= len(self.traffic_files):
            return False  # 没有更多流量文件，停止模拟

        self.current_traffic_index = next_index
        self.load_current_traffic()  # 加载新的流量文件
        return True

    def load_traffic(self, traffic_file: str) -> None:
        """Load passenger traffic from JSON file using unified data models"""
        with open(traffic_file, "r") as f:
            traffic_data = json.load(f)

        server_debug_log(f"Loading traffic from {traffic_file}, {len(traffic_data)} entries")

        self.traffic_queue = []
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

    def add_passenger(
        self,
        origin: int,
        destination: int,
        tick: Optional[int] = None,
    ) -> int:
        """Add a passenger to the simulation using unified data models"""
        if tick is None:
            tick = self.tick

        passenger = PassengerInfo(
            id=self.next_passenger_id,
            origin=origin,
            destination=destination,
            arrive_tick=tick,
        )

        self.passengers[passenger.id] = passenger

        # Add to floor queue
        floor_state = self.state.get_floor_by_number(origin)
        if floor_state:
            if destination > origin:
                floor_state.add_waiting_passenger(passenger.id, Direction.UP)
                self._emit_event(EventType.UP_BUTTON_PRESSED, {"floor": origin})
            else:
                floor_state.add_waiting_passenger(passenger.id, Direction.DOWN)
                self._emit_event(EventType.DOWN_BUTTON_PRESSED, {"floor": origin})

        self.next_passenger_id += 1
        server_debug_log(f"Added passenger {passenger.id}: {origin}→{destination} at tick {tick}")
        return passenger.id

    def _emit_event(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """Emit an event to be sent to clients using unified data models"""
        self.state.add_event(event_type, data)
        server_debug_log(f"Event emitted: {event_type.value} with data {data}")

    def step(self, num_ticks: int = 1) -> List[SimulationEvent]:
        with self.lock:
            new_events: List[SimulationEvent] = []
            for i in range(num_ticks):
                self.state.tick += 1
                server_debug_log(f"Processing tick {self.tick} (step {i+1}/{num_ticks})")
                tick_events = self._process_tick()
                new_events.extend(tick_events)
                server_debug_log(f"Tick {self.tick} completed - Generated {len(tick_events)} events")

                # 如果到达最大时长且尚未强制完成，强制完成剩余乘客
                if (
                    hasattr(self, "max_duration_ticks")
                    and self.tick >= self.max_duration_ticks
                    and not self._force_completed
                ):
                    completed_count = self.force_complete_remaining_passengers()
                    self._force_completed = True
                    if completed_count > 0:
                        server_debug_log(f"模拟结束，强制完成了 {completed_count} 个乘客")

            server_debug_log(f"Step completed - Final tick: {self.tick}, Total events: {len(new_events)}")
            return new_events

    def _process_tick(self) -> List[SimulationEvent]:
        """Process one simulation tick"""
        events_start = len(self.state.events)
        # 1. Add new passengers from traffic queue
        self._process_arrivals()

        # 2. Move elevators
        self._move_elevators()

        # 3. Process elevator stops and passenger boarding/alighting
        self._process_elevator_stops()

        # Return events generated this tick
        return self.state.events[events_start:]

    def _process_arrivals(self) -> None:
        """Process new passenger arrivals"""
        while self.traffic_queue and self.traffic_queue[0].tick <= self.tick:
            traffic_entry = self.traffic_queue.pop(0)
            passenger = PassengerInfo(
                id=traffic_entry.id,
                origin=traffic_entry.origin,
                destination=traffic_entry.destination,
                arrive_tick=self.tick,
            )
            assert (
                traffic_entry.origin != traffic_entry.destination
            ), f"乘客{passenger.id}目的地和起始地{traffic_entry.origin}重复"
            self.passengers[passenger.id] = passenger
            server_debug_log(f"乘客 {passenger.id:4}： 创建 | {passenger}")
            if passenger.destination > passenger.origin:
                self.floors[passenger.origin].up_queue.append(passenger.id)
                self._emit_event(EventType.UP_BUTTON_PRESSED, {"floor": passenger.origin, "passenger": passenger.id})
            else:
                self.floors[passenger.origin].down_queue.append(passenger.id)
                self._emit_event(EventType.DOWN_BUTTON_PRESSED, {"floor": passenger.origin, "passenger": passenger.id})

    def _calculate_distance_to_target(self, elevator: ElevatorState) -> float:
        """计算到目标楼层的距离（以floor_up_position为单位）"""
        current_pos = elevator.position.current_floor * 10 + elevator.position.floor_up_position
        target_pos = elevator.target_floor * 10
        return abs(target_pos - current_pos)

    def _should_start_deceleration(self, elevator: ElevatorState) -> bool:
        """判断是否应该开始减速
        减速需要1个tick（移动1个位置单位），所以当距离目标<=3时开始减速
        这样可以保证有一个完整的减速周期
        """
        distance = self._calculate_distance_to_target(elevator)
        return distance <= 3

    def _get_movement_speed(self, elevator: ElevatorState) -> int:
        """根据电梯状态获取移动速度"""
        if elevator.run_status == ElevatorStatus.START_UP:
            return 1
        elif elevator.run_status == ElevatorStatus.START_DOWN:
            return 1
        elif elevator.run_status == ElevatorStatus.CONSTANT_SPEED:
            return 2
        else:  # STOPPED
            return 0

    def _update_elevator_status(self, elevator: ElevatorState) -> None:
        """更新电梯运行状态"""
        current_floor = elevator.position.current_floor
        target_floor = elevator.target_floor

        if current_floor == target_floor and elevator.position.floor_up_position == 0:
            # 已到达目标楼层
            elevator.run_status = ElevatorStatus.STOPPED
            return

        if elevator.run_status == ElevatorStatus.STOPPED:
            # 从停止状态启动
            elevator.run_status = ElevatorStatus.START_UP
        elif elevator.run_status == ElevatorStatus.START_UP:
            # 从启动状态切换到匀速
            elevator.run_status = ElevatorStatus.CONSTANT_SPEED
        elif elevator.run_status == ElevatorStatus.CONSTANT_SPEED:
            # 检查是否需要开始减速
            if self._should_start_deceleration(elevator):
                elevator.run_status = ElevatorStatus.START_DOWN
        # START_DOWN状态会在到达目标时自动切换为STOPPED

    def _move_elevators(self) -> None:
        """Move all elevators towards their destinations with acceleration/deceleration"""
        for elevator in self.elevators:
            target_floor = elevator.target_floor
            current_floor = elevator.position.current_floor

            # 如果已在恰好目标楼层，标记为STOPPED，之后交给_process_elevator_stops处理
            if target_floor == current_floor:
                if elevator.next_target_floor is None:
                    continue
                if elevator.position.floor_up_position == 0:
                    server_debug_log(
                        f"电梯{elevator.id}已在目标楼层，当前{elevator.position.current_floor_float} / 目标{target_floor}"
                    )
                    elevator.run_status = ElevatorStatus.STOPPED
                    continue

            # 更新电梯状态
            self._update_elevator_status(elevator)

            # 获取移动速度
            movement_speed = self._get_movement_speed(elevator)

            if movement_speed == 0:
                continue

            # Move towards target
            old_floor = current_floor

            # 根据状态和方向调整移动速度
            if elevator.target_floor_direction == Direction.UP:
                # 向上移动
                new_floor = elevator.position.floor_up_position_add(movement_speed)
            else:
                # 向下移动
                new_floor = elevator.position.floor_up_position_add(-movement_speed)

            server_debug_log(
                f"电梯{elevator.id} 状态:{elevator.run_status.value} 速度:{movement_speed} "
                f"位置:{elevator.position.current_floor_float:.1f} 目标:{target_floor}"
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
                self._emit_event(EventType.STOPPED_AT_FLOOR, {"elevator": elevator.id, "floor": new_floor})

            # elevator.energy_consumed += abs(direction * elevator.speed_pre_tick) * 0.5

    def _process_elevator_stops(self) -> None:
        """Handle passenger boarding and alighting at elevator stops"""
        for elevator in self.elevators:
            if not elevator.run_status == ElevatorStatus.STOPPED:
                continue
            current_floor = elevator.current_floor

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
            floor = self.floors[current_floor]
            passengers_to_board: List[int] = []
            if not elevator.indicators.up and not elevator.indicators.down:
                if elevator.next_target_floor is not None:
                    elevator.position.target_floor = elevator.next_target_floor
                    elevator.next_target_floor = None
                elevator.indicators.set_direction(elevator.target_floor_direction)

            # Board passengers going up (if up indicator is on or no direction set)
            if elevator.indicators.up:
                available_capacity = elevator.max_capacity - len(elevator.passengers)
                passengers_to_board.extend(floor.up_queue[:available_capacity])
                floor.up_queue = floor.up_queue[available_capacity:]

            # Board passengers going down (if down indicator is on or no direction set)
            if elevator.indicators.down:
                # 先临时计算长度
                remaining_capacity = elevator.max_capacity - len(elevator.passengers) - len(passengers_to_board)
                if remaining_capacity > 0:
                    down_passengers = floor.down_queue[:remaining_capacity]
                    passengers_to_board.extend(down_passengers)
                    floor.down_queue = floor.down_queue[remaining_capacity:]

            # 没有上下指示的时候，触发等待，会消耗一个tick
            if not elevator.indicators.up and not elevator.indicators.down:
                self._emit_event(EventType.IDLE, {"elevator": elevator.id, "floor": current_floor})
                continue
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

    def elevator_go_to_floor(self, elevator_id: int, floor: int, immediate: bool = False) -> None:
        """Command elevator to go to specified floor"""
        if 0 <= elevator_id < len(self.elevators) and 0 <= floor < len(self.floors):
            elevator = self.elevators[elevator_id]
            if immediate:
                elevator.position.target_floor = floor
            else:
                elevator.next_target_floor = floor

    def elevator_set_indicators(self, elevator_id: int, up: Optional[bool] = None, down: Optional[bool] = None) -> None:
        """Set elevator direction indicators"""
        if 0 <= elevator_id < len(self.elevators):
            elevator = self.elevators[elevator_id]
            if up is not None:
                elevator.indicators.up = up
            if down is not None:
                elevator.indicators.down = down

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

    def _calculate_metrics(self) -> MetricsResponse:
        """Calculate performance metrics"""
        # 直接从state中筛选已完成的乘客
        completed = [p for p in self.state.passengers.values() if p.status == PassengerStatus.COMPLETED]

        total_passengers = len(self.state.passengers)
        if not completed:
            return MetricsResponse(
                done=0,
                total=total_passengers,
                avg_wait=0,
                p95_wait=0,
                avg_system=0,
                p95_system=0,
                energy_total=sum(e.energy_consumed for e in self.elevators),
            )

        wait_times = [float(p.wait_time) for p in completed]
        system_times = [float(p.system_time) for p in completed]

        def percentile(data: List[float], p: int) -> float:
            if not data:
                return 0.0
            sorted_data = sorted(data)
            index = int(len(sorted_data) * p / 100)
            return sorted_data[min(index, len(sorted_data) - 1)]

        return MetricsResponse(
            done=len(completed),
            total=total_passengers,
            avg_wait=sum(wait_times) / len(wait_times) if wait_times else 0,
            p95_wait=percentile(wait_times, 95),
            avg_system=sum(system_times) / len(system_times) if system_times else 0,
            p95_system=percentile(system_times, 95),
            energy_total=sum(e.energy_consumed for e in self.elevators),
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
        with self.lock:
            completed_count = 0
            current_tick = self.tick

            server_debug_log(f"强制完成未完成乘客，当前tick: {current_tick}")

            # 收集需要强制完成的乘客ID（使用set提高查找效率）
            passengers_to_complete = set()
            for passenger_id, passenger in self.state.passengers.items():
                if passenger.dropoff_tick == 0:
                    passengers_to_complete.add(passenger_id)

            server_debug_log(f"找到 {len(passengers_to_complete)} 个需要强制完成的乘客")

            # 批量处理：先从电梯中移除所有需要完成的乘客
            for elevator in self.elevators:
                # 使用列表推导式创建新的乘客列表，避免多次remove操作
                original_count = len(elevator.passengers)
                elevator.passengers = [pid for pid in elevator.passengers if pid not in passengers_to_complete]
                removed_count = original_count - len(elevator.passengers)

                # 清理乘客目的地映射
                for passenger_id in passengers_to_complete:
                    elevator.passenger_destinations.pop(passenger_id, None)

                if removed_count > 0:
                    server_debug_log(f"从电梯 {elevator.id} 移除了 {removed_count} 个强制完成的乘客")

            # 批量处理：从楼层等待队列中移除乘客
            for floor in self.floors:
                # 优化队列清理
                original_up = len(floor.up_queue)
                original_down = len(floor.down_queue)

                floor.up_queue = [pid for pid in floor.up_queue if pid not in passengers_to_complete]
                floor.down_queue = [pid for pid in floor.down_queue if pid not in passengers_to_complete]

                removed_up = original_up - len(floor.up_queue)
                removed_down = original_down - len(floor.down_queue)

                if removed_up > 0 or removed_down > 0:
                    server_debug_log(
                        f"从楼层 {floor.floor} 移除了 {removed_up}(上行) + {removed_down}(下行) 个等待乘客"
                    )

            # 最后设置乘客完成状态
            for passenger_id in passengers_to_complete:
                passenger = self.state.passengers[passenger_id]
                passenger.dropoff_tick = current_tick
                completed_count += 1

            server_debug_log(f"强制完成了 {completed_count} 个乘客")
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
            self._force_completed = False


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
        server_debug_log(f"HTTP /api/step request - ticks: {ticks}")
        events = simulation.step(ticks)
        server_debug_log(f"HTTP /api/step response - tick: {simulation.tick}, events: {len(events)}")
        return json_response(
            {
                "tick": simulation.tick,
                "events": [{"tick": e.tick, "type": e.type.value, "data": e.data} for e in events],
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


@app.route("/api/elevators/<int:elevator_id>/set_indicators", methods=["POST"])
def elevator_set_indicators(elevator_id: int) -> Response | tuple[Response, int]:
    try:
        data: Dict[str, Any] = request.get_json() or {}
        up = data.get("up")
        down = data.get("down")
        simulation.elevator_set_indicators(elevator_id, up, down)
        return json_response({"success": True})
    except Exception as e:
        return json_response({"error": str(e)}, 500)


@app.route("/api/traffic/next", methods=["POST"])
def next_traffic_round() -> Response | tuple[Response, int]:
    """切换到下一个流量文件"""
    try:
        success = simulation.next_traffic_round()
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


@app.route("/api/force_complete", methods=["POST"])
def force_complete_passengers() -> Response | tuple[Response, int]:
    """强制完成所有未完成的乘客"""
    try:
        completed_count = simulation.force_complete_remaining_passengers()
        return json_response({"success": True, "completed_count": completed_count})
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
