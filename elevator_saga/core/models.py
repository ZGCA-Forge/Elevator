#!/usr/bin/env python3
"""
Elevator Saga Data Models
统一的数据模型定义，用于客户端和服务器的类型一致性和序列化
"""
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union

# 类型变量
T = TypeVar("T", bound="SerializableModel")


class Direction(Enum):
    """电梯方向枚举"""

    UP = "up"
    DOWN = "down"
    STOPPED = "stopped"


class PassengerStatus(Enum):
    """乘客状态枚举"""

    WAITING = "waiting"
    IN_ELEVATOR = "in_elevator"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ElevatorStatus(Enum):  # OK
    """
    电梯运行状态机：stopped -1tick> start_up -1tick> constant_speed -?tick> start_down -1tick> stopped
    注意：START_UP/START_DOWN表示加速/减速状态，不表示移动方向
    实际移动方向由target_floor_direction属性决定
    """

    START_UP = "start_up"  # 启动加速状态（不表示向上方向）
    START_DOWN = "start_down"  # 减速状态（不表示向下方向）
    CONSTANT_SPEED = "constant_speed"  # 匀速状态
    STOPPED = "stopped"  # 停止状态


class EventType(Enum):
    """事件类型枚举"""

    UP_BUTTON_PRESSED = "up_button_pressed"
    DOWN_BUTTON_PRESSED = "down_button_pressed"
    PASSING_FLOOR = "passing_floor"
    STOPPED_AT_FLOOR = "stopped_at_floor"
    ELEVATOR_APPROACHING = "elevator_approaching"  # 电梯即将经过某层楼（START_DOWN状态）
    IDLE = "idle"
    PASSENGER_BOARD = "passenger_board"
    PASSENGER_ALIGHT = "passenger_alight"
    ELEVATOR_MOVE = "elevator_move"  # 电梯移动事件


class SerializableModel:
    """可序列化模型基类"""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)  # type: ignore

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), default=self._json_serializer)

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """从字典创建实例"""
        # 过滤掉init=False的字段
        import inspect

        sig = inspect.signature(cls.__init__)
        valid_params = set(sig.parameters.keys()) - {"self"}

        filtered_data = {k: v for k, v in data.items() if k in valid_params}
        instance = cls(**filtered_data)
        for k, v in cls.__dict__.items():
            if issubclass(v.__class__, Enum):  # 要求不能为None
                value = getattr(instance, k)
                setattr(instance, k, v.__class__(value))
        return instance

    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @staticmethod
    def _json_serializer(obj: Any) -> Union[Any, str]:
        """JSON序列化器，处理特殊类型"""
        if isinstance(obj, Enum):
            return obj.value
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, "to_dict"):
            return obj.to_dict()
        return str(obj)


@dataclass
class Position(SerializableModel):
    """位置信息"""

    current_floor: int = 0
    target_floor: int = 0
    floor_up_position: int = 0

    @property
    def current_floor_float(self) -> float:
        return round(self.current_floor + self.floor_up_position / 10, 1)

    def floor_up_position_add(self, num: int) -> int:
        self.floor_up_position += num

        # 处理向上楼层跨越
        while self.floor_up_position >= 10:
            self.current_floor += 1
            self.floor_up_position -= 10

        # 处理向下楼层跨越
        while self.floor_up_position <= -10:
            self.current_floor -= 1
            self.floor_up_position += 10

        return self.current_floor


@dataclass
class ElevatorIndicators(SerializableModel):
    """电梯指示灯状态"""

    up: bool = False
    down: bool = False

    def set_direction(self, direction: Direction) -> None:
        """根据方向设置指示灯"""
        if direction == Direction.UP:
            self.up = True
            self.down = False
        elif direction == Direction.DOWN:
            self.up = False
            self.down = True
        else:
            self.up = False
            self.down = False


@dataclass
class PassengerInfo(SerializableModel):
    """乘客信息"""

    id: int
    origin: int
    destination: int
    arrive_tick: int
    pickup_tick: int = 0
    dropoff_tick: int = 0
    arrived: bool = False
    elevator_id: Optional[int] = None

    @property
    def status(self) -> PassengerStatus:
        """乘客状态"""
        if self.arrived:
            return PassengerStatus.COMPLETED
        elif self.pickup_tick > 0:
            return PassengerStatus.IN_ELEVATOR
        else:
            return PassengerStatus.WAITING

    @property
    def floor_wait_time(self) -> int:
        """在楼层等待的时间（从到达到上电梯）"""
        return self.pickup_tick - self.arrive_tick

    @property
    def arrival_wait_time(self) -> int:
        """总等待时间（从到达到下电梯）"""
        return self.dropoff_tick - self.arrive_tick

    @property
    def travel_direction(self) -> Direction:
        """移动方向"""
        if self.destination > self.origin:
            return Direction.UP
        elif self.destination < self.origin:
            return Direction.DOWN
        else:
            return Direction.STOPPED


@dataclass
class ElevatorState(SerializableModel):
    """电梯状态"""

    id: int
    position: Position
    next_target_floor: Optional[int] = None
    passengers: List[int] = field(default_factory=list)  # 乘客ID列表
    max_capacity: int = 10
    speed_pre_tick: float = 0.5
    run_status: ElevatorStatus = ElevatorStatus.STOPPED
    last_tick_direction: Direction = Direction.STOPPED
    indicators: ElevatorIndicators = field(default_factory=ElevatorIndicators)
    passenger_destinations: Dict[int, int] = field(default_factory=dict)  # 乘客ID -> 目的地楼层映射
    energy_consumed: float = 0.0
    energy_rate: float = 1.0  # 能耗率：每tick消耗的能量单位
    last_update_tick: int = 0

    @property
    def current_floor(self) -> int:
        """当前楼层"""
        if isinstance(self.position, dict):
            self.position = Position.from_dict(self.position)
        return self.position.current_floor

    @property
    def current_floor_float(self) -> float:
        """当前楼层"""
        if isinstance(self.position, dict):
            self.position = Position.from_dict(self.position)  # type: ignore[arg-type]
        return self.position.current_floor_float

    @property
    def target_floor(self) -> int:
        """当前楼层"""
        if isinstance(self.position, dict):
            self.position = Position.from_dict(self.position)
        return self.position.target_floor

    @property
    def load_factor(self) -> float:
        """载重系数"""
        return len(self.passengers) / self.max_capacity

    @property
    def target_floor_direction(self) -> Direction:
        """目标方向"""
        next_floor = self.target_floor
        if next_floor > self.current_floor:
            return Direction.UP
        elif next_floor < self.current_floor:
            return Direction.DOWN
        else:
            return Direction.STOPPED

    @property
    def is_idle(self) -> bool:
        """是否空闲"""
        return self.run_status == ElevatorStatus.STOPPED

    @property
    def is_full(self) -> bool:
        """是否满载"""
        return len(self.passengers) >= self.max_capacity

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self.run_status in [ElevatorStatus.START_UP, ElevatorStatus.START_DOWN, ElevatorStatus.CONSTANT_SPEED]

    @property
    def pressed_floors(self) -> List[int]:
        """按下的楼层（基于当前乘客的目的地动态计算）"""
        return sorted(list(set(self.passenger_destinations.values())))

    def clear_destinations(self) -> None:
        """清空目标队列"""
        self.next_target_floor = None


@dataclass
class FloorState(SerializableModel):
    """楼层状态"""

    floor: int
    up_queue: List[int] = field(default_factory=list)  # 等待上行的乘客ID
    down_queue: List[int] = field(default_factory=list)  # 等待下行的乘客ID

    @property
    def has_waiting_passengers(self) -> bool:
        """是否有等待的乘客"""
        return len(self.up_queue) > 0 or len(self.down_queue) > 0

    @property
    def total_waiting(self) -> int:
        """总等待人数"""
        return len(self.up_queue) + len(self.down_queue)

    def add_waiting_passenger(self, passenger_id: int, direction: Direction) -> None:
        """添加等待乘客"""
        if direction == Direction.UP:
            if passenger_id not in self.up_queue:
                self.up_queue.append(passenger_id)
        elif direction == Direction.DOWN:
            if passenger_id not in self.down_queue:
                self.down_queue.append(passenger_id)

    def remove_waiting_passenger(self, passenger_id: int) -> bool:
        """移除等待乘客"""
        if passenger_id in self.up_queue:
            self.up_queue.remove(passenger_id)
            return True
        if passenger_id in self.down_queue:
            self.down_queue.remove(passenger_id)
            return True
        return False


@dataclass
class SimulationEvent(SerializableModel):
    """模拟事件"""

    tick: int
    type: EventType
    data: Dict[str, Any]
    timestamp: Optional[str] = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


@dataclass
class PerformanceMetrics(SerializableModel):
    """性能指标"""

    completed_passengers: int = 0
    total_passengers: int = 0
    average_floor_wait_time: float = 0.0
    p95_floor_wait_time: float = 0.0
    average_arrival_wait_time: float = 0.0
    p95_arrival_wait_time: float = 0.0
    total_energy_consumption: float = 0.0

    @property
    def completion_rate(self) -> float:
        """完成率"""
        if self.total_passengers == 0:
            return 0.0
        return self.completed_passengers / self.total_passengers


@dataclass
class SimulationState(SerializableModel):
    """模拟状态"""

    tick: int
    elevators: List[ElevatorState]
    floors: List[FloorState]
    passengers: Dict[int, PassengerInfo] = field(default_factory=dict)
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    events: List[SimulationEvent] = field(default_factory=list)

    def get_elevator_by_id(self, elevator_id: int) -> Optional[ElevatorState]:
        """根据ID获取电梯"""
        for elevator in self.elevators:
            if elevator.id == elevator_id:
                return elevator
        return None

    def get_floor_by_number(self, floor_number: int) -> Optional[FloorState]:
        """根据楼层号获取楼层"""
        for floor in self.floors:
            if floor.floor == floor_number:
                return floor
        return None

    def get_passengers_by_status(self, status: PassengerStatus) -> List[PassengerInfo]:
        """根据状态获取乘客"""
        return [p for p in self.passengers.values() if p.status == status]

    def add_event(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """添加事件"""
        event = SimulationEvent(tick=self.tick, type=event_type, data=data)
        self.events.append(event)


# ==================== HTTP API 数据模型 ====================


@dataclass
class APIRequest(SerializableModel):
    """API请求基类"""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class APIResponse(SerializableModel):
    """API响应基类"""

    success: bool
    request_id: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class StepRequest(APIRequest):
    """步进请求"""

    ticks: int = 1


@dataclass
class StepResponse(SerializableModel):
    """步进响应"""

    success: bool
    tick: int
    events: List[SimulationEvent] = field(default_factory=list)
    request_id: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class StateRequest(APIRequest):
    """状态请求"""

    include_passengers: bool = True
    include_events: bool = False
    since_tick: Optional[int] = None


@dataclass
class ElevatorCommand(SerializableModel):
    """电梯命令"""

    elevator_id: int
    command_type: str  # "go_to_floor", "stop"
    parameters: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ElevatorCommandResponse(SerializableModel):
    """电梯命令响应"""

    success: bool
    elevator_id: int


@dataclass
class GoToFloorCommand(SerializableModel):
    """前往楼层命令"""

    elevator_id: int
    floor: int
    immediate: bool = False
    command_type: str = field(default="go_to_floor", init=False)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"floor": self.floor, "immediate": self.immediate}


# ==================== 流量和配置数据模型 ====================


@dataclass
class TrafficEntry(SerializableModel):
    """流量条目"""

    id: int
    origin: int
    destination: int
    tick: int


@dataclass
class TrafficPattern(SerializableModel):
    """流量模式"""

    name: str
    description: str
    entries: List[TrafficEntry] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_entry(self, entry: TrafficEntry) -> None:
        """添加流量条目"""
        self.entries.append(entry)

    def get_entries_for_tick(self, tick: int) -> List[TrafficEntry]:
        """获取指定tick的流量条目"""
        return [entry for entry in self.entries if entry.tick == tick]

    @property
    def total_passengers(self) -> int:
        """总乘客数"""
        return len(self.entries)

    @property
    def duration(self) -> int:
        """流量持续时间"""
        if not self.entries:
            return 0
        return max(entry.tick for entry in self.entries)


# ==================== 便捷构造函数 ====================


def create_empty_simulation_state(elevators: int, floors: int, max_capacity: int) -> SimulationState:
    """创建空的模拟状态"""
    elevator_states = [ElevatorState(id=i, position=Position(), max_capacity=max_capacity) for i in range(elevators)]
    floor_states = [FloorState(floor=i) for i in range(floors)]
    return SimulationState(tick=0, elevators=elevator_states, floors=floor_states)


def create_simple_traffic_pattern(name: str, passengers: List[Tuple[int, int, int]]) -> TrafficPattern:
    """创建简单流量模式

    Args:
        name: 模式名称
        passengers: [(origin, destination, tick), ...]
    """
    entries = []
    for i, (origin, destination, tick) in enumerate(passengers, 1):
        entry = TrafficEntry(id=i, origin=origin, destination=destination, tick=tick)
        entries.append(entry)

    return TrafficPattern(
        name=name, description=f"Simple traffic pattern with {len(passengers)} passengers", entries=entries
    )
