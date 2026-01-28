
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Adjust path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routers.chat import _process_chat_background

class TestTraceContext(unittest.IsolatedAsyncioTestCase):
    
    @patch("routers.chat.get_client")
    @patch("routers.chat.get_context_service")
    @patch("routers.chat.get_extraction_agent")
    @patch("routers.chat.get_profile_service")
    @patch("routers.chat.get_memory_service")
    @patch("routers.chat.get_trace_service")
    async def test_trace_propagation(self, mock_trace, mock_mem, mock_prof, mock_ext, mock_ctx, mock_get_client):
        # Mock services
        mock_ctx.return_value = MagicMock()
        mock_ext.return_value = MagicMock()
        mock_prof.return_value = MagicMock()
        mock_mem.return_value = AsyncMock()  # memory service methods are async
        mock_trace.return_value = MagicMock()
        
        # Mock Langfuse Client and Span
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_span_context = MagicMock()
        mock_client.start_as_current_span.return_value = mock_span_context
        mock_span_context.__enter__.return_value = MagicMock()
        
        # Mock extraction agent result
        mock_ext.return_value.analyze_query.return_value = {
            "memory_items": [{"content": "fact1", "type": "fact"}], 
            "slot_updates": []
        }
        
        # Test Data
        trace_id = "test-trace-id-123"
        user_id = "user1"
        messages = [{"role": "user", "content": "hello"}]
        
        # Call the function
        await _process_chat_background(
            user_id=user_id,
            messages=messages,
            langfuse_trace_id=trace_id
        )
        
        # VERIFY: start_as_current_span called 3 times (对话记忆整理, 记忆提取, 分析对话内容)
        self.assertEqual(mock_client.start_as_current_span.call_count, 3)

        # First call should be 对话记忆整理 with trace_context
        first_call = mock_client.start_as_current_span.call_args_list[0]
        _, first_kwargs = first_call
        self.assertEqual(first_kwargs['name'], "对话记忆整理")
        self.assertEqual(first_kwargs['trace_context'], {"trace_id": trace_id})

        # Second call should be 记忆提取 without trace_context
        second_call = mock_client.start_as_current_span.call_args_list[1]
        _, second_kwargs = second_call
        self.assertEqual(second_kwargs['name'], "记忆提取")

        # Third call should be 分析对话内容 without trace_context
        third_call = mock_client.start_as_current_span.call_args_list[2]
        _, third_kwargs = third_call
        self.assertEqual(third_kwargs['name'], "分析对话内容")

        # Verify analyze_query was NOT called with langfuse_trace_id kwarg
        analyze_call_kwargs = mock_ext.return_value.analyze_query.call_args
        self.assertNotIn("langfuse_trace_id", analyze_call_kwargs.kwargs)

        # Verify add_memory_item called
        mock_mem.return_value.add_memory_item.assert_called()

if __name__ == "__main__":
    unittest.main()
