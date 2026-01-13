# Copyright (c) Statistics Canada. All rights reserved.

"""
helpers
~~~~~~~
Helper functions for tests.

This contains basic helper functions to demonstrate the test infrastructure.
"""


def get_default_timeout():
    """Get the default timeout for tests."""
    return 30


def format_test_name(test_name):
    """Format test name for logging."""
    return f"[TEST] {test_name}"