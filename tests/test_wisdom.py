import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from wisdom import WisdomManager

@pytest.fixture
def wisdom_manager():
    return WisdomManager()

def test_extract_json_valid(wisdom_manager):
    llm_output = "Here is the wisdom:\n```json\n{\n  \"wisdom\": \"Patience is key\",\n  \"reasoning\": \"Market is slow\"\n}\n```\nLooks good!"
    extracted = wisdom_manager.extract_json(llm_output)
    assert extracted is not None
    assert "wisdom" in extracted
    assert extracted["wisdom"] == "Patience is key"

def test_extract_json_invalid(wisdom_manager):
    llm_output = "No json here."
    extracted = wisdom_manager.extract_json(llm_output)
    assert extracted is None
