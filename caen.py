import json
import paho.mqtt.client as mqtt
import logging
import threading
import time
from safety import *
from caen_client import CAENTCPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CaenMQTTClient:
    def __init__(self, system_obj):
        self._system = system_obj
        self.TOPIC = system_obj.settings["Caen"]["mqtt_topic"]
        self._status = {}
        
        # Create MQTT client
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "CAEN")
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message
        
        try:
            self._client.connect(self._system.BROKER, self._system.PORT)
            logger.info(f"Connected to MQTT broker at {self._system.BROKER}:{self._system.PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
        
        # Create TCP client for direct CAEN communication
        self._caen = CAENTCPClient()
        
        # Create status update thread
        self._stop_thread = False
        self._update_thread = threading.Thread(target=self._status_update_loop)
        self._update_thread.daemon = True
        
        # Start client loop and update thread
        self.start_client_loop()
        
    def start_client_loop(self):
        """Start the MQTT client loop and status update thread"""
        try:
            self._client.loop_start()
            self._stop_thread = False
            self._update_thread.start()
            logger.info("Started CAEN client loops")
        except Exception as e:
            logger.error(f"Error starting client loops: {e}")
        
    def stop_client_loop(self):
        """Stop the MQTT client loop and status update thread"""
        try:
            self._stop_thread = True
            if self._update_thread.is_alive():
                self._update_thread.join(timeout=2)
            self._client.loop_stop()
            self._caen.disconnect()
            logger.info("Stopped CAEN client loops")
        except Exception as e:
            logger.error(f"Error stopping client loops: {e}")

    def on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection"""
        if rc == 0:
            self._client.subscribe(self.TOPIC)
            logger.info(f"Subscribed to CAEN topic: {self.TOPIC}")
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")

    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            self.handle_caen_message(msg.payload)
        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}")

    def handle_caen_message(self, payload):
        """Process CAEN status messages"""
        try:
            self._status = json.loads(payload)
            self._system.update_status({"caen": self._status})
            
            # Safety checks
            if self._system.has_valid_status():
                self._system.safety_flags["hv_safe"] = check_hv_safe(self._system.status)
        except Exception as e:
            logger.error(f"Error handling CAEN message: {e}")
            
    def _status_update_loop(self):
        """Background thread to periodically update CAEN status"""
        while not self._stop_thread:
            try:
                # Get status from CAEN
                status = self._caen.get_status()
                if status:
                    # Publish status update
                    self._client.publish(f"{self.TOPIC}/status", json.dumps(status))
                    logger.debug("Published CAEN status update")
            except Exception as e:
                logger.error(f"Error in status update loop: {e}")
            
            # Wait before next update
            time.sleep(2)
            
    def turn_on_channel(self, channel):
        """Turn on a CAEN channel"""
        try:
            success = self._caen.turn_on_channel(channel)
            if success:
                logger.info(f"Turned on CAEN channel {channel}")
            else:
                logger.error(f"Failed to turn on CAEN channel {channel}")
            return success
        except Exception as e:
            logger.error(f"Error turning on channel {channel}: {e}")
            return False
            
    def turn_off_channel(self, channel):
        """Turn off a CAEN channel"""
        try:
            success = self._caen.turn_off_channel(channel)
            if success:
                logger.info(f"Turned off CAEN channel {channel}")
            else:
                logger.error(f"Failed to turn off CAEN channel {channel}")
            return success
        except Exception as e:
            logger.error(f"Error turning off channel {channel}: {e}")
            return False

    ### Logic to control with the CAEN (not via MQTT) ###
