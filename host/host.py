'''import sys
import os
import time
import threading
import base64
import io
from PIL import Image
import mss
import pyautogui

# Add the parent directory to the path so we can import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.network import NetworkManager, MSG_FRAME, MSG_MOUSE_MOVE, MSG_MOUSE_CLICK, MSG_KEY_PRESS, MSG_KEY_RELEASE


class RemoteHost:
    """Remote access host application that shares screen and accepts input"""

    def __init__(self, host='192.168.1.3', port=9999, quality=70, frame_rate=15):
        """Initialize the remote host with specified settings"""
        self.host = host
        self.port = port
        self.quality = quality  # JPEG compression quality (0-100)
        self.frame_rate = frame_rate
        self.frame_interval = 1.0 / frame_rate
        self.running = False
        self.network = NetworkManager(is_server=True)
        self.screen_capture = mss.mss()
        self.screen_width, self.screen_height = pyautogui.size()

    def start(self):
        """Start the remote host server"""
        print("Starting remote host...")
        if not self.network.start_server(self.host, self.port):
            print("Failed to start server")
            return False

        print("Waiting for authentication...")
        if not self.network.authenticate():
            print("Authentication failed")
            self.network.close()
            return False

        print("Authentication successful")

        self.running = True

        # Start screen sharing and input handling in separate threads
        screen_thread = threading.Thread(target=self.screen_sharing_loop)
        screen_thread.daemon = True
        screen_thread.start()

        input_thread = threading.Thread(target=self.handle_client_input)
        input_thread.daemon = True
        input_thread.start()

        print(f"Remote host started on {self.host}:{self.port}")
        return True

    def screen_sharing_loop(self):
        """Continuously capture and send screen frames"""
        last_frame_time = 0

        monitor = {"top": 0, "left": 0, "width": self.screen_width, "height": self.screen_height}

        while self.running:
            current_time = time.time()

            # Limit frame rate
            if current_time - last_frame_time < self.frame_interval:
                time.sleep(0.001)  # Small sleep to prevent CPU hogging
                continue

            # Capture screen
            screenshot = self.screen_capture.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

            # Resize if needed (can be used to reduce bandwidth)
            # img = img.resize((int(self.screen_width * 0.75), int(self.screen_height * 0.75)))

            # Convert to bytes using JPEG compression
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=self.quality)
            img_bytes = buffer.getvalue()

            # Encode as base64 for safer transmission
            img_encoded = base64.b64encode(img_bytes).decode('utf-8')

            # Send the frame
            frame_data = {
                'type': MSG_FRAME,
                'width': img.width,
                'height': img.height,
                'data': img_encoded
            }

            if not self.network.send_data(frame_data):
                print("Error sending frame, connection might be closed")
                self.running = False
                break

            last_frame_time = current_time

    def handle_client_input(self):
        """Handle input commands from the client"""
        while self.running:
            try:
                data = self.network.receive_data()
                if not data:
                    continue

                msg_type = data.get('type')

                if msg_type == MSG_MOUSE_MOVE:
                    x_ratio = data.get('x', 0)
                    y_ratio = data.get('y', 0)
                    # Convert ratio to absolute screen position
                    x = int(x_ratio * self.screen_width)
                    y = int(y_ratio * self.screen_height)
                    pyautogui.moveTo(x, y)

                elif msg_type == MSG_MOUSE_CLICK:
                    button = data.get('button', 'left')
                    clicks = data.get('clicks', 1)
                    x_ratio = data.get('x', 0)
                    y_ratio = data.get('y', 0)
                    # Convert ratio to absolute screen position
                    x = int(x_ratio * self.screen_width)
                    y = int(y_ratio * self.screen_height)
                    pyautogui.click(x, y, clicks=clicks, button=button)

                elif msg_type == MSG_KEY_PRESS:
                    key = data.get('key')
                    if key:
                        pyautogui.keyDown(key)

                elif msg_type == MSG_KEY_RELEASE:
                    key = data.get('key')
                    if key:
                        pyautogui.keyUp(key)

            except Exception as e:
                print(f"Error handling client input: {e}")
                # Don't break the loop for input errors, just log them

    def stop(self):
        """Stop the remote host server"""
        self.running = False
        self.network.close()
        print("Remote host stopped")


def main():
    """Main function to run the host application"""
    import argparse

    parser = argparse.ArgumentParser(description='Remote Access Host')
    parser.add_argument('--host', default='0.0.0.0', help='Host address to bind')
    parser.add_argument('--port', type=int, default=9999, help='Port to listen on')
    parser.add_argument('--quality', type=int, default=70, help='JPEG compression quality (0-100)')
    parser.add_argument('--fps', type=int, default=15, help='Target frames per second')

    args = parser.parse_args()

    host = RemoteHost(
        host=args.host,
        port=args.port,
        quality=args.quality,
        frame_rate=args.fps
    )

    try:
        if host.start():
            print("Press Ctrl+C to stop the server")
            while host.running:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        host.stop()


if __name__ == "__main__":
    main()'''

import sys
import os
import time
import threading
import base64
import io
from PIL import Image, ImageDraw
import mss
import pyautogui

# Add the parent directory to the path so we can import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.network import NetworkManager, MSG_FRAME, MSG_MOUSE_MOVE, MSG_MOUSE_CLICK, MSG_KEY_PRESS, MSG_KEY_RELEASE


class RemoteHost:
    def __init__(self, host='0.0.0.0', port=9999, quality=70, frame_rate=15):
        self.host = host
        self.port = port
        self.quality = quality
        self.frame_rate = frame_rate
        self.frame_interval = 1.0 / frame_rate
        self.running = False
        self.network = NetworkManager(is_server=True)
        self.screen_capture = mss.mss()
        self.screen_width, self.screen_height = pyautogui.size()

    def start(self):
        print("Starting remote host...")
        if not self.network.start_server(self.host, self.port):
            print("Failed to start server")
            return False

        print("Waiting for authentication...")
        if not self.network.authenticate():
            print("Authentication failed")
            self.network.close()
            return False

        print("Authentication successful")
        self.running = True

        threading.Thread(target=self.screen_sharing_loop, daemon=True).start()
        threading.Thread(target=self.handle_client_input, daemon=True).start()

        print(f"Remote host started on {self.host}:{self.port}")
        return True

    def screen_sharing_loop(self):
        last_frame_time = 0
        monitor = {"top": 0, "left": 0, "width": self.screen_width, "height": self.screen_height}

        while self.running:
            current_time = time.time()
            if current_time - last_frame_time < self.frame_interval:
                time.sleep(0.001)
                continue

            screenshot = self.screen_capture.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

            # ✅ Draw green border
            draw = ImageDraw.Draw(img)
            border_thickness = 5
            for i in range(border_thickness):
                draw.rectangle(
                    [i, i, img.width - 1 - i, img.height - 1 - i],
                    outline="lime"
                )

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=self.quality)
            img_bytes = buffer.getvalue()
            img_encoded = base64.b64encode(img_bytes).decode('utf-8')

            frame_data = {
                'type': MSG_FRAME,
                'width': img.width,
                'height': img.height,
                'data': img_encoded
            }

            if not self.network.send_data(frame_data):
                print("Error sending frame, connection might be closed")
                self.running = False
                break

            last_frame_time = current_time

    def handle_client_input(self):
        while self.running:
            try:
                data = self.network.receive_data()
                if not data:
                    continue

                msg_type = data.get('type')

                if msg_type == MSG_MOUSE_MOVE:
                    x = int(data.get('x', 0) * self.screen_width)
                    y = int(data.get('y', 0) * self.screen_height)
                    pyautogui.moveTo(x, y)

                elif msg_type == MSG_MOUSE_CLICK:
                    x = int(data.get('x', 0) * self.screen_width)
                    y = int(data.get('y', 0) * self.screen_height)
                    button = data.get('button', 'left')
                    clicks = data.get('clicks', 1)
                    pyautogui.click(x, y, clicks=clicks, button=button)

                elif msg_type == MSG_KEY_PRESS:
                    key = data.get('key')
                    if key:
                        pyautogui.keyDown(key)

                elif msg_type == MSG_KEY_RELEASE:
                    key = data.get('key')
                    if key:
                        pyautogui.keyUp(key)

            except Exception as e:
                print(f"Error handling client input: {e}")

    def stop(self):
        self.running = False
        self.network.close()
        print("Remote host stopped")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Remote Access Host')
    parser.add_argument('--host', default='0.0.0.0', help='Host address to bind')
    parser.add_argument('--port', type=int, default=9999, help='Port to listen on')
    parser.add_argument('--quality', type=int, default=70, help='JPEG compression quality (0-100)')
    parser.add_argument('--fps', type=int, default=15, help='Target frames per second')

    args = parser.parse_args()

    host = RemoteHost(
        host=args.host,
        port=args.port,
        quality=args.quality,
        frame_rate=args.fps
    )

    try:
        if host.start():
            print("Press Ctrl+C to stop the server")
            while host.running:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        host.stop()


if __name__ == "__main__":
    main()
