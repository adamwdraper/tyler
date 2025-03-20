import pytest
import os
from pathlib import Path
import tempfile
from datetime import datetime, UTC
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from tyler.database.thread_store import ThreadStore
from tyler.database.models import ThreadRecord
from tyler.database.storage_backend import MemoryBackend, SQLBackend
from tyler.models.thread import Thread
from tyler.models.message import Message
from tyler.database.models import Base
from tyler.models.attachment import Attachment

pytest_plugins = ('pytest_asyncio',)

@pytest.fixture
def env_vars():
    """Save and restore environment variables."""
    old_vars = {}
    for var in [
        "TYLER_DB_TYPE",
        "TYLER_DB_HOST",
        "TYLER_DB_PORT",
        "TYLER_DB_NAME",
        "TYLER_DB_USER",
        "TYLER_DB_PASSWORD",
        "TYLER_DB_PATH",
        "TYLER_DB_ECHO",
        "TYLER_DB_POOL_SIZE",
        "TYLER_DB_MAX_OVERFLOW"
    ]:
        old_vars[var] = os.environ.get(var)
    yield
    # Restore old values
    for var, value in old_vars.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value

@pytest.mark.asyncio
async def test_env_var_config_sqlite(env_vars):
    """Test ThreadStore initialization with SQLite environment variables."""
    # Set environment variables for SQLite
    os.environ.update({
        "TYLER_DB_TYPE": "sqlite",
        "TYLER_DB_PATH": ":memory:",
        "TYLER_DB_ECHO": "true"
    })
    
    # Initialize store without URL
    store = ThreadStore()
    
    # Verify SQLite URL was constructed correctly
    assert "sqlite+aiosqlite" in store.database_url
    assert ":memory:" in store.database_url
    assert store.engine.echo is True

@pytest.mark.asyncio
async def test_env_var_config_postgresql(env_vars):
    """Test ThreadStore initialization with PostgreSQL environment variables."""
    # Set environment variables for PostgreSQL
    os.environ.update({
        "TYLER_DB_TYPE": "postgresql",
        "TYLER_DB_HOST": "testhost",
        "TYLER_DB_PORT": "5433",
        "TYLER_DB_NAME": "testdb",
        "TYLER_DB_USER": "testuser",
        "TYLER_DB_PASSWORD": "testpass",
        "TYLER_DB_ECHO": "true"
    })
    
    # Initialize store without URL
    store = ThreadStore()
    
    # Verify PostgreSQL URL was constructed correctly
    assert "postgresql+asyncpg" in store.database_url
    assert "testuser:testpass@testhost:5433/testdb" in store.database_url

@pytest.mark.asyncio
async def test_missing_sqlite_path(env_vars):
    """Test error when SQLite type is specified but path is missing."""
    # Set environment variables with missing path
    os.environ.update({
        "TYLER_DB_TYPE": "sqlite"
    })
    
    # Verify initialization raises ValueError
    with pytest.raises(ValueError) as excinfo:
        ThreadStore()
    
    # Verify error message
    assert "TYLER_DB_PATH environment variable is missing" in str(excinfo.value)

@pytest.mark.asyncio
async def test_missing_postgresql_vars(env_vars):
    """Test error when PostgreSQL type is specified but required vars are missing."""
    # Set environment variables with missing required vars
    os.environ.update({
        "TYLER_DB_TYPE": "postgresql",
        "TYLER_DB_HOST": "testhost",
        # Missing PORT, USER, PASSWORD, NAME
    })
    
    # Verify initialization raises ValueError
    with pytest.raises(ValueError) as excinfo:
        ThreadStore()
    
    # Verify error message mentions missing vars
    error_msg = str(excinfo.value)
    assert "missing required environment variables" in error_msg
    assert "TYLER_DB_PORT" in error_msg
    assert "TYLER_DB_USER" in error_msg
    assert "TYLER_DB_PASSWORD" in error_msg
    assert "TYLER_DB_NAME" in error_msg

@pytest.mark.asyncio
async def test_url_override(env_vars):
    """Test that explicit URL overrides environment variables."""
    # Set environment variables
    os.environ.update({
        "TYLER_DB_TYPE": "postgresql",
        "TYLER_DB_HOST": "wronghost",
        "TYLER_DB_PORT": "5432",
        "TYLER_DB_NAME": "wrongdb",
        "TYLER_DB_USER": "wronguser",
        "TYLER_DB_PASSWORD": "wrongpass"
    })
    
    # Initialize with explicit URL
    test_url = "sqlite+aiosqlite:///test.db"
    store = ThreadStore(test_url)
    
    # Verify explicit URL was used
    assert store.database_url == test_url

@pytest.mark.asyncio
async def test_memory_backend_default(env_vars):
    """Test that MemoryBackend is used when no configuration is provided."""
    # Clear any existing DB environment variables
    for var in ["TYLER_DB_TYPE", "TYLER_DB_PATH", "TYLER_DB_HOST", "TYLER_DB_PORT", 
                "TYLER_DB_NAME", "TYLER_DB_USER", "TYLER_DB_PASSWORD"]:
        if var in os.environ:
            del os.environ[var]
    
    # Initialize store without URL
    store = ThreadStore()
    
    # Verify MemoryBackend is used
    assert isinstance(store._backend, MemoryBackend)
    assert store.database_url is None

@pytest.fixture
async def thread_store():
    """Create a ThreadStore for testing using SQLBackend with an in-memory DB."""
    store = ThreadStore("sqlite+aiosqlite:///:memory:")
    await store.initialize()
    async with store._backend.engine.begin() as conn:
        # Reset tables for testing
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield store
    await store._backend.engine.dispose()

@pytest.fixture
def sample_thread():
    """Create a sample thread for testing."""
    thread = Thread(id="test-thread-1", title="Test Thread")
    thread.add_message(Message(role="user", content="Hello"))
    thread.updated_at = datetime.now(UTC)
    return thread

@pytest.mark.asyncio
async def test_thread_store_init():
    """Test ThreadStore initialization"""
    store = ThreadStore("sqlite+aiosqlite:///:memory:")
    await store.initialize()
    assert store.engine is not None
    
    # Verify we can save and retrieve a thread
    thread = Thread(title="Test Init")
    await store.save(thread)
    
    retrieved = await store.get(thread.id)
    assert retrieved is not None
    assert retrieved.title == "Test Init"

@pytest.mark.asyncio
async def test_lazy_initialization():
    """Test that ThreadStore initializes lazily when operations are performed."""
    # Create store without initializing
    store = ThreadStore("sqlite+aiosqlite:///:memory:")
    
    # Verify not initialized yet
    assert not store._initialized
    
    # Create a thread
    thread = Thread(title="Test Lazy Init")
    
    # Save thread - should trigger initialization
    await store.save(thread)
    
    # Verify initialized now
    assert store._initialized
    
    # Verify thread was saved
    retrieved = await store.get(thread.id)
    assert retrieved is not None
    assert retrieved.title == "Test Lazy Init"
    
    # Clean up
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_save_thread(thread_store, sample_thread):
    """Test saving a thread"""
    # Save the thread
    await thread_store.save(sample_thread)
    
    # Verify it was saved correctly using thread_store.get
    fetched = await thread_store.get(sample_thread.id)
    assert fetched is not None
    assert fetched.title == sample_thread.title
    assert len(fetched.messages) == 1
    assert fetched.messages[0].role == "user"

@pytest.mark.asyncio
async def test_get_thread(thread_store, sample_thread):
    """Test retrieving a thread"""
    # Save the thread first
    await thread_store.save(sample_thread)
    
    # Retrieve the thread
    retrieved_thread = await thread_store.get(sample_thread.id)
    assert retrieved_thread is not None
    assert retrieved_thread.id == sample_thread.id
    assert retrieved_thread.title == sample_thread.title
    assert len(retrieved_thread.messages) == 1
    assert retrieved_thread.messages[0].role == "user"
    assert retrieved_thread.messages[0].content == "Hello"

@pytest.mark.asyncio
async def test_get_nonexistent_thread(thread_store):
    """Test retrieving a non-existent thread"""
    thread = await thread_store.get("nonexistent-id")
    assert thread is None

@pytest.mark.asyncio
async def test_list_recent(thread_store):
    """Test listing recent threads"""
    # Create and save multiple threads
    threads = []
    for i in range(3):
        thread = Thread(
            id=f"test-thread-{i}",
            title=f"Test Thread {i}"
        )
        thread.add_message(Message(role="user", content=f"Message {i}"))
        await thread_store.save(thread)
        threads.append(thread)
    
    # List recent threads
    recent_threads = await thread_store.list_recent(limit=2)
    assert len(recent_threads) == 2
    # Should be in reverse order (most recent first)
    assert recent_threads[0].id == "test-thread-2"
    assert recent_threads[1].id == "test-thread-1"

@pytest.mark.asyncio
async def test_delete_thread(thread_store, sample_thread):
    """Test deleting a thread"""
    # Save the thread first
    await thread_store.save(sample_thread)
    
    # Delete the thread
    success = await thread_store.delete(sample_thread.id)
    assert success is True
    
    # Verify it's gone
    fetched = await thread_store.get(sample_thread.id)
    assert fetched is None

@pytest.mark.asyncio
async def test_delete_nonexistent_thread(thread_store):
    """Test deleting a non-existent thread"""
    success = await thread_store.delete("nonexistent-id")
    assert success is False

@pytest.mark.asyncio
async def test_find_by_attributes(thread_store):
    """Test finding threads by attributes"""
    # Create threads with different attributes
    thread1 = Thread(id="thread-1", title="Thread 1")
    thread1.attributes = {"category": "work", "priority": "high"}
    await thread_store.save(thread1)
    
    thread2 = Thread(id="thread-2", title="Thread 2")
    thread2.attributes = {"category": "personal", "priority": "low"}
    await thread_store.save(thread2)
    
    # Search by attributes using the ThreadStore API
    results = await thread_store.find_by_attributes({"category": "work"})
    
    assert len(results) == 1
    assert results[0].id == "thread-1"

@pytest.mark.asyncio
async def test_find_by_source(thread_store):
    """Test finding threads by source"""
    # Create threads with different sources
    thread1 = Thread(id="thread-1", title="Thread 1")
    thread1.source = {"name": "slack", "channel": "general"}
    await thread_store.save(thread1)
    
    thread2 = Thread(id="thread-2", title="Thread 2")
    thread2.source = {"name": "notion", "page_id": "123"}
    await thread_store.save(thread2)
    
    # Search by source using the ThreadStore API
    results = await thread_store.find_by_source("slack", {})
    
    assert len(results) == 1
    assert results[0].id == "thread-1"

@pytest.mark.asyncio
async def test_thread_update(thread_store, sample_thread):
    """Test updating an existing thread"""
    # Save the initial thread
    await thread_store.save(sample_thread)
    
    # Modify the thread
    sample_thread.title = "Updated Title"
    sample_thread.add_message(Message(role="assistant", content="Response"))
    
    # Save the updates
    await thread_store.save(sample_thread)
    
    # Verify the updates
    updated_thread = await thread_store.get(sample_thread.id)
    assert updated_thread.title == "Updated Title"
    assert len(updated_thread.messages) == 2
    assert updated_thread.messages[1].role == "assistant"
    assert updated_thread.messages[1].content == "Response"

@pytest.mark.asyncio
async def test_thread_store_default_url(env_vars):
    """Test ThreadStore initialization with default behavior."""
    # Clear any existing DB environment variables
    for var in ["TYLER_DB_TYPE", "TYLER_DB_PATH", "TYLER_DB_HOST", "TYLER_DB_PORT", 
                "TYLER_DB_NAME", "TYLER_DB_USER", "TYLER_DB_PASSWORD"]:
        if var in os.environ:
            del os.environ[var]
    
    # Initialize store without URL
    store = ThreadStore()
    
    # Verify MemoryBackend is used by default when no env vars or URL
    assert isinstance(store._backend, MemoryBackend)
    assert store.database_url is None

@pytest.mark.asyncio
async def test_thread_store_temp_cleanup():
    """Test that temporary database files are cleaned up."""
    # Create store with temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "threads.db")
        store = ThreadStore(f"sqlite+aiosqlite:///{db_path}")
        await store.initialize()
        
        # Save a thread
        thread = Thread(id="test-thread", title="Test Thread")
        await store.save(thread)
        
        # Verify thread was saved using the store API
        retrieved_thread = await store.get(thread.id)
        assert retrieved_thread is not None
        assert retrieved_thread.title == thread.title
        
        # Close store
        await store._backend.engine.dispose()
        
        # Verify database file exists in temp directory
        assert os.path.exists(db_path)
    
    # After exiting temp directory context, verify it's gone
    assert not os.path.exists(db_path)

@pytest.mark.asyncio
async def test_thread_store_connection_management():
    """Test proper connection management."""
    store = ThreadStore(":memory:")
    
    # Create tables
    async with store._backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create and save multiple threads
    threads = []
    for i in range(5):
        thread = Thread()
        await store.save(thread)
        threads.append(thread)
    
    # Verify all threads can be retrieved
    for thread in threads:
        retrieved = await store.get(thread.id)
        assert retrieved is not None
        assert retrieved.id == thread.id
    
    # Close all connections
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_thread_store_concurrent_access():
    """Test concurrent access to thread store."""
    store = ThreadStore(":memory:")
    
    # Create tables
    async with store._backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    thread = Thread()
    await store.save(thread)
    
    # Simulate concurrent access
    async def update_thread():
        # Each operation should get its own session
        retrieved = await store.get(thread.id)
        retrieved.title = "Updated"
        await store.save(retrieved)
    
    # Run multiple updates
    for _ in range(5):
        await update_thread()
    
    # Verify final state
    final = await store.get(thread.id)
    assert final.title == "Updated"
    
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_thread_store_json_serialization():
    """Test JSON serialization of complex thread data."""
    store = ThreadStore(":memory:")
    
    # Create tables
    async with store._backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    thread = Thread()
    
    # Add complex data
    thread.attributes = {
        "nested": {"key": "value"},
        "list": [1, 2, 3],
        "null": None,
        "bool": True
    }
    
    # Save and retrieve
    await store.save(thread)
    retrieved = await store.get(thread.id)
    
    # Verify complex data is preserved
    assert retrieved.attributes == thread.attributes
    
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_thread_store_error_handling():
    """Test error handling in thread store operations."""
    store = ThreadStore(":memory:")
    
    # Create tables
    async with store._backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Test invalid thread ID
    assert await store.get("nonexistent") is None
    
    # Test invalid JSON data
    thread = Thread()
    thread.attributes = {"invalid": object()}  # Object that can't be JSON serialized
    
    with pytest.raises(Exception):
        await store.save(thread)
        
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_thread_store_pagination():
    """Test thread listing with pagination."""
    store = ThreadStore(":memory:")
    
    # Create tables
    async with store._backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create 15 threads
    threads = []
    for i in range(15):
        thread = Thread()
        thread.title = f"Thread {i}"
        await store.save(thread)
        threads.append(thread)
    
    # Test different page sizes
    page1 = await store.list(limit=5)
    assert len(page1) == 5
    page2 = await store.list(limit=10, offset=5)
    assert len(page2) == 10
    all_threads = await store.list(limit=20)
    assert len(all_threads) == 15
    
    # Test ordering
    recent = await store.list(limit=5)
    assert recent[0].title == "Thread 14"  # Most recent first
    
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_message_sequence_preservation(thread_store):
    """Test that message sequences are preserved correctly in database"""
    # Create a thread with system and non-system messages
    thread = Thread(id="test-thread")
    thread.add_message(Message(role="user", content="First user message"))
    thread.add_message(Message(role="assistant", content="First assistant message"))
    thread.add_message(Message(role="system", content="System message"))
    thread.add_message(Message(role="user", content="Second user message"))
    
    # Save thread
    await thread_store.save(thread)
    
    # Retrieve thread
    loaded_thread = await thread_store.get(thread.id)
    
    # Verify sequences
    assert len(loaded_thread.messages) == 4
    assert loaded_thread.messages[0].role == "system"
    assert loaded_thread.messages[0].sequence == 0
    
    # Get non-system messages in order
    non_system = [m for m in loaded_thread.messages if m.role != "system"]
    assert len(non_system) == 3
    assert non_system[0].content == "First user message"
    assert non_system[0].sequence == 1
    assert non_system[1].content == "First assistant message"
    assert non_system[1].sequence == 2
    assert non_system[2].content == "Second user message"
    assert non_system[2].sequence == 3

@pytest.mark.asyncio
async def test_save_thread_with_attachments(thread_store):
    """Test saving a thread with attachments ensures they are stored before returning"""
    # Create a thread with an attachment
    thread = Thread()
    message = Message(role="user", content="Test with attachment")
    attachment = Attachment(
        filename="test.txt",
        content=b"Test content",
        mime_type="text/plain"
    )
    message.attachments.append(attachment)
    thread.add_message(message)
    
    # Save the thread
    saved_thread = await thread_store.save(thread)
    
    # Verify attachment was stored before returning
    assert saved_thread.messages[0].attachments[0].status == "stored"
    assert saved_thread.messages[0].attachments[0].file_id is not None
    assert saved_thread.messages[0].attachments[0].storage_path is not None
    
    # Verify we can retrieve it and attachment data persists
    retrieved_thread = await thread_store.get(thread.id)
    assert retrieved_thread.messages[0].attachments[0].status == "stored"
    assert retrieved_thread.messages[0].attachments[0].file_id is not None
    assert retrieved_thread.messages[0].attachments[0].storage_path is not None

@pytest.mark.asyncio
async def test_save_thread_with_multiple_attachments(thread_store):
    """Test saving a thread with multiple messages and attachments"""
    thread = Thread()
    
    # Add first message with attachment
    msg1 = Message(role="user", content="First message")
    att1 = Attachment(filename="test1.txt", content=b"Content 1", mime_type="text/plain")
    msg1.attachments.append(att1)
    thread.add_message(msg1)
    
    # Add second message with two attachments
    msg2 = Message(role="assistant", content="Second message")
    att2 = Attachment(filename="test2.txt", content=b"Content 2", mime_type="text/plain")
    att3 = Attachment(filename="test3.txt", content=b"Content 3", mime_type="text/plain")
    msg2.attachments.extend([att2, att3])
    thread.add_message(msg2)
    
    # Save and verify
    saved_thread = await thread_store.save(thread)
    
    # Check all attachments were stored
    assert all(att.status == "stored" for msg in saved_thread.messages for att in msg.attachments)
    assert all(att.file_id is not None for msg in saved_thread.messages for att in msg.attachments)

@pytest.mark.asyncio
async def test_save_thread_attachment_failure(thread_store):
    """Test that attachment storage failure is handled correctly"""
    thread = Thread()
    message = Message(role="user", content="Test with bad attachment")
    
    # Create an attachment that will fail to store (empty content)
    attachment = Attachment(
        filename="test.txt",
        mime_type="text/plain"
        # Deliberately omit content to cause storage failure
    )
    message.attachments.append(attachment)
    thread.add_message(message)
    
    # Attempt to save should raise an error
    with pytest.raises(RuntimeError):
        await thread_store.save(thread)
    
    # Verify the thread wasn't saved
    retrieved_thread = await thread_store.get(thread.id)
    assert retrieved_thread is None

@pytest.mark.asyncio
async def test_save_thread_partial_attachment_failure(thread_store):
    """Test handling of partial attachment storage failure"""
    thread = Thread()
    
    # First message with good attachment
    msg1 = Message(role="user", content="First message")
    good_att = Attachment(filename="good.txt", content=b"Good content", mime_type="text/plain")
    msg1.attachments.append(good_att)
    thread.add_message(msg1)
    
    # Second message with bad attachment
    msg2 = Message(role="assistant", content="Second message")
    bad_att = Attachment(filename="bad.txt", mime_type="text/plain")  # No content
    msg2.attachments.append(bad_att)
    thread.add_message(msg2)
    
    # Save should fail
    with pytest.raises(RuntimeError):
        await thread_store.save(thread)
    
    # Verify first attachment was cleaned up (not left orphaned)
    retrieved_thread = await thread_store.get(thread.id)
    assert retrieved_thread is None
    
    # Verify the file was cleaned up from storage
    from tyler.storage import get_file_store
    store = get_file_store()
    files = await store.list_files()
    assert not any(f.endswith("good.txt") for f in files)

@pytest.mark.asyncio
async def test_save_thread_database_failure_keeps_attachments(thread_store, monkeypatch):
    """Test that database failures don't clean up successfully stored attachments"""
    thread = Thread()
    message = Message(role="user", content="Test message")
    attachment = Attachment(filename="test.txt", content=b"Test content", mime_type="text/plain")
    message.attachments.append(attachment)
    thread.add_message(message)
    
    # Save once to store the attachment
    await thread_store.save(thread)
    
    # Now setup mocking to simulate a database error
    # Mock the session to fail on commit
    class MockSession:
        def __init__(self):
            self.in_transaction = False

        def begin(self):
            return self

        async def __aenter__(self):
            self.in_transaction = True
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            self.in_transaction = False

        def add(self, obj):
            pass

        async def commit(self):
            raise Exception("Database error")

        async def rollback(self):
            pass

        async def execute(self, *args, **kwargs):
            class MockResult:
                def scalar_one_or_none(self):
                    return None
            return MockResult()
            
        async def close(self):
            pass

        async def get(self, *args, **kwargs):
            return None

    # Attempt to save again with the mock session
    with monkeypatch.context() as m:
        # Replace _get_session with a function that returns our mock session
        async def mock_get_session():
            return MockSession()
        
        m.setattr(thread_store._backend, "_get_session", mock_get_session)
        
        with pytest.raises(RuntimeError) as exc_info:
            await thread_store.save(thread)
        assert "Database error" in str(exc_info.value)
    
    # Verify attachment files still exist (weren't cleaned up)
    from tyler.storage import get_file_store
    store = get_file_store()
    files = await store.list_files()
    assert any(attachment.file_id in f for f in files), f"Expected to find file ID {attachment.file_id} in {files}"

@pytest.mark.asyncio
async def test_default_backend():
    """When no URL is provided, ThreadStore should use MemoryBackend."""
    store = ThreadStore()
    # Check that the underlying _backend is MemoryBackend
    assert isinstance(store._backend, MemoryBackend)

@pytest.mark.asyncio
async def test_explicit_sql_backend():
    """When an explicit URL is provided, ThreadStore should use SQLBackend."""
    test_url = "sqlite+aiosqlite:///test.db"
    store = ThreadStore(test_url)
    assert isinstance(store._backend, SQLBackend) 