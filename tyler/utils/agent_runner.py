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
import traceback

# Get configured logger
logger = get_logger(__name__)

class AgentRunner:
    """Central registry and execution environment for agents."""
    
    def __init__(self):
        """Initialize the agent runner."""
        self._agents = {}  # Maps agent name -> agent instance
        
    def register_agent(self, name: str, agent: Any) -> None:
        """
        Register an agent with the runner.
        
        Args:
            name: Name to register the agent under
            agent: Agent instance to register
        """
        if name in self._agents:
            logger.warning(f"Overwriting existing agent with name '{name}'")
        self._agents[name] = agent
        logger.info(f"Registered agent '{name}'")
        
    def list_agents(self) -> List[str]:
        """Return a list of registered agent names."""
        return list(self._agents.keys())
        
    def get_agent(self, name: str) -> Optional[Any]:
        """
        Get a registered agent by name.
        
        Args:
            name: Name of the agent to retrieve
            
        Returns:
            The agent instance, or None if not found
        """
        return self._agents.get(name)
    
    @weave.op()
    async def run_agent(self, name: str, task: str, context: Optional[Dict[str, Any]] = None) -> Tuple[Any, Dict]:
        """
        Run an agent with a specific task.
        
        Args:
            name: Name of the agent to run
            task: Task description or instruction for the agent
            context: Optional dictionary of context information
            
        Returns:
            Tuple of (response_text, metrics)
            
        Raises:
            ValueError: If agent not found
            Exception: For any other errors during execution
        """
        agent = self.get_agent(name)
        if not agent:
            raise ValueError(f"Agent '{name}' not found")
        
        # Create a temporary thread for the task
        thread = Thread()
        
        # Add the task as a user message
        user_message = Message(
            role="user",
            content=task,
            source={
                "id": "agent_runner",
                "name": "AgentRunner",
                "type": "tool"
            }
        )
        thread.add_message(user_message)
        
        # Add context if provided (as a user message)
        if context:
            context_str = f"Here is additional context that may be helpful:\n{context}"
            context_message = Message(
                role="user", 
                content=context_str,
                source={
                    "id": "agent_runner",
                    "name": "AgentRunner",
                    "type": "tool"
                }
            )
            thread.add_message(context_message)
        
        # Execute the agent
        logger.info(f"Running agent '{name}' with task: {task[:50]}...")
        try:
            result_thread, new_messages = await agent.go(thread)
            
            # Get the last assistant message
            assistant_messages = [m for m in new_messages if m.role == "assistant"]
            if not assistant_messages:
                logger.warning(f"Agent '{name}' did not generate any assistant messages")
                return "No response generated.", {}
            
            # Get the final response and metrics
            response = assistant_messages[-1].content
            metrics = getattr(assistant_messages[-1], 'metrics', {})
            
            return response, metrics
            
        except Exception as e:
            logger.error(f"Error running agent '{name}': {str(e)}")
            logger.error(traceback.format_exc())
            raise

# Create a singleton instance
agent_runner = AgentRunner() 