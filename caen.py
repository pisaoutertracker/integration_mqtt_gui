import json
import paho.mqtt.client as mqtt

from safety import *


class CaenMQTTClient:

    def __init__(self, system_obj):
        self._system = system_obj
        self.TOPIC = system_obj.settings["Caen"]["mqtt_topic"]
        self._status = {}

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "CAEN")
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message
        self._client.connect(self._system.BROKER, self._system.PORT)
        
        # Start client loop
        self.start_client_loop()

    def start_client_loop(self):
        """Start the MQTT client loop to process network traffic"""
        self._client.loop_start()
        
    def stop_client_loop(self):
        """Stop the MQTT client loop"""
        self._client.loop_stop()

    def on_connect(self, client, userdata, flags, rc):
        self._client.subscribe(self.TOPIC)

    def on_message(self, client, userdata, msg):
        self.handle_caen_message(msg.payload)

        # Safety checks
        if self._system.has_valid_status():
            self._system.safety_flags["hv_safe"] = check_hv_safe(self._system.status)
            # Add more safety checks as needed

    def handle_caen_message(self, payload):
        self._status = json.loads(payload)
        self._system.update_status({"caen": self._status})

    ### Logic to control with the CAEN (not via MQTT) ###
