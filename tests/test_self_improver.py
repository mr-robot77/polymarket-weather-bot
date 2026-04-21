import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from self_improver import SelfImprover

@pytest.fixture
def improver():
    return SelfImprover()

def test_extract_json_valid(improver):
    llm_output = "Here are the new rules:\n```json\n{\n  \"key\": \"value\"\n}\n```\nLooks good!"
    extracted = improver.extract_json(llm_output)
    assert extracted is not None
    assert "key" in extracted
    assert "value" in extracted

def test_extract_json_invalid(improver):
    llm_output = "No json here."
    extracted = improver.extract_json(llm_output)
    assert extracted is None
