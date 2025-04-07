from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QTimer
import logging
import json
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from thermal_ui import Ui_MainWindow

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
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

        # Disable controls until thermal camera is started
        self.enable_controls(False)

        logger.info("Thermal camera tab initialized")

    def setup_camera_views(self):
        """Setup matplotlib figures for camera views"""
        try:
            # Create scene and canvas for individual cameras view
            scene1 = QtWidgets.QGraphicsScene()
            self.ui.graphicsView.setScene(scene1)

            # Create matplotlib figure for individual cameras with adjusted size
            self.cameras_fig = Figure(figsize=(8, 6), dpi=100)  # Adjusted figure size
            self.cameras_canvas = FigureCanvas(self.cameras_fig)
            scene1.addWidget(self.cameras_canvas)

            # Create 2x2 grid for cameras with proper spacing
            self.cameras_axes = self.cameras_fig.subplots(2, 2, gridspec_kw={"hspace": 0.4, "wspace": 0.3})
            self.camera_images = []

            # Initialize camera images with proper sizing
            for i in range(2):
                for j in range(2):
                    ax = self.cameras_axes[i, j]
                    img = ax.imshow(
                        np.zeros((24, 32)),
                        cmap="plasma",
                        aspect="equal",
                        interpolation="nearest",  # Added interpolation for better display
                    )
                    self.camera_images.append(img)
                    ax.set_title(f"Camera {i*2+j+1}")  # Updated to 1-based numbering
                    ax.set_xticks([])  # Hide x-axis ticks
                    ax.set_yticks([])  # Hide y-axis ticks

                    # Add colorbar with proper sizing
                    cbar = self.cameras_fig.colorbar(img, ax=ax, fraction=0.046, pad=0.04)
                    cbar.ax.tick_params(labelsize=8)  # Adjust colorbar text size

            self.cameras_fig.tight_layout()

            # Create scene and canvas for stitched image view
            scene2 = QtWidgets.QGraphicsScene()
            self.ui.graphicsView_2.setScene(scene2)

            # Create matplotlib figure for stitched image with adjusted size
            self.stitched_fig = Figure(figsize=(10, 4), dpi=100)  # Adjusted figure size
            self.stitched_canvas = FigureCanvas(self.stitched_fig)
            scene2.addWidget(self.stitched_canvas)

            # Create axes for stitched image with proper sizing
            self.stitched_ax = self.stitched_fig.add_subplot(111)
            self.stitched_image = self.stitched_ax.imshow(
                np.zeros((24, 32)),
                cmap="plasma",
                aspect="equal",
                interpolation="nearest",  # Added interpolation for better display
            )
            self.stitched_ax.set_title("Stitched Image")
            self.stitched_ax.set_xticks([])  # Hide x-axis ticks initially
            self.stitched_ax.set_yticks([])  # Hide y-axis ticks

            # Add colorbar for stitched image with proper sizing
            cbar = self.stitched_fig.colorbar(self.stitched_image, fraction=0.046, pad=0.04)
            cbar.ax.tick_params(labelsize=8)  # Adjust colorbar text size

            self.stitched_fig.tight_layout()

            # Create and set up position display
            self.ui.positionLE = QtWidgets.QLineEdit(self.ui.centralwidget)
            self.ui.positionLE.setObjectName("positionLE")
            self.ui.positionLE.setReadOnly(True)
            self.ui.positionLE.setFixedWidth(80)
            # Add it to the grid next to the position label
            self.ui.gridLayout.addWidget(self.ui.positionLE, 11, 14, 1, 1)

            logger.info("Camera views initialized")

        except Exception as e:
            logger.error(f"Error setting up camera views: {e}")

    def enable_controls(self, enabled=True):
        """Enable or disable all controls except Start Thermal Camera button"""
        controls = [
            self.ui.rotate_PB,
            self.ui.go_to_PB,
            self.ui.calibrate_PB,
            self.ui.set_abs_pos_PB,
            self.ui.export_abs_pos_PB,
            self.ui.get_frms_PB,
            self.ui.relse_mtr_PB,
            self.ui.run_PB,
            self.ui.stop_PB,
            self.ui.ip_DAngle_LE,
            self.ui.ip_angle_LE,
            self.ui.ip_angle_LE_2,  # This is the 90-degree angle input
            self.ui.ip_abs_pos_LE,
            self.ui.checkBox,  # Clock-wise checkbox
            self.ui.checkBox_2,  # Anti-clockwise checkbox
        ]
        for control in controls:
            control.setEnabled(enabled)

    def connect_signals(self):
        """Connect UI signals to their handlers"""
        try:
            # Connect buttons to their respective functions
            self.ui.start_tc_PB.clicked.connect(self.start_thermal_camera)
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
            if not self.system or not hasattr(self.system, "status"):
                return

            status = self.system.status.get("thermal_camera", {})
            if not status:
                return

            # Update position display
            if "position" in status:
                self.ui.positionLE.setText(f"{status['position']:.2f}")

            # Update running status
            if "running" in status:
                self.ui.run_stat_flg.setStyleSheet(
                    "background-color: green;" if status["running"] else "background-color: red;"
                )

            # Update streaming status
            if "streaming" in status:
                self.ui.streamin_image_flag.setStyleSheet(
                    "background-color: green;" if status["streaming"] else "background-color: red;"
                )

            # Update camera images with proper scaling
            if hasattr(self.system._thermalcamera, "_images"):
                for i, (camera_name, image_data) in enumerate(self.system._thermalcamera._images.items()):
                    if isinstance(image_data, np.ndarray):
                        # Update image data
                        self.camera_images[i].set_array(image_data)

                        # Calculate temperature range for consistent scaling
                        vmin = np.nanmin(image_data)
                        vmax = np.nanmax(image_data)
                        self.camera_images[i].set_clim(vmin, vmax)

                        # Update colorbar ticks
                        cbar = self.camera_images[i].colorbar
                        if cbar is not None:
                            cbar.set_ticks(np.linspace(vmin, vmax, 5))
                            cbar.set_ticklabels([f"{temp:.1f}°C" for temp in np.linspace(vmin, vmax, 5)])

                self.cameras_canvas.draw()

            # Update stitched image if available
            if hasattr(self.system._thermalcamera, "_figure_data"):
                figure_data = self.system._thermalcamera._figure_data
                if figure_data is not None and isinstance(figure_data, dict):
                    # Update image data
                    if "image" in figure_data:
                        self.stitched_image.set_array(figure_data["image"])

                        # Set temperature range
                        if "temp_min" in figure_data and "temp_max" in figure_data:
                            self.stitched_image.set_clim(figure_data["temp_min"], figure_data["temp_max"])

                    # Update x-axis if angle information is available
                    if "xticks" in figure_data and "xticklabels" in figure_data:
                        self.stitched_ax.set_xticks(figure_data["xticks"])
                        self.stitched_ax.set_xticklabels(figure_data["xticklabels"])
                        self.stitched_ax.set_xlabel("Angle (degrees)")

                    # Update colorbar
                    if "temp_min" in figure_data and "temp_max" in figure_data:
                        cbar = self.stitched_image.colorbar
                        if cbar is not None:
                            ticks = np.linspace(figure_data["temp_min"], figure_data["temp_max"], 5)
                            cbar.set_ticks(ticks)
                            cbar.set_ticklabels([f"{temp:.1f}°C" for temp in ticks])
                            cbar.set_label("Temperature (°C)")

                    self.stitched_canvas.draw()

        except Exception as e:
            logger.error(f"Error updating status: {e}")

    def rotate(self):
        """Rotate the thermal camera by the specified angle"""
        try:
            angle = float(self.ui.ip_DAngle_LE.text())
            if self.system._thermalcamera:
                if self.ui.checkBox.isChecked():
                    direction = "bw"
                elif self.ui.checkBox_2.isChecked():
                    direction = "fw"
                else:
                    raise ValueError("No direction selected")
                self.system._thermalcamera.rotate({"angle": angle, "direction": direction})
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
                self.system._thermalcamera.go_to({"position": angle})
                logger.info(f"Moving camera to {angle} degrees")
        except ValueError:
            logger.error("Invalid angle value")
        except Exception as e:
            logger.error(f"Error moving camera: {e}")

    def calibrate(self):
        """Calibrate the thermal camera"""
        try:
            # Use ip_angle_LE_2 which contains the 90-degree angle input
            limit = float(self.ui.ip_angle_LE_2.text())
            if self.system._thermalcamera:
                if self.system._thermalcamera:
                    if self.ui.checkBox.isChecked():
                        direction = "bw"
                    elif self.ui.checkBox_2.isChecked():
                        direction = "fw"
                    else:
                        raise ValueError("No direction selected")
                self.system._thermalcamera.calibrate({"prudence": limit, "direction": direction})
                logger.info(f"Calibrating camera with limit {limit} degrees")
        except ValueError:
            logger.error("Invalid angle limit value")
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

    def start_thermal_camera(self):
        """Initialize and start the thermal camera"""
        try:
            if self.system._thermalcamera:
                self.system._thermalcamera.initialize({})
                self.enable_controls(True)
                self.ui.start_tc_PB.setEnabled(False)
                logger.info("Thermal camera initialized")
        except Exception as e:
            logger.error(f"Error initializing thermal camera: {e}")

    def closeEvent(self, event):
        """Handle widget close event"""
        try:
            self.update_timer.stop()
            event.accept()
        except Exception as e:
            logger.error(f"Error in close event: {e}")
            event.accept()
