import sys
import os
import time
import threading
import io

import mss
from PIL import Image, ImageDraw
import lz4.frame

from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key

# Add parent dir for common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.network import NetworkManager, MSG_FRAME, MSG_MOUSE_MOVE, MSG_MOUSE_CLICK, MSG_KEY_PRESS, MSG_KEY_RELEASE

# Map string keys to pynput Key constants
KEY_MAP = {
    'enter': Key.enter, 'esc': Key.esc, 'tab': Key.tab,
    'backspace': Key.backspace, 'delete': Key.delete,
    'shift': Key.shift, 'ctrl': Key.ctrl, 'alt': Key.alt,
    'space': Key.space, 'left': Key.left, 'right': Key.right,
    'up': Key.up, 'down': Key.down, 'home': Key.home,
    'end': Key.end, 'pageup': Key.page_up, 'pagedown': Key.page_down,
    'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3, 'f4': Key.f4,
    'f5': Key.f5, 'f6': Key.f6, 'f7': Key.f7, 'f8': Key.f8,
    'f9': Key.f9, 'f10': Key.f10, 'f11': Key.f11, 'f12': Key.f12
}

class RemoteHost:
    def __init__(self, host='0.0.0.0', port=9999, quality=70, frame_rate=15):
        self.host = host
        self.port = port
        self.quality = quality
        self.frame_rate = frame_rate
        self.frame_interval = 1.0 / frame_rate
        self.running = False

        # Network and capture
        self.network = NetworkManager(is_server=True)
        self.sct = mss.mss()
        self.screen_width, self.screen_height = self.sct.monitors[1]['width'], self.sct.monitors[1]['height']

        # Input controllers
        self.mouse = MouseController()
        self.keyboard = KeyboardController()

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
        print(f"Remote host running on {self.host}:{self.port}")
        return True

    def screen_sharing_loop(self):
        last_time = 0
        monitor = {"top": 0, "left": 0, "width": self.screen_width, "height": self.screen_height}

        while self.running:
            now = time.time()
            if now - last_time < self.frame_interval:
                time.sleep(0.001)
                continue

            shot = self.sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.rgb)

            # Draw 5px green border
            draw = ImageDraw.Draw(img)
            for i in range(5):
                draw.rectangle(
                    [i, i, img.width - 1 - i, img.height - 1 - i],
                    outline="lime"
                )

            # JPEG encode
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=self.quality)
            jpeg_bytes = buf.getvalue()

            # LZ4 compress
            compressed = lz4.frame.compress(jpeg_bytes)

            # Send frame
            frame_data = {
                'type': MSG_FRAME,
                'width': img.width,
                'height': img.height,
                'data': compressed
            }
            if not self.network.send_data(frame_data):
                print("Send error; stopping.")
                self.running = False
                break

            last_time = now

    def handle_client_input(self):
        while self.running:
            data = self.network.receive_data()
            if not data:
                continue

            t = data.get('type')
            # Mouse move
            if t == MSG_MOUSE_MOVE:
                x = int(data['x'] * self.screen_width)
                y = int(data['y'] * self.screen_height)
                self.mouse.position = (x, y)

            # Mouse click
            elif t == MSG_MOUSE_CLICK:
                x = int(data['x'] * self.screen_width)
                y = int(data['y'] * self.screen_height)
                btn = Button.left if data.get('button') == 'left' else Button.right
                clicks = data.get('clicks', 1)
                # move first in case
                self.mouse.position = (x, y)
                for _ in range(clicks):
                    self.mouse.click(btn)

            # Key press
            elif t == MSG_KEY_PRESS:
                key_str = data.get('key')
                key = KEY_MAP.get(key_str, key_str)
                self.keyboard.press(key)

            # Key release
            elif t == MSG_KEY_RELEASE:
                key_str = data.get('key')
                key = KEY_MAP.get(key_str, key_str)
                self.keyboard.release(key)

    def stop(self):
        self.running = False
        self.network.close()
        print("Remote host stopped")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Remote Host')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=9999)
    parser.add_argument('--quality', type=int, default=70)
    parser.add_argument('--fps', type=int, default=15)
    args = parser.parse_args()

    host = RemoteHost(
        host=args.host,
        port=args.port,
        quality=args.quality,
        frame_rate=args.fps
    )

    try:
        if host.start():
            print("Press Ctrl+C to stop")
            while host.running:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down…")
    finally:
        host.stop()


if __name__ == "__main__":
    main()
