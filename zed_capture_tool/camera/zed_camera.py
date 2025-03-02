#!/usr/bin/env python3
"""
Camera module for ZED Camera Capture Tool.
Handles interaction with ZED camera via SDK.
"""

import os
import logging
import time
from datetime import datetime
from pathlib import Path
import json
import pyzed.sl as sl

class ZedCamera:
    """Class to manage the ZED camera operations"""
    
    # Resolution mapping 
    RESOLUTIONS = {
        "HD2K": sl.RESOLUTION.HD2K,
        "HD1080": sl.RESOLUTION.HD1080,
        "HD720": sl.RESOLUTION.HD720,
        "VGA": sl.RESOLUTION.VGA
    }
    
    def __init__(self):
        self.camera = sl.Camera()
        self.init_params = sl.InitParameters()
        self.runtime_params = sl.RuntimeParameters()
        self.is_connected = False
        self.logger = logging.getLogger("ZedCamera")
        
    def connect(self, settings):
        """Connect to the ZED camera with the specified settings"""
        if self.is_connected:
            self.disconnect()
            
        try:
            # Configure camera init parameters based on settings
            self.init_params.camera_resolution = self.RESOLUTIONS.get(
                settings["camera"]["resolution"], sl.RESOLUTION.HD1080
            )
            self.init_params.camera_fps = settings["camera"]["fps"]
            
            # Open the camera
            status = self.camera.open(self.init_params)
            if status != sl.ERROR_CODE.SUCCESS:
                self.logger.error(f"Failed to open camera: {status}")
                return False
                
            # Apply camera settings if in manual mode
            if settings["camera"]["mode"] == "manual":
                self.apply_manual_settings(settings["camera"])
                
            self.is_connected = True
            self.logger.info(f"Connected to ZED camera: {self.camera.get_camera_information().serial_number}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to camera: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from the ZED camera"""
        if self.is_connected:
            self.camera.close()
            self.is_connected = False
            self.logger.info("Disconnected from ZED camera")
            
    def apply_manual_settings(self, camera_settings):
        """Apply manual camera settings"""
        try:
            # Set video settings
            if camera_settings["brightness"] >= 0:
                self.camera.set_camera_settings(sl.VIDEO_SETTINGS.BRIGHTNESS, camera_settings["brightness"])
            
            if camera_settings["contrast"] >= 0:
                self.camera.set_camera_settings(sl.VIDEO_SETTINGS.CONTRAST, camera_settings["contrast"])
                
            if camera_settings["hue"] >= 0:
                self.camera.set_camera_settings(sl.VIDEO_SETTINGS.HUE, camera_settings["hue"])
                
            if camera_settings["saturation"] >= 0:
                self.camera.set_camera_settings(sl.VIDEO_SETTINGS.SATURATION, camera_settings["saturation"])
                
            # Set AEC/AGC settings
            if camera_settings["exposure"] >= 0:
                self.camera.set_camera_settings(sl.VIDEO_SETTINGS.EXPOSURE, camera_settings["exposure"])
                
            if camera_settings["gain"] >= 0:
                self.camera.set_camera_settings(sl.VIDEO_SETTINGS.GAIN, camera_settings["gain"])
                
            if camera_settings["whitebalance"] >= 0:
                self.camera.set_camera_settings(sl.VIDEO_SETTINGS.WHITEBALANCE_TEMPERATURE, camera_settings["whitebalance"])
                
            self.logger.info("Applied manual camera settings")
        except Exception as e:
            self.logger.error(f"Error applying manual settings: {e}")
            
    def get_current_settings(self):
        """Get current camera settings"""
        if not self.is_connected:
            return None
            
        settings = {
            "brightness": self.camera.get_camera_settings(sl.VIDEO_SETTINGS.BRIGHTNESS),
            "contrast": self.camera.get_camera_settings(sl.VIDEO_SETTINGS.CONTRAST),
            "hue": self.camera.get_camera_settings(sl.VIDEO_SETTINGS.HUE),
            "saturation": self.camera.get_camera_settings(sl.VIDEO_SETTINGS.SATURATION),
            "exposure": self.camera.get_camera_settings(sl.VIDEO_SETTINGS.EXPOSURE),
            "gain": self.camera.get_camera_settings(sl.VIDEO_SETTINGS.GAIN),
            "whitebalance": self.camera.get_camera_settings(sl.VIDEO_SETTINGS.WHITEBALANCE_TEMPERATURE)
        }
        
        return settings
        
    def get_available_resolutions(self):
        """Get list of available resolutions"""
        return list(self.RESOLUTIONS.keys())
        
    def capture_image(self, output_dir, file_prefix, metadata=None):
        """
        Capture an image from the camera
        
        Args:
            output_dir: Directory to save the image
            file_prefix: Prefix for the filename
            metadata: Dictionary containing metadata to save with the image
            
        Returns:
            tuple: (success, image_path)
        """
        if not self.is_connected:
            self.logger.error("Cannot capture: Camera not connected")
            return False, None
            
        try:
            # Create output directory if it doesn't exist
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_filename = f"{file_prefix}_{timestamp}.png"
            image_path = output_path / image_filename
            
            # Create a ZED image object
            image = sl.Mat()
            
            # Capture image
            if self.camera.grab(self.runtime_params) == sl.ERROR_CODE.SUCCESS:
                # Retrieve image
                self.camera.retrieve_image(image, sl.VIEW.LEFT)
                
                # Save image
                image.write(str(image_path))
                
                # Save metadata if provided
                if metadata:
                    # Add filename and timestamp to metadata
                    metadata["filename"] = image_filename
                    metadata["timestamp"] = timestamp
                    
                    # Save metadata to file
                    metadata_path = output_path / f"{file_prefix}_{timestamp}.json"
                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=4)
                        
                self.logger.info(f"Image captured and saved to {image_path}")
                return True, str(image_path)
            else:
                self.logger.error("Failed to grab image from camera")
                return False, None
                
        except Exception as e:
            self.logger.error(f"Error capturing image: {e}")
            return False, None