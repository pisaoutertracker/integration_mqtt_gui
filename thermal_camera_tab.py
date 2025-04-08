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
            self.cameras_fig = Figure(figsize=(8, 5), dpi=100)  # Increased width
            self.cameras_canvas = FigureCanvas(self.cameras_fig)
            scene1.addWidget(self.cameras_canvas)

            # Create 2x2 grid for cameras with minimal spacing
            self.cameras_axes = self.cameras_fig.subplots(2, 2, gridspec_kw={"hspace": 0.15, "wspace": 0.1})
            self.camera_images = []

            # Initialize camera images with proper sizing
            for i in range(2):
                for j in range(2):
                    ax = self.cameras_axes[i, j]
                    img = ax.imshow(np.zeros((24, 32)), cmap="plasma", aspect="equal", interpolation="nearest")
                    self.camera_images.append(img)
                    ax.set_title(f"Camera {i*2+j+1}")
                    ax.set_xticks([])
                    ax.set_yticks([])

                    # Add colorbar with proper sizing
                    cbar = self.cameras_fig.colorbar(img, ax=ax, fraction=0.046, pad=0.04)
                    cbar.ax.tick_params(labelsize=8)

            # Adjust subplot parameters to remove excess whitespace
            self.cameras_fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)

            # Create tab widget for stitched views
            self.stitched_tab_widget = QtWidgets.QTabWidget()
            self.ui.gridLayout.addWidget(self.stitched_tab_widget, 13, 0, 1, 16)

            # Create stitched view for each camera
            self.stitched_figs = []
            self.stitched_canvases = []
            self.stitched_images = []
            self.stitched_axes = []

            tab_names = ["Camera 1", "Camera 2", "Camera 3", "Camera 4"]
            for tab_name in tab_names:
                # Create tab widget
                tab = QtWidgets.QWidget()
                tab_layout = QtWidgets.QVBoxLayout(tab)

                # Create figure and canvas with proper aspect ratio for 360-degree view
                fig = Figure(figsize=(12, 3), dpi=100)
                canvas = FigureCanvas(fig)
                tab_layout.addWidget(canvas)

                # Create axes and image
                ax = fig.add_subplot(111)
                # Initialize with a 360-degree wide array
                img = ax.imshow(
                    np.zeros((24, 360)),  # Full 360-degree width
                    cmap="plasma",
                    aspect="auto",  # Use 'auto' to fill the space
                    interpolation="nearest",
                    extent=[0, 360, 0, 24],  # Set the extent to match degrees
                )

                # Set up the axes for degrees
                # ax.set_xlabel("Angle (degrees)") ! Do not set xlabel
                ax.set_xticks(np.linspace(0, 360, 9))  # Ticks every 45 degrees
                ax.set_yticks([])

                # Add colorbar
                cbar = fig.colorbar(img, fraction=0.046, pad=0.04)
                cbar.ax.tick_params(labelsize=8)

                # Adjust subplot parameters to maximize image space
                fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.15)

                # Store references
                self.stitched_figs.append(fig)
                self.stitched_canvases.append(canvas)
                self.stitched_images.append(img)
                self.stitched_axes.append(ax)

                # Add tab
                self.stitched_tab_widget.addTab(tab, tab_name)

            # Remove the old graphicsView_2 since we're using tabs now
            self.ui.graphicsView_2.setParent(None)

            # Create and set up position display
            self.ui.positionLE = QtWidgets.QLineEdit(self.ui.centralwidget)
            self.ui.positionLE.setObjectName("positionLE")
            self.ui.positionLE.setReadOnly(True)
            self.ui.positionLE.setFixedWidth(80)
            self.ui.gridLayout.addWidget(self.ui.positionLE, 11, 14, 1, 1)

            # Make status LEDs more visible with MARTA style
            self.ui.streamin_image_flag.setMinimumSize(30, 20)
            self.ui.streamin_image_flag.setMaximumSize(30, 20)
            self.ui.run_stat_flg.setMinimumSize(30, 20)
            self.ui.run_stat_flg.setMaximumSize(30, 20)

            # Update LED style to match MARTA coldroom tab
            led_style = """
                QFrame {
                    border: 1px solid black;
                    background-color: %s;
                }
            """
            self.ui.streamin_image_flag.setStyleSheet(led_style % "red")
            self.ui.run_stat_flg.setStyleSheet(led_style % "red")

            # Set the minimum width of the main window to accommodate the cameras
            self.widget.setMinimumWidth(1600)  # Increased width to avoid scrollbars

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
            self.ui.direction_combo,  # Direction combobox
        ]
        for control in controls:
            control.setEnabled(enabled)

    def connect_signals(self):
        """Connect UI signals to their handlers"""
        try:
            # Connect buttons to their respective functions
            self.ui.relse_mtr_PB_2.clicked.connect(self.start_thermal_camera)  # This is the Start Thermal Camera button
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

    def stitch_multiple_images(self, images, positions, temp_min, temp_max, full_coverage=360):
        """Stitch multiple images from different positions into a panorama"""
        # Get dimensions of a single image
        h, w = images[0].shape

        # Calculate total width based on full coverage and FOV
        total_width = int(w * full_coverage / 20)

        # Create canvas and count arrays for tracking overlaps
        panorama = np.zeros((h, total_width), dtype=np.float32)
        overlap_count = np.zeros((h, total_width), dtype=np.float32)

        # Place images on canvas based on absolute position within the full range
        for img, angle in zip(images, positions):
            # Calculate x offset based on absolute angle position in the full range
            # Normalize angle to 0-360 range if needed
            norm_angle = angle % full_coverage
            x_offset = int(norm_angle * w / 20)

            # Make sure offset is within bounds
            if x_offset + w <= total_width:
                # Add image to panorama (accumulate values)
                panorama[:, x_offset : x_offset + w] += img
                # Increment counter for overlapping pixels
                overlap_count[:, x_offset : x_offset + w] += 1
            else:
                # Handle case where image would wrap around
                wrap_width = total_width - x_offset
                # Add first part
                panorama[:, x_offset:] += img[:, :wrap_width]
                overlap_count[:, x_offset:] += 1
                # Add second part (wrap around)
                panorama[:, : w - wrap_width] += img[:, wrap_width:]
                overlap_count[:, : w - wrap_width] += 1

        # Compute mean for overlapping regions (avoid division by zero)
        mask = overlap_count > 0
        panorama[mask] = panorama[mask] / overlap_count[mask]

        # Convert to uint8 for display - use actual temperature range
        if np.isclose(temp_min, temp_max):
            temp_max = temp_min + 1.0  # Add a small difference to avoid division by zero
        
        # Create normalized array with proper handling of NaN values
        panorama_norm = np.zeros_like(panorama)
        valid_mask = ~np.isnan(panorama)
        panorama_norm[valid_mask] = 255 * (panorama[valid_mask] - temp_min) / (temp_max - temp_min)
        
        # Areas without data will be black (0)
        panorama_norm = np.nan_to_num(panorama_norm, nan=0.0)  # Convert NaNs to 0
        panorama_norm = np.clip(panorama_norm, 0, 255)  # Ensure values are in valid range
        panorama_norm = panorama_norm.astype(np.uint8)

        return panorama_norm, panorama

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

            # Update running status with MARTA style LED
            if "running" in status:
                led_style = """
                    QFrame {
                        border: 1px solid black;
                        background-color: %s;
                    }
                """
                self.ui.run_stat_flg.setStyleSheet(led_style % ("green" if status["running"] else "red"))

            # Update streaming status with MARTA style LED
            if "streaming" in status:
                led_style = """
                    QFrame {
                        border: 1px solid black;
                        background-color: %s;
                    }
                """
                self.ui.streamin_image_flag.setStyleSheet(led_style % ("green" if status["streaming"] else "red"))

            # Update camera images with proper scaling
            if hasattr(self.system._thermalcamera, "_images"):
                # First update individual camera views
                for i, (camera_name, image_data) in enumerate(self.system._thermalcamera._images.items()):
                    if isinstance(image_data, np.ndarray):
                        # Convert to float if needed
                        if image_data.dtype != np.float64:
                            try:
                                image_data = image_data.astype(np.float64)
                            except (ValueError, TypeError) as e:
                                logger.error(f"Failed to convert image data to float: {e}")
                                continue

                        # Update individual camera view
                        self.camera_images[i].set_array(image_data)

                        # Calculate temperature range for consistent scaling
                        vmin = np.nanmin(image_data)
                        vmax = np.nanmax(image_data)
                        self.camera_images[i].set_clim(vmin, vmax)

                        # Update colorbar ticks for camera view
                        cbar = self.camera_images[i].colorbar
                        if cbar is not None:
                            cbar.set_ticks(np.linspace(vmin, vmax, 5))
                            cbar.set_ticklabels([f"{temp:.1f}°C" for temp in np.linspace(vmin, vmax, 5)])

                # Draw camera canvas
                self.cameras_canvas.draw()

                # Create stitched images using the accumulated data
                try:
                    # Get stitching data from thermal camera
                    if hasattr(self.system._thermalcamera, "_stitching_data"):
                        for i, (camera_name, camera_data) in enumerate(self.system._thermalcamera._stitching_data.items()):
                            if camera_data:  # If we have data for this camera
                                # Get all images and positions
                                images = []
                                positions = []
                                temp_min = float("inf")
                                temp_max = float("-inf")

                                # Collect all images and positions
                                for pos, pos_images in camera_data.items():
                                    if pos_images:  # If we have images at this position
                                        # Average all images at this position
                                        avg_img = np.mean(pos_images, axis=0)
                                        images.append(avg_img)
                                        positions.append(float(pos))

                                        # Update temperature range
                                        temp_min = min(temp_min, avg_img.min())
                                        temp_max = max(temp_max, avg_img.max())

                                if images:  # If we have any images to stitch
                                    # Create stitched panorama
                                    panorama_norm, panorama = self.stitch_multiple_images(
                                        images, positions, temp_min, temp_max, full_coverage=360
                                    )

                                    # Ensure the panorama is properly sized for 360 degrees
                                    if panorama.shape[1] != 360:
                                        # Resize to 360 degrees if needed
                                        from scipy.ndimage import zoom
                                        zoom_factor = (1, 360 / panorama.shape[1])
                                        panorama = zoom(panorama, zoom_factor, order=1)

                                    # Update the stitched view
                                    self.stitched_images[i].set_array(panorama)
                                    self.stitched_images[i].set_clim(temp_min, temp_max)

                                    # Update colorbar
                                    cbar = self.stitched_images[i].colorbar
                                    if cbar is not None:
                                        cbar.set_ticks(np.linspace(temp_min, temp_max, 5))
                                        cbar.set_ticklabels([f"{temp:.1f}°C" for temp in np.linspace(temp_min, temp_max, 5)])

                                    # Draw canvas
                                    self.stitched_canvases[i].draw()

                except Exception as e:
                    logger.error(f"Error creating stitched images: {e}")
                    logger.error(f"Error details: {str(e)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error updating status: {e}")
            logger.error(f"Error details: {str(e)}", exc_info=True)

    def rotate(self):
        """Rotate the thermal camera by the specified angle"""
        try:
            angle = float(self.ui.ip_DAngle_LE.text())
            if self.system._thermalcamera:
                direction = "bw" if self.ui.direction_combo.currentText() == "Clockwise" else "fw"
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
                direction = "bw" if self.ui.direction_combo.currentText() == "Clockwise" else "fw"
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
                # Add logging to check available methods
                logger.info("Starting thermal camera")

                # Try using init method instead of initialize
                self.system._thermalcamera.init({})
                self.enable_controls(True)
                self.ui.relse_mtr_PB_2.setEnabled(False)  # Disable start button
                logger.info("Thermal camera initialized")
        except Exception as e:
            logger.error(f"Error using alternative init method: {e}")
            self.enable_controls(False)
            self.ui.relse_mtr_PB_2.setEnabled(True)  # Re-enable start button

    def closeEvent(self, event):
        """Handle widget close event"""
        try:
            self.update_timer.stop()
            event.accept()
        except Exception as e:
            logger.error(f"Error in close event: {e}")
            event.accept()
