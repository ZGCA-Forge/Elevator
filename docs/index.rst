Welcome to Elevator Saga's Documentation!
==========================================

.. image:: https://badge.fury.io/py/elevator-py.svg
   :target: https://badge.fury.io/py/elevator-py
   :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/elevator-py.svg
   :target: https://pypi.org/project/elevator-py/
   :alt: Python versions

.. image:: https://github.com/ZGCA-Forge/Elevator/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/ZGCA-Forge/Elevator/actions
   :alt: Build Status

.. image:: https://img.shields.io/github/stars/ZGCA-Forge/Elevator.svg?style=social&label=Star
   :target: https://github.com/ZGCA-Forge/Elevator
   :alt: GitHub stars

Elevator Saga is a Python implementation of an elevator `simulation game <https://play.elevatorsaga.com/>`_ with an event-driven architecture. Design and optimize elevator control algorithms to efficiently transport passengers in buildings.

Features
--------

🏢 **Realistic Simulation**: Physics-based elevator movement with acceleration, deceleration, and realistic timing

🎮 **Event-Driven Architecture**: React to various events such as button presses, elevator arrivals, and passenger boarding

🔌 **Client-Server Model**: Separate simulation server from control logic for clean architecture

📊 **Performance Metrics**: Track wait times, system times, completion rates, and energy consumption

⚡ **Energy Tracking**: Monitor and optimize energy consumption with configurable per-elevator energy rates

🎯 **Flexible Control**: Implement your own algorithms using a simple controller interface

Installation
------------

Basic Installation
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   pip install elevator-py

Quick Start
-----------

Running the Simulation
~~~~~~~~~~~~~~~~~~~~~~

**Terminal #1: Start the backend simulator**

.. code-block:: bash

   python -m elevator_saga.server.simulator

**Terminal #2: Start your controller**

.. code-block:: bash

   python -m elevator_saga.client_examples.bus_example

Architecture Overview
---------------------

Elevator Saga follows a **client-server architecture**:

- **Server** (`simulator.py`): Manages the simulation state, physics, and event generation
- **Client** (`base_controller.py`): Implements control algorithms and reacts to events
- **Communication** (`api_client.py`): HTTP-based API for state queries and commands
- **Data Models** (`models.py`): Unified data structures shared between client and server

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   models
   client
   communication
   events

.. toctree::
   :maxdepth: 1
   :caption: API Reference

   api/modules

Contributing
------------

Contributions are welcome! Please feel free to submit a Pull Request.

License
-------

This project is licensed under MIT License - see the LICENSE file for details.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
