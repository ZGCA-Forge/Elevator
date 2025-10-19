Logging System
==============

Overview
--------

Elevator Saga uses a unified logging system with colored output and multiple log levels. The logging system provides consistent, filterable output across all components.

Log Levels
----------

The logger supports four log levels with distinct colors:

* **DEBUG** - Gray/Bright Black - Detailed debugging information
* **INFO** - Cyan - General informational messages
* **WARNING** - Yellow - Warning messages
* **ERROR** - Red - Error messages

Configuration
-------------

Environment Variable
~~~~~~~~~~~~~~~~~~~~

The default log level is controlled by the ``ELEVATOR_LOG_LEVEL`` environment variable:

.. code-block:: bash

   # Set log level to DEBUG (default)
   export ELEVATOR_LOG_LEVEL=DEBUG

   # Set log level to INFO (less verbose)
   export ELEVATOR_LOG_LEVEL=INFO

   # Set log level to WARNING (only warnings and errors)
   export ELEVATOR_LOG_LEVEL=WARNING

   # Set log level to ERROR (only errors)
   export ELEVATOR_LOG_LEVEL=ERROR

If not set, the default is **DEBUG** mode.

Programmatic Control
~~~~~~~~~~~~~~~~~~~~

You can also control the log level programmatically:

.. code-block:: python

   from elevator_saga.utils.logger import LogLevel, set_log_level

   # Set to INFO level
   set_log_level(LogLevel.INFO)

   # Set to DEBUG level
   set_log_level(LogLevel.DEBUG)

Basic Usage
-----------

Simple Logging
~~~~~~~~~~~~~~

.. code-block:: python

   from elevator_saga.utils.logger import debug, info, warning, error

   # Simple messages
   info("Server started successfully")
   warning("Connection timeout")
   error("Failed to load configuration")
   debug("Processing tick 42")

With Prefix
~~~~~~~~~~~

Add a prefix to identify the source of the log message:

.. code-block:: python

   # Server logs
   info("Client registered", prefix="SERVER")
   debug("Algorithm client processed tick 42", prefix="SERVER")

   # Client logs
   info("API Client initialized", prefix="CLIENT")
   warning("Command ignored", prefix="CLIENT")

   # Controller logs
   info("启动 MyController 算法", prefix="CONTROLLER")
   error("模拟运行错误", prefix="CONTROLLER")

Advanced Usage
--------------

Custom Logger
~~~~~~~~~~~~~

Create a custom logger instance with specific settings:

.. code-block:: python

   from elevator_saga.utils.logger import get_logger, LogLevel

   # Get a custom logger
   logger = get_logger("MyComponent", min_level=LogLevel.WARNING)
   logger.info("This will not appear (level too low)")
   logger.warning("This will appear")
   logger.error("This will appear")

Color Output
~~~~~~~~~~~~

The logger automatically detects if output is to a TTY (terminal) and enables colors. When redirecting to files or pipes, colors are automatically disabled for clean output.

Log Format
----------

All log messages follow a consistent format::

   LEVEL     [PREFIX] message

Examples:

.. code-block:: text

   DEBUG    [SERVER] Algorithm client registered: abc-123
   INFO     [SERVER] Loading traffic from test_case_01.json
   WARNING  [SERVER] GUI client: timeout waiting for tick 42
   ERROR    [CLIENT] Reset failed: Connection refused
   INFO     [CONTROLLER] 启动 MyController 算法

Component Prefixes
------------------

Standard prefixes used throughout the system:

* **SERVER** - Simulator server logs
* **CLIENT** - API client logs
* **CONTROLLER** - Controller/algorithm logs

You can use any prefix that makes sense for your component.

API Reference
-------------

Functions
~~~~~~~~~

.. py:function:: debug(message: str, prefix: Optional[str] = None) -> None

   Log a DEBUG level message.

   :param message: The message to log
   :param prefix: Optional prefix to identify the source

.. py:function:: info(message: str, prefix: Optional[str] = None) -> None

   Log an INFO level message.

   :param message: The message to log
   :param prefix: Optional prefix to identify the source

.. py:function:: warning(message: str, prefix: Optional[str] = None) -> None

   Log a WARNING level message.

   :param message: The message to log
   :param prefix: Optional prefix to identify the source

.. py:function:: error(message: str, prefix: Optional[str] = None) -> None

   Log an ERROR level message.

   :param message: The message to log
   :param prefix: Optional prefix to identify the source

.. py:function:: set_log_level(level: LogLevel) -> None

   Set the global log level.

   :param level: The minimum log level to display

.. py:function:: get_logger(name: str = "ElevatorSaga", min_level: Optional[LogLevel] = None) -> Logger

   Get or create the global logger instance.

   :param name: Name of the logger
   :param min_level: Minimum log level (defaults to ELEVATOR_LOG_LEVEL or DEBUG)
   :return: Logger instance

Classes
~~~~~~~

.. py:class:: LogLevel

   Enumeration of available log levels.

   .. py:attribute:: DEBUG
      :value: 0

      Debug level - most verbose

   .. py:attribute:: INFO
      :value: 1

      Info level - general information

   .. py:attribute:: WARNING
      :value: 2

      Warning level - warnings only

   .. py:attribute:: ERROR
      :value: 3

      Error level - errors only

   .. py:method:: from_string(level_str: str) -> LogLevel
      :classmethod:

      Convert a string to a LogLevel.

      :param level_str: String representation (case-insensitive)
      :return: Corresponding LogLevel (defaults to DEBUG if invalid)

.. py:class:: Logger

   The main logger class.

   .. py:method:: __init__(name: str = "ElevatorSaga", min_level: LogLevel = LogLevel.INFO, use_color: bool = True)

      Initialize a logger instance.

      :param name: Logger name
      :param min_level: Minimum level to log
      :param use_color: Whether to use colored output

   .. py:method:: debug(message: str, prefix: Optional[str] = None) -> None

      Log a DEBUG message.

   .. py:method:: info(message: str, prefix: Optional[str] = None) -> None

      Log an INFO message.

   .. py:method:: warning(message: str, prefix: Optional[str] = None) -> None

      Log a WARNING message.

   .. py:method:: error(message: str, prefix: Optional[str] = None) -> None

      Log an ERROR message.

   .. py:method:: set_level(level: LogLevel) -> None

      Change the minimum log level.

Best Practices
--------------

1. **Use appropriate levels**:

   * DEBUG for detailed state changes and internal operations
   * INFO for significant events (startup, completion, etc.)
   * WARNING for unexpected but recoverable situations
   * ERROR for failures and exceptions

2. **Use prefixes consistently**:

   * Always use the same prefix for the same component
   * Use uppercase for standard prefixes (SERVER, CLIENT, CONTROLLER)

3. **Keep messages concise**:

   * One log message per event
   * Include relevant context (IDs, values, etc.)
   * Avoid multi-line messages

4. **Set appropriate default level**:

   * Use DEBUG for development
   * Use INFO for production
   * Use WARNING for minimal logging

5. **Avoid logging in tight loops**:

   * Excessive logging can impact performance
   * Consider conditional logging or sampling

Examples
--------

Server Startup
~~~~~~~~~~~~~~

.. code-block:: python

   from elevator_saga.utils.logger import info, debug

   info("Elevator simulation server (Async) running on http://127.0.0.1:8000", prefix="SERVER")
   info("Using Quart (async Flask) for better concurrency", prefix="SERVER")
   debug("Found 5 traffic files: ['test01.json', 'test02.json', ...]", prefix="SERVER")

Client Operations
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from elevator_saga.utils.logger import info, warning, error

   info("Client registered successfully with ID: xyz-789", prefix="CLIENT")
   warning("Client type 'gui' cannot send control commands", prefix="CLIENT")
   error("Reset failed: Connection refused", prefix="CLIENT")

Controller Logic
~~~~~~~~~~~~~~~~

.. code-block:: python

   from elevator_saga.utils.logger import info, debug

   info("启动 MyController 算法", prefix="CONTROLLER")
   debug("Updated traffic info - max_tick: 1000", prefix="CONTROLLER")
   info("停止 MyController 算法", prefix="CONTROLLER")
