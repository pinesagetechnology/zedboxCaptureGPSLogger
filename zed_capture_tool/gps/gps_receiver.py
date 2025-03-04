#!/usr/bin/env python3
"""
GPS module for ZED Camera Capture Tool.
Handles interaction with the uBlox GPS receiver via serial port.
"""

import logging
import math
import time
import threading
import serial
import pynmea2
from datetime import datetime

class GPSReceiver:
    """Class to manage the GPS operations"""
    # Add GPS model-specific configurations
    GPS_MODELS = {
        "uBlox": {
            "default_baud": 9600,
            "default_port": "/dev/ttyACM0"
        },
        "BU353N5": {
            "default_baud": 4800,
            "default_port": "/dev/ttyUSB0"
        }
    }

    def __init__(self):
        self.serial_port = None
        self.is_connected = False
        self.thread = None
        self.thread_running = False
        self.logger = logging.getLogger("GPSReceiver")
        
        # Current GPS data
        self.current_data = {
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "speed": None,
            "timestamp": None,
            "satellites": None,
            "fix_quality": None,
            "hdop": None
        }
        
        # Last position for distance calculation
        self.last_position = (None, None)
        
    def connect(self, settings):
        """Connect to the GPS device"""
        if self.is_connected:
            self.disconnect()
            
        try:
            # Get active device config
            active_device = settings["gps"]["active_device"]
            device_config = settings["gps"]["devices"][active_device]
            self.current_model = device_config["model"]

            port = settings["gps"]["port"]
            baud_rate = settings["gps"]["baud_rate"]
            timeout = settings["gps"]["timeout"]
            
            self.logger.info(f"Attempting to connect to GPS model {self.current_model} on {port} at {baud_rate} baud")
            
            # Try opening the port
            self.serial_port = serial.Serial(port, baud_rate, timeout=timeout)
            
            # Test if data is coming through
            initial_data = []
            for _ in range(5):  # Try to read 5 lines
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode('ascii', errors='replace').strip()
                    if line:
                        initial_data.append(line)
                        self.logger.debug(f"GPS initial data: {line}")
                time.sleep(0.2)
            
            if not initial_data:
                self.logger.warning(f"No initial data received from GPS on {port}")
            else:
                self.logger.info(f"Received {len(initial_data)} lines of initial GPS data")
                
            # Add last raw NMEA storage
            self.last_raw_nmea = None
            
            self.is_connected = True
            
            # Start the reading thread
            self.thread_running = True
            self.thread = threading.Thread(target=self._read_gps_data)
            self.thread.daemon = True
            self.thread.start()
            
            self.logger.info(f"Connected to GPS on port {port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to GPS: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from the GPS device"""
        if self.is_connected:
            # Stop the reading thread
            self.thread_running = False
            if self.thread:
                self.thread.join(timeout=1.0)
                
            # Close the serial port
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                
            self.is_connected = False
            self.serial_port = None
            self.logger.info("Disconnected from GPS")
            
    def _read_gps_data(self):
        """Read and parse GPS data in a background thread"""
        while self.thread_running and self.serial_port and self.serial_port.is_open:
            try:
                line = self.serial_port.readline().decode('ascii', errors='replace').strip()
                
                if line:
                    # Store raw NMEA sentence
                    self.last_raw_nmea = line
                    
                    if line.startswith('$'):
                        try:
                            msg = pynmea2.parse(line)
                            
                            # Parse different NMEA sentence types
                            if isinstance(msg, pynmea2.GGA):
                                # Global Positioning System Fix Data
                                self.current_data["latitude"] = msg.latitude
                                self.current_data["longitude"] = msg.longitude
                                self.current_data["altitude"] = msg.altitude
                                self.current_data["fix_quality"] = msg.gps_qual
                                self.current_data["satellites"] = msg.num_sats
                                self.current_data["hdop"] = msg.horizontal_dil
                                
                                if msg.timestamp:
                                    timestamp = datetime.combine(
                                        datetime.now().date(),
                                        msg.timestamp
                                    )
                                    self.current_data["timestamp"] = timestamp.isoformat()
                                    
                            elif isinstance(msg, pynmea2.RMC):
                                # Recommended Minimum Navigation Information
                                self.current_data["latitude"] = msg.latitude
                                self.current_data["longitude"] = msg.longitude
                                self.current_data["speed"] = msg.spd_over_grnd * 1.852  # Convert knots to km/h
                                
                                if msg.datestamp and msg.timestamp:
                                    timestamp = datetime.combine(msg.datestamp, msg.timestamp)
                                    self.current_data["timestamp"] = timestamp.isoformat()
                                    
                            # Update last position for distance calculation if we have valid coordinates
                            if self.current_data["latitude"] is not None and self.current_data["longitude"] is not None:
                                self.last_position = (self.current_data["latitude"], self.current_data["longitude"])
                                
                        except pynmea2.ParseError:
                            pass  # Ignore parse errors
                            
            except Exception as e:
                self.logger.error(f"Error reading GPS data: {e}")
                time.sleep(0.1)  # Prevent tight loop on error
                
    def get_current_data(self):
        """Get the current GPS data"""
        return self.current_data.copy()
        
    def has_fix(self):
        """Check if GPS has a fix (valid position)"""
        return (self.current_data["latitude"] is not None and 
                self.current_data["longitude"] is not None and 
                self.current_data["fix_quality"] is not None and 
                self.current_data["fix_quality"] > 0)
                
    def distance_from_last(self, new_position):
        """
        Calculate distance between current position and last saved position in meters
        
        Args:
            new_position: Tuple of (latitude, longitude)
            
        Returns:
            float: Distance in meters, or None if no previous position
        """
        if self.last_position[0] is None or self.last_position[1] is None:
            return None
            
        # Haversine formula for distance calculation
        lat1, lon1 = self.last_position
        lat2, lon2 = new_position
        
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371000  # Radius of earth in meters
        
        return c * r