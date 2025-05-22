"""Tests for top-level package imports."""

import pytest

def test_top_level_imports():
    """Verify that core classes can be imported directly from the tyler package."""
    try:
        from tyler import (
            Agent,
            StreamUpdate,
            Thread,
            Message,
            ThreadStore,
            FileStore,
            Registry,
            Attachment
        )
        # If imports succeed, the test passes implicitly
        assert True 
    except ImportError as e:
        pytest.fail(f"Failed to import one or more top-level classes: {e}")

# Example of testing a utility function if needed (optional)
# def test_top_level_utils():
#     try:
#         from tyler import get_logger
#         assert callable(get_logger)
#     except ImportError as e:
#         pytest.fail(f"Failed to import get_logger: {e}") 