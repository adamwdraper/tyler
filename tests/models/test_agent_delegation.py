"""
Tests for the agent delegation functionality.

This file tests the delegation of tasks from one agent to another,
focusing on the new direct delegation approach without registries.
"""
import os
os.environ["OPENAI_API_KEY"] = "dummy"
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call
import json
from tyler import Agent, Thread, Message, ThreadStore
from tyler.utils.tool_runner import tool_runner
import types
import asyncio

# Reset tool_runner between tests
@pytest.fixture(autouse=True)
def reset_tool_runner():
    """Reset registered tools for each test"""
    orig_tools = tool_runner.tools.copy()
    orig_attributes = tool_runner.tool_attributes.copy()
    tool_runner.tools = {}
    tool_runner.tool_attributes = {}
    yield
    tool_runner.tools = orig_tools
    tool_runner.tool_attributes = orig_attributes

@pytest.fixture
def mock_thread_store():
    """Mock thread store"""
    thread_store = MagicMock(spec=ThreadStore)
    thread_store.save = AsyncMock()
    thread_store.get = AsyncMock(return_value=None)
    return thread_store

@pytest.fixture
def mock_litellm():
    """Mock litellm to prevent real API calls"""
    with patch('litellm.acompletion', autospec=True) as mock:
        yield mock

@pytest.fixture
def thread():
    """Create a thread for testing"""
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Test message"
    ))
    return thread

@pytest.mark.asyncio
async def test_agent_delegation_tools_created():
    """Test that delegation tools are created for child agents"""
    # Create an agent with a child
    child_agent = Agent(
        name="ResearchAgent",
        model_name="gpt-4.1",
        purpose="Research agent purpose"
    )
    
    parent_agent = Agent(
        name="ParentAgent",
        model_name="gpt-4.1",
        purpose="Parent agent purpose",
        agents=[child_agent]
    )
    
    # Verify delegation tool was created
    tool_name = f"delegate_to_{child_agent.name}"
    assert tool_name in tool_runner.tools
    
    # Verify tool definition was added to parent's tools
    tool_names = [t.get('function', {}).get('name') for t in parent_agent._processed_tools if 'function' in t]
    assert tool_name in tool_names

@pytest.mark.asyncio
async def test_multiple_child_agents():
    """Test creating delegation tools for multiple child agents"""
    # Create multiple child agents
    research_agent = Agent(
        name="Research",
        model_name="gpt-4.1",
        purpose="Research purpose"
    )
    
    code_agent = Agent(
        name="Code",
        model_name="gpt-4.1",
        purpose="Code purpose"
    )
    
    creative_agent = Agent(
        name="Creative",
        model_name="gpt-4.1",
        purpose="Creative purpose"
    )
    
    # Create parent agent with multiple children
    parent_agent = Agent(
        name="Coordinator",
        model_name="gpt-4.1",
        purpose="Coordinator purpose",
        agents=[research_agent, code_agent, creative_agent]
    )
    
    # Verify delegation tools were created for all children
    assert "delegate_to_Research" in tool_runner.tools
    assert "delegate_to_Code" in tool_runner.tools
    assert "delegate_to_Creative" in tool_runner.tools
    
    # Verify parent agent has delegation tools in processed tools
    tool_names = [t.get('function', {}).get('name') for t in parent_agent._processed_tools if 'function' in t]
    assert "delegate_to_Research" in tool_names
    assert "delegate_to_Code" in tool_names
    assert "delegate_to_Creative" in tool_names

@pytest.mark.asyncio
async def test_agent_delegation_tool_call(mock_litellm, mock_thread_store):
    """Test that an agent can delegate to another agent via tool call"""
    # Create child agent
    child_agent = Agent(
        name="SpecialistAgent",
        model_name="gpt-4.1",
        purpose="Specialist purpose",
        thread_store=mock_thread_store
    )
    
    # Create parent agent
    parent_agent = Agent(
        name="MainAgent",
        model_name="gpt-4.1",
        purpose="Main purpose",
        agents=[child_agent],
        thread_store=mock_thread_store
    )
    
    # Create response objects
    tool_response = types.SimpleNamespace()
    message = types.SimpleNamespace()
    function = types.SimpleNamespace()
    function.name = f"delegate_to_{child_agent.name}"
    function.arguments = json.dumps({"task": "Do specialized work"})
    
    tool_call = types.SimpleNamespace()
    tool_call.id = "call_123"
    tool_call.type = "function"
    tool_call.function = function
    
    message.content = "I'll delegate this to the specialist"
    message.tool_calls = [tool_call]
    
    choice = types.SimpleNamespace()
    choice.message = message
    
    tool_response.choices = [choice]
    
    # Child agent response
    child_response = types.SimpleNamespace()
    child_message = types.SimpleNamespace()
    child_message.content = "I completed the specialized task"
    child_message.tool_calls = None
    child_choice = types.SimpleNamespace()
    child_choice.message = child_message
    child_response.choices = [child_choice]
    
    # Final response
    final_response = types.SimpleNamespace()
    final_message = types.SimpleNamespace()
    final_message.content = "Great, the task is complete"
    final_message.tool_calls = None
    final_choice = types.SimpleNamespace()
    final_choice.message = final_message
    final_response.choices = [final_choice]
    
    # Mock weave_call for metrics
    mock_weave_call = types.SimpleNamespace()
    mock_weave_call.id = "weave-123"
    mock_weave_call.ui_url = "https://weave.com/123"
    
    # Patch _get_completion method instead of relying on mock_litellm only
    with patch.object(Agent, '_get_completion') as mock_get_completion:
        # Set up the side effect sequence
        mock_get_completion.call.side_effect = [
            (tool_response, mock_weave_call),  # Parent delegates
            (child_response, mock_weave_call),  # Child completes
            (final_response, mock_weave_call)   # Parent acknowledges
        ]
        
        # Mock the tool execution
        async def mock_tool_execution(tool_call):
            """Mock the execution of the delegation tool"""
            return "Specialized task completed successfully"
        
        with patch.object(tool_runner, 'execute_tool_call', mock_tool_execution):
            # Create a thread
            thread = Thread()
            thread.add_message(Message(
                role="user",
                content="I need help with a specialized task"
            ))
            
            # Execute parent agent
            result_thread, messages = await parent_agent.go(thread)
            
            # Check that the thread contains the delegation and response
            assert any("I'll delegate this to the specialist" in m.content for m in result_thread.messages if m.role == "assistant")
            assert any("Specialized task completed successfully" in m.content for m in result_thread.messages if m.role == "tool")
            
            # Verify the mock was called the expected number of times
            assert mock_get_completion.call.call_count >= 1

@pytest.mark.asyncio
async def test_delegation_with_context(mock_litellm, mock_thread_store):
    """Test delegation with context passed to the child agent"""
    # Create child agent
    child_agent = Agent(
        name="ContextAwareAgent",
        model_name="gpt-4.1",
        purpose="Context-aware purpose",
        thread_store=mock_thread_store
    )
    
    # Create parent agent
    parent_agent = Agent(
        name="ContextProviderAgent",
        model_name="gpt-4.1",
        purpose="Context provider purpose",
        agents=[child_agent],
        thread_store=mock_thread_store
    )
    
    # Create parent response with context
    parent_response = types.SimpleNamespace()
    parent_message = types.SimpleNamespace()
    parent_function = types.SimpleNamespace()
    parent_function.name = f"delegate_to_{child_agent.name}"
    parent_function.arguments = json.dumps({
        "task": "Process data with context",
        "context": {
            "data_source": "database",
            "importance": "high",
            "deadline": "tomorrow"
        }
    })
    
    parent_tool_call = types.SimpleNamespace()
    parent_tool_call.id = "call_123"
    parent_tool_call.type = "function"
    parent_tool_call.function = parent_function
    
    parent_message.content = "Delegating with context"
    parent_message.tool_calls = [parent_tool_call]
    
    parent_choice = types.SimpleNamespace()
    parent_choice.message = parent_message
    
    parent_response.choices = [parent_choice]
    
    # Child agent response
    child_response = types.SimpleNamespace()
    child_message = types.SimpleNamespace()
    child_message.content = "I processed the data using the context provided"
    child_message.tool_calls = None
    
    child_choice = types.SimpleNamespace()
    child_choice.message = child_message
    
    child_response.choices = [child_choice]
    
    # Final response
    final_response = types.SimpleNamespace()
    final_message = types.SimpleNamespace()
    final_message.content = "Great, data processed"
    final_message.tool_calls = None
    final_choice = types.SimpleNamespace()
    final_choice.message = final_message
    final_response.choices = [final_choice]
    
    # Mock weave_call for metrics
    mock_weave_call = types.SimpleNamespace()
    mock_weave_call.id = "weave-123"
    mock_weave_call.ui_url = "https://weave.com/123"
    
    # Patch _get_completion method
    with patch.object(Agent, '_get_completion') as mock_get_completion:
        # Set up the side effect sequence
        mock_get_completion.call.side_effect = [
            (parent_response, mock_weave_call),  # Parent delegates with context
            (child_response, mock_weave_call),   # Child processes with context
            (final_response, mock_weave_call)    # Parent acknowledges
        ]
        
        # Mock the tool execution
        async def mock_tool_execution(tool_call):
            """Mock the execution of the delegation tool"""
            return "Data processed with context successfully"
        
        with patch.object(tool_runner, 'execute_tool_call', mock_tool_execution):
            # Create a thread
            thread = Thread()
            thread.add_message(Message(
                role="user",
                content="Process this data with the appropriate context"
            ))
            
            # Execute parent agent
            result_thread, messages = await parent_agent.go(thread)
            
            # Verify delegation occurred
            assert any("Delegating with context" in m.content for m in result_thread.messages if m.role == "assistant")
            assert any("Data processed with context successfully" in m.content for m in result_thread.messages if m.role == "tool")
            
            # Verify the mock was called the expected number of times
            assert mock_get_completion.call.call_count >= 1

@pytest.mark.asyncio
async def test_nested_agent_delegation(mock_litellm, mock_thread_store):
    """Test nested delegation where a child agent delegates to a grandchild"""
    # Create three-level agent hierarchy
    grandchild_agent = Agent(
        name="GrandchildAgent",
        model_name="gpt-4.1",
        purpose="Grandchild purpose",
        thread_store=mock_thread_store
    )
    
    child_agent = Agent(
        name="ChildAgent",
        model_name="gpt-4.1",
        purpose="Child purpose",
        agents=[grandchild_agent],
        thread_store=mock_thread_store
    )
    
    parent_agent = Agent(
        name="ParentAgent",
        model_name="gpt-4.1",
        purpose="Parent purpose",
        agents=[child_agent],
        thread_store=mock_thread_store
    )
    
    # Set up mock responses for delegation chain
    # Parent agent delegates to child
    parent_response = types.SimpleNamespace()
    parent_message = types.SimpleNamespace()
    parent_function = types.SimpleNamespace()
    parent_function.name = "delegate_to_ChildAgent"
    parent_function.arguments = json.dumps({"task": "Handle this complex task"})
    parent_tool_call = types.SimpleNamespace()
    parent_tool_call.id = "parent_call"
    parent_tool_call.type = "function"
    parent_tool_call.function = parent_function
    parent_message.content = "I'll delegate to the child agent"
    parent_message.tool_calls = [parent_tool_call]
    parent_choice = types.SimpleNamespace()
    parent_choice.message = parent_message
    parent_response.choices = [parent_choice]
    
    # Child agent delegates to grandchild
    child_response = types.SimpleNamespace()
    child_message = types.SimpleNamespace()
    child_function = types.SimpleNamespace()
    child_function.name = "delegate_to_GrandchildAgent"
    child_function.arguments = json.dumps({"task": "Execute specialized subtask"})
    child_tool_call = types.SimpleNamespace()
    child_tool_call.id = "child_call"
    child_tool_call.type = "function"
    child_tool_call.function = child_function
    child_message.content = "Delegating to the grandchild specialist"
    child_message.tool_calls = [child_tool_call]
    child_choice = types.SimpleNamespace()
    child_choice.message = child_message
    child_response.choices = [child_choice]
    
    # Grandchild completes the task
    grandchild_response = types.SimpleNamespace()
    grandchild_message = types.SimpleNamespace()
    grandchild_message.content = "Task completed by grandchild"
    grandchild_message.tool_calls = None
    grandchild_choice = types.SimpleNamespace()
    grandchild_choice.message = grandchild_message
    grandchild_response.choices = [grandchild_choice]
    
    # Set up follow-up responses
    follow_up_response = types.SimpleNamespace()
    follow_up_message = types.SimpleNamespace()
    follow_up_message.content = "Acknowledging completion"
    follow_up_message.tool_calls = None
    follow_up_choice = types.SimpleNamespace()
    follow_up_choice.message = follow_up_message
    follow_up_response.choices = [follow_up_choice]
    
    # Mock weave_call for metrics
    mock_weave_call = types.SimpleNamespace()
    mock_weave_call.id = "weave-123"
    mock_weave_call.ui_url = "https://weave.com/123"
    
    # Mock the _get_completion method
    with patch.object(Agent, '_get_completion') as mock_get_completion:
        # Set up the side effect sequence
        mock_get_completion.call.side_effect = [
            (parent_response, mock_weave_call),      # Parent delegates to child
            (child_response, mock_weave_call),       # Child delegates to grandchild
            (grandchild_response, mock_weave_call),  # Grandchild completes task
            (follow_up_response, mock_weave_call),   # Child acknowledges completion
            (follow_up_response, mock_weave_call)    # Parent acknowledges completion
        ]
        
        # Mock the tool execution
        async def mock_tool_execution(tool_call):
            """Mock the execution of the delegation tool"""
            return "Task completed successfully"
        
        with patch.object(tool_runner, 'execute_tool_call', mock_tool_execution):
            # Create a thread
            thread = Thread()
            thread.add_message(Message(
                role="user",
                content="Execute this complex multi-level task"
            ))
            
            # Execute parent agent
            result_thread, messages = await parent_agent.go(thread)
            
            # Verify delegation chain occurred
            assert any("I'll delegate to the child agent" in m.content for m in result_thread.messages if m.role == "assistant")
            assert any("delegate_to_ChildAgent" in m.name for m in result_thread.messages if m.role == "tool")
            assert any("Task completed successfully" in m.content for m in result_thread.messages if m.role == "tool")
            
            # Verify the mock was called the expected number of times
            assert mock_get_completion.call.call_count >= 1 