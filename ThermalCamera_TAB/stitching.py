import time
import json
import numpy as np
from matplotlib import pyplot as plt


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


def recalibrate_to_degrees(panorama, min_angle, max_angle, temp_min, temp_max, full_coverage=360):
    """Recalibrate the panorama to show angle in degrees and temperature in Celsius"""
    h, w = panorama.shape[:2]

    # Create a figure with proper x-axis in degrees
    plt.figure(figsize=(15, 6))
    img_display = plt.imshow(panorama, cmap="plasma", vmin=0, vmax=255)

    # Determine appropriate angle range for x-axis
    if max_angle - min_angle >= full_coverage - 10:  # Close enough to full coverage
        # For full coverage, show 0-360
        display_min = 0
        display_max = full_coverage
    else:
        # For partial coverage, show the actual min-max angles
        display_min = min_angle
        display_max = max_angle

    # Set x-axis ticks to show angles
    plt.xticks(np.linspace(0, w, 8), np.linspace(display_min, display_max, 8).round(1))

    plt.xlabel("Angle (degrees)")
    plt.yticks([])

    # Add colorbar to show temperature scale
    cbar = plt.colorbar(img_display, orientation="horizontal")

    # Create temperature tick positions that map to the 0-255 color range
    cbar_ticks = np.linspace(0, 255, 6)
    cbar_labels = np.linspace(temp_min, temp_max, 6).round(1)
    cbar.set_ticks(cbar_ticks)
    cbar.set_ticklabels([f"{t}°C" for t in cbar_labels])
    cbar.set_label("Temperature (°C)")

    plt.tight_layout()
    return plt.gcf()


def plot_circular_panorama(panorama, min_angle, max_angle, temp_min, temp_max, radius_range=(0.6, 0.9)):
    """
    Plot the panorama in a ring format

    Parameters:
    - panorama: The stitched panorama image
    - min_angle, max_angle: The angle range covered by the panorama in degrees
    - temp_min, temp_max: Temperature range in Celsius for colorbar
    - radius_range: Inner and outer radius of the ring as fraction of max radius
    """
    # Create a figure with polar projection
    fig = plt.figure(figsize=(12, 12))
    ax = fig.add_subplot(111, projection="polar")

    # Get dimensions
    h, w = panorama.shape

    # Create meshgrid in polar coordinates
    min_angle_rad = np.radians(min_angle)
    max_angle_rad = np.radians(max_angle)

    # Make sure max_angle_rad is greater than min_angle_rad
    if max_angle_rad <= min_angle_rad:
        max_angle_rad += 2 * np.pi

    # Create theta and r values
    theta_vals = np.linspace(min_angle_rad, max_angle_rad, w)

    # FIXED: Correctly use inner and outer radius
    inner_radius, outer_radius = radius_range

    # Create r values with proper spacing
    r_vals = np.linspace(outer_radius, inner_radius, h)  # Reversed for correct image orientation

    # Create the meshgrid
    theta, r = np.meshgrid(theta_vals, r_vals)

    # Normalize the panorama for colormap
    if temp_max > temp_min:
        normalized_data = (panorama.astype(float) / 255) * (temp_max - temp_min) + temp_min
    else:
        normalized_data = panorama.astype(float)

    # Plot using pcolormesh which works well with polar projection
    cax = ax.pcolormesh(theta, r, normalized_data, cmap="plasma", vmin=temp_min, vmax=temp_max)

    # Set the direction of theta increasing (clockwise)
    ax.set_theta_direction(-1)  # -1 for clockwise

    # Set where theta=0 is located
    ax.set_theta_zero_location("N")  # North

    # FIXED: Set the limits properly to show the entire ring
    # The minimum should be slightly smaller than inner_radius to ensure the entire ring is visible
    ax.set_rlim(inner_radius, outer_radius)

    # Empty the center of the ring by creating a white circle - only if inner_radius > 0
    if inner_radius > 0:
        center_circle = plt.Circle(
            (0, 0), inner_radius, transform=ax.transData._b, zorder=10, edgecolor="black", facecolor="white"
        )
        ax.add_artist(center_circle)

    # Set custom theta ticks
    angle_ticks = np.linspace(min_angle, max_angle, 8, endpoint=min_angle != max_angle - 360)
    angle_ticks = angle_ticks % 360
    ax.set_xticks(np.radians(angle_ticks))
    ax.set_xticklabels([f"{int(a)}°" for a in angle_ticks])

    # Remove radial ticks and labels
    ax.set_yticks([])
    ax.grid(False)

    # Add a colorbar
    cbar = fig.colorbar(cax, ax=ax, orientation="horizontal", pad=0.08, label="Temperature (°C)")

    # Add title
    plt.tight_layout()
    return fig


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

    # First pass to determine global temperature range
    for position in positions:
        # Get the image data for this position
        image_data = camera_data[position]
        if isinstance(image_data, list) and len(image_data) > 0:
            # Convert string image data to numpy array if needed. Average all images for this position
            # to get a single representative image
            img = np.array(image_data[0])
            if len(image_data) > 1:
                img = np.mean([np.array(data) for data in image_data], axis=0)
            images.append(img)

            # Update global min/max temperature values
            current_min = np.min(img)
            current_max = np.max(img)

            if current_min < temp_min:
                temp_min = current_min
            if current_max > temp_max:
                temp_max = current_max

    # Second pass to load images
    for position in positions:
        # Get the image data for this position
        image_data = camera_data[position]
        if isinstance(image_data, list) and len(image_data) > 0:
            # Convert string image data to numpy array if needed
            img = np.array(image_data[0])
            if len(image_data) > 1:
                img = np.mean([np.array(data) for data in image_data], axis=0)
            images.append(img)
            angles.append(float(position))

    return images, angles, temp_min, temp_max


def process_all_cameras(cameras):
    for name in cameras.keys():
        images, angles, temp_min, temp_max = process_camera_data(name, cameras)
        # Generate panoramas for each camera
        if len(images) > 0:
            angle_range = max(angles) - min(angles)
            full_coverage = 360 if angle_range > 300 else angle_range + 20
            pixel_panorama = stitch_images_pixel_based(images, angles, temp_min, temp_max, full_coverage)
            angle_calibrated_fig = recalibrate_to_degrees(
                pixel_panorama, min(angles), max(angles), temp_min, temp_max, full_coverage
            )
            ring_fig1 = plot_circular_panorama(
                pixel_panorama, min(angles), max(angles), temp_min, temp_max, radius_range=(0.3, 1.0)
            )
            # Save results
            angle_calibrated_fig.savefig(f"{name}_linear.jpg")
            ring_fig1.savefig(f"{name}_circular.jpg")


def load_data(file_path):
    """Load data from a JSON file"""
    with open(file_path, "r") as file:
        data = json.load(file)
    return data


def execute_stitching():
    """Main function to execute stitching"""
    cameras = load_data("stitching_data_preprocessed.json")
    process_all_cameras(cameras)


def loop():
    """Main loop to process all cameras"""
    while True:
        execute_stitching()


if __name__ == "__main__":
    execute_stitching()
