import asyncio
import json
import base64
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
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

async def handle_options(request):
    """Handle preflight CORS requests"""
    return web.Response(headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    })

async def offer(request):
    print("Received WebRTC offer")
    params = await request.json()
    pc = RTCPeerConnection()
    pcs.add(pc)

    video_track = VideoStream()
    pc.addTrack(video_track)

    await pc.setRemoteDescription(RTCSessionDescription(sdp=params["sdp"], type=params["type"]))
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    response_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Credentials": "true"
    }

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }, headers=response_headers)

async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        return web.Response(headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Allow-Credentials": "true",
        })
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

app = web.Application(middlewares=[cors_middleware])
app.router.add_route("POST", "/vws", offer)
app.router.add_route("OPTIONS", "/vws", handle_options)
# WebSocket control server
async def handle_control_websocket(websocket, path):
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

    if command_type == cmd.CMD_MOTOR:
        try:
            left_speed = int(data[1])
            right_speed = int(data[2])
            PWM.setMotorModel(left_speed, right_speed)
            print(f"Motor speeds set to left: {left_speed}, right: {right_speed}")
        except (ValueError, IndexError):
            print("Invalid motor command")

    elif command_type == cmd.CMD_SERVO:
        try:
            servo_id = data[1]
            angle = int(data[2])
            servo.setServoPwm(servo_id, angle)
            print(f"Servo {servo_id} set to angle {angle}")
        except (ValueError, IndexError):
            print("Invalid servo command")

    elif command_type == cmd.CMD_LED:
        try:
            led_mode = int(data[1])
            red = int(data[2])
            green = int(data[3])
            blue = int(data[4])
            brightness = int(data[5])
            led.ledMode(data)
            print(f"LED mode set to {led_mode}, RGB: ({red}, {green}, {blue}), Brightness: {brightness}")
        except (ValueError, IndexError):
            print("Invalid LED command")

async def start_control_server():
    try:
        print("Starting WebSocket control server...")
        server = await websockets.serve(handle_control_websocket, '0.0.0.0', 8765)
        print("Control WebSocket server started on ws://0.0.0.0:8765")
        await server.wait_closed()
    except Exception as e:
        print(f"Failed to start WebSocket server: {e}")

async def start_webrtc_server():
    print("Starting WebRTC server...")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=8766)
    await site.start()
    print("WebRTC server started on http://0.0.0.0:8766")

async def main():
    control_server_task = asyncio.create_task(start_control_server())
    webrtc_server_task = asyncio.create_task(start_webrtc_server())
    
    await asyncio.gather(control_server_task, webrtc_server_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped manually")
