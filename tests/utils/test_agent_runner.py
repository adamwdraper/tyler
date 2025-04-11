"""
Tests for the AgentRunner class.

This file tests the agent runner functionality, including registration,
listing, retrieval, and execution of agents.
"""
import os
os.environ["OPENAI_API_KEY"] = "dummy"
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from tyler.utils.agent_runner import AgentRunner, agent_runner
from tyler.models.agent import Agent
from tyler.models.thread import Thread
from tyler.models.message import Message

@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.name = "test_agent"
    agent.go = AsyncMock(return_value=(Thread(), [
        Message(role="assistant", content="Mock agent response")
    ]))
    return agent

@pytest.fixture
def agent_runner_instance():
    # Create a fresh instance for each test
    return AgentRunner()

@pytest.mark.asyncio
async def test_register_agent(agent_runner_instance, mock_agent):
    """Test registering an agent with the agent runner"""
    # Register the agent
    agent_runner_instance.register_agent(mock_agent.name, mock_agent)
    
    # Verify agent is registered
    assert mock_agent.name in agent_runner_instance.list_agents()
    assert agent_runner_instance.get_agent(mock_agent.name) == mock_agent

@pytest.mark.asyncio
async def test_register_duplicate_agent(agent_runner_instance, mock_agent):
    """Test registering an agent with a duplicate name"""
    # Register the agent twice
    agent_runner_instance.register_agent(mock_agent.name, mock_agent)
    
    # Create a second agent with the same name
    second_agent = MagicMock()
    second_agent.name = mock_agent.name
    
    # Register the second agent with the same name
    agent_runner_instance.register_agent(second_agent.name, second_agent)
    
    # Verify the second agent replaced the first
    assert mock_agent.name in agent_runner_instance.list_agents()
    assert agent_runner_instance.get_agent(mock_agent.name) == second_agent

@pytest.mark.asyncio
async def test_list_agents(agent_runner_instance, mock_agent):
    """Test listing registered agents"""
    # Register multiple agents
    agent_runner_instance.register_agent("agent1", mock_agent)
    
    agent2 = MagicMock()
    agent2.name = "agent2"
    agent_runner_instance.register_agent("agent2", agent2)
    
    # Get list of agents
    agents = agent_runner_instance.list_agents()
    
    # Verify list contains both agents
    assert "agent1" in agents
    assert "agent2" in agents
    assert len(agents) == 2

@pytest.mark.asyncio
async def test_get_agent(agent_runner_instance, mock_agent):
    """Test getting an agent by name"""
    # Register an agent
    agent_runner_instance.register_agent(mock_agent.name, mock_agent)
    
    # Get the agent by name
    retrieved_agent = agent_runner_instance.get_agent(mock_agent.name)
    
    # Verify correct agent is returned
    assert retrieved_agent == mock_agent

@pytest.mark.asyncio
async def test_get_nonexistent_agent(agent_runner_instance):
    """Test getting a nonexistent agent"""
    # Try to get a nonexistent agent
    retrieved_agent = agent_runner_instance.get_agent("nonexistent")
    
    # Verify None is returned
    assert retrieved_agent is None

@pytest.mark.asyncio
async def test_run_agent(agent_runner_instance, mock_agent):
    """Test running an agent on a task"""
    # Register an agent
    agent_runner_instance.register_agent(mock_agent.name, mock_agent)
    
    # Run the agent
    response, metrics = await agent_runner_instance.run_agent(mock_agent.name, "test task")
    
    # Verify agent.go was called
    mock_agent.go.assert_called_once()
    
    # Verify correct response string
    assert response == "Mock agent response"
    
    # Verify metrics were returned
    assert isinstance(metrics, dict)

@pytest.mark.asyncio
async def test_run_agent_with_context(agent_runner_instance, mock_agent):
    """Test running an agent with context"""
    # Register an agent
    agent_runner_instance.register_agent(mock_agent.name, mock_agent)
    
    # Run the agent with context
    context = {"key": "value"}
    response, metrics = await agent_runner_instance.run_agent(mock_agent.name, "test task", context)
    
    # Verify agent.go was called
    mock_agent.go.assert_called_once()
    
    # Verify correct response
    assert response == "Mock agent response"
    
    # Verify metrics were returned
    assert isinstance(metrics, dict)
    
    # Verify thread contains context as a user message
    thread = mock_agent.go.call_args[0][0]
    context_messages = [m for m in thread.messages if m.role == "user" and "additional context" in m.content.lower()]
    assert len(context_messages) == 1
    assert "key: value" in context_messages[0].content

@pytest.mark.asyncio
async def test_run_nonexistent_agent(agent_runner_instance):
    """Test running a nonexistent agent"""
    # Try to run a nonexistent agent
    with pytest.raises(ValueError) as excinfo:
        await agent_runner_instance.run_agent("nonexistent", "test task")
    
    # Verify error message
    assert "not found" in str(excinfo.value)

@pytest.mark.asyncio
async def test_global_agent_runner_instance():
    """Test the global agent_runner instance"""
    # Verify global instance exists
    assert agent_runner is not None
    assert isinstance(agent_runner, AgentRunner) 