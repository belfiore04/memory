import redis
import sys

def test_connection():
    host = "localhost"
    port = 6380
    print(f"Attempting to connect to FalkorDB at {host}:{port}...")
    
    try:
        r = redis.Redis(host=host, port=port, socket_connect_timeout=2)
        info = r.info(section="server")
        print("Success! Connected to Redis/FalkorDB.")
        print(f"Redis Version: {info.get('redis_version')}")
    except Exception as e:
        print(f"Connection Failed: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_connection()
