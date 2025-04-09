import json
import paho.mqtt.client as mqtt
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CleanRoomMQTTClient:
    def __init__(self, system_obj):
        self._system = system_obj
        
        # Initialize topics
        self.TOPIC = system_obj.settings["Cleanroom"]["mqtt_topic"]
        self.TOPIC_BASE = self.TOPIC.replace("#", "")
        
        logger.debug("Initializing Cleanroom MQTT client with topic:")
        logger.debug(f"Cleanroom topic: {self.TOPIC}")
        
        # Create MQTT client
        self._client = mqtt.Client(client_id="CLEANROOM")
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message
        
        # Initialize status dictionary
        self._status = {}
        
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
            # Subscribe to cleanroom topic
            self._client.subscribe(self.TOPIC)
            logger.debug(f"Subscribed to Cleanroom topic: {self.TOPIC}")
        else:
            logger.error(f"Connection failed with result code {rc}")

    def on_message(self, client, userdata, msg):
        logger.debug(f"Received MQTT message on topic: {msg.topic}")
        try:
            payload = msg.payload.decode()
            logger.debug(f"Payload: {payload}")
        except:
            logger.error("Could not decode payload as string")

        # Handle Cleanroom messages
        if msg.topic.startswith(self.TOPIC_BASE):
            if "status" in msg.topic:
                logger.debug("Processing Cleanroom status message")
                self.handle_status_message(msg.payload)
                logger.debug(f"Updated Cleanroom status: {self._status}")

    def handle_status_message(self, payload):
        try:
            self._status = json.loads(payload)
            logger.debug(f"Parsed Cleanroom status: {self._status}")
            self._system.update_status({"cleanroom": self._status})
        except Exception as e:
            logger.error(f"Error parsing Cleanroom status message: {e}")

    def publish_cmd(self, command, payload):
        """
        Publish a command to the cleanroom
        
        Args:
            command (str): The command to send
            payload: The command payload
        """
        topic = f"{self.TOPIC_BASE}cmd/{command}"
        logger.info(f"Sending command '{command}' to cleanroom with payload: {payload}")
        self._client.publish(topic, payload)

    @property
    def status(self):
        return self._status 