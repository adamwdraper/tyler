---
sidebar_position: 4
---

# Core concepts

This guide explains the core concepts and components that make up Tyler's architecture.

## Agent

The `Agent` class is the central component of Tyler. It:
- Manages conversations through threads
- Processes messages using LLMs (with GPT-4o as default)
- Executes tools when needed
- Maintains conversation state
- Supports streaming responses
- Handles file attachments and processing
- Integrates with Weave for monitoring
- Supports agent delegation (parent-child pattern)
- Allows selective loading of tools from modules

### Basic usage

```python
from tyler.models.agent import Agent

agent = Agent(
    model_name="gpt-4o",
    temperature=0.7,
    purpose="To help with tasks",
    tools=["web", "slack", "notion"]
)

# Process a thread
result = await agent.go(thread)

# Process with streaming
async for update in agent.go_stream(thread):
    if update.type == StreamUpdate.Type.CONTENT_CHUNK:
        print(update.data, end="")
```

### Agent delegation

Agents can delegate tasks to other specialized agents:

```python
# Create specialized agents
research_agent = Agent(
    name="ResearchAgent",
    purpose="Find information on specific topics",
    tools=["web"]
)

writing_agent = Agent(
    name="WritingAgent",
    purpose="Write and format text content",
    tools=["notion"]
)

# Create a coordinator agent that can delegate to specialized agents
coordinator = Agent(
    name="Coordinator",
    purpose="Coordinate tasks among specialized agents",
    agents=[research_agent, writing_agent]
)

# The coordinator can now use tools like "delegate_to_ResearchAgent" 
# and "delegate_to_WritingAgent" in conversations
```

### Selective tools loading

You can selectively load specific tools from modules:

```python
# Load only specific Notion tools
agent = Agent(
    tools=["notion:search_pages,create_page"]  # Only load these specific tools
)

# Mix selective and full module loading
agent = Agent(
    tools=[
        "web",  # Load all web tools
        "notion:search_pages,create_page"  # Only specific Notion tools
    ]
)
```

### Key methods

- `go(thread)`: Process a thread with tool execution
- `go_stream(thread)`: Process a thread with streaming updates
- `step(thread)`: Execute a single processing step
- `_process_message_files(message)`: Handle file attachments
- `_handle_tool_execution(tool_call)`: Execute tool calls

## Thread

Threads represent conversations and maintain:
- Message history with proper sequencing
- System prompts
- Conversation metadata and analytics
- Source tracking (e.g., Slack, web)
- Token usage statistics
- Performance metrics

### Creating threads

```python
from tyler.models.thread import Thread

# Basic thread
thread = Thread()

# Thread with title and source
thread = Thread(
    title="Support Conversation",
    source={
        "name": "slack",
        "channel": "C123",
        "thread_ts": "1234567890.123"
    }
)

# Thread with attributes
thread = Thread(
    attributes={
        "customer_id": "123",
        "priority": "high"
    }
)
```

### Message handling

```python
# Add messages (automatically handles sequencing)
system_msg = Message(role="system", content="You are a helpful assistant")
thread.add_message(system_msg)  # Gets sequence 0

user_msg = Message(role="user", content="Hello!")
thread.add_message(user_msg)    # Gets sequence 1

# Get messages by role
last_user = thread.get_last_message_by_role("user")
last_assistant = thread.get_last_message_by_role("assistant")

# Get messages for LLM completion
messages = thread.get_messages_for_chat_completion()
```

### Analytics and monitoring

```python
# Get token usage
stats = thread.get_total_tokens()
print(f"Total tokens: {stats['overall']['total_tokens']}")
print(f"By model: {stats['by_model']}")

# Get timing statistics
timing = thread.get_message_timing_stats()
print(f"Average latency: {timing['average_latency']}s")

# Get message distribution
counts = thread.get_message_counts()
print(f"Messages: {counts}")

# Get tool usage
tools = thread.get_tool_usage()
print(f"Tool calls: {tools['total_calls']}")
```

### Thread management

```python
# Generate descriptive title
title = await thread.generate_title()

# Ensure system prompt
thread.ensure_system_prompt("You are a helpful assistant")

# Clear conversation
thread.clear_messages()

# Convert to dict for storage
thread_data = thread.model_dump()
```

## Message

Messages are the basic units of conversation. They contain:
- Content (text or multimodal)
- Role (user, assistant, system, tool)
- Sequence number for ordering
- Attachments (files with automatic processing)
- Metrics (token usage, timing, model info)
- Source information
- Custom attributes

### Creating messages

```python
from tyler.models.message import Message

# Basic text message
message = Message(
    role="user",
    content="Hello!"
)

# Multimodal message (text + images)
message = Message(
    role="user",
    content=[
        {
            "type": "text",
            "text": "What's in this image?"
        },
        {
            "type": "image_url",
            "image_url": {
                "url": "path/to/image.jpg"
            }
        }
    ]
)

# Message with attributes and source
message = Message(
    role="user",
    content="Hello!",
    attributes={
        "customer_id": "123",
        "priority": "high"
    },
    source={
        "name": "slack",
        "thread_id": "123456"
    }
)

# Message with file attachment
message = Message(
    role="user",
    content="Here's a file",
    file_content=pdf_bytes,
    filename="document.pdf"
)

# Tool message
message = Message(
    role="tool",
    name="weather_tool",
    content='{"temperature": 72}',
    tool_call_id="call_123"  # Required for tool messages
)
```

### Message metrics

Messages automatically track various metrics:

```python
# Message metrics structure
message.metrics = {
    "model": "gpt-4o",          # Model used for generation
    "timing": {
        "started_at": "2024-02-26T12:00:00Z",
        "ended_at": "2024-02-26T12:00:01Z",
        "latency": 1.0
    },
    "usage": {
        "completion_tokens": 100,
        "prompt_tokens": 50,
        "total_tokens": 150
    },
    "weave_call": {
        "id": "call-123",
        "ui_url": "https://weave.ui/call-123"
    }
}
```

### Working with attachments

```python
# Add attachment using raw bytes
message.add_attachment(pdf_bytes, filename="document.pdf")

# Add attachment using Attachment object
attachment = Attachment(filename="data.json", content=json_bytes)
message.add_attachment(attachment)

# Ensure attachments are stored
await message.ensure_attachments_stored()
```

### Message serialization

```python
# Convert to chat completion format
chat_message = message.to_chat_completion_message()

# Convert to storage format
message_data = message.model_dump()
```

## Attachment

Attachments handle files in conversations:
- Support both binary and base64 encoded content
- Automatic storage management
- Content processing and extraction
- Status tracking (pending, stored, failed)
- URL generation for stored files
- Secure backend storage integration

### Creating attachments

```python
from tyler.models.attachment import Attachment

# From binary content
attachment = Attachment(
    filename="document.pdf",
    content=pdf_bytes,
    mime_type="application/pdf"
)

# From base64 content
attachment = Attachment(
    filename="image.png",
    content=base64_string,
    mime_type="image/png"
)

# With attributes
attachment = Attachment(
    filename="data.json",
    content=json_bytes,
    mime_type="application/json",
    attributes={
        "type": "json",
        "overview": "Configuration data",
        "parsed_content": {"key": "value"}
    }
)
```

### Storage management

```python
# Storage is handled automatically when saving threads
thread.add_message(message_with_attachment)
await thread_store.save(thread)  # Stores attachments automatically

# Manual storage if needed
await attachment.ensure_stored()

# Check storage status
if attachment.status == "stored":
    print(f"File stored at: {attachment.storage_path}")
    print(f"Access URL: {attachment.attributes['url']}")
elif attachment.status == "failed":
    print("Storage failed")
```

### Content retrieval

```python
# Get content as bytes
try:
    content = await attachment.get_content_bytes()
except ValueError as e:
    print(f"Content not available: {e}")

# Access attributes
if attachment.attributes:
    if "text" in attachment.attributes:
        print("Extracted text:", attachment.attributes["text"])
    if "overview" in attachment.attributes:
        print("Overview:", attachment.attributes["overview"])
```

### Storage configuration

```python
# Configure via environment variables
TYLER_FILE_STORAGE_TYPE=local  # or s3, gcs, etc.
TYLER_FILE_STORAGE_PATH=/path/to/files

# Storage metadata
print(f"Storage backend: {attachment.storage_backend}")
print(f"File ID: {attachment.file_id}")
print(f"Storage path: {attachment.storage_path}")
```

## Tools

Tools extend agent capabilities by providing specific functionalities that can be called during conversations. Tyler provides a modular tool system with built-in tools and support for custom tools.

### Tool Architecture

Each tool consists of:
- A function definition (OpenAI function format)
- An implementation function
- Optional attribute for interrupt behavior
- Weave integration for monitoring

Tools are organized into modules:
```python
from tyler.tools import (
    WEB_TOOLS,        # Web browsing and downloads
    SLACK_TOOLS,      # Slack integration
    NOTION_TOOLS,     # Notion integration
    IMAGE_TOOLS,      # Image processing
    AUDIO_TOOLS,      # Audio processing
    FILES_TOOLS,      # File operations and document processing
    COMMAND_LINE_TOOLS  # Shell commands
)
```

### Using Built-in Tools

```python
from tyler.models.agent import Agent

# Use specific tool modules
agent = Agent(
    tools=["web", "slack", "notion"]
)

# Mix built-in and custom tools
agent = Agent(
    tools=[
        "web",
        custom_tool,
        "slack"
    ]
)
```

### Creating Custom Tools

Tools follow the OpenAI function calling format:

```python
# Define tool
custom_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "custom_tool",
            "description": "Tool description",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Parameter description"
                    }
                },
                "required": ["param1"]
            }
        }
    },
    "implementation": lambda param1: f"Result: {param1}",
    "attributes": {  # Optional
        "type": "interrupt"  # Only valid attribute - indicates tool can interrupt processing
    }
}

# Use custom tool
agent = Agent(tools=[custom_tool])
```

### Tool Implementation

Tools can be implemented as simple functions or with Weave monitoring:

```python
# Simple implementation
def simple_tool(param1: str) -> str:
    return f"Processed: {param1}"

# With Weave monitoring
@weave.op(name="custom-tool")
def monitored_tool(*, param1: str) -> Dict:
    try:
        result = process_param(param1)
        return {
            "success": True,
            "result": result,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "result": None,
            "error": str(e)
        }
```

### Tool Categories

Built-in tools are organized by functionality:

#### Web Tools
- `web-fetch_page`: Fetch and parse web content
- `web-download_file`: Download files from URLs

#### File Tools
- File operations (read, write, delete)
- Directory management
- File type detection

#### Image Tools
- Image processing
- OCR
- Visual analysis

#### Audio Tools
- Audio processing
- Speech-to-text
- Audio analysis

#### Integration Tools
- Slack integration
- Notion integration
- Command line operations

### Tool Execution

Tools are executed automatically by the agent when needed:

```python
# Tool execution in conversation
thread = Thread()
thread.add_message(Message(
    role="user",
    content="What's on this webpage? https://example.com"
))

# Agent automatically uses web-fetch_page tool
result = await agent.go(thread)
```

### Error Handling

Tools should handle errors gracefully:

```python
def robust_tool(param1: str) -> Dict:
    try:
        # Tool logic
        return {
            "success": True,
            "result": result
        }
    except ValueError as e:
        return {
            "success": False,
            "error": f"Invalid input: {e}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Tool failed: {e}"
        }
```

### Best Practices

1. **Tool Definition**
   ```python
   # Clear description and parameter docs
   tool = {
       "definition": {
           "function": {
               "description": "Detailed purpose and usage",
               "parameters": {
                   "properties": {
                       "param1": {
                           "description": "Clear parameter purpose"
                       }
                   }
               }
           }
       }
   }
   ```

2. **Error Handling**
   ```python
   # Always return structured responses
   {
       "success": bool,
       "result": Any,
       "error": Optional[str]
   }
   ```

3. **Monitoring**
   ```python
   # Use Weave for production tools
   @weave.op(name="custom-tool")
   def monitored_tool():
       pass
   ```

## Storage

Tyler supports multiple storage backends:

### Thread Storage

Thread storage handles conversation persistence and retrieval through a unified `ThreadStore` class with pluggable backends:

```python
# In-memory storage (default)
from tyler.database.thread_store import ThreadStore
store = ThreadStore()  # Uses memory backend by default

# PostgreSQL storage
store = ThreadStore("postgresql+asyncpg://user:pass@localhost/dbname")
await store.initialize()  # Required before use

# SQLite storage
store = ThreadStore("sqlite+aiosqlite:///path/to/db.sqlite")
await store.initialize()

# Use with agent
agent = Agent(thread_store=store)
```

#### Memory Backend

Key characteristics:
- Fastest possible performance (direct dictionary access)
- No persistence (data is lost when program exits)
- No setup required (works out of the box)
- Perfect for scripts and one-off conversations
- Great for testing and development

#### SQL Backend (PostgreSQL/SQLite)

Key characteristics:
- Async operations for non-blocking I/O
- Persistent storage (survives restarts)
- Cross-session support
- Production-ready with PostgreSQL
- Development-friendly with SQLite
- Automatic schema management

Configuration options:
```python
# Environment variables
TYLER_DB_TYPE=sql           # Force SQL backend even without URL
TYLER_DB_ECHO=true          # Enable SQL logging
TYLER_DB_POOL_SIZE=10       # Connection pool size
TYLER_DB_MAX_OVERFLOW=20    # Max additional connections
```

Common operations:
```python
# Save thread and changes
thread = Thread()
await store.save(thread)

# Retrieve thread
thread = await store.get(thread_id)

# List recent threads
threads = await store.list_recent(limit=30)

# Find by attributes
threads = await store.find_by_attributes({
    "customer_id": "123",
    "priority": "high"
})

# Find by source
threads = await store.find_by_source(
    "slack",
    {"channel": "C123", "thread_ts": "123.456"}
)
```

### File Storage

```python
# Configure via environment
TYLER_FILE_STORAGE_TYPE=local
TYLER_FILE_STORAGE_PATH=/path/to/files

# Attachments are automatically processed and stored when saving a thread
message = Message(role="user", content="Here's a file")
message.add_attachment(file_bytes, filename="document.pdf")
thread.add_message(message)

# Simply save the thread - attachments are processed automatically
await thread_store.save(thread)

# Access attachment information after storage
for attachment in message.attachments:
    if attachment.status == "stored":
        print(f"File stored at: {attachment.storage_path}")
```

## Streaming

Tyler supports streaming responses:

### Basic streaming

```python
async for update in agent.go_stream(thread):
    if update.type == StreamUpdate.Type.CONTENT_CHUNK:
        print(update.data, end="")
```

### Stream update types

- `CONTENT_CHUNK`: Partial content from assistant
- `ASSISTANT_MESSAGE`: Complete assistant message
- `TOOL_MESSAGE`: Tool execution result
- `COMPLETE`: Final thread state
- `ERROR`: Error during processing

## Error handling

Tyler provides robust error handling:

### Try-except blocks

```python
try:
    result = await agent.go(thread)
except Exception as e:
    print(f"Error: {str(e)}")
```

### Error messages

```python
# Error messages are added to thread
message = Message(
    role="assistant",
    content="Error: Tool execution failed",
    metrics={"error": str(e)}
)
thread.add_message(message)
```

## MCP Integration

Tyler provides integration with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction), an open standard for communication between AI agents and tools.

### MCPService

The `MCPService` class is responsible for:
- Managing connections to MCP servers
- Discovering available tools from MCP servers
- Converting MCP tools to Tyler-compatible tools
- Executing tool calls against MCP servers

```python
from tyler.mcp.utils import initialize_mcp_service, cleanup_mcp_service

# Initialize MCP service
mcp_service = await initialize_mcp_service([
    {
        "name": "brave-search",
        "transport": "stdio",
        "command": ["python", "-m", "brave_search.server"],
        "auto_start": True
    }
])

# Get available tools
tools = mcp_service.get_tools_for_agent()

# Clean up when done
await cleanup_mcp_service(mcp_service)
```

### MCPServerManager

The `MCPServerManager` class handles:
- Starting and stopping MCP servers
- Managing server processes
- Handling server lifecycle events

```python
from tyler.mcp.server_manager import MCPServerManager

# Create server manager
server_manager = MCPServerManager()

# Start a server
await server_manager.start_server("brave-search", {
    "transport": "stdio",
    "command": ["python", "-m", "brave_search.server"],
    "auto_start": True
})

# Stop a server
await server_manager.stop_server("brave-search")

# Stop all servers
await server_manager.stop_all_servers()
```

### Supported Transport Protocols

Tyler supports multiple MCP transport protocols:
- **STDIO**: Communication via standard input/output
- **SSE**: Server-Sent Events over HTTP
- **WebSocket**: Bidirectional communication over WebSocket

### Integration with Agent

MCP tools can be used with Tyler agents:

```python
from tyler.models.agent import Agent

# Create agent with MCP tools
agent = Agent(
    model_name="gpt-4o",
    tools=["mcp"],
    config={
        "mcp": {
            "servers": [
                {
                    "name": "brave-search",
                    "transport": "stdio",
                    "command": ["python", "-m", "brave_search.server"],
                    "auto_start": True
                }
            ]
        }
    }
)
```

## Next steps

- See [Examples](./category/examples) for practical usage
- Learn about [Configuration](./configuration.md)
- Explore [API reference](./category/api-reference) 