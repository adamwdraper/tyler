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
    mock_module.TEST_TOOLS = [
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
    assert result['tool_call_id'] == 'test_id'
    assert result['name'] == 'test_tool'
    assert result['content'] == 'Result: test'

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
    assert result['tool_call_id'] == 'test_id'
    assert result['name'] == 'test_async_tool'
    assert result['content'] == 'Async Result: test'

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
    
    # Verify the result
    assert result['tool_call_id'] == 'test_interrupt_id'
    assert result['name'] == 'test_interrupt_tool'
    
    # Parse the content as JSON and verify
    content = json.loads(result['content'])
    assert content['type'] == 'interrupt_detected'
    assert content['message'] == 'Test interrupt'
    assert content['severity'] == 'high'

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
    
    # Verify the result
    assert result['tool_call_id'] == 'async_interrupt_id'
    assert result['name'] == 'async_interrupt_tool'
    
    # Parse the content and verify
    content = json.loads(result['content'])
    assert content['type'] == 'async_interrupt'
    assert content['message'] == 'Async interrupt'
    assert content['severity'] == 'medium'

def test_load_interrupt_tool_module(tool_runner):
    """Test loading interrupt tools from a module"""
    # Create a mock module with an interrupt tool
    mock_module = MagicMock()
    mock_module.TEST_TOOLS = [
        {
            'definition': {
                'type': 'function',
                'function': {
                    'name': 'mock_interrupt_tool',
                    'description': 'A mock interrupt tool',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'message': {'type': 'string'}
                        },
                        'required': ['message']
                    }
                }
            },
            'implementation': lambda message: json.dumps({'message': message}),
            'attributes': {
                'type': 'interrupt'
            }
        }
    ]
    
    with patch('importlib.import_module', return_value=mock_module):
        loaded_tools = tool_runner.load_tool_module('test')
        
        # Verify the tool was loaded correctly
        assert len(loaded_tools) == 1
        assert loaded_tools[0]['function']['name'] == 'mock_interrupt_tool'
        assert 'mock_interrupt_tool' in tool_runner.tools
        
        # Verify interrupt attributes were preserved
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
        loaded_tools = tool_runner.load_tool_module('test')
        assert len(loaded_tools) == 0 

@pytest.mark.asyncio
async def test_execute_tool_call_error_propagation(tool_runner):
    """Test that execute_tool_call properly propagates errors from both sync and async tools"""
    # Define tools that raise errors
    def sync_error_tool():
        raise ValueError("Sync tool error")
        
    async def async_error_tool():
        await asyncio.sleep(0.1)
        raise ValueError("Async tool error")
    
    # Register both tools
    tool_runner.register_tool('sync_error_tool', sync_error_tool)
    tool_runner.register_tool('async_error_tool', async_error_tool)
    
    # Test sync tool error
    sync_tool_call = MagicMock()
    sync_tool_call.id = 'sync_error_id'
    sync_tool_call.function.name = 'sync_error_tool'
    sync_tool_call.function.arguments = '{}'
    
    with pytest.raises(ValueError) as exc_info:
        await tool_runner.execute_tool_call(sync_tool_call)
    assert "Error executing tool 'sync_error_tool': Sync tool error" in str(exc_info.value)
    
    # Test async tool error
    async_tool_call = MagicMock()
    async_tool_call.id = 'async_error_id'
    async_tool_call.function.name = 'async_error_tool'
    async_tool_call.function.arguments = '{}'
    
    with pytest.raises(ValueError) as exc_info:
        await tool_runner.execute_tool_call(async_tool_call)
    assert "Error executing tool 'async_error_tool': Async tool error" in str(exc_info.value) 