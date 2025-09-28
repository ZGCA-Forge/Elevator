#!/usr/bin/env python3
from typing import List

from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import SimulationEvent, Direction


class TestElevatorBusController(ElevatorController):
    def __init__(self):
        super().__init__("http://127.0.0.1:8000", True)

    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        pass

    def on_event_execute_start(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        pass

    def on_event_execute_end(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        pass

    def on_passenger_call(self, passenger:ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        pass

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        pass

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        pass

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        pass

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        pass

    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        pass

    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        pass

if __name__ == "__main__":
    algorithm = TestElevatorBusController()
    algorithm.start()
