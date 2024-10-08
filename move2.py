import argparse
import socket
import json
import time
import os

# Constants
VISCA_PORT = 52381  # Default VISCA-over-IP port
PTZ_FILES_DIR = "ptz_positions"  # Directory to store PTZ positions

# Ensure directory for PTZ files exists
os.makedirs(PTZ_FILES_DIR, exist_ok=True)

# VISCA Command to get PTZ position
INQUIRY_CMD = bytes([0x81, 0x09, 0x06, 0x12, 0xFF])

def send_visca_command(ip, command):
    """Send VISCA command to camera and get the response."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(5)  # Timeout after 1 second
        sock.sendto(command, (ip, VISCA_PORT))
        response, _ = sock.recvfrom(16)  # 16 bytes for PTZ response
        return response

def get_ptz_position(ip):
    """Get the current PTZ position from the camera."""
    response = send_visca_command(ip, INQUIRY_CMD)
    # Parse PTZ values from response
    pan = int.from_bytes(response[2:4], byteorder='big')
    tilt = int.from_bytes(response[4:6], byteorder='big')
    zoom = int.from_bytes(response[6:8], byteorder='big')
    return {"pan": pan, "tilt": tilt, "zoom": zoom}

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
        return json.load(f)

def move_camera(ip, position, speed):
    """Send VISCA commands to move the camera to a specific PTZ position."""
    pan = position['pan']
    tilt = position['tilt']
    zoom = position['zoom']
    
    # VISCA command to move to absolute PTZ position
    command = bytes([
        0x81, 0x01, 0x06, 0x02,
        (pan >> 12) & 0x0F, (pan >> 8) & 0x0F, (pan >> 4) & 0x0F, pan & 0x0F,
        (tilt >> 12) & 0x0F, (tilt >> 8) & 0x0F, (tilt >> 4) & 0x0F, tilt & 0x0F,
        (zoom >> 12) & 0x0F, (zoom >> 8) & 0x0F, (zoom >> 4) & 0x0F, zoom & 0x0F,
        0xFF
    ])
    
    # Send the command to the camera
    send_visca_command(ip, command)

def interpolate_positions(start, end, step):
    """Calculate the intermediate PTZ position between start and end."""
    return {
        "pan": start["pan"] + (end["pan"] - start["pan"]) * step,
        "tilt": start["tilt"] + (end["tilt"] - start["tilt"]) * step,
        "zoom": start["zoom"] + (end["zoom"] - start["zoom"]) * step
    }

def animate_camera(ip, start, end, speed):
    """Animate the camera smoothly from start to end PTZ position."""
    steps = 100  # Number of interpolation steps for smooth animation
    delay = 1 / speed  # Delay between each movement step
    
    for step in range(steps + 1):
        t = step / steps
        intermediate_pos = interpolate_positions(start, end, t)
        move_camera(ip, intermediate_pos, speed)
        time.sleep(delay)

# Argument parsing
parser = argparse.ArgumentParser(description="Control VISCA camera PTZ positions.")
parser.add_argument('ip', type=str, help="IP address of the VISCA camera")
parser.add_argument('speed', type=float, help="Speed of the animation")
parser.add_argument('mode', type=str, choices=['start', 'end', 'prepare', 'run'], help="Mode of operation")
args = parser.parse_args()

ip = args.ip
speed = args.speed
mode = args.mode

if mode == 'start':
    # Save the current position as the start position
    position = get_ptz_position(ip)
    save_position(ip, 'start', position)
    print(f"Start position saved for camera {ip}: {position}")

elif mode == 'end':
    # Save the current position as the end position
    position = get_ptz_position(ip)
    save_position(ip, 'end', position)
    print(f"End position saved for camera {ip}: {position}")

elif mode == 'prepare':
    # Move the camera to the start position
    start_position = load_position(ip, 'start')
    move_camera(ip, start_position, speed)
    print(f"Camera {ip} moved to the start position.")

elif mode == 'run':
    # Animate the camera from the start position to the end position
    start_position = load_position(ip, 'start')
    end_position = load_position(ip, 'end')
    animate_camera(ip, start_position, end_position, speed)
    print(f"Animating camera {ip} from start to end position at speed {speed}.")
