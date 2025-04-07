import time
import json
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
import threading


def manual_stitch_images(images, angles, temp_min, temp_max, full_coverage=360):
    """Manual stitching if OpenCV stitcher fails"""
    # Get dimensions of a single image
    h, w = images[0].shape

    # Calculate total width based on full coverage and FOV
    # If full_coverage is 360, we'll create a full panorama
    total_width = int(w * full_coverage / 20)

    # Create canvas and count arrays for tracking overlaps
    panorama = np.zeros((h, total_width), dtype=np.float32)
    overlap_count = np.zeros((h, total_width), dtype=np.float32)

    # Place images on canvas based on absolute position within the full range
    for i, (img, angle) in enumerate(zip(images, angles)):
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
    panorama_norm = 255 * (panorama - temp_min) / (temp_max - temp_min)
    # Areas without data will be black (0)
    panorama_norm = np.clip(panorama_norm, 0, 255)  # Ensure values are in valid range
    panorama_norm = panorama_norm.astype(np.uint8)

    return panorama_norm, panorama  # Return both normalized and raw temperature data


def stitch_images_pixel_based(images, angles, temp_min, temp_max, full_coverage=360):
    # Make sure images are 8-bit single channel
    # Normalize to 0-255 range while preserving temperature scale
    images_8bit = []
    for img in images:
        img_norm = 255 * (img - temp_min) / (temp_max - temp_min)
        img_norm = np.clip(img_norm, 0, 255)
        images_8bit.append(img_norm.astype(np.uint8))

    # If built-in stitcher fails, fall back to manual stitching approach
    panorama_norm, _ = manual_stitch_images(images, angles, temp_min, temp_max, full_coverage)
    return panorama_norm


def create_figure_data(panorama, min_angle, max_angle, temp_min, temp_max, full_coverage=360):
    """Create data for figure without actually creating the figure"""
    h, w = panorama.shape[:2]

    # Determine appropriate angle range for x-axis
    if max_angle - min_angle >= full_coverage - 10:  # Close enough to full coverage
        # For full coverage, show 0-360
        display_min = 0
        display_max = full_coverage
    else:
        # For partial coverage, show the actual min-max angles
        display_min = min_angle
        display_max = max_angle

    # Create x-axis ticks
    xticks = np.linspace(0, w, 8)
    xticklabels = np.linspace(display_min, display_max, 8).round(1)

    # Create temperature tick positions that map to the 0-255 color range
    cbar_ticks = np.linspace(0, 255, 6)
    cbar_labels = np.linspace(temp_min, temp_max, 6).round(1)
    cbar_ticklabels = [f"{t}°C" for t in cbar_labels]

    return {
        'image': panorama,
        'xticks': xticks,
        'xticklabels': xticklabels,
        'cbar_ticks': cbar_ticks,
        'cbar_ticklabels': cbar_ticklabels,
        'temp_min': temp_min,
        'temp_max': temp_max
    }


def create_circular_data(panorama, min_angle, max_angle, temp_min, temp_max, radius_range=(0.6, 0.9)):
    """Create data for circular plot without creating the figure"""
    h, w = panorama.shape

    # Create theta and r values
    min_angle_rad = np.radians(min_angle)
    max_angle_rad = np.radians(max_angle)

    # Make sure max_angle_rad is greater than min_angle_rad
    if max_angle_rad <= min_angle_rad:
        max_angle_rad += 2 * np.pi

    # Create theta values
    theta_vals = np.linspace(min_angle_rad, max_angle_rad, w)

    # Create r values with proper spacing
    inner_radius, outer_radius = radius_range
    r_vals = np.linspace(outer_radius, inner_radius, h)  # Reversed for correct image orientation

    # Create the meshgrid
    theta, r = np.meshgrid(theta_vals, r_vals)

    # Normalize the panorama for colormap
    if temp_max > temp_min:
        normalized_data = (panorama.astype(float) / 255) * (temp_max - temp_min) + temp_min
    else:
        normalized_data = panorama.astype(float)

    # Create angle ticks
    angle_ticks = np.linspace(min_angle, max_angle, 8, endpoint=min_angle != max_angle - 360)
    angle_ticks = angle_ticks % 360
    angle_tick_positions = np.radians(angle_ticks)
    angle_tick_labels = [f"{int(a)}°" for a in angle_ticks]

    return {
        'theta': theta,
        'r': r,
        'data': normalized_data,
        'angle_tick_positions': angle_tick_positions,
        'angle_tick_labels': angle_tick_labels,
        'inner_radius': inner_radius,
        'outer_radius': outer_radius,
        'temp_min': temp_min,
        'temp_max': temp_max
    }


def process_camera_data(camera_name, cameras):
    """Process camera data to generate panoramas"""
    camera_data = cameras[camera_name]
    positions = list(camera_data.keys())

    # Sort positions based on angle (convert from string to float)
    positions = sorted(positions, key=lambda x: float(x))

    # Step 1: Load and prepare images
    images = []
    angles = []
    temp_min = float("inf")
    temp_max = float("-inf")

    for pos in positions:
        # Get all images at this position and average them
        pos_images = camera_data[pos]
        if pos_images:
            # Average all images at this position
            avg_img = np.mean(pos_images, axis=0)
            images.append(avg_img)
            angles.append(float(pos))

            # Update temperature range
            temp_min = min(temp_min, avg_img.min())
            temp_max = max(temp_max, avg_img.max())

    # Step 2: Stitch images
    panorama = stitch_images_pixel_based(images, angles, temp_min, temp_max)

    # Step 3: Create figure data
    figure_data = create_figure_data(panorama, min(angles), max(angles), temp_min, temp_max)
    circular_data = create_circular_data(panorama, min(angles), max(angles), temp_min, temp_max)

    return figure_data, circular_data


def process_all_cameras(cameras, settings=None):
    """Process all cameras and return figure data"""
    # Get the camera to use from settings
    camera_name = "camera0"  # Default to camera0
    if settings and "ThermalCamera" in settings and "stitch_camera" in settings["ThermalCamera"]:
        camera_name = settings["ThermalCamera"]["stitch_camera"]
    
    if camera_name in cameras:
        figure_data, circular_data = process_camera_data(camera_name, cameras)
        return figure_data, circular_data
    return None, None


def load_data(file_path):
    """Load data from a JSON file"""
    with open(file_path, "r") as f:
        return json.load(f)


def execute_stitching():
    """Execute the stitching process"""
    data = load_data("data.json")
    process_all_cameras(data)


def loop():
    """Main loop for testing"""
    while True:
        execute_stitching()
        time.sleep(1)


if __name__ == "__main__":
    loop()
