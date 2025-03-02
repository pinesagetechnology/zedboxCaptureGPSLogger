"""
Video capture extension for the ZED Camera Capture Tool.
Extends the capture module with video recording capabilities.
"""

import os
import logging
import time
import json
from datetime import datetime
from pathlib import Path
import pyzed.sl as sl

class VideoRecorder:
    """Class to manage video recording with the ZED camera"""
    
    def __init__(self, camera):
        """
        Initialize the video recorder
        
        Args:
            camera: ZedCamera instance
        """
        self.camera = camera
        self.logger = logging.getLogger("VideoRecorder")
        
        # Recording state
        self.is_recording = False
        self.recording_params = None
        self.recording_path = None
        self.start_time = None
        self.duration = 0
        
    def start_recording(self, output_dir, resolution=None, fps=None, bitrate=None, codec="H264"):
        """
        Start video recording
        
        Args:
            output_dir: Directory to save the video
            resolution: Video resolution (None to use current camera resolution)
            fps: Frame rate (None to use current camera FPS)
            bitrate: Video bitrate in Kbps (None for default)
            codec: Video codec ("H264" or "H265")
            
        Returns:
            bool: Success or failure
        """
        if not self.camera.is_connected:
            self.logger.error("Cannot start recording: Camera not connected")
            return False
            
        if self.is_recording:
            self.logger.warning("Already recording. Stop current recording first.")
            return False
            
        try:
            # Create output directory if it doesn't exist
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"zed_video_{timestamp}.svo"
            video_path = output_path / video_filename
            
            # Set up recording parameters
            recording_params = sl.RecordingParameters(
                str(video_path),
                sl.SVO_COMPRESSION_MODE.H264
            )
            
            # Set bitrate if specified
            if bitrate:
                recording_params.bitrate = bitrate
                
            # Start recording
            self.logger.info(f"Starting video recording to {video_path}")
            status = self.camera.camera.enable_recording(recording_params)
            
            if status != sl.ERROR_CODE.SUCCESS:
                self.logger.error(f"Failed to start recording: {status}")
                return False
                
            # Update state
            self.is_recording = True
            self.recording_params = recording_params
            self.recording_path = video_path
            self.start_time = datetime.now()
            
            # Save metadata
            metadata = {
                "filename": video_filename,
                "start_time": self.start_time.isoformat(),
                "camera_settings": {
                    "resolution": self.camera.camera.get_camera_information().camera_resolution.name,
                    "fps": self.camera.camera.get_camera_information().camera_fps
                },
                "recording_settings": {
                    "codec": codec,
                    "bitrate": bitrate
                }
            }
            
            metadata_path = output_path / f"zed_video_{timestamp}.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=4)
                
            self.logger.info("Recording started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting recording: {e}")
            return False
            
    def stop_recording(self):
        """
        Stop current video recording
        
        Returns:
            tuple: (success, video_path, duration_seconds)
        """
        if not self.is_recording:
            self.logger.warning("Not currently recording")
            return False, None, 0
            
        try:
            # Stop recording
            self.logger.info("Stopping video recording")
            self.camera.camera.disable_recording()
            
            # Update state
            self.is_recording = False
            end_time = datetime.now()
            self.duration = (end_time - self.start_time).total_seconds()
            
            # Update metadata
            if self.recording_path:
                metadata_path = self.recording_path.with_suffix('.json')
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                            
                        metadata["end_time"] = end_time.isoformat()
                        metadata["duration_seconds"] = self.duration
                        
                        with open(metadata_path, 'w') as f:
                            json.dump(metadata, f, indent=4)
                    except Exception as e:
                        self.logger.error(f"Error updating metadata: {e}")
                
            self.logger.info(f"Recording stopped. Duration: {self.duration:.1f} seconds, File: {self.recording_path}")
            return True, str(self.recording_path), self.duration
            
        except Exception as e:
            self.logger.error(f"Error stopping recording: {e}")
            return False, None, 0
            
    def get_recording_status(self):
        """
        Get current recording status
        
        Returns:
            dict: Status information
        """
        if not self.is_recording:
            return {
                "is_recording": False,
                "duration": 0,
                "file_path": None
            }
            
        # Calculate current duration
        current_time = datetime.now()
        current_duration = (current_time - self.start_time).total_seconds()
        
        return {
            "is_recording": True,
            "duration": current_duration,
            "file_path": str(self.recording_path) if self.recording_path else None,
            "start_time": self.start_time.isoformat() if self.start_time else None
        }