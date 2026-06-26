# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for log redaction in _AnsiColoredFormatter."""

import logging
import sys
from datacommons_api.core.logging import _AnsiColoredFormatter


def _create_record(msg: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test_file.py",
        lineno=10,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_url_parameter_redacted():
    formatter = _AnsiColoredFormatter()

    # Test 'key' parameter
    record1 = _create_record(
        "Fetching http://api.datacommons.org/v2/obs?key=AIzaSyA123_456-abc"
    )
    formatted1 = formatter.format(record1)
    assert "key=[REDACTED]" in formatted1
    assert "AIzaSyA123_456-abc" not in formatted1

    # Test 'api_key' parameter
    record2 = _create_record(
        "Fetching http://api.datacommons.org/v2/obs?api_key=AIzaSyA123"
    )
    formatted2 = formatter.format(record2)
    assert "api_key=[REDACTED]" in formatted2
    assert "AIzaSyA123" not in formatted2

    # Test multiple parameters
    record3 = _create_record(
        "Fetching http://api.datacommons.org/v2/obs?param=true&key=AIzaSyA123"
    )
    formatted3 = formatter.format(record3)
    assert "key=[REDACTED]" in formatted3
    assert "param=true" in formatted3
    assert "AIzaSyA123" not in formatted3


def test_explicit_api_key_redacted():
    formatter = _AnsiColoredFormatter()

    record = _create_record("Configured api_key=AIzaSyA123 in environment")
    formatted = formatter.format(record)
    assert "api_key=[REDACTED]" in formatted
    assert "AIzaSyA123" not in formatted


def test_standalone_long_key_redacted():
    formatter = _AnsiColoredFormatter()

    # Long key (length >= 20) should be redacted
    record1 = _create_record("Found key=AIzaSyA123456789012345")
    formatted1 = formatter.format(record1)
    assert "key=[REDACTED]" in formatted1
    assert "AIzaSyA123456789012345" not in formatted1

    # Standalone key with dashes/underscores
    record2 = _create_record("Found key=AIza_SyA-123456789012")
    formatted2 = formatter.format(record2)
    assert "key=[REDACTED]" in formatted2
    assert "AIza_SyA-123456789012" not in formatted2


def test_legitimate_key_preserved():
    formatter = _AnsiColoredFormatter()

    # Short keys or data keys should be preserved
    record1 = _create_record("Querying key=Count_Person for population")
    formatted1 = formatter.format(record1)
    assert "key=Count_Person" in formatted1

    record2 = _create_record("Querying key=country/USA for entity")
    formatted2 = formatter.format(record2)
    assert "key=country/USA" in formatted2

    # Key length < 20 should be preserved (unless it's api_key= or URL param)
    record3 = _create_record("Found key=short_key_123")  # length 13
    formatted3 = formatter.format(record3)
    assert "key=short_key_123" in formatted3


def test_traceback_redacted():
    formatter = _AnsiColoredFormatter()

    try:
        # Raise an error that contains a key in the message
        raise ValueError("Failed to connect with key=AIzaSyA123456789012345")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test_file.py",
        lineno=10,
        msg="An error occurred",
        args=(),
        exc_info=exc_info,
    )

    formatted = formatter.format(record)
    # The formatted message should contain the traceback, and the key should be redacted
    assert "key=[REDACTED]" in formatted
    assert "AIzaSyA123456789012345" not in formatted


def test_keys_with_special_characters_redacted():
    formatter = _AnsiColoredFormatter()

    # Test key with base64 symbols (+, /, =) and percent encoding (%2B, %2F)
    special_key = "AIzaSyA123+abc/xyz=789%2B%2F"

    # 1. URL parameter redaction
    record1 = _create_record(
        f"Fetching http://api.datacommons.org/v2/obs?key={special_key}&param=true"
    )
    formatted1 = formatter.format(record1)
    assert "key=[REDACTED]" in formatted1
    assert "param=true" in formatted1
    assert special_key not in formatted1

    # 2. Explicit label redaction
    record2 = _create_record(f"Configured api_key={special_key} in context")
    formatted2 = formatter.format(record2)
    assert "api_key=[REDACTED]" in formatted2
    assert special_key not in formatted2

    # 3. Standalone long key redaction
    record3 = _create_record(f"Found key={special_key} in config file")
    formatted3 = formatter.format(record3)
    assert "key=[REDACTED]" in formatted3
    assert special_key not in formatted3
