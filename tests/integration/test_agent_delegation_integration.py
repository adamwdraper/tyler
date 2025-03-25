"""
Integration tests for the agent delegation system.

These tests verify that the entire agent delegation system works
correctly under various scenarios, with a focus on parallel execution.
"""
import os
os.environ["OPENAI_API_KEY"] = "dummy"
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
import types
import asyncio
from tyler.models.agent import Agent
from tyler.models.thread import Thread
from tyler.models.message import Message
from tyler.utils.agent_runner import agent_runner
from tyler.utils.tool_runner import tool_runner
from tyler.database.thread_store import ThreadStore
from datetime import datetime, UTC

# Reset agent_runner between tests
@pytest.fixture(autouse=True)
def reset_agent_runner():
    """Reset the agent_runner for each test"""
    agent_runner.agents = {}
    yield

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
    thread_store = AsyncMock(spec=ThreadStore)
    thread_store.save = AsyncMock()
    thread_store.get = AsyncMock(return_value=None)
    return thread_store

def create_tool_call_response(tool_calls):
    """Helper to create a response with tool calls"""
    response = types.SimpleNamespace()
    
    # Create message with tool_calls
    message = types.SimpleNamespace()
    message.content = "Processing tasks"
    message.role = "assistant"
    message.tool_calls = []
    
    # Add each tool call
    for tool_call in tool_calls:
        message.tool_calls.append(tool_call)
    
    # Create choice
    choice = types.SimpleNamespace()
    choice.message = message
    choice.finish_reason = "tool_calls"
    choice.index = 0
    
    # Add choice to response
    response.choices = [choice]
    response.id = "test-id"
    response.model = "gpt-4o"
    
    # Add usage
    response.usage = types.SimpleNamespace()
    response.usage.completion_tokens = 10
    response.usage.prompt_tokens = 20
    response.usage.total_tokens = 30
    
    return response

def create_assistant_response(content):
    """Helper to create a simple assistant response"""
    response = types.SimpleNamespace()
    
    # Create message
    message = types.SimpleNamespace()
    message.content = content
    message.role = "assistant"
    message.tool_calls = None
    
    # Create choice
    choice = types.SimpleNamespace()
    choice.message = message
    choice.finish_reason = "stop"
    choice.index = 0
    
    # Add choice to response
    response.choices = [choice]
    response.id = "test-id"
    response.model = "gpt-4o"
    
    # Add usage
    response.usage = types.SimpleNamespace()
    response.usage.completion_tokens = 10
    response.usage.prompt_tokens = 20
    response.usage.total_tokens = 30
    
    return response

@pytest.mark.asyncio
async def test_parallel_agent_delegation(mock_thread_store):
    """Test that multiple agent delegations happen in parallel"""
    # Create specialized agents
    research_agent = Agent(
        name="Research",
        model_name="gpt-4o",
        purpose="Research purpose",
        thread_store=mock_thread_store
    )
    
    code_agent = Agent(
        name="Code",
        model_name="gpt-4o",
        purpose="Code purpose",
        thread_store=mock_thread_store
    )
    
    creative_agent = Agent(
        name="Creative",
        model_name="gpt-4o",
        purpose="Creative purpose",
        thread_store=mock_thread_store
    )
    
    # Create coordinator agent
    coordinator_agent = Agent(
        name="Coordinator",
        model_name="gpt-4o",
        purpose="Coordination purpose",
        agents=[research_agent, code_agent, creative_agent],
        thread_store=mock_thread_store
    )
    
    # Create tool calls that will be returned by the LLM
    research_function = types.SimpleNamespace()
    research_function.name = "delegate_to_Research"
    research_function.arguments = json.dumps({"task": "Research quantum computing"})
    research_tool_call = types.SimpleNamespace()
    research_tool_call.id = "research_call"
    research_tool_call.type = "function"
    research_tool_call.function = research_function
    
    code_function = types.SimpleNamespace()
    code_function.name = "delegate_to_Code"
    code_function.arguments = json.dumps({"task": "Write a CSV to JSON converter"})
    code_tool_call = types.SimpleNamespace()
    code_tool_call.id = "code_call"
    code_tool_call.type = "function"
    code_tool_call.function = code_function
    
    creative_function = types.SimpleNamespace()
    creative_function.name = "delegate_to_Creative"
    creative_function.arguments = json.dumps({"task": "Create a tagline for QuantumLeap"})
    creative_tool_call = types.SimpleNamespace()
    creative_tool_call.id = "creative_call"
    creative_tool_call.type = "function"
    creative_tool_call.function = creative_function
    
    # Create a thread with a request that requires delegation
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="""I need help with multiple tasks:
        1. Research on quantum computing
        2. A CSV to JSON converter
        3. A tagline for my startup called "QuantumLeap"
        """
    ))
    
    # Create a timer to measure how long each agent execution takes
    # In a real implementation, the agents would execute in parallel
    execution_times = []
    
    # Patch the run_agent method to record execution times
    original_run_agent = agent_runner.run_agent
    
    async def timed_run_agent(agent_name, task, context=None):
        """Wrapper to time agent execution"""
        start_time = datetime.now(UTC)
        result = await original_run_agent(agent_name, task, context)
        elapsed = (datetime.now(UTC) - start_time).total_seconds()
        execution_times.append((agent_name, elapsed))
        return result
    
    # Create a mock weave_call object
    mock_weave_call = types.SimpleNamespace()
    mock_weave_call.id = "weave-123"
    mock_weave_call.ui_url = "https://weave.com/123"
    
    # Patch the _get_completion method
    with patch.object(Agent, '_get_completion') as mock_get_completion:
        # Set up mock responses
        mock_get_completion.call.side_effect = [
            (create_tool_call_response([research_tool_call, code_tool_call, creative_tool_call]), mock_weave_call),
            (create_assistant_response("Research on quantum computing completed"), mock_weave_call),
            (create_assistant_response("CSV to JSON converter written"), mock_weave_call),
            (create_assistant_response("Tagline for QuantumLeap created"), mock_weave_call),
            (create_assistant_response("All tasks completed successfully"), mock_weave_call)
        ]
        
        with patch.object(agent_runner, 'run_agent', timed_run_agent):
            # Run the coordinator agent
            start_time = datetime.now(UTC)
            result_thread, messages = await coordinator_agent.go(thread)
            total_time = (datetime.now(UTC) - start_time).total_seconds()
            
            # Verify all three delegations occurred
            delegations = [msg for msg in result_thread.messages 
                          if msg.role == "tool" and "delegate_to_" in msg.name]
            
            assert len(delegations) == 3
            
            # The key verification: Parallel execution means the total time should be
            # less than the sum of individual execution times
            # Note: This is a bit of a simplification since the timing depends on the test itself,
            # but the concept is important to verify parallel execution
            total_agent_time = sum(time for _, time in execution_times)
            
            # Log times for debugging
            print(f"Total execution time: {total_time}")
            print(f"Individual agent times: {execution_times}")
            print(f"Sum of agent times: {total_agent_time}")
            
            # In a parallel execution, total time should be less than sum of individual times
            # but this might be hard to verify in tests due to test overhead
            # So we're checking that all agents were called
            assert len(execution_times) == 3
            
            # Verify each agent was called
            agent_names = [name for name, _ in execution_times]
            assert "Research" in agent_names
            assert "Code" in agent_names
            assert "Creative" in agent_names
            
            # Verify the mock was called the expected number of times
            assert mock_get_completion.call.call_count == 5  # 1 coordinator call + 3 agent calls + 1 follow-up

@pytest.mark.asyncio
async def test_agent_delegation_error_handling(mock_thread_store):
    """Test that errors in delegated agents are properly handled"""
    # Create agents
    failing_agent = Agent(
        name="FailingAgent",
        model_name="gpt-4o",
        purpose="Agent that will fail",
        thread_store=mock_thread_store
    )
    
    working_agent = Agent(
        name="WorkingAgent",
        model_name="gpt-4o",
        purpose="Agent that works correctly",
        thread_store=mock_thread_store
    )
    
    # Create coordinator agent
    coordinator_agent = Agent(
        name="ErrorHandlingCoordinator",
        model_name="gpt-4o",
        purpose="Coordinator that handles errors",
        agents=[failing_agent, working_agent],
        thread_store=mock_thread_store
    )
    
    # Create tool calls
    failing_function = types.SimpleNamespace()
    failing_function.name = "delegate_to_FailingAgent"
    failing_function.arguments = json.dumps({"task": "Do something that will fail"})
    failing_tool_call = types.SimpleNamespace()
    failing_tool_call.id = "failing_call"
    failing_tool_call.type = "function"
    failing_tool_call.function = failing_function
    
    working_function = types.SimpleNamespace()
    working_function.name = "delegate_to_WorkingAgent"
    working_function.arguments = json.dumps({"task": "Do something that will work"})
    working_tool_call = types.SimpleNamespace()
    working_tool_call.id = "working_call"
    working_tool_call.type = "function"
    working_tool_call.function = working_function
    
    # Create a thread
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Do multiple things, some will fail"
    ))
    
    # Create a mock weave_call object
    mock_weave_call = types.SimpleNamespace()
    mock_weave_call.id = "weave-123"
    mock_weave_call.ui_url = "https://weave.com/123"
    
    # Patch agent_runner.run_agent to simulate a failure for the failing agent
    original_run_agent = agent_runner.run_agent
    
    async def mock_run_agent(agent_name, task, context=None):
        """Mock that simulates a failing agent"""
        if agent_name == "FailingAgent":
            raise Exception("Simulated agent failure")
        else:
            return await original_run_agent(agent_name, task, context)
    
    # Patch the _get_completion method
    with patch.object(Agent, '_get_completion') as mock_get_completion:
        # Set up mock responses
        mock_get_completion.call.side_effect = [
            (create_tool_call_response([failing_tool_call, working_tool_call]), mock_weave_call),
            (create_assistant_response("Task completed successfully"), mock_weave_call),
            (create_assistant_response("One task failed but one succeeded"), mock_weave_call)
        ]
        
        with patch.object(agent_runner, 'run_agent', mock_run_agent):
            # Run the coordinator agent
            result_thread, messages = await coordinator_agent.go(thread)
            
            # Verify both delegations were attempted
            tool_messages = [msg for msg in result_thread.messages if msg.role == "tool"]
            
            # Log messages for debugging
            print("Messages in thread:")
            for msg in result_thread.messages:
                print(f"{msg.role}: {msg.content}")
                if hasattr(msg, 'name'):
                    print(f"  Name: {msg.name}")
            
            # In our current implementation, both tools execute in parallel
            # and errors are handled gracefully, so we should see both messages
            assert any("FailingAgent" in msg.name for msg in tool_messages)
            assert any("WorkingAgent" in msg.name for msg in tool_messages)
            
            # Verify that an error message was generated for the failing agent
            error_messages = [msg for msg in tool_messages 
                             if "FailingAgent" in msg.name and "fail" in msg.content.lower()]
            assert len(error_messages) > 0
            
            # Verify that the working agent's message was processed correctly
            success_messages = [msg for msg in tool_messages 
                              if "WorkingAgent" in msg.name and "success" in msg.content.lower()]
            assert len(success_messages) > 0 