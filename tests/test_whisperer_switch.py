import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock dependencies to avoid actual service instantiation and side effects
sys.modules['services.memory_service'] = MagicMock()
sys.modules['services.context_service'] = MagicMock()
sys.modules['services.profile_service'] = MagicMock()
sys.modules['services.chat_log_service'] = MagicMock()
sys.modules['services.trace_service'] = MagicMock()
sys.modules['services.feedback_service'] = MagicMock()
sys.modules['services.focus_service'] = MagicMock()
sys.modules['agents.extraction_agent'] = MagicMock()
sys.modules['agents.whisperer_agent'] = MagicMock()
sys.modules['agents.whisperer_agent'] = MagicMock()
sys.modules['routers.auth'] = MagicMock()

from pydantic import BaseModel
class MessageItem(BaseModel):
    role: str
    content: str
mock_schemas = MagicMock()
mock_schemas.MessageItem = MessageItem
sys.modules['schemas.common'] = mock_schemas


# Mock openai and langfuse
mock_openai = MagicMock()
sys.modules['openai'] = mock_openai
mock_langfuse = MagicMock()
sys.modules['langfuse'] = mock_langfuse
sys.modules['langfuse.openai'] = MagicMock()

# Setup specific mocks for langfuse.get_client().start_as_current_span
mock_span = MagicMock()
mock_span.__enter__ = MagicMock(return_value=None)
mock_span.__exit__ = MagicMock(return_value=None)

mock_client = MagicMock()
mock_client.start_as_current_span.return_value = mock_span
mock_langfuse.get_client.return_value = mock_client
mock_langfuse.observe = lambda name=None, **kwargs: lambda func: func # minimal decorator mock

# Now import the target function
try:
    from routers.chat import _process_chat_background
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

async def test_whisperer_switch():
    print("Testing Whisperer Switch...")

    # Mock Services
    mock_focus_service = MagicMock()
    mock_profile_service = MagicMock()
    mock_whisperer_agent = MagicMock()
    mock_context_service = MagicMock()
    mock_extraction_agent = MagicMock()
    
    # Setup extraction agent result to avoid unpacking errors if logic is hit
    # The code unpacks analysis_result.get("memory_items", []) etc.
    # MagicMock works for .get(), but extraction_agent.analyze_query returns a dict usually.
    mock_extraction_agent.analyze_query.return_value = {
        "memory_items": [],
        "slot_updates": [],
        "recent_focus": []
    }

    # Setup standard returns to ensure it reaches the whisperer block
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"}
    ]
    
    # Mock context data
    mock_context_service.get_context.return_value = {"history": [{"role": "user", "content": "prev"}]}
    mock_profile_service.get_all_slots.return_value = {} # Empty profile
    
    # We need to pass mock services directly since logic uses 'or get_service()'
    
    # Scenario 1: ENABLE_WHISPERER = "false"
    print("\n[Scenario 1] ENABLE_WHISPERER='false'")
    with patch.dict(os.environ, {"ENABLE_WHISPERER": "false"}):
        await _process_chat_background(
            user_id="test_user",
            messages=messages,
            focus_service=mock_focus_service,
            profile_service=mock_profile_service,
            whisperer_agent=mock_whisperer_agent,
            context_service=mock_context_service,
            extraction_agent=mock_extraction_agent,
            memory_service=MagicMock(),
            trace_service=MagicMock()
        )
    
    if mock_whisperer_agent.create_suggestion.called:
        print("FAIL: Whisperer was called when disabled!")
    else:
        print("PASS: Whisperer was NOT called when disabled.")

    # Reset mocks
    mock_whisperer_agent.create_suggestion.reset_mock()

    # Scenario 2: ENABLE_WHISPERER = "true"
    print("\n[Scenario 2] ENABLE_WHISPERER='true'")
    with patch.dict(os.environ, {"ENABLE_WHISPERER": "true"}):
        # We need to ensure we don't hit the "empty data" return
        # Logic: if not active_focus and not current_profile and len(recent_history) <= 2: return
        # We set active_focus to be non-empty
        mock_focus_service.get_active_focus_with_time.return_value = ["some focus"]
        
        # [FIX] Mock return value must be a tuple to satisfy unpacking
        mock_whisperer_agent.create_suggestion.return_value = ("Test Suggestion", 123)
        
        await _process_chat_background(
            user_id="test_user",
            messages=messages,
            focus_service=mock_focus_service,
            profile_service=mock_profile_service,
            whisperer_agent=mock_whisperer_agent,
            context_service=mock_context_service,
            extraction_agent=mock_extraction_agent,
            memory_service=MagicMock(),
            trace_service=MagicMock()
        )

    if mock_whisperer_agent.create_suggestion.called:
        print("PASS: Whisperer was called when enabled.")
    else:
        print("FAIL: Whisperer was NOT called when enabled!")

if __name__ == "__main__":
    asyncio.run(test_whisperer_switch())
