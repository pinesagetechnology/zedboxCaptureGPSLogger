#!/usr/bin/env python3
"""
Capture module for ZED Camera Capture Tool.
Handles the logic for capturing images based on time or GPS intervals.
"""

import logging
import time
import threading
from datetime import datetime
from pathlib import Path
import json

class CaptureController:
    """Class to control the image capture process with support for multiple view types"""
    
    def __init__(self, camera, gps, settings):
        self.camera = camera
        self.gps = gps
        self.settings = settings
        self.logger = logging.getLogger("CaptureController")
        
        # Capture state
        self.is_capturing = False
        self.capture_thread = None
        self.stop_event = threading.Event()
        
        # Capture statistics
        self.capture_count = 0
        self.last_capture_time = None
        self.last_capture_location = None
        self.distance_traveled = 0
        
        # Create output directory if it doesn't exist
        output_dir = Path(settings["output_directory"])
        output_dir.mkdir(parents=True, exist_ok=True)
        
    def start_capture(self, settings=None):
        """
        Start the capture process
        
        Args:
            settings: Optional updated settings to use
        """
        if self.is_capturing:
            self.logger.warning("Capture already in progress")
            return False
            
        if settings:
            self.settings = settings
            
        # Check if camera and GPS are connected
        if not self.camera.is_connected:
            self.logger.error("Cannot start capture: Camera not connected")
            return False
            
        if self.settings["capture_mode"] == "gps" and not self.gps.is_connected:
            self.logger.error("Cannot start capture in GPS mode: GPS not connected")
            return False
            
        # Reset capture state
        self.capture_count = 0
        self.last_capture_time = None
        self.last_capture_location = None
        self.distance_traveled = 0
        self.stop_event.clear()
        
        # Start capture thread
        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
        self.logger.info(f"Started capture in {self.settings['capture_mode']} mode")
        return True
        
    def stop_capture(self):
        """Stop the capture process"""
        if not self.is_capturing:
            return
            
        self.stop_event.set()
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
            
        self.is_capturing = False
        self.logger.info(f"Stopped capture after {self.capture_count} image sets")
        
    def _capture_loop(self):
        """Main capture loop running in a separate thread"""
        try:
            mode = self.settings["capture_mode"]
            output_dir = self.settings["output_directory"]
            
            # Get the view types to capture from settings
            view_types = self._get_view_types_from_settings()
            
            if mode == "time":
                # Time-based capture
                interval = self.settings["time_interval"]
                self.logger.info(f"Capturing every {interval} seconds with view types: {view_types}")
                
                while not self.stop_event.is_set():
                    # Capture image with metadata
                    self._capture_image(output_dir, view_types=view_types)
                    
                    # Wait for the specified interval
                    for _ in range(int(interval * 10)):  # Check stop event 10 times per second
                        if self.stop_event.is_set():
                            break
                        time.sleep(0.1)
                        
            elif mode == "gps":
                # GPS-based capture
                distance_threshold = self.settings["gps_interval"]
                self.logger.info(f"Capturing every {distance_threshold} meters with view types: {view_types}")
                
                # Set initial capture location if GPS has fix
                gps_data = self.gps.get_current_data()
                if self.gps.has_fix():
                    self.last_capture_location = (gps_data["latitude"], gps_data["longitude"])
                
                # Initial capture
                self._capture_image(output_dir, view_types=view_types)
                
                while not self.stop_event.is_set():
                    # Get current GPS location
                    gps_data = self.gps.get_current_data()
                    
                    if self.gps.has_fix() and self.last_capture_location:
                        current_location = (gps_data["latitude"], gps_data["longitude"])
                        
                        # Calculate distance between current location and last capture location directly
                        distance = self._calculate_distance(self.last_capture_location, current_location)
                        
                        if distance and distance >= distance_threshold:
                            # We've moved far enough, capture another image
                            self._capture_image(output_dir, view_types=view_types)
                            self.distance_traveled += distance
                            # Update last capture location to current location
                            self.last_capture_location = current_location
                    
                    # Short sleep to prevent CPU overuse
                    time.sleep(0.1)
                    
        except Exception as e:
            self.logger.error(f"Error in capture loop: {e}")
            self.is_capturing = False
            
    def _get_view_types_from_settings(self):
        """Get list of view types to capture from settings"""
        if "view_types" in self.settings:
            # Get enabled view types from settings
            view_types = []
            for view_type, enabled in self.settings["view_types"].items():
                if enabled:
                    view_types.append(view_type)
                    
            # If nothing is enabled, default to RGB
            if not view_types:
                view_types = ["rgb"]
                
            return view_types
        else:
            # Default to just RGB if no view types specified in settings
            return ["rgb"]
            
    def _capture_image(self, output_dir, view_types=None):
        """Capture images with metadata for all specified view types"""
        try:
            # If no view types specified, get from settings
            if view_types is None:
                view_types = self._get_view_types_from_settings()
                
            # Get current GPS data
            gps_data = self.gps.get_current_data()
            
            # Create metadata
            metadata = {
                "datetime": datetime.now().isoformat(),
                "capture_mode": self.settings["capture_mode"],
                "gps": {
                    "latitude": gps_data["latitude"],
                    "longitude": gps_data["longitude"],
                    "altitude": gps_data["altitude"],
                    "satellites": gps_data["satellites"],
                    "fix_quality": gps_data["fix_quality"],
                    "has_fix": self.gps.has_fix()
                },
                "camera": {
                    "resolution": self.settings["camera"]["resolution"],
                    "mode": self.settings["camera"]["mode"]
                },
                "view_types": view_types,
                "sequence_number": self.capture_count
            }
            
            # Generate file prefix
            date_str = datetime.now().strftime("%Y%m%d")
            file_prefix = f"zed_{date_str}"
            
            # Capture images for all specified view types
            success, image_paths = self.camera.capture_image(output_dir, file_prefix, metadata, view_types)
            
            if success:
                self.capture_count += 1
                self.last_capture_time = datetime.now()
                
                # Update last capture location if we have GPS
                if self.gps.has_fix():
                    self.last_capture_location = (gps_data["latitude"], gps_data["longitude"])
                    
                # Log captured images
                image_types = ", ".join(image_paths.keys())
                self.logger.info(f"Captured image set #{self.capture_count} with types: {image_types}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error capturing image: {e}")
            return False
            
    def get_capture_stats(self):
        """Get current capture statistics"""
        return {
            "is_capturing": self.is_capturing,
            "capture_count": self.capture_count,
            "last_capture_time": self.last_capture_time.isoformat() if self.last_capture_time else None,
            "distance_traveled": round(self.distance_traveled, 2) if self.distance_traveled else 0,
            "mode": self.settings["capture_mode"]
        }
    
    def _calculate_distance(self, pos1, pos2):
        """
        Calculate distance between two GPS coordinates
        
        Args:
            pos1: Tuple of (latitude, longitude)
            pos2: Tuple of (latitude, longitude)
            
        Returns:
            float: Distance in meters
        """
        import math
        # Both positions must be valid
        if pos1[0] is None or pos1[1] is None or pos2[0] is None or pos2[1] is None:
            return None
            
        # Convert decimal degrees to radians
        lat1, lon1 = pos1
        lat2, lon2 = pos2
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371000  # Radius of earth in meters
        
        return c * r