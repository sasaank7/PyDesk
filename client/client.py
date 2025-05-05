import sys
import os
import time
import lz4.frame
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QFrame
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

        # Hardcoded host and port
        host = "localhost"
        port = 9999

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
