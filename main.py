#!/usr/bin/env python3
"""
ZED Camera Capture Tool - Main Application

This tool provides a GUI interface for capturing photos from a ZED camera
with options for time interval or GPS location-based capture.
"""

import sys
import os
import logging
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
from config import setup_logging

def main():
    """Main application entry point"""
    # Setup logging
    setup_logging()
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("ZED Camera Capture Tool")
    
    # Create and show main window
    main_window = MainWindow()
    main_window.show()
    
    # Start application event loop
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()