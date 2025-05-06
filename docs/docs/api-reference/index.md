---
sidebar_position: 1
---

# API Reference

This section provides detailed documentation for Tyler's core components and APIs. Each page covers a specific component's interface, methods, and usage patterns.

## Core Components

1. [Agent](./agent.md) - The central component for managing conversations and executing tasks
2. [Thread](./thread.md) - Manages conversation history and context
3. [Message](./message.md) - Handles individual interactions and content
4. [Attachment](./attachment.md) - Manages file attachments and content storage

## Installation

To use these components, install Tyler:

```bash
pip install tyler-agent
```

## Basic Usage

Here's a quick example of using the core components:

```python
from tyler import Agent, Thread, Message

# Create an agent
agent = Agent(
    model_name="gpt-4o",
    purpose="To help with tasks"
)

# Create a thread
thread = Thread()

# Add a message
message = Message(
    role="user",
    content="Hello!"
)
thread.add_message(message)

# Process the thread
processed_thread, new_messages = await agent.go(thread)
```

## Component Relationships

The components work together in the following way:
- `Agent` processes threads and manages tools
- `Thread` contains messages and maintains context
- `Message` holds content and metadata

## Type Definitions

All components use TypeScript-style type definitions:

```python
class Agent:
    """The main agent class."""
    model_name: str
    purpose: str
    tools: List[Tool]
    ...

class Thread:
    """Conversation thread class."""
    messages: List[Message]
    system_prompt: Optional[str]
    ...

class Message:
    """Individual message class."""
    role: str
    content: str
    name: Optional[str]
    ...
```

## Error Handling

All components use standard Python exceptions:

```python
try:
    await agent.go(thread)
except AgentError as e:
    print(f"Agent error: {e}")
except ThreadError as e:
    print(f"Thread error: {e}")
except MessageError as e:
    print(f"Message error: {e}")
```

## See Also

- [Examples](../examples/index.md) - Practical usage examples
- [Configuration](../configuration.md) - Configuration options
- [Core Concepts](../core-concepts.md) - Architecture overview 