import asyncio
import json
import base64
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaBlackhole
from picamera2 import Picamera2, Preview
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from picamera2.encoders import Quality
from libcamera import Transform
import websockets
from Motor import Motor
from servo import Servo
from Led import Led
from Command import COMMAND as cmd

pcs = set()

# Initialize hardware components
PWM = Motor()
servo = Servo()
led = Led()

class VideoStream(VideoStreamTrack):
    """A video stream track that captures frames from the PiCamera."""
    def __init__(self):
        super().__init__()
        self.camera = Picamera2()
        self.camera.configure(self.camera.create_video_configuration(
            main={"size": (320, 240)},
            transform=Transform(hflip=1, vflip=1)
        ))
        self.encoder = JpegEncoder(q=80)
        self.output = FileOutput()
        self.camera.start_recording(self.encoder, self.output, quality=Quality.VERY_HIGH)

    async def recv(self):
        frame = self.output.get_frame()
        if frame is None:
            return None
        return frame

async def index(request):
    content = open('index.html').read()
    return web.Response(content_type='text/html', text=content)

async def offer(request):
    params = await request.json()
    pc = RTCPeerConnection()
    pcs.add(pc)

    video_track = VideoStream()
    pc.addTrack(video_track)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print("ICE state:", pc.iceConnectionState)
        if pc.iceConnectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    await pc.setRemoteDescription(RTCSessionDescription(sdp=params["sdp"], type=params["type"]))
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})

async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

app = web.Application()
app.router.add_get("/", index)
app.router.add_post("/offer", offer)
app.on_shutdown.append(on_shutdown)

async def handle_control_websocket(websocket):
    """Handle WebSocket control commands"""
    print(f"Control client connected: {websocket.remote_address}")
    try:
        async for message in websocket:
            data = json.loads(message)
            if 'command' in data:
                cmd_str = data['command']
                handle_command(cmd_str)
    except websockets.exceptions.ConnectionClosed:
        print("Control client disconnected")

def handle_command(cmd_str):
    """Handle control commands"""
    data = cmd_str.split("#")
    command_type = data[0]

    # Handle motor control commands
    if command_type == cmd.CMD_MOTOR:
        try:
            left_speed = int(data[1])
            right_speed = int(data[2])
            print(f"Setting motor speed: left={left_speed}, right={right_speed}")
            PWM.setMotorModel(left_speed, right_speed)
        except (ValueError, IndexError):
            print("Invalid motor command data:", data)

    # Handle servo control commands
    elif command_type == cmd.CMD_SERVO:
        try:
            servo_id = data[1]
            angle = int(data[2])
            print(f"Setting servo {servo_id} to angle {angle}")
            servo.setServoPwm(servo_id, angle)
        except (ValueError, IndexError):
            print("Invalid servo command data:", data)

    # Handle LED control commands
    elif command_type == cmd.CMD_LED:
        try:
            led_mode = int(data[1])
            red = int(data[2])
            green = int(data[3])
            blue = int(data[4])
            brightness = int(data[5])
            print(f"Setting LED mode: {led_mode}, Color: ({red}, {green}, {blue}), Brightness: {brightness}")
            led.ledMode(led_mode, red, green, blue, brightness)
        except (ValueError, IndexError):
            print("Invalid LED command data:", data)

    # Handle other commands (e.g., ultrasonic sensor)
    elif command_type == cmd.CMD_SONIC:
        print("Ultrasonic command received")

    # Handle custom actions
    elif command_type == cmd.CMD_ACTION:
        action_type = data[1]
        print(f"Performing action: {action_type}")

    else:
        print("Unrecognized command:", command_type)

async def start_control_server():
    control_server = await websockets.serve(handle_control_websocket, '0.0.0.0', 8765)
    print("Control WebSocket server started on ws://0.0.0.0:8765")
    await control_server.wait_closed()

async def start_webrtc_server():
    web.run_app(app, port=8080)

async def main():
    await asyncio.gather(
        start_webrtc_server(),
        start_control_server()
    )

if __name__ == "__main__":
    asyncio.run(main())
