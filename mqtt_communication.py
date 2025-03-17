import paho.mqtt.client as mqtt
import json
import time
import threading
import random
from datetime import datetime
import math
import signal
import argparse

class VirtualMQTTServer:
    def __init__(self):
        # Initialize MQTT clients
        self.publisher = mqtt.Client("virtual_server_pub")
        self.subscriber = mqtt.Client("virtual_server_sub")
        
        # Connect callbacks
        self.subscriber.on_connect = self.on_connect
        self.subscriber.on_message = self.on_message
        
        # Data storage
        self.sensor_data = {
            'clean_room': {
                'temperature': 23.0,
                'humidity': 45.0
            },
            'cold_room': {
                'temperature': 5.0,
                'humidity': 60.0,
                'target_temperature': 5.0,
                'target_humidity': 60.0,
                'light_state': 0,
                'run_state': 0,
                'temp_control': 0,
                'humidity_control': 0,
                'external_dry_air': 0,
                'door_state': 0,
                'co2_level': 400.0,
                'alarms': 0
            },
            'marta_co2_plant': {
                'temperature': 25.0,
                'humidity': 50.0,
                'co2_level': 400.0,
                'target_temperature': 25.0,
                'target_humidity': 50.0,
                'target_co2': 400.0,
                'state': 'CONNECTED',
                'flow_active': 0,
                'speed_setpoint': 0,
                'flow_setpoint': 0,
                'alarms': []
            }
        }
        
        # Control flags
        self.running = True
        self.transition_speed = 0.1  # Rate of change per second
        
        # Thread locks
        self.data_lock = threading.Lock()
        
        # Start server
        try:
            print("Starting Virtual MQTT Server on localhost:1883")
            
            # Connect both clients to localhost
            self.publisher.connect("127.0.0.1", 1883, keepalive=60)
            self.subscriber.connect("127.0.0.1", 1883, keepalive=60)
            
            # Start the subscriber loop in a separate thread
            self.subscriber_thread = threading.Thread(target=self.subscriber.loop_forever)
            self.subscriber_thread.daemon = True
            self.subscriber_thread.start()
            
            # Start publisher thread
            self.publisher_thread = threading.Thread(target=self.publish_data)
            self.publisher_thread.daemon = True
            self.publisher_thread.start()
            
            # Ensure MARTA is connected on startup
            with self.data_lock:
                self.sensor_data['marta_co2_plant']['state'] = 'CONNECTED'
            
            print("Virtual MQTT Server started successfully")
            
        except Exception as e:
            print(f"Failed to start MQTT server: {str(e)}")
            raise  # Re-raise the exception to handle it in the main thread
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Subscriber connected successfully")
            # Subscribe to command topics
            self.subscriber.subscribe("command/#")
            self.subscriber.subscribe("MARTA/cmd/#")
        else:
            print(f"Failed to connect with code {rc}")
    
    def on_message(self, client, userdata, message):
        try:
            # Parse command
            topic_parts = message.topic.split('/')
            
            if topic_parts[0] == "command":
                room = topic_parts[1]
                parameter = topic_parts[2]
                
                # Parse target value
                payload = message.payload.decode()
                
                # Handle boolean values for control states
                if parameter in ['temp_control', 'humidity_control']:
                    target_value = payload.lower() == 'true' or payload == '1'
                else:
                    try:
                        target_value = float(payload)
                    except ValueError:
                        target_value = 1 if payload.lower() == 'true' else 0
                
                # Update target value with thread safety
                with self.data_lock:
                    if room == "cold_room":
                        if parameter == "temperature" and self.sensor_data[room]['temp_control']:
                            self.sensor_data[room]['target_temperature'] = target_value
                            print(f"Received command to set {room} temperature to {target_value}°C")
                        elif parameter == "humidity" and self.sensor_data[room]['humidity_control']:
                            self.sensor_data[room]['target_humidity'] = target_value
                            print(f"Received command to set {room} humidity to {target_value}%")
                        elif parameter == "light":
                            self.sensor_data[room]['light_state'] = int(target_value)
                            print(f"Setting cold room light: {'ON' if target_value else 'OFF'}")
                        elif parameter == "run":
                            self.sensor_data[room]['run_state'] = int(target_value)
                            print(f"Setting cold room run state: {'ON' if target_value else 'OFF'}")
                        elif parameter == "temp_control":
                            self.sensor_data[room]['temp_control'] = target_value
                            print(f"Setting temperature control: {'ON' if target_value else 'OFF'}")
                        elif parameter == "humidity_control":
                            self.sensor_data[room]['humidity_control'] = target_value
                            print(f"Setting humidity control: {'ON' if target_value else 'OFF'}")
                        elif parameter == "external_dry_air":
                            self.sensor_data[room]['external_dry_air'] = int(target_value)
                            print(f"Setting external dry air: {'ON' if target_value else 'OFF'}")
                        elif parameter == "door":
                            self.sensor_data[room]['door_state'] = int(target_value)
                            print(f"Setting door: {'ON' if target_value else 'OFF'}")
                    elif room == "marta_co2_plant":
                        if parameter == "co2":
                            self.sensor_data[room]['target_co2'] = target_value
                            print(f"Received command to set CO2 level to {target_value} ppm")
            
            elif topic_parts[0] == "MARTA" and topic_parts[1] == "cmd":
                command = topic_parts[2]
                value = message.payload.decode()
                
                with self.data_lock:
                    marta_data = self.sensor_data['marta_co2_plant']
                    
                    if command == "start_chiller":
                        marta_data['state'] = 'CHILLER_RUNNING'
                        print("MARTA: Starting chiller")
                    elif command == "start_co2":
                        if marta_data['state'] == 'CHILLER_RUNNING':
                            marta_data['state'] = 'CO2_RUNNING'
                            print("MARTA: Starting CO2")
                    elif command == "stop_co2":
                        if marta_data['state'] == 'CO2_RUNNING':
                            marta_data['state'] = 'CHILLER_RUNNING'
                            print("MARTA: Stopping CO2")
                    elif command == "stop_chiller":
                        marta_data['state'] = 'CONNECTED'
                        print("MARTA: Stopping chiller")
                    elif command == "set_flow_active":
                        marta_data['flow_active'] = int(value)
                        print(f"MARTA: Setting flow active to {value}")
                    elif command == "set_temperature_setpoint":
                        temp = float(value)
                        if -35 <= temp <= 25:
                            marta_data['target_temperature'] = temp
                            print(f"MARTA: Setting temperature setpoint to {temp}°C")
                    elif command == "set_speed_setpoint":
                        speed = float(value)
                        if 0 <= speed <= 6000:
                            marta_data['speed_setpoint'] = speed
                            print(f"MARTA: Setting speed setpoint to {speed}")
                    elif command == "set_flow_setpoint":
                        flow = float(value)
                        if 0 <= flow <= 5:
                            marta_data['flow_setpoint'] = flow
                            print(f"MARTA: Setting flow setpoint to {flow}")
                    elif command == "clear_alarms":
                        marta_data['alarms'] = []
                        print("MARTA: Clearing alarms")
                    elif command == "reconnect":
                        marta_data['state'] = 'CONNECTED'
                        print("MARTA: Reconnecting")
                
        except Exception as e:
            print(f"Error processing command: {str(e)}")
    
    def publish_data(self):
        while self.running:
            try:
                # Update and publish data for each room with thread safety
                with self.data_lock:
                    for room, data in self.sensor_data.items():
                        # Update temperature (with some random variation)
                        current_temp = data['temperature']
                        if room == 'cold_room' and data['temp_control']:
                            target_temp = data['target_temperature']
                            if abs(current_temp - target_temp) > 0.1:
                                direction = 1 if target_temp > current_temp else -1
                                data['temperature'] += direction * self.transition_speed
                        elif room == 'marta_co2_plant':
                            target_temp = data['target_temperature']
                            if abs(current_temp - target_temp) > 0.1:
                                direction = 1 if target_temp > current_temp else -1
                                data['temperature'] += direction * self.transition_speed
                        data['temperature'] += random.uniform(-0.1, 0.1)
                        
                        # Update humidity (with some random variation)
                        current_humid = data['humidity']
                        if room == 'cold_room' and data['humidity_control']:
                            target_humid = data['target_humidity']
                            if abs(current_humid - target_humid) > 0.1:
                                direction = 1 if target_humid > current_humid else -1
                                data['humidity'] += direction * self.transition_speed
                        elif room == 'marta_co2_plant':
                            target_humid = data['target_humidity']
                            if abs(current_humid - target_humid) > 0.1:
                                direction = 1 if target_humid > current_humid else -1
                                data['humidity'] += direction * self.transition_speed
                        data['humidity'] += random.uniform(-0.2, 0.2)
                        
                        # Update CO2 for MARTA plant and cold room
                        if room in ['marta_co2_plant', 'cold_room']:
                            current_co2 = data['co2_level']
                            target_co2 = data['target_co2'] if room == 'marta_co2_plant' else 400.0  # Fixed target for cold room
                            if abs(current_co2 - target_co2) > 1:
                                direction = 1 if target_co2 > current_co2 else -1
                                data['co2_level'] += direction * self.transition_speed * 5
                            data['co2_level'] += random.uniform(-2, 2)
                            
                            # Publish MARTA status
                            if room == 'marta_co2_plant':
                                status_payload = {
                                    'state': data['state'],
                                    'temperature': round(data['temperature'], 2),
                                    'humidity': round(data['humidity'], 2),
                                    'co2_level': round(data['co2_level'], 2),
                                    'flow_active': data['flow_active'],
                                    'speed_setpoint': data['speed_setpoint'],
                                    'flow_setpoint': data['flow_setpoint'],
                                    'alarms': data['alarms'],
                                    'timestamp': datetime.now().astimezone().isoformat()
                                }
                                self.publisher.publish("MARTA/status", json.dumps(status_payload))
                        
                        try:
                            # Get current time with timezone info
                            current_time = datetime.now().astimezone()
                            
                            # Publish temperature
                            temp_payload = {
                                'value': round(data['temperature'], 2),
                                'timestamp': current_time.isoformat()
                            }
                            self.publisher.publish(f"{room}/temperature", json.dumps(temp_payload))
                            
                            # Publish humidity
                            humid_payload = {
                                'value': round(data['humidity'], 2),
                                'timestamp': current_time.isoformat()
                            }
                            self.publisher.publish(f"{room}/humidity", json.dumps(humid_payload))
                            
                            # Publish additional cold room sensors
                            if room == 'cold_room':
                                # Publish CO2
                                co2_payload = {
                                    'value': round(data['co2_level'], 2),
                                    'timestamp': current_time.isoformat()
                                }
                                self.publisher.publish(f"{room}/co2", json.dumps(co2_payload))
                                
                                # Publish binary states
                                for state in ['light_state', 'run_state', 'door_state', 'alarms',
                                            'temp_control', 'humidity_control', 'external_dry_air']:
                                    state_payload = {
                                        'value': data[state],
                                        'timestamp': current_time.isoformat()
                                    }
                                    self.publisher.publish(f"{room}/{state}", json.dumps(state_payload))
                            
                            # Publish CO2 for MARTA plant
                            if room == 'marta_co2_plant':
                                co2_payload = {
                                    'value': round(data['co2_level'], 2),
                                    'timestamp': current_time.isoformat()
                                }
                                self.publisher.publish(f"{room}/co2", json.dumps(co2_payload))
                        except Exception as e:
                            print(f"Error publishing data: {str(e)}")
                            continue
                
                # Add some simulated sensor data
                for i in range(1, 4):
                    try:
                        current_time = datetime.now().astimezone()
                        sensor_payload = {
                            'value': 10 * math.sin(time.time() / 10) + random.uniform(-1, 1),
                            'timestamp': current_time.isoformat()
                        }
                        self.publisher.publish(f"sensor{i}/raw_data", json.dumps(sensor_payload))
                    except Exception as e:
                        print(f"Error publishing sensor data: {str(e)}")
                        continue
                
                # Sleep for a short interval
                time.sleep(1)
                
            except Exception as e:
                print(f"Error in publish loop: {str(e)}")
                time.sleep(1)
    
    def stop(self):
        print("Stopping server...")
        self.running = False
        
        # Stop MQTT clients
        try:
            self.subscriber.loop_stop()
            self.subscriber.disconnect()
            self.publisher.disconnect()
        except:
            pass
        
        print("Server stopped")

def signal_handler(signum, frame):
    print("\nSignal received, stopping server...")
    if 'server' in globals():
        server.stop()
    exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        server = VirtualMQTTServer()
        
        # Keep the main thread running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
    except Exception as e:
        print(f"Error: {str(e)}")
        server.stop()
