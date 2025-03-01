# ZED Camera Capture Tool

A Python application for capturing images from a ZED camera on a ZED-X Box Orin with GPS metadata integration.

## Features

- Image capture in two modes:
  - Time-based interval (e.g., every 10 seconds)
  - GPS location-based (e.g., every 5 meters)
- JSON metadata with each image containing:
  - GPS coordinates
  - Date and time
  - Camera settings
- Camera settings control:
  - Automatic or manual mode
  - Resolution adjustment
  - Brightness, contrast, exposure, etc.
- User-friendly PyQt5 interface
- Integration with uBlox GPS receiver

## Requirements

- ZED-X Box Orin running Linux
- ZED Camera
- uBlox GPS receiver
- Python 3.6 or higher
- Required Python packages (see requirements.txt)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/zed-capture-tool.git
   cd zed-capture-tool
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install the ZED SDK if you haven't already:
   Follow the instructions at https://www.stereolabs.com/docs/installation/

4. Install the application:
   ```
   pip install -e .
   ```

## Usage

1. Run the application:
   ```
   zed_capture
   ```
   or
   ```
   python -m zed_capture_tool.main
   ```

2. Connect to your ZED camera and GPS device using the Settings tab.

3. Configure capture settings:
   - Select capture mode (time or GPS)
   - Set interval (seconds or meters)
   - Choose output directory

4. Start capturing images with the "Start Capture" button, or take individual shots with "Single Capture".

## Technical Details

- Language: Python (as requested since you mentioned the C# UI limitations on Linux)
- UI Framework: PyQt5 (cross-platform UI that works well on Linux)
- Dependencies:

  - pyzed: Official ZED SDK Python bindings
  - pyserial and pynmea2: For GPS communication
  - PyQt5: For the graphical interface

## Directory Structure

```
zed_capture_tool/
├── main.py                    # Main application entry point
├── config.py                  # Configuration module
├── camera/                    # Camera module
│   ├── __init__.py
│   └── zed_camera.py          # ZED camera interface
├── gps/                       # GPS module
│   ├── __init__.py
│   └── gps_receiver.py        # GPS receiver interface
├── capture/                   # Capture module
│   ├── __init__.py
│   └── capture_controller.py  # Capture controller
└── ui/                        # UI module
    ├── __init__.py
    └── main_window.py         # Main window UI
```

## License

[MIT License](LICENSE)