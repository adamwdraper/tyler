---
sidebar_position: 5
---

# Database Storage

This example demonstrates how to use persistent database storage with Tyler, including PostgreSQL integration and metrics tracking.

## Overview

The example shows:
- Setting up PostgreSQL database storage
- Initializing and using ThreadStore
- Saving and retrieving threads
- Tracking message metrics
- Using file storage

## Code

```python
from dotenv import load_dotenv
import os
import asyncio
from tyler import Agent, Thread, Message, ThreadStore
from tyler import FileStore
import weave

# Load environment variables from .env file
load_dotenv()

# Initialize weave for tracing (optional)
if os.getenv("WANDB_API_KEY"):
    weave.init("tyler")

async def main():
    """
    Demonstrates database persistence with metrics tracking.
    Uses environment variables for database configuration.
    """
    # Construct PostgreSQL URL from environment variables
    db_url = f"postgresql+asyncpg://{os.getenv('TYLER_DB_USER')}:{os.getenv('TYLER_DB_PASSWORD')}@{os.getenv('TYLER_DB_HOST')}:{os.getenv('TYLER_DB_PORT')}/{os.getenv('TYLER_DB_NAME')}"

    # Initialize ThreadStore with PostgreSQL URL
    store = await ThreadStore.create(db_url)

    # Initialize file store
    file_store = await FileStore.create()
    print(f"Initialized file store at: {file_store.base_path}")
    
    # Create agent with database storage
    agent = Agent(
        model_name="gpt-4.1",
        purpose="To help with general questions",
        thread_store=store
    )
    
    # Create and save a new thread
    thread = Thread()
    await store.save(thread)
    
    # Add a message
    message = Message(
        role="user",
        content="What are the benefits of database storage over memory storage?"
    )
    thread.add_message(message)
    await store.save(thread)
    
    # Get response
    processed_thread, new_messages = await agent.go(thread)
    
    print("Assistant's response:")
    for message in new_messages:
        if message.role == "assistant":
            print(message.content)
            print("\nMessage metrics:")
            print(f"- Tokens: {message.metrics['completion_tokens']} completion, {message.metrics['prompt_tokens']} prompt")
            print(f"- Model: {message.metrics['model']}")
            print(f"- Latency: {message.metrics['latency']:.0f}ms")

if __name__ == "__main__":
    asyncio.run(main())
```

## Step-by-Step Explanation

### 1. Database Setup
```python
db_url = f"postgresql+asyncpg://{os.getenv('TYLER_DB_USER')}:{os.getenv('TYLER_DB_PASSWORD')}@{os.getenv('TYLER_DB_HOST')}:{os.getenv('TYLER_DB_PORT')}/{os.getenv('TYLER_DB_NAME')}"

store = await ThreadStore.create(db_url)
```
- Constructs database URL from environment variables
- Initializes ThreadStore with PostgreSQL
- Creates necessary database tables

### 2. File Storage Setup
```python
file_store = await FileStore.create()
print(f"Initialized file store at: {file_store.base_path}")
```
- Initializes file storage for attachments
- Uses default or configured storage path

### 3. Agent Configuration
```python
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with general questions",
    thread_store=store
)
```
- Creates agent with database storage
- Sets model and purpose
- Connects to thread store

### 4. Thread Management
```python
thread = Thread()
await store.save(thread)

message = Message(
    role="user",
    content="What are the benefits of database storage over memory storage?"
)
thread.add_message(message)
await store.save(thread)
```
- Creates and saves threads
- Adds messages
- Persists changes to database

## Docker Database Setup

Tyler includes a built-in Docker Compose configuration to easily set up a PostgreSQL database for development and testing.

### Prerequisites
- Docker and Docker Compose installed on your system
- Tyler installed via uv (`uv add tyler-agent`)

### Setup Steps

1. **Create Environment Variables**

   Create or update your `.env` file in your project directory with PostgreSQL configuration:
   ```bash
   # Database Configuration for Docker PostgreSQL
   TYLER_DB_TYPE=postgresql
   TYLER_DB_HOST=localhost
   TYLER_DB_PORT=5433  # Using 5433 to avoid conflicts with local PostgreSQL
   TYLER_DB_NAME=tyler
   TYLER_DB_USER=tyler
   TYLER_DB_PASSWORD=tyler_dev
   ```

2. **Create a Docker Compose File**

   Create a `docker-compose.yml` file in your project directory:
   ```yaml
   version: '3.8'

   services:
     postgres:
       image: postgres:16
       container_name: tyler-postgres
       environment:
         POSTGRES_DB: ${TYLER_DB_NAME:-tyler}
         POSTGRES_USER: ${TYLER_DB_USER:-tyler}
         POSTGRES_PASSWORD: ${TYLER_DB_PASSWORD:-tyler_dev}
       ports:
         - "${TYLER_DB_PORT:-5433}:5432"
       volumes:
         - postgres_data:/var/lib/postgresql/data
       healthcheck:
         test: ["CMD-SHELL", "pg_isready -U ${TYLER_DB_USER:-tyler}"]
         interval: 5s
         timeout: 5s
         retries: 5

   volumes:
     postgres_data:
   ```

3. **Start PostgreSQL with Docker**

   Start the PostgreSQL container using Docker Compose:
   ```bash
   # Start the PostgreSQL container
   docker-compose up -d
   ```

   This command will:
   - Create a Docker container named `tyler-postgres` running PostgreSQL 16
   - Configure it with the credentials from your environment variables
   - Map the PostgreSQL port to your local machine
   - Create a persistent volume for your data

4. **Initialize the Database**

   After starting the container, initialize the database schema using the Narrator CLI:
   ```bash
   # Initialize the database schema
   narrator-db init --database-url "postgresql+asyncpg://tyler:tyler_dev@localhost:5433/tyler"
   ```

5. **Verify Connection**

   You can test your database connection using:
   ```bash
   # Check database status
   narrator-db status --database-url "postgresql+asyncpg://tyler:tyler_dev@localhost:5433/tyler"
   ```

### Additional Database Commands

The Narrator provides CLI commands for database management:

```bash
# Initialize database with specific URL
narrator-db init --database-url "postgresql+asyncpg://user:pass@localhost:5432/dbname"

# Check database status
narrator-db status --database-url "postgresql+asyncpg://user:pass@localhost:5432/dbname"
```

### Additional Docker Commands

- **View Container Status**
  ```bash
  docker ps
  ```

- **Stop the Container**
  ```bash
  docker-compose down
  ```

- **View Container Logs**
  ```bash
  docker logs tyler-postgres
  ```

## Configuration Requirements

### Environment Variables
```bash
# Database Configuration
TYLER_DB_TYPE=postgresql
TYLER_DB_HOST=localhost
TYLER_DB_PORT=5432
TYLER_DB_NAME=tyler
TYLER_DB_USER=tyler
TYLER_DB_PASSWORD=tyler_dev

# Optional Database Settings
TYLER_DB_ECHO=false
TYLER_DB_POOL_SIZE=5
TYLER_DB_MAX_OVERFLOW=10
TYLER_DB_POOL_TIMEOUT=30
TYLER_DB_POOL_RECYCLE=1800

# File Storage Configuration
TYLER_FILE_STORAGE_TYPE=local
TYLER_FILE_STORAGE_PATH=/path/to/files

# Monitoring
WANDB_API_KEY=your-wandb-api-key
```

## Expected Output

When you run this example, you'll see output similar to:

```
Initialized file store at: /Users/username/.tyler/files

Assistant's response:
Database storage offers several advantages over in-memory storage:
1. Persistence across sessions
2. Scalability for large datasets
3. Concurrent access support
4. Data integrity and recovery
5. Query and filtering capabilities

Message metrics:
- Tokens: 128 completion, 84 prompt
- Model: gpt-4.1
- Latency: 450ms
```

## Key Concepts

1. **Database Storage**
   - Thread persistence
   - Message history
   - Concurrent access
   - Data integrity

2. **File Storage**
   - Attachment handling
   - File organization
   - Path management

3. **Metrics Tracking**
   - Token usage
   - Model performance
   - Response latency

4. **Environment Configuration**
   - Database settings
   - Connection pooling
   - Storage paths

## Common Customizations

### SQLite Storage
```python
store = await ThreadStore.create("sqlite:///path/to/database.db")
```

### Custom File Storage
```python
from tyler import FileStore

store = await FileStore.create(
    base_path="/path/to/files"
)
``` 