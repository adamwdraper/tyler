"""Agent runner module.

This module provides a central registry and execution environment for agents.
It follows the same pattern as tool_runner.
"""
import asyncio
import weave
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, UTC
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
    
    @weave.op()
    async def run_agent(self, agent_name: str, task: str, context: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Run an agent on a task with weave tracking.
        
        Args:
            agent_name: The name of the agent to run
            task: The task to run the agent on
            context: Optional context to provide to the agent
            
        Returns:
            Tuple containing the agent's response and execution metrics
            
        Raises:
            ValueError: If the agent is not found
        """
        # Track execution time
        start_time = datetime.now(UTC)
        
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
        try:
            result_thread, messages = await agent.go(thread)
            
            # Format the response (just the assistant messages)
            response = "\n\n".join([
                m.content for m in messages 
                if m.role == "assistant" and m.content
            ])
            
            # Calculate execution time and create metrics
            end_time = datetime.now(UTC)
            execution_time = (end_time - start_time).total_seconds() * 1000  # Convert to milliseconds
            
            metrics = {
                "agent_name": agent_name,
                "timing": {
                    "started_at": start_time.isoformat(),
                    "ended_at": end_time.isoformat(),
                    "latency": execution_time
                },
                "task_length": len(task),
                "response_length": len(response),
                "message_count": len(messages)
            }
            
            # Extract model metrics if available in the messages
            model_metrics = {}
            for message in messages:
                if hasattr(message, 'metrics') and message.metrics:
                    if 'model' in message.metrics:
                        model_metrics['model'] = message.metrics['model']
                    if 'usage' in message.metrics:
                        model_metrics['usage'] = message.metrics['usage']
                    # Only need to get this once
                    if model_metrics:
                        break
                        
            if model_metrics:
                metrics['model'] = model_metrics
            
            logger.info(f"Agent {agent_name} completed task in {execution_time:.2f}ms")
            return response, metrics
            
        except Exception as e:
            # Record error in metrics
            end_time = datetime.now(UTC)
            execution_time = (end_time - start_time).total_seconds() * 1000
            
            error_metrics = {
                "agent_name": agent_name,
                "timing": {
                    "started_at": start_time.isoformat(),
                    "ended_at": end_time.isoformat(),
                    "latency": execution_time
                },
                "error": str(e)
            }
            
            logger.error(f"Error running agent {agent_name}: {str(e)}")
            raise ValueError(f"Error running agent '{agent_name}': {str(e)}") from e

# Create a shared instance
agent_runner = AgentRunner() 