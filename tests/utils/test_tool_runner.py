import pytest
from tyler.utils.tool_runner import ToolRunner
from pathlib import Path
import os
from unittest.mock import patch, MagicMock
import asyncio
import json
import types
import sys
import importlib
import base64

@pytest.fixture
def tool_runner():
    return ToolRunner()

@pytest.fixture
def sample_tool():
    return {
        'definition': {
            'type': 'function',
            'function': {
                'name': 'test_tool',
                'description': 'A test tool',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'param1': {'type': 'string'}
                    },
                    'required': ['param1']
                }
            }
        },
        'implementation': lambda param1: f"Result: {param1}"
    }

@pytest.fixture
def sample_async_tool():
    async def async_implementation(param1: str) -> str:
        await asyncio.sleep(0.1)  # Simulate async work
        return f"Async Result: {param1}"
        
    return {
        'definition': {
            'type': 'function',
            'function': {
                'name': 'test_async_tool',
                'description': 'An async test tool',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'param1': {'type': 'string'}
                    },
                    'required': ['param1']
                }
            }
        },
        'implementation': async_implementation
    }

@pytest.fixture
def sample_interrupt_tool():
    """Fixture for an interrupt-type tool"""
    return {
        'definition': {
            'type': 'function',
            'function': {
                'name': 'test_interrupt_tool',
                'description': 'A test interrupt tool',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'message': {'type': 'string'},
                        'severity': {
                            'type': 'string',
                            'enum': ['high', 'medium', 'low']
                        }
                    },
                    'required': ['message', 'severity']
                }
            }
        },
        'implementation': lambda message, severity: json.dumps({
            'type': 'interrupt_detected',
            'message': message,
            'severity': severity
        }),
        'attributes': {
            'type': 'interrupt'
        }
    }

@pytest.fixture
def sample_file_tool():
    """Fixture for a tool that returns files in tuple format"""
    async def file_tool_impl(filename: str) -> tuple[dict, list[dict]]:
        return (
            {"success": True, "message": "File generated"},
            [{
                "content": b"test content",
                "filename": filename,
                "mime_type": "text/plain"
            }]
        )
    
    return {
        'definition': {
            'type': 'function',
            'function': {
                'name': 'test_file_tool',
                'description': 'A test tool that returns files',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'filename': {'type': 'string'}
                    },
                    'required': ['filename']
                }
            }
        },
        'implementation': file_tool_impl
    }

def test_register_tool(tool_runner, sample_tool):
    """Test registering a new tool"""
    tool_runner.register_tool('test_tool', sample_tool['implementation'])
    assert 'test_tool' in tool_runner.tools
    assert 'implementation' in tool_runner.tools['test_tool']
    assert not tool_runner.tools['test_tool']['is_async']

def test_register_and_get_tool_attributes(tool_runner):
    """Test registering and retrieving tool attributes"""
    tool_name = "test_tool"
    
    # Test tool without attributes
    assert tool_runner.get_tool_attributes(tool_name) is None
    
    # Test tool with interrupt type
    test_attributes = {
        "type": "interrupt"
    }
    tool_runner.register_tool_attributes(tool_name, test_attributes)
    assert tool_name in tool_runner.tool_attributes
    assert tool_runner.tool_attributes[tool_name] == test_attributes
    
    # Test getting attributes
    retrieved_attributes = tool_runner.get_tool_attributes(tool_name)
    assert retrieved_attributes == test_attributes
    
    # Test tool with empty attributes
    tool_name_2 = "test_tool_2"
    tool_runner.register_tool_attributes(tool_name_2, {})
    assert tool_runner.get_tool_attributes(tool_name_2) == {}
    
    # Test getting attributes for non-existent tool
    assert tool_runner.get_tool_attributes("nonexistent-tool") is None

def test_register_async_tool(tool_runner, sample_async_tool):
    """Test registering a new async tool"""
    tool_runner.register_tool('test_async_tool', sample_async_tool['implementation'])
    assert 'test_async_tool' in tool_runner.tools
    assert 'implementation' in tool_runner.tools['test_async_tool']
    assert tool_runner.tools['test_async_tool']['is_async']

def test_load_tool_module(tool_runner):
    """Test loading tools from a module"""
    # Create a mock module with tools
    mock_module = MagicMock()
    mock_module.TOOLS = [
        {
            'definition': {
                'type': 'function',
                'function': {
                    'name': 'mock_tool',
                    'description': 'A mock tool',
                    'parameters': {}
                }
            },
            'implementation': lambda: "mock result",
            'attributes': {
                'type': 'interrupt'
            }
        },
        {
            'definition': {
                'type': 'function',
                'function': {
                    'name': 'mock_tool_2',
                    'description': 'A mock tool without type',
                    'parameters': {}
                }
            },
            'implementation': lambda: "mock result"
            # No attributes specified
        }
    ]
    
    with patch('importlib.import_module', return_value=mock_module):
        loaded_tools = tool_runner.load_tool_module('test')
        assert len(loaded_tools) == 2
        
        # Check first tool with interrupt type
        assert loaded_tools[0]['function']['name'] == 'mock_tool'
        assert 'mock_tool' in tool_runner.tools
        tool_attributes = tool_runner.get_tool_attributes('mock_tool')
        assert tool_attributes is not None
        assert tool_attributes['type'] == 'interrupt'
        
        # Check second tool without attributes
        assert loaded_tools[1]['function']['name'] == 'mock_tool_2'
        assert 'mock_tool_2' in tool_runner.tools
        assert tool_runner.get_tool_attributes('mock_tool_2') is None

def test_run_tool(tool_runner, sample_tool):
    """Test running a registered tool"""
    tool_runner.register_tool('test_tool', sample_tool['implementation'])
    result = tool_runner.run_tool('test_tool', {'param1': 'hello'})
    assert result == 'Result: hello'

@pytest.mark.asyncio
async def test_run_tool_async(tool_runner, sample_async_tool):
    """Test running a registered async tool"""
    tool_runner.register_tool('test_async_tool', sample_async_tool['implementation'])
    result = await tool_runner.run_tool_async('test_async_tool', {'param1': 'hello'})
    assert result == 'Async Result: hello'

def test_run_tool_with_invalid_name(tool_runner):
    """Test running a nonexistent tool"""
    with pytest.raises(ValueError) as exc_info:
        tool_runner.run_tool("nonexistent-tool", {})
    assert "Tool 'nonexistent-tool' not found" in str(exc_info.value)

def test_run_async_tool_with_sync_method(tool_runner, sample_async_tool):
    """Test running an async tool with sync method"""
    tool_runner.register_tool('test_async_tool', sample_async_tool['implementation'])
    with pytest.raises(ValueError) as exc_info:
        tool_runner.run_tool('test_async_tool', {'param1': 'hello'})
    assert "is async and must be run with run_tool_async" in str(exc_info.value)

@pytest.mark.asyncio
async def test_run_sync_tool_with_async_method(tool_runner, sample_tool):
    """Test running a sync tool with async method"""
    tool_runner.register_tool('test_tool', sample_tool['implementation'])
    result = await tool_runner.run_tool_async('test_tool', {'param1': 'hello'})
    assert result == 'Result: hello'

def test_get_tool_description(tool_runner, sample_tool):
    """Test getting tool descriptions"""
    tool_runner.tools['test_tool'] = {
        'definition': sample_tool['definition']['function'],
        'implementation': sample_tool['implementation']
    }
    desc = tool_runner.get_tool_description('test_tool')
    assert desc == 'A test tool'
    
    # Test invalid tool
    desc = tool_runner.get_tool_description('nonexistent-tool')
    assert desc is None

def test_list_tools(tool_runner, sample_tool):
    """Test listing available tools"""
    tool_runner.tools['test_tool'] = {
        'definition': sample_tool['definition']['function'],
        'implementation': sample_tool['implementation']
    }
    tools = tool_runner.list_tools()
    assert isinstance(tools, list)
    assert 'test_tool' in tools

def test_get_tool_parameters(tool_runner, sample_tool):
    """Test getting tool parameter schemas"""
    tool_runner.tools['test_tool'] = {
        'definition': sample_tool['definition']['function'],
        'implementation': sample_tool['implementation']
    }
    params = tool_runner.get_tool_parameters('test_tool')
    assert isinstance(params, dict)
    assert 'properties' in params
    assert 'param1' in params['properties']
    
    # Test invalid tool
    params = tool_runner.get_tool_parameters('nonexistent-tool')
    assert params is None

def test_get_tools_for_chat_completion(tool_runner, sample_tool):
    """Test getting tools in chat completion format"""
    tool_runner.tools['test_tool'] = {
        'definition': sample_tool['definition']['function'],
        'implementation': sample_tool['implementation']
    }
    tools = tool_runner.get_tools_for_chat_completion()
    assert isinstance(tools, list)
    assert len(tools) == 1
    assert tools[0]['type'] == 'function'
    assert tools[0]['function']['name'] == 'test_tool'
    assert tools[0]['function']['description'] == 'A test tool'

@pytest.mark.asyncio
async def test_execute_tool_call(tool_runner, sample_tool):
    """Test executing a tool call"""
    tool_runner.tools['test_tool'] = {
        'definition': sample_tool['definition']['function'],
        'implementation': sample_tool['implementation'],
        'is_async': False
    }

    # Create a mock tool call object
    tool_call = MagicMock()
    tool_call.id = 'test_id'
    tool_call.function.name = 'test_tool'
    tool_call.function.arguments = '{"param1": "test"}'

    result = await tool_runner.execute_tool_call(tool_call)
    # The raw result should match what the implementation returns
    assert result == 'Result: test'

@pytest.mark.asyncio
async def test_execute_async_tool_call(tool_runner, sample_async_tool):
    """Test executing an async tool call"""
    tool_runner.tools['test_async_tool'] = {
        'definition': sample_async_tool['definition']['function'],
        'implementation': sample_async_tool['implementation'],
        'is_async': True
    }

    # Create a mock tool call object
    tool_call = MagicMock()
    tool_call.id = 'test_id'
    tool_call.function.name = 'test_async_tool'
    tool_call.function.arguments = '{"param1": "test"}'

    result = await tool_runner.execute_tool_call(tool_call)
    # The raw result should match what the implementation returns
    assert result == 'Async Result: test'

def test_register_interrupt_tool(tool_runner, sample_interrupt_tool):
    """Test registering an interrupt tool"""
    tool_runner.register_tool('test_interrupt_tool', sample_interrupt_tool['implementation'], sample_interrupt_tool['definition']['function'])
    tool_runner.register_tool_attributes('test_interrupt_tool', sample_interrupt_tool['attributes'])
    
    # Verify tool registration
    assert 'test_interrupt_tool' in tool_runner.tools
    assert 'implementation' in tool_runner.tools['test_interrupt_tool']
    assert not tool_runner.tools['test_interrupt_tool']['is_async']
    
    # Verify interrupt attributes
    tool_attributes = tool_runner.get_tool_attributes('test_interrupt_tool')
    assert tool_attributes is not None
    assert tool_attributes['type'] == 'interrupt'

@pytest.mark.asyncio
async def test_execute_interrupt_tool_call(tool_runner, sample_interrupt_tool):
    """Test executing an interrupt tool call"""
    # Register the interrupt tool
    tool_runner.register_tool('test_interrupt_tool', sample_interrupt_tool['implementation'], sample_interrupt_tool['definition']['function'])
    tool_runner.register_tool_attributes('test_interrupt_tool', sample_interrupt_tool['attributes'])
    
    # Create a mock tool call object
    tool_call = MagicMock()
    tool_call.id = 'test_interrupt_id'
    tool_call.function.name = 'test_interrupt_tool'
    tool_call.function.arguments = '{"message": "Test interrupt", "severity": "high"}'
    
    # Execute the tool call
    result = await tool_runner.execute_tool_call(tool_call)
    
    # Verify the result - should be the raw JSON string
    expected_json = json.dumps({
        'type': 'interrupt_detected',
        'message': 'Test interrupt',
        'severity': 'high'
    })
    assert result == expected_json

@pytest.mark.asyncio
async def test_execute_async_interrupt_tool_call(tool_runner):
    """Test executing an async interrupt tool"""
    # Define an async interrupt tool
    async def async_interrupt_impl(message: str, severity: str):
        await asyncio.sleep(0.1)  # Simulate async work
        return json.dumps({
            'type': 'async_interrupt',
            'message': message,
            'severity': severity
        })
    
    # Register the async interrupt tool
    tool_runner.register_tool(
        'async_interrupt_tool',
        async_interrupt_impl,
        {
            'name': 'async_interrupt_tool',
            'description': 'An async interrupt tool',
            'parameters': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'severity': {'type': 'string'}
                },
                'required': ['message', 'severity']
            }
        }
    )
    tool_runner.register_tool_attributes('async_interrupt_tool', {'type': 'interrupt'})
    
    # Create a mock tool call
    tool_call = MagicMock()
    tool_call.id = 'async_interrupt_id'
    tool_call.function.name = 'async_interrupt_tool'
    tool_call.function.arguments = '{"message": "Async interrupt", "severity": "medium"}'
    
    # Execute the tool call
    result = await tool_runner.execute_tool_call(tool_call)
    
    # Verify the result - should be the raw JSON string
    expected_json = json.dumps({
        'type': 'async_interrupt',
        'message': 'Async interrupt',
        'severity': 'medium'
    })
    assert result == expected_json

def test_load_interrupt_tool_module(tool_runner):
    """Test loading interrupt tools from a module"""
    # Create a mock module with interrupt tools
    mock_module = MagicMock()
    mock_module.TOOLS = [
        {
            'definition': {
                'type': 'function',
                'function': {
                    'name': 'mock_interrupt_tool',
                    'description': 'A mock interrupt tool',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'message': {'type': 'string'},
                            'severity': {
                                'type': 'string',
                                'enum': ['high', 'medium', 'low']
                            }
                        },
                        'required': ['message', 'severity']
                    }
                }
            },
            'implementation': lambda message, severity: json.dumps({
                'type': 'interrupt_detected',
                'message': message,
                'severity': severity
            }),
            'attributes': {
                'type': 'interrupt'
            }
        }
    ]
    
    with patch('importlib.import_module', return_value=mock_module):
        loaded_tools = tool_runner.load_tool_module('test')
        assert len(loaded_tools) == 1
        
        # Check that the interrupt tool was loaded correctly
        assert loaded_tools[0]['function']['name'] == 'mock_interrupt_tool'
        assert 'mock_interrupt_tool' in tool_runner.tools
        tool_attributes = tool_runner.get_tool_attributes('mock_interrupt_tool')
        assert tool_attributes is not None
        assert tool_attributes['type'] == 'interrupt'

def test_get_tool_definition(tool_runner, sample_tool):
    """Test getting tool definition"""
    # Test with non-existent tool
    assert tool_runner.get_tool_definition('nonexistent') is None
    
    # Test with existing tool
    tool_runner.tools['test_tool'] = {
        'definition': sample_tool['definition']['function'],
        'implementation': sample_tool['implementation']
    }
    definition = tool_runner.get_tool_definition('test_tool')
    assert definition == sample_tool['definition']['function']

def test_run_tool_missing_implementation(tool_runner):
    """Test running a tool with missing implementation"""
    tool_runner.tools['test_tool'] = {}  # Tool with no implementation
    with pytest.raises(ValueError) as exc_info:
        tool_runner.run_tool('test_tool', {})
    assert "Implementation for tool 'test_tool' not found" in str(exc_info.value)

def test_run_tool_execution_error(tool_runner):
    """Test running a tool that raises an exception"""
    def failing_tool():
        raise ValueError("Tool execution failed")
    
    tool_runner.register_tool('failing_tool', failing_tool)
    with pytest.raises(ValueError) as exc_info:
        tool_runner.run_tool('failing_tool', {})
    assert "Error executing tool 'failing_tool': Tool execution failed" in str(exc_info.value)

@pytest.mark.asyncio
async def test_load_tool_module_with_invalid_tools(tool_runner):
    """Test loading tools with invalid formats"""
    mock_module = MagicMock()
    mock_module.TEST_TOOLS = [
        {
            # Missing 'definition' key
            'implementation': lambda: "result"
        },
        {
            'definition': {
                # Invalid type
                'type': 'not_function',
                'function': {
                    'name': 'invalid_tool',
                    'description': 'Invalid tool',
                    'parameters': {}
                }
            },
            'implementation': lambda: "result"
        }
    ]
    
    with patch('importlib.import_module', return_value=mock_module):
        loaded_tools = tool_runner.load_tool_module('test')
        assert len(loaded_tools) == 0  # No tools should be loaded due to invalid formats

@pytest.mark.asyncio
async def test_load_tool_module_import_fallback(tool_runner, monkeypatch):
    """Test tool module loading with import fallback"""
    mock_tool = {
        'definition': {
            'type': 'function',
            'function': {
                'name': 'fallback_tool',
                'description': 'A fallback tool',
                'parameters': {}
            }
        },
        'implementation': lambda: "fallback result",
        'attributes': {'type': 'test'}
    }
    
    # Create a mock tyler.tools module
    mock_tools = types.ModuleType('tyler.tools')
    mock_tools.TOOL_MODULES = {'test': [mock_tool]}
    sys.modules['tyler.tools'] = mock_tools
    
    # Mock importlib.import_module to raise ImportError for tyler.tools.test
    original_import = importlib.import_module
    def mock_import(name, *args, **kwargs):
        if name == 'tyler.tools.test':
            raise ImportError("Module not found")
        if name == 'tyler.tools':
            return mock_tools
        return original_import(name, *args, **kwargs)
    
    monkeypatch.setattr(importlib, 'import_module', mock_import)
    
    try:
        loaded_tools = tool_runner.load_tool_module('test')
        assert len(loaded_tools) == 1
        assert loaded_tools[0]['function']['name'] == 'fallback_tool'
        assert 'fallback_tool' in tool_runner.tools
    finally:
        # Clean up
        if 'tyler.tools' in sys.modules:
            del sys.modules['tyler.tools']

@pytest.mark.asyncio
async def test_load_tool_module_all_imports_fail(tool_runner):
    """Test tool module loading when all imports fail"""
    # Create a mock module that raises ImportError
    def mock_import(*args, **kwargs):
        if args[0] == 'tyler.tools.test':
            raise ImportError("Module not found")
        elif args[0] == 'tyler.tools':
            mock_module = MagicMock()
            mock_module.TOOL_MODULES = {}  # Empty TOOL_MODULES
            return mock_module
        return MagicMock()
    
    with patch('importlib.import_module', side_effect=mock_import):
        # Now we expect a ValueError to be raised
        with pytest.raises(ValueError, match=r".*[Tt]ool module.*test.*not found.*"):
            tool_runner.load_tool_module('test')
        # We're no longer checking for exact error message wording as it's brittle

@pytest.mark.asyncio
async def test_execute_tool_call_with_tuple_return(tool_runner):
    """Test executing a tool that returns a tuple with files"""
    # Define a tool that returns a tuple
    async def file_tool() -> tuple[dict, list]:
        return (
            {"success": True, "message": "File generated"},
            [{
                "filename": "test.txt",
                "content": b"test content",
                "mime_type": "text/plain",
                "description": "A test file"
            }]
        )
    
    # Register the tool
    tool_runner.register_tool('test_file_tool', file_tool)
    
    # Create a tool call
    tool_call = types.SimpleNamespace(
        id="test_id",
        type="function",
        function=types.SimpleNamespace(
            name="test_file_tool",
            arguments='{}'
        )
    )
    
    # Execute the tool
    result = await tool_runner.execute_tool_call(tool_call)
    
    # Check the result structure - should be a tuple with two elements
    assert isinstance(result, tuple)
    assert len(result) == 2
    
    # First element should be a dict with success info
    assert isinstance(result[0], dict)
    assert result[0]["success"] is True
    assert result[0]["message"] == "File generated"
    
    # Second element should be a list of file info
    assert isinstance(result[1], list)
    assert len(result[1]) == 1
    file_info = result[1][0]
    assert file_info["filename"] == "test.txt"
    assert file_info["content"] == b"test content"
    assert file_info["mime_type"] == "text/plain"
    assert file_info["description"] == "A test file"

@pytest.mark.asyncio
async def test_execute_tool_call_with_no_files(tool_runner):
    """Test executing a tool that returns a tuple with no files"""
    async def no_file_tool() -> tuple[dict, None]:
        return ({"success": True}, None)
    
    # Register the tool
    tool_runner.register_tool('no_file_tool', no_file_tool)
    
    # Create a tool call
    tool_call = types.SimpleNamespace(
        id="test_id",
        type="function",
        function=types.SimpleNamespace(
            name="no_file_tool",
            arguments='{}'
        )
    )
    
    # Execute the tool
    result = await tool_runner.execute_tool_call(tool_call)
    
    # Check the result - should be a tuple with two elements
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert result[0] == {"success": True}
    assert result[1] is None

@pytest.mark.asyncio
async def test_execute_tool_call_with_empty_files(tool_runner):
    """Test executing a tool that returns a tuple with empty files list"""
    async def empty_file_tool() -> tuple[dict, list]:
        return ({"success": True}, [])
    
    # Register the tool
    tool_runner.register_tool('empty_file_tool', empty_file_tool)
    
    # Create a tool call
    tool_call = types.SimpleNamespace(
        id="test_id",
        type="function",
        function=types.SimpleNamespace(
            name="empty_file_tool",
            arguments='{}'
        )
    )
    
    # Execute the tool
    result = await tool_runner.execute_tool_call(tool_call)
    
    # Check the result - should be a tuple with two elements
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert result[0] == {"success": True}
    assert result[1] == []

@pytest.mark.asyncio
async def test_execute_tool_call_with_image_file():
    """Test executing a tool that returns an image file."""
    tool_runner = ToolRunner()
    
    # Define a tool that returns an image file
    async def image_tool() -> tuple[dict, list]:
        # Create a simple 1x1 pixel image in base64
        image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        return (
            {"success": True, "message": "Image generated"},
            [{
                "filename": "test.png",
                "content": image_base64,  # Base64 encoded image
                "mime_type": "image/png",
                "description": "A test image"
            }]
        )
    
    # Register the tool
    tool_runner.register_tool('test_image_tool', image_tool)
    
    # Create a tool call
    tool_call = types.SimpleNamespace(
        id="test_id",
        type="function",
        function=types.SimpleNamespace(
            name="test_image_tool",
            arguments='{}'
        )
    )
    
    # Execute the tool
    result = await tool_runner.execute_tool_call(tool_call)
    
    # Check the result structure - should be a tuple with two elements
    assert isinstance(result, tuple)
    assert len(result) == 2
    
    # First element should be a dict with success info
    assert isinstance(result[0], dict)
    assert result[0]["success"] is True
    assert result[0]["message"] == "Image generated"
    
    # Second element should be a list of file info
    assert isinstance(result[1], list)
    assert len(result[1]) == 1
    file_info = result[1][0]
    assert file_info["filename"] == "test.png"
    assert file_info["mime_type"] == "image/png"
    assert file_info["description"] == "A test image"
    
    # Verify the image content is valid base64
    try:
        decoded = base64.b64decode(file_info["content"])
        assert len(decoded) > 0
    except Exception as e:
        pytest.fail(f"Invalid base64 encoding for image content: {str(e)}")

@pytest.mark.asyncio
async def test_execute_tool_call_with_invalid_image_file():
    """Test executing a tool that returns an invalid image file."""
    tool_runner = ToolRunner()
    
    # Define a tool that returns an invalid image file (binary data instead of base64)
    async def invalid_image_tool() -> tuple[dict, list]:
        return (
            {"success": True, "message": "Image generated"},
            [{
                "filename": "test.png",
                "content": b"invalid binary data",  # Binary data, not base64 encoded
                "mime_type": "image/png"
            }]
        )
    
    # Register the tool
    tool_runner.register_tool('invalid_image_tool', invalid_image_tool)
    
    # Create a tool call
    tool_call = types.SimpleNamespace(
        id="test_id",
        type="function",
        function=types.SimpleNamespace(
            name="invalid_image_tool",
            arguments='{}'
        )
    )
    
    # Execute the tool - should return the tuple as is since validation is done at a higher level
    result = await tool_runner.execute_tool_call(tool_call)
    
    # Check the result structure - should be a tuple with two elements
    assert isinstance(result, tuple)
    assert len(result) == 2
    
    # First element should be a dict with success info
    assert isinstance(result[0], dict)
    assert result[0]["success"] is True
    assert result[0]["message"] == "Image generated"
    
    # Second element should be a list of file info
    assert isinstance(result[1], list)
    assert len(result[1]) == 1
    file_info = result[1][0]
    assert file_info["filename"] == "test.png"
    assert file_info["mime_type"] == "image/png"
    assert file_info["content"] == b"invalid binary data"

def test_selective_tool_loading(tool_runner):
    """Test loading specific tools from a module using the format 'module:tool1,tool2'"""
    # Create a mock module with multiple tools
    mock_module = MagicMock()
    mock_module.TOOLS = [
        {
            'definition': {
                'type': 'function',
                'function': {
                    'name': 'mock_tool_1',
                    'description': 'First mock tool',
                    'parameters': {}
                }
            },
            'implementation': lambda: "mock result 1"
        },
        {
            'definition': {
                'type': 'function',
                'function': {
                    'name': 'mock_tool_2',
                    'description': 'Second mock tool',
                    'parameters': {}
                }
            },
            'implementation': lambda: "mock result 2"
        },
        {
            'definition': {
                'type': 'function',
                'function': {
                    'name': 'mock_tool_3',
                    'description': 'Third mock tool',
                    'parameters': {}
                }
            },
            'implementation': lambda: "mock result 3"
        }
    ]
    
    # Test selective loading with the new format
    with patch('importlib.import_module', return_value=mock_module):
        # Load only specific tools
        loaded_tools = tool_runner.load_tool_module('test:mock_tool_1,mock_tool_3')
        
        # Should only have loaded 2 of the 3 tools
        assert len(loaded_tools) == 2
        
        # Check that the right tools were loaded
        tool_names = [tool['function']['name'] for tool in loaded_tools]
        assert 'mock_tool_1' in tool_names
        assert 'mock_tool_2' not in tool_names
        assert 'mock_tool_3' in tool_names
        
        # Check tools are registered in the tool_runner
        assert 'mock_tool_1' in tool_runner.tools
        assert 'mock_tool_2' not in tool_runner.tools
        assert 'mock_tool_3' in tool_runner.tools

def test_selective_tool_loading_backward_compatibility(tool_runner):
    """Test that the old format for loading all tools from a module still works"""
    # Create a mock module with multiple tools
    mock_module = MagicMock()
    mock_module.TOOLS = [
        {
            'definition': {
                'type': 'function',
                'function': {
                    'name': 'mock_tool_1',
                    'description': 'First mock tool',
                    'parameters': {}
                }
            },
            'implementation': lambda: "mock result 1"
        },
        {
            'definition': {
                'type': 'function',
                'function': {
                    'name': 'mock_tool_2',
                    'description': 'Second mock tool',
                    'parameters': {}
                }
            },
            'implementation': lambda: "mock result 2"
        }
    ]
    
    # Test standard loading with just the module name
    with patch('importlib.import_module', return_value=mock_module):
        # Load all tools using the old format
        loaded_tools = tool_runner.load_tool_module('test')
        
        # Should have loaded all tools
        assert len(loaded_tools) == 2
        
        # Check that all tools were loaded
        tool_names = [tool['function']['name'] for tool in loaded_tools]
        assert 'mock_tool_1' in tool_names
        assert 'mock_tool_2' in tool_names
        
        # Check tools are registered in the tool_runner
        assert 'mock_tool_1' in tool_runner.tools
        assert 'mock_tool_2' in tool_runner.tools 