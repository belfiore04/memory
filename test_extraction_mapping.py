
import json
from agents.extraction_agent import ExtractionAgent
from unittest.mock import MagicMock

def test_mapping():
    agent = ExtractionAgent()
    
    # Mock the LLM response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    # Return a JSON with English slot name directly
    mock_response.choices[0].message.content = json.dumps({
        "slot_updates": [
            {
                "slot": "occupation",
                "value": "程序员",
                "evidence": "我是写代码的"
            }
        ],
        "memory_items": [],
        "recent_focus": []
    })
    mock_response.usage = None
    
    agent.client.chat.completions.create = MagicMock(return_value=mock_response)
    
    # Run analysis
    result = agent.analyze_query("user_123", "我是写代码的")
    
    print(f"Result slot: {result['slot_updates'][0]['slot']}")
    if result['slot_updates'][0]['slot'] == "occupation":
        print("Success: Kept occupation as is")
    else:
        print("Failure: Unexpected slot name")

if __name__ == "__main__":
    test_mapping()
