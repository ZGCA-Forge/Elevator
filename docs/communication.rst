HTTP Communication Architecture
================================

Elevator Saga uses a **client-server architecture** with HTTP-based communication. The server manages the simulation state and physics, while clients send commands and query state over HTTP.

Architecture Overview
---------------------

.. code-block:: text

   ┌─────────────────┐                    ┌─────────────────┐
   │  Client         │                    │  Server         │
   │  (Controller)   │                    │  (Simulator)    │
   ├─────────────────┤                    ├─────────────────┤
   │ base_controller │◄──── HTTP ────────►│ simulator.py    │
   │ proxy_models    │                    │ Flask Routes    │
   │ api_client      │                    │                 │
   └─────────────────┘                    └─────────────────┘
           │                                       │
           │  GET /api/state                       │
           │  POST /api/step                       │
           │  POST /api/elevators/:id/go_to_floor  │
           │                                       │
           └───────────────────────────────────────┘

The separation provides:

- **Modularity**: Server and client can be developed independently
- **Multiple Clients**: Multiple controllers can compete/cooperate
- **Language Flexibility**: Clients can be written in any language
- **Network Deployment**: Server and client can run on different machines

Server Side: Simulator
----------------------

The server is implemented in ``elevator_saga/server/simulator.py`` using **Flask** as the HTTP framework.

API Endpoints
~~~~~~~~~~~~~

**GET /api/state**

Returns complete simulation state:

.. code-block:: python

   @app.route("/api/state", methods=["GET"])
   def get_state() -> Response:
       try:
           state = simulation.get_state()
           return json_response(state)
       except Exception as e:
           return json_response({"error": str(e)}, 500)

Response format:

.. code-block:: json

   {
     "tick": 42,
     "elevators": [
       {
         "id": 0,
         "position": {"current_floor": 2, "target_floor": 5, "floor_up_position": 3},
         "passengers": [101, 102],
         "max_capacity": 10,
         "run_status": "constant_speed",
         "energy_consumed": 38.5,
         "energy_rate": 1.0,
         "..."
       }
     ],
     "floors": [
       {"floor": 0, "up_queue": [103], "down_queue": []},
       "..."
     ],
     "passengers": {
       "101": {"id": 101, "origin": 0, "destination": 5, "..."}
     },
     "metrics": {
       "done": 50,
       "total": 100,
       "avg_wait": 15.2,
       "p95_wait": 30.0,
       "avg_system": 25.5,
       "p95_system": 45.0,
       "total_energy_consumption": 156.0
     }
   }

**POST /api/step**

Advances simulation by specified number of ticks:

.. code-block:: python

   @app.route("/api/step", methods=["POST"])
   def step_simulation() -> Response:
       try:
           data = request.get_json() or {}
           ticks = data.get("ticks", 1)
           events = simulation.step(ticks)
           return json_response({
               "tick": simulation.tick,
               "events": events,
           })
       except Exception as e:
           return json_response({"error": str(e)}, 500)

Request body:

.. code-block:: json

   {"ticks": 1}

Response:

.. code-block:: json

   {
     "tick": 43,
     "events": [
       {
         "tick": 43,
         "type": "stopped_at_floor",
         "data": {"elevator": 0, "floor": 5, "reason": "move_reached"}
       }
     ]
   }

**POST /api/elevators/:id/go_to_floor**

Commands an elevator to go to a floor:

.. code-block:: python

   @app.route("/api/elevators/<int:elevator_id>/go_to_floor", methods=["POST"])
   def elevator_go_to_floor(elevator_id: int) -> Response:
       try:
           data = request.get_json() or {}
           floor = data["floor"]
           immediate = data.get("immediate", False)
           simulation.elevator_go_to_floor(elevator_id, floor, immediate)
           return json_response({"success": True})
       except Exception as e:
           return json_response({"error": str(e)}, 500)

Request body:

.. code-block:: json

   {"floor": 5, "immediate": false}

- ``immediate=false``: Set as next target after current destination
- ``immediate=true``: Change target immediately (cancels current target)

**POST /api/reset**

Resets simulation to initial state:

.. code-block:: python

   @app.route("/api/reset", methods=["POST"])
   def reset_simulation() -> Response:
       try:
           simulation.reset()
           return json_response({"success": True})
       except Exception as e:
           return json_response({"error": str(e)}, 500)

**POST /api/traffic/next**

Loads next traffic scenario:

.. code-block:: python

   @app.route("/api/traffic/next", methods=["POST"])
   def next_traffic_round() -> Response:
       try:
           full_reset = request.get_json().get("full_reset", False)
           success = simulation.next_traffic_round(full_reset)
           if success:
               return json_response({"success": True})
           else:
               return json_response({"success": False, "error": "No more scenarios"}, 400)
       except Exception as e:
           return json_response({"error": str(e)}, 500)

**GET /api/traffic/info**

Gets current traffic scenario information:

.. code-block:: python

   @app.route("/api/traffic/info", methods=["GET"])
   def get_traffic_info() -> Response:
       try:
           info = simulation.get_traffic_info()
           return json_response(info)
       except Exception as e:
           return json_response({"error": str(e)}, 500)

Response:

.. code-block:: json

   {
     "current_index": 0,
     "total_files": 5,
     "max_tick": 1000
   }

Client Side: API Client
-----------------------

The client is implemented in ``elevator_saga/client/api_client.py`` using Python's built-in ``urllib`` library.

ElevatorAPIClient Class
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class ElevatorAPIClient:
       """Unified elevator API client"""

       def __init__(self, base_url: str):
           self.base_url = base_url.rstrip("/")
           # Caching fields
           self._cached_state: Optional[SimulationState] = None
           self._cached_tick: int = -1
           self._tick_processed: bool = False

State Caching Strategy
~~~~~~~~~~~~~~~~~~~~~~~

The API client implements **smart caching** to reduce HTTP requests:

.. code-block:: python

   def get_state(self, force_reload: bool = False) -> SimulationState:
       """Get simulation state with caching"""
       # Return cached state if valid
       if not force_reload and self._cached_state is not None and not self._tick_processed:
           return self._cached_state

       # Fetch fresh state
       response_data = self._send_get_request("/api/state")
       # ... parse and create SimulationState ...

       # Update cache
       self._cached_state = simulation_state
       self._cached_tick = simulation_state.tick
       self._tick_processed = False  # Mark as fresh

       return simulation_state

   def mark_tick_processed(self) -> None:
       """Mark current tick as processed, invalidating cache"""
       self._tick_processed = True

**Cache Behavior**:

1. First ``get_state()`` call in a tick fetches from server
2. Subsequent calls within same tick return cached data
3. After ``step()`` is called, cache is invalidated
4. Next ``get_state()`` fetches fresh data

This provides:

- **Performance**: Minimize HTTP requests
- **Consistency**: All operations in a tick see same state
- **Freshness**: New tick always gets new state

Core API Methods
~~~~~~~~~~~~~~~~

**get_state(force_reload=False)**

Fetches current simulation state:

.. code-block:: python

   def get_state(self, force_reload: bool = False) -> SimulationState:
       if not force_reload and self._cached_state is not None and not self._tick_processed:
           return self._cached_state

       response_data = self._send_get_request("/api/state")

       # Parse response into data models
       elevators = [ElevatorState.from_dict(e) for e in response_data["elevators"]]
       floors = [FloorState.from_dict(f) for f in response_data["floors"]]
       # ... handle passengers and metrics ...

       simulation_state = SimulationState(
           tick=response_data["tick"],
           elevators=elevators,
           floors=floors,
           passengers=passengers,
           metrics=metrics,
           events=[]
       )

       # Update cache
       self._cached_state = simulation_state
       self._cached_tick = simulation_state.tick
       self._tick_processed = False

       return simulation_state

**step(ticks=1)**

Advances simulation:

.. code-block:: python

   def step(self, ticks: int = 1) -> StepResponse:
       response_data = self._send_post_request("/api/step", {"ticks": ticks})

       # Parse events
       events = []
       for event_data in response_data["events"]:
           event_dict = event_data.copy()
           if "type" in event_dict:
               event_dict["type"] = EventType(event_dict["type"])
           events.append(SimulationEvent.from_dict(event_dict))

       return StepResponse(
           success=True,
           tick=response_data["tick"],
           events=events
       )

**go_to_floor(elevator_id, floor, immediate=False)**

Sends elevator to floor:

.. code-block:: python

   def go_to_floor(self, elevator_id: int, floor: int, immediate: bool = False) -> bool:
       command = GoToFloorCommand(
           elevator_id=elevator_id,
           floor=floor,
           immediate=immediate
       )

       try:
           response = self.send_elevator_command(command)
           return response
       except Exception as e:
           debug_log(f"Go to floor failed: {e}")
           return False

HTTP Request Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The client uses ``urllib.request`` for HTTP communication:

**GET Request**:

.. code-block:: python

   def _send_get_request(self, endpoint: str) -> Dict[str, Any]:
       url = f"{self.base_url}{endpoint}"

       try:
           with urllib.request.urlopen(url, timeout=60) as response:
               data = json.loads(response.read().decode("utf-8"))
               return data
       except urllib.error.URLError as e:
           raise RuntimeError(f"GET {url} failed: {e}")

**POST Request**:

.. code-block:: python

   def _send_post_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
       url = f"{self.base_url}{endpoint}"
       request_body = json.dumps(data).encode("utf-8")

       req = urllib.request.Request(
           url,
           data=request_body,
           headers={"Content-Type": "application/json"}
       )

       try:
           with urllib.request.urlopen(req, timeout=600) as response:
               response_data = json.loads(response.read().decode("utf-8"))
               return response_data
       except urllib.error.URLError as e:
           raise RuntimeError(f"POST {url} failed: {e}")

Communication Flow
------------------

Typical communication sequence during one tick:

.. code-block:: text

   Client                                 Server
     │                                      │
     │  1. GET /api/state                   │
     ├─────────────────────────────────────►│
     │  ◄── SimulationState (cached)        │
     │                                      │
     │  2. Analyze state, make decisions    │
     │                                      │
     │  3. POST /api/elevators/0/go_to_floor│
     ├─────────────────────────────────────►│
     │  ◄── {"success": true}               │
     │                                      │
     │  4. GET /api/state (from cache)      │
     │     No HTTP request!                 │
     │                                      │
     │  5. POST /api/step                   │
     ├─────────────────────────────────────►│
     │         Server processes tick        │
     │         - Moves elevators            │
     │         - Boards/alights passengers  │
     │         - Generates events           │
     │  ◄── {tick: 43, events: [...]}       │
     │                                      │
     │  6. Process events                   │
     │     Cache invalidated                │
     │                                      │
     │  7. GET /api/state (fetches fresh)   │
     ├─────────────────────────────────────►│
     │  ◄── SimulationState                 │
     │                                      │
     └──────────────────────────────────────┘

Error Handling
--------------

Both client and server implement robust error handling:

**Server Side**:

.. code-block:: python

   @app.route("/api/step", methods=["POST"])
   def step_simulation() -> Response:
       try:
           # ... process request ...
           return json_response(result)
       except Exception as e:
           return json_response({"error": str(e)}, 500)

**Client Side**:

.. code-block:: python

   def go_to_floor(self, elevator_id: int, floor: int, immediate: bool = False) -> bool:
       try:
           response = self.send_elevator_command(command)
           return response
       except Exception as e:
           debug_log(f"Go to floor failed: {e}")
           return False

Thread Safety
-------------

The simulator uses a lock to ensure thread-safe access:

.. code-block:: python

   class ElevatorSimulation:
       def __init__(self, ...):
           self.lock = threading.Lock()

       def step(self, num_ticks: int = 1) -> List[SimulationEvent]:
           with self.lock:
               # ... process ticks ...

       def get_state(self) -> SimulationStateResponse:
           with self.lock:
               # ... return state ...

This allows Flask to handle concurrent requests safely.

**Batch Commands**:

.. code-block:: python

   # ❌ Bad - sequential commands
   elevator1.go_to_floor(5)
   time.sleep(0.1)  # Wait for response
   elevator2.go_to_floor(3)

   # ✅ Good - issue commands quickly
   elevator1.go_to_floor(5)
   elevator2.go_to_floor(3)
   # All commands received before next tick

**Cache Awareness**:

Use ``mark_tick_processed()`` to explicitly invalidate cache if needed, but normally the framework handles this automatically.

Testing the API
---------------

You can test the API directly using curl:

.. code-block:: bash

   # Get state
   curl http://127.0.0.1:8000/api/state

   # Step simulation
   curl -X POST http://127.0.0.1:8000/api/step \
     -H "Content-Type: application/json" \
     -d '{"ticks": 1}'

   # Send elevator to floor
   curl -X POST http://127.0.0.1:8000/api/elevators/0/go_to_floor \
     -H "Content-Type: application/json" \
     -d '{"floor": 5, "immediate": false}'

   # Reset simulation
   curl -X POST http://127.0.0.1:8000/api/reset \
     -H "Content-Type: application/json" \
     -d '{}'

Next Steps
----------

- See :doc:`events` for understanding how events drive the simulation
- See :doc:`client` for using the API through proxy models
- Check the source code for complete implementation details
