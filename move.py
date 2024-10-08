import argparse
import json
import os
import time
from visca_over_ip import Camera

# Constants
PTZ_FILES_DIR = "C:\Dev\Cam-Animator\ptz_positions"  # Directory to store PTZ positions

# Ensure directory for PTZ files exists
os.makedirs(PTZ_FILES_DIR, exist_ok=True)

def save_position(ip, mode, position):
    """Save the PTZ position to a file."""
    file_path = os.path.join(PTZ_FILES_DIR, f"{ip}_{mode}.json")
    with open(file_path, 'w') as f:
        json.dump(position, f)

def load_position(ip, mode):
    """Load the PTZ position from a file."""
    file_path = os.path.join(PTZ_FILES_DIR, f"{ip}_{mode}.json")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No saved PTZ position for {mode}.")
    with open(file_path, 'r') as f:
        position = json.load(f)
        # Ensure values are integers
        position["pan"] = (position["pan"])
        position["tilt"] = (position["tilt"])
        position["zoom"] = (position["zoom"])
        return position

def get_ptz_position(camera):
    """Get the current PTZ position from the camera."""
    #_, tilt = camera.get_pantilt_position()

    # Get the pan and tilt hex
    response = camera._send_command('06 12', query=True)
    pan_bytes = response[1:5].hex()
    tilt_bytes = response[5:9].hex()

    # Get the zoom hex
    response = camera._send_command('04 47', query=True)
    zoom_bytes = response[1:5].hex()
    return {"pan": pan_bytes, "tilt": tilt_bytes, "zoom": zoom_bytes}

def move_camera(camera, position, pan_speed, tilt_speed):
    """Move the camera to a specific PTZ position."""
    # Debug statements to check the position values
    
    pan_speed = int(pan_speed)
    tilt_speed = int(tilt_speed)

    # Ensure the positions are within valid ranges
    pan_position = (position["pan"])
    tilt_position = (position["tilt"])
    zoom_position = (position["zoom"])

    if not (-24 <= pan_speed <= 24):
        raise ValueError(f"Invalid pan speed: {pan_speed}. Must be between -24 and 24.")
    if not (-24 <= tilt_speed <= 24):
        raise ValueError(f"Invalid tilt speed: {tilt_speed}. Must be between -24 and 24.")

    # Debug statements to check the types and values before sending
    # print(f"Pan Speed: {pan_speed}, Tilt Speed: {tilt_speed}")
    # print(f"Pan Position: {pan_position}, Tilt Position: {tilt_position}, Zoom Position: {zoom_position}")

    # Convert to hex strings
    pan_speed_hex = f'{abs(pan_speed):02x}'
    tilt_speed_hex = f'{abs(tilt_speed):02x}'

    try:

        # Command the camera to move pan and tilt
        camera._send_command(
            '0602' + pan_speed_hex + tilt_speed_hex + pan_position + tilt_position 
        )

        # Command the camera to move zoom
        camera._send_command(
            '0447' + zoom_position
        )
    except Exception as e:
        print(f"Error while moving camera: {e}")

def encode(integer: int):
    """Converts a signed integer to hex with each nibble seperated by a 0"""
    pos_hex = integer.to_bytes(2, 'big', signed=True).hex()
    return ' '.join(['0' + char for char in pos_hex])

def decode(zero_padded: str):
    """:param zero_padded: bytes like this: 0x01020304
        :return: an integer like this 0x1234"""

    # Convert zero padded hex string to bytes
    zero_padded_bytes = bytes.fromhex(zero_padded.replace(' ', ''))

    unpadded_bytes = bytes.fromhex(zero_padded_bytes.hex()[1::2])
    return int.from_bytes(unpadded_bytes, 'big', signed=True)

def interpolate_positions(start, end, step):
    """Calculate the intermediate PTZ position between start and end and return as hex strings."""
    
    # Start and end positions are visca hex strings
    # These are in the format '0p0p0p0p' where p is a hex digit
    # Convert to integers using decode()
    start_pan_int = decode(start['pan'])
    start_tilt_int = decode(start['tilt'])
    start_zoom_int = decode(start['zoom'])

    end_pan_int = decode(end['pan'])
    end_tilt_int = decode(end['tilt'])
    end_zoom_int = decode(end['zoom'])

    # Calculate the intermediate position using a smoother interpolation (e.g., cubic interpolation)
    def linear_interpolation(start, end, t):
        return start + (end - start) * t

    intermediate_pan = int(linear_interpolation(start_pan_int, end_pan_int, step))
    intermediate_tilt = int(linear_interpolation(start_tilt_int, end_tilt_int, step))
    intermediate_zoom = int(linear_interpolation(start_zoom_int, end_zoom_int, step))

    # Convert back to hex strings
    intermediate_pos = {
        "pan": encode(intermediate_pan),
        "tilt": encode(intermediate_tilt),
        "zoom": encode(intermediate_zoom)
    }

    return intermediate_pos

def animate_camera(camera, start, end, seconds):
    """Animate the camera smoothly from start to end PTZ position."""
    steps_per_second = 10
    steps = int(seconds * steps_per_second)  # Calculate steps ensuring a max of 5 per second

    # Calculate the movement speed based on the distance between start and end positions
    distance_per_step_pan = (abs(decode(start['pan']) - decode(end['pan']))) / steps
    distance_per_step_tilt = (abs(decode(start['tilt']) - decode(end['tilt']))) / steps

    print(f"Distance per step pan: {distance_per_step_pan}, Distance per step tilt: {distance_per_step_tilt}")

    pan_speed = ((distance_per_step_pan/10) * 24 * 2) - 24
    tilt_speed = ((distance_per_step_tilt/10) * 24 * 2) - 24

    print(f"Pan Speed: {pan_speed}, Tilt Speed: {tilt_speed}")

    # Calculate the delay between each movement step based on the move speed
    delay = (seconds / steps)

    for step in range(steps + 1):
        t = step / steps
        intermediate_pos = interpolate_positions(start, end, t)

        # print(f"Animating step {step}: {intermediate_pos}")

        move_camera(camera, intermediate_pos, pan_speed, tilt_speed)

        # Delay between each step
        time.sleep(1/steps_per_second)


# Argument parsing
parser = argparse.ArgumentParser(description="Control VISCA camera PTZ positions.")
parser.add_argument('ip', type=str, help="IP address of the VISCA camera")
parser.add_argument('port', type=int, help="Port number of the VISCA camera")
parser.add_argument('speed', type=float, help="Speed of the animation")
parser.add_argument('mode', type=str, choices=['start', 'end', 'prepare', 'run'], help="Mode of operation")
args = parser.parse_args()

ip = args.ip
port = args.port
speed = args.speed
mode = args.mode

# Initialize camera connection with IP and custom port
camera = Camera(ip, port=port)

if mode == 'start':
    # Save the current position as the start position
    position = get_ptz_position(camera)
    save_position(ip, 'start', position)
    print(f"Start position saved for camera {ip}: {position}")

elif mode == 'end':
    # Save the current position as the end position
    position = get_ptz_position(camera)
    save_position(ip, 'end', position)
    print(f"End position saved for camera {ip}: {position}")

elif mode == 'prepare':
    # Move the camera to the start position
    start_position = load_position(ip, 'start')
    move_camera(camera, start_position, 24, 24)
    print(f"Camera {ip} moved to the start position.")

elif mode == 'run':
    # Animate the camera from the start position to the end position
    start_position = load_position(ip, 'start')
    end_position = load_position(ip, 'end')

    # Animate the camera from start to end
    animate_camera(camera, start_position, end_position, speed)
    print(f"Animating camera {ip} from start to end position at speed {speed}.")

