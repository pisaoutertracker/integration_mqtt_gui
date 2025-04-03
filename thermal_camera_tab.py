from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QTimer
import logging
import json
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from thermal_ui import Ui_MainWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ThermalCameraTab(QtWidgets.QWidget):
    def __init__(self, system):
        super(ThermalCameraTab, self).__init__()
        self.system = system
        
        # Create widget to hold the UI
        self.widget = QtWidgets.QMainWindow()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self.widget)
        
        # Create layout for this widget and add the UI
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addWidget(self.widget)
        
        # Initialize matplotlib figures
        self.setup_camera_views()
        
        # Connect signals
        self.connect_signals()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)  # Update every second
        
        logger.info("Thermal camera tab initialized")
        
    def setup_camera_views(self):
        """Setup matplotlib figures for camera views"""
        try:
            # Create scene and canvas for individual cameras view
            scene1 = QtWidgets.QGraphicsScene()
            self.ui.graphicsView.setScene(scene1)
            
            # Create matplotlib figure for individual cameras
            self.cameras_fig = Figure(figsize=(8, 6))
            self.cameras_canvas = FigureCanvas(self.cameras_fig)
            scene1.addWidget(self.cameras_canvas)
            
            # Create 2x2 grid for cameras
            self.cameras_axes = self.cameras_fig.subplots(2, 2)
            self.camera_images = []
            
            # Initialize camera images
            for i in range(2):
                for j in range(2):
                    img = self.cameras_axes[i, j].imshow(
                        np.zeros((24, 32)),
                        cmap='plasma',
                        aspect='auto'
                    )
                    self.camera_images.append(img)
                    self.cameras_axes[i, j].set_title(f"Camera {i*2+j}")
                    
            self.cameras_fig.tight_layout()
            
            # Create scene and canvas for stitched image view
            scene2 = QtWidgets.QGraphicsScene()
            self.ui.graphicsView_2.setScene(scene2)
            
            # Create matplotlib figure for stitched image
            self.stitched_fig = Figure(figsize=(8, 6))
            self.stitched_canvas = FigureCanvas(self.stitched_fig)
            scene2.addWidget(self.stitched_canvas)
            
            # Create axes for stitched image
            self.stitched_ax = self.stitched_fig.add_subplot(111)
            self.stitched_image = self.stitched_ax.imshow(
                np.zeros((24, 32)),
                cmap='plasma',
                aspect='auto'
            )
            self.stitched_ax.set_title("Stitched Image")
            
            self.stitched_fig.tight_layout()
            
            logger.info("Camera views initialized")
            
        except Exception as e:
            logger.error(f"Error setting up camera views: {e}")
            
    def connect_signals(self):
        """Connect UI signals to their handlers"""
        try:
            # Connect buttons to their respective functions
            self.ui.rotate_PB.clicked.connect(self.rotate)
            self.ui.go_to_PB.clicked.connect(self.go_to)
            self.ui.calibrate_PB.clicked.connect(self.calibrate)
            self.ui.set_abs_pos_PB.clicked.connect(self.set_absolute_position)
            self.ui.export_abs_pos_PB.clicked.connect(self.export_absolute_position)
            self.ui.get_frms_PB.clicked.connect(self.get_frames)
            self.ui.relse_mtr_PB.clicked.connect(self.release_motor)
            self.ui.run_PB.clicked.connect(self.run)
            self.ui.stop_PB.clicked.connect(self.stop)
            
            logger.info("Thermal camera signals connected")
        except Exception as e:
            logger.error(f"Error connecting signals: {e}")
            
    def update_status(self):
        """Update UI with current thermal camera status"""
        try:
            if not self.system or not hasattr(self.system, 'status'):
                return
                
            status = self.system.status.get('thermal_camera', {})
            if not status:
                return
                
            # Update position display
            if 'position' in status:
                self.ui.positionLE.setText(f"{status['position']:.2f}")
                
            # Update running status
            if 'running' in status:
                self.ui.run_stat_flg.setStyleSheet(
                    "background-color: green;" if status['running'] else "background-color: red;"
                )
                
            # Update streaming status
            if 'streaming' in status:
                self.ui.streamin_image_flag.setStyleSheet(
                    "background-color: green;" if status['streaming'] else "background-color: red;"
                )
                
            # Update camera images
            if hasattr(self.system._thermalcamera, '_images'):
                for i, (camera_name, image_data) in enumerate(self.system._thermalcamera._images.items()):
                    if isinstance(image_data, np.ndarray):
                        self.camera_images[i].set_array(image_data)
                        self.camera_images[i].set_clim(image_data.min(), image_data.max())
                
                self.cameras_canvas.draw()
                
            # Update stitched image if available
            if hasattr(self.system._thermalcamera, '_stitched_figures'):
                stitched = self.system._thermalcamera._stitched_figures
                if stitched is not None:
                    self.stitched_image.set_array(stitched)
                    self.stitched_image.set_clim(stitched.min(), stitched.max())
                    self.stitched_canvas.draw()
                
        except Exception as e:
            logger.error(f"Error updating status: {e}")
            
    def rotate(self):
        """Rotate the thermal camera by the specified angle"""
        try:
            angle = float(self.ui.ip_DAngle_LE.text())
            if self.system._thermalcamera:
                self.system._thermalcamera.rotate({"angle": angle})
                logger.info(f"Rotating camera by {angle} degrees")
        except ValueError:
            logger.error("Invalid angle value")
        except Exception as e:
            logger.error(f"Error rotating camera: {e}")
            
    def go_to(self):
        """Go to the specified angle"""
        try:
            angle = float(self.ui.ip_angle_LE.text())
            if self.system._thermalcamera:
                self.system._thermalcamera.go_to({"angle": angle})
                logger.info(f"Moving camera to {angle} degrees")
        except ValueError:
            logger.error("Invalid angle value")
        except Exception as e:
            logger.error(f"Error moving camera: {e}")
            
    def calibrate(self):
        """Calibrate the thermal camera"""
        try:
            limit = self.ui.angle_limit_DSB.value()
            if self.system._thermalcamera:
                self.system._thermalcamera.calibrate({"limit": limit})
                logger.info("Calibrating camera")
        except Exception as e:
            logger.error(f"Error calibrating camera: {e}")
            
    def set_absolute_position(self):
        """Set the absolute position"""
        try:
            position = float(self.ui.ip_abs_pos_LE.text())
            if self.system._thermalcamera:
                self.system._thermalcamera.set_absolute_position({"position": position})
                logger.info(f"Setting absolute position to {position}")
        except ValueError:
            logger.error("Invalid position value")
        except Exception as e:
            logger.error(f"Error setting absolute position: {e}")
            
    def export_absolute_position(self):
        """Export the absolute position"""
        try:
            if self.system._thermalcamera:
                self.system._thermalcamera.export_absolute_position({})
                logger.info("Exporting absolute position")
        except Exception as e:
            logger.error(f"Error exporting absolute position: {e}")
            
    def get_frames(self):
        """Get frames from all cameras"""
        try:
            if self.system._thermalcamera:
                self.system._thermalcamera.get_frames({})
                logger.info("Getting frames from all cameras")
        except Exception as e:
            logger.error(f"Error getting frames: {e}")
            
    def release_motor(self):
        """Release the stepper motor"""
        try:
            if self.system._thermalcamera:
                self.system._thermalcamera.release({})
                logger.info("Releasing stepper motor")
        except Exception as e:
            logger.error(f"Error releasing motor: {e}")
            
    def run(self):
        """Start the thermal camera process"""
        try:
            if self.system._thermalcamera:
                self.system._thermalcamera.run({})
                logger.info("Starting thermal camera process")
        except Exception as e:
            logger.error(f"Error starting process: {e}")
            
    def stop(self):
        """Stop the thermal camera process"""
        try:
            if self.system._thermalcamera:
                self.system._thermalcamera.stop({})
                logger.info("Stopping thermal camera process")
        except Exception as e:
            logger.error(f"Error stopping process: {e}")
            
    def closeEvent(self, event):
        """Handle widget close event"""
        try:
            self.update_timer.stop()
            event.accept()
        except Exception as e:
            logger.error(f"Error in close event: {e}")
            event.accept() 