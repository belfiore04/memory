
import os
import time
import uuid
from dotenv import load_dotenv
from langfuse import Langfuse

# Load environment variables
load_dotenv()

from langfuse import get_client

# Load environment variables
load_dotenv()

def test_score():
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    print(f"Host: {host}")
    print(f"Public Key: {public_key[:5]}..." if public_key else "Public Key: None")
    
    try:
        client = get_client() # Uses env vars automatically
        
        trace_id = f"test-trace-{uuid.uuid4()}"
        print(f"Creating test trace: {trace_id}")
        
        # In v2/v3, usage might vary. get_client() returns a singleton 
        # that usually exposes score().
        
        client.create_score(
            trace_id=trace_id,
            name="user_feedback_script",
            value=1.0,
            comment="Test from script using get_client"
        )
        
        print("Score submitted. Flushing...")
        client.flush()
        print("Done.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_score()
