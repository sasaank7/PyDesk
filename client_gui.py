from PyQt5 import QtWidgets, QtGui, QtCore
import os
import sys
import subprocess

# Determine base path (for PyInstaller bundle or normal run)
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)

# Paths
LOGO_FILE = os.path.join(base_path, "digital_tree_logo.png")
BANNER_FILE = os.path.join(base_path, "digital_nebula.jpg")  # Your JPEG file
ICON_FILE = os.path.join(base_path, "computer_icon.png")

# --- Login Window ---
class LoginWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Remote Control Client Login")
        self.setFixedSize(600, 400)
        self.setStyleSheet("background-color: #f5f5f5;")

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)

        if os.path.exists(LOGO_FILE):
            logo = QtGui.QPixmap(LOGO_FILE)
            logo_lbl = QtWidgets.QLabel()
            logo_lbl.setPixmap(logo.scaledToWidth(200, QtCore.Qt.SmoothTransformation))
            logo_lbl.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(logo_lbl)

        form_layout = QtWidgets.QFormLayout()
        self.username = QtWidgets.QLineEdit()
        self.username.setFixedHeight(35)
        self.password = QtWidgets.QLineEdit()
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password.setFixedHeight(35)

        form_layout.addRow("Username:", self.username)
        form_layout.addRow("Password:", self.password)
        layout.addLayout(form_layout)

        self.submit_btn = QtWidgets.QPushButton("Submit")
        self.submit_btn.setFixedSize(150, 45)
        self.submit_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.submit_btn.clicked.connect(self.on_submit)
        layout.addWidget(self.submit_btn, alignment=QtCore.Qt.AlignCenter)

        self.setLayout(layout)

    def on_submit(self):
        if self.username.text().strip() == "Admin" and self.password.text().strip() == "password":
            self.accepted = True
            self.close()
        else:
            QtWidgets.QMessageBox.critical(self, "Login Failed", "Invalid username or password.")
            self.accepted = False


# --- Host Window ---
class HostWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Select Host")
        self.setFixedSize(500, 300)
        self.setStyleSheet("background-color: #f5f5f5;")

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)

        if os.path.exists(BANNER_FILE):
            banner = QtGui.QPixmap(BANNER_FILE)
            banner_lbl = QtWidgets.QLabel()
            banner_lbl.setPixmap(banner.scaled(440, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            banner_lbl.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(banner_lbl)

        self.host_btn = QtWidgets.QPushButton("HOST")
        self.host_btn.setFixedSize(200, 60)
        self.host_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; font-size: 16px;")

        if os.path.exists(ICON_FILE):
            icon = QtGui.QIcon(ICON_FILE)
            self.host_btn.setIcon(icon)
            self.host_btn.setIconSize(QtCore.QSize(32, 32))

        self.host_btn.clicked.connect(self.launch_client)
        layout.addWidget(self.host_btn, alignment=QtCore.Qt.AlignCenter)

        self.setLayout(layout)

    def launch_client(self):
        python_exe = sys.executable
        base_dir = os.path.dirname(os.path.abspath(__file__))
        main_script = os.path.join(base_dir, "main.py")

        cmd = [python_exe, main_script, "client", "--host", "localhost", "--port", "9999"]
        subprocess.Popen(cmd, cwd=base_dir)
        self.close()


# Entry Point
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    login = LoginWindow()
    login.show()
    app.exec_()

    if getattr(login, 'accepted', False):
        host = HostWindow()
        host.show()
        app.exec_()
