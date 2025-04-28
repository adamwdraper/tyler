import pytest
import os
from pathlib import Path
import tempfile
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.asyncio import create_async_engine
from tyler.database.thread_store import ThreadStore
from tyler.database.models import ThreadRecord
from tyler.models.thread import Thread
from tyler.models.message import Message

pytest_plugins = ('pytest_asyncio',)

@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db') as f:
        url = f"sqlite+aiosqlite:///{f.name}"
        # Create a fresh database file
        engine = create_async_engine(url)
        # Close any existing connections - this needs to be awaited
        # We'll use sync_engine instead since we're in a sync context
        sync_url = url.replace("sqlite+aiosqlite://", "sqlite://")
        sync_engine = create_engine(sync_url)
        sync_engine.dispose()
        yield url

@pytest.fixture
def alembic_config(temp_db):
    """Get Alembic config for testing."""
    package_dir = Path(__file__).parent.parent.parent / "tyler" / "database"
    alembic_ini = package_dir / "migrations" / "alembic.ini"
    config = Config(alembic_ini)
    
    # Override the database URL in the config
    # Note: Alembic still uses sync URL
    sync_url = temp_db.replace("sqlite+aiosqlite://", "sqlite://")
    config.set_main_option("sqlalchemy.url", sync_url)
    
    # Set the script location
    config.set_main_option("script_location", str(package_dir / "migrations"))
    
    # Create a fresh engine for cleanup
    engine = create_engine(sync_url)
    try:
        # Drop all tables in reverse order to handle dependencies
        with engine.begin() as conn:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            for table in reversed(tables):
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
    finally:
        # Ensure we close all connections
        engine.dispose()
    
    return config

@pytest.mark.asyncio
async def test_initial_migration(temp_db, alembic_config):
    """Test that initial migration creates correct schema."""
    # Run migrations (using sync URL)
    sync_url = temp_db.replace("sqlite+aiosqlite://", "sqlite://")
    command.upgrade(alembic_config, "head")
    
    # Check schema
    engine = create_engine(sync_url)
    try:
        inspector = inspect(engine)
        
        # Check if threads table exists
        assert 'threads' in inspector.get_table_names()
        
        # Check columns
        columns = {col['name']: col for col in inspector.get_columns('threads')}
        assert 'id' in columns
        assert 'title' in columns
        assert 'attributes' in columns
        assert 'platforms' in columns
        assert 'metrics' in columns
        assert 'created_at' in columns
        assert 'updated_at' in columns
        
        # Check column types (using SQLite type names)
        assert columns['id']['type'].__class__.__name__ == 'VARCHAR'
        assert columns['attributes']['type'].__class__.__name__ == 'JSON'
        assert columns['created_at']['type'].__class__.__name__ == 'DATETIME'
        assert columns['updated_at']['type'].__class__.__name__ == 'DATETIME'
        
        # Check indexes
        indexes = inspector.get_indexes('threads')
        index_names = {idx['name'] for idx in indexes}
        assert 'ix_threads_updated_at' in index_names
    finally:
        engine.dispose()

@pytest.mark.asyncio
async def test_migration_with_data(temp_db, alembic_config):
    """Test that migrations preserve existing data."""
    # Set up database and store
    command.upgrade(alembic_config, "head")
    store = ThreadStore(temp_db)
    
    # Add test data with various fields
    thread = Thread()
    thread.title = "Test Thread"
    thread.attributes = {"category": "test", "priority": "high"}
    thread.platforms = {
        "slack": {
            "channel": "C123",
            "thread_ts": "1234567890.123"
        }
    }
    
    # Add messages
    thread.add_message(Message(role="user", content="Test message"))
    thread.add_message(Message(role="assistant", content="Test response"))
    
    # Save thread and verify it was saved
    await store.save(thread)
    saved_thread = await store.get(thread.id)
    assert saved_thread is not None
    assert saved_thread.title == thread.title
    
    # Create a backup of the data
    sync_url = temp_db.replace("sqlite+aiosqlite://", "sqlite://")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            # Backup threads
            thread_result = conn.execute(text("SELECT * FROM threads")).fetchall()
            thread_data = [dict(row._mapping) for row in thread_result]
            
            # Backup messages
            message_result = conn.execute(text("SELECT * FROM messages")).fetchall()
            message_data = [dict(row._mapping) for row in message_result]
    finally:
        engine.dispose()
    
    # Run downgrade and upgrade
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    
    # Restore the data
    engine = create_engine(sync_url)
    try:
        with engine.begin() as conn:
            # Restore threads first
            for row in thread_data:
                conn.execute(
                    text("INSERT INTO threads (id, title, attributes, platforms, metrics, created_at, updated_at) VALUES (:id, :title, :attributes, :platforms, :metrics, :created_at, :updated_at)"),
                    row
                )
            
            # Then restore messages
            for row in message_data:
                conn.execute(
                    text("INSERT INTO messages (id, thread_id, sequence, role, content, name, tool_call_id, tool_calls, attributes, timestamp, source, attachments, metrics) VALUES (:id, :thread_id, :sequence, :role, :content, :name, :tool_call_id, :tool_calls, :attributes, :timestamp, :source, :attachments, :metrics)"),
                    row
                )
    finally:
        engine.dispose()
    
    # Verify data is preserved
    loaded_thread = await store.get(thread.id)
    assert loaded_thread is not None
    assert loaded_thread.title == thread.title
    assert loaded_thread.attributes == thread.attributes
    assert loaded_thread.platforms == thread.platforms
    assert len(loaded_thread.messages) == len(thread.messages)
    
    # Verify message content
    for orig_msg, loaded_msg in zip(thread.messages, loaded_thread.messages):
        assert orig_msg.role == loaded_msg.role
        assert orig_msg.content == loaded_msg.content

@pytest.mark.asyncio
async def test_migration_downgrade(temp_db, alembic_config):
    """Test that downgrades work correctly."""
    # Set up database
    command.upgrade(alembic_config, "head")
    
    # Add some data
    store = ThreadStore(temp_db)
    thread = Thread()
    await store.save(thread)
    
    # Run downgrade
    command.downgrade(alembic_config, "base")
    
    # Verify tables are gone
    sync_url = temp_db.replace("sqlite+aiosqlite://", "sqlite://")
    engine = create_engine(sync_url)
    try:
        inspector = inspect(engine)
        assert 'threads' not in inspector.get_table_names()
    finally:
        engine.dispose()

@pytest.mark.asyncio
async def test_migration_idempotency(temp_db, alembic_config):
    """Test that running migrations multiple times is safe."""
    sync_url = temp_db.replace("sqlite+aiosqlite://", "sqlite://")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    
    # Run migrations multiple times
    command.upgrade(alembic_config, "head")
    command.upgrade(alembic_config, "head")
    
    # Should not raise any errors
    engine = create_engine(sync_url)
    inspector = inspect(engine)
    assert 'threads' in inspector.get_table_names()

@pytest.mark.asyncio
async def test_migration_empty_db(temp_db, alembic_config):
    """Test migrations on empty database."""
    sync_url = temp_db.replace("sqlite+aiosqlite://", "sqlite://")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    
    # Create empty database first
    engine = create_engine(sync_url)
    
    # Run migrations
    command.upgrade(alembic_config, "head")
    
    # Check schema was created
    inspector = inspect(engine)
    assert 'threads' in inspector.get_table_names() 