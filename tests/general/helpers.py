# Copyright (c) Statistics Canada. All rights reserved.

"""
helpers
~~~~~~~
Helper functions and configuration for tests.

This contains basic helper functions and configuration constants.
"""

# Test configuration constants
TEST_CONFIG = {
    'default_timeout': 30,
    'container_start_timeout': 60,
    'http_request_timeout': 10,
    'retry_attempts': 3,
}


def get_default_timeout():
    """Get the default timeout for tests."""
    return TEST_CONFIG['default_timeout']


def format_test_name(test_name):
    """Format test name for logging."""
    return f"[TEST] {test_name}"


def get_test_config(key, default=None):
    """Get a configuration value."""
    return TEST_CONFIG.get(key, default)