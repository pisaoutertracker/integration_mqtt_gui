import sys
import os
import yaml
import logging
from PyQt5 import QtWidgets, uic, QtGui
from PyQt5.QtCore import Qt, QTimer
from system import System
from caenGUI import caenGUI
from thermal_camera_tab import ThermalCameraTab


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MainApp(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainApp, self).__init__()
        
        # Create system instance to hold references to all components
        self.system = System()
        
        # Set up the main UI
        self.setup_ui()
        
        # Connect signals and slots
        self.connect_signals()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_ui)
        self.update_timer.start(1000)  # Update every second
        
        # Connect to MQTT broker at startup
        self.connect_mqtt()
    
    def closeEvent(self, event):
        """Handle application close event"""
        try:
            logger.info("Application closing, cleaning up resources...")
            
            # Stop the update timer
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
                logger.debug("Stopped update timer")
            
            # Cleanup CAEN GUI if it exists
            if hasattr(self, 'caen_gui'):
                self.caen_gui.cleanup()
                logger.debug("Cleaned up CAEN GUI")
            
            # Cleanup Thermal Camera tab if it exists
            if hasattr(self, 'thermal_camera_tab'):
                self.thermal_camera_tab.cleanup()
                logger.debug("Cleaned up Thermal Camera tab")
            
            # Cleanup MQTT connection
            if hasattr(self, 'system') and hasattr(self.system, 'mqtt_client'):
                self.system.mqtt_client.disconnect()
                self.system.mqtt_client.loop_stop()
                logger.debug("Disconnected MQTT client")
            
            # Cleanup MARTA Cold Room client
            if hasattr(self, 'system') and hasattr(self.system, '_martacoldroom'):
                self.system._martacoldroom.disconnect()
                logger.debug("Disconnected MARTA Cold Room client")
            
            # Cleanup system resources
            if hasattr(self, 'system'):
                self.system.cleanup()
                logger.debug("Cleaned up system resources")
            
            # Close all tabs
            if hasattr(self, 'tab_widget'):
                for i in range(self.tab_widget.count()):
                    widget = self.tab_widget.widget(i)
                    if hasattr(widget, 'cleanup'):
                        widget.cleanup()
                logger.debug("Cleaned up all tabs")
            
            logger.info("All resources cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            # Still accept the close event even if cleanup fails
            event.accept()
            return
        
        # Accept the close event
        event.accept()
    
    def setup_ui(self):
        # Create main window with tab widget
        self.setWindowTitle("Integration MQTT GUI")
        self.resize(1200, 800)
        
        # Create central widget and layout
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.central_widget)
        
        # Create tab widget
        self.tab_widget = QtWidgets.QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # Load the MARTA Cold Room tab from UI file
        # Create a temporary QMainWindow to load the UI
        temp_window = QtWidgets.QMainWindow()
        marta_ui_file = os.path.join("MARTA_Cold_Room_TAB", "marta_coldroom_tab.ui")
        uic.loadUi(marta_ui_file, temp_window)
        
        # Create a QWidget for our tab and get the central widget from temp_window
        self.marta_coldroom_tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.marta_coldroom_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Move the central widget from temp_window to our tab
        central_widget = temp_window.centralWidget()
        central_widget.setParent(self.marta_coldroom_tab)
        layout.addWidget(central_widget)
        
        # Add the tab to the tab widget
        self.tab_widget.addTab(self.marta_coldroom_tab, "MARTA Cold Room")
        
        # Add CAEN tab
        self.caen_tab = QtWidgets.QWidget()
        self.setup_caen_tab()
        self.tab_widget.addTab(self.caen_tab, "CAEN Control")
        
        # Add Thermal Camera tab
        self.thermal_camera_tab = ThermalCameraTab(self.system)
        self.tab_widget.addTab(self.thermal_camera_tab, "Thermal Camera")
        
        # Load settings tab from UI file
        self.settings_tab = QtWidgets.QWidget()
        uic.loadUi("settings_ui.ui", self.settings_tab)
        self.tab_widget.addTab(self.settings_tab, "Settings")
        
        # Pre-fill settings with values from system
        self.load_settings_to_ui()
        
        # Setup status bar
        self.statusBar().showMessage("Ready")
        logger.info("UI setup completed")
    
    def setup_caen_tab(self):
        """Setup the CAEN control tab"""
        layout = QtWidgets.QVBoxLayout(self.caen_tab)
        
        # Create CAEN GUI instance
        self.caen_gui = caenGUI(self.system)  # Pass system instance to caenGUI
        layout.addWidget(self.caen_gui)
    
    def load_settings_to_ui(self):
        # Fill settings UI with current values
        self.settings_tab.brokerLineEdit.setText(self.system.settings["mqtt"]["broker"])
        self.settings_tab.portSpinBox.setValue(self.system.settings["mqtt"]["port"])
        self.settings_tab.martaTopicLineEdit.setText(self.system.settings["MARTA"]["mqtt_topic"])
        self.settings_tab.coldroomTopicLineEdit.setText(self.system.settings["Coldroom"]["mqtt_topic"])
        self.settings_tab.co2SensorTopicLineEdit.setText(self.system.settings["Coldroom"]["co2_sensor_topic"])
        self.settings_tab.thermalCameraTopicLineEdit.setText(self.system.settings["ThermalCamera"]["mqtt_topic"])
    
    def connect_signals(self):
        # Connect settings tab
        self.settings_tab.saveButton.clicked.connect(self.save_settings)
        
        # Connect Cold Room controls
        # Light controls
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "coldroom_light_toggle_PB")
        if button:
            button.clicked.connect(self.toggle_coldroom_light)
        
        # Dry air controls
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "coldroom_dry_toggle_PB")
        if button:
            button.clicked.connect(self.toggle_coldroom_dry)    
        
        # Door controls
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "coldroom_door_toggle_PB")
        if button:
            button.clicked.connect(self.toggle_coldroom_door)
        
        # Temperature controls
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "coldroom_temp_ctrl_PB")
        if button:
            button.clicked.connect(self.toggle_coldroom_temp_control)        

        # Temperature setpoint controls
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "coldroom_temp_set_PB")
        if button:
            button.clicked.connect(self.set_coldroom_temperature)

        # Humidity controls
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "coldroom_humidity_ctrl_PB")
        if button:
            button.clicked.connect(self.toggle_coldroom_humidity_control)

        # Humidity setpoint controls
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "coldroom_humidity_set_PB")
        if button:
            button.clicked.connect(self.set_coldroom_humidity)

        # Run controls  
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "coldroom_run_toggle_PB")
        if button:
            button.clicked.connect(self.toggle_coldroom_run)           

        # MARTA CO2 Plant controls
        # Temperature controls
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "marta_temp_set_PB")
        if button:
            button.clicked.connect(self.set_marta_temperature)

        #Speed controls
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "marta_speed_set_PB")
        if button:
            button.clicked.connect(self.set_marta_speed)
        
        #Flow controls
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "marta_flow_set_PB")
        if button:
            button.clicked.connect(self.set_marta_flow)
        
        # Supply temperature label
        label = self.marta_coldroom_tab.findChild(QtWidgets.QLabel, "marta_temp_supply_value_label")
        if label:
            logger.debug("Connected supply temperature label")
            
        # Return temperature label
        label = self.marta_coldroom_tab.findChild(QtWidgets.QLabel, "marta_temp_return_value_label")
        if label:
            logger.debug("Connected return temperature label")
            
        # Supply pressure label
        label = self.marta_coldroom_tab.findChild(QtWidgets.QLabel, "marta_pressure_supply_value_label")
        if label:
            logger.debug("Connected supply pressure label")
            
        # Return pressure label
        label = self.marta_coldroom_tab.findChild(QtWidgets.QLabel, "marta_pressure_return_value_label")
        if label:
            logger.debug("Connected return pressure label")

        # Speed label
        label = self.marta_coldroom_tab.findChild(QtWidgets.QLabel, "marta_speed_value_label")
        if label:
            logger.debug("Connected speed label")
            
        # Other MARTA controls
        # Start chiller button
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "marta_chiller_start_PB")
        if button:
            button.clicked.connect(self.start_marta_chiller)
            
        # Start CO2 button
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "marta_co2_start_PB")
        if button:
            button.clicked.connect(self.start_marta_co2)

        # Stop CO2 button
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "marta_co2_stop_PB")
        if button:
            button.clicked.connect(self.stop_marta_co2)

        # Stop chiller button
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "marta_chiller_stop_PB")
        if button:
            button.clicked.connect(self.stop_marta_chiller)
            
        # Clear alarms button
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "marta_alarms_clear_PB")
        if button:
            button.clicked.connect(self.clear_marta_alarms)
        
        # Reconnect button
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "marta_reconnect_PB")
        if button:
            button.clicked.connect(self.reconnect_marta)
        
        # Refresh button
        button = self.marta_coldroom_tab.findChild(QtWidgets.QPushButton, "marta_refresh_PB")
        if button:
            button.clicked.connect(self.refresh_marta)

        # Flow active checkbox
        checkbox = self.marta_coldroom_tab.findChild(QtWidgets.QCheckBox, "marta_flow_active_CB")
        if checkbox:
            checkbox.clicked.connect(self.toggle_marta_flow_active)
        
        # Add debug logging for all connections
        # Log all connections
        logger.debug("Signal connections:")
        for button in self.marta_coldroom_tab.findChildren(QtWidgets.QPushButton):
            logger.debug(f"Found button: {button.objectName()}")
        
        for checkbox in self.marta_coldroom_tab.findChildren(QtWidgets.QCheckBox):
            logger.debug(f"Found checkbox: {checkbox.objectName()}")

        # Add input validation for numeric fields
        temp_lineedit = self.marta_coldroom_tab.findChild(QtWidgets.QLineEdit, "marta_temp_LE")
        if temp_lineedit:
            validator = QtGui.QDoubleValidator(-35, 25, 2)  # min, max, decimals
            temp_lineedit.setValidator(validator)
        
        # Add input validation for numeric fields
        speed_lineedit = self.marta_coldroom_tab.findChild(QtWidgets.QLineEdit, "marta_speed_LE")
        if speed_lineedit:
            validator = QtGui.QDoubleValidator(0, 6000, 2)  # min, max, decimals
            speed_lineedit.setValidator(validator)
        
        # Add input validation for numeric fields
        flow_lineedit = self.marta_coldroom_tab.findChild(QtWidgets.QLineEdit, "marta_flow_LE")
        if flow_lineedit:
            validator = QtGui.QDoubleValidator(0, 5, 2)  # min, max, decimals
            flow_lineedit.setValidator(validator)

    
    def connect_mqtt(self):
        """Connect to MQTT broker using settings"""
        try:
            # Get broker settings from system
            server = self.system.settings["mqtt"]["broker"]
            port = self.system.settings["mqtt"]["port"]
            
            # Update system broker and port (in case they were changed)
            self.system.BROKER = server
            self.system.PORT = port
            
            # Start MQTT thread
            self.system.start_mqtt_thread()
            
            # Update status
            status_msg = f"Connected to MQTT broker at {server}:{port}"
            self.statusBar().showMessage(status_msg)
            logger.info(status_msg)
            
        except Exception as e:
            error_msg = f"Failed to connect to MQTT broker: {str(e)}"
            self.statusBar().showMessage(error_msg)
            logger.error(error_msg)
    
    def update_ui(self):
        """Update UI with current system status"""
        try:
            # Get the central widget
            central = self.marta_coldroom_tab
            
            # Update Cleanroom values from system status
            if 'cleanroom' in self.system.status:
                cleanroom = self.system.status['cleanroom']
                logger.debug(f"Updating Cleanroom UI with status: {cleanroom}")
                
                # Temperature
                label = central.findChild(QtWidgets.QLabel, "cleanroom_temp_value_label")
                if label and 'temperature' in cleanroom and cleanroom['temperature'] is not None:
                    temp_value = cleanroom['temperature']
                    label.setText(f"{temp_value:.1f}")
                    logger.debug(f"Updated Cleanroom temperature: {temp_value}")
                
                # Humidity
                label = central.findChild(QtWidgets.QLabel, "cleanroom_humidity_value_label")
                if label and 'humidity' in cleanroom and cleanroom['humidity'] is not None:
                    humid_value = cleanroom['humidity']
                    label.setText(f"{humid_value:.1f}")
                    logger.debug(f"Updated Cleanroom humidity: {humid_value}")
                
                # Dewpoint
                label = central.findChild(QtWidgets.QLabel, "cleanroom_dewpoint_value_label")
                if label and 'dewpoint' in cleanroom and cleanroom['dewpoint'] is not None:
                    dewpoint = cleanroom['dewpoint']
                    label.setText(f"{dewpoint:.1f}")
                    logger.debug(f"Updated Cleanroom dewpoint: {dewpoint}")
                
                # Pressure
                label = central.findChild(QtWidgets.QLabel, "cleanroom_pressure_value_label")
                if label and 'pressure' in cleanroom and cleanroom['pressure'] is not None:
                    pressure = cleanroom['pressure']
                    label.setText(f"{pressure:.1f}")
                    logger.debug(f"Updated Cleanroom pressure: {pressure}")
            
            # Update Cold Room values from system status
            if 'coldroom' in self.system.status:
                coldroom = self.system.status['coldroom']
                logger.debug(f"Updating Coldroom UI with status: {coldroom}")
                
                temp_control_active = coldroom.get('ch_temperature', {}).get('status', False)
                hum_control_active = coldroom.get('ch_humidity', {}).get('status', False)

                # Temperature control LED
                if 'ch_temperature' in coldroom: 
                    if 'status' in coldroom['ch_temperature']:
                        # print("status read", coldroom["ch_temperature"]["status"]) # 1 = ON, 0 = OFF
                        # Update Temperature control LED
                        ctrl_temp_led = central.findChild(QtWidgets.QFrame, "ctrl_temp_LED")
                        if ctrl_temp_led:
                            ctrl_temp_led.setStyleSheet("background-color: green;" if coldroom['ch_temperature']['status'] else "background-color: black;") # LED is green when ON
                            logger.debug(f"Updated temp control LED: {'green' if coldroom['ch_temperature']['status'] else 'black'}") 

                # Humidity control LED
                if 'ch_humidity' in coldroom:
                    if 'status' in coldroom['ch_humidity']:
                        # print("status read", coldroom["ch_humidity"]["status"]) # 1 = ON, 0 = OFF
                        # Update Humidity control LED
                        ctrl_humidity_led = central.findChild(QtWidgets.QFrame, "ctrl_humidity_LED")
                        if ctrl_humidity_led:
                            ctrl_humidity_led.setStyleSheet("background-color: green;" if coldroom['ch_humidity']['status'] else "background-color: black;") # LED is green when ON
                            logger.debug(f"Updated humidity control LED: {'green' if coldroom['ch_humidity']['status'] else 'black'}")    
                
                # Temperature
                if 'ch_temperature' in coldroom:
                    # Current temperature
                    label = central.findChild(QtWidgets.QLabel, "coldroom_temp_value_label")
                    if label:
                        temp_value = coldroom['ch_temperature'].get('value', '?')
                        label.setText(f"{temp_value:.1f}")
                        logger.debug(f"Updated temperature: {temp_value}")
                    
                # Temperature setpoint
                lineedit = central.findChild(QtWidgets.QLineEdit, "coldroom_temp_LE")
                if lineedit:
                    user_has_entered_value = bool(lineedit.text().strip())
                    # Case 1: User is actively typing - preserve their input
                    if lineedit.hasFocus():
                        pass
                    # Case 2: User has entered a value - use that value
                    elif temp_control_active and user_has_entered_value:
                        setpoint = lineedit.text()
                        lineedit.setText(str(setpoint))
                        logger.debug(f"Updated temperature setpoint: {setpoint}")
                    else:
                        lineedit.clear()
                        logger.debug("Cleared temperature setpoint")
                    
                
                # Humidity
                if 'ch_humidity' in coldroom:
                    # Current humidity
                    label = central.findChild(QtWidgets.QLabel, "coldroom_humidity_value_label")
                    if label:
                        humid_value = coldroom['ch_humidity'].get('value', '?')
                        label.setText(f"{humid_value:.1f}")
                        logger.debug(f"Updated humidity: {humid_value}")
                
                # Humidity setpoint
                lineedit = central.findChild(QtWidgets.QLineEdit, "coldroom_humidity_LE")
                if lineedit:
                    user_has_entered_value = bool(lineedit.text().strip())
                    # Case 1: User is actively typing - preserve their input
                    if lineedit.hasFocus():
                        pass    
                    # Case 2: User has entered a value - use that value
                    elif hum_control_active and user_has_entered_value:
                        setpoint = lineedit.text()
                        lineedit.setText(str(setpoint))
                        logger.debug(f"Updated humidity setpoint: {setpoint}")
                    else:
                        lineedit.clear()
                        logger.debug("Cleared humidity setpoint")   

                # # Humidity setpoint
                # if 'ch_humidity' in coldroom:
                #     lineedit = central.findChild(QtWidgets.QLineEdit, "coldroom_humidity_LE")
                #     if lineedit and not lineedit.hasFocus():
                #         setpoint = coldroom['ch_humidity'].get('setpoint', lineedit.text())
                #         lineedit.setText(str(setpoint))
                #         logger.debug(f"Updated humidity setpoint: {setpoint}")
                    
                # Dewpoint (from coldroom data)
                label = central.findChild(QtWidgets.QLabel, "coldroom_dewpoint_value_label")
                if label and 'dew_point_c' in coldroom:
                    dewpoint = coldroom['dew_point_c']
                    label.setText(f"{dewpoint:.1f}")
                    logger.debug(f"Updated dewpoint: {dewpoint}")
                
                # Light status and LED
                if 'light' in coldroom:
                    # Update light LED
                    light_led = central.findChild(QtWidgets.QFrame, "light_LED")
                    if light_led:
                        light_led.setStyleSheet("background-color: yellow;" if coldroom['light'] else "background-color: black;") # LED is yellow when ON
                        logger.debug(f"Updated light LED: {'yellow' if coldroom['light'] else 'black'}")
                
                # Door status and LED
                if 'CmdDoorUnlock_Reff' in coldroom:
                    door_status = "OPEN" if coldroom['CmdDoorUnlock_Reff'] else "CLOSED"
                    label = central.findChild(QtWidgets.QLabel, "coldroom_door_state_label")
                    if label:
                        label.setText(door_status)
                        logger.debug(f"Updated door status: {door_status}")
                    
                
                # Update safe to open LED based on door_locked safety flag
                safe_to_open_led = central.findChild(QtWidgets.QFrame, "safe_to_open_LED")
                if safe_to_open_led:
                    is_locked = self.system.safety_flags.get("door_locked", True)  # True means locked/unsafe
                    safe_to_open_led.setStyleSheet("background-color: red;" if is_locked else "background-color: green;")
                    logger.debug(f"Updated safe to open LED: {'red' if is_locked else 'green'} (door_locked={is_locked})")
                
                # Run status
                if 'running' in coldroom:
                    label = central.findChild(QtWidgets.QLabel, "coldroom_run_state_label")
                    if label:
                        run_text = "Running" if coldroom['running'] else "Stopped"
                        label.setText(run_text)
                        logger.debug(f"Updated run state label: {run_text}")
                
                # External dry air status
                if 'dry_air_status' in coldroom:
                    # Update dry air LED
                    dry_air_led = central.findChild(QtWidgets.QFrame, "dryair_LED")
                    if dry_air_led:
                        dry_air_led.setStyleSheet("background-color: green;" if coldroom['dry_air_status'] else "background-color: red;")
                        logger.debug(f"Updated dry air LED: {'green' if coldroom['dry_air_status'] else 'red'}")
            
            # Update CO2 sensor data
            if 'co2_sensor' in self.system.status:
                co2_data = self.system.status['co2_sensor']
                logger.debug(f"Updating CO2 sensor data: {co2_data}")
                
                # Update CO2 level
                label = central.findChild(QtWidgets.QLabel, "coldroom_co2_value_label")
                if label and 'CO2' in co2_data:
                    co2_value = co2_data['CO2']
                    label.setText(f"{co2_value:.1f}")
                    logger.debug(f"Updated CO2 level: {co2_value}")
            
            # Update MARTA CO2 Plant values
            if 'marta' in self.system.status:
                marta = self.system.status['marta']
                logger.debug(f"Updating MARTA UI with status: {marta}")
                
                # Update FSM state
                if 'fsm_state' in marta:
                    state_label = central.findChild(QtWidgets.QLabel, "marta_state_label")
                    if state_label:
                        state_label.setText(marta['fsm_state'])
                        logger.debug(f"Updated MARTA state: {marta['fsm_state']}")
                    # Update state-specific UI elements
                    if marta['fsm_state'] == "ALARM":
                        # Highlight alarm state
                        alarm_frame = central.findChild(QtWidgets.QFrame, "marta_alarm_frame")
                        if alarm_frame:
                            alarm_frame.setStyleSheet("background-color: red;")
                        
                        # Show alarm message
                        alarm_msg = central.findChild(QtWidgets.QLabel, "marta_alarm_msg_label")
                        if alarm_msg and 'alarm_message' in marta:
                            alarm_msg.setText(marta['alarm_message'])
                    else:
                        # Clear alarm highlighting
                        alarm_frame = central.findChild(QtWidgets.QFrame, "marta_alarm_frame")
                        if alarm_frame:
                            alarm_frame.setStyleSheet("")

                # Temperature from TT05_CO2 (Supply)
                if 'TT05_CO2' in marta:
                    label = central.findChild(QtWidgets.QLabel, "marta_temp_supply_value_label")
                    if label:
                        temp_value = marta['TT05_CO2']
                        label.setText(f"{temp_value:.1f}")
                        logger.debug(f"Updated MARTA supply temperature: {temp_value}")

                # Temperature setpoint
                lineedit = central.findChild(QtWidgets.QLineEdit, "marta_temp_LE")
                if lineedit:
                    user_has_entered_value = bool(lineedit.text().strip())
                    # Case 1: User is actively typing - preserve their input
                    if lineedit.hasFocus():
                        pass
                    # Case 2: User has entered a value - use that value
                    elif temp_control_active and user_has_entered_value:
                        temp_setpoint = lineedit.text()
                        lineedit.setText(str(temp_setpoint))
                        logger.debug(f"Updated MARTA temperature setpoint: {temp_setpoint}")
                    else:
                        lineedit.clear()
                        logger.debug("Cleared MARTA temperature setpoint")


                # Temperature from TT06_CO2 (Return)
                if 'TT06_CO2' in marta:
                    label = central.findChild(QtWidgets.QLabel, "marta_temp_return_value_label")
                    if label:
                        temp_value = marta['TT06_CO2']
                        label.setText(f"{temp_value:.1f}")
                        logger.debug(f"Updated MARTA return temperature: {temp_value}")

                # Pressure from PT05_CO2 (Supply)
                if 'PT05_CO2' in marta:
                    label = central.findChild(QtWidgets.QLabel, "marta_pressure_supply_value_label")
                    if label:
                        pressure_value = marta['PT05_CO2']
                        label.setText(f"{pressure_value:.3f}")
                        logger.debug(f"Updated MARTA supply pressure: {pressure_value}")

                # Pressure from PT06_CO2 (Return)
                if 'PT06_CO2' in marta:
                    label = central.findChild(QtWidgets.QLabel, "marta_pressure_return_value_label")
                    if label:
                        pressure_value = marta['PT06_CO2']
                        label.setText(f"{pressure_value:.3f}")
                        logger.debug(f"Updated MARTA return pressure: {pressure_value}")
                
                # Speed
                if 'speed' in marta:
                    label = central.findChild(QtWidgets.QLabel, "marta_speed_value_label")
                    if label:
                        speed_value = marta['speed']
                        label.setText(f"{speed_value:.1f}")
                        logger.debug(f"Updated MARTA speed: {speed_value}")
                # Temperature setpoint
                # spinbox = central.findChild(QtWidgets.QDoubleSpinBox, "marta_temp_spinbox")
                # if spinbox:
                #     temp_setpoint = marta.get('temperature_setpoint', spinbox.value())
                #     spinbox.setValue(temp_setpoint)
                #     logger.debug(f"Updated MARTA temperature setpoint: {temp_setpoint}")

                # Flow setpoint (affects speed)
                if 'flow_setpoint' in marta:
                    # spinbox = central.findChild(QtWidgets.QDoubleSpinBox, "marta_flow_spinbox")
                    # if spinbox:
                    #     flow_value = marta['flow_setpoint']
                    #     spinbox.setValue(flow_value)
                    #     logger.debug(f"Updated MARTA flow setpoint: {flow_value}")
                    lineedit = central.findChild(QtWidgets.QLineEdit, "marta_flow_LE")
                    if lineedit:
                        user_has_entered_value = bool(lineedit.text().strip())
                        # Case 1: User is actively typing - preserve their input
                        if lineedit.hasFocus():
                            pass
                        # Case 2: User has entered a value - use that value
                        elif flow_control_active and user_has_entered_value:
                            flow_value = lineedit.text()
                            lineedit.setText(str(flow_value))
                            logger.debug(f"Updated MARTA flow setpoint: {flow_value}")
                        else:
                            lineedit.clear()
                            logger.debug("Cleared MARTA flow setpoint")


                # Speed setpoint
                if 'speed_setpoint' in marta:
                    # spinbox = central.findChild(QtWidgets.QDoubleSpinBox, "marta_speed_spinbox")
                    # if spinbox:
                    #     speed_value = marta['speed_setpoint']
                    #     spinbox.setValue(speed_value)
                    #     logger.debug(f"Updated MARTA speed setpoint: {speed_value}")
                    lineedit = central.findChild(QtWidgets.QLineEdit, "marta_speed_LE")
                    if lineedit:
                        user_has_entered_value = bool(lineedit.text().strip())
                        # Case 1: User is actively typing - preserve their input
                        if lineedit.hasFocus():
                            pass
                        # Case 2: User has entered a value - use that value
                        elif speed_control_active and user_has_entered_value:
                            speed_value = lineedit.text()
                            lineedit.setText(str(speed_value))
                            logger.debug(f"Updated MARTA speed setpoint: {speed_value}")                    
                        else:
                            lineedit.clear()
                            logger.debug("Cleared MARTA speed setpoint")
                
                # Update FSM state in status bar if available
                if 'fsm_state' in marta:
                    self.statusBar().showMessage(f"MARTA State: {marta['fsm_state']}")
                    self.update_marta_button_states(marta['fsm_state'])
                    logger.debug(f"Updated MARTA state: {marta['fsm_state']}")
                
        except Exception as e:
            error_msg = f"Error updating UI: {str(e)}"
            logger.error(error_msg)
            self.statusBar().showMessage(error_msg)
    
    # Cold Room control methods
    
    def set_coldroom_temperature(self):
        central = self.marta_coldroom_tab    
        # Check if temperature control is enabled
        coldroom = self.system.status.get('coldroom', {})
        if not coldroom['ch_temperature'].get('status', False):
            msg = "Temperature control is not enabled. Please enable temperature control first."
            self.statusBar().showMessage(msg)
            logger.warning(msg)
            return

        lineedit = central.findChild(QtWidgets.QLineEdit, "coldroom_temp_LE")
        if not lineedit:
            msg = "Cannot find temperature input field"
            self.statusBar().showMessage(msg)
            logger.error(msg)
            return

        try:
            value = float(lineedit.text())
            if self.system._martacoldroom:
                self.system._martacoldroom.set_temperature(str(value))
                msg = f"Set coldroom temperature to {value}°C"
                self.statusBar().showMessage(msg)
                logger.info(msg)
            else:
                msg = "MARTA Cold Room client not initialized"
                self.statusBar().showMessage(msg)
                logger.error(msg)
        except ValueError:
            msg = "Invalid temperature value"
            self.statusBar().showMessage(msg)
            logger.error(msg)
    
    def set_coldroom_humidity(self):
        central = self.marta_coldroom_tab
        # Check if humidity control is enabled
        coldroom = self.system.status.get('coldroom', {})
        if not coldroom['ch_humidity'].get('status', False):
            msg = "Humidity control is not enabled. Please enable humidity control first."
            self.statusBar().showMessage(msg)
            logger.warning(msg)
            return
        
        lineedit = central.findChild(QtWidgets.QLineEdit, "coldroom_humidity_LE")
        if not lineedit:
            msg = "Cannot find humidity input field"
            self.statusBar().showMessage(msg)
            logger.error(msg)
            return

        try:
            value = float(lineedit.text())
            if self.system._martacoldroom:
                self.system._martacoldroom.set_humidity(str(value))
                msg = f"Set coldroom humidity to {value}%"
                self.statusBar().showMessage(msg)
                logger.info(msg)
            else:
                msg = "MARTA Cold Room client not initialized"
                self.statusBar().showMessage(msg)
                logger.error(msg)
        except ValueError:
            msg = "Invalid humidity value"
            self.statusBar().showMessage(msg)
            logger.error(msg)

    def toggle_coldroom_light(self):
        coldroom = self.system.status.get('coldroom', {})
        current_state = coldroom.get('light', 0)
        new_state = 0 if current_state else 1
        if self.system._martacoldroom:
            self.system._martacoldroom.control_light(str(new_state))
            msg = f"Set coldroom light to {'ON' if new_state else 'OFF'}"
            self.statusBar().showMessage(msg)
            logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)

    def toggle_coldroom_run(self):
        coldroom = self.system.status.get('coldroom', {})
        current_state = coldroom.get('run_state', 0)
        # current_state = coldroom.get('running', 0)
        new_state = 0 if current_state else 1

        if self.system._martacoldroom:
                # Use proper command for run/stop
                if new_state:
                    self.system._martacoldroom.publish_cmd("run", self.system._martacoldroom._coldroom_client, str(new_state))
                else:
                    self.system._martacoldroom.publish_cmd("stop", self.system._martacoldroom._coldroom_client, str(new_state))
                msg = "Started coldroom" if new_state else "Stopped coldroom"
                self.statusBar().showMessage(msg)
                logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)

        # if self.system._martacoldroom:
        #     if new_state:
        #         self.system._martacoldroom.run(str(new_state))
        #         msg = "Started coldroom"
        #     else:
        #         self.system._martacoldroom.stop(str(new_state))
        #         msg = "Stopped coldroom"
        #     self.statusBar().showMessage(msg)
        #     logger.info(msg)
        # else:
        #     msg = "MARTA Cold Room client not initialized"
        #     self.statusBar().showMessage(msg)
        #     logger.error(msg)

    def toggle_coldroom_dry(self):
        coldroom = self.system.status.get('coldroom', {})
        current_state = coldroom.get('external_dry_air', 0)
        new_state = 0 if current_state else 1
        if self.system._martacoldroom:
            self.system._martacoldroom.control_external_dry_air(str(new_state))
            msg = f"Set external dry air to {'ON' if new_state else 'OFF'}"
            self.statusBar().showMessage(msg)
            logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)


    def toggle_coldroom_door(self):
        coldroom = self.system.status.get('coldroom', {})
        current_state = coldroom.get('door_state', 0)
        # current_state = coldroom.get('CmdDoorUnlock_Reff', 0)  # Changed to match your status key
        new_state = 0 if current_state else 1
 
        # This would normally require safety checks
        if self.system._martacoldroom:
            # For demo purposes, we're just toggling the state
            self.system._martacoldroom.publish_cmd("door", self.system._martacoldroom._coldroom_client, str(new_state))
            msg = f"Set door to {'OPEN' if new_state else 'CLOSED'}"
            self.statusBar().showMessage(msg)
            logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)

    def toggle_coldroom_temp_control(self):
        coldroom = self.system.status.get('coldroom', {})
        current_state = coldroom.get('ch_temperature_status', False)
        new_state = not current_state  # Toggle the state
        
        if self.system._martacoldroom:
            self.system._martacoldroom.control_temperature(str(int(new_state)))
            msg = f"Temperature control {'enabled' if new_state else 'disabled'}"
            self.statusBar().showMessage(msg)
            logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)

    def toggle_coldroom_humidity_control(self):
        coldroom = self.system.status.get('coldroom', {})
        current_state = coldroom.get('ch_humidity_status', False)
        new_state = not current_state  # Toggle the state
        
        if self.system._martacoldroom:
            self.system._martacoldroom.control_humidity(str(int(new_state)))
            msg = f"Humidity control {'enabled' if new_state else 'disabled'}"
            self.statusBar().showMessage(msg)
            logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)

    # MARTA CO2 Plant control methods

    def update_marta_button_states(self, state):
        central = self.marta_coldroom_tab
        
        # Get all MARTA control buttons
        start_chiller_btn = central.findChild(QtWidgets.QPushButton, "marta_chiller_start_PB")
        stop_chiller_btn = central.findChild(QtWidgets.QPushButton, "marta_stop_chiller_PB")
        start_co2_btn = central.findChild(QtWidgets.QPushButton, "marta_co2_start_PB")
        stop_co2_btn = central.findChild(QtWidgets.QPushButton, "marta_co2_stop_PB")
        
        # Enable/disable based on state
        if state == "CONNECTED":
            if start_chiller_btn: start_chiller_btn.setEnabled(True)
            if stop_chiller_btn: stop_chiller_btn.setEnabled(False)
            if start_co2_btn: start_co2_btn.setEnabled(False)
            if stop_co2_btn: stop_co2_btn.setEnabled(False)
        elif state == "CHILLER_RUNNING":
            if start_chiller_btn: start_chiller_btn.setEnabled(False)
            if stop_chiller_btn: stop_chiller_btn.setEnabled(True)
            if start_co2_btn: start_co2_btn.setEnabled(True)
            if stop_co2_btn: stop_co2_btn.setEnabled(False)
        elif state == "CO2_RUNNING":
            if start_chiller_btn: start_chiller_btn.setEnabled(False)
            if stop_chiller_btn: stop_chiller_btn.setEnabled(True)
            if start_co2_btn: start_co2_btn.setEnabled(False)
            if stop_co2_btn: stop_co2_btn.setEnabled(True)
        elif state == "ALARM":
            # Only allow alarm clearing
            if start_chiller_btn: start_chiller_btn.setEnabled(False)
            if stop_chiller_btn: stop_chiller_btn.setEnabled(False)
            if start_co2_btn: start_co2_btn.setEnabled(False)
            if stop_co2_btn: stop_co2_btn.setEnabled(False)

    def set_marta_temperature(self):
        central = self.marta_coldroom_tab
        lineedit = central.findChild(QtWidgets.QLineEdit, "marta_temp_LE")
        
        if not lineedit:
            msg = "Cannot find MARTA temperature input field"
            self.statusBar().showMessage(msg)
            logger.error(msg)
            return

        try:
            value = float(lineedit.text())
            if -35 <= value <= 25:  # Validate range from marta.py
                if self.system._martacoldroom:
                    self.system._martacoldroom.set_temperature_setpoint(str(value))
                    # self.system._martacoldroom.publish_cmd("set_temperature", self.system._martacoldroom._marta_client, str(value))

                    msg = f"Set MARTA temperature to {value}°C"
                    self.statusBar().showMessage(msg)
                    logger.info(msg)
                else:
                    msg = "MARTA Cold Room client not initialized"
                    self.statusBar().showMessage(msg)
                    logger.error(msg)
            else:
                msg = "Temperature must be between -35°C and 25°C"
                self.statusBar().showMessage(msg)
                logger.error(msg)
        except ValueError:
            msg = "Invalid temperature value"
            self.statusBar().showMessage(msg)
            logger.error(msg)
    
    def set_marta_speed(self):
        central = self.marta_coldroom_tab
        lineedit = central.findChild(QtWidgets.QLineEdit, "marta_speed_LE")
        
        if not lineedit:
            msg = "Cannot find MARTA speed input field"
            self.statusBar().showMessage(msg)
            logger.error(msg)
            return

        try:
            value = float(lineedit.text())
            if 0 <= value <= 6000:  # Validate range from marta.py
                if self.system._martacoldroom:
                    self.system._martacoldroom.set_speed_setpoint(str(value))
                    # self.system._martacoldroom.publish_cmd("set_speed", self.system._martacoldroom._marta_client, str(value))

                    msg = f"Set MARTA speed to {value} RPM"
                    self.statusBar().showMessage(msg)
                    logger.info(msg)
                else:
                    msg = "MARTA Cold Room client not initialized"
                    self.statusBar().showMessage(msg)
                    logger.error(msg)
            else:
                msg = "Speed must be between 0 and 6000 RPM"
                self.statusBar().showMessage(msg)
                logger.error(msg)
        except ValueError:
            msg = "Invalid speed value"
            self.statusBar().showMessage(msg)
            logger.error(msg)
    
    def set_marta_flow(self):
        central = self.marta_coldroom_tab
        lineedit = central.findChild(QtWidgets.QLineEdit, "marta_flow_LE")
        
        if not lineedit:
            msg = "Cannot find MARTA flow input field"
            self.statusBar().showMessage(msg)
            logger.error(msg)
            return

        try:
            value = float(lineedit.text())
            if 0 <= value <= 5:  # Validate range from marta.py
                if self.system._martacoldroom:
                    self.system._martacoldroom.set_flow_setpoint(str(value))
                    # self.system._martacoldroom.publish_cmd("set_flow", self.system._martacoldroom._marta_client, str(value))

                    msg = f"Set MARTA flow to {value}"
                    self.statusBar().showMessage(msg)
                    logger.info(msg)
                else:
                    msg = "MARTA Cold Room client not initialized"
                    self.statusBar().showMessage(msg)
                    logger.error(msg)
            else:
                msg = "Flow must be between 0 and 5"
                self.statusBar().showMessage(msg)
                logger.error(msg)
        except ValueError:
            msg = "Invalid flow value"
            self.statusBar().showMessage(msg)
            logger.error(msg)
    
    def start_marta_chiller(self):
        if self.system._martacoldroom:
            self.system._martacoldroom.start_chiller("1")
            # self.system._martacoldroom.publish_cmd("start_chiller", self.system._martacoldroom._marta_client, "1")
            
            msg = "Started MARTA chiller"
            self.statusBar().showMessage(msg)
            logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)

    def stop_marta_chiller(self):
        if self.system._martacoldroom:
            self.system._martacoldroom.stop_chiller("1")
            # self.system._martacoldroom.publish_cmd("stop_chiller", self.system._martacoldroom._marta_client, "1")
            
            msg = "Stopped MARTA chiller"
            self.statusBar().showMessage(msg)
            logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)
    
    def start_marta_co2(self):
        if self.system._martacoldroom:
            self.system._martacoldroom.start_co2("1")
            # self.system._martacoldroom.publish_cmd("start_co2", self.system._martacoldroom._marta_client, "1")
            
            msg = "Started MARTA CO2"
            self.statusBar().showMessage(msg)
            logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)
    
    def stop_marta_co2(self):
        if self.system._martacoldroom:
            self.system._martacoldroom.stop_co2("1")
            # self.system._martacoldroom.publish_cmd("stop_co2", self.system._martacoldroom._marta_client, "1")
            
            msg = "Stopped MARTA CO2"
            self.statusBar().showMessage(msg)
            logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)
    
    def reconnect_marta(self):
        if self.system._martacoldroom:
            self.system._martacoldroom.reconnect("1")
            # self.system._martacoldroom.publish_cmd("reconnect", self.system._martacoldroom._marta_client, "1")
            
            msg = "Reconnecting to MARTA"
            self.statusBar().showMessage(msg)
            logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)
    
    def refresh_marta(self):
        if self.system._martacoldroom:
            self.system._martacoldroom.refresh("1")
            # self.system._martacoldroom.publish_cmd("refresh", self.system._martacoldroom._marta_client, "1")
            
            msg = "Refreshing MARTA"
            self.statusBar().showMessage(msg)
            logger.info(msg)    
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)

    def clear_marta_alarms(self):
        if self.system._martacoldroom:
            self.system._martacoldroom.clear_alarms("1")
            # self.system._martacoldroom.publish_cmd("clear_alarms", self.system._martacoldroom._marta_client, "1")
            
            msg = "Cleared MARTA alarms"
            self.statusBar().showMessage(msg)
            logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)
    
    def toggle_marta_flow_active(self):
        central = self.marta_coldroom_tab
        checkbox = central.findChild(QtWidgets.QCheckBox, "marta_flow_active_CB")
        
        if not checkbox:
            msg = "Cannot find flow active checkbox"
            self.statusBar().showMessage(msg)
            logger.error(msg)
            return
            
        state = 1 if checkbox.isChecked() else 0
        if self.system._martacoldroom:
            self.system._martacoldroom.set_flow_active(str(state))
            # self.system._martacoldroom.publish_cmd("set_flow_active", self.system._martacoldroom._marta_client, str(state))
            
            msg = f"Set flow active to {'ON' if state else 'OFF'}"
            self.statusBar().showMessage(msg)
            logger.info(msg)
        else:
            msg = "MARTA Cold Room client not initialized"
            self.statusBar().showMessage(msg)
            logger.error(msg)
    
    def save_settings(self):
        try:
            # Update settings object
            self.system.settings["mqtt"]["broker"] = self.settings_tab.brokerLineEdit.text()
            self.system.settings["mqtt"]["port"] = self.settings_tab.portSpinBox.value()
            self.system.settings["MARTA"]["mqtt_topic"] = self.settings_tab.martaTopicLineEdit.text()
            self.system.settings["Coldroom"]["mqtt_topic"] = self.settings_tab.coldroomTopicLineEdit.text()
            self.system.settings["Coldroom"]["co2_sensor_topic"] = self.settings_tab.co2SensorTopicLineEdit.text()
            self.system.settings["ThermalCamera"]["mqtt_topic"] = self.settings_tab.thermalCameraTopicLineEdit.text()
            self.system.settings["Cleanroom"]["mqtt_topic"] = self.settings_tab.cleanroomTopicLineEdit.text()
            
            # Write to file
            with open("settings.yaml", "w") as f:
                yaml.dump(self.system.settings, f, default_flow_style=False)
            
            msg = "Settings saved successfully"
            self.statusBar().showMessage(msg)
            logger.info(msg)
            
            # Update system broker and port
            self.system.BROKER = self.system.settings["mqtt"]["broker"]
            self.system.PORT = self.system.settings["mqtt"]["port"]
            
        except Exception as e:
            msg = f"Error saving settings: {str(e)}"
            self.statusBar().showMessage(msg)
            logger.error(msg)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
