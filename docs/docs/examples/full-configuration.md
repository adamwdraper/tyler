---
sidebar_position: 4
---

# Full Configuration

This example demonstrates how to use all available configuration options in Tyler, including custom tools, persistent storage, and monitoring.

## Overview

The example shows:
- Setting up a custom weather tool
- Configuring persistent storage with SQLite
- Setting up monitoring with Weave
- Using multiple tools together
- Customizing agent behavior

## Code

```python
from dotenv import load_dotenv
from tyler import Agent, Thread, Message, ThreadStore
import asyncio
import weave
import os

# Load environment variables from .env file
load_dotenv()

# Initialize weave for tracing (optional)
if os.getenv("WANDB_API_KEY"):
    weave.init("tyler")

# Example custom tool implementation
async def get_weather_async(location: str) -> str:
    """
    Async implementation of the weather tool.
    In a real application, this would call a weather API asynchronously.
    """
    # Simulate async API call
    await asyncio.sleep(0.5)
    return f"The weather in {location} is sunny with a temperature of 72°F"

# Define custom weather tool
weather_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and country"
                    }
                },
                "required": ["location"]
            }
        }
    },
    "implementation": get_weather_async
}

# Initialize thread store with SQLite database
thread_store = ThreadStore()

# Initialize agent with all available configuration options
agent = Agent(
    # Core LLM settings
    model_name="gpt-4.1",          # The LLM model to use
    temperature=0.7,              # Controls randomness in responses (0.0 to 1.0)
    
    # Agent identity and behavior
    name="WeatherBot",            # Custom name for the agent
    purpose="To demonstrate agent configuration with weather information capabilities",
    notes="""
    Key capabilities and guidelines:
    - Provides weather information using custom weather tool
    - Uses web tools for additional real-time information when needed
    - Executes command line operations when required
    - Maintains conversation history in SQLite database
    - Gives clear, concise responses with context
    """,
    
    # Tools configuration
    tools=[
        "web",                    # Built-in web tools module
        "command_line",           # Built-in command line tools
        weather_tool,             # Custom weather information tool
    ],
    max_tool_recursion=10,        # Maximum number of recursive tool calls
    
    # Storage configuration
    thread_store=thread_store     # Use SQLite for persistent storage
)

async def main():
    # Create a new thread
    thread = Thread()
    await thread_store.save(thread)

    # Add a user message that will demonstrate multiple capabilities
    message = Message(
        role="user",
        content="""Please help me with the following:
1. What's the current weather in Tokyo?
2. Compare that with the weather in New York
3. List the contents of the current directory"""
    )
    thread.add_message(message)
    await thread_store.save(thread)

    # Process the thread
    processed_thread, new_messages = await agent.go(thread.id)

    # Print all non-user messages
    for message in new_messages:
        if message.role == "assistant":
            print(f"\n{agent.name}: {message.content}")
        elif message.role == "tool":
            print(f"\nTool ({message.name}): {message.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration Options

### 1. LLM Settings
```python
agent = Agent(
    model_name="gpt-4.1",     # Model to use
    temperature=0.7,         # Response creativity
)
```
Controls the core language model behavior:
- Model selection
- Temperature for response variation
- Token limits and other model parameters

### 2. Agent Identity
```python
agent = Agent(
    name="WeatherBot",
    purpose="To demonstrate agent configuration...",
    notes="Key capabilities and guidelines...",
)
```
Defines the agent's:
- Custom name
- Primary purpose
- Behavioral guidelines
- Capabilities and limitations

### 3. Tools Configuration
```python
agent = Agent(
    tools=[
        "web",              # Built-in tools
        "command_line",
        weather_tool,       # Custom tools
    ],
    max_tool_recursion=10,
)
```
Configures:
- Available tools
- Tool execution limits
- Custom tool implementations

### 4. Storage Configuration
```python
thread_store = ThreadStore()
agent = Agent(
    thread_store=thread_store
)
```
Sets up:
- Persistent storage
- Thread history
- Message tracking

## Environment Variables

```bash
# LLM Configuration
OPENAI_API_KEY=your-api-key

# Database Configuration
TYLER_DB_TYPE=sqlite
TYLER_DB_PATH=~/.tyler/data/tyler.db

# Monitoring
WANDB_API_KEY=your-wandb-api-key

# Optional Tool Settings
TYLER_WEB_TIMEOUT=30
TYLER_COMMAND_TIMEOUT=10
```

## Expected Output

When you run this example, you'll see output similar to:

```
Tool (get_weather): The weather in Tokyo is sunny with a temperature of 72°F

WeatherBot: I'll help you with all of those requests:

1. Tokyo Weather: It's currently sunny and 72°F in Tokyo.

2. Let me check New York's weather...

Tool (get_weather): The weather in New York is sunny with a temperature of 72°F

WeatherBot: New York is also sunny and 72°F. Both cities are experiencing similar weather conditions today.

3. Let me list the directory contents...

Tool (command_line): [Directory contents listed here]

WeatherBot: Here are the contents of the current directory: [...]
```

## Key Concepts

1. **Agent Configuration**
   - Model settings
   - Identity and behavior
   - Tool configuration
   - Storage setup

2. **Custom Tools**
   - Async implementation
   - Schema definition
   - Parameter validation

3. **Persistent Storage**
   - Thread management
   - History tracking
   - Database configuration

4. **Monitoring**
   - Weave integration
   - Performance tracking
   - Error logging

## Common Customizations

### Different Storage Backend
```python
from tyler.database import ThreadStore

store = ThreadStore(
    db_type="postgresql",
    host="localhost",
    port=5432
)
```

### Custom System Prompt
```python
thread = Thread(
    system_prompt="You are a weather expert..."
)
```

### Additional Tools
```python
agent = Agent(
    tools=[
        "web",
        "command_line",
        weather_tool,
        another_custom_tool
    ]
)
``` 