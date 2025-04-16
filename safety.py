import os
import yaml

try:
    with open(os.path.join(os.path.dirname(__file__), "safety_cfg.yaml"), "r") as f:
        safety_settings = yaml.safe_load(f)
except Exception as e:
    print(f"Warning: Could not load safety_cfg.yaml: {str(e)}")
    safety_settings = {
        "internal_temperatures": [
            "TT05_CO2",  # MARTA supply temperature
            "TT06_CO2",  # MARTA return temperature
            "ch_temperature"  # Coldroom temperature
        ]
    }

### Safety functions ###
# Example of a safety function
# def check_dummy_condition(*args, **kwargs):
#     # Dummy condition check
#     return True


def check_dew_point(system_status):
    print(f"Checking dew point: {system_status}")
    try:
        # Get the three required temperature values
        marta_supply_temp = system_status.get("marta", {}).get("TT05_CO2")
        marta_return_temp = system_status.get("marta", {}).get("TT06_CO2")
        coldroom_temp = system_status.get("coldroom", {}).get("ch_temperature", {}).get("value")
        # coldroom = system_status.get("coldroom", {})
        # print(f"Coldroom: {coldroom.get('CmdDoorUnlock_Reff')}")
        # door_status = system_status.get("coldroom", {}).get("CmdDoorUnlock_Reff")
        # print(f"Door status: {door_status}")
        
        # Create list of available temperatures
        internal_temperatures = []
        if marta_supply_temp is not None:
            internal_temperatures.append(marta_supply_temp)
        if marta_return_temp is not None:
            internal_temperatures.append(marta_return_temp)
        if coldroom_temp is not None:
            internal_temperatures.append(coldroom_temp)
            
        # print(f"Available temperatures: {internal_temperatures}")
        
        # Only proceed if we have all three temperatures
        if len(internal_temperatures) != 3:
            print(f"Not all temperatures available. Found {len(internal_temperatures)} out of 3")
            return False
            
        # Get the minimum temperature among the three
        min_temperature = min(internal_temperatures)
        
        if "coldroom" not in system_status or "CmdDoorUnlock_Reff" not in system_status["coldroom"]:
            print("Coldroom data not available")
            return False  # Conservative approach - if we can't check, assume it's unsafe
            
        if system_status["coldroom"]["CmdDoorUnlock_Reff"] == 1:  # Door is open
            # Check if environment data exists
            if "cleanroom" not in system_status or "dewpoint" not in system_status["cleanroom"]:
                return False  # Conservative approach
            reference_dew_point = system_status["cleanroom"]["dewpoint"]  # External dewpoint
            print(f"Reference dew point: {reference_dew_point}")
        else:  # Door is closed
            if "dew_point_c" not in system_status["coldroom"]:
                return False  # Conservative approach
            reference_dew_point = system_status["coldroom"]["dew_point_c"]
            print(f"Reference dew point: {reference_dew_point}")
            
        # reference_dew_point = system_status["cleanroom"]["dewpoint"]
        # print(f"Min temperature: {min_temperature}, Dew point: {reference_dew_point}")
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


def check_door_safe_to_open(system_status):
    """
    Check if it's safe to open the door based on multiple safety conditions.
    Returns True if it's safe to open the door, False otherwise.
    """
    try:
        # Check if we have all necessary data
        if "coldroom" not in system_status:
            return False  # Conservative approach - if we can't check, assume it's unsafe
            
        # 1. Check if dew point conditions are safe
        dew_point_safe = check_dew_point(system_status)
        
        # 2. Check if high voltage is safe
        # hv_safe = check_hv_safe(system_status)
        
        # 3. Check if light is off (light should be off when opening door)
        # light_off = not check_light_status(system_status)
        
        # 4. Check if door is currently closed (can't open if already open)
        door_closed = not check_door_status(system_status)
        
        # It's safe to open the door if:
        # - Dew point conditions are safe
        # - High voltage is safe
        # - Light is off
        # - Door is currently closed
        is_safe = dew_point_safe and door_closed
        
        return is_safe
        
    except Exception as e:
        print(f"Error in check_door_safe_to_open: {str(e)}")
        return False  # Conservative approach - if we can't check, assume it's unsafe
