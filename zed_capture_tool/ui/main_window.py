#!/usr/bin/env python3
"""
Main window module for ZED Camera Capture Tool.
Implements the main user interface using Tkinter.
"""

import os
import logging
import time
import json
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import StringVar, IntVar, DoubleVar, BooleanVar
import cv2
from PIL import Image, ImageTk
import pyzed.sl as sl

from zed_capture_tool.camera.zed_camera import ZedCamera
from zed_capture_tool.gps.gps_receiver import GPSReceiver
from zed_capture_tool.capture.capture_controller import CaptureController
from zed_capture_tool.video.video_recorder import VideoRecorder
from zed_capture_tool.config import load_settings, save_settings

class MainWindow:
    """Main application window using Tkinter"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("ZED Camera Capture Tool")
        self.root.geometry("800x700")
        
        # Set up logging
        self.logger = logging.getLogger("MainWindow")
        
        # Load settings
        self.settings = load_settings()
        
        # Initialize modules
        self.camera = ZedCamera()
        self.gps = GPSReceiver()
        self.capture_controller = None  # Will initialize after camera and GPS are connected
        
        # Variables for UI elements
        self.capture_mode_var = StringVar(value="time" if self.settings["capture_mode"] == "time" else "gps")
        self.time_interval_var = IntVar(value=self.settings["time_interval"])
        self.gps_interval_var = DoubleVar(value=self.settings["gps_interval"])
        self.output_dir_var = StringVar(value=self.settings["output_directory"])
        self.camera_mode_var = StringVar(value=self.settings["camera"]["mode"])
        self.resolution_var = StringVar(value=self.settings["camera"]["resolution"])
        self.fps_var = IntVar(value=self.settings["camera"]["fps"])
        
        # Camera setting variables
        self.camera_settings_vars = {}
        for name in ["brightness", "contrast", "hue", "saturation", "exposure", "gain", "whitebalance"]:
            self.camera_settings_vars[name] = {
                "value": IntVar(value=self.settings["camera"][name]),
                "auto": BooleanVar(value=(self.settings["camera"][name] == -1))
            }
        
        # GPS setting variables
        self.gps_port_var = StringVar(value=self.settings["gps"]["port"])
        self.gps_baud_var = IntVar(value=self.settings["gps"]["baud_rate"])
        
        # Set up UI
        self.setup_ui()
        
        # Status variables
        self.is_capturing = False
        self.capture_count = 0
        
        # Timer for UI updates
        self.update_ui()
        
        # Connect to devices
        self.connect_devices()
        
    def setup_ui(self):
        """Set up the main user interface"""
        
        # Create a notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Capture tab
        self.capture_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.capture_tab, text="Photo Capture")
        self.setup_capture_tab()
        
        # Video tab
        self.video_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.video_tab, text="Video Recording")
        self.setup_video_tab()
        
        # GPS tab
        self.gps_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.gps_tab, text="GPS Monitor")
        self.setup_gps_tab()
        
        # Settings tab
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="Settings")
        self.setup_settings_tab()
        
        # Status bar
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.camera_status_label = ttk.Label(self.status_frame, text="Camera: Disconnected")
        self.camera_status_label.pack(side=tk.LEFT, padx=5)
        
        self.gps_status_label = ttk.Label(self.status_frame, text="GPS: Disconnected")
        self.gps_status_label.pack(side=tk.LEFT, padx=5)
        
        self.capture_status_label = ttk.Label(self.status_frame, text="Capture: Idle")
        self.capture_status_label.pack(side=tk.LEFT, padx=5)
        
        self.capture_count_label = ttk.Label(self.status_frame, text="Images: 0")
        self.capture_count_label.pack(side=tk.LEFT, padx=5)
        
    def setup_capture_tab(self):
        """Set up the capture tab UI with multiple camera views"""
        
        # Preview area - Now with multiple views
        preview_frame = ttk.LabelFrame(self.capture_tab, text="Camera Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create a frame to hold all preview images
        views_frame = ttk.Frame(preview_frame)
        views_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create labels for each view type
        self.preview_labels = {}
        
        # RGB View
        rgb_frame = ttk.LabelFrame(views_frame, text="RGB View")
        rgb_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        self.preview_labels["rgb"] = tk.Label(rgb_frame, text="No RGB preview", bg="#222222", fg="white")
        self.preview_labels["rgb"].pack(fill=tk.BOTH, expand=True)
        
        # Depth View
        depth_frame = ttk.LabelFrame(views_frame, text="Depth Map")
        depth_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        
        self.preview_labels["depth"] = tk.Label(depth_frame, text="No depth preview", bg="#222222", fg="white")
        self.preview_labels["depth"].pack(fill=tk.BOTH, expand=True)
        
        # Disparity View
        disparity_frame = ttk.LabelFrame(views_frame, text="Disparity Map")
        disparity_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        
        self.preview_labels["disparity"] = tk.Label(disparity_frame, text="No disparity preview", bg="#222222", fg="white")
        self.preview_labels["disparity"].pack(fill=tk.BOTH, expand=True)
        
        # Point Cloud View (optional)
        point_cloud_frame = ttk.LabelFrame(views_frame, text="Point Cloud")
        point_cloud_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")
        
        self.preview_labels["point_cloud"] = tk.Label(point_cloud_frame, text="No point cloud preview", bg="#222222", fg="white")
        self.preview_labels["point_cloud"].pack(fill=tk.BOTH, expand=True)
        
        # Configure grid to expand properly
        views_frame.columnconfigure(0, weight=1)
        views_frame.columnconfigure(1, weight=1)
        views_frame.rowconfigure(0, weight=1)
        views_frame.rowconfigure(1, weight=1)
        
        # Capture mode selection
        view_select_frame = ttk.Frame(preview_frame)
        view_select_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(view_select_frame, text="Views to Capture:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        # Checkboxes for selecting views to capture
        self.capture_rgb_var = BooleanVar(value=True)
        self.capture_depth_var = BooleanVar(value=False)
        self.capture_disparity_var = BooleanVar(value=False)
        self.capture_point_cloud_var = BooleanVar(value=False)
        
        ttk.Checkbutton(view_select_frame, text="RGB", variable=self.capture_rgb_var).grid(row=0, column=1, padx=5)
        ttk.Checkbutton(view_select_frame, text="Depth", variable=self.capture_depth_var).grid(row=0, column=2, padx=5)
        ttk.Checkbutton(view_select_frame, text="Disparity", variable=self.capture_disparity_var).grid(row=0, column=3, padx=5)
        ttk.Checkbutton(view_select_frame, text="Point Cloud", variable=self.capture_point_cloud_var).grid(row=0, column=4, padx=5)
        
        # Capture controls
        control_frame = ttk.LabelFrame(self.capture_tab, text="Capture Controls")
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Capture mode
        mode_frame = ttk.Frame(control_frame)
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Time interval option
        time_radio = ttk.Radiobutton(mode_frame, text="Time Interval:", 
                                    variable=self.capture_mode_var, value="time", 
                                    command=self.on_capture_mode_changed)
        time_radio.grid(row=0, column=0, sticky=tk.W)
        
        time_spin = ttk.Spinbox(mode_frame, from_=1, to=3600, width=10, 
                                textvariable=self.time_interval_var)
        time_spin.grid(row=0, column=1, padx=5)
        
        ttk.Label(mode_frame, text="seconds").grid(row=0, column=2, sticky=tk.W)
        
        # GPS interval option
        gps_radio = ttk.Radiobutton(mode_frame, text="GPS Distance:", 
                                    variable=self.capture_mode_var, value="gps", 
                                    command=self.on_capture_mode_changed)
        gps_radio.grid(row=0, column=3, sticky=tk.W, padx=(20, 0))
        
        gps_spin = ttk.Spinbox(mode_frame, from_=1, to=1000, width=10, 
                                textvariable=self.gps_interval_var)
        gps_spin.grid(row=0, column=4, padx=5)
        
        ttk.Label(mode_frame, text="meters").grid(row=0, column=5, sticky=tk.W)
        
        # Output directory
        dir_frame = ttk.Frame(control_frame)
        dir_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(dir_frame, text="Output directory:").grid(row=0, column=0, sticky=tk.W)
        
        dir_entry = ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=50)
        dir_entry.grid(row=0, column=1, padx=5, sticky=tk.W+tk.E)
        
        browse_button = ttk.Button(dir_frame, text="Browse...", command=self.on_browse_clicked)
        browse_button.grid(row=0, column=2, padx=5)
        
        dir_frame.columnconfigure(1, weight=1)
        
        # Capture buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.start_button = ttk.Button(button_frame, text="Start Capture", 
                                        command=self.on_start_capture_clicked)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.start_button.state(['disabled'])  # Disabled until camera is connected
        
        self.stop_button = ttk.Button(button_frame, text="Stop Capture", 
                                        command=self.on_stop_capture_clicked)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.stop_button.state(['disabled'])  # Disabled until capture starts
        
        self.single_capture_button = ttk.Button(button_frame, text="Single Capture", 
                                                command=self.on_single_capture_clicked)
        self.single_capture_button.pack(side=tk.LEFT, padx=5)
        self.single_capture_button.state(['disabled'])  # Disabled until camera is connected
        
    def setup_settings_tab(self):
        """Set up the settings tab UI"""
        
        # Create a notebook for settings categories
        settings_notebook = ttk.Notebook(self.settings_tab)
        settings_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Camera settings tab
        camera_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(camera_tab, text="Camera")
        
        # Camera mode
        mode_frame = ttk.Frame(camera_tab)
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(mode_frame, text="Camera Mode:").grid(row=0, column=0, sticky=tk.W)
        
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.camera_mode_var, 
                                 values=["auto", "manual"], state="readonly", width=15)
        mode_combo.grid(row=0, column=1, padx=5, sticky=tk.W)
        mode_combo.bind("<<ComboboxSelected>>", self.on_camera_mode_changed)
        
        # Resolution and FPS
        res_frame = ttk.Frame(camera_tab)
        res_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(res_frame, text="Resolution:").grid(row=0, column=0, sticky=tk.W)
        
        res_combo = ttk.Combobox(res_frame, textvariable=self.resolution_var, 
                                values=["HD2K", "HD1080", "HD720", "VGA"], 
                                state="readonly", width=15)
        res_combo.grid(row=0, column=1, padx=5, sticky=tk.W)
        
        ttk.Label(res_frame, text="FPS:").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        
        fps_combo = ttk.Combobox(res_frame, textvariable=self.fps_var, 
                                values=[15, 30, 60, 100], 
                                state="readonly", width=15)
        fps_combo.grid(row=0, column=3, padx=5, sticky=tk.W)
        
        # Camera settings sliders
        settings_frame = ttk.Frame(camera_tab)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create settings sliders
        settings_info = [
            ("brightness", "Brightness", 0, 8),
            ("contrast", "Contrast", 0, 8),
            ("hue", "Hue", 0, 11),
            ("saturation", "Saturation", 0, 8),
            ("exposure", "Exposure", -1, 100, True),
            ("gain", "Gain", -1, 100, True),
            ("whitebalance", "White Balance", -1, 6500, True)
        ]
        
        self.camera_setting_widgets = {}
        
        for idx, setting in enumerate(settings_info):
            if len(setting) == 4:
                name, label, min_val, max_val = setting
                auto_option = False
            else:
                name, label, min_val, max_val, auto_option = setting
                
            # Create setting frame
            setting_frame = ttk.LabelFrame(settings_frame, text=label)
            setting_frame.grid(row=idx // 2, column=idx % 2, padx=10, pady=5, sticky=tk.W+tk.E+tk.N+tk.S)
            
            # Auto checkbox if applicable
            if auto_option:
                auto_check = ttk.Checkbutton(setting_frame, text="Auto", 
                                          variable=self.camera_settings_vars[name]["auto"],
                                          command=lambda n=name: self.on_auto_checkbox_changed(n))
                auto_check.pack(anchor=tk.W, padx=5, pady=2)
                
            # Create scale
            scale = ttk.Scale(setting_frame, from_=min_val if not auto_option else min_val + 1, 
                            to=max_val, orient=tk.HORIZONTAL, 
                            variable=self.camera_settings_vars[name]["value"],
                            command=lambda val, n=name: self.on_scale_value_changed(n, val))
            scale.pack(fill=tk.X, padx=5, pady=5)
            
            # Value label
            value_label = ttk.Label(setting_frame, text=str(self.camera_settings_vars[name]["value"].get()))
            value_label.pack(anchor=tk.E, padx=5, pady=2)
            
            # Store widgets
            self.camera_setting_widgets[name] = {
                "scale": scale,
                "label": value_label,
                "auto": auto_check if auto_option else None
            }
            
            # Disable scale if auto is checked
            if auto_option and self.camera_settings_vars[name]["auto"].get():
                scale.state(['disabled'])
        
        # Camera connect buttons
        cam_button_frame = ttk.Frame(camera_tab)
        cam_button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.connect_camera_button = ttk.Button(cam_button_frame, text="Connect Camera", 
                                              command=self.on_connect_camera_clicked)
        self.connect_camera_button.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_camera_button = ttk.Button(cam_button_frame, text="Disconnect Camera", 
                                                 command=self.on_disconnect_camera_clicked)
        self.disconnect_camera_button.pack(side=tk.LEFT, padx=5)
        self.disconnect_camera_button.state(['disabled'])
        
        # GPS settings tab
        gps_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(gps_tab, text="GPS")
        
        # GPS port
        port_frame = ttk.Frame(gps_tab)
        port_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(port_frame, text="Port:").grid(row=0, column=0, sticky=tk.W)
        
        port_entry = ttk.Entry(port_frame, textvariable=self.gps_port_var, width=20)
        port_entry.grid(row=0, column=1, padx=5, sticky=tk.W)
        
        ttk.Label(port_frame, text="Baud Rate:").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        
        baud_combo = ttk.Combobox(port_frame, textvariable=self.gps_baud_var, 
                                 values=[4800, 9600, 19200, 38400, 57600, 115200], 
                                 state="readonly", width=10)
        baud_combo.grid(row=0, column=3, padx=5, sticky=tk.W)
        
        # GPS connect buttons
        gps_button_frame = ttk.Frame(gps_tab)
        gps_button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.connect_gps_button = ttk.Button(gps_button_frame, text="Connect GPS", 
                                           command=self.on_connect_gps_clicked)
        self.connect_gps_button.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_gps_button = ttk.Button(gps_button_frame, text="Disconnect GPS", 
                                              command=self.on_disconnect_gps_clicked)
        self.disconnect_gps_button.pack(side=tk.LEFT, padx=5)
        self.disconnect_gps_button.state(['disabled'])
        
        # Save button
        save_frame = ttk.Frame(self.settings_tab)
        save_frame.pack(fill=tk.X, padx=10, pady=10)
        
        save_button = ttk.Button(save_frame, text="Save Settings", 
                               command=self.on_save_settings_clicked)
        save_button.pack(side=tk.RIGHT, padx=5)
        
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
        try:
            # Update camera status
            if self.camera.is_connected:
                self.camera_status_label.config(text="Camera: Connected")
                self.connect_camera_button.state(['disabled'])
                self.disconnect_camera_button.state(['!disabled'])
                self.start_button.state(['!disabled'])
                self.single_capture_button.state(['!disabled'])
                
                # Enable video recording buttons
                if hasattr(self, 'start_record_button'):
                    if not hasattr(self, 'video_recorder') or not self.video_recorder.is_recording:
                        self.start_record_button.state(['!disabled'])
                    else:
                        self.start_record_button.state(['disabled'])
            else:
                self.camera_status_label.config(text="Camera: Disconnected")
                self.connect_camera_button.state(['!disabled'])
                self.disconnect_camera_button.state(['disabled'])
                self.start_button.state(['disabled'])
                self.single_capture_button.state(['disabled'])
                
                # Disable video recording buttons
                if hasattr(self, 'start_record_button'):
                    self.start_record_button.state(['disabled'])
                    
            # Update GPS status
            if self.gps.is_connected:
                gps_data = self.gps.get_current_data()
                fix_status = "Fix" if self.gps.has_fix() else "No Fix"
                sats = gps_data["satellites"] if gps_data["satellites"] else "?"
                
                self.gps_status_label.config(text=f"GPS: Connected ({fix_status}, Sats: {sats})")
                self.connect_gps_button.state(['disabled'])
                self.disconnect_gps_button.state(['!disabled'])
            else:
                self.gps_status_label.config(text="GPS: Disconnected")
                self.connect_gps_button.state(['!disabled'])
                self.disconnect_gps_button.state(['disabled'])
                
            # Update capture status if controller exists
            if self.capture_controller:
                if self.capture_controller.is_capturing:
                    stats = self.capture_controller.get_capture_stats()
                    
                    self.capture_status_label.config(text=f"Capture: Active ({stats['mode']} mode)")
                    self.capture_count_label.config(text=f"Images: {stats['capture_count']}")
                    
                    self.start_button.state(['disabled'])
                    self.stop_button.state(['!disabled'])
                    self.single_capture_button.state(['disabled'])
                else:
                    self.capture_status_label.config(text="Capture: Idle")
                    
                    if self.camera.is_connected:
                        self.start_button.state(['!disabled'])
                        self.single_capture_button.state(['!disabled'])
                    else:
                        self.start_button.state(['disabled'])
                        self.single_capture_button.state(['disabled'])
                        
                    self.stop_button.state(['disabled'])
                    
            # Update video recording status
            if hasattr(self, 'video_recorder'):
                if self.video_recorder.is_recording:
                    status = self.video_recorder.get_recording_status()
                    duration = status["duration"]
                    file_path = status["file_path"]
                    
                    if hasattr(self, 'recording_status_label'):
                        self.recording_status_label.config(text="Recording")
                        self.recording_duration_label.config(text=f"{duration:.1f} seconds")
                        
                        if file_path:
                            self.recording_file_label.config(text=os.path.basename(file_path))
                            
                    # Update button states
                    if hasattr(self, 'start_record_button'):
                        self.start_record_button.state(['disabled'])
                        self.stop_record_button.state(['!disabled'])
                        
        except Exception as e:
            self.logger.error(f"Error updating UI: {e}")
            
        # Schedule the next update
        self.root.after(500, self.update_ui)
        
    def update_settings_from_ui(self):
        """Update settings dictionary from UI values"""
        # Capture settings
        self.settings["capture_mode"] = self.capture_mode_var.get()
        self.settings["time_interval"] = self.time_interval_var.get()
        self.settings["gps_interval"] = self.gps_interval_var.get()
        self.settings["output_directory"] = self.output_dir_var.get()
        
        # Add view type settings
        if not "view_types" in self.settings:
            self.settings["view_types"] = {}
            
        if hasattr(self, 'capture_rgb_var'):
            self.settings["view_types"]["rgb"] = self.capture_rgb_var.get()
            self.settings["view_types"]["depth"] = self.capture_depth_var.get()
            self.settings["view_types"]["disparity"] = self.capture_disparity_var.get()
            self.settings["view_types"]["point_cloud"] = self.capture_point_cloud_var.get()
            
        # Camera settings
        self.settings["camera"]["mode"] = self.camera_mode_var.get()
        self.settings["camera"]["resolution"] = self.resolution_var.get()
        self.settings["camera"]["fps"] = self.fps_var.get()
        
        # Camera parameters
        for name, vars_dict in self.camera_settings_vars.items():
            if "auto" in vars_dict and vars_dict["auto"].get():
                self.settings["camera"][name] = -1  # Auto mode
            else:
                self.settings["camera"][name] = vars_dict["value"].get()
                
        # GPS settings
        self.settings["gps"]["port"] = self.gps_port_var.get()
        self.settings["gps"]["baud_rate"] = self.gps_baud_var.get()
        
        return self.settings
        
    def on_connect_camera_clicked(self):
        """Connect to ZED camera"""
        settings = self.update_settings_from_ui()
        
        self.root.title("ZED Camera Capture Tool - Connecting to camera...")
        self.root.update()
        
        success = self.camera.connect(settings)
        
        if success:
            self.root.title("ZED Camera Capture Tool")
            
            # Initialize capture controller if not already
            if not self.capture_controller:
                self.capture_controller = CaptureController(self.camera, self.gps, settings)
            
            # Start preview updates
            self.update_preview()
                
            return True
        else:
            self.root.title("ZED Camera Capture Tool")
            messagebox.showerror("Connection Error", 
                               "Failed to connect to ZED camera. Please check connections and settings.")
            return False
            
    def on_disconnect_camera_clicked(self):
        """Disconnect from ZED camera"""
        # Stop capture if running
        if self.capture_controller and self.capture_controller.is_capturing:
            self.capture_controller.stop_capture()

        # Remove preview image if it exists
        if hasattr(self, 'photo_image'):
            self.preview_label.config(image=None)
            self.photo_image = None
            
        self.camera.disconnect()
        
    def on_connect_gps_clicked(self):
        """Connect to GPS receiver"""
        settings = self.update_settings_from_ui()
        
        self.root.title("ZED Camera Capture Tool - Connecting to GPS...")
        self.root.update()
        
        success = self.gps.connect(settings)
        
        if success:
            self.root.title("ZED Camera Capture Tool")
            
            # Initialize capture controller if not already
            if not self.capture_controller and self.camera.is_connected:
                self.capture_controller = CaptureController(self.camera, self.gps, settings)
                
            return True
        else:
            self.root.title("ZED Camera Capture Tool")
            messagebox.showerror("Connection Error", 
                               "Failed to connect to GPS. Please check connections and port settings.")
            return False
            
    def on_disconnect_gps_clicked(self):
        """Disconnect from GPS receiver"""
        # Stop capture if running in GPS mode
        if (self.capture_controller and 
            self.capture_controller.is_capturing and 
            self.settings["capture_mode"] == "gps"):
            self.capture_controller.stop_capture()
            
        self.gps.disconnect()
        
    def on_start_capture_clicked(self):
        """Start capture process"""
        if not self.camera.is_connected:
            messagebox.showerror("Error", "Camera not connected")
            return
            
        if self.settings["capture_mode"] == "gps" and not self.gps.is_connected:
            messagebox.showerror("Error", "GPS not connected. Required for GPS-based capture.")
            return
            
        # Update settings from UI
        settings = self.update_settings_from_ui()
        
        # Start capture
        if self.capture_controller.start_capture(settings):
            self.root.title(f"ZED Camera Capture Tool - Capturing ({settings['capture_mode']} mode)")
        else:
            messagebox.showerror("Error", "Failed to start capture")
            
    def on_stop_capture_clicked(self):
        """Stop capture process"""
        if self.capture_controller:
            self.capture_controller.stop_capture()
            self.root.title("ZED Camera Capture Tool")
            
    def on_single_capture_clicked(self):
        """Capture a single image with all selected view types"""
        if not self.camera.is_connected:
            messagebox.showerror("Error", "Camera not connected")
            return
            
        # Update settings from UI
        settings = self.update_settings_from_ui()
        
        # Initialize capture controller if not already
        if not self.capture_controller:
            self.capture_controller = CaptureController(self.camera, self.gps, settings)
            
        # Get selected view types to capture
        view_types = self.get_selected_view_types()
        
        if not view_types:
            messagebox.showerror("Error", "No view types selected for capture")
            return
            
        # Capture images
        output_dir = settings["output_directory"]
        success = self.capture_controller._capture_image(output_dir, view_types=view_types)
        
        if success:
            self.capture_count_label.config(text=f"Images: {self.capture_controller.capture_count}")
        else:
            messagebox.showerror("Error", "Failed to capture image")
    
    def get_selected_view_types(self):
        """Get list of selected view types to capture"""
        view_types = []
        
        if hasattr(self, 'capture_rgb_var') and self.capture_rgb_var.get():
            view_types.append("rgb")
            
        if hasattr(self, 'capture_depth_var') and self.capture_depth_var.get():
            view_types.append("depth")
            
        if hasattr(self, 'capture_disparity_var') and self.capture_disparity_var.get():
            view_types.append("disparity")
            
        if hasattr(self, 'capture_point_cloud_var') and self.capture_point_cloud_var.get():
            view_types.append("point_cloud")
            
        # If nothing is selected, default to RGB
        if not view_types:
            view_types = ["rgb"]
            
        return view_types

    def on_browse_clicked(self):
        """Open file dialog to select output directory"""
        current_dir = self.output_dir_var.get()
        
        directory = filedialog.askdirectory(
            initialdir=current_dir,
            title="Select Output Directory"
        )
        
        if directory:
            self.output_dir_var.set(directory)
            
    def on_capture_mode_changed(self):
        """Handle capture mode radio button changes"""
        mode = self.capture_mode_var.get()
        if mode == "time":
            self.settings["capture_mode"] = "time"
        else:
            self.settings["capture_mode"] = "gps"
                
    def on_camera_mode_changed(self, event=None):
        """Handle camera mode combobox changes"""
        is_manual = (self.camera_mode_var.get() == "manual")
        
        # Enable/disable manual sliders based on mode
        for name, widgets in self.camera_setting_widgets.items():
            # For settings with auto option
            if widgets["auto"]:
                if is_manual:
                    widgets["auto"].state(['!disabled'])
                    if not self.camera_settings_vars[name]["auto"].get():
                        widgets["scale"].state(['!disabled'])
                    else:
                        widgets["scale"].state(['disabled'])
                else:
                    widgets["auto"].state(['disabled'])
                    widgets["scale"].state(['disabled'])
            else:
                if is_manual:
                    widgets["scale"].state(['!disabled'])
                else:
                    widgets["scale"].state(['disabled'])
                
        self.settings["camera"]["mode"] = "manual" if is_manual else "auto"
        
    def on_save_settings_clicked(self):
        """Save current settings"""
        settings = self.update_settings_from_ui()
        
        if save_settings(settings):
            messagebox.showinfo("Success", "Settings saved successfully")
        else:
            messagebox.showerror("Error", "Failed to save settings")
            
    def on_scale_value_changed(self, name, value):
        """Handle slider value changes"""
        try:
            # Convert from string to float to int
            value = int(float(value))
            self.camera_setting_widgets[name]["label"].config(text=str(value))
            self.camera_settings_vars[name]["value"].set(value)
        except Exception as e:
            self.logger.error(f"Error updating scale value: {e}")
        
    def on_auto_checkbox_changed(self, name):
        """Handle auto checkbox changes"""
        is_checked = self.camera_settings_vars[name]["auto"].get()
        
        # Enable/disable slider based on auto checkbox
        if is_checked:
            self.camera_setting_widgets[name]["scale"].state(['disabled'])
            self.settings["camera"][name] = -1  # -1 indicates auto mode
        else:
            self.camera_setting_widgets[name]["scale"].state(['!disabled'])
            self.settings["camera"][name] = self.camera_settings_vars[name]["value"].get()
            
    def on_closing(self):
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
        
        # Destroy window
        self.root.destroy()
    
    def update_preview(self):
        """Update the camera preview images for all views"""
        if not self.camera.is_connected:
            return
            
        try:
            # Get all view types
            views_to_display = ["rgb", "depth", "disparity"]
            frame_data = self.camera.get_current_frame(views_to_display)
            
            if not frame_data:
                return
                
            # Import numpy if needed for conversions
            import numpy as np
                
            # Create a dictionary to store the PhotoImage objects to prevent garbage collection
            if not hasattr(self, 'photo_images'):
                self.photo_images = {}
                
            # Process each view
            for view_name, image_data in frame_data.items():
                if image_data is not None and view_name in self.preview_labels:
                    # Convert image data based on view type
                    if view_name == "rgb":
                        # RGB image - convert from BGR to RGB
                        image_rgb = cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)
                    elif view_name == "depth":
                        # Depth image - normalize for better visualization
                        # Scale to 0-255 for visibility
                        depth_normalized = cv2.normalize(image_data, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                        # Apply colormap for better visualization
                        image_rgb = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_JET)
                        image_rgb = cv2.cvtColor(image_rgb, cv2.COLOR_BGR2RGB)
                    elif view_name == "disparity":
                        # Disparity image - normalize for better visualization
                        disparity_normalized = cv2.normalize(image_data, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                        # Apply colormap for better visualization
                        image_rgb = cv2.applyColorMap(disparity_normalized, cv2.COLORMAP_JET)
                        image_rgb = cv2.cvtColor(image_rgb, cv2.COLOR_BGR2RGB)
                    elif view_name == "point_cloud":
                        # Point cloud - create a simple 2D representation
                        # This is just a placeholder - a proper 3D visualization would require more complex code
                        point_cloud_img = image_data[:, :, 0:3]  # Take RGB part
                        image_rgb = cv2.cvtColor(point_cloud_img.astype(np.uint8), cv2.COLOR_BGR2RGB)
                    else:
                        # For any other view type, just convert to RGB
                        image_rgb = cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)
                    
                    # Resize image to fit the preview area
                    preview_width = self.preview_labels[view_name].winfo_width()
                    preview_height = self.preview_labels[view_name].winfo_height()
                    
                    if preview_width > 100 and preview_height > 100:  # Ensure the widget has a reasonable size
                        # Calculate aspect ratio
                        img_height, img_width = image_rgb.shape[:2]
                        aspect_ratio = img_width / img_height
                        
                        # Calculate new dimensions maintaining aspect ratio
                        if preview_width / preview_height > aspect_ratio:
                            # Preview area is wider than the image
                            new_height = preview_height
                            new_width = int(new_height * aspect_ratio)
                        else:
                            # Preview area is taller than the image
                            new_width = preview_width
                            new_height = int(new_width / aspect_ratio)
                        
                        # Resize image
                        image_resized = cv2.resize(image_rgb, (new_width, new_height))
                        
                        # Convert to PIL Image
                        image_pil = Image.fromarray(image_resized)
                        
                        # Convert to PhotoImage for Tkinter
                        self.photo_images[view_name] = ImageTk.PhotoImage(image=image_pil)
                        
                        # Update label
                        self.preview_labels[view_name].config(image=self.photo_images[view_name])
                        self.preview_labels[view_name].image = self.photo_images[view_name]  # Keep a reference
                        
        except Exception as e:
            self.logger.error(f"Error updating preview: {e}")
            
        # Schedule next update if still connected
        if self.camera.is_connected:
            self.root.after(100, self.update_preview)  # Update every 100ms
            
    def setup_video_tab(self):
        """Set up the video recording tab UI"""
        
        # Video control frame
        control_frame = ttk.LabelFrame(self.video_tab, text="Video Recording")
        control_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Output directory
        dir_frame = ttk.Frame(control_frame)
        dir_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(dir_frame, text="Output directory:").grid(row=0, column=0, sticky=tk.W)
        
        # Reuse the same output directory from capture tab
        dir_entry = ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=50)
        dir_entry.grid(row=0, column=1, padx=5, sticky=tk.W+tk.E)
        
        browse_button = ttk.Button(dir_frame, text="Browse...", command=self.on_browse_clicked)
        browse_button.grid(row=0, column=2, padx=5)
        
        dir_frame.columnconfigure(1, weight=1)
        
        # Video settings
        settings_frame = ttk.Frame(control_frame)
        settings_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Codec selection
        ttk.Label(settings_frame, text="Codec:").grid(row=0, column=0, sticky=tk.W)
        
        self.codec_var = StringVar(value="H264")
        codec_combo = ttk.Combobox(settings_frame, textvariable=self.codec_var, 
                                values=["H264", "H265"], state="readonly", width=10)
        codec_combo.grid(row=0, column=1, padx=5, sticky=tk.W)
        
        # Bitrate
        ttk.Label(settings_frame, text="Bitrate (Kbps):").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        
        self.bitrate_var = IntVar(value=8000)  # 8 Mbps default
        bitrate_spin = ttk.Spinbox(settings_frame, from_=1000, to=50000, increment=1000,
                                textvariable=self.bitrate_var, width=8)
        bitrate_spin.grid(row=0, column=3, padx=5, sticky=tk.W)
        
        # Recording duration limit
        ttk.Label(settings_frame, text="Duration limit (sec):").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        
        self.duration_limit_var = IntVar(value=0)  # 0 means no limit
        duration_spin = ttk.Spinbox(settings_frame, from_=0, to=3600, increment=10,
                                textvariable=self.duration_limit_var, width=8)
        duration_spin.grid(row=1, column=1, padx=5, sticky=tk.W, pady=(10, 0))
        ttk.Label(settings_frame, text="(0 = no limit)").grid(row=1, column=2, sticky=tk.W, pady=(10, 0))
        
        # Record buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.start_record_button = ttk.Button(button_frame, text="Start Recording", 
                                            command=self.on_start_recording_clicked)
        self.start_record_button.pack(side=tk.LEFT, padx=5)
        self.start_record_button.state(['disabled'])  # Disabled until camera is connected
        
        self.stop_record_button = ttk.Button(button_frame, text="Stop Recording", 
                                        command=self.on_stop_recording_clicked)
        self.stop_record_button.pack(side=tk.LEFT, padx=5)
        self.stop_record_button.state(['disabled'])  # Disabled until recording starts
        
        # Recording status
        status_frame = ttk.LabelFrame(self.video_tab, text="Recording Status")
        status_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Status labels
        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(status_grid, text="Status:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.recording_status_label = ttk.Label(status_grid, text="Not recording")
        self.recording_status_label.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(status_grid, text="Duration:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.recording_duration_label = ttk.Label(status_grid, text="0 seconds")
        self.recording_duration_label.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(status_grid, text="Output file:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.recording_file_label = ttk.Label(status_grid, text="None")
        self.recording_file_label.grid(row=2, column=1, sticky=tk.W, pady=2)
        
        # Video file list
        list_frame = ttk.LabelFrame(self.video_tab, text="Recorded Videos")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add a listbox with scrollbar
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.video_listbox = tk.Listbox(list_container)
        self.video_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.video_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.video_listbox.config(yscrollcommand=scrollbar.set)
        
        # Button to refresh video list
        refresh_button = ttk.Button(list_frame, text="Refresh List", command=self.refresh_video_list)
        refresh_button.pack(side=tk.LEFT, padx=5, pady=5)

    # Add these methods to handle video recording functionality
    def on_start_recording_clicked(self):
        """Start video recording"""
        if not self.camera.is_connected:
            messagebox.showerror("Error", "Camera not connected")
            return
            
        # Get output directory
        output_dir = self.output_dir_var.get()
        
        # Get recording settings
        codec = self.codec_var.get()
        bitrate = self.bitrate_var.get()
        
        # Initialize video recorder if not already
        if not hasattr(self, 'video_recorder'):
            self.video_recorder = VideoRecorder(self.camera)
        
        # Start recording
        success = self.video_recorder.start_recording(
            output_dir=output_dir,
            codec=codec,
            bitrate=bitrate
        )
        
        if success:
            # Update UI
            self.recording_status_label.config(text="Recording")
            self.start_record_button.state(['disabled'])
            self.stop_record_button.state(['!disabled'])
            
            # Start duration timer
            self.recording_start_time = time.time()
            self.update_recording_duration()
            
            # Set up duration limit if specified
            duration_limit = self.duration_limit_var.get()
            if duration_limit > 0:
                self.root.after(duration_limit * 1000, self.check_duration_limit)
        else:
            messagebox.showerror("Error", "Failed to start recording")

    def on_stop_recording_clicked(self):
        """Stop video recording"""
        if not hasattr(self, 'video_recorder') or not self.video_recorder.is_recording:
            return
            
        # Stop recording
        success, video_path, duration = self.video_recorder.stop_recording()
        
        if success:
            # Update UI
            self.recording_status_label.config(text="Not recording")
            self.recording_duration_label.config(text="0 seconds")
            self.recording_file_label.config(text=os.path.basename(video_path) if video_path else "None")
            
            self.start_record_button.state(['!disabled'])
            self.stop_record_button.state(['disabled'])
            
            # Refresh video list
            self.refresh_video_list()
            
            # Show success message
            messagebox.showinfo("Recording Complete", 
                            f"Video saved to:\n{video_path}\n\nDuration: {duration:.1f} seconds")
        else:
            messagebox.showerror("Error", "Failed to stop recording")

    def update_recording_duration(self):
        """Update the recording duration display"""
        if hasattr(self, 'video_recorder') and self.video_recorder.is_recording:
            status = self.video_recorder.get_recording_status()
            duration = status["duration"]
            self.recording_duration_label.config(text=f"{duration:.1f} seconds")
            
            # Update file path
            file_path = status["file_path"]
            if file_path:
                self.recording_file_label.config(text=os.path.basename(file_path))
            
            # Schedule next update
            self.root.after(500, self.update_recording_duration)

    def check_duration_limit(self):
        """Check if recording duration limit has been reached"""
        if hasattr(self, 'video_recorder') and self.video_recorder.is_recording:
            duration_limit = self.duration_limit_var.get()
            if duration_limit > 0:
                status = self.video_recorder.get_recording_status()
                if status["duration"] >= duration_limit:
                    self.logger.info(f"Duration limit reached ({duration_limit} seconds). Stopping recording.")
                    self.on_stop_recording_clicked()

    def refresh_video_list(self):
        """Refresh the list of recorded videos"""
        try:
            # Clear current list
            self.video_listbox.delete(0, tk.END)
            
            # Get output directory
            output_dir = self.output_dir_var.get()
            print(f"Looking for videos in: {output_dir}")  # Debug print
            
            if not output_dir or not os.path.exists(output_dir):
                print(f"Output directory doesn't exist: {output_dir}")  # Debug print
                return
                
            # Find all SVO files in the directory
            video_files = sorted(Path(output_dir).glob("*.svo"), reverse=True)
            print(f"Found {len(list(video_files))} video files")  # Debug print
            
            for video_file in video_files:
                # Try to get metadata
                metadata_file = video_file.with_suffix('.json')
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                            
                        start_time = metadata.get("start_time", "Unknown")
                        duration = metadata.get("duration_seconds", 0)
                        
                        # Format display string
                        display = f"{video_file.name} - {start_time} ({duration:.1f}s)"
                    except:
                        display = f"{video_file.name}"
                else:
                    display = f"{video_file.name}"
                    
                self.video_listbox.insert(tk.END, display)
        except Exception as e:
            self.logger.error(f"Error refreshing video list: {e}")
            print(f"Error refreshing video list: {e}")  # Debug print

    # Update the on_closing method to handle video recording
    def on_closing(self):
        """Handle window close event"""
        # Stop recording if active
        if hasattr(self, 'video_recorder') and self.video_recorder.is_recording:
            self.video_recorder.stop_recording()
        
        # Stop any active processes
        if self.capture_controller and self.capture_controller.is_capturing:
            self.capture_controller.stop_capture()
            
        # Disconnect devices
        self.camera.disconnect()
        self.gps.disconnect()
        
        # Save settings
        self.update_settings_from_ui()
        save_settings(self.settings)
        
        # Destroy window
        self.root.destroy()
    def setup_gps_tab(self):
        """Set up the GPS testing and monitoring tab"""
        
        # Main frame
        main_frame = ttk.Frame(self.gps_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # GPS Connection Frame
        conn_frame = ttk.LabelFrame(main_frame, text="GPS Connection")
        conn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Port and baud rate
        settings_frame = ttk.Frame(conn_frame)
        settings_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(settings_frame, text="Port:").grid(row=0, column=0, sticky=tk.W)
        
        # Default to ttyACM0 for your setup
        self.gps_port_var.set("/dev/ttyACM0")
        port_entry = ttk.Entry(settings_frame, textvariable=self.gps_port_var, width=20)
        port_entry.grid(row=0, column=1, padx=5, sticky=tk.W)
        
        ttk.Label(settings_frame, text="Baud Rate:").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        
        baud_combo = ttk.Combobox(settings_frame, textvariable=self.gps_baud_var, 
                                values=[4800, 9600, 19200, 38400, 57600, 115200], 
                                state="readonly", width=10)
        baud_combo.grid(row=0, column=3, padx=5, sticky=tk.W)
        
        # Connect buttons
        button_frame = ttk.Frame(conn_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.gps_connect_button = ttk.Button(button_frame, text="Connect GPS", 
                                        command=self.on_gps_connect_clicked)
        self.gps_connect_button.pack(side=tk.LEFT, padx=5)
        
        self.gps_disconnect_button = ttk.Button(button_frame, text="Disconnect GPS", 
                                            command=self.on_gps_disconnect_clicked)
        self.gps_disconnect_button.pack(side=tk.LEFT, padx=5)
        self.gps_disconnect_button.state(['disabled'])
        
        self.gps_test_button = ttk.Button(button_frame, text="Test GPS Signal", 
                                        command=self.on_test_gps_clicked)
        self.gps_test_button.pack(side=tk.LEFT, padx=5)
        self.gps_test_button.state(['disabled'])
        
        # GPS Status Frame
        status_frame = ttk.LabelFrame(main_frame, text="GPS Status")
        status_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Status grid - show key GPS data
        self.gps_status_grid = ttk.Frame(status_frame)
        self.gps_status_grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create status labels
        status_labels = [
            ("Connection Status:", "Not Connected", "gps_connection_status"),
            ("Fix Type:", "No Fix", "gps_fix_type"),
            ("Satellites:", "0", "gps_satellites"),
            ("Latitude:", "N/A", "gps_latitude"),
            ("Longitude:", "N/A", "gps_longitude"),
            ("Altitude:", "N/A", "gps_altitude"),
            ("Speed:", "N/A", "gps_speed"),
            ("Time:", "N/A", "gps_time")
        ]
        
        self.gps_status_labels = {}
        
        for i, (label_text, default_value, variable_name) in enumerate(status_labels):
            ttk.Label(self.gps_status_grid, text=label_text).grid(row=i, column=0, sticky=tk.W, pady=2)
            label = ttk.Label(self.gps_status_grid, text=default_value)
            label.grid(row=i, column=1, sticky=tk.W, pady=2, padx=5)
            self.gps_status_labels[variable_name] = label
        
        # Raw NMEA data display
        nmea_frame = ttk.LabelFrame(main_frame, text="Raw NMEA Data")
        nmea_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Text widget with scrollbar for NMEA sentences
        self.nmea_text = tk.Text(nmea_frame, height=8, width=80, wrap=tk.WORD)
        self.nmea_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(nmea_frame, orient="vertical", command=self.nmea_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.nmea_text.config(yscrollcommand=scrollbar.set)
        
        # Button to clear NMEA log
        clear_button = ttk.Button(nmea_frame, text="Clear Log", 
                                command=lambda: self.nmea_text.delete(1.0, tk.END))
        clear_button.pack(pady=5)

    def on_gps_connect_clicked(self):
        """Connect to GPS receiver from GPS tab"""
        settings = self.update_settings_from_ui()
        
        self.root.title("ZED Camera Capture Tool - Connecting to GPS...")
        self.root.update()
        
        # Update UI immediately to show trying to connect
        self.gps_status_labels["gps_connection_status"].config(text="Connecting...")
        self.gps_status_labels["gps_connection_status"].config(foreground="orange")
        self.root.update()
        
        # Enable verbose logging for connection
        old_level = logging.getLogger("GPSReceiver").level
        logging.getLogger("GPSReceiver").setLevel(logging.DEBUG)
        
        # Connect to GPS
        success = self.gps.connect(settings)
        
        # Reset logging level
        logging.getLogger("GPSReceiver").setLevel(old_level)
        
        if success:
            self.root.title("ZED Camera Capture Tool")
            
            # Initialize capture controller if not already and camera is connected
            if not self.capture_controller and self.camera.is_connected:
                self.capture_controller = CaptureController(self.camera, self.gps, settings)
                
            # Update GPS status labels
            self.gps_status_labels["gps_connection_status"].config(text="Connected")
            self.gps_status_labels["gps_connection_status"].config(foreground="green")
            
            # Update UI
            self.gps_connect_button.state(['disabled'])
            self.gps_disconnect_button.state(['!disabled'])
            self.gps_test_button.state(['!disabled'])
            
            # Start GPS monitoring
            self.start_gps_monitoring()
            
            return True
        else:
            self.root.title("ZED Camera Capture Tool")
            self.gps_status_labels["gps_connection_status"].config(text="Connection Failed")
            self.gps_status_labels["gps_connection_status"].config(foreground="red")
            
            messagebox.showerror("Connection Error", 
                            "Failed to connect to GPS on " + settings["gps"]["port"] + 
                            ". Please check connections and port settings.")
            return False

    def on_gps_disconnect_clicked(self):
        """Disconnect from GPS receiver from GPS tab"""
        # Stop capture if running in GPS mode
        if (self.capture_controller and 
            self.capture_controller.is_capturing and 
            self.settings["capture_mode"] == "gps"):
            self.capture_controller.stop_capture()
            
        # Stop GPS monitoring
        self.stop_gps_monitoring()
        
        # Disconnect GPS
        self.gps.disconnect()
        
        # Update GPS status labels
        self.gps_status_labels["gps_connection_status"].config(text="Disconnected")
        self.gps_status_labels["gps_connection_status"].config(foreground="")
        
        # Reset other status labels
        for key in ["gps_fix_type", "gps_satellites", "gps_latitude", "gps_longitude", 
                "gps_altitude", "gps_speed", "gps_time"]:
            self.gps_status_labels[key].config(text="N/A")
        
        # Update UI
        self.gps_connect_button.state(['!disabled'])
        self.gps_disconnect_button.state(['disabled'])
        self.gps_test_button.state(['disabled'])

    def on_test_gps_clicked(self):
        """Test GPS connection and show detailed information"""
        if not self.gps.is_connected:
            messagebox.showerror("Error", "GPS not connected")
            return
            
        # Read several NMEA sentences
        try:
            raw_data = []
            if self.gps.serial_port and self.gps.serial_port.is_open:
                self.nmea_text.insert(tk.END, "--- Testing GPS Connection ---\n")
                
                timeout = time.time() + 5  # 5 second timeout
                while time.time() < timeout and len(raw_data) < 10:
                    if self.gps.serial_port.in_waiting:
                        line = self.gps.serial_port.readline().decode('ascii', errors='replace').strip()
                        if line:
                            raw_data.append(line)
                            self.nmea_text.insert(tk.END, line + "\n")
                            self.nmea_text.see(tk.END)
                            self.root.update()
                    time.sleep(0.1)
                    
                if not raw_data:
                    self.nmea_text.insert(tk.END, "No data received from GPS. Check connections.\n")
                else:
                    self.nmea_text.insert(tk.END, f"Received {len(raw_data)} NMEA sentences.\n")
                    
                self.nmea_text.insert(tk.END, "--- Test Complete ---\n\n")
                self.nmea_text.see(tk.END)
        except Exception as e:
            self.nmea_text.insert(tk.END, f"Error testing GPS: {e}\n")
            self.logger.error(f"Error testing GPS: {e}")

    def start_gps_monitoring(self):
        """Start monitoring GPS data updates"""
        if not hasattr(self, 'gps_monitor_running'):
            self.gps_monitor_running = True
            self.update_gps_status()
            
    def stop_gps_monitoring(self):
        """Stop GPS monitoring"""
        self.gps_monitor_running = False
        
    def update_gps_status(self):
        """Update GPS status display with latest data"""
        if not self.gps_monitor_running:
            return
            
        if self.gps.is_connected:
            try:
                # Get current GPS data
                gps_data = self.gps.get_current_data()
                
                # Update fix type
                if self.gps.has_fix():
                    fix_type = "3D Fix" if gps_data["altitude"] is not None else "2D Fix"
                    self.gps_status_labels["gps_fix_type"].config(text=fix_type)
                    self.gps_status_labels["gps_fix_type"].config(foreground="green")
                else:
                    self.gps_status_labels["gps_fix_type"].config(text="No Fix")
                    self.gps_status_labels["gps_fix_type"].config(foreground="red")
                    
                # Update satellite count
                sat_count = gps_data["satellites"] if gps_data["satellites"] is not None else "0"
                self.gps_status_labels["gps_satellites"].config(text=str(sat_count))
                
                # Update coordinates if available
                if gps_data["latitude"] is not None and gps_data["longitude"] is not None:
                    lat = f"{gps_data['latitude']:.6f}° N" if gps_data['latitude'] >= 0 else f"{-gps_data['latitude']:.6f}° S"
                    lon = f"{gps_data['longitude']:.6f}° E" if gps_data['longitude'] >= 0 else f"{-gps_data['longitude']:.6f}° W"
                    
                    self.gps_status_labels["gps_latitude"].config(text=lat)
                    self.gps_status_labels["gps_longitude"].config(text=lon)
                else:
                    self.gps_status_labels["gps_latitude"].config(text="N/A")
                    self.gps_status_labels["gps_longitude"].config(text="N/A")
                    
                # Update altitude if available
                if gps_data["altitude"] is not None:
                    self.gps_status_labels["gps_altitude"].config(text=f"{gps_data['altitude']:.1f} m")
                else:
                    self.gps_status_labels["gps_altitude"].config(text="N/A")
                    
                # Update speed if available
                if gps_data["speed"] is not None:
                    self.gps_status_labels["gps_speed"].config(text=f"{gps_data['speed']:.1f} km/h")
                else:
                    self.gps_status_labels["gps_speed"].config(text="N/A")
                    
                # Update time if available
                if gps_data["timestamp"] is not None:
                    self.gps_status_labels["gps_time"].config(text=gps_data["timestamp"])
                else:
                    self.gps_status_labels["gps_time"].config(text="N/A")
                    
                # Add NMEA data if new data is available
                if hasattr(self.gps, 'last_raw_nmea') and self.gps.last_raw_nmea:
                    self.nmea_text.insert(tk.END, self.gps.last_raw_nmea + "\n")
                    self.nmea_text.see(tk.END)
                    
                    # Keep text widget from growing too large
                    if float(self.nmea_text.index('end-1c').split('.')[0]) > 100:
                        self.nmea_text.delete(1.0, "end-100c")
                        
            except Exception as e:
                self.logger.error(f"Error updating GPS status: {e}")
                
        # Schedule next update
        if self.gps_monitor_running:
            self.root.after(1000, self.update_gps_status)  # Update every second