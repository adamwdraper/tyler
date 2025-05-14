---
sidebar_position: 3
---

# Using Tools

This example demonstrates how to use both built-in and custom tools with Tyler. It shows how to create a custom tool for posting to Slack and combine it with the built-in web tools.

## Overview

The example shows:
- Creating a custom tool with a schema and implementation
- Using built-in tools (web tools)
- Combining multiple tools in a single agent
- Processing web content and posting to Slack

## Code

```python
from dotenv import load_dotenv
from tyler import Agent, Thread, Message
import weave
import asyncio
import os
import logging

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.info("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

def post_to_slack_implementation(message: str, channel: str = "#general") -> str:
    """
    Implementation of the Slack posting tool.
    In a real application, this would use the Slack API to post messages.
    """
    # This is a mock implementation
    return f"Message posted to Slack channel {channel}: {message}"

# Define custom Slack posting tool
custom_slack_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "post_to_slack",
            "description": "Post a message to a Slack channel",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message to post to Slack"
                    },
                    "channel": {
                        "type": "string",
                        "description": "The Slack channel to post to (default: #general)",
                        "default": "#general"
                    }
                },
                "required": ["message"]
            }
        }
    },
    "implementation": post_to_slack_implementation
}

# Initialize the agent with both built-in and custom tools
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with web browsing and posting content to Slack",
    tools=[
        "web",          # Load the web tools module
        custom_slack_tool,     # Add our Slack posting tool
    ]
)

async def main():
    # Create a thread with a user question
    thread = Thread()

    # Add a user message
    message = Message(
        role="user",
        content="Please fetch the article at https://www.adamwdraper.com/learnings/2021/7/17/leadership, summarize its key points about leadership style, and post the summary to Slack."
    )
    thread.add_message(message)

    # Process the thread - the agent will use both web and Slack tools
    processed_thread, new_messages = await agent.go(thread)

    # Print all non-user messages
    for message in new_messages:
        print(f"{message.role.capitalize()}: {message.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Step-by-Step Explanation

### 1. Custom Tool Definition
```python
custom_slack_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "post_to_slack",
            "description": "Post a message to a Slack channel",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The message to post"},
                    "channel": {"type": "string", "description": "The channel"}
                },
                "required": ["message"]
            }
        }
    },
    "implementation": post_to_slack_implementation
}
```
Defines a custom tool with:
- Function schema (name, description, parameters)
- Implementation function
- Parameter validation

### 2. Agent Initialization
```python
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with web browsing and posting content to Slack",
    tools=[
        "web",              # Built-in web tools
        custom_slack_tool,  # Custom Slack tool
    ]
)
```
Creates an agent that can:
- Browse web content
- Post messages to Slack
- Combine both capabilities

### 3. Thread Processing
```python
message = Message(
    role="user",
    content="Please fetch the article... and post the summary to Slack."
)
thread.add_message(message)
processed_thread, new_messages = await agent.go(thread)
```
The agent will:
1. Fetch and read the article using web tools
2. Generate a summary
3. Post the summary to Slack

## Configuration Requirements

### Environment Variables
```bash
# For web tools (optional)
TYLER_WEB_TIMEOUT=30
TYLER_WEB_MAX_PAGES=10

# For Slack integration (in production)
SLACK_BOT_TOKEN=your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret

# For monitoring (optional)
WANDB_API_KEY=your-wandb-api-key
```

## Expected Output

When you run this example, you'll see output similar to:

```
Tool (web_fetch): [Content of the leadership article]
Assistant: I've read the article and here's a summary of the key points...
Tool (post_to_slack): Message posted to Slack channel #general: [Summary of leadership points]
Assistant: I've fetched the article, summarized it, and posted the summary to Slack...
```

## Key Concepts

1. **Tool Definition**
   - Schema-based tool definition
   - Parameter validation
   - Implementation function

2. **Tool Combination**
   - Multiple tools in one agent
   - Built-in and custom tools
   - Tool coordination

3. **Web Processing**
   - Content fetching
   - Text extraction
   - Content summarization

4. **Slack Integration**
   - Message posting
   - Channel management
   - Error handling

## Common Customizations

### Different Channel
```python
message = Message(
    content="Post this to the #leadership channel: Hello team!"
)
```

### Custom Tool Behavior
```python
def custom_implementation(message: str, channel: str = "#general") -> str:
    # Your custom Slack posting logic here
    return result
```

### Additional Tools
```python
agent = Agent(
    tools=[
        "web",
        "command_line",
        custom_slack_tool
    ]
)
``` 