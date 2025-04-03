import json
import paho.mqtt.client as mqtt

from .safety import *


class MartaColdRoomMQTTClient:

    def __init__(self, system_obj):
        self._system = system_obj
        # MARTA
        self.TOPIC_MARTA = system_obj.settings["MARTA"]["mqtt_topic"]
        self.TOPIC_BASE_MARTA = self.TOPIC_MARTA.replace("#", "")
        self._marta_client = mqtt.Client()
        self._marta_client.on_connect = self.on_connect
        self._marta_client.on_message = self.on_message
        self._marta_client.connect(self._system.BROKER, self._system.PORT)
        self._marta_status = {}
        # Coldroom
        self.TOPIC_COLDROOM = system_obj.settings["Coldroom"]["mqtt_topic"]
        self.TOPIC_BASE_COLDROOM = self.TOPIC_COLDROOM.replace("#", "")
        self._coldroom_client = mqtt.Client("COLDROOM")
        self._coldroom_client.on_connect = self.on_connect
        self._coldroom_client.on_message = self.on_message
        self._coldroom_client.connect(self._system.BROKER, self._system.PORT)
        self._coldroom_state = {}

    def on_connect(self, client, userdata, flags, rc):
        if client == self._marta_client:
            self._marta_client.subscribe(self.TOPIC_MARTA)
        elif client == self._coldroom_client:
            self._coldroom_client.subscribe(self.TOPIC_COLDROOM)

    def on_message(self, client, userdata, msg):

        if client == self._marta_client:
            if msg.topic.startswith(f"{self.TOPIC_BASE_MARTA}/status"):
                self.handle_marta_status_message(msg.payload)
        elif client == self._coldroom_client:
            if msg.topic.startswith(f"{self.TOPIC_BASE_COLDROOM}/state"):
                self.handle_coldroom_state_message(msg.payload)
        else:
            pass

        # Safety checks
        if self._system.has_valid_status():
            self._system._safety_flags["door_locked"] = not check_dew_point(self._system.status)
            self._system._safety_flags["sleep"] = check_door_status(self._system.status)

    def publish_cmd(self, command, client, payload):
        if client == self._marta_client:
            self._marta_client.publish(f"{self.TOPIC_BASE_MARTA}/cmd/{command}", payload)
        elif client == self._coldroom_client:
            self._coldroom_client.publish(f"{self.TOPIC_BASE_COLDROOM}/cmd/{command}", payload)
        else:
            pass

    ### MARTA ###

    def handle_marta_status_message(self, payload):
        self._marta_status = json.loads(payload)
        self._system.update_status({"marta": self._marta_status})

    ## Commands ##

    def start_chiller(self, payload):
        self.publish_cmd("start_chiller", self._marta_client, payload)

    def start_co2(self, payload):
        self.publish_cmd("start_co2", self._marta_client, payload)

    def stop_co2(self, payload):
        self.publish_cmd("stop_co2", self._marta_client, payload)

    def stop_chiller(self, payload):
        self.publish_cmd("stop_chiller", self._marta_client, payload)

    def set_flow_active(self, payload):
        self.publish_cmd("set_flow_active", self._marta_client, payload)

    def set_temperature_setpoint(self, payload):
        self.publish_cmd("set_temperature_setpoint", self._marta_client, payload)

    def set_speed_setpoint(self, payload):
        self.publish_cmd("set_speed_setpoint", self._marta_client, payload)

    def set_flow_setpoint(self, payload):
        self.publish_cmd("set_flow_setpoint", self._marta_client, payload)

    def clear_alarms(self, payload):
        self.publish_cmd("clear_alarms", self._marta_client, payload)

    def reconnect(self, payload):
        self.publish_cmd("reconnect", self._marta_client, payload)

    def refresh(self, payload):
        self.publish_cmd("refresh", self._marta_client, payload)

    ### COLDROOM ###

    def handle_coldroom_state_message(self, payload):
        self._coldroom_state = json.loads(payload)
        self._system.update_status({"coldroom": self._coldroom_state})

    ## Commands ##

    def set_temperature(self, payload):
        self.publish_cmd("set_temperature", self._coldroom_client, payload)

    def set_humidity(self, payload):
        self.publish_cmd("set_humidity", self._coldroom_client, payload)

    def control_light(self, payload):
        self.publish_cmd("control_light", self._coldroom_client, payload)

    def control_temperature(self, payload):
        self.publish_cmd("control_temperature", self._coldroom_client, payload)

    def control_humidity(self, payload):
        self.publish_cmd("control_humidity", self._coldroom_client, payload)

    def control_external_dry_air(self, payload):
        self.publish_cmd("control_external_dry_air", self._coldroom_client, payload)

    def reset_alarms(self, payload):
        self.publish_cmd("reset_alarms", self._coldroom_client, payload)

    def run(self, payload):
        self.publish_cmd("run", self._coldroom_client, payload)

    def stop(self, payload):
        self.publish_cmd("stop", self._coldroom_client, payload)

    ### Properties ###
    @property
    def marta_status(self):
        return self._marta_status

    @property
    def coldroom_state(self):
        return self._coldroom_state

    @property
    def door_locked(self):
        return self._door_locked
