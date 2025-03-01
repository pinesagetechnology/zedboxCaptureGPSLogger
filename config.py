#!/usr/bin/env python3
"""
Config module for ZED Camera Capture Tool.
"""

import os
import json
import logging
from pathlib import Path

# Default application settings
DEFAULT_SETTINGS = {
    "output_directory": str(Path.home() / "zed_captures"),
    "time_interval": 10,  # seconds
    "gps_interval": 5,    # meters
    "capture_mode": "time",  # "time" or "gps"
    "metadata_format": "json",
    "camera": {
        "mode": "auto",  # "auto" or "manual"
        "resolution": "HD1080",  # HD720, HD1080, HD2K, VGA
        "fps": 30,
        "brightness": 4,
        "contrast": 4,
        "hue": 0,
        "saturation": 4,
        "exposure": -1,  # -1 for auto
        "gain": -1,      # -1 for auto
        "whitebalance": -1,  # -1 for auto
    },
    "gps": {
        "port": "/dev/ttyACM0",
        "baud_rate": 9600,
        "timeout": 1.0
    }
}

CONFIG_PATH = Path.home() / ".config" / "zed_capture_tool"
SETTINGS_FILE = CONFIG_PATH / "settings.json"

def setup_logging():
    """Configure logging for the application"""
    log_path = CONFIG_PATH / "logs"
    log_path.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path / "app.log"),
            logging.StreamHandler()
        ]
    )

def load_settings():
    """Load settings from file or create default if doesn't exist"""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                # Merge with defaults to ensure all keys exist
                return {**DEFAULT_SETTINGS, **settings}
        else:
            save_settings(DEFAULT_SETTINGS)
            return DEFAULT_SETTINGS
    except Exception as e:
        logging.error(f"Error loading settings: {e}")
        return DEFAULT_SETTINGS

def save_settings(settings):
    """Save settings to file"""
    try:
        CONFIG_PATH.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        logging.error(f"Error saving settings: {e}")
        return False