'''import sys
import os
import threading
import time
import base64
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QMessageBox, QFrame
)
from PyQt5.QtGui import QPixmap, QImage, QPainter
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect

# Add the parent directory to the path so we can import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.network import NetworkManager, MSG_FRAME, MSG_MOUSE_MOVE, MSG_MOUSE_CLICK, MSG_KEY_PRESS, MSG_KEY_RELEASE

LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")


class FrameReceiver(QThread):
    frame_received = pyqtSignal(QImage)
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

                img_bytes = base64.b64decode(data.get('data', ''))
                q_img = QImage.fromData(img_bytes)
                if q_img.isNull():
                    self.error_occurred.emit("Received invalid image data")
                    continue

                self.frame_received.emit(q_img)
            except Exception as e:
                self.error_occurred.emit(f"Error receiving frame: {e}")
                time.sleep(1)

    def stop(self):
        self.running = False
        self.wait()


class ConnectionWindow(QWidget):
    connected = pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Connect to Remote Host")
        self.setFixedSize(500, 300)
        layout = QVBoxLayout(self)

        logo = QLabel()
        pixmap = QPixmap(LOGO_PATH)
        logo.setPixmap(pixmap.scaled(450, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        self.host_input = QLineEdit("localhost")
        self.host_input.setPlaceholderText("Host IP or hostname")
        layout.addWidget(self.host_input)

        self.port_input = QLineEdit("9999")
        self.port_input.setPlaceholderText("Port")
        layout.addWidget(self.port_input)

        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self.try_connect)
        layout.addWidget(connect_btn)
        layout.setAlignment(connect_btn, Qt.AlignCenter)

    def try_connect(self):
        try:
            port = int(self.port_input.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Port", "Enter a valid port number.")
            return
        self.connected.emit(self.host_input.text(), port)


class RemoteView(QFrame):
    def __init__(self, network):
        super().__init__()
        self.network = network
        self.setFrameStyle(QFrame.Box)
        self.setLineWidth(2)
        self.setStyleSheet("QFrame { border: 2px solid green; }")
        self.remote_pixmap = None
        self.remote_width = 0
        self.remote_height = 0
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    def update_frame(self, q_img):
        pixmap = QPixmap.fromImage(q_img)
        self.remote_pixmap = pixmap
        self.remote_width = pixmap.width()
        self.remote_height = pixmap.height()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.remote_pixmap:
            painter = QPainter(self)
            target_rect = self.rect()
            painter.drawPixmap(target_rect, self.remote_pixmap)

    def mouseMoveEvent(self, event):
        if not self.remote_width or not self.remote_height:
            return
        x_ratio = event.x() / self.width()
        y_ratio = event.y() / self.height()
        self.network.send_data({'type': MSG_MOUSE_MOVE, 'x': x_ratio, 'y': y_ratio})

    def mousePressEvent(self, event):
        if not self.remote_width or not self.remote_height:
            return
        x_ratio = event.x() / self.width()
        y_ratio = event.y() / self.height()
        button = 'left' if event.button() == Qt.LeftButton else 'right'
        self.network.send_data({
            'type': MSG_MOUSE_CLICK,
            'x': x_ratio,
            'y': y_ratio,
            'button': button,
            'clicks': 1
        })

    def keyPressEvent(self, event):
        key = event.text().lower() or None
        if key:
            self.network.send_data({'type': MSG_KEY_PRESS, 'key': key})

    def keyReleaseEvent(self, event):
        key = event.text().lower() or None
        if key:
            self.network.send_data({'type': MSG_KEY_RELEASE, 'key': key})


class ScreenWindow(QMainWindow):
    def __init__(self, network):
        super().__init__()
        self.network = network
        self.setWindowTitle("Remote Control Session")

        # Uncomment to remove OS title bar (optional)
        # self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)

        self.init_ui()

    def init_ui(self):
        central = QWidget()
        vlay = QVBoxLayout(central)
        vlay.setContentsMargins(0, 0, 0, 0)

        bar = QWidget()
        bar.setFixedHeight(50)
        bar.setStyleSheet("background-color:#f0f0f0;")
        hlay = QHBoxLayout(bar)
        hlay.setContentsMargins(10, 0, 10, 0)

        logo = QLabel()
        pixmap = QPixmap(LOGO_PATH)
        logo.setPixmap(pixmap.scaledToHeight(40, Qt.SmoothTransformation))
        hlay.addWidget(logo)
        hlay.addStretch()

        disc_btn = QPushButton("Disconnect")
        disc_btn.setStyleSheet("background-color:red;color:white;padding:5px;")
        disc_btn.clicked.connect(self.confirm_disconnect)
        hlay.addWidget(disc_btn)

        vlay.addWidget(bar)

        self.remote_view = RemoteView(self.network)
        vlay.addWidget(self.remote_view)

        self.setCentralWidget(central)

    def confirm_disconnect(self):
        reply = QMessageBox.question(self, "Disconnect",
            "Are you sure you want to disconnect?", QMessageBox.Yes | QMessageBox.Cancel)
        if reply == QMessageBox.Yes:
            QApplication.quit()


class RemoteClientApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.network = NetworkManager(is_server=False)
        self.conn_win = ConnectionWindow()
        self.conn_win.connected.connect(self.start_session)
        self.conn_win.show()

    def start_session(self, host, port):
        self.conn_win.close()
        if not self.network.connect(host, port) or not self.network.authenticate():
            QMessageBox.warning(None, "Connection Failed", f"Could not connect to {host}:{port}")
            self.app.quit()
            return

        self.screen_win = ScreenWindow(self.network)

        # Fill available screen (prevents cropping by OS UI elements)
        screen_rect = QApplication.primaryScreen().availableGeometry()
        self.screen_win.setGeometry(screen_rect)
        self.screen_win.show()

        self.receiver = FrameReceiver(self.network)
        self.receiver.frame_received.connect(self.screen_win.remote_view.update_frame)
        self.receiver.error_occurred.connect(self.handle_error)
        self.receiver.start()

    def handle_error(self, msg):
        QMessageBox.warning(self.screen_win, "Error", msg)
        self.app.quit()


def main():
    app = RemoteClientApp()
    sys.exit(app.app.exec_())


if __name__ == "__main__":
    main()

'''


import sys
import os
import threading
import time

import lz4.frame
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QMessageBox, QFrame
)
from PyQt5.QtGui import QPixmap, QImage, QPainter
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# Add parent dir for common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.network import (
    NetworkManager,
    MSG_FRAME, MSG_MOUSE_MOVE, MSG_MOUSE_CLICK,
    MSG_KEY_PRESS, MSG_KEY_RELEASE
)

LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")


class FrameReceiver(QThread):
    frame_received = pyqtSignal(QImage)
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

                compressed = data.get('data')
                jpeg_bytes = lz4.frame.decompress(compressed)
                q_img = QImage.fromData(jpeg_bytes)
                if q_img.isNull():
                    self.error_occurred.emit("Invalid image data")
                    continue

                self.frame_received.emit(q_img)
            except Exception as e:
                self.error_occurred.emit(f"Receive error: {e}")
                time.sleep(1)

    def stop(self):
        self.running = False
        self.wait()


class ConnectionWindow(QWidget):
    connected = pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Connect to Remote Host")
        self.setFixedSize(500, 300)
        layout = QVBoxLayout(self)

        logo = QLabel()
        pix = QPixmap(LOGO_PATH)
        logo.setPixmap(pix.scaled(450, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        self.host_input = QLineEdit("localhost")
        layout.addWidget(self.host_input)

        self.port_input = QLineEdit("9999")
        layout.addWidget(self.port_input)

        btn = QPushButton("Connect")
        btn.clicked.connect(self.on_connect)
        layout.addWidget(btn, alignment=Qt.AlignCenter)

    def on_connect(self):
        try:
            port = int(self.port_input.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Port", "Enter a valid port.")
            return
        self.connected.emit(self.host_input.text(), port)


class RemoteView(QFrame):
    def __init__(self, network):
        super().__init__()
        self.network = network
        self.setStyleSheet("QFrame { border: 2px solid green; }")
        self.remote_pixmap = None
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    def update_frame(self, q_img):
        self.remote_pixmap = QPixmap.fromImage(q_img)
        self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if self.remote_pixmap:
            painter = QPainter(self)
            painter.drawPixmap(self.rect(), self.remote_pixmap)

    def mouseMoveEvent(self, e):
        if not self.remote_pixmap: return
        x, y = e.x() / self.width(), e.y() / self.height()
        self.network.send_data({'type': MSG_MOUSE_MOVE, 'x': x, 'y': y})

    def mousePressEvent(self, e):
        if not self.remote_pixmap: return
        x, y = e.x() / self.width(), e.y() / self.height()
        btn = 'left' if e.button() == Qt.LeftButton else 'right'
        self.network.send_data({
            'type': MSG_MOUSE_CLICK, 'x': x, 'y': y,
            'button': btn, 'clicks': 1
        })

    def keyPressEvent(self, e):
        k = e.text().lower()
        if k:
            self.network.send_data({'type': MSG_KEY_PRESS, 'key': k})

    def keyReleaseEvent(self, e):
        k = e.text().lower()
        if k:
            self.network.send_data({'type': MSG_KEY_RELEASE, 'key': k})


class ScreenWindow(QMainWindow):
    def __init__(self, network):
        super().__init__()
        self.network = network
        self.setWindowTitle("Remote Control Session")
        self._build_ui()

    def _build_ui(self):
        c = QWidget()
        v = QVBoxLayout(c)
        v.setContentsMargins(0, 0, 0, 0)

        bar = QWidget()
        bar.setFixedHeight(50)
        bar.setStyleSheet("background-color:#f0f0f0;")
        h = QHBoxLayout(bar)
        h.setContentsMargins(10, 0, 10, 0)

        logo = QLabel()
        pix = QPixmap(LOGO_PATH)
        logo.setPixmap(pix.scaledToHeight(40, Qt.SmoothTransformation))
        h.addWidget(logo)
        h.addStretch()

        # Focus Mode button
        self.fullscreen_btn = QPushButton("Focus Mode")
        self.fullscreen_btn.setCheckable(True)
        self.fullscreen_btn.setStyleSheet("padding:5px;")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        h.addWidget(self.fullscreen_btn)

        # Disconnect button
        disc = QPushButton("Disconnect")
        disc.setStyleSheet("background-color:red;color:white;padding:5px;")
        disc.clicked.connect(lambda: QApplication.quit())
        h.addWidget(disc)

        v.addWidget(bar)

        self.remote_view = RemoteView(self.network)
        v.addWidget(self.remote_view)
        self.setCentralWidget(c)

    def show_fullscreen(self):
        self.showMaximized()

    def toggle_fullscreen(self):
        if self.fullscreen_btn.isChecked():
            self.fullscreen_btn.setText("Exit Focus Mode")
            self.showFullScreen()
        else:
            self.fullscreen_btn.setText("Focus Mode")
            self.showNormal()
            self.showMaximized()



class RemoteClientApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.network = NetworkManager(is_server=False)
        self.conn = ConnectionWindow()
        self.conn.connected.connect(self.start)
        self.conn.show()

    def start(self, host, port):
        self.conn.close()
        if not (self.network.connect(host, port) and self.network.authenticate()):
            QMessageBox.warning(None, "Connection Failed", f"{host}:{port}")
            self.app.quit()
            return

        self.win = ScreenWindow(self.network)
        self.win.show_fullscreen()

        self.receiver = FrameReceiver(self.network)
        self.receiver.frame_received.connect(self.win.remote_view.update_frame)
        self.receiver.error_occurred.connect(lambda m: QMessageBox.warning(self.win, "Error", m))
        self.receiver.start()

    def run(self):
        sys.exit(self.app.exec_())


def main():
    RemoteClientApp().run()


if __name__ == "__main__":
    main()
