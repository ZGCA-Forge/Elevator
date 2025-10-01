"""
Test module imports to ensure all modules can be imported successfully
"""

import pytest


def test_import_core_models():
    """Test importing core data models"""
    from elevator_saga.core.models import (
        Direction,
        ElevatorState,
        ElevatorStatus,
        EventType,
        FloorState,
        PassengerInfo,
        PassengerStatus,
        SimulationState,
        TrafficEntry,
        TrafficPattern,
    )

    assert Direction is not None
    assert ElevatorState is not None
    assert ElevatorStatus is not None
    assert EventType is not None
    assert FloorState is not None
    assert PassengerInfo is not None
    assert PassengerStatus is not None
    assert SimulationState is not None
    assert TrafficEntry is not None
    assert TrafficPattern is not None


def test_import_client_api():
    """Test importing client API"""
    from elevator_saga.client.api_client import ElevatorAPIClient

    assert ElevatorAPIClient is not None


def test_import_proxy_models():
    """Test importing proxy models"""
    from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger

    assert ProxyElevator is not None
    assert ProxyFloor is not None
    assert ProxyPassenger is not None


def test_import_base_controller():
    """Test importing base controller"""
    from elevator_saga.client.base_controller import ElevatorController

    assert ElevatorController is not None


def test_import_simulator():
    """Test importing simulator"""
    from elevator_saga.server.simulator import ElevatorSimulation

    assert ElevatorSimulation is not None


def test_import_client_example():
    """Test importing client example"""
    from elevator_saga.client_examples.bus_example import ElevatorBusExampleController

    assert ElevatorBusExampleController is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
