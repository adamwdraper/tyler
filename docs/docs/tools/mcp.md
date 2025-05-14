# MCP Tools

Tyler provides support for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction), allowing seamless integration with MCP-compatible tools and services.

## Overview

[MCP](https://modelcontextprotocol.io/introduction) is an open standard for communication between AI agents and tools. It defines a protocol for discovering, invoking, and streaming results from tools. Tyler's MCP integration allows you to:

- Connect to MCP servers using various transport protocols (WebSocket, SSE, STDIO)
- Automatically discover available tools from MCP servers
- Invoke MCP tools as if they were native Tyler tools
- Manage MCP server lifecycle

## Configuration

To use MCP tools with Tyler, you need to:

1. Initialize the MCP service with server configurations
2. Get the MCP tools for the agent
3. Create an agent with the MCP tools

## Server Configuration Options

MCP servers can be configured with the following options:

| Option | Description |
|--------|-------------|
| `name` | Unique identifier for the server |
| `transport` | Transport protocol: `stdio`, `sse`, or `websocket` |
| `command` | Command to start the server (for `stdio` transport) |
| `args` | Arguments to pass to the command (for `stdio` transport) |
| `startup_timeout` | Timeout in seconds for server startup |
| `required` | Whether the server is required for operation |
| `env` | Environment variables to set for the server process |
| `url` | URL for connecting to the server (for `sse` and `websocket` transports) |
| `headers` | Optional HTTP headers for connection (for `sse` and `websocket` transports) |

## Example Usage

Here's a complete example of using Tyler with the Brave Search MCP server:

```python
"""Example of using Tyler with the Brave Search MCP server."""
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
            model_name="gpt-4.1",
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
```

## Available MCP Servers

Tyler can work with any MCP-compatible server. For a comprehensive and up-to-date list of available MCP servers, refer to the official [Model Context Protocol servers repository](https://github.com/modelcontextprotocol/servers). This repository contains reference implementations, community-built servers, and additional resources for working with MCP.

The repository includes servers for various use cases including:
- Web search
- File system access
- Database interactions
- API integrations
- And many more

New servers are regularly added by the community, making it the best place to discover MCP tools for your specific needs.

## Advanced Usage

For more advanced usage, you can directly interact with the MCP service:

```python
from tyler.mcp.utils import initialize_mcp_service, cleanup_mcp_service

# Initialize MCP service with custom configuration
server_configs = [
    {
        "name": "custom-server",
        "transport": "websocket",
        "url": "ws://localhost:8765"
    }
]

# Initialize the MCP service
mcp_service = await initialize_mcp_service(server_configs)

try:
    # Get all available tools
    all_tools = mcp_service.get_tools_for_agent()
    
    # Get tools from specific servers
    custom_tools = mcp_service.get_tools_for_agent(["custom-server"])
    
    # Use the tools with an agent
    agent = Agent(
        model_name="gpt-4.1",
        tools=custom_tools
    )
    
    # Process a thread
    result = await agent.go(thread)
    
finally:
    # Clean up when done
    await cleanup_mcp_service()
``` 