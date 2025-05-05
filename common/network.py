import socket
import struct
import pickle
import ssl
from cryptography.fernet import Fernet

# Constants
DEFAULT_PORT = 9999
BUFFER_SIZE = 4096
AUTH_KEY = "remote_control_auth_key_2025"  # Simple authentication key for MVP

# Message types
MSG_AUTH = 0
MSG_FRAME = 1
MSG_MOUSE_MOVE = 2
MSG_MOUSE_CLICK = 3
MSG_KEY_PRESS = 4
MSG_KEY_RELEASE = 5
MSG_FILE_TRANSFER = 6  # Optional enhancement


class NetworkManager:
    """Handles network communication for both client and host"""

    def __init__(self, is_server=False, use_ssl=False):
        self.is_server = is_server
        self.use_ssl = use_ssl
        self.socket = None
        self.client_socket = None
        self.encryption_key = Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)

    def start_server(self, host='0.0.0.0', port=DEFAULT_PORT):
        """Start a server socket to listen for connections"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Apply SSL if needed (optional enhancement)
        if self.use_ssl:
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(certfile="cert.pem", keyfile="key.pem")
            self.socket = context.wrap_socket(self.socket, server_side=True)

        self.socket.bind((host, port))
        self.socket.listen(1)
        print(f"Server started on {host}:{port}")

        # Accept client connection
        self.client_socket, addr = self.socket.accept()
        print(f"Connection from {addr}")

        # Send encryption key
        self._send_raw(self.encryption_key)

        return True

    def connect(self, host, port=DEFAULT_PORT):
        """Connect to a remote host"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # Apply SSL if needed (optional enhancement)
            if self.use_ssl:
                context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                self.socket = context.wrap_socket(self.socket)

            self.socket.connect((host, port))
            print(f"Connecting....")

            # Receive encryption key
            self.encryption_key = self._recv_raw()
            self.cipher = Fernet(self.encryption_key)

            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def authenticate(self, key=AUTH_KEY):
        """Send authentication to the server"""
        if self.is_server:
            # Server receives authentication
            data = self.receive_data()
            if data['type'] == MSG_AUTH and data['key'] == AUTH_KEY:
                return True
            return False
        else:
            # Client sends authentication
            self.send_data({'type': MSG_AUTH, 'key': key})
            return True

    def send_data(self, data):
        """Send data with type and size header"""
        try:
            if self.is_server:
                socket_to_use = self.client_socket
            else:
                socket_to_use = self.socket

            # Serialize the data
            serialized = pickle.dumps(data)

            # Encrypt the data
            encrypted = self.cipher.encrypt(serialized)

            # Prepare header (content size)
            header = struct.pack("!I", len(encrypted))

            # Send header followed by content
            socket_to_use.sendall(header + encrypted)
            return True
        except Exception as e:
            print(f"Error sending data: {e}")
            return False

    def _send_raw(self, data):
        """Send raw data without encryption (used for key exchange)"""
        if isinstance(data, str):
            data = data.encode()

        if self.is_server:
            socket_to_use = self.client_socket
        else:
            socket_to_use = self.socket

        header = struct.pack("!I", len(data))
        socket_to_use.sendall(header + data)

    def _recv_raw(self, buffer_size=BUFFER_SIZE):
        """Receive raw data without decryption (used for key exchange)"""
        if self.is_server:
            socket_to_use = self.client_socket
        else:
            socket_to_use = self.socket

        header = socket_to_use.recv(4)
        if not header:
            return None

        data_size = struct.unpack("!I", header)[0]

        chunks = []
        bytes_received = 0

        while bytes_received < data_size:
            chunk_size = min(buffer_size, data_size - bytes_received)
            chunk = socket_to_use.recv(chunk_size)
            if not chunk:
                raise ConnectionError("Connection closed while receiving data")
            chunks.append(chunk)
            bytes_received += len(chunk)

        return b''.join(chunks)

    def receive_data(self, buffer_size=BUFFER_SIZE):
        """Receive data with handling for large payloads"""
        try:
            if self.is_server:
                socket_to_use = self.client_socket
            else:
                socket_to_use = self.socket

            # First receive the header containing content size
            header = socket_to_use.recv(4)
            if not header:
                return None

            data_size = struct.unpack("!I", header)[0]

            # Receive the content in chunks if necessary
            chunks = []
            bytes_received = 0

            while bytes_received < data_size:
                chunk_size = min(buffer_size, data_size - bytes_received)
                chunk = socket_to_use.recv(chunk_size)
                if not chunk:
                    raise ConnectionError("Connection closed while receiving data")
                chunks.append(chunk)
                bytes_received += len(chunk)

            encrypted_data = b''.join(chunks)

            # Decrypt the data
            decrypted = self.cipher.decrypt(encrypted_data)

            # Deserialize the data
            data = pickle.loads(decrypted)

            return data
        except Exception as e:
            print(f"Error receiving data: {e}")
            return None

    def close(self):
        """Close the connection"""
        try:
            if self.is_server and self.client_socket:
                self.client_socket.close()
            if self.socket:
                self.socket.close()
            return True
        except Exception as e:
            print(f"Error closing connection: {e}")
            return False