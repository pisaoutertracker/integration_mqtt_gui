import socket
import logging
import threading
import time
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BUFFER_SIZE = 100000

class CAENTCPClient:
    """Handles TCP communication with CAEN power supply"""
    
    def __init__(self, ip="192.168.0.45", port=7000):
        self.ip = ip
        self.port = port
        self._socket = None
        self._lock = threading.Lock()  # Thread safety for socket operations
        self._status = {}
        self._connected = False
        self._header_bytes = 4
        
    def connect(self):
        """Establish connection to CAEN power supply"""
        try:
            with self._lock:
                if self._socket:
                    try:
                        self._socket.close()
                    except:
                        pass
                
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(600)  # 5 second timeout
                self._socket.connect((self.ip, self.port))
                self._connected = True
                logger.info(f"Connected to CAEN at {self.ip}:{self.port}")
                return True
        except Exception as e:
            self._connected = False
            logger.error(f"Failed to connect to CAEN: {e}")
            return False
            
    def disconnect(self):
        """Close connection to CAEN power supply"""
        try:
            with self._lock:
                if self._socket:
                    self._socket.close()
                    self._socket = None
                self._connected = False
            logger.info("Disconnected from CAEN")
        except Exception as e:
            logger.error(f"Error disconnecting from CAEN: {e}")
            
    def is_connected(self):
        """Check if connected to CAEN"""
        return self._connected
            
    def _encode_message(self, message):
        """Encode message with CAEN protocol header"""
        try:
            message_length = len(message) + self._header_bytes + 4
            N = 0
            return (
                message_length.to_bytes(4, byteorder="big") + 
                N.to_bytes(4, byteorder="big") + 
                message.encode("utf-8")
            )
        except Exception as e:
            logger.error(f"Error encoding message: {e}")
            raise
            
    def send_command(self, command):
        """Send a command to CAEN and return response"""
        if not self._connected:
            if not self.connect():
                return None
                
        try:
            print(command)
            with self._lock:
                # Send command
                encoded_message = self._encode_message(command)
                self._socket.send(encoded_message)
                
                # Get response
                data = self._socket.recv(BUFFER_SIZE)[8:].decode("utf-8")
                return data
        except Exception as e:
            logger.error(f"Error sending command to CAEN: {e}")
            self._connected = False
            return None
            
    def get_status(self):
        """Get current status of all channels"""
        try:
            response = self.send_command("GetStatus,PowerSupplyId:caen")
            if not response:
                return {}
                
            # Parse response
            status = {}
            for token in response.split(","):
                if token.startswith("caen"):
                    try:
                        key, value = token.split(":")
                        status[key] = float(value)
                    except:
                        continue
                        
            self._status = status
            return status
            
        except Exception as e:
            logger.error(f"Error getting CAEN status: {e}")
            return {}
            
    def turn_on_channel(self, channel):
        """Turn on a specific channel"""
        try:
            response = self.send_command(f"TurnOn,PowerSupplyId:caen,ChannelId:{channel}")
            return response is not None
        except Exception as e:
            logger.error(f"Error turning on channel {channel}: {e}")
            return False
            
    def turn_off_channel(self, channel):
        """Turn off a specific channel"""
        try:
            response = self.send_command(f"TurnOff,PowerSupplyId:caen,ChannelId:{channel}")
            return response is not None
        except Exception as e:
            logger.error(f"Error turning off channel {channel}: {e}")
            return False 
