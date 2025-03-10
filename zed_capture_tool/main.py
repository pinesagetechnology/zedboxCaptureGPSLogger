#!/usr/bin/env python3
"""
ZED Camera Capture Tool - Main Application

This tool provides a GUI interface for capturing photos from a ZED camera
with options for time interval or GPS location-based capture.
"""

import sys
import os
import logging
import tkinter as tk
from .ui.main_window import MainWindow
from zed_capture_tool.config import setup_logging

def main():
    """Main application entry point"""
    # Setup logging
    setup_logging()
    
    # Create Tkinter root
    root = tk.Tk()
    root.title("ZED Camera Capture Tool")
    
    # Create main window
    app = MainWindow(root)
    
    # Set up close handler
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Start Tkinter event loop
    root.mainloop()

if __name__ == "__main__":
    main()