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
        self.TOPIC_CLEANROOM = system_obj.settings["Cleanroom"]["mqtt_topic"]
        self.TOPIC_BASE_CLEANROOM = self.TOPIC_CLEANROOM.replace("#", "")
        self.TOPIC_MARTA = system_obj.settings["MARTA"]["mqtt_topic"]
        self.TOPIC_BASE_MARTA = self.TOPIC_MARTA.replace("#", "")
        self.TOPIC_COLDROOM = system_obj.settings["Coldroom"]["mqtt_topic"]
        self.TOPIC_BASE_COLDROOM = self.TOPIC_COLDROOM.replace("#", "")
        self.TOPIC_CO2_SENSOR = system_obj.settings["Coldroom"]["co2_sensor_topic"]
        
        logger.info("Initializing MQTT client with topics:")
        logger.info(f"Cleanroom topic: {self.TOPIC_CLEANROOM}")
        logger.info(f"MARTA topic: {self.TOPIC_MARTA}")
        logger.info(f"Coldroom topic: {self.TOPIC_COLDROOM}")
        logger.info(f"CO2 sensor topic: {self.TOPIC_CO2_SENSOR}")
        
        # Create single MQTT client
        self._client = mqtt.Client(client_id="MARTA_COLDROOM_CLEANROOM")
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message
        
        # Set connection parameters
        self._client.keepalive = 60
        self._client.connect_timeout = 5
        
        # Initialize status dictionaries
        self._marta_status = {}
        self._coldroom_state = {}
        self._cleanroom_status = {}
        self._co2_sensor_data = {}
        self._current_topic = None

        
        # Connect to broker
        try:
            logger.debug(f"Connecting to MQTT broker at {self._system.BROKER}:{self._system.PORT}")
            self._client.connect(self._system.BROKER, self._system.PORT, keepalive=60)
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
            logger.info("Connected to MQTT broker, subscribing to topics...")
            # Subscribe to all topics
            self._client.subscribe(self.TOPIC_CLEANROOM)
            logger.info(f"Subscribed to Cleanroom topic: {self.TOPIC_CLEANROOM}")
            self._client.subscribe(self.TOPIC_MARTA)
            logger.info(f"Subscribed to MARTA topic: {self.TOPIC_MARTA}")
            self._client.subscribe(self.TOPIC_COLDROOM)
            logger.info(f"Subscribed to Coldroom topic: {self.TOPIC_COLDROOM}")
            self._client.subscribe(self.TOPIC_CO2_SENSOR)
            logger.info(f"Subscribed to CO2 sensor topic: {self.TOPIC_CO2_SENSOR}")
        else:
            logger.error(f"Connection failed with result code {rc}")

    def on_message(self, client, userdata, msg):
        logger.info(f"Received MQTT message on topic: {msg.topic}")
        # logger.info(f"Payload: {msg.payload}")
        try:
            payload = msg.payload.decode()
            logger.info(f"Payload: {payload}")
        except:
            logger.error("Could not decode payload as string")
            return

        # Store msg.topic for use in handle_cleanroom_status_message
        self._current_topic = msg.topic
        logger.info(f"Current topic: {self._current_topic}")

        # Handle Cleanroom messages (with leading slash)
        if msg.topic.startswith(self.TOPIC_BASE_CLEANROOM[:-1]):
            logger.info(f"Processing Cleanroom environment message: {msg.topic}")
            self.handle_cleanroom_status_message(msg.payload)
            logger.info(f"Updated Cleanroom status: {self._cleanroom_status}")


        # Handle MARTA messages
        elif msg.topic.startswith(self.TOPIC_BASE_MARTA): # Add MARTA topic
            if "status" in msg.topic:
                logger.info("Processing MARTA status message")
                self.handle_marta_status_message(msg.payload)
                logger.info(f"Updated MARTA status: {self._marta_status}")

        # Handle Coldroom messages
        elif msg.topic.startswith(self.TOPIC_BASE_COLDROOM): # Add Coldroom topic
            if "state" in msg.topic:
                logger.info("Processing Coldroom state message")
                self.handle_coldroom_state_message(msg.payload)
                logger.info(f"Updated Coldroom state: {self._coldroom_state}")
        
        # Handle CO2 sensor messages
        elif msg.topic == self.TOPIC_CO2_SENSOR: # Add CO2 sensor topic
            logger.info("Processing CO2 sensor message")
            self.handle_co2_sensor_message(msg.payload)
            logger.info(f"Updated CO2 sensor data: {self._co2_sensor_data}")
        else:
            logger.warning(f"Received message on unknown topic: {msg.topic}")

        # Safety checks
        if self._system.has_valid_status():
            self._system.safety_flags["door_locked"] = not check_dew_point(self._system.status)
            self._system.safety_flags["sleep"] = check_door_status(self._system.status)
            logger.debug(f"Safety flags updated: {self._system.safety_flags}")

    def publish_cmd(self, command, target, payload):
        """
        Publish a command to either MARTA or Coldroom or Cleanroom
        
        Args:
            command (str): The command to send
            target (str): Either 'marta' or 'coldroom' or 'cleanroom'
            payload: The command payload
        """
        if target == 'marta': # Add MARTA topic
            topic = f"{self.TOPIC_BASE_MARTA}cmd/{command}"
        elif target == 'cleanroom': # Add cleanroom topic
            topic = f"{self.TOPIC_BASE_CLEANROOM}cmd/{command}"
        else:  # Add Coldroom topic
            topic = f"{self.TOPIC_BASE_COLDROOM}cmd/{command}"
        
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

    ### CLEANROOM ###

    def handle_cleanroom_status_message(self, payload):
        try:
            # Parse the payload
            data = json.loads(payload)
            logger.info(f"Processing cleanroom data: {data}")
            
            # Update cleanroom status based on topic
            if isinstance(data, dict):
                if "temperature" in data:
                    self._cleanroom_status["temperature"] = float(data["temperature"])
                    logger.info(f"Updated temperature: {self._cleanroom_status['temperature']}")
                if "RH" in data:
                    self._cleanroom_status["humidity"] = float(data["RH"])
                    logger.info(f"Updated humidity: {self._cleanroom_status['humidity']}")
                if "dewpoint" in data:
                    self._cleanroom_status["dewpoint"] = float(data["dewpoint"])
                    logger.info(f"Updated dewpoint: {self._cleanroom_status['dewpoint']}")
                if "Pressure" in data:
                    self._cleanroom_status["pressure"] = float(data["Pressure"])
                    logger.info(f"Updated pressure: {self._cleanroom_status['pressure']}")
            else:
                # Handle case where payload is a single value
                try:
                    value = float(data)
                    if "temperature" in self._current_topic:
                        self._cleanroom_status["temperature"] = value
                        logger.info(f"Updated temperature from single value: {value}")
                    elif "RH" in self._current_topic:
                        self._cleanroom_status["humidity"] = value
                        logger.info(f"Updated humidity from single value: {value}")
                    elif "dewpoint" in self._current_topic:
                        self._cleanroom_status["dewpoint"] = value
                        logger.info(f"Updated dewpoint from single value: {value}")
                    elif "Pressure" in self._current_topic:
                        self._cleanroom_status["pressure"] = value
                        logger.info(f"Updated pressure from single value: {value}")
                except (ValueError, TypeError):
                    logger.error(f"Could not convert payload to float: {data}")
            
            logger.info(f"Current cleanroom status: {self._cleanroom_status}")
            self._system.update_status({"cleanroom": self._cleanroom_status})
        except Exception as e:
            logger.error(f"Error parsing Cleanroom status message: {e}")
            logger.error(f"Payload was: {payload}")

    ### COLDROOM ###

    def handle_coldroom_state_message(self, payload):
        try:
            self._coldroom_state = json.loads(payload)
            logger.debug(f"Parsed Coldroom state: {self._coldroom_state}")
            
            # Update control states
            if "ch_temperature_status" in self._coldroom_state:
                self._coldroom_state["temperature_control"] = self._coldroom_state["ch_temperature_status"]
            if "ch_humidity_status" in self._coldroom_state:
                self._coldroom_state["humidity_control"] = self._coldroom_state["ch_humidity_status"]
                
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
    def cleanroom_status(self):
        return self._cleanroom_status

    @property
    def coldroom_state(self):
        return self._coldroom_state

    @property
    def door_locked(self):
        return self._system.safety_flags.get("door_locked", True)  # Default to True (safe) if not available

