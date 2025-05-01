---
sidebar_position: 6
---

# ThreadStore API

The `ThreadStore` class provides a unified interface for thread storage with pluggable backends. It supports both in-memory storage for development/testing and SQL backends (PostgreSQL and SQLite) for production use.

## Initialization

```python
from tyler import ThreadStore

# RECOMMENDED: Factory pattern for immediate connection validation
# PostgreSQL
store = await ThreadStore.create("postgresql+asyncpg://user:pass@localhost/dbname")

# SQLite
store = await ThreadStore.create("sqlite+aiosqlite:///path/to/db.sqlite")

# In-memory
store = await ThreadStore.create()  # No URL for memory backend

# For backward compatibility: Direct constructor (connects on first operation)
store = ThreadStore("postgresql+asyncpg://user:pass@localhost/dbname")
```

The factory pattern immediately connects to the database, allowing you to:
- Validate connection parameters early
- Fail fast if there are connection problems
- Ensure the store is fully ready to use

### Connection Pooling Configuration

Environment variables for connection pooling:
```bash
# Connection pool settings
TYLER_DB_POOL_SIZE=5       # Max number of connections to keep open
TYLER_DB_MAX_OVERFLOW=10   # Max additional connections above pool_size
TYLER_DB_POOL_TIMEOUT=30   # Seconds to wait for a connection from pool
TYLER_DB_POOL_RECYCLE=300  # Seconds after which a connection is recycled
```

## Methods

### initialize

Initialize the storage backend.

```python
async def initialize(self) -> None
```

Initializes the underlying storage backend. Called automatically by the factory method or on first operation if using the direct constructor.

### save

Save a thread to storage, filtering out system messages.

```python
async def save(self, thread: Thread) -> Thread
```

Creates or updates thread and all non-system messages. System messages are never saved because they are ephemeral and injected by agents at completion time.

Example:
```python
thread = Thread()
thread.add_message(Message(role="user", content="Hello"))
saved_thread = await store.save(thread)
```

### get

Get a thread by ID.

```python
async def get(self, thread_id: str) -> Optional[Thread]
```

Returns thread with all messages if found, None otherwise.

Example:
```python
thread = await store.get("thread_123")
if thread:
    print(f"Found {len(thread.messages)} messages")
```

### delete

Delete a thread by ID.

```python
async def delete(self, thread_id: str) -> bool
```

Returns True if thread was deleted, False if not found.

Example:
```python
if await store.delete("thread_123"):
    print("Thread deleted")
```

### list

List threads with pagination.

```python
async def list(
    self,
    limit: int = 100,
    offset: int = 0
) -> List[Thread]
```

Returns threads sorted by updated_at/created_at.

Example:
```python
# Get first page
threads = await store.list(limit=50, offset=0)

# Get next page
next_page = await store.list(limit=50, offset=50)
```

### find_by_attributes

Find threads by matching attributes.

```python
async def find_by_attributes(
    self,
    attributes: Dict[str, Any]
) -> List[Thread]
```

Returns threads where all specified attributes match.

Example:
```python
threads = await store.find_by_attributes({
    "customer_id": "123",
    "priority": "high"
})
```

### find_by_source

Find threads by source name and properties.

```python
async def find_by_source(
    self,
    source_name: str,
    properties: Dict[str, Any]
) -> List[Thread]
```

Returns threads matching source name and properties.

Example:
```python
threads = await store.find_by_source(
    "slack",
    {
        "channel": "C123",
        "thread_ts": "1234567890.123"
    }
)
```

### list_recent

List recent threads.

```python
async def list_recent(
    self,
    limit: Optional[int] = None
) -> List[Thread]
```

Returns threads sorted by updated_at/created_at (newest first).

Example:
```python
# Get 10 most recent threads
recent = await store.list_recent(limit=10)
```

## Properties

### database_url

Get the database URL if using SQL backend.

```python
@property
def database_url(self) -> Optional[str]
```

Returns the database URL or None for memory backend.

### engine

Get the SQLAlchemy engine if using SQL backend.

```python
@property
def engine(self) -> Optional[Any]
```

Returns the SQLAlchemy engine or None for memory backend.

## Backend Types

### MemoryBackend

In-memory storage for development and testing.

```python
# Uses memory backend by default when no configuration is provided
store = await ThreadStore.create()  # No URL creates memory backend
```

### SQLBackend

SQL-based storage for production use.

```python
# PostgreSQL
store = await ThreadStore.create("postgresql+asyncpg://user:pass@localhost/dbname")

# SQLite
store = await ThreadStore.create("sqlite+aiosqlite:///path/to/db.sqlite")
```

## System Message Handling

System messages are never saved by the `ThreadStore`. This is by design:

1. System messages are ephemeral and controlled by agents
2. Each agent can inject its own system message at completion time
3. This allows the same thread to be used by different agents with different system prompts
4. When a thread is retrieved from storage, any system messages will need to be added again by the agent

```python
# System messages are never saved
thread = Thread()
thread.add_message(Message(role="system", content="You are an assistant"))
thread.add_message(Message(role="user", content="Hello"))
await thread_store.save(thread)

# When retrieved, only the user message is present
retrieved = await thread_store.get(thread.id)
system_messages = [m for m in retrieved.messages if m.role == "system"]
print(len(system_messages))  # 0
```

## Best Practices

1. **Use Factory Pattern**
   ```python
   # Connect and validate at startup
   try:
       store = await ThreadStore.create("postgresql+asyncpg://user:pass@host/dbname")
       print("Database connection established")
   except Exception as e:
       print(f"Database connection failed: {e}")
       # Handle the error appropriately (e.g., exit application or use fallback)
   ```

2. **Backend Selection**
   ```python
   # For development/testing
   store = await ThreadStore.create()  # In-memory
   
   # For local development with persistence
   store = await ThreadStore.create("sqlite+aiosqlite:///app.db")
   
   # For production
   store = await ThreadStore.create("postgresql+asyncpg://user:pass@host/dbname")
   ```

3. **Error Handling**
   ```python
   try:
       # Connect at startup for early error detection
       store = await ThreadStore.create("postgresql+asyncpg://user:pass@host/dbname")
   except Exception as e:
       print(f"Database connection failed: {e}")
       # Handle startup error
       
   try:
       # Handle operation errors
       thread = await store.get(thread_id)
   except Exception as e:
       print(f"Database operation error: {e}")
       # Handle operation error
   ```

4. **Batch Operations**
   ```python
   # Use pagination for large datasets
   async def process_all_threads():
       offset = 0
       while True:
           threads = await store.list(limit=100, offset=offset)
           if not threads:
               break
           for thread in threads:
               await process_thread(thread)
           offset += 100
   ```

5. **Source Management**
   ```python
   # Track external sources
   thread = Thread(
       source={
           "name": "slack",
           "channel": "C123",
           "thread_ts": "123.456"
       }
   )
   await store.save(thread)
   
   # Find related threads
   related = await store.find_by_source(
       "slack",
       {"channel": "C123"}
   )
   ```

6. **System Message Awareness**
   ```python
   # Remember that system messages aren't stored
   agent = Agent(thread_store=store)
   
   # When retrieving a thread, the agent will need to add its system message
   thread = await store.get(thread_id)
   
   # The agent adds its own system message before processing
   await agent.go(thread)
   ```

## See Also

- [Thread API](./thread.md)
- [Message API](./message.md)
- [Agent API](./agent.md)

## Storing Threads with Reactions

When threads with reactions are stored, all reaction data is automatically saved as part of the thread's state. This includes:

1. Which users have reacted to which messages
2. The specific emoji reactions used
3. The association between message IDs and their reactions

### Reaction Persistence

Reactions are stored as part of the thread's metadata and are automatically handled during save and load operations:

```python
# Create a thread and add reactions
thread = Thread()
thread.add_message("Hello, world!", "user1")
message_id = thread.messages[0].id
thread.add_reaction(message_id, ":heart:", "user2")
thread.add_reaction(message_id, ":thumbsup:", "user3")

# Save the thread with reactions
thread_store = InMemoryThreadStore()
thread_id = thread_store.save_thread(thread)

# Later, retrieve the thread with all reactions intact
loaded_thread = thread_store.get_thread(thread_id)

# The reactions are still available
reactions = loaded_thread.get_reactions(message_id)
print(reactions)  # Output: {":heart:": ["user2"], ":thumbsup:": ["user3"]}
```

### Reaction Storage Format

When implementing a custom ThreadStore, be aware that reactions are stored in the following format within the thread's data structure:

```json
{
  "messages": [...],
  "reactions": {
    "message_id_1": {
      ":emoji1:": ["user_id1", "user_id2"],
      ":emoji2:": ["user_id3"]
    },
    "message_id_2": {
      ":emoji3:": ["user_id1"]
    }
  }
}
```

Custom storage implementations should preserve this structure to ensure reactions are correctly maintained.

## Database Schema

The ThreadStore uses the following tables internally:

- `threads`: Stores thread metadata (id, title, created_at, updated_at, attributes, source)
- `messages`: Stores message data (id, thread_id, role, content, sequence, created_at, updated_at, token_count, attributes)
- `message_files`: Stores file attachment metadata for messages
- `message_reactions`: Stores user reactions to messages (message_id, emoji, user_id)

## Best Practices

1. **Connection Management**
   ```python
   # The ThreadStore manages its own connection pool
   thread_store = ThreadStore("threads.db")
   
   # No need to manually close connections
   # The store handles connection lifecycle
   ```

2. **Batch Operations**
   ```python
   # Save multiple threads
   for thread in threads:
       await thread_store.save(thread)
   
   # Delete multiple threads
   for thread_id in thread_ids:
       await thread_store.delete(thread_id)
   ```

3. **Efficient Queries**
   ```python
   # Use list_threads for pagination
   first_page, total = await thread_store.list_threads(limit=10)
   second_page, _ = await thread_store.list_threads(offset=10, limit=10)
   
   # Use search_threads for full-text search
   results, _ = await thread_store.search_threads("important")
   ```

4. **Working with Sources**
   ```python
   # Create a thread with source information
   thread = Thread(
       source={
           "name": "slack",
           "channel": "C123",
           "thread_ts": "1234567890.123"
       }
   )
   await thread_store.save(thread)
   
   # Later, find the thread by source
   thread = await thread_store.get_by_source("slack", "1234567890.123")
   ```

5. **Working with Reactions**
   ```python
   # Load a thread
   thread = await thread_store.get(thread_id)
   
   # Add reactions to a message
   message_id = thread.messages[0].id
   thread.add_reaction(message_id, ":thumbsup:", "user1")
   
   # Save changes
   await thread_store.save(thread)
   ```

## See Also

- [Thread API](./thread.md)
- [Message API](./message.md)
- [Storage Concepts](../core-concepts.md#storage) 