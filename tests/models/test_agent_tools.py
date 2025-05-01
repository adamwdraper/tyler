import pytest
from tyler import Agent
from tyler.tools import TOOL_MODULES, TOOLS
from tyler.utils.tool_runner import tool_runner

@pytest.mark.asyncio
async def test_agent_loads_individual_tools():
    """Test that agent correctly loads tools when specifying individual modules"""
    # Test loading just web tools
    agent_web = Agent(
        model_name="gpt-4o",
        purpose="test",
        tools=["web"]
    )
    # Verify web tools are loaded
    web_tool_names = {tool['definition']['function']['name'] for tool in TOOL_MODULES['web']}
    agent_web_tools = {tool['function']['name'] for tool in agent_web._processed_tools}
    assert web_tool_names == agent_web_tools, f"Expected {web_tool_names}, got {agent_web_tools}"
    
    # Test loading just slack tools
    agent_slack = Agent(
        model_name="gpt-4o",
        purpose="test",
        tools=["slack"]
    )
    # Verify slack tools are loaded
    slack_tool_names = {tool['definition']['function']['name'] for tool in TOOL_MODULES['slack']}
    agent_slack_tools = {tool['function']['name'] for tool in agent_slack._processed_tools}
    assert slack_tool_names == agent_slack_tools, f"Expected {slack_tool_names}, got {agent_slack_tools}"

@pytest.mark.asyncio
async def test_agent_loads_multiple_tool_modules():
    """Test that agent correctly loads tools when specifying multiple modules"""
    agent = Agent(
        model_name="gpt-4o",
        purpose="test",
        tools=["web", "slack"]
    )
    
    # Get expected tools from both modules
    expected_tools = set()
    for module in ["web", "slack"]:
        module_tools = {tool['definition']['function']['name'] for tool in TOOL_MODULES[module]}
        expected_tools.update(module_tools)
    
    # Get actual tools loaded in agent
    agent_tools = {tool['function']['name'] for tool in agent._processed_tools}
    
    assert expected_tools == agent_tools, f"Expected {expected_tools}, got {agent_tools}"

@pytest.mark.asyncio
async def test_agent_loads_no_tools_by_default():
    """Test that agent loads no tools when none are specified"""
    agent = Agent(
        model_name="gpt-4o",
        purpose="test"
    )
    
    assert len(agent._processed_tools) == 0, "Expected no tools to be loaded by default"

@pytest.mark.asyncio
async def test_agent_tool_functionality():
    """Test that loaded tools are actually functional"""
    agent = Agent(
        model_name="gpt-4o",
        purpose="test",
        tools=["web"]
    )
    
    # Verify web tools exist in processed tools
    web_tools = [tool for tool in agent._processed_tools if tool['function']['name'].startswith('web-')]
    assert len(web_tools) > 0, "No web tools were loaded"
    
    # Verify the tools are properly registered in the global tool runner
    for tool in web_tools:
        tool_name = tool['function']['name']
        assert tool_name in tool_runner.tools, f"Tool {tool_name} not registered in tool runner"

@pytest.mark.asyncio
async def test_agent_with_custom_tool():
    """Test that agent correctly loads and registers custom tools"""
    # Define a custom tool
    custom_tool = {
        "definition": {
            "function": {
                "name": "custom-test-tool",
                "description": "A test custom tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param": {
                            "type": "string",
                            "description": "A test parameter"
                        }
                    },
                    "required": ["param"]
                }
            }
        },
        "implementation": lambda params: {"content": f"Custom tool executed with param: {params['param']}"},
        "attributes": {
            "type": "utility",
            "category": "test"
        }
    }
    
    # Create agent with custom tool
    agent = Agent(
        model_name="gpt-4o",
        purpose="test",
        tools=[custom_tool]
    )
    
    # Verify custom tool is loaded
    custom_tools = [tool for tool in agent._processed_tools if tool['function']['name'] == "custom-test-tool"]
    assert len(custom_tools) == 1
    
    # Verify tool is registered in tool runner
    assert "custom-test-tool" in tool_runner.tools
    
    # Verify tool attributes are registered
    attributes = tool_runner.get_tool_attributes("custom-test-tool")
    assert attributes == {"type": "utility", "category": "test"}

@pytest.mark.asyncio
async def test_agent_with_invalid_tool_type():
    """Test that agent raises error for invalid tool type"""
    # Try to create agent with invalid tool type (not string or dict)
    with pytest.raises(ValueError) as excinfo:
        Agent(
            model_name="gpt-4o",
            purpose="test",
            tools=[123]  # Invalid tool type
        )
    
    # Check that the error message contains information about invalid type
    assert "Invalid tool type" in str(excinfo.value) or "type" in str(excinfo.value)

@pytest.mark.asyncio
async def test_agent_with_missing_tool_module():
    """Test that agent raises error for missing tool module"""
    # Try to create agent with non-existent tool module
    with pytest.raises(ValueError) as excinfo:
        Agent(
            model_name="gpt-4o",
            purpose="test",
            tools=["non_existent_module"]  # Non-existent module
        )
    
    # Check that the error message contains information about the missing module
    assert "non_existent_module" in str(excinfo.value)

@pytest.mark.asyncio
async def test_agent_with_custom_tool_missing_keys():
    """Test that agent raises error for custom tool with missing keys"""
    # Define an invalid custom tool missing implementation
    invalid_tool = {
        "definition": {
            "function": {
                "name": "invalid-tool",
                "description": "An invalid tool",
                "parameters": {}
            }
        }
        # Missing implementation key
    }
    
    # Try to create agent with invalid tool
    with pytest.raises(ValueError, match="Custom tools must have 'definition' and 'implementation' keys"):
        Agent(
            model_name="gpt-4o",
            purpose="test",
            tools=[invalid_tool]
        )

@pytest.mark.asyncio
async def test_agent_with_multiple_custom_tools():
    """Test that agent correctly loads multiple custom tools"""
    # Define custom tools
    custom_tool1 = {
        "definition": {
            "function": {
                "name": "custom-tool-1",
                "description": "First custom tool",
                "parameters": {}
            }
        },
        "implementation": lambda params: {"content": "Custom tool 1 executed"}
    }
    
    custom_tool2 = {
        "definition": {
            "function": {
                "name": "custom-tool-2",
                "description": "Second custom tool",
                "parameters": {}
            }
        },
        "implementation": lambda params: {"content": "Custom tool 2 executed"}
    }
    
    # Create agent with multiple custom tools
    agent = Agent(
        model_name="gpt-4o",
        purpose="test",
        tools=[custom_tool1, custom_tool2]
    )
    
    # Verify both tools are loaded
    tool_names = [tool['function']['name'] for tool in agent._processed_tools]
    assert "custom-tool-1" in tool_names
    assert "custom-tool-2" in tool_names
    
    # Verify both tools are registered in tool runner
    assert "custom-tool-1" in tool_runner.tools
    assert "custom-tool-2" in tool_runner.tools

@pytest.mark.asyncio
async def test_agent_with_mixed_tools():
    """Test that agent correctly loads both built-in and custom tools"""
    # Define a custom tool
    custom_tool = {
        "definition": {
            "function": {
                "name": "custom-mixed-tool",
                "description": "A custom tool in mixed setup",
                "parameters": {}
            }
        },
        "implementation": lambda params: {"content": "Custom mixed tool executed"}
    }
    
    # Create agent with both built-in and custom tools
    agent = Agent(
        model_name="gpt-4o",
        purpose="test",
        tools=["web", custom_tool]  # Mix of string and dict
    )
    
    # Get all tool names
    tool_names = [tool['function']['name'] for tool in agent._processed_tools]
    
    # Verify custom tool is loaded
    assert "custom-mixed-tool" in tool_names
    
    # Verify web tools are loaded
    web_tool_names = {tool['definition']['function']['name'] for tool in TOOL_MODULES['web']}
    for name in web_tool_names:
        assert name in tool_names 

@pytest.mark.asyncio
async def test_agent_with_selective_tools():
    """Test that agent correctly loads selective tools using the 'module:tool1,tool2' format"""
    # Verify there are multiple tools in the 'web' module to test with
    web_tools = TOOL_MODULES['web']
    assert len(web_tools) >= 2, "Need at least 2 web tools for this test"
    
    # Get the names of the first two web tools for our selective loading test
    first_tool = web_tools[0]['definition']['function']['name']
    second_tool = web_tools[1]['definition']['function']['name']
    
    # Create agent with only specific web tools
    agent = Agent(
        model_name="gpt-4o",
        purpose="test",
        tools=[f"web:{first_tool},{second_tool}"]  # Only select specific tools
    )
    
    # Get all loaded tool names
    tool_names = {tool['function']['name'] for tool in agent._processed_tools}
    
    # Should have loaded exactly the specified tools
    assert len(tool_names) == 2, f"Expected 2 tools, got {len(tool_names)}: {tool_names}"
    assert first_tool in tool_names, f"Tool {first_tool} should be loaded"
    assert second_tool in tool_names, f"Tool {second_tool} should be loaded"
    
    # Verify no other web tools were loaded
    for tool in web_tools[2:]:  # Skip the first two we explicitly included
        tool_name = tool['definition']['function']['name']
        assert tool_name not in tool_names, f"Tool {tool_name} should not be loaded"

@pytest.mark.asyncio
async def test_agent_with_mixed_selective_tools():
    """Test that agent correctly processes mixed selective and full module loading"""
    # Create agent with a mix of selective tools and full modules
    agent = Agent(
        model_name="gpt-4o",
        purpose="test",
        tools=[
            "web",  # All web tools
            "slack:slack-post_message"  # Only specific slack tool
        ]
    )
    
    # Get all loaded tool names
    tool_names = {tool['function']['name'] for tool in agent._processed_tools}
    
    # All web tools should be loaded
    web_tool_names = {tool['definition']['function']['name'] for tool in TOOL_MODULES['web']}
    for name in web_tool_names:
        assert name in tool_names, f"Web tool {name} should be loaded"
    
    # Only specified slack tool should be loaded
    slack_tool_names = {tool['definition']['function']['name'] for tool in TOOL_MODULES['slack']}
    for name in slack_tool_names:
        if name == "slack-post_message":
            assert name in tool_names, f"Slack tool {name} should be loaded"
        else:
            assert name not in tool_names, f"Slack tool {name} should not be loaded" 