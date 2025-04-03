import os
import yaml

with open(os.path.join(os.path.dirname(__file__), "safety_cfg.yaml"), "r") as f:
    safety_settings = yaml.safe_load(f)

### Safety functions ###
# Example of a safety function
# def check_dummy_condition(*args, **kwargs):
#     # Dummy condition check
#     return True


def check_dew_point(system_status):
    internal_temperatures = safety_settings["internal_temperatures"]
    if system_status["coldroom"]["door_status"] == 1:  # Door is open
        reference_dew_point = system_status["environment"]["HumAndTemp001"]["dewpoint"]  # External dewpoint
    else:  # Door is closed
        reference_dew_point = system_status["coldroom"]["dew_point_c"]
    min_temperature = float("inf")
    for subsystem in system_status.values():
        for temperature in internal_temperatures:
            if temperature in subsystem:
                min_temperature = min(min_temperature, subsystem[temperature])
    return min_temperature > reference_dew_point


def check_door_status(system_status):
    return system_status["coldroom"]["door_status"] == 1  # Door is open


def check_light_status(system_status):
    return system_status["coldroom"]["light"] == 1  # Light is on


def check_hv_safe(system_status):
    lv_on = True
    for channel in system_status["caen"]:
        if channel.endswith("LV"):
            if system_status["caen"][channel]["isOn"]:
                lv_on = False
                break
    light_on = check_light_status(system_status)
    door_open = check_door_status(system_status)
    is_safe = lv_on and (not light_on) and (not door_open)
    return is_safe
