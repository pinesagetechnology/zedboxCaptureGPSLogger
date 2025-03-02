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
    
    # View types mapping
    VIEW_TYPES = {
        "rgb": sl.VIEW.LEFT,
        "right": sl.VIEW.RIGHT,
        "depth": sl.VIEW.DEPTH,
        "disparity": sl.VIEW.DISPARITY,
        "confidence": sl.VIEW.CONFIDENCE
    }
    
    def __init__(self):
        self.camera = sl.Camera()
        self.init_params = sl.InitParameters()
        self.runtime_params = sl.RuntimeParameters()
        self.is_connected = False
        self.logger = logging.getLogger("ZedCamera")

        # Store images for different view types
        self.view_images = {}
        
        # Point cloud handling
        self.point_cloud = sl.Mat()
        
    def connect(self, settings):
        """Connect to the ZED camera with the specified settings"""
        if self.is_connected:
            self.disconnect()
                
        try:
            # For ZED X, only HD1080 is supported based on testing
            self.init_params.camera_resolution = sl.RESOLUTION.HD1080
            self.logger.info("Using HD1080 resolution for ZED X camera")

            # Enable depth and point cloud
            self.init_params.depth_mode = sl.DEPTH_MODE.ULTRA  # Use ULTRA for best quality
            self.init_params.coordinate_units = sl.UNIT.METER  # Use meters for depth
            self.init_params.depth_minimum_distance = 0.3  # Minimum depth in meters
            self.init_params.depth_maximum_distance = 20  # Maximum depth in meters
            
            # Configure depth sensing parameters (optional)
            # self.init_params.coordinate_system = sl.COORDINATE_SYSTEM.RIGHT_HANDED_Y_UP

            # Set FPS (use requested FPS, but default to 15 which we know works)
            fps = settings["camera"]["fps"]
            self.init_params.camera_fps = 15  # Default to known working value
            if fps in [15, 30]:  # Common supported FPS values
                self.init_params.camera_fps = fps
                
            # Open the camera
            self.logger.info(f"Opening camera with HD1080 resolution at {self.init_params.camera_fps} FPS")
            status = self.camera.open(self.init_params)
            if status != sl.ERROR_CODE.SUCCESS:
                self.logger.error(f"Failed to open camera: {status}")
                return False
                    
            # Apply camera settings if in manual mode
            if settings["camera"]["mode"] == "manual":
                self.apply_manual_settings(settings["camera"])

            # Initialize the image containers for each view type
            for view_name in self.VIEW_TYPES:
                self.view_images[view_name] = sl.Mat()

            self.is_connected = True
            self.logger.info(f"Connected to ZED camera: {self.camera.get_camera_information().serial_number}")
            return True
                
        except Exception as e:
            self.logger.error(f"Error connecting to camera: {e}")
            return False
            
    def get_current_frame(self, view_types=None):
        """
        Get the current frame from the camera in multiple view types
        
        Args:
            view_types: List of view types to retrieve (e.g., ["rgb", "depth", "disparity"]) or None for all views
            
        Returns:
            dict: Dictionary of view_type: image_data pairs
        """
        if not self.is_connected:
            return None
            
        if view_types is None:
            # Default to get just the RGB image
            view_types = ["rgb"]
            
        result = {}
        
        try:
            # Grab frame
            if self.camera.grab(self.runtime_params) == sl.ERROR_CODE.SUCCESS:
                # Retrieve all requested view types
                for view_name in view_types:
                    if view_name in self.VIEW_TYPES:
                        self.camera.retrieve_image(self.view_images[view_name], self.VIEW_TYPES[view_name])
                        # Get numpy array and store in result
                        result[view_name] = self.view_images[view_name].get_data()
                    elif view_name == "point_cloud":
                        # Special handling for point cloud
                        self.camera.retrieve_measure(self.point_cloud, sl.MEASURE.XYZRGBA)
                        result[view_name] = self.point_cloud.get_data()
        except Exception as e:
            self.logger.error(f"Error getting current frame: {e}")
            
        return result
    
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
        
    def capture_image(self, output_dir, file_prefix, metadata=None, view_types=None):
        """
        Capture images from the camera
        
        Args:
            output_dir: Directory to save the images
            file_prefix: Prefix for the filename
            metadata: Dictionary containing metadata to save with the image
            view_types: List of view types to capture (e.g., ["rgb", "depth", "disparity"]) or None for RGB only
            
        Returns:
            tuple: (success, image_paths)
        """
        if not self.is_connected:
            self.logger.error("Cannot capture: Camera not connected")
            return False, None
            
        if view_types is None:
            # Default to just RGB if not specified
            view_types = ["rgb"]
            
        try:
            # Create output directory if it doesn't exist
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_paths = {}
            
            # Capture all view types
            if self.camera.grab(self.runtime_params) == sl.ERROR_CODE.SUCCESS:
                # Process each view type
                for view_name in view_types:
                    if view_name in self.VIEW_TYPES:
                        # Generate filename for this view
                        image_filename = f"{file_prefix}_{view_name}_{timestamp}.png"
                        image_path = output_path / image_filename
                        
                        # Retrieve and save image
                        self.camera.retrieve_image(self.view_images[view_name], self.VIEW_TYPES[view_name])
                        self.view_images[view_name].write(str(image_path))
                        image_paths[view_name] = str(image_path)
                        
                    elif view_name == "point_cloud":
                        # Special handling for point cloud - save as PLY file
                        cloud_filename = f"{file_prefix}_pointcloud_{timestamp}.ply"
                        cloud_path = output_path / cloud_filename
                        
                        # Retrieve and save point cloud
                        self.camera.retrieve_measure(self.point_cloud, sl.MEASURE.XYZRGBA)
                        
                        # Save as PLY - SDK already has this function
                        self.camera.save_point_cloud(str(cloud_path))
                        image_paths["point_cloud"] = str(cloud_path)
                
                # Save metadata if provided
                if metadata:
                    # Add filenames and timestamp to metadata
                    metadata["filenames"] = {k: os.path.basename(v) for k, v in image_paths.items()}
                    metadata["timestamp"] = timestamp
                    metadata["view_types"] = view_types
                    
                    # Save metadata to file
                    metadata_path = output_path / f"{file_prefix}_metadata_{timestamp}.json"
                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=4)
                        
                self.logger.info(f"Images captured and saved to {output_dir}")
                return True, image_paths
            else:
                self.logger.error("Failed to grab image from camera")
                return False, None
                
        except Exception as e:
            self.logger.error(f"Error capturing image: {e}")
            return False, None