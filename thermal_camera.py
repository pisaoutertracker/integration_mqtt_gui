import struct
import json
import paho.mqtt.client as mqtt
import base64
import time
import numpy as np

# Set matplotlib backend to Qt5Agg before importing matplotlib components
import matplotlib
matplotlib.use('Qt5Agg')

from matplotlib import pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable

from image_stitching import process_all_cameras


class ThermalCameraMQTTClient:

    def __init__(self, system_obj):
        self._system = system_obj
        self.TOPIC = system_obj.settings["ThermalCamera"]["mqtt_topic"]
        self.TOPIC_BASE = self.TOPIC.replace("#", "")

        self._stitching_data = {}
        self._images = {f"camera{i}": np.random.rand(32, 24) for i in range(4)}
        self.__init_cameras_pic()

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "thermalcam")
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message
        self._client.connect(self._system.BROKER, self._system.PORT)

    def on_connect(self, client, userdata, flags, rc):
        self._client.subscribe(self.TOPIC)

    def on_message(self, client, userdata, msg):
        if msg.topic.startswith(f"{self.TOPIC_BASE}/state"):
            self.handle_state_message(msg.payload)
        elif msg.topic.startswith(f"{self.TOPIC_BASE}/camera"):
            self.handle_camera_message(msg.topic, json.loads(msg.payload))
        else:
            pass

    def handle_state_message(self, payload):
        """Handle incoming state messages."""
        self._status = json.loads(payload)
        self._system.update_status({"thermal_camera": self._status})

    def handle_camera_message(self, topic, payload):
        camera_name = topic.split("/")[2]
        response = json.loads(payload)
        image_data = base64.b64decode(response["image"])
        position = float(response["position"])
        flo_arr = [struct.unpack("f", image_data[i : i + 4])[0] for i in range(0, len(image_data), 4)]
        processed_image = np.flip(np.rot90(np.array(flo_arr).reshape(24, 32)), axis=0)
        if camera_name not in self._stitching_data:
            self._stitching_data[camera_name] = {}
        if position not in self._stitching_data[camera_name]:
            self._stitching_data[camera_name][position] = []
        self._stitching_data[camera_name][position].append(processed_image)
        self._images[camera_name].set_data(processed_image)
        self._images[camera_name].set_clim(min(flo_arr), max(flo_arr))
        plt.draw()

    def publish_cmd(self, command, params=None):
        """Publish a command to the MQTT broker."""
        if params is None:
            params = {}
        payload = json.dumps(params)
        self._client.publish(f"{self.TOPIC_BASE}/cmd/{command}", payload)

    ### Commands ###
    def rotate(self, payload):
        self.publish_cmd("rotate", payload)

    def go_to(self, payload):
        self.publish_cmd("go_to", payload)

    def calibrate(self, payload):
        self.publish_cmd("calibrate", payload)

    def get_switch_state(self, payload):
        self.publish_cmd("get_switch_state", payload)

    def set_absolute_position(self, payload):
        self.publish_cmd("set_absolute_position", payload)

    def export_absolute_position(self, payload):
        self.publish_cmd("export_absolute_position", payload)

    def import_absolute_position(self, payload):
        self.publish_cmd("import_absolute_position", payload)

    def get_frame(self, payload):
        self.publish_cmd("get_frame", payload)

    def get_frames(self, payload):
        self.publish_cmd("get_frames", payload)

    def init(self, payload):
        self.publish_cmd("init", payload)

    def release(self, payload):
        self.publish_cmd("release", payload)

    def run(self, payload):
        self.publish_cmd("run", payload)

    def stop(self, payload):
        self.publish_cmd("stop", payload)

    ### Pictures ###
    def __init_cameras_pic(self):
        self._fig_cameras, self._axs_cameras = plt.subplots(2, 2, figsize=(10, 8))
        self._images = [
            self._axs_cameras[i, j].imshow(self._images[f"camera{i*2+j}"], cmap="plasma")
            for i in range(2)
            for j in range(2)
        ]
        self._cbar = [
            make_axes_locatable(self._axs_cameras[i, j]).append_axes("right", size="5%", pad=0.05)
            for i in range(2)
            for j in range(2)
        ]
        self._cbar = [self._fig_cameras.colorbar(self._images[i], cax=self._cbar[i]) for i in range(4)]
        self._titles = [self._axs_cameras[i, j].set_title(f"Camera {i*2+j}") for i in range(2) for j in range(2)]

    def __stitching(self):
        self._stitched_figures = process_all_cameras(self._stitching_data)

    ### MQTT Client Loop ###
    def loop_start(self):
        self._client.loop_start()
