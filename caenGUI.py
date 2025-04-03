import sys
import json
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QLabel
from PyQt5.QtCore import pyqtSlot, QTimer
from PyQt5.QtGui import QFont
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class caenGUI(QWidget):
    def __init__(self, system):
        super().__init__()
        self.system = system
        
        # Initialize UI
        self.initUI()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)  # Update every second

    def initUI(self):
        """Initialize the GUI layout"""
        try:
            self.setWindowTitle("CAEN Control")

            self.layout = QHBoxLayout()
            self.setLayout(self.layout)

            # Define channels
            self.channels = []
            for s in [6, 7, 8, 9, 10, 11]:
                self.channels += [f"LV{s}.{x}" for x in range(1, 9)]
            for s in [0, 1, 2, 3]:
                self.channels += [f"HV{s}.{x}" for x in range(1, 13)]

            self.led = {}
            self.label = {}
            
            # Create channel controls
            for i, channel in enumerate(self.channels):
                if i % 24 == 0:
                    line = QFrame()
                    line.setFrameShape(QFrame.VLine)
                    self.layout.addWidget(line)
                    vlayout = QVBoxLayout()
                    self.layout.addLayout(vlayout)
                
                hlayout = QHBoxLayout()
                vlayout.addLayout(hlayout)
                
                # Channel label
                l = QLabel(channel + ":")
                hlayout.addWidget(l)
                
                # ON button
                on_button = QPushButton("ON", self)
                on_button.setMinimumWidth(30)
                on_button.clicked.connect(lambda checked, ch=channel: self.on(ch))
                hlayout.addWidget(on_button)
                
                # OFF button  
                off_button = QPushButton("OFF", self)
                off_button.setMinimumWidth(30)
                off_button.clicked.connect(lambda checked, ch=channel: self.off(ch))
                hlayout.addWidget(off_button)
                
                # Status label
                self.label[channel] = QLabel("n/a")
                self.label[channel].setFont(QFont("Arial", 9))
                hlayout.addWidget(self.label[channel])
                
                # Status LED
                self.led[channel] = QFrame(self)
                self.led[channel].setFrameShape(QFrame.Box)
                self.led[channel].setFixedSize(30, 30)
                self.led[channel].setStyleSheet("background-color: red")
                hlayout.addWidget(self.led[channel])
                
            logger.info("CAEN GUI initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing CAEN GUI: {e}")
            raise

    def closeEvent(self, event):
        """Handle widget close event"""
        try:
            self.update_timer.stop()
            event.accept()
        except Exception as e:
            logger.error(f"Error in close event: {e}")
            event.accept()

    @pyqtSlot()
    def update_status(self):
        """Update GUI with current CAEN status"""
        try:
            if not self.system or not hasattr(self.system, 'status'):
                return
                
            status = self.system.status.get('caen', {})
            if not status:
                return
                
            # Update channel displays
            for channel in self.channels:
                try:
                    channel_on = status.get(f"caen_{channel}_IsOn", 0) > 0.5
                    self.led[channel].setStyleSheet(
                        "background-color: green" if channel_on else "background-color: red"
                    )
                    
                    if "LV" in channel:
                        voltage = status.get(f"caen_{channel}_Voltage", 0)
                        current = status.get(f"caen_{channel}_Current", 0)
                        power = voltage * current
                        self.label[channel].setText(
                            f'V: {voltage:1.1f}V\nI: {current:1.1f}A ({power:1.1f}W)'
                        )
                    else:
                        voltage = status.get(f"caen_{channel}_Voltage", 0)
                        current = status.get(f"caen_{channel}_Current", 0)
                        self.label[channel].setText(
                            f'V: {voltage:3.1f}V\nI: {current:1.2f}uA'
                        )
                except Exception as e:
                    logger.error(f"Error updating channel {channel}: {e}")
                    
        except Exception as e:
            logger.error(f"Error updating status: {e}")

    @pyqtSlot()
    def on(self, channel):
        """Turn on a channel"""
        try:
            if hasattr(self.system, '_caen') and self.system._caen:
                if self.system._caen.turn_on_channel(channel):
                    logger.info(f"Turned on channel {channel}")
                else:
                    logger.error(f"Failed to turn on channel {channel}")
        except Exception as e:
            logger.error(f"Error turning on channel {channel}: {e}")

    @pyqtSlot() 
    def off(self, channel):
        """Turn off a channel"""
        try:
            if hasattr(self.system, '_caen') and self.system._caen:
                if self.system._caen.turn_off_channel(channel):
                    logger.info(f"Turned off channel {channel}")
                else:
                    logger.error(f"Failed to turn off channel {channel}")
        except Exception as e:
            logger.error(f"Error turning off channel {channel}: {e}") 