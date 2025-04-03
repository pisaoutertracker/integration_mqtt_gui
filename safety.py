import os
import yaml

try:
    with open(os.path.join(os.path.dirname(__file__), "safety_cfg.yaml"), "r") as f:
        safety_settings = yaml.safe_load(f)
except Exception as e:
    print(f"Warning: Could not load safety_cfg.yaml: {str(e)}")
    safety_settings = {"internal_temperatures": ["TT_1"]}

### Safety functions ###
# Example of a safety function
# def check_dummy_condition(*args, **kwargs):
#     # Dummy condition check
#     return True


def check_dew_point(system_status):
    try:
        internal_temperatures = safety_settings.get("internal_temperatures", [])
        
        if "coldroom" not in system_status or "door_status" not in system_status["coldroom"]:
            return False  # Conservative approach - if we can't check, assume it's unsafe
            
        if system_status["coldroom"]["door_status"] == 1:  # Door is open
            # Check if environment data exists
            if "environment" not in system_status or "HumAndTemp001" not in system_status["environment"]:
                return False  # Conservative approach
            reference_dew_point = system_status["environment"]["HumAndTemp001"]["dewpoint"]  # External dewpoint
        else:  # Door is closed
            if "dew_point_c" not in system_status["coldroom"]:
                return False  # Conservative approach
            reference_dew_point = system_status["coldroom"]["dew_point_c"]
            
        min_temperature = float("inf")
        for subsystem in system_status.values():
            for temperature in internal_temperatures:
                if temperature in subsystem:
                    min_temperature = min(min_temperature, subsystem[temperature])
                    
        # If no temperatures were found, be conservative
        if min_temperature == float("inf"):
            return False
            
        return min_temperature > reference_dew_point
    except Exception as e:
        print(f"Error in check_dew_point: {str(e)}")
        return False  # Conservative approach


def check_door_status(system_status):
    try:
        if "coldroom" not in system_status or "door_status" not in system_status["coldroom"]:
            return False  # Conservative approach
        return system_status["coldroom"]["door_status"] == 1  # Door is open
    except Exception as e:
        print(f"Error in check_door_status: {str(e)}")
        return False  # Conservative approach


def check_light_status(system_status):
    try:
        if "coldroom" not in system_status or "light" not in system_status["coldroom"]:
            return False  # Conservative approach
        return system_status["coldroom"]["light"] == 1  # Light is on
    except Exception as e:
        print(f"Error in check_light_status: {str(e)}")
        return False  # Conservative approach


def check_hv_safe(system_status):
    try:
        if "caen" not in system_status:
            return False  # Conservative approach
            
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
    except Exception as e:
        print(f"Error in check_hv_safe: {str(e)}")
        return False  # Conservative approach
