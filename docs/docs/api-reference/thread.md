---
sidebar_position: 2
---

# Thread API

The `Thread` class manages conversations and maintains context between messages. It's responsible for organizing messages, handling system prompts, storing conversation metadata, and tracking analytics.

## Initialization

```python
from tyler.models.thread import Thread
from datetime import datetime, UTC

# Create a new thread
thread = Thread()

# Create a thread with custom parameters
thread = Thread(
    title="My Thread",
    messages=[],
    attributes={},
    source={"name": "slack", "thread_id": "123"}
)
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | str | No | UUID4 | Unique thread identifier |
| `title` | Optional[str] | No | "Untitled Thread" | Thread title |
| `messages` | List[Message] | No | \[\] | List of messages |
| `created_at` | datetime | No | now(UTC) | Creation timestamp |
| `updated_at` | datetime | No | now(UTC) | Last update timestamp |
| `attributes` | Dict | No | \{\} | Custom metadata |
| `source` | Optional[Dict[str, Any]] | No | None | Source information (e.g. Slack thread ID) |

## Methods

### add_message

Add a new message to the thread and update analytics.

```python
def add_message(
    self,
    message: Message
) -> None
```

Messages are sequenced based on their role:
- System messages always get sequence 0 and are inserted at the beginning
- Other messages get incremental sequence numbers starting at 1
- Updates thread's `updated_at` timestamp

#### Example

```python
message = Message(role="user", content="Hello!")
thread.add_message(message)
```

### ensure_system_prompt

Ensures a system prompt exists as the first message in the thread.

```python
def ensure_system_prompt(
    self,
    prompt: str
) -> None
```

Only adds a system message if none exists at the start of the thread.
Does not modify any existing system messages.

### get_messages_for_chat_completion

Return messages in the format expected by chat completion APIs.

```python
async def get_messages_for_chat_completion(self, file_store: Optional[FileStore] = None) -> List[Dict[str, Any]]
```

This method returns all non-system messages from the thread in the format required by chat completion APIs. System messages stored in the thread are intentionally skipped, as system prompts are now handled ephemerally by agent classes at completion time.

**Parameters:**
- `file_store`: Optional FileStore instance to pass to messages for file URL access.

**Returns:**
- A list of message dictionaries in the format expected by completion APIs.

**Example:**

```python
# Get messages for completion
messages = await thread.get_messages_for_chat_completion()

# Agents will typically add system prompts at completion time
system_prompt = "You are a helpful assistant."
completion_messages = [{"role": "system", "content": system_prompt}] + messages

# Use with completion API
response = await litellm.acompletion(
    model="gpt-4",
    messages=completion_messages
)
```

**Note:** This method intentionally skips any system messages stored in the thread. In the current architecture, system prompts are handled ephemerally by the agent classes and injected at completion time, rather than being stored in the thread.

### clear_messages

Clear all messages from the thread.

```python
def clear_messages(self) -> None
```

Removes all messages and updates the thread's `updated_at` timestamp.

### get_last_message_by_role

Return the last message with the specified role.

```python
def get_last_message_by_role(
    self,
    role: Literal["user", "assistant", "system", "tool"]
) -> Optional[Message]
```

Returns the most recent message with the specified role, or None if no messages exist with that role.

### generate_title

Generate a concise title for the thread using GPT-4o.

```python
@weave.op()
def generate_title(self) -> str
```

Uses GPT-4o to generate a descriptive title based on the conversation content.
Updates the thread's title and `updated_at` timestamp.

### get_total_tokens

Get total token usage across all messages in the thread.

```python
def get_total_tokens(self) -> Dict[str, Any]
```

Returns:
```python
{
    "overall": {
        "completion_tokens": int,
        "prompt_tokens": int,
        "total_tokens": int
    },
    "by_model": {
        "model_name": {
            "completion_tokens": int,
            "prompt_tokens": int,
            "total_tokens": int
        }
    }
}
```

### get_model_usage

Get usage statistics for a specific model or all models.

```python
def get_model_usage(
    self,
    model_name: Optional[str] = None
) -> Dict[str, Any]
```

Returns per-model statistics including:
```python
{
    "model_name": {
        "calls": int,
        "completion_tokens": int,
        "prompt_tokens": int,
        "total_tokens": int
    }
}
```

### get_message_timing_stats

Calculate timing statistics across all messages.

```python
def get_message_timing_stats(self) -> Dict[str, Any]
```

Returns:
```python
{
    "total_latency": float,  # in milliseconds
    "average_latency": float,  # in milliseconds
    "message_count": int
}
```

### get_message_counts

Get count of messages by role.

```python
def get_message_counts(self) -> Dict[str, int]
```

Returns:
```python
{
    "system": int,
    "user": int,
    "assistant": int,
    "tool": int
}
```

### get_tool_usage

Get count of tool function calls in the thread.

```python
def get_tool_usage(self) -> Dict[str, Any]
```

Returns:
```python
{
    "tools": {
        "tool_name": call_count
    },
    "total_calls": int
}
```

### get_system_message

Get the system message from the thread if it exists.

```python
def get_system_message(self) -> Optional[Message]
```

Returns the system message from the thread, or None if no system message exists.

### get_messages_in_sequence

Get messages sorted by sequence number.

```python
def get_messages_in_sequence(self) -> List[Message]
```

Returns a list of messages sorted by their sequence number.

### to_dict

Convert thread to a dictionary suitable for JSON serialization.

```python
def to_dict(self) -> Dict[str, Any]
```

Returns:
```python
{
    "id": str,
    "title": str,
    "messages": List[Dict],  # Serialized messages
    "created_at": str,       # ISO format with timezone
    "updated_at": str,       # ISO format with timezone
    "attributes": Dict,
    "source": Optional[Dict]
}
```

## Field Validators

### ensure_timezone

Ensures all datetime fields are timezone-aware UTC.

```python
@field_validator("created_at", "updated_at", mode="before")
def ensure_timezone(cls, value: datetime) -> datetime
```

Converts naive datetime objects to UTC timezone-aware ones.

## Best Practices

1. **Message Sequencing**
   ```python
   # Messages are automatically sequenced
   thread.add_message(Message(role="system", content="..."))  # Gets sequence 0
   thread.add_message(Message(role="user", content="..."))    # Gets sequence 1
   ```

2. **System Prompts**
   ```python
   # Add system prompt safely
   thread.ensure_system_prompt("You are a helpful assistant...")
   ```

3. **Analytics**
   ```python
   # Monitor token usage
   usage = thread.get_total_tokens()
   print(f"Total tokens: {usage['overall']['total_tokens']}")
   
   # Track performance
   timing = thread.get_message_timing_stats()
   print(f"Average latency: {timing['average_latency']} ms")
   
   # Get model-specific usage
   model_usage = thread.get_model_usage("gpt-4o")
   print(f"GPT-4o calls: {model_usage['calls']}")
   
   # Track tool usage
   tool_usage = thread.get_tool_usage()
   print(f"Total tool calls: {tool_usage['total_calls']}")
   ```

4. **Message Organization**
   ```python
   # Get messages in sequence order
   ordered_messages = thread.get_messages_in_sequence()
   
   # Get the last message from a specific role
   last_assistant_msg = thread.get_last_message_by_role("assistant")
   
   # Get the system message
   system_msg = thread.get_system_message()
   ```

5. **Source Tracking**
   ```python
   thread = Thread(
       source={
           "name": "slack",
           "channel": "C123",
           "thread_ts": "1234567890.123"
       }
   )
   ```

## See Also

- [Agent API](./agent.md)
- [Message API](./message.md)
- [Core Concepts](../core-concepts.md) 