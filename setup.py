#!/usr/bin/env python3
"""
Setup script for Elevator Saga Python Package
"""
from setuptools import setup, find_packages

with open("README_CN.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="elevator-saga",
    version="1.0.0",
    author="Elevator Saga Team",
    description="Python implementation of Elevator Saga game with PyEE event system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Education", 
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Games/Entertainment :: Simulation",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pyee>=11.0.0",
        "numpy>=1.20.0",
        "matplotlib>=3.5.0",
        "seaborn>=0.11.0",
        "pandas>=1.3.0",,
        "flask
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov",
            "black",
            "flake8",
        ],
    },
    entry_points={
        "console_scripts": [
            "elevator-saga=elevator_saga.cli.main:main",
            "elevator-server=elevator_saga.cli.main:server_main",
            "elevator-client=elevator_saga.cli.main:client_main",
            "elevator-grader=elevator_saga.grader.grader:main",
            "elevator-batch-test=elevator_saga.grader.batch_runner:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
