# Overview

Tyler comes with several built-in tool modules and supports custom tools to extend its capabilities. Each module can be enabled by including its name in the agent's `tools` configuration.

## Available Built-in Tools

- [Web Tools](./web.md) - Tools for interacting with web content
- [Slack Tools](./slack.md) - Tools for Slack workspace integration
- [Command Line Tools](./command-line.md) - Safe access to system commands
- [Notion Tools](./notion.md) - Tools for Notion workspace integration
- [Image Tools](./image.md) - Tools for image generation and manipulation
- [Audio Tools](./audio.md) - Tools for text-to-speech and speech-to-text conversion
- [File Tools](./files.md) - Tools for reading, writing, and processing various file types and documents (PDFs, CSVs, JSON, etc.)

## Selective Tool Loading

Instead of loading all tools from a module, you can selectively load specific tools using the format `"module:tool1,tool2,tool3"`:

```python
# Load all web tools but only specific Notion tools
agent = Agent(
    tools=[
        "web",                                    # Load all web tools
        "notion:search_pages,create_page"         # Only load these specific Notion tools
    ]
)

# Selectively load tools from multiple modules
agent = Agent(
    tools=[
        "web:fetch_page,download_file",           # Only specific web tools
        "slack:post_message",                     # Only specific Slack tool
        "command_line:execute_command",           # Only specific command line tool
        "notion:search_pages,create_page,update_page"  # Only specific Notion tools
    ]
)
```

This provides greater control over which tools are available to an agent, allowing you to create more specialized agents with precisely defined capabilities.

## MCP Tools

Tyler provides first-class support for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction), an open standard for communication between AI agents and tools. MCP allows Tyler to seamlessly integrate with a growing ecosystem of compatible tools and services.

With MCP integration, Tyler can:
- Connect to MCP servers using various transport protocols (WebSocket, SSE, STDIO)
- Automatically discover available tools from MCP servers
- Invoke MCP tools as if they were native Tyler tools
- Manage MCP server lifecycle

See the [MCP Tools](./mcp.md) documentation for detailed information on configuring and using MCP with Tyler.

## Building Custom Tools

Tyler's functionality can be extended by creating custom tools. A custom tool consists of three main components:

1. **Function Definition**: OpenAI function schema describing the tool
2. **Implementation**: The actual Python function that executes the tool
3. **Attributes** (optional): Tool metadata - currently only supports `{"type": "interrupt"}` for interrupt tools

### Basic Structure

```python
# custom_tools.py

TOOLS = [
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "my-custom-tool",
                "description": "Description of what the tool does",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {
                            "type": "string",
                            "description": "Description of parameter 1"
                        },
                        "param2": {
                            "type": "integer",
                            "description": "Description of parameter 2"
                        }
                    },
                    "required": ["param1"]
                }
            }
        },
        "implementation": my_tool_function,
        # Attributes are optional and only used for interrupt tools
        "attributes": {
            "type": "interrupt"  # Only valid attribute, used to mark interrupt tools
        }
    }
]
```

### Implementation Function

Your tool implementation can be either synchronous or asynchronous:

```python
# Synchronous implementation
def my_tool_function(param1: str, param2: int = 0) -> Union[str, Dict]:
    """
    Implement your tool logic here.
    Returns either a string or a dictionary with results.
    """
    result = do_something(param1, param2)
    return {
        "status": "success",
        "data": result
    }

# Asynchronous implementation
async def my_async_tool(param1: str, param2: int = 0) -> Union[str, Dict]:
    """
    Implement your async tool logic here.
    """
    result = await do_something_async(param1, param2)
    return {
        "status": "success",
        "data": result
    }
```

### Returning Files

Tools can return files by using a tuple return format:

```python
async def file_generating_tool() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Tool that generates and returns files.
    
    Returns:
        Tuple containing:
            - Dict with response data (success status, messages, metadata etc.)
            - List of file dictionaries, each containing:
                - filename: Name of the file
                - content: File content as bytes
                - mime_type: MIME type of the file
                - description: Optional description of the file
    """
    # Generate your content
    content = generate_something()
    
    # Create file data
    file_data = {
        "filename": "output.txt",
        "content": content.encode('utf-8'),
        "mime_type": "text/plain",
        "description": "Generated output file"  # Optional
    }
    
    return (
        {
            "success": True, 
            "message": "File generated successfully",
            "metadata": {
                "file_count": 1,
                "total_size": len(content)
            }
        },
        [file_data]  # List of file dictionaries
    )
```

## Using Tools

### Basic Usage

To use both built-in and custom tools, include them in your agent's configuration:

```python
from tyler.models import Agent

# Define a custom tool
def calculator_implementation(operation: str, x: float, y: float) -> str:
    """Simple calculator implementation"""
    if operation == "add":
        result = x + y
    elif operation == "subtract":
        result = x - y
    elif operation == "multiply":
        result = x * y
    elif operation == "divide":
        result = x / y if y != 0 else "Error: division by zero"
    return f"Result: {result}"

custom_calculator = {
    "definition": {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Perform basic calculations",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                        "description": "The mathematical operation to perform"
                    },
                    "x": {"type": "number", "description": "First number"},
                    "y": {"type": "number", "description": "Second number"}
                },
                "required": ["operation", "x", "y"]
            }
        }
    },
    "implementation": calculator_implementation
}

# Initialize agent with both built-in and custom tools
agent = Agent(
    model_name="gpt-4o",
    purpose="To help with various tasks",
    tools=[
        "web",              # Built-in tools
        "slack",
        "notion",
        "command_line",
        "image",
        "audio",            # Audio processing tools
        "files",            # File and document handling tools
        custom_calculator   # Custom tool
    ]
)
```