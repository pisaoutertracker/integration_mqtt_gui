import struct
import json
import paho.mqtt.client as mqtt
import base64
import time
import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable

from .stitching import process_all_cameras


class ThermalCameraMQTTClient:
    """MQTT client for controlling a thermal camera system."""

    BROKER = "192.168.0.45"
    PORT = 1883
    TOPIC_BASE = "/thermalcamera/#"

    def __init__(self):
        self._running = False
        self._position = 0
        self._switch_state = False
        self._streaming = False
        self._stitching_data = {}
        self._images = {f"camera{i}": np.random.rand(32, 24) for i in range(4)}
        self.__init_cameras_pic()

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "thermalcam")
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message
        self._client.connect(self.BROKER, self.PORT)

    def on_connect(self, client, userdata, flags, rc):
        self._client.subscribe(self.TOPIC_STATE)
        self._client.subscribe(self.TOPIC_BASE)

    def on_message(self, client, userdata, msg):
        if msg.topic.startswith("thermalcamera/state"):
            self.handle_state_message(msg.payload)
        elif msg.topic.startswith("thermalcamera/camera"):
            self.handle_camera_message(msg.topic, json.loads(msg.payload))
        else:
            pass

    def handle_state_message(self, payload):
        """Handle incoming state messages."""
        state_dict = json.loads(payload)
        self._running = state_dict["running"]
        self._position = state_dict["position"]
        self._switch_state = state_dict["switch_state"]
        self._streaming = state_dict["streaming"]

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
        self._client.publish(f"thermalcamera/cmd/{command}", payload)

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

    ### Properties ###
    @property
    def running(self):
        return self._running

    @property
    def position(self):
        return self._position

    @property
    def switch_state(self):
        return self._switch_state

    @property
    def streaming(self):
        return self._streaming

    @property
    def fig_cameras(self):
        return self._fig_cameras

    @property
    def client(self):
        return self._client

    @property
    def stitched_figures(self):
        return self._stitched_figures

    ### MQTT Client Loop ###
    def loop_start(self):
        self._client.loop_start()
