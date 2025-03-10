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
- User-friendly Tkinter interface
- Integration with uBlox GPS receiver

## Requirements

- ZED-X Box Orin running Linux
- ZED Camera
- uBlox GPS receiver
- Python 3.6 or higher
- Required Python packages (see requirements.txt)

## Installation

1. Create a virtual environment:
   ```bash
   python3 -m venv zed_venv
   source zed_venv/bin/activate
   ```

2. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/zed-capture-tool.git
   cd zed-capture-tool
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install the ZED SDK if you haven't already:
   Follow the instructions at https://www.stereolabs.com/docs/installation/

5. Install the application:
   ```bash
   pip install -e .
   ```

## Usage

1. Run the application:
   ```bash
   zed_capture
   ```
   or
   ```bash
   python -m zed_capture_tool.main
   ```

2. Connect to your ZED camera and GPS device using the Settings tab.

3. Configure capture settings:
   - Select capture mode (time or GPS)
   - Set interval (seconds or meters)
   - Choose output directory

4. Start capturing images with the "Start Capture" button, or take individual shots with "Single Capture".

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
    └── main_window.py         # Main window UI using Tkinter
```

## Troubleshooting

### Python-tk Installation
If you encounter errors related to Tkinter, you might need to install the Python Tkinter package:

```bash
sudo apt-get update
sudo apt-get install python3-tk
```

### GPS Serial Port Permissions
If you have issues connecting to the GPS device, you may need to add your user to the 'dialout' group to access serial ports:

```bash
sudo usermod -a -G dialout $USER
```
(You'll need to log out and back in for this to take effect)

### ZED SDK Issues
Make sure you have the correct version of the ZED SDK installed for your system. Follow the Stereolabs documentation for your specific platform.

## License

[MIT License](LICENSE)