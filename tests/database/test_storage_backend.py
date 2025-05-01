import os
import asyncio
import pytest
from datetime import datetime, UTC

from tyler.database.storage_backend import MemoryBackend, SQLBackend
from tyler import Thread, Message
from tyler.database.models import Base


@pytest.fixture
def sample_thread():
    thread = Thread(id='test-thread', title='Test Thread')
    thread.attributes = {'category': 'test'}
    thread.updated_at = datetime.now(UTC)
    thread.add_message(Message(role='user', content='Hello'))
    return thread


@pytest.mark.asyncio
async def test_memory_backend_save_get_delete(sample_thread):
    backend = MemoryBackend()
    await backend.initialize()

    # Save thread
    saved = await backend.save(sample_thread)
    assert saved.id == sample_thread.id

    # Get thread
    fetched = await backend.get(sample_thread.id)
    assert fetched is not None
    assert fetched.title == sample_thread.title

    # List threads
    threads = await backend.list()
    assert len(threads) >= 1

    # Delete thread
    success = await backend.delete(sample_thread.id)
    assert success is True
    assert await backend.get(sample_thread.id) is None


@pytest.mark.asyncio
async def test_memory_backend_find(sample_thread):
    backend = MemoryBackend()
    await backend.initialize()

    # Save two threads with different attributes
    thread1 = sample_thread
    thread2 = Thread(id='test-thread-2', title='Thread 2')
    thread2.attributes = {'category': 'different'}
    thread1.updated_at = datetime.now(UTC)
    thread2.updated_at = datetime.now(UTC)

    await backend.save(thread1)
    await backend.save(thread2)

    found = await backend.find_by_attributes({'category': 'test'})
    assert len(found) == 1
    assert found[0].id == thread1.id

    # Test find by platform
    thread1.platforms = {'slack': {'channel': 'general'}}
    thread2.platforms = {'notion': {}}
    await backend.save(thread1)
    await backend.save(thread2)

    found_platform = await backend.find_by_platform('slack', {'channel': 'general'})
    assert len(found_platform) == 1
    assert found_platform[0].id == thread1.id


@pytest.mark.asyncio
async def test_sql_backend_save_get_delete(tmp_path, sample_thread):
    # Create a temporary in-memory SQLite backend
    backend = SQLBackend(":memory:")
    await backend.initialize()

    # Create tables
    async with backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Save thread
    saved = await backend.save(sample_thread)
    assert saved.id == sample_thread.id

    # Get thread
    fetched = await backend.get(sample_thread.id)
    assert fetched is not None
    assert fetched.title == sample_thread.title

    # List threads
    threads = await backend.list()
    assert len(threads) >= 1

    # Delete thread
    success = await backend.delete(sample_thread.id)
    assert success is True
    assert await backend.get(sample_thread.id) is None


@pytest.mark.asyncio
async def test_sql_backend_find(tmp_path):
    # Create a temporary in-memory SQLite backend
    backend = SQLBackend(":memory:")
    await backend.initialize()
    
    # Create tables
    async with backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create and save test threads
    thread1 = Thread(id='sql-thread-1', title='SQL Thread 1')
    thread1.attributes = {'category': 'sql'}
    thread1.updated_at = datetime.now(UTC)
    thread1.add_message(Message(role='user', content='Hello SQL'))

    thread2 = Thread(id='sql-thread-2', title='SQL Thread 2')
    thread2.attributes = {'category': 'other'}
    thread2.updated_at = datetime.now(UTC)
    thread2.add_message(Message(role='user', content='Hi there'))

    await backend.save(thread1)
    await backend.save(thread2)

    # Test find by attributes
    found = await backend.find_by_attributes({'category': 'sql'})
    assert len(found) == 1
    assert found[0].id == 'sql-thread-1'

    # Test find by platform
    thread1.platforms = {'github': {'repo': 'tyler'}}
    thread2.platforms = {'gitlab': {}}
    await backend.save(thread1)
    await backend.save(thread2)

    found_platform = await backend.find_by_platform('github', {'repo': 'tyler'})
    assert len(found_platform) == 1
    assert found_platform[0].id == 'sql-thread-1'


@pytest.mark.asyncio
async def test_sql_backend_list_recent(tmp_path):
    backend = SQLBackend(":memory:")
    await backend.initialize()

    # Create tables
    async with backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create threads with slight delays
    threads = []
    for i in range(3):
        t = Thread(id=f'recent-{i}', title=f'Thread {i}')
        t.updated_at = datetime.now(UTC)
        t.add_message(Message(role='user', content=f'Message {i}'))
        await backend.save(t)
        threads.append(t)
        await asyncio.sleep(0.01)  # ensure timestamp difference

    recent = await backend.list_recent(limit=2)
    assert len(recent) == 2
    # Most recent thread should be the last one saved
    assert recent[0].id == 'recent-2'
    assert recent[1].id == 'recent-1'


@pytest.mark.asyncio
async def test_save_thread(tmp_path, sample_thread):
    # Create a temporary SQLite backend with proper URL format
    db_path = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    backend = SQLBackend(db_path)
    await backend.initialize()
    
    # Create tables
    async with backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Save thread
    saved = await backend.save(sample_thread)
    assert saved.id == sample_thread.id

    # Get thread
    fetched = await backend.get(sample_thread.id)
    assert fetched is not None
    assert fetched.title == sample_thread.title
    assert len(fetched.messages) == len(sample_thread.messages)

    # Clean up
    await backend.engine.dispose()
    
    # Verify database file exists in temp directory
    assert os.path.exists(f"{tmp_path}/test.db") 