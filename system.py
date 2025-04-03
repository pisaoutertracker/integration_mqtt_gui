import os
import yaml
from .thermal_camera import ThermalCameraMQTTClient
from .marta_coldroom import MartaColdRoomMQTTClient
from .caen import CaenMQTTClient


class System:
    def __init__(self):
        # Settings
        self._settings = {}
        with open(os.path.join(os.path.dirname(__file__), "settings.yaml"), "r") as f:
            self.settings = yaml.safe_load(f)

        # Global variables
        self.BROKER = self.settings["mqtt"]["broker"]
        self.PORT = self.settings["mqtt"]["port"]
        self._status = {"marta": {}, "coldroom": {}, "thermal_camera": {}}
        self.safety_flags = {"door_locked": True, "sleep": True, "hv_safe": False}  # Default value to safest state

        # Initialize MQTT clients
        self._martacoldroom = MartaColdRoomMQTTClient(system=self)
        self._thermalcamera = ThermalCameraMQTTClient(system=self)
        self._caen = CaenMQTTClient(system=self)

    @property
    def settings(self):
        return self._settings

    @property
    def status(self):
        return self._status

    def update_status(self, status):
        try:
            assert isinstance(status, dict)
            self._status.update(status)
        except AssertionError:
            pass

    def has_valid_status(self):
        is_valid = True
        for subsystem in self._status.values():
            if subsystem == {}:
                is_valid = False
                break
        return is_valid
