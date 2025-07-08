"""
Example script demonstrating agent-to-agent delegation using the parent-child approach.

This script creates multiple specialized agents and attaches them to
a main coordinator agent which can delegate tasks to them.
"""
import asyncio
import os
from tyler import Agent, Thread, Message
from tyler.utils.logging import get_logger
import weave

# Load environment variables and configure logging first
from dotenv import load_dotenv
load_dotenv()

logger = get_logger(__name__)

try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

async def main():
    # Create specialized agents
    research_agent = Agent(
        name="Research",  # Using simple, unique names
        model_name="gpt-4.1",
        purpose="To conduct in-depth research on topics and provide comprehensive information.",
        tools=["web"]  # Give research agent web search tools
    )
    
    code_agent = Agent(
        name="Code",  # Using simple, unique names
        model_name="gpt-4.1",
        purpose="To write, review, and explain code in various programming languages.",
        tools=[]  # No additional tools needed for coding
    )
    
    creative_agent = Agent(
        name="Creative",  # Using simple, unique names
        model_name="gpt-4.1",
        purpose="To generate creative content such as stories, poems, and marketing copy.",
        tools=[]  # No additional tools needed for creative writing
    )
    
    # Create main agent with specialized agents as a list
    main_agent = Agent(
        name="Coordinator",
        model_name="gpt-4.1",
        purpose="To coordinate work by delegating tasks to specialized agents when appropriate.",
        tools=[],  # No additional tools needed since agents will be added as tools
        agents=[research_agent, code_agent, creative_agent]  # Simple list instead of dictionary
    )
    
    # Initialize a thread with a complex query that requires delegation
    thread = Thread()
    
    # Add a message that will likely require delegation
    thread.add_message(Message(
        role="user",
        content="""I need help with a few things:
        
1. I need research on the latest advancements in quantum computing
2. I need a short Python script that can convert CSV to JSON
3. I need a creative tagline for my tech startup called "QuantumLeap"
        
Please help me with these tasks.
        """
    ))
    
    # Print configured child agents
    child_agent_names = [agent.name for agent in main_agent.agents]
    logger.info(f"Configured child agents: {child_agent_names}")
    logger.info(f"Available delegation tools: {len([t for t in main_agent._processed_tools if 'delegate_to_' in t.get('function', {}).get('name', '')])}")
    
    # Process with the main agent
    result_thread, messages = await main_agent.go(thread)
    
    # Print the results
    print("\n=== FINAL CONVERSATION ===\n")
    for message in result_thread.messages:
        if message.role == "user":
            print(f"\nUser: {message.content}\n")
        elif message.role == "assistant":
            print(f"\nAssistant: {message.content}\n")
            if message.tool_calls:
                print(f"[Tool calls: {', '.join([tc['function']['name'] for tc in message.tool_calls])}]")
        elif message.role == "tool":
            print(f"\nTool ({message.name}): {message.content}\n")

if __name__ == "__main__":
    asyncio.run(main()) 