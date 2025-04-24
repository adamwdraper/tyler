# Database Migrations in Tyler

This document describes how to manage database migrations in Tyler.

## Running Migrations

When Tyler is updated, you may need to run database migrations to update your database schema. There are several ways to do this depending on how you installed Tyler.

### Using the Tyler CLI (Recommended)

If you installed Tyler through pip, pypi, or uv, you can use the built-in CLI command:

```bash
# Upgrade to latest version
tyler db upgrade

# Check current migration version
tyler db current

# View migration history
tyler db history
```

### Using the Direct Database CLI

Tyler also provides a dedicated database CLI:

```bash
tyler-db upgrade
```

### Using Programmatic API

You can also run migrations from your Python code:

```python
import asyncio
from alembic import command
from tyler.database.cli import get_alembic_config

async def run_migrations():
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, "head")

# Run migrations
asyncio.run(run_migrations())
```

## When to Run Migrations

You should run migrations:

1. After updating Tyler to a new version
2. When instructed to in the release notes
3. Before using new features that require database schema changes

## Common Migration Commands

| Command | Description |
|---------|-------------|
| `tyler db upgrade` | Update database to latest schema version |
| `tyler db downgrade` | Downgrade database by one version |
| `tyler db current` | Show current database version |
| `tyler db history` | Show migration history |
| `tyler db migrate` | Generate a new migration based on model changes (developer use) |

## Troubleshooting

If you encounter issues running migrations:

1. Check your database connection settings
2. Ensure you're using the latest version of Tyler
3. Make sure your database user has sufficient permissions
4. Check the logs for detailed error messages 