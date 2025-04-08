---
sidebar_position: 6
---

# ThreadStore API

The `ThreadStore` class provides a unified interface for thread storage with pluggable backends. It supports both in-memory storage for development/testing and SQL backends (PostgreSQL and SQLite) for production use.

## Initialization

```python
from tyler.database.thread_store import ThreadStore

# PostgreSQL
store = await ThreadStore.create("postgresql+asyncpg://user:pass@localhost/dbname")

# SQLite
store = await ThreadStore.create("sqlite+aiosqlite:///path/to/db.sqlite")

# In-memory
store = await ThreadStore.create()  # No URL for memory backend
```

The factory pattern immediately connects to the database, allowing you to:
- Validate connection parameters early
- Fail fast if there are connection problems
- Ensure the store is fully ready to use

### Configuration

Environment variables:
```bash
# Database type
TYLER_DB_TYPE=postgresql    # Use PostgreSQL backend
TYLER_DB_TYPE=sqlite        # Use SQLite backend

# PostgreSQL configuration (required when TYLER_DB_TYPE=postgresql)
TYLER_DB_HOST=localhost     # Database host
TYLER_DB_PORT=5432          # Database port
TYLER_DB_NAME=tyler         # Database name
TYLER_DB_USER=tyler_user    # Database user
TYLER_DB_PASSWORD=password  # Database password

# SQLite configuration (required when TYLER_DB_TYPE=sqlite)
TYLER_DB_PATH=/path/to/db.sqlite  # Path to SQLite database file

# Optional settings
TYLER_DB_ECHO=true          # Enable SQL logging
TYLER_DB_POOL_SIZE=10       # Connection pool size
TYLER_DB_MAX_OVERFLOW=20    # Max additional connections
```

## Methods

### save

Save a thread to storage.

```python
async def save(self, thread: Thread, file_store: Optional[FileStore] = None) -> Thread
```

Creates or updates thread and all messages. Returns saved thread. If the thread contains messages with attachments, a file_store instance must be provided to process them.

Example:
```python
thread = Thread()
thread.add_message(Message(role="user", content="Hello"))
saved_thread = await store.save(thread)

# With file attachment
message = Message(role="user", content="Here's a document")
message.add_attachment(pdf_bytes, filename="document.pdf")
thread.add_message(message)

# FileStore needed when attachments are present
file_store = await FileStore.create()
saved_thread = await store.save(thread, file_store=file_store)
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

### async_session

Get the SQLAlchemy async session factory if using SQL backend.

```python
@property
def async_session(self) -> Optional[Any]
```

Returns the SQLAlchemy async session factory or None for memory backend.

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

## Best Practices

1. **Connect at Startup**
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
   
   # Using environment variables
   # Set TYLER_DB_TYPE and other required variables
   store = await ThreadStore.create()  # Will use configured database type
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

6. **Attachment Processing**
   ```python
   # Attachments are automatically processed when saving a thread
   message = Message(role="user", content="Here's a file")
   message.add_attachment(file_bytes, filename="document.pdf")
   thread.add_message(message)
   
   # Need to create and pass a FileStore to process attachments
   file_store = await FileStore.create()
   
   # Save with file_store to process and store all attachments
   await store.save(thread, file_store=file_store)
   ```

7. **Environment Variable Configuration**
   ```python
   # Set required environment variables
   os.environ["TYLER_DB_TYPE"] = "postgresql"
   os.environ["TYLER_DB_HOST"] = "localhost"
   os.environ["TYLER_DB_PORT"] = "5432"
   os.environ["TYLER_DB_NAME"] = "tyler"
   os.environ["TYLER_DB_USER"] = "tyler_user"
   os.environ["TYLER_DB_PASSWORD"] = "password"
   
   # Create store using environment variables
   store = await ThreadStore.create()  # Will connect to PostgreSQL
   ```

## See Also

- [Thread API](./thread.md)
- [Message API](./message.md)
- [Attachment API](./attachment.md) 