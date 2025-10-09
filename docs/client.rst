Client Architecture and Proxy Models
====================================

The Elevator Saga client provides a powerful abstraction layer that allows you to interact with the simulation using dynamic proxy objects. This architecture provides type-safe, read-only access to simulation state while enabling elevator control commands.

Overview
--------

The client architecture consists of three main components:

1. **Proxy Models** (``proxy_models.py``): Dynamic proxies that provide transparent access to server state
2. **API Client** (``api_client.py``): HTTP client for communicating with the server
3. **Base Controller** (``base_controller.py``): Abstract base class for implementing control algorithms

Proxy Models
------------

Proxy models in ``elevator_saga/client/proxy_models.py`` provide a clever way to access remote state as if it were local. They inherit from the data models but override attribute access to fetch fresh data from the server.

How Proxy Models Work
~~~~~~~~~~~~~~~~~~~~~~

The proxy pattern implementation uses Python's ``__getattribute__`` magic method to intercept attribute access:

1. When you access an attribute (e.g., ``elevator.current_floor``), the proxy intercepts the call
2. The proxy fetches the latest state from the server via API client
3. The proxy returns the requested attribute from the fresh state
4. All accesses are **read-only** to maintain consistency

This design ensures you always work with the most up-to-date simulation state without manual refresh calls.

ProxyElevator
~~~~~~~~~~~~~

Dynamic proxy for ``ElevatorState`` that provides access to elevator properties and control methods:

.. code-block:: python

   class ProxyElevator(ElevatorState):
       """
       Dynamic proxy for elevator state
       Provides complete type-safe access and control methods
       """

       def __init__(self, elevator_id: int, api_client: ElevatorAPIClient):
           self._elevator_id = elevator_id
           self._api_client = api_client
           self._init_ok = True

       def go_to_floor(self, floor: int, immediate: bool = False) -> bool:
           """Command elevator to go to specified floor"""
           return self._api_client.go_to_floor(self._elevator_id, floor, immediate)

**Accessible Properties** (from ElevatorState):

- ``id``: Elevator identifier
- ``current_floor``: Current floor number
- ``current_floor_float``: Precise position (e.g., 2.5)
- ``target_floor``: Destination floor
- ``position``: Full Position object
- ``passengers``: List of passenger IDs on board
- ``max_capacity``: Maximum passenger capacity
- ``run_status``: Current ElevatorStatus
- ``target_floor_direction``: Direction to target (UP/DOWN/STOPPED)
- ``last_tick_direction``: Previous movement direction
- ``is_idle``: Whether stopped
- ``is_full``: Whether at capacity
- ``is_running``: Whether in motion
- ``pressed_floors``: Destination floors of current passengers
- ``load_factor``: Current load (0.0 to 1.0)
- ``indicators``: Up/down indicator lights

**Control Method**:

- ``go_to_floor(floor, immediate=False)``: Send elevator to floor

  - ``immediate=True``: Change target immediately
  - ``immediate=False``: Queue as next target after current destination

**Example Usage**:

.. code-block:: python

   # Access elevator state
   print(f"Elevator {elevator.id} at floor {elevator.current_floor}")
   print(f"Direction: {elevator.target_floor_direction.value}")
   print(f"Passengers: {len(elevator.passengers)}/{elevator.max_capacity}")

   # Check status
   if elevator.is_idle:
       print("Elevator is idle")
   elif elevator.is_full:
       print("Elevator is full!")

   # Control elevator
   if elevator.current_floor == 0:
       elevator.go_to_floor(5)  # Send to floor 5

ProxyFloor
~~~~~~~~~~

Dynamic proxy for ``FloorState`` that provides access to floor information:

.. code-block:: python

   class ProxyFloor(FloorState):
       """
       Dynamic proxy for floor state
       Provides read-only access to floor information
       """

       def __init__(self, floor_id: int, api_client: ElevatorAPIClient):
           self._floor_id = floor_id
           self._api_client = api_client
           self._init_ok = True

**Accessible Properties** (from FloorState):

- ``floor``: Floor number
- ``up_queue``: List of passenger IDs waiting to go up
- ``down_queue``: List of passenger IDs waiting to go down
- ``has_waiting_passengers``: Whether any passengers are waiting
- ``total_waiting``: Total number of waiting passengers

**Example Usage**:

.. code-block:: python

   floor = floors[0]
   print(f"Floor {floor.floor}")
   print(f"Waiting to go up: {len(floor.up_queue)} passengers")
   print(f"Waiting to go down: {len(floor.down_queue)} passengers")

   if floor.has_waiting_passengers:
       print(f"Total waiting: {floor.total_waiting}")

ProxyPassenger
~~~~~~~~~~~~~~

Dynamic proxy for ``PassengerInfo`` that provides access to passenger information:

.. code-block:: python

   class ProxyPassenger(PassengerInfo):
       """
       Dynamic proxy for passenger information
       Provides read-only access to passenger data
       """

       def __init__(self, passenger_id: int, api_client: ElevatorAPIClient):
           self._passenger_id = passenger_id
           self._api_client = api_client
           self._init_ok = True

**Accessible Properties** (from PassengerInfo):

- ``id``: Passenger identifier
- ``origin``: Starting floor
- ``destination``: Target floor
- ``arrive_tick``: When passenger appeared
- ``pickup_tick``: When passenger boarded (0 if waiting)
- ``dropoff_tick``: When passenger reached destination (0 if in transit)
- ``elevator_id``: Current elevator ID (None if waiting)
- ``status``: Current PassengerStatus
- ``wait_time``: Ticks waited before boarding
- ``system_time``: Total ticks in system
- ``travel_direction``: UP or DOWN

**Example Usage**:

.. code-block:: python

   print(f"Passenger {passenger.id}")
   print(f"From floor {passenger.origin} to {passenger.destination}")
   print(f"Status: {passenger.status.value}")

   if passenger.status == PassengerStatus.IN_ELEVATOR:
       print(f"In elevator {passenger.elevator_id}")
       print(f"Waited {passenger.floor_wait_time} ticks")

Read-Only Protection
~~~~~~~~~~~~~~~~~~~~

All proxy models are **read-only**. Attempting to modify attributes will raise an error:

.. code-block:: python

   elevator.current_floor = 5  # ❌ Raises AttributeError
   elevator.passengers.append(123)  # ❌ Raises AttributeError

This ensures that:

1. Client cannot corrupt server state
2. All state changes go through proper API commands
3. State consistency is maintained

Implementation Details
~~~~~~~~~~~~~~~~~~~~~~

The proxy implementation uses a clever pattern with ``_init_ok`` flag:

.. code-block:: python

   class ProxyElevator(ElevatorState):
       _init_ok = False

       def __init__(self, elevator_id: int, api_client: ElevatorAPIClient):
           self._elevator_id = elevator_id
           self._api_client = api_client
           self._init_ok = True  # Enable proxy behavior

       def __getattribute__(self, name: str) -> Any:
           # During initialization, use normal attribute access
           if not name.startswith("_") and self._init_ok and name not in self.__class__.__dict__:
               # Try to find as a method of this class
               try:
                   self_attr = object.__getattribute__(self, name)
                   if callable(self_attr):
                       return object.__getattribute__(self, name)
               except AttributeError:
                   pass
               # Fetch fresh state and return attribute
               elevator_state = self._get_elevator_state()
               return elevator_state.__getattribute__(name)
           else:
               return object.__getattribute__(self, name)

       def __setattr__(self, name: str, value: Any) -> None:
           # Allow setting during initialization only
           if not self._init_ok:
               object.__setattr__(self, name, value)
           else:
               raise AttributeError(f"Cannot modify read-only attribute '{name}'")

This design:

1. Allows normal initialization of internal fields (``_elevator_id``, ``_api_client``)
2. Intercepts access to data attributes after initialization
3. Preserves access to class methods (like ``go_to_floor``)
4. Blocks all attribute modifications after initialization

Base Controller
---------------

The ``ElevatorController`` class in ``base_controller.py`` provides the framework for implementing control algorithms:

.. code-block:: python

   from elevator_saga.client.base_controller import ElevatorController
   from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
   from typing import List

   class MyController(ElevatorController):
       def __init__(self):
           super().__init__("http://127.0.0.1:8000", auto_run=True)

       def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
           """Called once at start with all elevators and floors"""
           print(f"Initialized with {len(elevators)} elevators")

       def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
           """Called when a passenger presses a button"""
           print(f"Passenger {passenger.id} at floor {floor.floor} going {direction}")

       def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
           """Called when elevator stops at a floor"""
           print(f"Elevator {elevator.id} stopped at floor {floor.floor}")
           # Implement your dispatch logic here

       def on_elevator_idle(self, elevator: ProxyElevator) -> None:
           """Called when elevator becomes idle"""
           # Send idle elevator somewhere useful
           elevator.go_to_floor(0)

The controller provides these event handlers:

- ``on_init(elevators, floors)``: Initialization
- ``on_event_execute_start(tick, events, elevators, floors)``: Before processing tick events
- ``on_event_execute_end(tick, events, elevators, floors)``: After processing tick events
- ``on_passenger_call(passenger, floor, direction)``: Button press
- ``on_elevator_stopped(elevator, floor)``: Elevator arrival
- ``on_elevator_idle(elevator)``: Elevator becomes idle
- ``on_passenger_board(elevator, passenger)``: Passenger boards
- ``on_passenger_alight(elevator, passenger, floor)``: Passenger alights
- ``on_elevator_passing_floor(elevator, floor, direction)``: Elevator passes floor
- ``on_elevator_approaching(elevator, floor, direction)``: Elevator about to arrive
- ``on_elevator_move(elevator, from_position, to_position, direction, status)``: Elevator moves

Complete Example
----------------

Here's a simple controller that sends idle elevators to the ground floor:

.. code-block:: python

   #!/usr/bin/env python3
   from typing import List
   from elevator_saga.client.base_controller import ElevatorController
   from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger

   class SimpleController(ElevatorController):
       def __init__(self):
           super().__init__("http://127.0.0.1:8000", auto_run=True)
           self.pending_calls = []

       def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
           print(f"Controlling {len(elevators)} elevators in {len(floors)}-floor building")

       def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
           print(f"Call from floor {floor.floor}, direction {direction}")
           self.pending_calls.append((floor.floor, direction))
           # Dispatch nearest idle elevator
           self._dispatch_to_call(floor.floor)

       def on_elevator_idle(self, elevator: ProxyElevator) -> None:
           if self.pending_calls:
               floor, direction = self.pending_calls.pop(0)
               elevator.go_to_floor(floor)
           else:
               # No calls, return to ground floor
               elevator.go_to_floor(0)

       def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
           print(f"Elevator {elevator.id} at floor {floor.floor}")
           print(f"  Passengers on board: {len(elevator.passengers)}")
           print(f"  Waiting at floor: {floor.total_waiting}")

       def _dispatch_to_call(self, floor: int) -> None:
           # Find nearest idle elevator and send it
           # (Simplified - real implementation would be more sophisticated)
           pass

   if __name__ == "__main__":
       controller = SimpleController()
       controller.start()

Benefits of Proxy Architecture
-------------------------------

1. **Type Safety**: IDE autocomplete and type checking work perfectly
2. **Always Fresh**: No need to manually refresh state
3. **Clean API**: Access remote state as if it were local
4. **Read-Only Safety**: Cannot accidentally corrupt server state
5. **Separation of Concerns**: State management handled by proxies, logic in controller
6. **Testability**: Can mock API client for unit tests

Next Steps
----------

- See :doc:`communication` for details on the HTTP API
- See :doc:`events` for understanding the event-driven simulation
- Check ``client_examples/bus_example.py`` for a complete implementation
