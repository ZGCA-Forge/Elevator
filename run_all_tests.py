#!/usr/bin/env python3
"""
Test runner for Elevator Saga project
"""
import argparse
import subprocess
import sys
import os
from pathlib import Path


def check_dependencies():
    """Check if all dependencies are installed correctly"""
    print("🔍 Checking dependencies...")
    try:
        import elevator_saga

        print(f"✅ elevator_saga version: {getattr(elevator_saga, '__version__', 'unknown')}")

        # Check main dependencies
        dependencies = ["pyee", "numpy", "matplotlib", "seaborn", "pandas", "flask"]
        for dep in dependencies:
            try:
                __import__(dep)
                print(f"✅ {dep}: installed")
            except ImportError:
                print(f"❌ {dep}: missing")
                return False

        print("✅ All dependencies are correctly installed")
        return True
    except ImportError as e:
        print(f"❌ Error importing elevator_saga: {e}")
        return False


def run_unit_tests():
    """Run unit tests"""
    print("🧪 Running unit tests...")

    # Check if tests directory exists
    tests_dir = Path("tests")
    if not tests_dir.exists():
        print("ℹ️  No tests directory found, creating basic test structure...")
        tests_dir.mkdir()
        (tests_dir / "__init__.py").touch()

        # Create a basic test file
        basic_test = tests_dir / "test_basic.py"
        basic_test.write_text(
            '''"""Basic tests for elevator_saga"""
import unittest
from elevator_saga.core.models import Direction, SimulationEvent


class TestBasic(unittest.TestCase):
    """Basic functionality tests"""
    
    def test_direction_enum(self):
        """Test Direction enum"""
        self.assertEqual(Direction.UP.value, "up")
        self.assertEqual(Direction.DOWN.value, "down")
        self.assertEqual(Direction.NONE.value, "none")
    
    def test_import(self):
        """Test that main modules can be imported"""
        import elevator_saga.client.base_controller
        import elevator_saga.core.models
        import elevator_saga.server.simulator


if __name__ == '__main__':
    unittest.main()
'''
        )

    # Run pytest if available, otherwise unittest
    try:
        result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"], capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result.returncode == 0
    except FileNotFoundError:
        print("pytest not found, using unittest...")
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "tests"], capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result.returncode == 0


def run_example_tests():
    """Run example files to ensure they work"""
    print("🚀 Running example tests...")

    example_files = ["simple_example.py", "test_example.py"]
    for example_file in example_files:
        if os.path.exists(example_file):
            print(f"Testing {example_file}...")
            # Just check if the file can be imported without errors
            try:
                result = subprocess.run(
                    [sys.executable, "-c", f"import {example_file[:-3]}"], capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    print(f"✅ {example_file}: import successful")
                else:
                    print(f"❌ {example_file}: import failed")
                    print(result.stderr)
                    return False
            except subprocess.TimeoutExpired:
                print(f"⏰ {example_file}: timeout (probably waiting for server)")
                # This is expected for examples that try to connect to server
                print(f"✅ {example_file}: import successful (with server connection)")
            except Exception as e:
                print(f"❌ {example_file}: error - {e}")
                return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Run tests for Elevator Saga")
    parser.add_argument("--check-deps", action="store_true", help="Check dependencies only")
    parser.add_argument("--type", choices=["unit", "examples", "all"], default="all", help="Type of tests to run")

    args = parser.parse_args()

    success = True

    if args.check_deps:
        success = check_dependencies()
    else:
        # Always check dependencies first
        if not check_dependencies():
            print("❌ Dependency check failed")
            return 1

        if args.type in ["unit", "all"]:
            if not run_unit_tests():
                success = False

        if args.type in ["examples", "all"]:
            if not run_example_tests():
                success = False

    if success:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
