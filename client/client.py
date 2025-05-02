import sys
import os
import threading
import time
import base64
import io
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QMessageBox, QStatusBar, QSplitter)
from PyQt5.QtGui import QPixmap, QImage, QKeyEvent, QMouseEvent
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPoint

# Add the parent directory to the path so we can import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.network import NetworkManager, MSG_FRAME, MSG_MOUSE_MOVE, MSG_MOUSE_CLICK, MSG_KEY_PRESS, MSG_KEY_RELEASE


class FrameReceiver(QThread):
    """Thread to receive screen frames from the host"""
    frame_received = pyqtSignal(QPixmap)
    error_occurred = pyqtSignal(str)

    def __init__(self, network):
        super().__init__()
        self.network = network
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            try:
                data = self.network.receive_data()
                if not data or data.get('type') != MSG_FRAME:
                    continue

                # Extract frame data
                width = data.get('width', 0)
                height = data.get('height', 0)
                img_encoded = data.get('data', '')

                # Decode base64 to bytes
                img_bytes = base64.b64decode(img_encoded)

                # Create QImage from bytes
                q_img = QImage.fromData(img_bytes)

                if q_img.isNull():
                    self.error_occurred.emit("Received invalid image data")
                    continue

                # Convert to QPixmap and emit signal
                pixmap = QPixmap.fromImage(q_img)
                self.frame_received.emit(pixmap)

            except Exception as e:
                self.error_occurred.emit(f"Error receiving frame: {e}")
                time.sleep(1)  # Prevent tight loop on error

    def stop(self):
        self.running = False
        self.wait()


class RemoteView(QWidget):
    """Widget to display the remote screen and handle input events"""

    def __init__(self, network):
        super().__init__()
        self.network = network
        self.remote_pixmap = None
        self.remote_width = 0
        self.remote_height = 0
        self.setFocusPolicy(Qt.StrongFocus)  # Enable keyboard focus
        self.setMouseTracking(True)  # Track mouse movements

    def update_frame(self, pixmap):
        """Update the displayed frame"""
        self.remote_pixmap = pixmap
        self.remote_width = pixmap.width()
        self.remote_height = pixmap.height()
        self.setMinimumSize(self.remote_width, self.remote_height)
        self.update()

    def paintEvent(self, event):
        """Paint the remote screen frame"""
        if self.remote_pixmap:
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self.remote_pixmap)

    def mouseMoveEvent(self, event):
        """Handle mouse movement and send to host"""
        if not self.remote_width or not self.remote_height:
            return

        # Convert local coordinates to ratio (0-1) of remote screen
        x_ratio = event.x() / self.remote_width
        y_ratio = event.y() / self.remote_height

        # Send mouse position to host
        self.network.send_data({
            'type': MSG_MOUSE_MOVE,
            'x': x_ratio,
            'y': y_ratio
        })

    def mousePressEvent(self, event):
        """Handle mouse clicks and send to host"""
        if not self.remote_width or not self.remote_height:
            return

        # Convert local coordinates to ratio (0-1) of remote screen
        x_ratio = event.x() / self.remote_width
        y_ratio = event.y() / self.remote_height

        # Determine which button was pressed
        button = 'left'
        if event.button() == Qt.RightButton:
            button = 'right'
        elif event.button() == Qt.MiddleButton:
            button = 'middle'

        # Send mouse click to host
        self.network.send_data({
            'type': MSG_MOUSE_CLICK,
            'x': x_ratio,
            'y': y_ratio,
            'button': button,
            'clicks': 1
        })

    def keyPressEvent(self, event):
        """Handle key press and send to host"""
        key = self._qt_key_to_pyautogui(event)
        if key:
            self.network.send_data({
                'type': MSG_KEY_PRESS,
                'key': key
            })

    def keyReleaseEvent(self, event):
        """Handle key release and send to host"""
        key = self._qt_key_to_pyautogui(event)
        if key:
            self.network.send_data({
                'type': MSG_KEY_RELEASE,
                'key': key
            })

    def _qt_key_to_pyautogui(self, event):
        """Convert Qt key event to pyautogui key name"""
        # This is a simplified mapping and can be expanded
        key_map = {
            Qt.Key_Return: 'enter',
            Qt.Key_Escape: 'esc',
            Qt.Key_Tab: 'tab',
            Qt.Key_Backspace: 'backspace',
            Qt.Key_Delete: 'delete',
            Qt.Key_Shift: 'shift',
            Qt.Key_Control: 'ctrl',
            Qt.Key_Alt: 'alt',
            Qt.Key_CapsLock: 'capslock',
            Qt.Key_Space: 'space',
            Qt.Key_Left: 'left',
            Qt.Key_Right: 'right',
            Qt.Key_Up: 'up',
            Qt.Key_Down: 'down',
            Qt.Key_Home: 'home',
            Qt.Key_End: 'end',
            Qt.Key_PageUp: 'pageup',
            Qt.Key_PageDown: 'pagedown',
            Qt.Key_F1: 'f1',
            Qt.Key_F2: 'f2',
            Qt.Key_F3: 'f3',
            Qt.Key_F4: 'f4',
            Qt.Key_F5: 'f5',
            Qt.Key_F6: 'f6',
            Qt.Key_F7: 'f7',
            Qt.Key_F8: 'f8',
            Qt.Key_F9: 'f9',
            Qt.Key_F10: 'f10',
            Qt.Key_F11: 'f11',
            Qt.Key_F12: 'f12',
        }

        # Get key from mapping
        key = key_map.get(event.key())

        # Handle regular text keys
        if not key and event.key() >= 32 and event.key() <= 126:  # ASCII printable chars
            key = chr(event.key()).lower()

        return key


# Needed for Qt paint events
from PyQt5.QtGui import QPainter


class RemoteClient(QMainWindow):
    """Main client application window"""

    def __init__(self):
        super().__init__()
        self.network = NetworkManager(is_server=False)
        self.frame_receiver = None
        self.connected = False
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Remote Control Client")
        self.setGeometry(100, 100, 1024, 768)

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Connection controls
        conn_layout = QHBoxLayout()

        self.host_input = QLineEdit("localhost")
        self.host_input.setPlaceholderText("Host IP or hostname")
        conn_layout.addWidget(QLabel("Host:"))
        conn_layout.addWidget(self.host_input)

        self.port_input = QLineEdit("9999")
        self.port_input.setPlaceholderText("Port")
        conn_layout.addWidget(QLabel("Port:"))
        conn_layout.addWidget(self.port_input)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_to_host)
        conn_layout.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_from_host)
        self.disconnect_btn.setEnabled(False)
        conn_layout.addWidget(self.disconnect_btn)

        main_layout.addLayout(conn_layout)

        # Remote view
        self.remote_view = RemoteView(self.network)
        main_layout.addWidget(self.remote_view)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Disconnected")

    def connect_to_host(self):
        """Connect to the remote host"""
        host = self.host_input.text()

        try:
            port = int(self.port_input.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Port", "Please enter a valid port number")
            return

        self.status_bar.showMessage(f"Connecting to {host}:{port}...")

        # Connect in a separate thread to keep UI responsive
        def connect_thread():
            if self.network.connect(host, port):
                if self.network.authenticate():
                    self.connected = True

                    # Start receiving frames in a background thread
                    self.frame_receiver = FrameReceiver(self.network)
                    self.frame_receiver.frame_received.connect(self.remote_view.update_frame)
                    self.frame_receiver.error_occurred.connect(self.handle_error)
                    self.frame_receiver.start()

                    # Update UI
                    self.connect_btn.setEnabled(False)
                    self.disconnect_btn.setEnabled(True)
                    self.host_input.setEnabled(False)
                    self.port_input.setEnabled(False)
                    self.status_bar.showMessage(f"Connected to {host}:{port}")
                else:
                    self.network.close()
                    self.status_bar.showMessage("Authentication failed")
                    QMessageBox.warning(self, "Authentication Failed", "Failed to authenticate with the host")
            else:
                self.status_bar.showMessage("Connection failed")
                QMessageBox.warning(self, "Connection Failed", f"Failed to connect to {host}:{port}")

        threading.Thread(target=connect_thread).start()

    def disconnect_from_host(self):
        """Disconnect from the remote host"""
        if self.frame_receiver:
            self.frame_receiver.stop()
            self.frame_receiver = None

        self.network.close()
        self.connected = False

        # Update UI
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.host_input.setEnabled(True)
        self.port_input.setEnabled(True)
        self.status_bar.showMessage("Disconnected")

    def handle_error(self, error_msg):
        """Handle errors from the frame receiver"""
        self.status_bar.showMessage(f"Error: {error_msg}")

        # If the connection is broken, disconnect
        if "connection" in error_msg.lower():
            self.disconnect_from_host()

    def closeEvent(self, event):
        """Handle window close event"""
        if self.connected:
            self.disconnect_from_host()
        event.accept()


def main():
    """Main function to run the client application"""
    app = QApplication(sys.argv)
    client = RemoteClient()
    client.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()