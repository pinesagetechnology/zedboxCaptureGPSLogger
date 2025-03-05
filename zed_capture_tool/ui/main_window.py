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
        self.root.geometry("2400x2100")  # Example large size
        
        # Set up logging
        self.logger = logging.getLogger("MainWindow")
        
        # Load settings
        self.settings = load_settings()
        
        # Initialize modules
        self.camera = ZedCamera()
        self.gps = GPSReceiver()
        self.capture_controller = None  # Created after we connect devices
        
        # Variables for UI
        self.capture_mode_var = StringVar(value=self.settings["capture_mode"])
        self.time_interval_var = IntVar(value=self.settings["time_interval"])
        self.gps_interval_var = DoubleVar(value=self.settings["gps_interval"])
        self.output_dir_var = StringVar(value=self.settings["output_directory"])
        self.camera_mode_var = StringVar(value=self.settings["camera"]["mode"])
        self.resolution_var = StringVar(value=self.settings["camera"]["resolution"])
        self.fps_var = IntVar(value=self.settings["camera"]["fps"])
        
        # GPS port
        self.gps_port_var = StringVar(value=self.settings["gps"]["port"])
        
        # Camera setting variables
        self.camera_settings_vars = {}
        for name in ["brightness", "contrast", "hue", "saturation", "exposure", "gain", "whitebalance"]:
            self.camera_settings_vars[name] = {
                "value": IntVar(value=self.settings["camera"][name]),
                "auto": BooleanVar(value=(self.settings["camera"][name] == -1))
            }
        
        # UI setup
        self.setup_ui()
        
        # Status variables
        self.is_capturing = False
        self.capture_count = 0
        
        # Timer for UI updates
        self.update_ui()
        
        # Attempt to connect to camera & GPS on startup
        self.connect_devices()

    def setup_ui(self):
        """Top-level UI layout"""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tabs:
        self.capture_tab = ttk.Frame(self.notebook)
        self.video_tab   = ttk.Frame(self.notebook)
        self.gps_tab     = ttk.Frame(self.notebook)
        self.settings_tab= ttk.Frame(self.notebook)
        
        self.notebook.add(self.capture_tab,   text="Photo Capture")
        self.notebook.add(self.video_tab,     text="Video Recording")
        self.notebook.add(self.gps_tab,       text="GPS Monitor")
        self.notebook.add(self.settings_tab,  text="Settings")
        
        # Set up each tab
        self.setup_capture_tab()
        self.setup_video_tab()
        self.setup_gps_tab()
        self.setup_settings_tab()
        
        # Status bar at the bottom
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
        """Photo capture UI, including preview frames."""
        preview_frame = ttk.LabelFrame(self.capture_tab, text="Camera Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        views_frame = ttk.Frame(preview_frame)
        views_frame.pack(padx=10, pady=10)
        
        # We'll hold references to the label widgets in a dict
        self.preview_labels = {}
        
        # Dimensions for each preview
        preview_width = 320
        preview_height = 240
        
        # Make frames for each type of preview (RGB, Depth, etc.)
        # 1) RGB
        rgb_frame = ttk.LabelFrame(views_frame, text="RGB View")
        rgb_frame.grid(row=0, column=0, padx=5, pady=5)
        
        rgb_canvas = tk.Canvas(rgb_frame, width=preview_width, height=preview_height, bg="#222222")
        rgb_canvas.pack()
        
        self.preview_labels["rgb"] = tk.Label(rgb_canvas, text="No RGB preview", bg="#222222", fg="white")
        self.preview_labels["rgb"].place(x=preview_width//2, y=preview_height//2, anchor="center")
        
        # 2) Depth
        depth_frame = ttk.LabelFrame(views_frame, text="Depth Map")
        depth_frame.grid(row=0, column=1, padx=5, pady=5)
        
        depth_canvas = tk.Canvas(depth_frame, width=preview_width, height=preview_height, bg="#222222")
        depth_canvas.pack()
        
        self.preview_labels["depth"] = tk.Label(depth_canvas, text="No depth preview", bg="#222222", fg="white")
        self.preview_labels["depth"].place(x=preview_width//2, y=preview_height//2, anchor="center")
        
        # 3) Disparity or Confidence
        third_frame = ttk.LabelFrame(views_frame, text="Additional View")
        third_frame.grid(row=0, column=2, padx=5, pady=5)
        
        third_canvas = tk.Canvas(third_frame, width=preview_width, height=preview_height, bg="#222222")
        third_canvas.pack()
        
        self.preview_labels["disparity"] = tk.Label(third_canvas, text="No additional view", bg="#222222", fg="white")
        self.preview_labels["disparity"].place(x=preview_width//2, y=preview_height//2, anchor="center")
        
        # Also store the preview dimensions so we can reference them in update_preview()
        self.preview_dimensions = {
            "width": preview_width,
            "height": preview_height
        }
        
        # Checkboxes for which views to capture
        view_select_frame = ttk.Frame(preview_frame)
        view_select_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(view_select_frame, text="Views to Capture:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        self.view_vars = {}
        self.view_checkbuttons = {}  # This is the missing dictionary

        # Create checkbox for "RGB" view (always shown)
        self.view_vars["rgb"] = tk.BooleanVar(value=True)
        self.view_checkbuttons["rgb"] = ttk.Checkbutton(view_select_frame, text="RGB", variable=self.view_vars["rgb"])
        self.view_checkbuttons["rgb"].grid(row=0, column=1, padx=5)
        
        # Create checkboxes for additional views ("depth", "disparity", "confidence")
        view_names = ["depth", "disparity", "confidence"]
        for i, view_name in enumerate(view_names, start=2):
            self.view_vars[view_name] = tk.BooleanVar(value=False)
            self.view_checkbuttons[view_name] = ttk.Checkbutton(view_select_frame, text=view_name.title(), variable=self.view_vars[view_name])
            # Initially, hide these checkboxes until the camera connects and you decide to show them:
            self.view_checkbuttons[view_name].grid(row=0, column=i, padx=5)
            self.view_checkbuttons[view_name].grid_remove()
        
        # Capture controls
        control_frame = ttk.LabelFrame(self.capture_tab, text="Capture Controls")
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Radio buttons for "time" vs "gps" mode
        mode_frame = ttk.Frame(control_frame)
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        
        time_radio = ttk.Radiobutton(mode_frame,
                                     text="Time Interval:",
                                     variable=self.capture_mode_var,
                                     value="time",
                                     command=self.on_capture_mode_changed)
        time_radio.grid(row=0, column=0, sticky=tk.W)
        
        time_spin = ttk.Spinbox(mode_frame, from_=1, to=3600, width=10, textvariable=self.time_interval_var)
        time_spin.grid(row=0, column=1, padx=5)
        ttk.Label(mode_frame, text="seconds").grid(row=0, column=2, sticky=tk.W)
        
        gps_radio = ttk.Radiobutton(mode_frame,
                                    text="GPS Distance:",
                                    variable=self.capture_mode_var,
                                    value="gps",
                                    command=self.on_capture_mode_changed)
        gps_radio.grid(row=0, column=3, sticky=tk.W, padx=(20, 0))
        
        gps_spin = ttk.Spinbox(mode_frame, from_=1, to=1000, width=10, textvariable=self.gps_interval_var)
        gps_spin.grid(row=0, column=4, padx=5)
        ttk.Label(mode_frame, text="meters").grid(row=0, column=5, sticky=tk.W)
        
        # Output directory
        dir_frame = ttk.Frame(control_frame)
        dir_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(dir_frame, text="Output directory:").grid(row=0, column=0, sticky=tk.W)
        dir_entry = ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=50)
        dir_entry.grid(row=0, column=1, padx=5, sticky=tk.W + tk.E)
        
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
        self.stop_button.state(['disabled'])
        
        self.single_capture_button = ttk.Button(button_frame, text="Single Capture",
                                                command=self.on_single_capture_clicked)
        self.single_capture_button.pack(side=tk.LEFT, padx=5)
        self.single_capture_button.state(['disabled'])
    
    def setup_video_tab(self):
        """Set up the video recording UI."""
        control_frame = ttk.LabelFrame(self.video_tab, text="Video Recording")
        control_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Same output directory
        dir_frame = ttk.Frame(control_frame)
        dir_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(dir_frame, text="Output directory:").grid(row=0, column=0, sticky=tk.W)
        dir_entry = ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=50)
        dir_entry.grid(row=0, column=1, padx=5, sticky=tk.W + tk.E)
        browse_button = ttk.Button(dir_frame, text="Browse...", command=self.on_browse_clicked)
        browse_button.grid(row=0, column=2, padx=5)
        dir_frame.columnconfigure(1, weight=1)
        
        # Video settings
        settings_frame = ttk.Frame(control_frame)
        settings_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(settings_frame, text="Codec:").grid(row=0, column=0, sticky=tk.W)
        self.codec_var = StringVar(value="H264")
        codec_combo = ttk.Combobox(settings_frame,
                                   textvariable=self.codec_var,
                                   values=["H264", "H265"],
                                   state="readonly",
                                   width=10)
        codec_combo.grid(row=0, column=1, padx=5, sticky=tk.W)
        
        ttk.Label(settings_frame, text="Bitrate (Kbps):").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        self.bitrate_var = IntVar(value=8000)
        bitrate_spin = ttk.Spinbox(settings_frame, from_=1000, to=50000, increment=1000,
                                   textvariable=self.bitrate_var, width=8)
        bitrate_spin.grid(row=0, column=3, padx=5, sticky=tk.W)
        
        # Duration limit
        ttk.Label(settings_frame, text="Duration limit (sec):").grid(row=1, column=0, sticky=tk.W, pady=(10,0))
        self.duration_limit_var = IntVar(value=0)
        duration_spin = ttk.Spinbox(settings_frame, from_=0, to=3600, increment=10,
                                    textvariable=self.duration_limit_var, width=8)
        duration_spin.grid(row=1, column=1, padx=5, sticky=tk.W, pady=(10,0))
        ttk.Label(settings_frame, text="(0 = no limit)").grid(row=1, column=2, sticky=tk.W, pady=(10,0))
        
        # Record buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.start_record_button = ttk.Button(button_frame, text="Start Recording",
                                              command=self.on_start_recording_clicked)
        self.start_record_button.pack(side=tk.LEFT, padx=5)
        self.start_record_button.state(['disabled'])
        
        self.stop_record_button = ttk.Button(button_frame, text="Stop Recording",
                                             command=self.on_stop_recording_clicked)
        self.stop_record_button.pack(side=tk.LEFT, padx=5)
        self.stop_record_button.state(['disabled'])
        
        # Recording status info
        status_frame = ttk.LabelFrame(self.video_tab, text="Recording Status")
        status_frame.pack(fill=tk.X, padx=10, pady=10)
        
        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(status_grid, text="Status:").grid(row=0, column=0, sticky=tk.W)
        self.recording_status_label = ttk.Label(status_grid, text="Not recording")
        self.recording_status_label.grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(status_grid, text="Duration:").grid(row=1, column=0, sticky=tk.W)
        self.recording_duration_label = ttk.Label(status_grid, text="0 seconds")
        self.recording_duration_label.grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(status_grid, text="Output file:").grid(row=2, column=0, sticky=tk.W)
        self.recording_file_label = ttk.Label(status_grid, text="None")
        self.recording_file_label.grid(row=2, column=1, sticky=tk.W)
        
        # List of videos
        list_frame = ttk.LabelFrame(self.video_tab, text="Recorded Videos")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.video_listbox = tk.Listbox(list_container)
        self.video_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.video_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.video_listbox.config(yscrollcommand=scrollbar.set)
        
        refresh_button = ttk.Button(list_frame, text="Refresh List", command=self.refresh_video_list)
        refresh_button.pack(side=tk.LEFT, padx=5, pady=5)

    def setup_gps_tab(self):
        """A dedicated tab for GPS status and data."""
        # Overall status
        status_frame = ttk.LabelFrame(self.gps_tab, text="GPS Status")
        status_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # We'll show multiple fields in a grid
        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # We'll keep them in a dictionary for easy reference
        self.gps_status_labels = {}
        
        info_items = [
            ("gps_connection_status", "Connection:", "Disconnected"),
            ("gps_fix_type",         "Fix Type:",    "N/A"),
            ("gps_satellites",       "Satellites:",  "N/A"),
            ("gps_latitude",         "Latitude:",    "N/A"),
            ("gps_longitude",        "Longitude:",   "N/A"),
            ("gps_altitude",         "Altitude:",    "N/A"),
            ("gps_speed",            "Speed:",       "N/A"),
            ("gps_time",             "Time:",        "N/A")
        ]
        
        for i, (key, labeltext, default_value) in enumerate(info_items):
            row = i // 2
            col = (i % 2)*2
            ttk.Label(status_grid, text=labeltext).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            lab = ttk.Label(status_grid, text=default_value)
            lab.grid(row=row, column=col+1, sticky=tk.W, padx=5, pady=2)
            self.gps_status_labels[key] = lab
        
        # Add a variable for baud rate and default it to 4800
        self.gps_baud_rate_var = tk.IntVar(value=4800)
        
        # GPS Control frame
        control_frame = ttk.LabelFrame(self.gps_tab, text="GPS Control")
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Port frame
        port_frame = ttk.Frame(control_frame)
        port_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(port_frame, text="Port:").grid(row=0, column=0, sticky=tk.W)
        port_entry = ttk.Entry(port_frame, textvariable=self.gps_port_var, width=20)
        port_entry.grid(row=0, column=1, padx=5, sticky=tk.W)
        
        # Baud rate dropdown
        ttk.Label(port_frame, text="Baud:").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        baud_combo = ttk.Combobox(
            port_frame,
            textvariable=self.gps_baud_rate_var,
            values=[4800, 9600, 19200, 38400, 57600, 115200],
            state="readonly",
            width=10
        )
        baud_combo.grid(row=0, column=3, padx=5, sticky=tk.W)
        
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.gps_connect_button = ttk.Button(button_frame, text="Connect GPS",
                                             command=self.on_connect_gps_clicked)
        self.gps_connect_button.pack(side=tk.LEFT, padx=5)
        
        self.gps_disconnect_button = ttk.Button(button_frame, text="Disconnect GPS",
                                                command=self.on_disconnect_gps_clicked)
        self.gps_disconnect_button.pack(side=tk.LEFT, padx=5)
        self.gps_disconnect_button.state(['disabled'])
        
        self.gps_test_button = ttk.Button(button_frame, text="Test GPS",
                                          command=self.on_test_gps_clicked)
        self.gps_test_button.pack(side=tk.LEFT, padx=5)
        self.gps_test_button.state(['disabled'])
        
        # NMEA text display
        nmea_frame = ttk.LabelFrame(self.gps_tab, text="NMEA Data")
        nmea_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        nmea_container = ttk.Frame(nmea_frame)
        nmea_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.nmea_text = tk.Text(nmea_container, height=12, width=80)
        self.nmea_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        sb = ttk.Scrollbar(nmea_container, orient="vertical", command=self.nmea_text.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.nmea_text.config(yscrollcommand=sb.set)
        
        # Clear log
        button_clear = ttk.Button(nmea_frame, text="Clear",
                                  command=lambda: self.nmea_text.delete("1.0", tk.END))
        button_clear.pack(side=tk.RIGHT, padx=5, pady=5)
        
    def setup_settings_tab(self):
        """Camera + GPS settings (sliders, etc.)."""
        settings_notebook = ttk.Notebook(self.settings_tab)
        settings_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Camera tab
        camera_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(camera_tab, text="Camera")
        
        # Camera Mode
        mode_frame = ttk.Frame(camera_tab)
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(mode_frame, text="Camera Mode:").grid(row=0, column=0, sticky=tk.W)
        mode_combo = ttk.Combobox(mode_frame,
                                  textvariable=self.camera_mode_var,
                                  values=["auto", "manual"],
                                  state="readonly",
                                  width=15)
        mode_combo.grid(row=0, column=1, padx=5, sticky=tk.W)
        mode_combo.bind("<<ComboboxSelected>>", self.on_camera_mode_changed)
        
        # Resolution & FPS
        res_frame = ttk.Frame(camera_tab)
        res_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(res_frame, text="Resolution:").grid(row=0, column=0, sticky=tk.W)
        res_combo = ttk.Combobox(res_frame,
                                 textvariable=self.resolution_var,
                                 values=["HD2K", "HD1080", "HD720", "VGA"],
                                 state="readonly",
                                 width=15)
        res_combo.grid(row=0, column=1, padx=5, sticky=tk.W)
        
        ttk.Label(res_frame, text="FPS:").grid(row=0, column=2, sticky=tk.W, padx=(20,0))
        fps_combo = ttk.Combobox(res_frame,
                                 textvariable=self.fps_var,
                                 values=[15, 30, 60, 100],
                                 state="readonly",
                                 width=15)
        fps_combo.grid(row=0, column=3, padx=5, sticky=tk.W)
        
        # Sliders for brightness/contrast/hue/etc.
        sliders_frame = ttk.Frame(camera_tab)
        sliders_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.camera_setting_widgets = {}
        
        # (setting_key, label, min, max, is_auto_capable)
        camera_settings_info = [
            ("brightness",   "Brightness",   0, 8,   False),
            ("contrast",     "Contrast",     0, 8,   False),
            ("hue",          "Hue",          0, 11,  False),
            ("saturation",   "Saturation",   0, 8,   False),
            ("exposure",     "Exposure",     0, 100, True),
            ("gain",         "Gain",         0, 100, True),
            ("whitebalance", "WhiteBalance", 0, 6500,True),
        ]
        
        for idx, (key, label, minval, maxval, auto_opt) in enumerate(camera_settings_info):
            lf = ttk.LabelFrame(sliders_frame, text=label)
            lf.grid(row=idx//2, column=idx%2, padx=10, pady=5, sticky=tk.W+tk.E)
            
            auto_chk = None
            if auto_opt:
                # "Auto" checkbox
                auto_chk = ttk.Checkbutton(lf,
                                           text="Auto",
                                           variable=self.camera_settings_vars[key]["auto"],
                                           command=lambda k=key: self.on_auto_checkbox_changed(k))
                auto_chk.pack(anchor=tk.W, padx=5, pady=2)
            
            scale = ttk.Scale(lf,
                              from_=minval,
                              to=maxval,
                              orient=tk.HORIZONTAL,
                              variable=self.camera_settings_vars[key]["value"],
                              command=lambda val, k=key: self.on_scale_value_changed(k, val))
            scale.pack(fill=tk.X, padx=5, pady=5)
            
            val_label = ttk.Label(lf, text=str(self.camera_settings_vars[key]["value"].get()))
            val_label.pack(anchor=tk.E, padx=5, pady=2)
            
            self.camera_setting_widgets[key] = {
                "scale": scale,
                "label": val_label,
                "auto": auto_chk
            }
            
            # If auto is on, disable the slider
            if auto_opt and self.camera_settings_vars[key]["auto"].get():
                scale.state(['disabled'])
        
        # Connect/Disconnect camera from this tab
        cam_button_frame = ttk.Frame(camera_tab)
        cam_button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.connect_camera_button = ttk.Button(cam_button_frame, text="Connect Camera",
                                                command=self.on_connect_camera_clicked)
        self.connect_camera_button.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_camera_button = ttk.Button(cam_button_frame, text="Disconnect Camera",
                                                   command=self.on_disconnect_camera_clicked)
        self.disconnect_camera_button.pack(side=tk.LEFT, padx=5)
        self.disconnect_camera_button.state(['disabled'])
        
        # GPS sub-tab
        gps_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(gps_tab, text="GPS")
        
        # Just a minimal note: you can keep it blank if you prefer the full GPS panel in the “GPS Monitor” tab.

        # Save settings button
        save_frame = ttk.Frame(self.settings_tab)
        save_frame.pack(fill=tk.X, padx=10, pady=10)
        
        save_btn = ttk.Button(save_frame, text="Save Settings",
                              command=self.on_save_settings_clicked)
        save_btn.pack(side=tk.RIGHT, padx=5)

    # ----------------- Device Connection on Startup -----------------
    
    def connect_devices(self):
        """Try connecting camera and GPS automatically at startup."""
        if self.on_connect_camera_clicked():
            self.logger.info("Successfully connected to ZED camera on startup.")
        if self.on_connect_gps_clicked():
            self.logger.info("Successfully connected to GPS on startup.")

    # ----------------- UI Updater -----------------
    
    def update_ui(self):
        """Periodic UI refresh for statuses, every ~500ms."""
        try:
            # Camera status
            if self.camera.is_connected:
                self.camera_status_label.config(text="Camera: Connected")
                self.connect_camera_button.state(['disabled'])
                self.disconnect_camera_button.state(['!disabled'])
                self.start_button.state(['!disabled'])
                self.single_capture_button.state(['!disabled'])
                
                # Video
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
                
                if hasattr(self, 'start_record_button'):
                    self.start_record_button.state(['disabled'])
            
            # GPS status
            if self.gps.is_connected:
                gps_data = self.gps.get_current_data()
                fix_status = "Fix" if self.gps.has_fix() else "No Fix"
                sats = gps_data["satellites"] if gps_data.get("satellites") else "?"
                self.gps_status_label.config(text=f"GPS: Connected ({fix_status}, Sats: {sats})")
                self.gps_connect_button.state(['disabled'])
                self.gps_disconnect_button.state(['!disabled'])
                self.gps_test_button.state(['!disabled'])
                
                # Update detailed GPS info in the GPS tab
                self.update_gps_details()
            else:
                self.gps_status_label.config(text="GPS: Disconnected")
                self.gps_connect_button.state(['!disabled'])
                self.gps_disconnect_button.state(['disabled'])
                self.gps_test_button.state(['disabled'])
            
            # If capture is running
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
            
            # Video status
            if hasattr(self, 'video_recorder'):
                if self.video_recorder.is_recording:
                    status = self.video_recorder.get_recording_status()
                    self.recording_status_label.config(text="Recording")
                    self.recording_duration_label.config(text=f"{status['duration']:.1f} seconds")
                    
                    if status["file_path"]:
                        self.recording_file_label.config(text=os.path.basename(status["file_path"]))
                    
                    if hasattr(self, 'start_record_button'):
                        self.start_record_button.state(['disabled'])
                        self.stop_record_button.state(['!disabled'])
                    
        except Exception as e:
            self.logger.error(f"Error updating UI: {e}")
        
        self.root.after(500, self.update_ui)

    # ----------------- Camera Connect/Disconnect -----------------
    
    def on_connect_camera_clicked(self):
        """Connect to the ZED camera using current settings."""
        settings = self.update_settings_from_ui()
        
        self.root.title("ZED Camera Capture Tool - Connecting to camera...")
        self.root.update()
        
        success = self.camera.connect(settings)
        
        self.root.title("ZED Camera Capture Tool")
        if success:
            if not self.capture_controller:
                self.capture_controller = CaptureController(self.camera, self.gps, settings)
            
            # Show available view types in the UI
            self.update_view_ui_for_available_types()
            # Start the live preview
            self.update_preview()
            
            return True
        else:
            messagebox.showerror("Connection Error",
                                 "Failed to connect to ZED camera.\nCheck connections and settings.")
            return False

    def on_disconnect_camera_clicked(self):
        """Disconnect the camera."""
        if self.capture_controller and self.capture_controller.is_capturing:
            self.capture_controller.stop_capture()
        
        # Clear any displayed preview
        if "rgb" in self.preview_labels:
            self.preview_labels["rgb"].config(image=None, text="No RGB preview")
        if "depth" in self.preview_labels:
            self.preview_labels["depth"].config(image=None, text="No depth preview")
        if "disparity" in self.preview_labels:
            self.preview_labels["disparity"].config(image=None, text="No additional view")
        
        self.camera.disconnect()

    # ----------------- GPS Connect/Disconnect -----------------
    
    def on_connect_gps_clicked(self):
        """Connect to GPS using current settings."""
        settings = self.update_settings_from_ui()
        
        # Override the baud rate with the user’s selection
        settings["gps"]["baud_rate"] = self.gps_baud_rate_var.get()

        self.root.title("ZED Camera Capture Tool - Connecting to GPS...")
        self.root.update()
        
        # Show status in the detailed label
        self.gps_status_labels["gps_connection_status"].config(text="Connecting...", foreground="orange")
        
        # Temporarily set debug to see GPS parse logs
        old_level = logging.getLogger("GPSReceiver").level
        logging.getLogger("GPSReceiver").setLevel(logging.DEBUG)
        
        success = self.gps.connect(settings)
        
        # Restore logging level
        logging.getLogger("GPSReceiver").setLevel(old_level)
        
        self.root.title("ZED Camera Capture Tool")
        if success:
            self.gps_status_labels["gps_connection_status"].config(text="Connected", foreground="green")
            if not self.capture_controller and self.camera.is_connected:
                self.capture_controller = CaptureController(self.camera, self.gps, settings)
            
            return True
        else:
            self.gps_status_labels["gps_connection_status"].config(text="Connection Failed", foreground="red")
            messagebox.showerror("Connection Error",
                                 f"Failed to connect to GPS on port {settings['gps']['port']}.")
            return False
    
    def on_disconnect_gps_clicked(self):
        """Disconnect from the GPS device."""
        if (self.capture_controller and
            self.capture_controller.is_capturing and
            self.settings["capture_mode"] == "gps"):
            self.capture_controller.stop_capture()
        
        self.gps.disconnect()
        
        self.gps_status_labels["gps_connection_status"].config(text="Disconnected", foreground="")
        for key in ["gps_fix_type", "gps_satellites", "gps_latitude", "gps_longitude",
                    "gps_altitude", "gps_speed", "gps_time"]:
            self.gps_status_labels[key].config(text="N/A")
    
    def on_test_gps_clicked(self):
        """Manually read a few lines from the GPS and display them."""
        if not self.gps.is_connected:
            messagebox.showerror("Error", "GPS not connected")
            return
        
        # Clear the text widget or append a header
        self.nmea_text.insert(tk.END, "--- Last 5 NMEA Sentences ---\n")
        self.nmea_text.see(tk.END)
        
        # We attempt to read e.g. 10 lines or until 5 seconds passes
        count = 0
        # Retrieve and display the stored sentences
        for sentence in self.gps.last_nmea_sentences:
            self.nmea_text.insert(tk.END, sentence + "\n")
            count += 1
        
        self.nmea_text.insert(tk.END, "--- End of Test ---\n\n")
        self.nmea_text.see(tk.END)
        
        if count == 0:
            self.nmea_text.insert(tk.END, "No data received.\n")
        else 
            # Retrieve the latest parsed data from the GPSReceiver
            data = self.gps.current_data
            output = []
            output.append("--- User Friendly GPS Data ---")
            # Fix Quality
            fix_quality = data.get("fix_quality")
            if fix_quality is None or fix_quality == 0:
                fix_type = "No Fix"
            elif fix_quality == 1:
                fix_type = "GPS Fix"
            elif fix_quality == 2:
                fix_type = "DGPS Fix"
            else:
                fix_type = str(fix_quality)
            output.append(f"Fix Quality: {fix_type}")

            # Satellites
            satellites = data.get("satellites")
            output.append(f"Satellites: {satellites if satellites is not None else 'N/A'}")

            # Coordinates
            lat = data.get("latitude")
            lon = data.get("longitude")
            if lat is not None and lon is not None:
                dms_lat = format_coordinate(lat, is_lat=True)
                dms_lon = format_coordinate(lon, is_lat=False)
                output.append(f"Position: {dms_lat}, {dms_lon}")
                output.append(f"Google Maps: https://maps.google.com/?q={lat},{lon}")
            else:
                output.append("Position: N/A")

            # Altitude
            altitude = data.get("altitude")
            output.append(f"Altitude: {altitude} m" if altitude is not None else "Altitude: N/A")

            # Speed
            speed = data.get("speed")
            output.append(f"Speed: {speed} km/h" if speed is not None else "Speed: N/A")

            # Timestamp
            timestamp = data.get("timestamp")
            output.append(f"GPS Time: {timestamp}" if timestamp is not None else "GPS Time: N/A")

            for userfriendlyData in output:
                self.nmea_text.insert(tk.END, userfriendlyData + "\n")

        self.nmea_text.insert(tk.END, "--- Test Complete ---\n\n")
        self.nmea_text.see(tk.END)

    # ----------------- Capture (Time/GPS/Single) -----------------
    
    def on_start_capture_clicked(self):
        """Start auto-capturing according to time or GPS distance."""
        if not self.camera.is_connected:
            messagebox.showerror("Error", "Camera not connected")
            return
        
        if self.capture_mode_var.get() == "gps" and not self.gps.is_connected:
            messagebox.showerror("Error", "GPS not connected (required for GPS mode).")
            return
        
        settings = self.update_settings_from_ui()
        if not self.capture_controller:
            self.capture_controller = CaptureController(self.camera, self.gps, settings)
        
        success = self.capture_controller.start_capture(settings)
        if success:
            self.root.title(f"ZED Camera Capture Tool - Capturing ({settings['capture_mode']} mode)")
        else:
            messagebox.showerror("Error", "Failed to start capture")

    def on_stop_capture_clicked(self):
        if self.capture_controller:
            self.capture_controller.stop_capture()
            self.root.title("ZED Camera Capture Tool")

    def on_single_capture_clicked(self):
        """Grab one set of images right now."""
        if not self.camera.is_connected:
            messagebox.showerror("Error", "Camera not connected")
            return
        
        settings = self.update_settings_from_ui()
        if not self.capture_controller:
            self.capture_controller = CaptureController(self.camera, self.gps, settings)
        
        view_types = self.get_selected_view_types()
        if not view_types:
            messagebox.showerror("Error", "No view types selected for capture")
            return
        
        output_dir = settings["output_directory"]
        success = self.capture_controller._capture_image(output_dir, view_types=view_types)
        # The _capture_image is an internal method, so rely carefully. 
        # In a production code, you'd expose a single-capture method more gracefully.
        
        if success:
            self.capture_count_label.config(text=f"Images: {self.capture_controller.capture_count}")
        else:
            messagebox.showerror("Error", "Failed to capture image")

    def get_selected_view_types(self):
        """Return which views have been checkboxed by the user."""
        result = []
        for vtype, var in self.view_vars.items():
            if var.get():
                result.append(vtype)
        # If none selected, default to rgb
        if not result:
            result = ["rgb"]
        
        # Filter out any that the ZED SDK does not actually support
        if self.camera.is_connected:
            available = self.camera.get_available_view_types()
            result = [r for r in result if r in available]
        
        return result

    def on_capture_mode_changed(self):
        """Time vs GPS radio changed."""
        self.settings["capture_mode"] = self.capture_mode_var.get()

    def on_browse_clicked(self):
        """Pick an output directory."""
        current_dir = self.output_dir_var.get()
        directory = filedialog.askdirectory(initialdir=current_dir,
                                            title="Select Output Directory")
        if directory:
            self.output_dir_var.set(directory)

    # ----------------- Preview -----------------
    
    def update_preview(self):
        """Continuously fetch frames from the ZED and display them."""
        if not self.camera.is_connected:
            return
        
        try:
            # Decide which views to request from the camera
            # (At least "rgb", plus depth or disparity if available)
            available = self.camera.get_available_view_types()
            views_to_display = ["rgb"]
            if "depth" in available:
                views_to_display.append("depth")
            # If "disparity" is not in the SDK, we might use "confidence" instead
            if "disparity" in available:
                views_to_display.append("disparity")
            elif "confidence" in available:
                views_to_display.append("confidence")
            
            frames = self.camera.get_current_frame(views_to_display)
            if not frames:
                return
            
            import numpy as np
            
            # We store references to ImageTk objects so they don't get GC'd
            if not hasattr(self, 'photo_images'):
                self.photo_images = {}
            
            w = self.preview_dimensions["width"]
            h = self.preview_dimensions["height"]
            
            for vtype, img_data in frames.items():
                if img_data is None:
                    continue
                if vtype not in self.preview_labels:
                    continue
                
                # Convert from BGR to something displayable
                if vtype == "rgb":
                    image_rgb = cv2.cvtColor(img_data, cv2.COLOR_BGR2RGB)
                elif vtype in ["depth", "disparity", "confidence"]:
                    # Normalize for visualization
                    normed = cv2.normalize(img_data, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                    colorized = cv2.applyColorMap(normed, cv2.COLORMAP_JET)
                    image_rgb = cv2.cvtColor(colorized, cv2.COLOR_BGR2RGB)
                else:
                    # Fallback
                    image_rgb = cv2.cvtColor(img_data, cv2.COLOR_BGR2RGB)
                
                resized = cv2.resize(image_rgb, (w, h))
                pil_img = Image.fromarray(resized)
                self.photo_images[vtype] = ImageTk.PhotoImage(image=pil_img)
                
                # If we got "confidence" but the label is "disparity", map it
                label_key = vtype
                if vtype == "confidence" and "disparity" in self.preview_labels:
                    label_key = "disparity"
                
                self.preview_labels[label_key].config(image=self.photo_images[vtype], text="")
                
        except Exception as e:
            self.logger.error(f"Error updating preview: {e}")
        
        # Schedule next update
        if self.camera.is_connected:
            self.root.after(100, self.update_preview)

    def update_view_ui_for_available_types(self):
        """Reveal/hide the checkboxes for whichever view types are supported by the SDK."""
        if not self.camera.is_connected:
            return
        available = self.camera.get_available_view_types()
        
        # Depth
        if "depth" in available:
            if "depth" in self.view_vars:
                self.view_vars["depth"].set(True)  # or default to False as you like
                self.view_checkbuttons["depth"].grid()
        else:
            if "depth" in self.view_checkbuttons:
                self.view_checkbuttons["depth"].grid_remove()
        
        # Disparity or confidence
        if "disparity" in available:
            if "disparity" in self.view_vars:
                self.view_vars["disparity"].set(False)
                self.view_checkbuttons["disparity"].grid()
        elif "confidence" in available:
            if "confidence" in self.view_vars:
                self.view_checkbuttons["confidence"].grid()
        # else hide them

    # ----------------- Video Recording -----------------
    
    def on_start_recording_clicked(self):
        if not self.camera.is_connected:
            messagebox.showerror("Error", "Camera not connected")
            return
        out_dir = self.output_dir_var.get()
        codec = self.codec_var.get()
        bitrate = self.bitrate_var.get()
        
        if not hasattr(self, 'video_recorder'):
            self.video_recorder = VideoRecorder(self.camera)
        
        success = self.video_recorder.start_recording(output_dir=out_dir,
                                                      codec=codec,
                                                      bitrate=bitrate)
        if success:
            self.recording_status_label.config(text="Recording")
            self.start_record_button.state(['disabled'])
            self.stop_record_button.state(['!disabled'])
            
            # If you want to enforce a duration limit
            duration_limit = self.duration_limit_var.get()
            if duration_limit > 0:
                self.root.after(duration_limit*1000, self.check_duration_limit)
        else:
            messagebox.showerror("Error", "Failed to start recording")

    def on_stop_recording_clicked(self):
        if not hasattr(self, 'video_recorder'):
            return
        if not self.video_recorder.is_recording:
            return
        
        success, video_path, duration = self.video_recorder.stop_recording()
        if success:
            self.recording_status_label.config(text="Not recording")
            self.recording_duration_label.config(text="0 seconds")
            if video_path:
                self.recording_file_label.config(text=os.path.basename(video_path))
            self.start_record_button.state(['!disabled'])
            self.stop_record_button.state(['disabled'])
            
            self.refresh_video_list()
            
            messagebox.showinfo("Recording Complete",
                                f"Video saved to: {video_path}\nDuration: {duration:.1f} seconds")
        else:
            messagebox.showerror("Error", "Failed to stop recording")

    def check_duration_limit(self):
        """Stop the recording if we've hit the user-specified limit."""
        if hasattr(self, 'video_recorder') and self.video_recorder.is_recording:
            limit = self.duration_limit_var.get()
            status = self.video_recorder.get_recording_status()
            if status["duration"] >= limit > 0:
                self.logger.info(f"Recording reached duration limit {limit} sec. Stopping.")
                self.on_stop_recording_clicked()

    def refresh_video_list(self):
        """Reload any .svo files in the output directory and display them."""
        self.video_listbox.delete(0, tk.END)
        out_dir = self.output_dir_var.get()
        if not os.path.isdir(out_dir):
            return
        files = sorted(Path(out_dir).glob("*.svo"), reverse=True)
        for f in files:
            # If there's metadata (json) we can parse it
            meta_file = f.with_suffix('.json')
            display = f.name
            if meta_file.exists():
                try:
                    with open(meta_file, 'r') as mf:
                        md = json.load(mf)
                    stime = md.get("start_time", "")
                    dur = md.get("duration_seconds", 0)
                    display = f"{f.name} - {stime} ({dur:.1f}s)"
                except:
                    pass
            self.video_listbox.insert(tk.END, display)

    # ----------------- Camera Settings Handling -----------------
    
    def on_camera_mode_changed(self, event=None):
        """Switch between auto/manual mode for brightness/exposure/gain..."""
        is_manual = (self.camera_mode_var.get() == "manual")
        for name, widgets in self.camera_setting_widgets.items():
            if widgets["auto"] is not None:
                # if manual, let user toggle "auto" or not
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
                # For settings w/o auto
                if is_manual:
                    widgets["scale"].state(['!disabled'])
                else:
                    widgets["scale"].state(['disabled'])
        self.settings["camera"]["mode"] = self.camera_mode_var.get()

    def on_auto_checkbox_changed(self, name):
        """If user toggles 'Auto' for e.g. exposure/gain, disable the slider."""
        if self.camera_settings_vars[name]["auto"].get():
            self.camera_setting_widgets[name]["scale"].state(['disabled'])
            self.settings["camera"][name] = -1
        else:
            self.camera_setting_widgets[name]["scale"].state(['!disabled'])
            self.settings["camera"][name] = self.camera_settings_vars[name]["value"].get()

    def on_scale_value_changed(self, name, raw_value):
        """Whenever the user moves a slider, update the label."""
        try:
            val = int(float(raw_value))
            self.camera_setting_widgets[name]["label"].config(text=str(val))
            self.camera_settings_vars[name]["value"].set(val)
        except Exception as e:
            self.logger.error(f"Error updating scale: {e}")

    # ----------------- Settings Save/Load -----------------

    def update_settings_from_ui(self):
        """Pull the latest UI states into self.settings."""
        self.settings["capture_mode"] = self.capture_mode_var.get()
        self.settings["time_interval"] = self.time_interval_var.get()
        self.settings["gps_interval"] = self.gps_interval_var.get()
        self.settings["output_directory"] = self.output_dir_var.get()
        
        # Save which views are toggled
        if "view_types" not in self.settings:
            self.settings["view_types"] = {}
        for vtype, var in self.view_vars.items():
            self.settings["view_types"][vtype] = var.get()
        
        # Camera
        self.settings["camera"]["mode"] = self.camera_mode_var.get()
        self.settings["camera"]["resolution"] = self.resolution_var.get()
        self.settings["camera"]["fps"] = self.fps_var.get()
        
        for name, vs in self.camera_settings_vars.items():
            if vs["auto"].get():
                self.settings["camera"][name] = -1
            else:
                self.settings["camera"][name] = vs["value"].get()
        
        # GPS
        self.settings["gps"]["port"] = self.gps_port_var.get()
        self.settings["gps"]["baud_rate"] = self.gps_baud_rate_var.get()
        
        return self.settings

    def on_save_settings_clicked(self):
        """User pressed 'Save Settings'."""
        s = self.update_settings_from_ui()
        if save_settings(s):
            messagebox.showinfo("Success", "Settings saved successfully.")
        else:
            messagebox.showerror("Error", "Failed to save settings.")

    # ----------------- Window Close -----------------
    
    def on_closing(self):
        """When the user closes the window, stop everything cleanly."""
        # If recording, stop
        if hasattr(self, 'video_recorder') and self.video_recorder.is_recording:
            self.video_recorder.stop_recording()
        
        # If capturing, stop
        if self.capture_controller and self.capture_controller.is_capturing:
            self.capture_controller.stop_capture()
        
        # Disconnect
        self.camera.disconnect()
        self.gps.disconnect()
        
        # Save any changed settings
        self.update_settings_from_ui()
        save_settings(self.settings)
        
        self.root.destroy()

    def format_coordinate(coord, is_lat=True):
        """
        Convert a decimal coordinate into a DMS (degrees, minutes, seconds) string.
        Returns a string like: 37°48'30.00" N or 122°24'15.00" W.
        """
        try:
            d = abs(coord)
            degrees = int(d)
            minutes = int((d - degrees) * 60)
            seconds = (d - degrees - minutes/60) * 3600
            direction = ''
            if is_lat:
                direction = 'N' if coord >= 0 else 'S'
            else:
                direction = 'E' if coord >= 0 else 'W'
            return f"{degrees}°{minutes}'{seconds:.2f}\" {direction}"
        except Exception:
            return "N/A"

    def update_gps_details(self):
        """
        Update the detailed GPS status labels in the GPS tab with user-friendly data.
        """
        if self.gps.is_connected:
            gps_data = self.gps.get_current_data()
            fix_status = "Fix" if self.gps.has_fix() else "No Fix"
            self.gps_status_labels["gps_connection_status"].config(text="Connected")
            self.gps_status_labels["gps_fix_type"].config(text=fix_status)
            self.gps_status_labels["gps_satellites"].config(text=str(gps_data.get("satellites", "?")))
            
            latitude = gps_data.get("latitude")
            longitude = gps_data.get("longitude")
            # Use the helper function to format coordinates if available
            if latitude is not None:
                self.gps_status_labels["gps_latitude"].config(text=format_coordinate(latitude, is_lat=True))
            else:
                self.gps_status_labels["gps_latitude"].config(text="N/A")
            
            if longitude is not None:
                self.gps_status_labels["gps_longitude"].config(text=format_coordinate(longitude, is_lat=False))
            else:
                self.gps_status_labels["gps_longitude"].config(text="N/A")
            
            self.gps_status_labels["gps_altitude"].config(text=str(gps_data.get("altitude", "N/A")))
            self.gps_status_labels["gps_speed"].config(text=str(gps_data.get("speed", "N/A")))
            self.gps_status_labels["gps_time"].config(text=str(gps_data.get("timestamp", "N/A")))
