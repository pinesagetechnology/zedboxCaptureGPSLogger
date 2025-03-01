#!/usr/bin/env python3
"""
Main window module for ZED Camera Capture Tool.
Implements the main user interface.
"""

import os
import logging
import time
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QGroupBox, QLabel, QPushButton, 
    QRadioButton, QSpinBox, QDoubleSpinBox, QComboBox,
    QCheckBox, QSlider, QFileDialog, QMessageBox,
    QLineEdit, QTextEdit, QStatusBar, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QDir
from PyQt5.QtGui import QPixmap, QImage

from camera.zed_camera import ZedCamera
from gps.gps_receiver import GPSReceiver
from capture.capture_controller import CaptureController
from config import load_settings, save_settings

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Set up logging
        self.logger = logging.getLogger("MainWindow")
        
        # Load settings
        self.settings = load_settings()
        
        # Initialize modules
        self.camera = ZedCamera()
        self.gps = GPSReceiver()
        self.capture_controller = None  # Will initialize after camera and GPS are connected
        
        # Timers
        self.ui_update_timer = QTimer(self)
        self.ui_update_timer.timeout.connect(self.update_ui)
        self.ui_update_timer.start(500)  # Update UI every 500ms
        
        # Set up UI
        self.setWindowTitle("ZED Camera Capture Tool")
        self.resize(800, 600)
        self.setup_ui()
        
        # Connect to devices
        self.connect_devices()
        
    def setup_ui(self):
        """Set up the main user interface"""
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Tab widget
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # Capture tab
        capture_tab = QWidget()
        tab_widget.addTab(capture_tab, "Capture")
        self.setup_capture_tab(capture_tab)
        
        # Settings tab
        settings_tab = QWidget()
        tab_widget.addTab(settings_tab, "Settings")
        self.setup_settings_tab(settings_tab)
        
        # Status display
        self.setup_status_display(main_layout)
        
    def setup_capture_tab(self, tab):
        """Set up the capture tab UI"""
        layout = QVBoxLayout(tab)
        
        # Preview area
        preview_group = QGroupBox("Camera Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("No preview available")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setStyleSheet("background-color: #222;")
        preview_layout.addWidget(self.preview_label)
        
        layout.addWidget(preview_group)
        
        # Capture controls
        capture_group = QGroupBox("Capture Controls")
        capture_layout = QVBoxLayout(capture_group)
        
        # Capture mode
        mode_layout = QHBoxLayout()
        
        self.time_mode_radio = QRadioButton("Time Interval:")
        self.time_mode_radio.setChecked(self.settings["capture_mode"] == "time")
        self.time_mode_radio.toggled.connect(self.on_capture_mode_changed)
        
        self.time_interval_spin = QSpinBox()
        self.time_interval_spin.setRange(1, 3600)
        self.time_interval_spin.setValue(self.settings["time_interval"])
        self.time_interval_spin.setSuffix(" seconds")
        
        self.gps_mode_radio = QRadioButton("GPS Distance:")
        self.gps_mode_radio.setChecked(self.settings["capture_mode"] == "gps")
        self.gps_mode_radio.toggled.connect(self.on_capture_mode_changed)
        
        self.gps_interval_spin = QDoubleSpinBox()
        self.gps_interval_spin.setRange(1, 1000)
        self.gps_interval_spin.setValue(self.settings["gps_interval"])
        self.gps_interval_spin.setSuffix(" meters")
        
        mode_layout.addWidget(self.time_mode_radio)
        mode_layout.addWidget(self.time_interval_spin)
        mode_layout.addStretch()
        mode_layout.addWidget(self.gps_mode_radio)
        mode_layout.addWidget(self.gps_interval_spin)
        
        capture_layout.addLayout(mode_layout)
        
        # Output directory
        dir_layout = QHBoxLayout()
        
        dir_layout.addWidget(QLabel("Output directory:"))
        
        self.output_dir_edit = QLineEdit(self.settings["output_directory"])
        self.output_dir_edit.setReadOnly(True)
        dir_layout.addWidget(self.output_dir_edit)
        
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.on_browse_clicked)
        dir_layout.addWidget(self.browse_button)
        
        capture_layout.addLayout(dir_layout)
        
        # Capture buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Capture")
        self.start_button.clicked.connect(self.on_start_capture_clicked)
        self.start_button.setEnabled(False)  # Disabled until camera is connected
        
        self.stop_button = QPushButton("Stop Capture")
        self.stop_button.clicked.connect(self.on_stop_capture_clicked)
        self.stop_button.setEnabled(False)  # Disabled until capture starts
        
        self.single_capture_button = QPushButton("Single Capture")
        self.single_capture_button.clicked.connect(self.on_single_capture_clicked)
        self.single_capture_button.setEnabled(False)  # Disabled until camera is connected
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.single_capture_button)
        
        capture_layout.addLayout(button_layout)
        
        layout.addWidget(capture_group)
        
    def setup_settings_tab(self, tab):
        """Set up the settings tab UI"""
        layout = QVBoxLayout(tab)
        
        # Camera settings
        camera_group = QGroupBox("Camera Settings")
        camera_layout = QVBoxLayout(camera_group)
        
        # Camera mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Camera Mode:"))
        
        self.camera_mode_combo = QComboBox()
        self.camera_mode_combo.addItems(["Auto", "Manual"])
        self.camera_mode_combo.setCurrentIndex(0 if self.settings["camera"]["mode"] == "auto" else 1)
        self.camera_mode_combo.currentIndexChanged.connect(self.on_camera_mode_changed)
        
        mode_layout.addWidget(self.camera_mode_combo)
        mode_layout.addStretch()
        
        camera_layout.addLayout(mode_layout)
        
        # Resolution and FPS
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Resolution:"))
        
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["HD2K", "HD1080", "HD720", "VGA"])
        self.resolution_combo.setCurrentText(self.settings["camera"]["resolution"])
        
        res_layout.addWidget(self.resolution_combo)
        res_layout.addStretch()
        
        res_layout.addWidget(QLabel("FPS:"))
        
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["15", "30", "60", "100"])
        self.fps_combo.setCurrentText(str(self.settings["camera"]["fps"]))
        
        res_layout.addWidget(self.fps_combo)
        
        camera_layout.addLayout(res_layout)
        
        # Create settings sliders
        self.camera_sliders = {}
        
        settings_names = [
            ("brightness", "Brightness", 0, 8),
            ("contrast", "Contrast", 0, 8),
            ("hue", "Hue", 0, 11),
            ("saturation", "Saturation", 0, 8),
            ("exposure", "Exposure", -1, 100, True),
            ("gain", "Gain", -1, 100, True),
            ("whitebalance", "White Balance", -1, 6500, True)
        ]
        
        for setting in settings_names:
            if len(setting) == 4:
                name, label, min_val, max_val = setting
                auto_option = False
            else:
                name, label, min_val, max_val, auto_option = setting
                
            # Create slider group
            slider_group = QGroupBox(label)
            slider_layout = QVBoxLayout(slider_group)
            
            # Create auto checkbox if applicable
            if auto_option:
                auto_check = QCheckBox("Auto")
                auto_check.setChecked(self.settings["camera"][name] == -1)
                auto_check.stateChanged.connect(lambda state, n=name: self.on_auto_checkbox_changed(n, state))
                slider_layout.addWidget(auto_check)
                
            # Create slider and value display
            slider_row = QHBoxLayout()
            
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_val if not auto_option else min_val + 1, max_val)
            value = self.settings["camera"][name]
            if auto_option and value == -1:
                value = (max_val - min_val + 1) // 2  # Set to middle value when auto
            slider.setValue(value)
            
            value_label = QLabel(str(value))
            
            slider.valueChanged.connect(lambda value, lbl=value_label, n=name: self.on_slider_value_changed(n, value, lbl))
            
            slider_row.addWidget(slider)
            slider_row.addWidget(value_label)
            
            slider_layout.addLayout(slider_row)
            
            # Store widgets
            self.camera_sliders[name] = {
                "slider": slider,
                "label": value_label,
                "auto": auto_check if auto_option else None
            }
            
            # Disable slider if auto is checked
            if auto_option and self.settings["camera"][name] == -1:
                slider.setEnabled(False)
                
            camera_layout.addWidget(slider_group)
            
        # Connect/Disconnect button
        camera_button_layout = QHBoxLayout()
        
        self.connect_camera_button = QPushButton("Connect Camera")
        self.connect_camera_button.clicked.connect(self.on_connect_camera_clicked)
        
        self.disconnect_camera_button = QPushButton("Disconnect Camera")
        self.disconnect_camera_button.clicked.connect(self.on_disconnect_camera_clicked)
        self.disconnect_camera_button.setEnabled(False)
        
        camera_button_layout.addWidget(self.connect_camera_button)
        camera_button_layout.addWidget(self.disconnect_camera_button)
        
        camera_layout.addLayout(camera_button_layout)
        
        layout.addWidget(camera_group)
        
        # GPS settings
        gps_group = QGroupBox("GPS Settings")
        gps_layout = QVBoxLayout(gps_group)
        
        # GPS port
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        
        self.gps_port_edit = QLineEdit(self.settings["gps"]["port"])
        port_layout.addWidget(self.gps_port_edit)
        
        port_layout.addWidget(QLabel("Baud Rate:"))
        
        self.gps_baud_combo = QComboBox()
        self.gps_baud_combo.addItems(["4800", "9600", "19200", "38400", "57600", "115200"])
        self.gps_baud_combo.setCurrentText(str(self.settings["gps"]["baud_rate"]))
        
        port_layout.addWidget(self.gps_baud_combo)
        
        gps_layout.addLayout(port_layout)
        
        # GPS connect button
        gps_button_layout = QHBoxLayout()
        
        self.connect_gps_button = QPushButton("Connect GPS")
        self.connect_gps_button.clicked.connect(self.on_connect_gps_clicked)
        
        self.disconnect_gps_button = QPushButton("Disconnect GPS")
        self.disconnect_gps_button.clicked.connect(self.on_disconnect_gps_clicked)
        self.disconnect_gps_button.setEnabled(False)
        
        gps_button_layout.addWidget(self.connect_gps_button)
        gps_button_layout.addWidget(self.disconnect_gps_button)
        
        gps_layout.addLayout(gps_button_layout)
        
        layout.addWidget(gps_group)
        
        # Save settings button
        self.save_settings_button = QPushButton("Save Settings")
        self.save_settings_button.clicked.connect(self.on_save_settings_clicked)
        
        layout.addWidget(self.save_settings_button)
        
    def setup_status_display(self, layout):
        """Set up the status display area"""
        status_layout = QHBoxLayout()
        
        # Camera status
        self.camera_status_label = QLabel("Camera: Disconnected")
        status_layout.addWidget(self.camera_status_label)
        
        # GPS status
        self.gps_status_label = QLabel("GPS: Disconnected")
        status_layout.addWidget(self.gps_status_label)
        
        # Capture status
        self.capture_status_label = QLabel("Capture: Idle")
        status_layout.addWidget(self.capture_status_label)
        
        # Capture count
        self.capture_count_label = QLabel("Images: 0")
        status_layout.addWidget(self.capture_count_label)
        
        layout.addLayout(status_layout)
        
    def connect_devices(self):
        """Connect to camera and GPS devices on startup"""
        # Try to connect to camera
        if self.on_connect_camera_clicked():
            self.logger.info("Successfully connected to ZED camera on startup")
            
        # Try to connect to GPS
        if self.on_connect_gps_clicked():
            self.logger.info("Successfully connected to GPS on startup")
            
    def update_ui(self):
        """Update UI with current status (called by timer)"""
        # Update camera status
        if self.camera.is_connected:
            self.camera_status_label.setText("Camera: Connected")
            self.connect_camera_button.setEnabled(False)
            self.disconnect_camera_button.setEnabled(True)
            self.start_button.setEnabled(True)
            self.single_capture_button.setEnabled(True)
        else:
            self.camera_status_label.setText("Camera: Disconnected")
            self.connect_camera_button.setEnabled(True)
            self.disconnect_camera_button.setEnabled(False)
            self.start_button.setEnabled(False)
            self.single_capture_button.setEnabled(False)
            
        # Update GPS status
        if self.gps.is_connected:
            gps_data = self.gps.get_current_data()
            fix_status = "Fix" if self.gps.has_fix() else "No Fix"
            sats = gps_data["satellites"] if gps_data["satellites"] else "?"
            
            self.gps_status_label.setText(f"GPS: Connected ({fix_status}, Sats: {sats})")
            self.connect_gps_button.setEnabled(False)
            self.disconnect_gps_button.setEnabled(True)
        else:
            self.gps_status_label.setText("GPS: Disconnected")
            self.connect_gps_button.setEnabled(True)
            self.disconnect_gps_button.setEnabled(False)
            
        # Update capture status if controller exists
        if self.capture_controller:
            if self.capture_controller.is_capturing:
                stats = self.capture_controller.get_capture_stats()
                
                self.capture_status_label.setText(f"Capture: Active ({stats['mode']} mode)")
                self.capture_count_label.setText(f"Images: {stats['capture_count']}")
                
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                self.single_capture_button.setEnabled(False)
            else:
                self.capture_status_label.setText("Capture: Idle")
                
                self.start_button.setEnabled(self.camera.is_connected)
                self.stop_button.setEnabled(False)
                self.single_capture_button.setEnabled(self.camera.is_connected)
                
    def update_settings_from_ui(self):
        """Update settings dictionary from UI values"""
        # Capture settings
        self.settings["capture_mode"] = "time" if self.time_mode_radio.isChecked() else "gps"
        self.settings["time_interval"] = self.time_interval_spin.value()
        self.settings["gps_interval"] = self.gps_interval_spin.value()
        self.settings["output_directory"] = self.output_dir_edit.text()
        
        # Camera settings
        self.settings["camera"]["mode"] = "auto" if self.camera_mode_combo.currentIndex() == 0 else "manual"
        self.settings["camera"]["resolution"] = self.resolution_combo.currentText()
        self.settings["camera"]["fps"] = int(self.fps_combo.currentText())
        
        # Camera parameters
        for name, widgets in self.camera_sliders.items():
            if widgets["auto"] and widgets["auto"].isChecked():
                self.settings["camera"][name] = -1  # Auto mode
            else:
                self.settings["camera"][name] = widgets["slider"].value()
                
        # GPS settings
        self.settings["gps"]["port"] = self.gps_port_edit.text()
        self.settings["gps"]["baud_rate"] = int(self.gps_baud_combo.currentText())
        
        return self.settings
        
    @pyqtSlot()
    def on_connect_camera_clicked(self):
        """Connect to ZED camera"""
        settings = self.update_settings_from_ui()
        
        self.status_bar.showMessage("Connecting to camera...")
        success = self.camera.connect(settings)
        
        if success:
            self.status_bar.showMessage("Camera connected successfully", 3000)
            
            # Initialize capture controller if not already
            if not self.capture_controller:
                self.capture_controller = CaptureController(self.camera, self.gps, settings)
                
            # Enable camera-related UI elements
            self.update_ui()
            return True
        else:
            self.status_bar.showMessage("Failed to connect to camera", 3000)
            QMessageBox.warning(self, "Connection Error", "Failed to connect to ZED camera. Please check connections and settings.")
            return False
            
    @pyqtSlot()
    def on_disconnect_camera_clicked(self):
        """Disconnect from ZED camera"""
        # Stop capture if running
        if self.capture_controller and self.capture_controller.is_capturing:
            self.capture_controller.stop_capture()
            
        self.camera.disconnect()
        self.status_bar.showMessage("Camera disconnected", 3000)
        self.update_ui()
        
    @pyqtSlot()
    def on_connect_gps_clicked(self):
        """Connect to GPS receiver"""
        settings = self.update_settings_from_ui()
        
        self.status_bar.showMessage("Connecting to GPS...")
        success = self.gps.connect(settings)
        
        if success:
            self.status_bar.showMessage("GPS connected successfully", 3000)
            
            # Initialize capture controller if not already
            if not self.capture_controller and self.camera.is_connected:
                self.capture_controller = CaptureController(self.camera, self.gps, settings)
                
            self.update_ui()
            return True
        else:
            self.status_bar.showMessage("Failed to connect to GPS", 3000)
            QMessageBox.warning(self, "Connection Error", "Failed to connect to GPS. Please check connections and port settings.")
            return False
            
    @pyqtSlot()
    def on_disconnect_gps_clicked(self):
        """Disconnect from GPS receiver"""
        # Stop capture if running in GPS mode
        if (self.capture_controller and 
            self.capture_controller.is_capturing and 
            self.capture_controller.settings["capture_mode"] == "gps"):
            self.capture_controller.stop_capture()
            
        self.gps.disconnect()
        self.status_bar.showMessage("GPS disconnected", 3000)
        self.update_ui()
        
    @pyqtSlot()
    def on_start_capture_clicked(self):
        """Start capture process"""
        if not self.camera.is_connected:
            QMessageBox.warning(self, "Error", "Camera not connected")
            return
            
        if self.settings["capture_mode"] == "gps" and not self.gps.is_connected:
            QMessageBox.warning(self, "Error", "GPS not connected. Required for GPS-based capture.")
            return
            
        # Update settings from UI
        settings = self.update_settings_from_ui()
        
        # Start capture
        if self.capture_controller.start_capture(settings):
            self.status_bar.showMessage(f"Started capture in {settings['capture_mode']} mode", 3000)
        else:
            QMessageBox.warning(self, "Error", "Failed to start capture")
            
        self.update_ui()
        
    @pyqtSlot()
    def on_stop_capture_clicked(self):
        """Stop capture process"""
        if self.capture_controller:
            self.capture_controller.stop_capture()
            self.status_bar.showMessage("Capture stopped", 3000)
            
        self.update_ui()
        
    @pyqtSlot()
    def on_single_capture_clicked(self):
        """Capture a single image"""
        if not self.camera.is_connected:
            QMessageBox.warning(self, "Error", "Camera not connected")
            return
            
        # Update settings from UI
        settings = self.update_settings_from_ui()
        
        # Initialize capture controller if not already
        if not self.capture_controller:
            self.capture_controller = CaptureController(self.camera, self.gps, settings)
            
        # Capture single image
        output_dir = settings["output_directory"]
        success = self.capture_controller._capture_image(output_dir)
        
        if success:
            self.status_bar.showMessage("Image captured successfully", 3000)
            self.capture_count_label.setText(f"Images: {self.capture_controller.capture_count}")
        else:
            QMessageBox.warning(self, "Error", "Failed to capture image")
            
    @pyqtSlot()
    def on_browse_clicked(self):
        """Open file dialog to select output directory"""
        current_dir = self.output_dir_edit.text()
        
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", current_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.output_dir_edit.setText(directory)
            self.settings["output_directory"] = directory
            
    @pyqtSlot(bool)
    def on_capture_mode_changed(self, checked):
        """Handle capture mode radio button changes"""
        if checked:
            if self.time_mode_radio.isChecked():
                self.settings["capture_mode"] = "time"
                self.time_interval_spin.setEnabled(True)
                self.gps_interval_spin.setEnabled(False)
            else:
                self.settings["capture_mode"] = "gps"
                self.time_interval_spin.setEnabled(False)
                self.gps_interval_spin.setEnabled(True)
                
    @pyqtSlot(int)
    def on_camera_mode_changed(self, index):
        """Handle camera mode combobox changes"""
        is_manual = index == 1
        
        # Enable/disable manual sliders based on mode
        for name, widgets in self.camera_sliders.items():
            # For settings with auto option
            if widgets["auto"]:
                widgets["auto"].setEnabled(is_manual)
                widgets["slider"].setEnabled(is_manual and not widgets["auto"].isChecked())
            else:
                widgets["slider"].setEnabled(is_manual)
                
        self.settings["camera"]["mode"] = "manual" if is_manual else "auto"
        
    @pyqtSlot()
    def on_save_settings_clicked(self):
        """Save current settings"""
        settings = self.update_settings_from_ui()
        
        if save_settings(settings):
            self.status_bar.showMessage("Settings saved successfully", 3000)
        else:
            self.status_bar.showMessage("Failed to save settings", 3000)
            
    @pyqtSlot(str, int, QLabel)
    def on_slider_value_changed(self, name, value, label):
        """Handle slider value changes"""
        label.setText(str(value))
        self.settings["camera"][name] = value
        
    @pyqtSlot(str, int)
    def on_auto_checkbox_changed(self, name, state):
        """Handle auto checkbox changes"""
        is_checked = state == Qt.Checked
        
        # Enable/disable slider based on auto checkbox
        self.camera_sliders[name]["slider"].setEnabled(not is_checked)
        
        # Update settings
        if is_checked:
            self.settings["camera"][name] = -1  # -1 indicates auto mode
        else:
            self.settings["camera"][name] = self.camera_sliders[name]["slider"].value()
            
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop any active processes
        if self.capture_controller and self.capture_controller.is_capturing:
            self.capture_controller.stop_capture()
            
        # Disconnect devices
        self.camera.disconnect()
        self.gps.disconnect()
        
        # Save settings
        self.update_settings_from_ui()
        save_settings(self.settings)
        
        # Accept the close event
        event.accept()