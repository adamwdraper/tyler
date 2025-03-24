"""Agent runner module.

This module provides a central registry and execution environment for agents.
It follows the same pattern as tool_runner.
"""
import asyncio
from typing import Dict, Any, Optional, List
from tyler.models.thread import Thread
from tyler.models.message import Message
from tyler.utils.logging import get_logger

# Get configured logger
logger = get_logger(__name__)

class AgentRunner:
    """Central registry and execution environment for agents."""
    
    def __init__(self):
        """Initialize the agent runner."""
        self.agents = {}  # name -> Agent
        
    def register_agent(self, name: str, agent) -> None:
        """
        Register an agent with the registry.
        
        Args:
            name: Unique name for the agent
            agent: The agent instance to register
        """
        if name in self.agents:
            logger.warning(f"Agent '{name}' already registered. Overwriting.")
        
        self.agents[name] = agent
        logger.info(f"Registered agent: {name}")
        
    def list_agents(self) -> List[str]:
        """Return a list of registered agent names."""
        return list(self.agents.keys())
        
    def get_agent(self, name: str):
        """
        Get an agent by name.
        
        Args:
            name: The name of the agent to retrieve
            
        Returns:
            The agent instance or None if not found
        """
        return self.agents.get(name)
    
    async def run_agent(self, agent_name: str, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Run an agent on a task.
        
        Args:
            agent_name: The name of the agent to run
            task: The task to run the agent on
            context: Optional context to provide to the agent
            
        Returns:
            The agent's response
            
        Raises:
            ValueError: If the agent is not found
        """
        # Get the agent
        agent = self.get_agent(agent_name)
        if not agent:
            raise ValueError(f"Agent '{agent_name}' not found")
        
        # Create a new thread for the agent
        thread = Thread()
        
        # Add context as a system message if provided
        if context:
            context_content = "Context information:\n"
            for key, value in context.items():
                context_content += f"- {key}: {value}\n"
            thread.add_message(Message(
                role="system",
                content=context_content
            ))
        
        # Add the task as a user message
        thread.add_message(Message(
            role="user",
            content=task
        ))
        
        # Execute the agent
        logger.info(f"Running agent {agent_name} with task: {task}")
        result_thread, messages = await agent.go(thread)
        
        # Format the response (just the assistant messages)
        response = "\n\n".join([
            m.content for m in messages 
            if m.role == "assistant" and m.content
        ])
        
        return response

# Create a shared instance
agent_runner = AgentRunner() 