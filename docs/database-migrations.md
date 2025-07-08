# Database Migrations in Tyler

This document describes how to manage database migrations when using Tyler with the Narrator storage library.

## Running Migrations

When the Narrator is updated, you may need to run database migrations to update your database schema. The Narrator provides a dedicated CLI for database management.

### Using the Narrator CLI (Recommended)

If you installed the-narrator through pip, pypi, or uv, you can use the built-in CLI command:

```bash
# Initialize the database
narrator-db init --database-url "postgresql+asyncpg://user:pass@localhost/dbname"

# Check database status
narrator-db status --database-url "postgresql+asyncpg://user:pass@localhost/dbname"
```

You can also use environment variables instead of passing the database URL:

```bash
# Set environment variable
export NARRATOR_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/dbname"

# Then run without --database-url flag
narrator-db init
narrator-db status
```

### Using Programmatic API

You can also initialize the database from your Python code:

```python
import asyncio
from narrator import ThreadStore

async def init_database():
    # Initialize database with URL
    store = await ThreadStore.create("postgresql+asyncpg://user:pass@localhost/dbname")
    print("Database initialized successfully")

# Run initialization
asyncio.run(init_database())
```

## When to Initialize Database

You should initialize the database:

1. After installing the-narrator for the first time
2. When setting up a new environment
3. Before using database storage features

## Common Database Commands

| Command | Description |
|---------|-------------|
| `narrator-db init` | Initialize database tables |
| `narrator-db status` | Check database connection and status |

## Troubleshooting

If you encounter issues with database initialization:

1. Check your database connection settings
2. Ensure you're using the latest version of the-narrator
3. Make sure your database user has sufficient permissions
4. Check the logs for detailed error messages
5. Verify that your database server is running and accessible 