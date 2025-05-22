# Configuration guide

Tyler offers extensive configuration options to customize its behavior for your specific needs. This guide covers all available configuration options and their usage.

## Environment variables

Tyler uses environment variables for configuration. These can be set in a `.env` file or directly in your environment.

### Core settings

```bash
# LLM Provider Configuration
OPENAI_API_KEY=your-openai-api-key
# Or for other providers:
ANTHROPIC_API_KEY=your-anthropic-key
AZURE_API_KEY=your-azure-key
VERTEX_PROJECT=your-project-id

# Database Configuration
TYLER_DB_TYPE=postgresql  # or sqlite
TYLER_DB_HOST=localhost
TYLER_DB_PORT=5432
TYLER_DB_NAME=tyler
TYLER_DB_USER=tyler
TYLER_DB_PASSWORD=tyler_dev

# File Storage Configuration
TYLER_FILE_STORAGE_TYPE=local
TYLER_FILE_STORAGE_PATH=/path/to/files  # Optional, defaults to ~/.tyler/files
TYLER_MAX_FILE_SIZE=52428800  # Optional, 50MB default
TYLER_MAX_STORAGE_SIZE=5368709120  # Optional, 5GB limit
TYLER_ALLOWED_MIME_TYPES=application/pdf,image/jpeg,image/png  # Optional, comma-separated list

# Logging Configuration
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
WANDB_API_KEY=your-wandb-api-key  # For Weave monitoring
```

### Optional settings

```bash
# Database Pool Settings
TYLER_DB_ECHO=false
TYLER_DB_POOL_SIZE=5
TYLER_DB_MAX_OVERFLOW=10
TYLER_DB_POOL_TIMEOUT=30
TYLER_DB_POOL_RECYCLE=1800

# Service Integration Settings
NOTION_TOKEN=your-notion-token
SLACK_BOT_TOKEN=your-slack-bot-token
SLACK_SIGNING_SECRET=your-slack-signing-secret
```

## Agent configuration

The `Agent` class accepts various configuration options to customize its behavior:

```python
from tyler import Agent

agent = Agent(
    # Required
    model_name="gpt-4.1",  # LLM model to use
    purpose="To help with tasks",  # Agent's purpose
    
    # Optional
    temperature=0.7,  # Response creativity (0.0-1.0)
    max_tokens=1000,  # Maximum response length
    tools=[],  # List of custom tools
    system_prompt="Custom system prompt",  # Override default prompt
    attributes={},  # Custom metadata
)
```

### Available models

Tyler supports any model available through LiteLLM:

```python
# OpenAI
agent = Agent(model_name="gpt-4.1")

# Anthropic
agent = Agent(model_name="claude-2")

# Azure OpenAI
agent = Agent(model_name="azure/your-deployment-name")

# Google VertexAI
agent = Agent(model_name="chat-bison")

# AWS Bedrock
agent = Agent(model_name="anthropic.claude-v2")
```

## Storage configuration

Tyler provides flexible storage options for both database and file storage needs.

### Database storage

Tyler supports multiple database backends for storing threads and messages. The database storage is handled through the `ThreadStore` class.

#### Memory storage (Default)
```python
from tyler import ThreadStore

# Use factory pattern for immediate connection validation
store = await ThreadStore.create()  # Uses memory backend

# Used by default when creating an agent
agent = Agent(purpose="My purpose")  # Uses ThreadStore with memory backend

# Thread operations are immediate
thread = Thread()
await store.save(thread)
```

Key characteristics:
- Fastest possible performance (direct dictionary access)
- No persistence (data is lost when program exits)
- No setup required (works out of the box)
- Perfect for scripts and one-off conversations
- Great for testing and development

#### PostgreSQL storage
```python
from tyler import ThreadStore

# Use factory pattern for immediate connection validation
db_url = "postgresql+asyncpg://user:pass@localhost/dbname"
try:
    store = await ThreadStore.create(db_url)
    print("Connected to database successfully")
except Exception as e:
    print(f"Database connection failed: {e}")
    # Handle connection failure appropriately

# Create agent with database storage
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with tasks",
    thread_store=store
)

# Must save threads and changes to persist
thread = Thread()
await store.save(thread)  # Required
thread.add_message(message)
await store.save(thread)  # Save changes

# Always use thread.id with database storage
result = await agent.go(thread.id)
```

Key characteristics:
- Async operations for non-blocking I/O
- Persistent storage (data survives program restarts)
- Cross-session support (can access threads from different processes)
- Production-ready
- Automatic schema management through SQLAlchemy
- Connection validation at startup with factory pattern

#### SQLite storage
```python
from tyler import ThreadStore

# Use factory pattern for immediate connection validation
db_url = "sqlite+aiosqlite:///path/to/db.sqlite"
store = await ThreadStore.create(db_url)

# Or use in-memory SQLite database
store = await ThreadStore.create("sqlite+aiosqlite://")  # In-memory SQLite
```

#### Connection Error Handling

The factory pattern allows you to handle connection errors gracefully at startup:

```python
try:
    store = await ThreadStore.create("postgresql+asyncpg://user:pass@host/dbname")
    print("Database connection established")
except Exception as e:
    print(f"Database connection failed: {e}")
    # Options:
    # 1. Exit the application
    # 2. Fall back to a different database
    # 3. Use in-memory storage as fallback
    store = await ThreadStore.create()  # Fallback to memory storage
    print("Using in-memory storage as fallback")
```

### File storage

Tyler automatically manages file storage for attachments and files using a local file system with a sharded directory structure. The storage is configured through environment variables and is initialized automatically when needed.

Configuration options:
- `TYLER_FILE_STORAGE_TYPE`: Storage backend type (default: "local")
- `TYLER_FILE_STORAGE_PATH`: Base directory for file storage (default: ~/.tyler/files)
- `TYLER_MAX_FILE_SIZE`: Maximum allowed file size in bytes (default: 52428800 / 50MB)
- `TYLER_MAX_STORAGE_SIZE`: Maximum total storage size in bytes (default: 5368709120 / 5GB)
- `TYLER_ALLOWED_MIME_TYPES`: Comma-separated list of allowed MIME types (default: common document, image, and archive types)

#### Creating and using a FileStore instance

```python
from tyler import FileStore, Agent

# Create a FileStore instance with factory pattern
file_store = await FileStore.create(
    base_path="/path/to/files",  # Optional custom path
    max_file_size=100 * 1024 * 1024,  # 100MB (optional)
    max_storage_size=10 * 1024 * 1024 * 1024  # 10GB (optional)
)

# Or use default settings from environment variables
file_store = await FileStore.create()

# Pass the file_store instance to an Agent
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with tasks",
    thread_store=thread_store,
    file_store=file_store  # Explicitly pass file_store instance
)

# When saving a thread with attachments, the FileStore is used internally
await thread_store.save(thread)
```

The file storage system provides:

Key features:
- Automatic initialization and configuration
- Sharded directory structure for efficient organization
- File validation and MIME type detection
- Configurable size limits through environment variables
- Support for various file types:
  - Documents (PDF, Word, text, CSV, JSON)
  - Images (JPEG, PNG, GIF, WebP, SVG)
  - Archives (ZIP, TAR, GZIP)
- Secure file handling with proper permissions

## Monitoring configuration

### Weave integration

[W&B Weave](https://weave-docs.wandb.ai/) is a framework for tracking, evaluating, and improving LLM-based applications. While this is optional, you are going to want to use this to understand how your agent is performing.
```python
from tyler.monitoring import WeaveMonitor

monitor = WeaveMonitor(
    api_key="your-wandb-api-key",
    project_name="tyler-monitoring",
    entity="your-username"
)
```

## Custom tool configuration

Tyler comes with several built-in tools and supports creating custom tools. Here are some examples:

### Weather tool example
```python
weather_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City and country"
                    }
                },
                "required": ["location"]
            }
        }
    },
    "implementation": lambda location: f"Weather in {location}: Sunny",
    "attributes": {
        "type": "standard"  # or "interrupt" for interrupt tools
    }
}
```

### Slack tools
```python
from tyler.tools.slack import TOOLS as SLACK_TOOLS

agent = Agent(
    model_name="gpt-4.1",
    purpose="Slack assistant",
    tools=["slack"]  # This will load all Slack tools
)

# Required environment variables:
# SLACK_BOT_TOKEN=your-bot-token
# SLACK_SIGNING_SECRET=your-signing-secret
```

### Notion tools
```python
from tyler.tools.notion import TOOLS as NOTION_TOOLS

agent = Agent(
    model_name="gpt-4.1",
    purpose="Notion assistant",
    tools=["notion"]  # This will load all Notion tools
)

# Required environment variables:
# NOTION_TOKEN=your-notion-token
```

### Using multiple tools
```python
agent = Agent(
    model_name="gpt-4.1",
    purpose="Multi-purpose assistant",
    tools=[
        "slack",      # Include all Slack tools
        "notion",     # Include all Notion tools
        weather_tool  # Include custom weather tool
    ]
)
```

## Best practices

1. **Environment variables**
   - Use `.env` files for local development
   - Use secure secrets management in production
   - Never commit sensitive values to version control

2. **Database configuration**
   - Use connection pooling for better performance
   - Set appropriate timeouts and pool sizes
   - Use SSL in production

3. **File storage**
   - Set appropriate file size limits
   - Use secure storage in production
   - Implement proper backup strategies

4. **Monitoring**
   - Enable monitoring in production
   - Set appropriate logging levels
   - Monitor token usage and costs

5. **Security**
   - Use HTTPS for all external connections
   - Implement rate limiting
   - Follow the principle of least privilege

## Next steps

- Learn about [Core concepts](./core-concepts.md)
- Explore [API reference](./category/api-reference)
- See [Examples](./category/examples) for common configurations
