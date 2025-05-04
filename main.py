import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description='Remote Access and Control MVP')
    parser.add_argument('mode', choices=['host', 'client'], help='Start as host or client')

    # Host-specific arguments
    parser.add_argument('--host', default='0.0.0.0',
                        help='Host address to bind (host mode) or connect to (client mode)')
    parser.add_argument('--port', type=int, default=9999, help='Port to use')
    parser.add_argument('--quality', type=int, default=70, help='[Host only] JPEG compression quality (0-100)')
    parser.add_argument('--fps', type=int, default=15, help='[Host only] Target frames per second')

    args = parser.parse_args()

    if args.mode == 'host':
        # Import and run host
        try:
            from host.host import RemoteHost

            host = RemoteHost(
                host=args.host,
                port=args.port,
                quality=args.quality,
                frame_rate=args.fps
            )

            if host.start():
                print("Press Ctrl+C to stop the server")
                try:
                    while host.running:
                        import time
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\nStopping server...")
                finally:
                    host.stop()
        except ImportError:
            print("Error: Could not import host module. Make sure all dependencies are installed.")
            return 1

    elif args.mode == 'client':
        # Import and run client
        try:
            from client.client import main as client_main
            client_main()
        except ImportError:
            print("Error: Could not import client module. Make sure all dependencies are installed.")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
