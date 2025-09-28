from typing import Any

from elevator_saga.client.api_client import ElevatorAPIClient
from elevator_saga.core.models import ElevatorState, FloorState, PassengerInfo


class ProxyFloor(FloorState):
    """
    楼层动态代理类
    直接使用 FloorState 数据模型实例，提供完整的类型安全访问
    """

    init_ok = False

    def __init__(self, floor_id: int, api_client: ElevatorAPIClient):
        self._floor_id = floor_id
        self._api_client = api_client
        self._cached_instance = None
        self.init_ok = True

    def _get_floor_state(self) -> FloorState:
        """获取 FloorState 实例"""
        # 获取当前状态
        state = self._api_client.get_state()
        floor_data = next((f for f in state.floors if f.floor == self._floor_id), None)

        if floor_data is None:
            raise AttributeError(f"Floor {self._floor_id} not found")

        # 如果是字典，转换为 FloorState 实例
        if isinstance(floor_data, dict):
            return FloorState.from_dict(floor_data)
        else:
            # 如果已经是 FloorState 实例，直接返回
            return floor_data

    def __getattr__(self, name: str) -> Any:
        """动态获取楼层属性"""
        floor_state = self._get_floor_state()
        try:
            if hasattr(floor_state, name):
                attr = getattr(floor_state, name)
                # 如果是 property 或方法，调用并返回结果
                if callable(attr):
                    return attr()
                else:
                    return attr
        except AttributeError:

            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        """禁止修改属性，保持只读特性"""
        if not self.init_ok:
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

    init_ok = False

    def __init__(self, elevator_id: int, api_client: ElevatorAPIClient):
        self._elevator_id = elevator_id
        self._api_client = api_client
        self.init_ok = True

    def _get_elevator_state(self) -> ElevatorState:
        """获取 ElevatorState 实例"""
        # 获取当前状态
        state = self._api_client.get_state()
        elevator_data = next((e for e in state.elevators if e.id == self._elevator_id), None)

        if elevator_data is None:
            raise AttributeError(f"Elevator {self._elevator_id} not found")

        # 如果是字典，转换为 ElevatorState 实例
        if isinstance(elevator_data, dict):
            return ElevatorState.from_dict(elevator_data)
        else:
            # 如果已经是 ElevatorState 实例，直接返回
            return elevator_data

    def __getattr__(self, name: str) -> Any:
        """动态获取电梯属性"""
        try:
            elevator_state = self._get_elevator_state()
            # 直接从 ElevatorState 实例获取属性
            return getattr(elevator_state, name)

        except AttributeError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def go_to_floor(self, floor: int, immediate: bool = False) -> bool:
        """前往指定楼层"""
        return self._api_client.go_to_floor(self._elevator_id, floor, immediate)

    def set_up_indicator(self, value: bool) -> None:
        """设置上行指示器"""
        self._api_client.set_indicators(self._elevator_id, up=value)

    def set_down_indicator(self, value: bool) -> None:
        """设置下行指示器"""
        self._api_client.set_indicators(self._elevator_id, down=value)

    def __setattr__(self, name: str, value: Any) -> None:
        """禁止修改属性，保持只读特性"""
        if not self.init_ok:
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

    init_ok = False

    def __init__(self, passenger_id: int, api_client: ElevatorAPIClient):
        self._passenger_id = passenger_id
        self._api_client = api_client
        self.init_ok = True

    def _get_passenger_info(self) -> PassengerInfo:
        """获取 PassengerInfo 实例"""
        # 获取当前状态
        state = self._api_client.get_state()

        # 在乘客字典中查找
        passenger_data = state.passengers.get(self._passenger_id)
        if passenger_data is None:
            raise AttributeError(f"Passenger {self._passenger_id} not found")

        # 如果是字典，转换为 PassengerInfo 实例
        if isinstance(passenger_data, dict):
            return PassengerInfo.from_dict(passenger_data)
        else:
            # 如果已经是 PassengerInfo 实例，直接返回
            return passenger_data

    def __getattr__(self, name: str) -> Any:
        """动态获取乘客属性"""
        try:
            passenger_info = self._get_passenger_info()
            # 直接从 PassengerInfo 实例获取属性
            return getattr(passenger_info, name)

        except AttributeError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        """禁止修改属性，保持只读特性"""
        if not self.init_ok:
            object.__setattr__(self, name, value)
        else:
            raise AttributeError(f"Cannot modify read-only attribute '{name}'")

    def __repr__(self) -> str:
        return f"ProxyPassenger(id={self._passenger_id})"
