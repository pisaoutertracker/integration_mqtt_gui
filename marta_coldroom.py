import json
import paho.mqtt.client as mqtt
import sys
import logging

from safety import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MartaColdRoomMQTTClient:

    def __init__(self, system_obj):
        self._system = system_obj
        
        # Initialize topics
        self.TOPIC_MARTA = system_obj.settings["MARTA"]["mqtt_topic"]
        self.TOPIC_BASE_MARTA = self.TOPIC_MARTA.replace("#", "")
        self.TOPIC_COLDROOM = system_obj.settings["Coldroom"]["mqtt_topic"]
        self.TOPIC_BASE_COLDROOM = self.TOPIC_COLDROOM.replace("#", "")
        self.TOPIC_CO2_SENSOR = system_obj.settings["Coldroom"]["co2_sensor_topic"]
        
        logger.debug("Initializing MQTT client with topics:")
        logger.debug(f"MARTA topic: {self.TOPIC_MARTA}")
        logger.debug(f"Coldroom topic: {self.TOPIC_COLDROOM}")
        logger.debug(f"CO2 sensor topic: {self.TOPIC_CO2_SENSOR}")
        
        # Create single MQTT client
        self._client = mqtt.Client(client_id="MARTA_COLDROOM")
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message
        
        # Initialize status dictionaries
        self._marta_status = {}
        self._coldroom_state = {}
        self._co2_sensor_data = {}
        
        # Connect to broker
        try:
            logger.debug(f"Connecting to MQTT broker at {self._system.BROKER}:{self._system.PORT}")
            self._client.connect(self._system.BROKER, self._system.PORT)
            logger.debug("MQTT client connected successfully")
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            raise
        
        # Start client loop
        self.start_client_loops()

    def start_client_loops(self):
        """Start the MQTT client loop to process network traffic"""
        logger.debug("Starting MQTT client loop")
        self._client.loop_start()
        logger.debug("MQTT client loop started")
        
    def stop_client_loops(self):
        """Stop the MQTT client loop"""
        logger.debug("Stopping MQTT client loop")
        self._client.loop_stop()
        logger.debug("MQTT client loop stopped")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.debug("Connected to MQTT broker, subscribing to topics...")
            # Subscribe to all topics
            self._client.subscribe(self.TOPIC_MARTA)
            logger.debug(f"Subscribed to MARTA topic: {self.TOPIC_MARTA}")
            self._client.subscribe(self.TOPIC_COLDROOM)
            logger.debug(f"Subscribed to Coldroom topic: {self.TOPIC_COLDROOM}")
            self._client.subscribe(self.TOPIC_CO2_SENSOR)
            logger.debug(f"Subscribed to CO2 sensor topic: {self.TOPIC_CO2_SENSOR}")
        else:
            logger.error(f"Connection failed with result code {rc}")

    def on_message(self, client, userdata, msg):
        logger.debug(f"Received MQTT message on topic: {msg.topic}")
        try:
            payload = msg.payload.decode()
            logger.debug(f"Payload: {payload}")
        except:
            logger.error("Could not decode payload as string")

        # Handle MARTA messages
        if msg.topic.startswith(self.TOPIC_BASE_MARTA):
            if "status" in msg.topic:
                logger.debug("Processing MARTA status message")
                self.handle_marta_status_message(msg.payload)
                logger.debug(f"Updated MARTA status: {self._marta_status}")
                
        # Handle Coldroom messages
        elif msg.topic.startswith(self.TOPIC_BASE_COLDROOM):
            if "state" in msg.topic:
                logger.debug("Processing Coldroom state message")
                self.handle_coldroom_state_message(msg.payload)
                logger.debug(f"Updated Coldroom state: {self._coldroom_state}")
        
        # Handle CO2 sensor messages
        elif msg.topic == self.TOPIC_CO2_SENSOR:
            logger.debug("Processing CO2 sensor message")
            self.handle_co2_sensor_message(msg.payload)
            logger.debug(f"Updated CO2 sensor data: {self._co2_sensor_data}")
        else:
            logger.warning(f"Received message on unknown topic: {msg.topic}")

        # Safety checks
        if self._system.has_valid_status():
            self._system.safety_flags["door_locked"] = not check_dew_point(self._system.status)
            self._system.safety_flags["sleep"] = check_door_status(self._system.status)
            logger.debug(f"Safety flags updated: {self._system.safety_flags}")

    def publish_cmd(self, command, target, payload):
        """
        Publish a command to either MARTA or Coldroom
        
        Args:
            command (str): The command to send
            target (str): Either 'marta' or 'coldroom'
            payload: The command payload
        """
        if target == 'marta':
            topic = f"{self.TOPIC_BASE_MARTA}cmd/{command}"
        else:  # coldroom
            topic = f"{self.TOPIC_BASE_COLDROOM}cmd/{command}"
            print(topic)
        
        logger.info(f"Sending command '{command}' to {target} with payload: {payload}")
        self._client.publish(topic, payload)

    ### MARTA ###

    def handle_marta_status_message(self, payload):
        try:
            self._marta_status = json.loads(payload)
            logger.debug(f"Parsed MARTA status: {self._marta_status}")
            self._system.update_status({"marta": self._marta_status})
        except Exception as e:
            logger.error(f"Error parsing MARTA status message: {e}")

    ## Commands ##

    def start_chiller(self, payload):
        self.publish_cmd("start_chiller", 'marta', payload)

    def start_co2(self, payload):
        self.publish_cmd("start_co2", 'marta', payload)

    def stop_co2(self, payload):
        self.publish_cmd("stop_co2", 'marta', payload)

    def stop_chiller(self, payload):
        self.publish_cmd("stop_chiller", 'marta', payload)

    def set_flow_active(self, payload):
        self.publish_cmd("set_flow_active", 'marta', payload)

    def set_temperature_setpoint(self, payload):
        self.publish_cmd("set_temperature_setpoint", 'marta', payload)

    def set_speed_setpoint(self, payload):
        self.publish_cmd("set_speed_setpoint", 'marta', payload)

    def set_flow_setpoint(self, payload):
        self.publish_cmd("set_flow_setpoint", 'marta', payload)

    def clear_alarms(self, payload):
        self.publish_cmd("clear_alarms", 'marta', payload)

    def reconnect(self, payload):
        self.publish_cmd("reconnect", 'marta', payload)

    def refresh(self, payload):
        self.publish_cmd("refresh", 'marta', payload)

    ### COLDROOM ###

    def handle_coldroom_state_message(self, payload):
        try:
            self._coldroom_state = json.loads(payload)
            logger.debug(f"Parsed Coldroom state: {self._coldroom_state}")
            self._system.update_status({"coldroom": self._coldroom_state})
        except Exception as e:
            logger.error(f"Error parsing Coldroom state message: {e}")

    ## Commands ##

    def set_temperature(self, payload):
        self.publish_cmd("set_temperature", 'coldroom', payload)

    def set_humidity(self, payload):
        self.publish_cmd("set_humidity", 'coldroom', payload)

    def control_light(self, payload):
        self.publish_cmd("control_light", 'coldroom', payload)

    def control_temperature(self, payload):
        self.publish_cmd("control_temperature", 'coldroom', payload)

    def control_humidity(self, payload):
        self.publish_cmd("control_humidity", 'coldroom', payload)

    def control_external_dry_air(self, payload):
        self.publish_cmd("control_external_dry_air", 'coldroom', payload)

    def reset_alarms(self, payload):
        self.publish_cmd("reset_alarms", 'coldroom', payload)

    def run(self, payload):
        self.publish_cmd("run", 'coldroom', payload)

    def stop(self, payload):
        self.publish_cmd("stop", 'coldroom', payload)

    def handle_co2_sensor_message(self, payload):
        """Handle incoming CO2 sensor messages"""
        try:
            self._co2_sensor_data = json.loads(payload)
            logger.debug(f"Parsed CO2 sensor data: {self._co2_sensor_data}")
            self._system.update_status({"co2_sensor": self._co2_sensor_data})
        except Exception as e:
            logger.error(f"Error parsing CO2 sensor message: {e}")

    ### Properties ###
    @property
    def marta_status(self):
        return self._marta_status

    @property
    def coldroom_state(self):
        return self._coldroom_state

    @property
    def door_locked(self):
        return self._system.safety_flags.get("door_locked", True)  # Default to True (safe) if not available
