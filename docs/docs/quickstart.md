---
sidebar_position: 2
---

# Quickstart

This guide will help you install Tyler and create your first AI agent.

## Installation

### System requirements

Tyler requires Python 3.12.8 or later. You can check your Python version by running:

```bash
python --version
```

If you need to install or update Python, visit the [official Python website](https://www.python.org/downloads/).

Tyler also requires some system libraries for processing PDFs and images. Install them using Homebrew:

```bash
brew install libmagic poppler
```

### Installing Tyler

Install the latest version from PyPI:

```bash
uv add tyler-agent
```

### Basic configuration

Create a `.env` file in your project directory with your OpenAI API key (minimum required configuration):

```bash
# OpenAI API Key (or other LLM provider)
OPENAI_API_KEY=your-api-key-here
```

For additional configuration options, see the [Configuration guide](./configuration.md).

## Creating your first agent

Let's create a simple agent that can use web tools and respond to questions. This example demonstrates:
- Setting up a Tyler agent
- Creating a conversation thread
- Sending and receiving messages
- Using built-in tools
- Optional Weave monitoring integration

```python
from dotenv import load_dotenv
from tyler import Agent, Thread, Message
import asyncio
import weave
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

# Initialize the agent (uses in-memory storage by default)
agent = Agent(
    model_name="gpt-4.1",
    purpose="To be a helpful assistant.",
    tools=[
        "web",
        "slack"
    ]
)

async def main():
    # Create a new thread
    thread = Thread()

    # Add a user message
    message = Message(
        role="user",
        content="What tools do you have?"
    )
    thread.add_message(message)

    # Process the thread
    processed_thread, new_messages = await agent.go(thread)

    # Print the assistant's response
    for message in new_messages:
        if message.role == "assistant":
            print(f"Assistant: {message.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Understanding the code

### 1. Environment setup
```python
from dotenv import load_dotenv
load_dotenv()
```
Loads environment variables from your `.env` file, which should contain your API keys and configuration.

### 2. Weave monitoring (Optional)

[W&B Weave](https://weave-docs.wandb.ai/) is a framework for tracking, evaluating, and improving LLM-based applications. While this is optional, you are going to want to use this to understand how your agent is performing.
```python
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.info("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")
```

### 3. Agent initialization
```python
agent = Agent(
    model_name="gpt-4.1",
    purpose="To be a helpful assistant.",
    tools=[
        "web",
        "slack"
    ]
)
```
Creates a new Tyler agent with:
- GPT-4.1 model
- A general-purpose role
- Web and Slack tools enabled
- Default in-memory storage

### 4. Thread and message handling
```python
thread = Thread()
message = Message(
    role="user",
    content="What tools do you have?"
)
thread.add_message(message)
```
Creates a conversation thread and adds a message to it.

### 5. Processing and response
```python
processed_thread, new_messages = await agent.go(thread)
```
Processes the thread using the agent, which:
- Analyzes the messages
- Executes any necessary tools
- Generates responses

## Expected output

When you run this example, you'll see output similar to:

```
Assistant: I have access to the following tools:

1. Web Tools:
   - Fetch and process web content
   - Download files from URLs
   - Extract text from web pages

2. Slack Tools:
   - Send messages to channels
   - Upload files
   - Interact with users
   - Manage conversations

I can use these tools to help you with tasks like:
- Looking up information online
- Processing web content
- Communicating through Slack
- Handling file attachments

Is there anything specific you'd like me to help you with using these tools?
```

## Common customizations

### Different model
```python
agent = Agent(
    model_name="gpt-3.5-turbo",  # Use a faster, cheaper model
    purpose="To be a helpful assistant."
)
```

### Additional tools
```python
agent = Agent(
    model_name="gpt-4.1",
    purpose="To be a helpful assistant.",
    tools=[
        "web",
        "slack",
        "notion",
        "command_line"
    ]
)
```

### Custom system prompt
```python
thread = Thread(
    system_prompt="You are an AI assistant focused on technical support."
)
```

### Message attributes
```python
message = Message(
    role="user",
    content="Hello!",
    attributes={
        "source": "website",
        "user_id": "123"
    }
)
```

## Next steps

- Learn [How Tyler works](./how-it-works.md)
- Explore [Configuration](./configuration.md)
- See [Examples](./category/examples) of Tyler in action 