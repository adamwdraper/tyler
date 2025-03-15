"""
Tools package initialization.
"""
import importlib
import sys
import os
import glob
from typing import Dict, List
from tyler.utils.logging import get_logger

# Get configured logger
logger = get_logger(__name__)

# Initialize empty tool lists for each module
WEB_TOOLS = []
SLACK_TOOLS = []
COMMAND_LINE_TOOLS = []
NOTION_TOOLS = []
IMAGE_TOOLS = []
AUDIO_TOOLS = []
FILES_TOOLS = []
BROWSER_TOOLS = []

# Combined tools list
TOOLS = []

# Try to import each tool module
try:
    from . import web as web_module
    from . import slack as slack_module
    from . import command_line as command_line_module
    from . import notion as notion_module
    from . import image as image_module
    from . import audio as audio_module
    from . import files as files_module
    from . import browser as browser_module
except ImportError as e:
    print(f"Warning: Some tool modules could not be imported: {e}")

# Get tool lists from each module and maintain both individual and combined lists
try:
    module_tools = getattr(web_module, "TOOLS", [])
    WEB_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load web tools: {e}")

try:
    module_tools = getattr(slack_module, "TOOLS", [])
    SLACK_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load slack tools: {e}")

try:
    module_tools = getattr(command_line_module, "TOOLS", [])
    COMMAND_LINE_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load command line tools: {e}")

try:
    module_tools = getattr(notion_module, "TOOLS", [])
    NOTION_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load notion tools: {e}")

try:
    module_tools = getattr(image_module, "TOOLS", [])
    IMAGE_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load image tools: {e}")

try:
    module_tools = getattr(audio_module, "TOOLS", [])
    AUDIO_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load audio tools: {e}")

try:
    module_tools = getattr(files_module, "TOOLS", [])
    FILES_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load files tools: {e}")

try:
    module_tools = getattr(browser_module, "TOOLS", [])
    BROWSER_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load browser tools: {e}")

__all__ = [
    'TOOLS',
    'WEB_TOOLS',
    'SLACK_TOOLS',
    'COMMAND_LINE_TOOLS',
    'NOTION_TOOLS',
    'IMAGE_TOOLS',
    'AUDIO_TOOLS',
    'FILES_TOOLS',
    'BROWSER_TOOLS'
]

# Map of module names to their tools for dynamic loading
TOOL_MODULES: Dict[str, List] = {
    'web': WEB_TOOLS,
    'slack': SLACK_TOOLS,
    'command_line': COMMAND_LINE_TOOLS,
    'notion': NOTION_TOOLS,
    'image': IMAGE_TOOLS,
    'audio': AUDIO_TOOLS,
    'files': FILES_TOOLS,
    'browser': BROWSER_TOOLS
} 