from typing import Any

from elevator_saga.client.api_client import ElevatorAPIClient
from elevator_saga.core.models import ElevatorState, FloorState, PassengerInfo


class ProxyFloor(FloorState):
    """
    楼层动态代理类
    直接使用 FloorState 数据模型实例，提供完整的类型安全访问
    """

    _init_ok = False

    def __init__(self, floor_id: int, api_client: ElevatorAPIClient):
        self._floor_id = floor_id
        self._api_client = api_client
        self._cached_instance = None
        self._init_ok = True

    def _get_floor_state(self) -> FloorState:
        """获取 FloorState 实例"""
        state = self._api_client.get_state()
        floor_data = next((f for f in state.floors if f.floor == self._floor_id), None)
        if floor_data is None:
            raise ValueError(f"Floor {self._floor_id} not found in state")
        return floor_data

    def __getattribute__(self, name: str) -> Any:
        if not name.startswith("_") and self._init_ok and name not in self.__class__.__dict__:
            try:
                self_attr = object.__getattribute__(self, name)
                if callable(self_attr):
                    return object.__getattribute__(self, name)
            except AttributeError:
                pass
            floor_state = self._get_floor_state()
            return floor_state.__getattribute__(name)
        else:
            return object.__getattribute__(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        """禁止修改属性，保持只读特性"""
        if not self._init_ok:
            object.__setattr__(self, name, value)
        else:
            raise AttributeError(f"Cannot modify read-only attribute '{name}'")

    def __repr__(self) -> str:
        return f"ProxyFloor(floor={self._floor_id})"


class ProxyElevator(ElevatorState):
    """
    电梯动态代理类
    直接使用 ElevatorState 数据模型实例，提供完整的类型安全访问和操作方法
    """

    _init_ok = False

    def __init__(self, elevator_id: int, api_client: ElevatorAPIClient):
        self._elevator_id = elevator_id
        self._api_client = api_client
        self._init_ok = True

    def _get_elevator_state(self) -> ElevatorState:
        """获取 ElevatorState 实例"""
        # 获取当前状态
        state = self._api_client.get_state()
        elevator_data = next((e for e in state.elevators if e.id == self._elevator_id), None)
        if elevator_data is None:
            raise ValueError(f"Elevator {self._elevator_id} not found in state")
        return elevator_data

    def __getattribute__(self, name: str) -> Any:
        if not name.startswith("_") and self._init_ok and name not in self.__class__.__dict__:
            try:
                self_attr = object.__getattribute__(self, name)
                if callable(self_attr):
                    return object.__getattribute__(self, name)
            except AttributeError:
                pass
            elevator_state = self._get_elevator_state()
            return elevator_state.__getattribute__(name)
        else:
            return object.__getattribute__(self, name)

    def go_to_floor(self, floor: int, immediate: bool = False) -> bool:
        """前往指定楼层"""
        return self._api_client.go_to_floor(self._elevator_id, floor, immediate)

    def __setattr__(self, name: str, value: Any) -> None:
        """禁止修改属性，保持只读特性"""
        if not self._init_ok:
            object.__setattr__(self, name, value)
        else:
            raise AttributeError(f"Cannot modify read-only attribute '{name}'")

    def __repr__(self) -> str:
        return f"ProxyElevator(id={self._elevator_id})"


class ProxyPassenger(PassengerInfo):
    """
    乘客动态代理类
    直接使用 PassengerInfo 数据模型实例，提供完整的类型安全访问
    """

    _init_ok = False

    def __init__(self, passenger_id: int, api_client: ElevatorAPIClient):
        self._passenger_id = passenger_id
        self._api_client = api_client
        self._init_ok = True

    def _get_passenger_info(self) -> PassengerInfo:
        """获取 PassengerInfo 实例"""
        state = self._api_client.get_state()
        passenger_data = state.passengers.get(self._passenger_id)
        if passenger_data is None:
            raise ValueError(f"Passenger {self._passenger_id} not found in state")
        return passenger_data

    def __getattribute__(self, name: str) -> Any:
        if not name.startswith("_") and self._init_ok and name not in self.__class__.__dict__:
            try:
                self_attr = object.__getattribute__(self, name)
                if callable(self_attr):
                    return object.__getattribute__(self, name)
            except AttributeError:
                pass
            psg_info = self._get_passenger_info()
            return psg_info.__getattribute__(name)
        else:
            return object.__getattribute__(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        """禁止修改属性，保持只读特性"""
        if not self._init_ok:
            object.__setattr__(self, name, value)
        else:
            raise AttributeError(f"Cannot modify read-only attribute '{name}'")

    def __repr__(self) -> str:
        return f"ProxyPassenger(id={self._passenger_id})"
