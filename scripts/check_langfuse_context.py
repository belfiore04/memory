
import asyncio
from langfuse import observe, get_client
import sys
from dotenv import load_dotenv

load_dotenv()

# Mock client to avoid network errors or needing keys if possible?
# But get_client() initializes based on env vars. The user has valid env vars.
# We just want to check local context propagation.

@observe(name="Inner Function")
async def inner_function():
    # Check what Langfuse thinks is the current trace ID
    trace_id = get_client().get_current_trace_id()
    print(f"Inner Function Trace ID: {trace_id}")
    return trace_id

async def background_task(parent_trace_id):
    print(f"Background Task received parent Trace ID: {parent_trace_id}")
    
    # 1. Simulating the fix: manually creating a trace handle
    print("Attempting to restore context using trace(id=...).span(...)")
    
    # Initialize trace object pointing to the parent trace
    trace = get_client().trace(id=parent_trace_id)
    
    # Create the span for this background task
    # IMPORTANT: We hope this sets the context for downstream @observe calls
    with trace.span(name="Background Wrapper") as span:
        current_id = get_client().get_current_trace_id()
        print(f"Trace ID inside span context: {current_id}")
        
        if current_id != parent_trace_id:
            print(f"WARNING: Current Trace ID {current_id} != Parent Trace ID {parent_trace_id}")
        
        # Call inner function
        inner_trace_id = await inner_function()
        
        if inner_trace_id == parent_trace_id:
            print("SUCCESS: Inner function attached to parent trace.")
        else:
            print(f"FAILURE: Inner function has different trace ID: {inner_trace_id}")
            # Identify if it created a new trace or what
            if inner_trace_id != current_id:
                 print("Inner function created YET ANOTHER trace?")

@observe(name="Root Trace")
async def main():
    root_trace_id = get_client().get_current_trace_id()
    print(f"Root Trace ID: {root_trace_id}")
    
    # Verify that get_current_trace_id works
    if not root_trace_id:
        print("ERROR: Could not get root trace ID. Check API keys/connection?")
        return

    await background_task(root_trace_id)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Execution failed: {e}")
