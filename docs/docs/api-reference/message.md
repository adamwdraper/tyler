---
sidebar_position: 3
---

# Message API

The `Message` class represents individual interactions within a thread. It handles text and multimodal content, attachments, metrics, and metadata for each message in a conversation.

## Initialization

```python
from tyler import Message
from datetime import datetime, UTC

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

# Message with file attachment
message = Message(
    role="assistant",
    content="Here's the analysis",
    file_content=pdf_bytes,  # Raw file bytes
    filename="document.pdf"  # Will be automatically converted to attachment
)

# Tool message
message = Message(
    role="tool",
    name="weather_tool",
    content='{"temperature": 72}',
    tool_call_id="call_123"  # Required for tool messages
)

# Message with source and attributes
message = Message(
    role="user",
    content="Hello!",
    source={
        "entity": {
            "id": "U123456",
            "name": "John Doe",
            "type": "user"
        },
        "platform": {
            "name": "slack",
            "attributes": {
                "thread_ts": "1234567890.123456"
            }
        }
    },
    attributes={"customer_id": "456"}
)
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | str | No | Auto-generated | Unique message identifier (SHA-256 hash of content) |
| `role` | Literal["system", "user", "assistant", "tool"] | Yes | None | Message role |
| `sequence` | Optional[int] | No | None | Message sequence in thread (0 for system, incremental for others) |
| `content` | Optional[Union[str, List[Union[TextContent, ImageContent]]]] | No | None | Message content (text or multimodal) |
| `name` | Optional[str] | No | None | Tool name (for tool messages) |
| `tool_call_id` | Optional[str] | No | None | Tool call ID (required for tool messages) |
| `tool_calls` | Optional[list] | No | None | Tool calls (for assistant messages) |
| `attributes` | Dict | No | {} | Custom metadata |
| `timestamp` | datetime | No | now(UTC) | Message timestamp |
| `source` | Optional[MessageSource] | No | None | Source information (see MessageSource structure) |
| `attachments` | List[Attachment] | No | [] | File attachments |
| `metrics` | Dict[str, Any] | No | Default metrics | Message metrics and analytics |
| `reactions` | Dict[str, List[str]] | No | {} | Map of emoji to list of user IDs who reacted |

### Source Structure

```python
# TypedDict definitions for source structure
class PlatformSource(TypedDict, total=False):
    name: str  # Name of the platform (slack, discord, etc.)
    attributes: Optional[Dict[str, Any]]  # Platform-specific attributes

class EntitySource(TypedDict, total=False):
    id: str  # Unique identifier for the entity
    name: str  # Human-readable name of the entity
    type: Literal["user", "agent", "tool"]  # Type of entity
    attributes: Optional[Dict[str, Any]]  # All other entity-specific attributes

class MessageSource(TypedDict, total=False):
    entity: Optional[EntitySource]  # Information about the entity that created the message
    platform: Optional[PlatformSource]  # Information about the platform where the message was created
```

### Content Types

```python
# TypedDict definitions for content types
class ImageUrl(TypedDict):
    url: str

class ImageContent(TypedDict):
    type: Literal["image_url"]
    image_url: ImageUrl

class TextContent(TypedDict):
    type: Literal["text"]
    text: str
```

### Metrics Structure

```python
{
    "model": None,          # Model used for generation
    "timing": {
        "started_at": None, # Start timestamp
        "ended_at": None,   # End timestamp
        "latency": 0        # Processing time in milliseconds
    },
    "usage": {
        "completion_tokens": 0,
        "prompt_tokens": 0,
        "total_tokens": 0
    },
    "weave_call": {
        "id": "",          # Weave trace ID
        "ui_url": ""       # Weave UI URL
    }
}
```

### Reactions Structure

```python
{
    ":thumbsup:": ["user1", "user2"],  # Emoji shortcode -> list of user IDs
    ":heart:": ["user1"],
    ":rocket:": ["user3"]
}
```

## Methods

### model_dump

Convert message to a dictionary suitable for JSON serialization.

```python
def model_dump(self, mode: str = "json") -> Dict[str, Any]
```

Parameters:
- `mode`: Serialization mode, either "json" or "python"
  - "json": Converts datetimes to ISO strings (default)
  - "python": Keeps datetimes as datetime objects

Returns a complete dictionary representation including:
```python
{
    "id": str,
    "role": str,
    "sequence": int,
    "content": Union[str, List],
    "name": Optional[str],
    "tool_call_id": Optional[str],
    "tool_calls": Optional[List],
    "timestamp": str,        # ISO format with timezone (if mode="json")
    "source": Optional[Dict],
    "metrics": Dict,
    "attributes": Dict,
    "attachments": Optional[List[Dict]],  # Serialized attachments
    "reactions": Dict[str, List[str]]     # Map of emoji to user IDs
}
```

For attachments, each attachment is serialized as:
```python
{
    "filename": str,
    "mime_type": str,
    "file_id": Optional[str],
    "storage_path": Optional[str],
    "storage_backend": Optional[str],
    "status": str,  # "pending", "stored", or "failed"
    "attributes": Optional[Dict]  # Processed content and metadata
}
```

The `attributes` field contains file-specific information such as extracted text, image analysis, or parsed JSON data, depending on the file type.

### to_chat_completion_message

Return message in the format expected by chat completion APIs.

```python
def to_chat_completion_message(self, file_store: Optional[FileStore] = None) -> Dict[str, Any]
```

Parameters:
- `file_store`: Optional FileStore instance for accessing file URLs

Returns:
```python
{
    "role": str,
    "content": str,
    "sequence": int,
    "name": Optional[str],        # For tool messages
    "tool_calls": Optional[List], # For assistant messages
    "tool_call_id": Optional[str] # For tool messages
}
```

For messages with attachments:
- User and tool messages: Adds file references to content
- Assistant messages: Adds "Generated Files:" section with file references

### add_attachment

Add an attachment to the message.

```python
def add_attachment(
    self,
    attachment: Union[Attachment, bytes],
    filename: Optional[str] = None
) -> None
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `attachment` | Union[Attachment, bytes] | Yes | None | Attachment object or raw bytes |
| `filename` | Optional[str] | With bytes | None | Required when attachment is bytes |

#### Examples

```python
# Add using raw bytes
message.add_attachment(pdf_bytes, filename="document.pdf")

# Add using Attachment object
attachment = Attachment(filename="data.json", content=json_bytes)
message.add_attachment(attachment)
```

### add_reaction

Add a reaction to a message.

```python
def add_reaction(
    self,
    emoji: str,
    user_id: str
) -> bool
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `emoji` | str | Yes | None | Emoji shortcode (e.g., ":thumbsup:") |
| `user_id` | str | Yes | None | ID of the user adding the reaction |

#### Returns

`True` if reaction was added, `False` if it already existed.

#### Example

```python
# Add a thumbs up reaction from user1
message.add_reaction(":thumbsup:", "user123")
```

### remove_reaction

Remove a reaction from a message.

```python
def remove_reaction(
    self,
    emoji: str,
    user_id: str
) -> bool
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `emoji` | str | Yes | None | Emoji shortcode (e.g., ":thumbsup:") |
| `user_id` | str | Yes | None | ID of the user removing the reaction |

#### Returns

`True` if reaction was removed, `False` if it didn't exist.

#### Example

```python
# Remove a heart reaction from user1
message.remove_reaction(":heart:", "user123")
```

### get_reactions

Get all reactions for this message.

```python
def get_reactions(self) -> Dict[str, List[str]]
```

#### Returns

Dictionary mapping emoji to list of user IDs who reacted with that emoji.

#### Example

```python
reactions = message.get_reactions()
# Example result: {":thumbsup:": ["user123", "user789"], ":heart:": ["user456"]}
```

### get_reaction_counts

Get counts of reactions for this message.

```python
def get_reaction_counts(self) -> Dict[str, int]
```

#### Returns

Dictionary mapping emoji to count of reactions.

#### Example

```python
counts = message.get_reaction_counts()
# Example result: {":thumbsup:": 2, ":heart:": 1}
```

### _serialize_tool_calls

Helper method to serialize tool calls into a JSON-friendly format.

```python
def _serialize_tool_calls(self, tool_calls) -> Optional[List[Dict]]
```

Handles various tool call formats:
- OpenAI response objects with model_dump or to_dict methods
- Objects with direct attribute access
- Dictionary representations
- Returns None if no valid tool calls are found

## Working with Attachments

The `Message` class provides seamless integration with the `Attachment` model for handling files in conversations.

### Attachment Storage Flow

When a message with attachments is added to a thread and saved:

1. The `ThreadStore.save()` method triggers processing of all attachments
2. Each attachment's `process_and_store()` method is called
3. The attachment content is analyzed and processed based on file type
4. The file is stored in the configured storage backend
5. The attachment's metadata is updated:
   - `status` changes from "pending" to "stored"
   - `file_id` and `storage_path` are set
   - `attributes` is populated with file-specific information

### Attachment Types and Processing

Different file types receive specialized processing:

| File Type | MIME Type | Attributes Added |
|-----------|-----------|-----------------|
| Images | image/* | type, overview, text (OCR), analysis |
| Documents | application/pdf | type, text (extracted), overview |
| Text | text/* | type, preview, text |
| JSON | application/json | type, overview, parsed_content |
| Audio | audio/* | type, description |
| Other | * | type, description |

### Accessing Attachment Content

```python
# Get raw content bytes
content_bytes = await attachment.get_content_bytes()

# Access processed attributes
if attachment.attributes:
    # Common attributes
    file_type = attachment.attributes.get("type")
    url = attachment.attributes.get("url")
    
    # Type-specific attributes
    if file_type == "image":
        text = attachment.attributes.get("text")  # OCR text
        overview = attachment.attributes.get("overview")  # Description
    elif file_type == "document":
        text = attachment.attributes.get("text")  # Extracted text
    elif file_type == "json":
        parsed = attachment.attributes.get("parsed_content")  # Parsed JSON
```

### Attachment URLs

The Message model automatically handles attachment URLs when converting to chat completion format:

```python
# Get chat completion format
chat_message = message.to_chat_completion_message()

# For messages with attachments, URLs are included in the content
# Example: [File: /files/path/to/file.pdf (application/pdf)]
```

The URL is retrieved from:
1. `attachment.attributes["url"]` if available
2. Constructed from `attachment.storage_path` if not

## Working with Reactions

The `Message` class supports Slack-like emoji reactions, allowing multiple users to react to a message.

### Adding and Removing Reactions

```python
# Add a reaction (returns True if added, False if already existed)
message.add_reaction(":thumbsup:", "user123")
message.add_reaction(":heart:", "user456")
message.add_reaction(":thumbsup:", "user789")  # Multiple users can use same emoji

# Remove a reaction (returns True if removed, False if not found)
message.remove_reaction(":heart:", "user456")
```

### Getting Reactions and Counts

```python
# Get all reactions (emoji -> list of user IDs)
reactions = message.get_reactions()
# Example: {":thumbsup:": ["user123", "user789"], ":heart:": ["user456"]}

# Get reaction counts (emoji -> count)
counts = message.get_reaction_counts()
# Example: {":thumbsup:": 2, ":heart:": 1}

# Check if a specific user reacted with an emoji
has_reaction = "user123" in message.reactions.get(":thumbsup:", [])
```

### Reactions and Serialization

Reactions are automatically included in serialized messages:

```python
# Serialize message including reactions
data = message.model_dump()
# data["reactions"] will contain {":thumbsup:": ["user123", "user789"], ...}

# Deserialize message with reactions
new_message = Message.model_validate(data)
```

## Field Validators

### ensure_timezone

Ensures timestamp is timezone-aware UTC.

```python
@field_validator("timestamp", mode="before")
def ensure_timezone(cls, value: datetime) -> datetime
```

### validate_role

Validate role field.

```python
@field_validator("role")
def validate_role(cls, v: str) -> str
```

Ensures role is one of: system, user, assistant, tool

### validate_tool_message

Validate tool message requirements.

```python
@model_validator(mode='after')
def validate_tool_message(self) -> 'Message'
```

Ensures tool messages have required tool_call_id

### validate_tool_calls

Validate tool_calls field structure.

```python
@field_validator("tool_calls")
def validate_tool_calls(cls, v: list) -> list
```

Ensures tool calls have proper structure with id, type, and function fields

### validate_source

Validate source field structure.

```python
@field_validator("source")
def validate_source(cls, v) -> Optional[Dict]
```

Ensures the source field has the correct structure with valid entity type if present.

## Best Practices

1. **Message Sequencing**
   ```python
   # System messages get sequence 0
   system_msg = Message(role="system", content="System prompt")
   thread.add_message(system_msg)  # Gets sequence 0
   
   # Other messages get incremental sequences
   user_msg = Message(role="user", content="Hello")
   thread.add_message(user_msg)    # Gets sequence 1
   ```

2. **File Handling**
   ```python
   # Add file during creation
   message = Message(
       content="Here's a file",
       file_content=bytes_data,
       filename="document.pdf"
   )
   
   # Or add after creation
   message.add_attachment(bytes_data, filename="data.pdf")
   
   # Add attachment with explicit attributes
   attachment = Attachment(
       filename="image.jpg",
       content=image_bytes,
       mime_type="image/jpeg",
       attributes={
           "type": "image",
           "overview": "A landscape photograph"
       }
   )
   message.add_attachment(attachment)
   
   # Let ThreadStore handle attachment storage
   thread.add_message(message)
   await thread_store.save(thread)  # Will process and store attachments
   ```

3. **Tool Messages**
   ```python
   # Tool messages require tool_call_id
   tool_msg = Message(
       role="tool",
       name="web_search",
       content="Search results...",
       tool_call_id="call_123"
   )
   ```

4. **Metrics Tracking**
   ```python
   # Update metrics after processing
   message.metrics.update({
       "model": "gpt-4.1",
       "timing": {
           "started_at": start_time,
           "ended_at": end_time,
           "latency": latency_ms  # in milliseconds
       },
       "usage": {
           "completion_tokens": response.usage.completion_tokens,
           "prompt_tokens": response.usage.prompt_tokens,
           "total_tokens": response.usage.total_tokens
       }
   })
   ```

5. **Source Attribution**
   ```python
   # Using detailed source attribution
   message = Message(
       role="user",
       content="Hello",
       source={
           "entity": {
               "id": "U123456",
               "name": "John Doe",
               "type": "user",
               "attributes": {
                   "email": "john@example.com"
               }
           },
           "platform": {
               "name": "slack",
               "attributes": {
                   "channel_id": "C123456",
                   "thread_ts": "1234567890.123456"
               }
           }
       }
   )
   ```

6. **Attachment URL Handling**
   ```python
   # The Message model automatically handles attachment URLs in chat completions
   # When converting a message to chat completion format:
   chat_message = message.to_chat_completion_message(file_store)
   ```

7. **Using Reactions**
   ```python
   # Add reactions from users
   message.add_reaction(":thumbsup:", "user123")
   message.add_reaction(":thumbsup:", "user456")  # Multiple users can use same emoji
   message.add_reaction(":heart:", "user123")     # Users can add multiple reactions
   
   # Get reaction counts for display
   counts = message.get_reaction_counts()
   if ":thumbsup:" in counts:
       print(f"👍 {counts[':thumbsup:']}")  # Display: 👍 2
   
   # Remove a reaction
   message.remove_reaction(":thumbsup:", "user123")
   ```

## Reactions

Messages in a thread can receive emoji reactions from users. These reactions are stored as part of the message's metadata and provide a way for users to express sentiment without creating new messages.

### Reaction Structure

Reactions to a message are stored in a dictionary format where:
- Keys are emoji strings (e.g., `:heart:`, `:thumbsup:`)
- Values are lists of user IDs who reacted with that emoji

Example of the internal reaction structure:

```python
message.reactions = {
    ":heart:": ["user123", "user456"],
    ":thumbsup:": ["user789", "user123"]
}
```

### Accessing Reactions

While reactions are stored within the message object, they are typically managed through the Thread API, which provides methods for adding, removing, and querying reactions:

```python
# Add a reaction to this message
thread.add_reaction(message.id, ":heart:", "user123")

# Get all reactions for this message
reactions = thread.get_reactions(message.id)

# Remove a reaction
thread.remove_reaction(message.id, ":heart:", "user123")
```

### Displaying Reactions

When rendering messages in a UI, you can access the message's reactions to display them:

```python
# Get a message from a thread
message = thread.messages[0]

# Access reactions
if hasattr(message, 'reactions') and message.reactions:
    for emoji, users in message.reactions.items():
        print(f"{emoji}: {len(users)} reactions")
```

### Reaction Events

When reactions are added or removed, the message object itself doesn't emit events. Instead, listen for reaction events at the thread level:

```python
# Example of listening for reaction events on a thread
def on_reaction_added(message_id, emoji, user_id):
    print(f"User {user_id} reacted with {emoji} to message {message_id}")

thread.on("reaction_added", on_reaction_added)
```

## See Also

- [Thread API](./thread.md)
- [Attachment API](./attachment.md)
- [Core Concepts](../core-concepts.md) 