import pytest
from utils.tool_runner import ToolRunner
from pathlib import Path
import os
from unittest.mock import patch

@pytest.fixture
def tool_runner():
    return ToolRunner()

def test_tool_loading(tool_runner):
    """Test that tools are properly loaded from the tools directory"""
    # Check that we have some tools loaded
    assert len(tool_runner.tools) > 0
    
    # Verify that common tools are loaded
    assert "command_line-run_command" in tool_runner.tools
    assert "notion-search" in tool_runner.tools
    assert "notion-get_page" in tool_runner.tools

def test_list_tools(tool_runner):
    """Test listing available tools"""
    tools = tool_runner.list_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0
    assert "command_line-run_command" in tools
    assert "notion-search" in tools

def test_get_tool_description(tool_runner):
    """Test getting tool descriptions"""
    # Test valid tool
    desc = tool_runner.get_tool_description("command_line-run_command")
    assert isinstance(desc, str)
    assert "Executes whitelisted command" in desc
    
    # Test invalid tool
    desc = tool_runner.get_tool_description("nonexistent-tool")
    assert desc is None

def test_get_tool_parameters(tool_runner):
    """Test getting tool parameter schemas"""
    # Test valid tool
    params = tool_runner.get_tool_parameters("command_line-run_command")
    assert isinstance(params, dict)
    assert "properties" in params
    assert "command" in params["properties"]
    
    # Test invalid tool
    params = tool_runner.get_tool_parameters("nonexistent-tool")
    assert params is None

def test_run_command_line_tool(tool_runner):
    """Test running a command line tool"""
    result = tool_runner.run_tool("command_line-run_command", {
        "command": "echo 'test'",
        "working_dir": "."
    })
    
    assert isinstance(result, dict)
    assert "error" not in result or not result["error"]
    assert "output" in result
    assert "test" in result["output"]
    assert result["exit_code"] == 0

def test_run_tool_with_invalid_name(tool_runner):
    """Test running a nonexistent tool"""
    with pytest.raises(ValueError) as exc_info:
        tool_runner.run_tool("nonexistent-tool", {})
    assert "Tool 'nonexistent-tool' not found" in str(exc_info.value)

def test_run_tool_with_invalid_parameters(tool_runner):
    """Test running a tool with invalid parameters"""
    with pytest.raises(ValueError) as exc_info:
        tool_runner.run_tool("command_line-run_command", {
            "invalid_param": "value"
        })
    assert "Error executing tool" in str(exc_info.value)

def test_run_tool_with_unsafe_command(tool_runner):
    """Test running command line tool with unsafe command"""
    result = tool_runner.run_tool("command_line-run_command", {
        "command": "rm -rf /"
    })
    
    assert isinstance(result, dict)
    assert "error" in result
    assert "Command not allowed" in result["error"]

@patch('requests.post')
def test_run_notion_search_tool(mock_post, tool_runner):
    """Test running Notion search tool with mocked API response"""
    # Mock successful API response
    mock_response = type('Response', (), {
        'raise_for_status': lambda: None,
        'json': lambda: {'results': [{'id': '123', 'title': 'Test Page'}]}
    })
    mock_post.return_value = mock_response

    result = tool_runner.run_tool("notion-search", {
        "query": "test",
        "page_size": 1
    })
    
    assert isinstance(result, dict)
    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0]["id"] == "123"
    mock_post.assert_called_once()

@patch('requests.get')
def test_run_notion_get_page_tool(mock_get, tool_runner):
    """Test running Notion get_page tool with mocked API response"""
    # Mock successful API response
    mock_response = type('Response', (), {
        'raise_for_status': lambda: None,
        'json': lambda: {'id': '123', 'properties': {'title': 'Test Page'}}
    })
    mock_get.return_value = mock_response

    result = tool_runner.run_tool("notion-get_page", {
        "page_id": "123"
    })
    
    assert isinstance(result, dict)
    assert "id" in result
    assert result["id"] == "123"
    mock_get.assert_called_once()

@patch('requests.post')
def test_run_notion_tool_error(mock_post, tool_runner):
    """Test handling of Notion API errors"""
    # Mock error response
    def raise_error():
        raise Exception("API Error")
    
    mock_response = type('Response', (), {
        'raise_for_status': raise_error,
        'json': lambda: {'error': 'API Error'}
    })
    mock_post.return_value = mock_response

    with pytest.raises(ValueError) as exc_info:
        tool_runner.run_tool("notion-search", {
            "query": "test",
            "page_size": 1
        })
    assert "Error executing tool" in str(exc_info.value)

def test_tool_path_resolution(tool_runner):
    """Test that tool paths are properly resolved"""
    tools_dir = Path(tool_runner.tools["command_line-run_command"]["module"].__file__).parent
    assert tools_dir.name == "tools"
    assert (tools_dir / "command_line.py").exists()
    assert (tools_dir / "notion.py").exists()

def test_tool_definition_structure(tool_runner):
    """Test that tool definitions have the expected structure"""
    tool = tool_runner.tools["command_line-run_command"]
    
    assert "module" in tool
    assert "definition" in tool
    assert "name" in tool["definition"]
    assert "description" in tool["definition"]
    assert "parameters" in tool["definition"] 