import pytest
from regions import SUPPORTED, label, resolve


def test_label_valid():
    assert label("us-east-1") == "US East (N. Virginia)"


def test_label_invalid():
    assert label("stinky") == "stinky"


def test_resolve_valid_name():
    assert resolve("US East (N. Virginia)") == "us-east-1"


def test_resolve_valid_code():
    assert resolve("us-east-1") == "us-east-1"


def test_resolve_invalid():
    assert resolve("stinky") is None


def test_resolve_none():
    assert resolve(None) is None


def test_resolve_empty():
    assert resolve("") is None


def test_resolve_whitespace():
    assert resolve("   ") is None


def test_resolve_case_insensitive():
    assert resolve("us-EAST-1") == "us-east-1"


def test_resolve_trailing_whitespace():
    assert resolve("us-east-1   ") == "us-east-1"


def test_resolve_case_insensitive_name():
    assert resolve("us east (n. virginia)") == "us-east-1"


def test_resolve_case_insensitive_name_with_whitespace():
    assert resolve("   us east (n. virginia)   ") == "us-east-1"


@pytest.mark.parametrize("code", SUPPORTED)
def test_round_trip(code):
    assert resolve(label(code)) == code
