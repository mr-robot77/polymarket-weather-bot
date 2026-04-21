import sys
import os
import pytest

# Add src to python path so tests can run
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from market_scanner import MarketScanner

@pytest.fixture
def scanner():
    return MarketScanner()

def test_parse_market_details_valid(scanner):
    market = {
        "id": "123",
        "question": "Will the temperature in Chicago be 80-84 degrees on April 25?",
        "tokens": [{"token_id": "abc"}],
        "clobTokenIds": ["def"],
        "outcomes": ["Yes", "No"],
        "marketSlug": "chicago-temp-apr-25"
    }
    details = scanner.parse_market_details(market)
    assert details is not None
    assert details["city"] == "Chicago"
    assert details["temp_min"] == 80.0
    assert details["temp_max"] == 84.0
    assert details["date"] == "April 25"
    assert details["title"] == market["question"]

def test_parse_market_details_invalid(scanner):
    market = {
        "id": "123",
        "question": "Will Trump win the election?",
    }
    details = scanner.parse_market_details(market)
    assert details is None
