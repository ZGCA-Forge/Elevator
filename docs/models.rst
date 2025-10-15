Data Models
===========

The Elevator Saga system uses a unified data model architecture defined in ``elevator_saga/core/models.py``. These models ensure type consistency and serialization between the client and server components.

Overview
--------

All data models inherit from ``SerializableModel``, which provides:

- **to_dict()**: Convert model to dictionary
- **to_json()**: Convert model to JSON string
- **from_dict()**: Create model instance from dictionary
- **from_json()**: Create model instance from JSON string

This unified serialization approach ensures seamless data exchange over HTTP between client and server.

Core Enumerations
-----------------

Direction
~~~~~~~~~

Represents the direction of elevator movement or passenger travel:

.. code-block:: python

   class Direction(Enum):
       UP = "up"           # Moving upward
       DOWN = "down"       # Moving downward
       STOPPED = "stopped" # Not moving

ElevatorStatus
~~~~~~~~~~~~~~

Represents the elevator's operational state in the state machine:

.. code-block:: python

   class ElevatorStatus(Enum):
       START_UP = "start_up"           # Acceleration phase
       START_DOWN = "start_down"       # Deceleration phase
       CONSTANT_SPEED = "constant_speed" # Constant speed phase
       STOPPED = "stopped"             # Stopped at floor

**Important**: ``START_UP`` and ``START_DOWN`` refer to **acceleration/deceleration states**, not movement direction. The actual movement direction is determined by the ``target_floor_direction`` property.

State Machine Transition:

.. code-block:: text

   STOPPED → START_UP → CONSTANT_SPEED → START_DOWN → STOPPED
      1 tick    1 tick      N ticks         1 tick

PassengerStatus
~~~~~~~~~~~~~~~

Represents the passenger's current state:

.. code-block:: python

   class PassengerStatus(Enum):
       WAITING = "waiting"         # Waiting at origin floor
       IN_ELEVATOR = "in_elevator" # Inside an elevator
       COMPLETED = "completed"     # Reached destination
       CANCELLED = "cancelled"     # Cancelled (unused)

EventType
~~~~~~~~~

Defines all possible simulation events:

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

Core Data Models
----------------

Position
~~~~~~~~

Represents elevator position with sub-floor granularity:

.. code-block:: python

   @dataclass
   class Position(SerializableModel):
       current_floor: int = 0        # Current floor number
       target_floor: int = 0         # Target floor number
       floor_up_position: int = 0    # Position within floor (0-9)

- **floor_up_position**: Represents position between floors with 10 units per floor
- **current_floor_float**: Returns floating-point floor position (e.g., 2.5 = halfway between floors 2 and 3)

Example:

.. code-block:: python

   position = Position(current_floor=2, floor_up_position=5)
   print(position.current_floor_float)  # 2.5

ElevatorState
~~~~~~~~~~~~~

Complete state information for an elevator:

.. code-block:: python

   @dataclass
   class ElevatorState(SerializableModel):
       id: int
       position: Position
       next_target_floor: Optional[int] = None
       passengers: List[int] = []  # Passenger IDs
       max_capacity: int = 10
       speed_pre_tick: float = 0.5
       run_status: ElevatorStatus = ElevatorStatus.STOPPED
       last_tick_direction: Direction = Direction.STOPPED
       indicators: ElevatorIndicators = field(default_factory=ElevatorIndicators)
       passenger_destinations: Dict[int, int] = {}  # passenger_id -> floor
       energy_consumed: float = 0.0
       energy_rate: float = 1.0  # Energy consumption rate per tick
       last_update_tick: int = 0

Key Properties:

- ``current_floor``: Integer floor number
- ``current_floor_float``: Precise position including sub-floor
- ``target_floor``: Destination floor
- ``target_floor_direction``: Direction to target (UP/DOWN/STOPPED)
- ``is_idle``: Whether elevator is stopped
- ``is_full``: Whether elevator is at capacity
- ``is_running``: Whether elevator is in motion
- ``pressed_floors``: List of destination floors for current passengers
- ``load_factor``: Current load as fraction of capacity (0.0 to 1.0)

Energy Tracking:

- ``energy_consumed``: Total energy consumed by this elevator during the simulation
- ``energy_rate``: Energy consumption rate per tick when moving (default: 1.0). Can be customized in traffic configuration files to simulate different elevator types (e.g., older elevators with higher rates, newer energy-efficient elevators with lower rates)

FloorState
~~~~~~~~~~

State information for a building floor:

.. code-block:: python

   @dataclass
   class FloorState(SerializableModel):
       floor: int
       up_queue: List[int] = []    # Passenger IDs waiting to go up
       down_queue: List[int] = []  # Passenger IDs waiting to go down

Properties:

- ``has_waiting_passengers``: Whether any passengers are waiting
- ``total_waiting``: Total number of waiting passengers

PassengerInfo
~~~~~~~~~~~~~

Complete information about a passenger:

.. code-block:: python

   @dataclass
   class PassengerInfo(SerializableModel):
       id: int
       origin: int              # Starting floor
       destination: int         # Target floor
       arrive_tick: int         # When passenger appeared
       pickup_tick: int = 0     # When passenger boarded elevator
       dropoff_tick: int = 0    # When passenger reached destination
       elevator_id: Optional[int] = None

Properties:

- ``status``: Current PassengerStatus
- ``wait_time``: Ticks waited before boarding
- ``system_time``: Total ticks in system (arrive to dropoff)
- ``travel_direction``: UP/DOWN based on origin and destination

SimulationState
~~~~~~~~~~~~~~~

Complete state of the simulation:

.. code-block:: python

   @dataclass
   class SimulationState(SerializableModel):
       tick: int
       elevators: List[ElevatorState]
       floors: List[FloorState]
       passengers: Dict[int, PassengerInfo]
       metrics: PerformanceMetrics
       events: List[SimulationEvent]

Helper Methods:

- ``get_elevator_by_id(id)``: Find elevator by ID
- ``get_floor_by_number(number)``: Find floor by number
- ``get_passengers_by_status(status)``: Filter passengers by status
- ``add_event(type, data)``: Add new event to queue

Traffic and Configuration
-------------------------

TrafficEntry
~~~~~~~~~~~~

Defines a single passenger arrival:

.. code-block:: python

   @dataclass
   class TrafficEntry(SerializableModel):
       id: int
       origin: int
       destination: int
       tick: int  # When passenger arrives

TrafficPattern
~~~~~~~~~~~~~~

Collection of traffic entries defining a test scenario:

.. code-block:: python

   @dataclass
   class TrafficPattern(SerializableModel):
       name: str
       description: str
       entries: List[TrafficEntry]
       metadata: Dict[str, Any]

Properties:

- ``total_passengers``: Number of passengers in pattern
- ``duration``: Tick when last passenger arrives

Performance Metrics
-------------------

PerformanceMetrics
~~~~~~~~~~~~~~~~~~

Tracks simulation performance:

.. code-block:: python

   @dataclass
   class PerformanceMetrics(SerializableModel):
       completed_passengers: int = 0
       total_passengers: int = 0
       average_floor_wait_time: float = 0.0
       p95_floor_wait_time: float = 0.0        # 95th percentile
       average_arrival_wait_time: float = 0.0
       p95_arrival_wait_time: float = 0.0      # 95th percentile
       total_energy_consumption: float = 0.0   # Total energy consumed by all elevators

Properties:

- ``completion_rate``: Fraction of passengers completed (0.0 to 1.0)

Energy Metrics:

- ``total_energy_consumption``: Sum of energy consumed by all elevators in the system. Each elevator consumes ``energy_rate`` units of energy per tick when moving.

API Models
----------

The models also include HTTP API request/response structures:

- ``APIRequest``: Base request with ID and timestamp
- ``APIResponse``: Base response with success flag
- ``StepRequest/StepResponse``: Advance simulation time
- ``StateRequest``: Query simulation state
- ``ElevatorCommand``: Send command to elevator
- ``GoToFloorCommand``: Specific command to move elevator

Example Usage
-------------

Creating a Simulation State
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from elevator_saga.core.models import (
       create_empty_simulation_state,
       ElevatorState,
       Position,
   )

   # Create a building with 3 elevators, 10 floors, capacity 8
   state = create_empty_simulation_state(
       elevators=3,
       floors=10,
       max_capacity=8
   )

   # Access elevator state
   elevator = state.elevators[0]
   print(f"Elevator {elevator.id} at floor {elevator.current_floor}")

Working with Traffic Patterns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from elevator_saga.core.models import (
       create_simple_traffic_pattern,
       TrafficPattern,
   )

   # Create traffic pattern: (origin, destination, tick)
   pattern = create_simple_traffic_pattern(
       name="morning_rush",
       passengers=[
           (0, 5, 10),   # Floor 0→5 at tick 10
           (0, 8, 15),   # Floor 0→8 at tick 15
           (2, 0, 20),   # Floor 2→0 at tick 20
       ]
   )

   print(f"Pattern has {pattern.total_passengers} passengers")
   print(f"Duration: {pattern.duration} ticks")

Serialization
~~~~~~~~~~~~~

All models support JSON serialization:

.. code-block:: python

   # Serialize to JSON
   elevator = state.elevators[0]
   json_str = elevator.to_json()

   # Deserialize from JSON
   restored = ElevatorState.from_json(json_str)

   # Or use dictionaries
   data = elevator.to_dict()
   restored = ElevatorState.from_dict(data)

This enables seamless transmission over HTTP between client and server.

Energy System
-------------

Overview
~~~~~~~~

The energy system tracks energy consumption of elevators to help optimize control algorithms for both passenger service and energy efficiency.

How Energy Works
~~~~~~~~~~~~~~~~

**Energy Consumption:**

- Each elevator has an ``energy_rate`` attribute (default: 1.0)
- When an elevator moves (any tick where it's not stopped), it consumes energy equal to its ``energy_rate``
- Energy consumption is independent of speed, direction, or load
- Total system energy is the sum of all individual elevator energy consumption

**Configuration:**

Energy rates are configured in traffic JSON files via the ``elevator_energy_rates`` field:

.. code-block:: json

   {
     "building": {
       "floors": 10,
       "elevators": 3,
       "elevator_capacity": 10,
       "elevator_energy_rates": [1.0, 1.0, 1.2],
       "scenario": "custom_scenario",
       "duration": 600
     },
     "traffic": []
   }

In this example, elevators 0 and 1 have standard energy rates (1.0), while elevator 2 consumes 20% more energy (1.2), perhaps representing an older or less efficient unit.

**Use Cases:**

1. **Algorithm Optimization**: Balance passenger wait times against energy consumption
2. **Heterogeneous Fleets**: Model buildings with elevators of different ages/efficiencies
3. **Cost Analysis**: Evaluate the energy cost of different control strategies
4. **Green Building Simulation**: Optimize for minimal energy while maintaining service quality

Example Usage
~~~~~~~~~~~~~

.. code-block:: python

   # Get current state
   state = api_client.get_state()

   # Check individual elevator energy
   for elevator in state.elevators:
       print(f"Elevator {elevator.id}: {elevator.energy_consumed} units consumed")
       print(f"  Energy rate: {elevator.energy_rate} units/tick")

   # Check total system energy
   metrics = state.metrics
   print(f"Total system energy: {metrics.total_energy_consumption} units")
   print(f"Completed passengers: {metrics.completed_passengers}")

   # Calculate energy per passenger
   if metrics.completed_passengers > 0:
       energy_per_passenger = metrics.total_energy_consumption / metrics.completed_passengers
       print(f"Energy per passenger: {energy_per_passenger:.2f} units")

**Default Behavior:**

If ``elevator_energy_rates`` is not specified in the traffic file, all elevators default to an energy rate of 1.0, ensuring backward compatibility with existing traffic files.
