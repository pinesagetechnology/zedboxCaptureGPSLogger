#!/usr/bin/env python3
"""
Setup script for ZED Camera Capture Tool.
"""

from setuptools import setup, find_packages

setup(
    name="zed_capture_tool",
    version="0.1.0",
    description="A tool for capturing images from ZED camera with GPS metadata",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "pyqt5>=5.15.0",
        "pyzed",
        "pyserial>=3.5",
        "pynmea2>=1.18.0",
    ],
    entry_points={
        "console_scripts": [
            "zed_capture=zed_capture_tool.main:main",
        ],
    },
    python_requires=">=3.6",
)