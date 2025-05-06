"""Example of using Tyler with the Brave Search MCP server.

This example demonstrates how to use Tyler with the Brave Search MCP server.
"""
# Load environment variables and configure logging first
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

# Now import everything else
import asyncio
import os
import sys
import weave
from typing import List, Dict, Any

from tyler import Agent, Thread, Message
from tyler.mcp.utils import initialize_mcp_service, cleanup_mcp_service

# Add the parent directory to the path so we can import the example utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize weave tracing if WANDB_API_KEY is set
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

async def main():
    """Run the example."""
    # Check for Brave API key
    brave_api_key = os.environ.get("BRAVE_API_KEY")
    if not brave_api_key:
        logger.warning("BRAVE_API_KEY environment variable not set. "
                      "Please set it to use the Brave Search API.")
        return
        
    logger.info("Initializing MCP service with Brave Search server...")
    
    # Configure the Brave Search MCP server
    server_configs = [
        {
            "name": "brave",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "startup_timeout": 5,
            "required": True,
            "env": {
                "BRAVE_API_KEY": brave_api_key
            }
        }
    ]
    
    # Initialize the MCP service
    mcp_service = await initialize_mcp_service(server_configs)
    
    try:
        # Get the MCP tools for the agent
        mcp_tools = mcp_service.get_tools_for_agent(["brave"])
        
        if not mcp_tools:
            logger.error("No tools discovered from the Brave Search MCP server.")
            return
            
        logger.info(f"Discovered {len(mcp_tools)} tools from the Brave Search MCP server.")
        
        # Create an agent with the MCP tools
        agent = Agent(
            name="Tyler",
            model_name="gpt-4o",
            tools=mcp_tools
        )
        
        # Create a thread
        thread = Thread()
        
        # Add a user message
        thread.add_message(Message(
            role="user",
            content="What can you tell me about quantum computing?"
        ))
        
        # Process the thread with streaming
        logger.info("Processing thread with streaming...")
        async for update in agent.go_stream(thread):
            if update.type.name == "CONTENT_CHUNK":
                print(update.data, end="", flush=True)
            elif update.type.name == "TOOL_MESSAGE":
                print(f"\n[Tool execution: {update.data['name']}]\n")
            elif update.type.name == "COMPLETE":
                print("\n\nProcessing complete!")
                
    finally:
        # Clean up the MCP service
        logger.info("Cleaning up MCP service...")
        await cleanup_mcp_service()


if __name__ == "__main__":
    asyncio.run(main()) 