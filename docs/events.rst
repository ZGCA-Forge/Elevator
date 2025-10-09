Event-Driven Simulation and Tick-Based Execution
================================================

Elevator Saga uses an **event-driven, tick-based** discrete simulation model. The simulation progresses in discrete time steps (ticks), and events are generated to notify the controller about state changes.

Simulation Overview
-------------------

.. code-block:: text

   ┌──────────────────────────────────────────────────────────┐
   │                  Simulation Loop                         │
   │                                                          │
   │  Tick N                                                  │
   │    1. Update elevator status (START_UP → CONSTANT_SPEED) │
   │    2. Process arrivals (new passengers)                  │
   │    3. Move elevators (physics simulation)                │
   │    4. Process stops (boarding/alighting)                 │
   │    5. Generate events                                    │
   │                                                          │
   │  Events sent to client → Client processes → Commands     │
   │                                                          │
   │  Tick N+1                                                │
   │    (repeat...)                                           │
   └──────────────────────────────────────────────────────────┘

Tick-Based Execution
--------------------

What is a Tick?
~~~~~~~~~~~~~~~

A **tick** is the fundamental unit of simulation time. Each tick represents one discrete time step where:

1. Physics is updated (elevators move)
2. State changes occur (passengers board/alight)
3. Events are generated
4. Controller receives events and makes decisions

Think of it like frames in a video game - the simulation updates at discrete intervals.

Tick Processing Flow
~~~~~~~~~~~~~~~~~~~~

In ``simulator.py``, the ``step()`` method processes ticks:

.. code-block:: python

   def step(self, num_ticks: int = 1) -> List[SimulationEvent]:
       """Process one or more simulation ticks"""
       with self.lock:
           new_events = []
           for _ in range(num_ticks):
               self.state.tick += 1
               tick_events = self._process_tick()
               new_events.extend(tick_events)

               # Force complete passengers if max duration reached
               if self.tick >= self.max_duration_ticks:
                   completed_count = self.force_complete_remaining_passengers()

           return new_events

Each ``_process_tick()`` executes the four-phase cycle:

.. code-block:: python

   def _process_tick(self) -> List[SimulationEvent]:
       """Process one simulation tick"""
       events_start = len(self.state.events)

       # Phase 1: Update elevator status
       self._update_elevator_status()

       # Phase 2: Add new passengers from traffic queue
       self._process_arrivals()

       # Phase 3: Move elevators
       self._move_elevators()

       # Phase 4: Process elevator stops and passenger boarding/alighting
       self._process_elevator_stops()

       # Return events generated this tick
       return self.state.events[events_start:]

Elevator State Machine
-----------------------

Elevators transition through states each tick:

.. code-block:: text

   STOPPED ──(target set)──► START_UP ──(1 tick)──► CONSTANT_SPEED
                                                           │
                                                    (near target)
                                                           ▼
                                                      START_DOWN
                                                           │
                                                      (1 tick)
                                                           ▼
                               (arrived)               STOPPED

State Transitions
~~~~~~~~~~~~~~~~~

**Phase 1: Update Elevator Status** (``_update_elevator_status()``):

.. code-block:: python

   def _update_elevator_status(self) -> None:
       """Update elevator operational state"""
       for elevator in self.elevators:
           # If no direction, check for next target
           if elevator.target_floor_direction == Direction.STOPPED:
               if elevator.next_target_floor is not None:
                   self._set_elevator_target_floor(elevator, elevator.next_target_floor)
                   self._process_passenger_in()
                   elevator.next_target_floor = None
               else:
                   continue

           # Transition state machine
           if elevator.run_status == ElevatorStatus.STOPPED:
               # Start acceleration
               elevator.run_status = ElevatorStatus.START_UP
           elif elevator.run_status == ElevatorStatus.START_UP:
               # Switch to constant speed after 1 tick
               elevator.run_status = ElevatorStatus.CONSTANT_SPEED

**Important Notes**:

- ``START_UP`` = acceleration (not direction!)
- ``START_DOWN`` = deceleration (not direction!)
- Actual movement direction is ``target_floor_direction`` (UP/DOWN)
- State transitions happen **before** movement

Movement Physics
----------------

Speed by State
~~~~~~~~~~~~~~

Elevators move at different speeds depending on their state:

.. code-block:: python

   def _move_elevators(self) -> None:
       """Move all elevators towards their destinations"""
       for elevator in self.elevators:
           # Determine speed based on state
           movement_speed = 0
           if elevator.run_status == ElevatorStatus.START_UP:
               movement_speed = 1      # Accelerating: 0.1 floors/tick
           elif elevator.run_status == ElevatorStatus.START_DOWN:
               movement_speed = 1      # Decelerating: 0.1 floors/tick
           elif elevator.run_status == ElevatorStatus.CONSTANT_SPEED:
               movement_speed = 2      # Full speed: 0.2 floors/tick

           if movement_speed == 0:
               continue

           # Apply movement in appropriate direction
           if elevator.target_floor_direction == Direction.UP:
               new_floor = elevator.position.floor_up_position_add(movement_speed)
           elif elevator.target_floor_direction == Direction.DOWN:
               new_floor = elevator.position.floor_up_position_add(-movement_speed)

Position System
~~~~~~~~~~~~~~~

Positions use a **10-unit sub-floor** system:

- ``current_floor = 2, floor_up_position = 0`` → exactly at floor 2
- ``current_floor = 2, floor_up_position = 5`` → halfway between floors 2 and 3
- ``current_floor = 2, floor_up_position = 10`` → advances to ``current_floor = 3, floor_up_position = 0``

This granularity allows smooth movement and precise deceleration timing.

Deceleration Logic
~~~~~~~~~~~~~~~~~~

Elevators must decelerate before stopping:

.. code-block:: python

   def _should_start_deceleration(self, elevator: ElevatorState) -> bool:
       """Check if should start decelerating"""
       distance = self._calculate_distance_to_target(elevator)
       return distance == 1  # Start deceleration 1 position unit before target

   # In _move_elevators():
   if elevator.run_status == ElevatorStatus.CONSTANT_SPEED:
       if self._should_start_deceleration(elevator):
           elevator.run_status = ElevatorStatus.START_DOWN

This ensures elevators don't overshoot their target floor.

Event System
------------

Event Types
~~~~~~~~~~~

The simulation generates 9 types of events defined in ``EventType`` enum:

.. code-block:: python

   class EventType(Enum):
       UP_BUTTON_PRESSED = "up_button_pressed"
       DOWN_BUTTON_PRESSED = "down_button_pressed"
       PASSING_FLOOR = "passing_floor"
       STOPPED_AT_FLOOR = "stopped_at_floor"
       ELEVATOR_APPROACHING = "elevator_approaching"
       IDLE = "idle"
       PASSENGER_BOARD = "passenger_board"
       PASSENGER_ALIGHT = "passenger_alight"
       ELEVATOR_MOVE = "elevator_move"

Event Generation
~~~~~~~~~~~~~~~~

Events are generated during tick processing:

**Passenger Arrival**:

.. code-block:: python

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
           self.passengers[passenger.id] = passenger

           if passenger.destination > passenger.origin:
               self.floors[passenger.origin].up_queue.append(passenger.id)
               # Generate UP_BUTTON_PRESSED event
               self._emit_event(
                   EventType.UP_BUTTON_PRESSED,
                   {"floor": passenger.origin, "passenger": passenger.id}
               )
           else:
               self.floors[passenger.origin].down_queue.append(passenger.id)
               # Generate DOWN_BUTTON_PRESSED event
               self._emit_event(
                   EventType.DOWN_BUTTON_PRESSED,
                   {"floor": passenger.origin, "passenger": passenger.id}
               )

**Elevator Movement**:

.. code-block:: python

   def _move_elevators(self) -> None:
       for elevator in self.elevators:
           # ... movement logic ...

           # Elevator moves
           if elevator.target_floor_direction != Direction.STOPPED:
               self._emit_event(
                   EventType.ELEVATOR_MOVE,
                   {
                       "elevator": elevator.id,
                       "from_position": old_position,
                       "to_position": elevator.position.current_floor_float,
                       "direction": elevator.target_floor_direction.value,
                       "status": elevator.run_status.value,
                   }
               )

           # Passing a floor
           if old_floor != new_floor and new_floor != target_floor:
               self._emit_event(
                   EventType.PASSING_FLOOR,
                   {
                       "elevator": elevator.id,
                       "floor": new_floor,
                       "direction": elevator.target_floor_direction.value
                   }
               )

           # About to arrive (during deceleration)
           if self._near_next_stop(elevator):
               self._emit_event(
                   EventType.ELEVATOR_APPROACHING,
                   {
                       "elevator": elevator.id,
                       "floor": int(round(elevator.position.current_floor_float)),
                       "direction": elevator.target_floor_direction.value
                   }
               )

           # Arrived at target
           if target_floor == new_floor and elevator.position.floor_up_position == 0:
               elevator.run_status = ElevatorStatus.STOPPED
               self._emit_event(
                   EventType.STOPPED_AT_FLOOR,
                   {
                       "elevator": elevator.id,
                       "floor": new_floor,
                       "reason": "move_reached"
                   }
               )

**Boarding and Alighting**:

.. code-block:: python

   def _process_elevator_stops(self) -> None:
       for elevator in self.elevators:
           if elevator.run_status != ElevatorStatus.STOPPED:
               continue

           current_floor = elevator.current_floor

           # Passengers alight
           passengers_to_remove = []
           for passenger_id in elevator.passengers:
               passenger = self.passengers[passenger_id]
               if passenger.destination == current_floor:
                   passenger.dropoff_tick = self.tick
                   passengers_to_remove.append(passenger_id)

           for passenger_id in passengers_to_remove:
               elevator.passengers.remove(passenger_id)
               self._emit_event(
                   EventType.PASSENGER_ALIGHT,
                   {"elevator": elevator.id, "floor": current_floor, "passenger": passenger_id}
               )

**Idle Detection**:

.. code-block:: python

   # If elevator stopped with no direction, it's idle
   if elevator.last_tick_direction == Direction.STOPPED:
       self._emit_event(
           EventType.IDLE,
           {"elevator": elevator.id, "floor": current_floor}
       )

Event Processing in Controller
-------------------------------

The ``ElevatorController`` base class automatically routes events to handler methods:

.. code-block:: python

   class ElevatorController(ABC):
       def _execute_events(self, events: List[SimulationEvent]) -> None:
           """Process events and route to handlers"""
           for event in events:
               if event.type == EventType.UP_BUTTON_PRESSED:
                   passenger_id = event.data["passenger"]
                   floor = self.floors[event.data["floor"]]
                   passenger = ProxyPassenger(passenger_id, self.api_client)
                   self.on_passenger_call(passenger, floor, "up")

               elif event.type == EventType.DOWN_BUTTON_PRESSED:
                   passenger_id = event.data["passenger"]
                   floor = self.floors[event.data["floor"]]
                   passenger = ProxyPassenger(passenger_id, self.api_client)
                   self.on_passenger_call(passenger, floor, "down")

               elif event.type == EventType.STOPPED_AT_FLOOR:
                   elevator = self.elevators[event.data["elevator"]]
                   floor = self.floors[event.data["floor"]]
                   self.on_elevator_stopped(elevator, floor)

               elif event.type == EventType.IDLE:
                   elevator = self.elevators[event.data["elevator"]]
                   self.on_elevator_idle(elevator)

               elif event.type == EventType.ELEVATOR_MOVE:
                   elevator = self.elevators[event.data["elevator"]]
                   from_position = event.data["from_position"]
                   to_position = event.data["to_position"]
                   direction = event.data["direction"]
                   status = event.data["status"]
                   self.on_elevator_move(elevator, from_position, to_position, direction, status)

               # ... other event types ...

Control Flow: Bus Example
--------------------------

The ``bus_example.py`` demonstrates a simple "bus route" algorithm:

.. code-block:: python

   class ElevatorBusExampleController(ElevatorController):
       def __init__(self):
           super().__init__("http://127.0.0.1:8000", True)
           self.all_passengers = []
           self.max_floor = 0

       def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
           """Initialize elevators to starting positions"""
           self.max_floor = floors[-1].floor
           self.floors = floors

           for i, elevator in enumerate(elevators):
               # Distribute elevators evenly across floors
               target_floor = (i * (len(floors) - 1)) // len(elevators)
               elevator.go_to_floor(target_floor, immediate=True)

       def on_event_execute_start(self, tick: int, events: List[SimulationEvent],
                                   elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
           """Print state before processing events"""
           print(f"Tick {tick}: Processing {len(events)} events {[e.type.value for e in events]}")
           for elevator in elevators:
               print(
                   f"\t{elevator.id}[{elevator.target_floor_direction.value},"
                   f"{elevator.current_floor_float}/{elevator.target_floor}]"
                   + "👦" * len(elevator.passengers),
                   end=""
               )
           print()

       def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
           """Implement bus route logic"""
           print(f"🛑 Elevator E{elevator.id} stopped at F{floor.floor}")

           # Bus algorithm: go up to top, then down to bottom, repeat
           if elevator.last_tick_direction == Direction.UP and elevator.current_floor == self.max_floor:
               # At top, start going down
               elevator.go_to_floor(elevator.current_floor - 1)
           elif elevator.last_tick_direction == Direction.DOWN and elevator.current_floor == 0:
               # At bottom, start going up
               elevator.go_to_floor(elevator.current_floor + 1)
           elif elevator.last_tick_direction == Direction.UP:
               # Continue upward
               elevator.go_to_floor(elevator.current_floor + 1)
           elif elevator.last_tick_direction == Direction.DOWN:
               # Continue downward
               elevator.go_to_floor(elevator.current_floor - 1)

       def on_elevator_idle(self, elevator: ProxyElevator) -> None:
           """Send idle elevator to floor 1"""
           elevator.go_to_floor(1)

Execution Sequence
~~~~~~~~~~~~~~~~~~

Here's what happens in a typical tick:

.. code-block:: text

   Server: Tick 42
     Phase 1: Update status
       - Elevator 0: STOPPED → START_UP (has target)
     Phase 2: Process arrivals
       - Passenger 101 arrives at floor 0, going to floor 5
       - Event: UP_BUTTON_PRESSED
     Phase 3: Move elevators
       - Elevator 0: floor 2.0 → 2.1 (accelerating)
     Phase 4: Process stops
       - (no stops this tick)

     Events: [UP_BUTTON_PRESSED, PASSING_FLOOR]

   Client: Receive events
     on_event_execute_start(tick=42, events=[...])
       - Print "Tick 42: Processing 2 events"

     _execute_events():
       - UP_BUTTON_PRESSED → on_passenger_call()
         → Controller decides which elevator to send
       - PASSING_FLOOR → on_elevator_passing_floor()

     on_event_execute_end(tick=42, events=[...])

   Client: Send commands
     - elevator.go_to_floor(0)  → POST /api/elevators/0/go_to_floor

   Client: Step simulation
     - POST /api/step → Server processes tick 43

Key Timing Concepts
-------------------

Immediate vs. Queued
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Queued (default): Wait until current target reached
   elevator.go_to_floor(5, immediate=False)
   # ← Sets elevator.next_target_floor = 5
   # ← Processed when current_floor == target_floor

   # Immediate: Change target right away
   elevator.go_to_floor(5, immediate=True)
   # ← Sets elevator.position.target_floor = 5 immediately
   # ← May interrupt current journey

Use ``immediate=True`` for emergency redirects, ``immediate=False`` (default) for normal operation.

Performance Metrics
-------------------

Metrics are calculated from passenger data:

.. code-block:: python

   def _calculate_metrics(self) -> PerformanceMetrics:
       """Calculate performance metrics"""
       completed = [p for p in self.state.passengers.values()
                    if p.status == PassengerStatus.COMPLETED]

       floor_wait_times = [float(p.floor_wait_time) for p in completed]
       arrival_wait_times = [float(p.arrival_wait_time) for p in completed]

       def average_excluding_top_percent(data: List[float], exclude_percent: int) -> float:
           """计算排除掉最长的指定百分比后的平均值"""
           if not data:
               return 0.0
           sorted_data = sorted(data)
           keep_count = int(len(sorted_data) * (100 - exclude_percent) / 100)
           if keep_count == 0:
               return 0.0
           kept_data = sorted_data[:keep_count]
           return sum(kept_data) / len(kept_data)

       return PerformanceMetrics(
           completed_passengers=len(completed),
           total_passengers=len(self.state.passengers),
           average_floor_wait_time=sum(floor_wait_times) / len(floor_wait_times) if floor_wait_times else 0,
           p95_floor_wait_time=average_excluding_top_percent(floor_wait_times, 5),
           average_arrival_wait_time=sum(arrival_wait_times) / len(arrival_wait_times) if arrival_wait_times else 0,
           p95_arrival_wait_time=average_excluding_top_percent(arrival_wait_times, 5),
       )

Key metrics:

- **Floor wait time**: ``pickup_tick - arrive_tick`` (在楼层等待的时间，从到达到上电梯)
- **Arrival wait time**: ``dropoff_tick - arrive_tick`` (总等待时间，从到达到下电梯)
- **P95 metrics**: 排除掉最长的5%时间后，计算剩余95%的平均值

Summary
-------

The event-driven, tick-based architecture provides:

- **Deterministic**: Same inputs always produce same results
- **Testable**: Easy to create test scenarios with traffic files
- **Debuggable**: Clear event trail shows what happened when
- **Flexible**: Easy to implement different dispatch algorithms
- **Scalable**: Can simulate large buildings and many passengers

Next Steps
----------

- Study ``bus_example.py`` for a complete working example
- Implement your own controller by extending ``ElevatorController``
- Experiment with different dispatch algorithms
- Analyze performance metrics to optimize your approach
