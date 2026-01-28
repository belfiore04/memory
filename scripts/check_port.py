import socket
import sys

def check_port(host, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        if result == 0:
            print(f"Success: Port {port} is open")
            return True
        else:
            print(f"Error: Port {port} is closed (code: {result})")
            return False
        sock.close()
    except Exception as e:
        print(f"Exception: {e}")
        return False

if __name__ == "__main__":
    check_port("localhost", 6380)
