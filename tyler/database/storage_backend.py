"""Storage backend implementations for ThreadStore."""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC
import json
import os
from pathlib import Path
import tempfile
import asyncio
from sqlalchemy import create_engine, select, cast, String, text
from sqlalchemy.orm import sessionmaker, selectinload
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from tyler.models.thread import Thread
from tyler.models.message import Message
from tyler.models.attachment import Attachment
from tyler.utils.logging import get_logger
from .models import Base, ThreadRecord, MessageRecord

logger = get_logger(__name__)

class StorageBackend(ABC):
    """Abstract base class for thread storage backends."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage backend."""
        pass
    
    @abstractmethod
    async def save(self, thread: Thread) -> Thread:
        """Save a thread to storage."""
        pass
    
    @abstractmethod
    async def get(self, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID."""
        pass
    
    @abstractmethod
    async def delete(self, thread_id: str) -> bool:
        """Delete a thread by ID."""
        pass
    
    @abstractmethod
    async def list(self, limit: int = 100, offset: int = 0) -> List[Thread]:
        """List threads with pagination."""
        pass
    
    @abstractmethod
    async def find_by_attributes(self, attributes: Dict[str, Any]) -> List[Thread]:
        """Find threads by matching attributes."""
        pass
    
    @abstractmethod
    async def find_by_source(self, source_name: str, properties: Dict[str, Any]) -> List[Thread]:
        """Find threads by source name and properties."""
        pass
    
    @abstractmethod
    async def list_recent(self, limit: Optional[int] = None) -> List[Thread]:
        """List recent threads."""
        pass

class MemoryBackend(StorageBackend):
    """In-memory storage backend using a dictionary."""
    
    def __init__(self):
        self._threads: Dict[str, Thread] = {}
    
    async def initialize(self) -> None:
        pass  # No initialization needed for memory backend
    
    async def save(self, thread: Thread) -> Thread:
        self._threads[thread.id] = thread
        return thread
    
    async def get(self, thread_id: str) -> Optional[Thread]:
        return self._threads.get(thread_id)
    
    async def delete(self, thread_id: str) -> bool:
        if thread_id in self._threads:
            del self._threads[thread_id]
            return True
        return False
    
    async def list(self, limit: int = 100, offset: int = 0) -> List[Thread]:
        threads = sorted(
            self._threads.values(),
            key=lambda t: t.updated_at if hasattr(t, 'updated_at') else t.created_at,
            reverse=True
        )
        return threads[offset:offset + limit]
    
    async def find_by_attributes(self, attributes: Dict[str, Any]) -> List[Thread]:
        matching_threads = []
        for thread in self._threads.values():
            if all(
                thread.attributes.get(k) == v 
                for k, v in attributes.items()
            ):
                matching_threads.append(thread)
        return matching_threads
    
    async def find_by_source(self, source_name: str, properties: Dict[str, Any]) -> List[Thread]:
        matching_threads = []
        for thread in self._threads.values():
            source = getattr(thread, 'source', {})
            if (
                isinstance(source, dict) and 
                source.get('name') == source_name and
                all(source.get(k) == v for k, v in properties.items())
            ):
                matching_threads.append(thread)
        return matching_threads
    
    async def list_recent(self, limit: Optional[int] = None) -> List[Thread]:
        threads = list(self._threads.values())
        threads.sort(key=lambda t: t.updated_at or t.created_at, reverse=True)
        if limit is not None:
            threads = threads[:limit]
        return threads

class SQLBackend(StorageBackend):
    """SQL storage backend supporting both SQLite and PostgreSQL."""
    
    def __init__(self, database_url: Optional[str] = None):
        if database_url is None:
            # Create a temporary directory that persists until program exit
            tmp_dir = Path(tempfile.gettempdir()) / "tyler_threads"
            tmp_dir.mkdir(exist_ok=True)
            database_url = f"sqlite+aiosqlite:///{tmp_dir}/threads.db"
        elif database_url == ":memory:":
            database_url = "sqlite+aiosqlite:///:memory:"
            
        self.database_url = database_url
        
        # Configure engine options
        engine_kwargs = {
            'echo': os.environ.get("TYLER_DB_ECHO", "").lower() == "true"
        }
        
        # Add pool configuration if specified and not using SQLite
        if not self.database_url.startswith('sqlite'):
            pool_size = os.environ.get("TYLER_DB_POOL_SIZE")
            max_overflow = os.environ.get("TYLER_DB_MAX_OVERFLOW")
            
            if pool_size is not None:
                engine_kwargs['pool_size'] = int(pool_size)
            if max_overflow is not None:
                engine_kwargs['max_overflow'] = int(max_overflow)
            
        self.engine = create_async_engine(self.database_url, **engine_kwargs)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def initialize(self) -> None:
        """Initialize the database by creating tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def _create_message_from_record(self, msg_record: MessageRecord) -> Message:
        """Helper method to create a Message from a MessageRecord"""
        message = Message(
            id=msg_record.id,
            role=msg_record.role,
            sequence=msg_record.sequence,
            content=msg_record.content,
            name=msg_record.name,
            tool_call_id=msg_record.tool_call_id,
            tool_calls=msg_record.tool_calls,
            attributes=msg_record.attributes,
            timestamp=msg_record.timestamp,
            source=msg_record.source,
            metrics=msg_record.metrics
        )
        if msg_record.attachments:
            message.attachments = [Attachment(**a) for a in msg_record.attachments]
        return message

    def _create_thread_from_record(self, record: ThreadRecord) -> Thread:
        """Helper method to create a Thread from a ThreadRecord"""
        thread = Thread(
            id=record.id,
            title=record.title,
            attributes=record.attributes,
            source=record.source,
            created_at=record.created_at,
            updated_at=record.updated_at,
            messages=[]
        )
        # Sort messages: system messages first, then others by sequence
        sorted_messages = sorted(record.messages, 
            key=lambda m: (0 if m.role == "system" else 1, m.sequence))
        for msg_record in sorted_messages:
            message = self._create_message_from_record(msg_record)
            thread.messages.append(message)
        return thread

    def _create_message_record(self, message: Message, thread_id: str, sequence: int) -> MessageRecord:
        """Helper method to create a MessageRecord from a Message"""
        return MessageRecord(
            id=message.id,
            thread_id=thread_id,
            sequence=sequence,
            role=message.role,
            content=message.content,
            name=message.name,
            tool_call_id=message.tool_call_id,
            tool_calls=message.tool_calls,
            attributes=message.attributes,
            timestamp=message.timestamp,
            source=message.source,
            attachments=[a.model_dump() for a in message.attachments] if message.attachments else None,
            metrics=message.metrics
        )

    async def save(self, thread: Thread) -> Thread:
        """Save a thread and its messages to the database."""
        async with self.async_session() as session:
            try:
                # First process and store all attachments
                logger.info(f"Starting to process attachments for thread {thread.id}")
                for message in thread.messages:
                    if message.attachments:
                        logger.info(f"Processing {len(message.attachments)} attachments for message {message.id}")
                        for attachment in message.attachments:
                            logger.info(f"Processing attachment {attachment.filename} with status {attachment.status}")
                            await attachment.process_and_store()
                            logger.info(f"Finished processing attachment {attachment.filename}, new status: {attachment.status}")

                async with session.begin():
                    # Get existing thread if it exists
                    stmt = select(ThreadRecord).options(selectinload(ThreadRecord.messages)).where(ThreadRecord.id == thread.id)
                    result = await session.execute(stmt)
                    thread_record = result.scalar_one_or_none()
                    
                    if thread_record:
                        # Update existing thread
                        thread_record.title = thread.title
                        thread_record.attributes = thread.attributes
                        thread_record.source = thread.source
                        thread_record.updated_at = datetime.now(UTC)
                        thread_record.messages = []  # Clear existing messages
                    else:
                        # Create new thread record
                        thread_record = ThreadRecord(
                            id=thread.id,
                            title=thread.title,
                            attributes=thread.attributes,
                            source=thread.source,
                            created_at=thread.created_at,
                            updated_at=thread.updated_at,
                            messages=[]
                        )
                    
                    # Process messages in order
                    sequence = 1
                    
                    # First handle system messages
                    for message in thread.messages:
                        if message.role == "system":
                            thread_record.messages.append(self._create_message_record(message, thread.id, 0))
                    
                    # Then handle non-system messages
                    for message in thread.messages:
                        if message.role != "system":
                            thread_record.messages.append(self._create_message_record(message, thread.id, sequence))
                            sequence += 1
                    
                    session.add(thread_record)
                    await session.commit()
                    return thread
                    
            except Exception as e:
                # If database operation failed after attachment storage,
                # we don't need to clean up attachments as they might be used by other threads
                if isinstance(e, RuntimeError) and "Failed to process attachment" in str(e):
                    # Only clean up if attachment processing/storage failed
                    await self._cleanup_failed_attachments(thread)
                if "Database error" in str(e):
                    # Don't clean up attachments for database errors
                    raise RuntimeError(f"Failed to save thread: Database error") from e
                raise RuntimeError(f"Failed to save thread: {str(e)}") from e

    async def get(self, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID."""
        async with self.async_session() as session:
            stmt = select(ThreadRecord).options(selectinload(ThreadRecord.messages)).where(ThreadRecord.id == thread_id)
            result = await session.execute(stmt)
            thread_record = result.scalar_one_or_none()
            return self._create_thread_from_record(thread_record) if thread_record else None

    async def delete(self, thread_id: str) -> bool:
        """Delete a thread by ID."""
        async with self.async_session() as session:
            async with session.begin():
                record = await session.get(ThreadRecord, thread_id)
                if record:
                    await session.delete(record)
                    return True
                return False

    async def list(self, limit: int = 100, offset: int = 0) -> List[Thread]:
        """List threads with pagination."""
        async with self.async_session() as session:
            result = await session.execute(
                select(ThreadRecord)
                .options(selectinload(ThreadRecord.messages))
                .order_by(ThreadRecord.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return [self._create_thread_from_record(record) for record in result.scalars().all()]

    async def find_by_attributes(self, attributes: Dict[str, Any]) -> List[Thread]:
        """Find threads by matching attributes."""
        async with self.async_session() as session:
            query = select(ThreadRecord).options(selectinload(ThreadRecord.messages))
            for key, value in attributes.items():
                if self.database_url.startswith('sqlite'):
                    # Use SQLite json_extract
                    query = query.where(text(f"json_extract(attributes, '$.{key}') = :value").bindparams(value=str(value)))
                else:
                    # Use PostgreSQL JSONB operators
                    query = query.where(ThreadRecord.attributes[key].astext == str(value))
            result = await session.execute(query)
            return [self._create_thread_from_record(record) for record in result.scalars().all()]

    async def find_by_source(self, source_name: str, properties: Dict[str, Any]) -> List[Thread]:
        """Find threads by source name and properties."""
        async with self.async_session() as session:
            query = select(ThreadRecord).options(selectinload(ThreadRecord.messages))
            
            if self.database_url.startswith('sqlite'):
                # Use SQLite json_extract for source name
                query = query.where(text("json_extract(source, '$.name') = :name").bindparams(name=source_name))
                # Add property conditions
                for key, value in properties.items():
                    query = query.where(text(f"json_extract(source, '$.{key}') = :value_{key}").bindparams(**{f"value_{key}": str(value)}))
            else:
                # Use PostgreSQL JSONB operators
                query = query.where(cast(ThreadRecord.source['name'], String) == source_name)
                for key, value in properties.items():
                    query = query.where(cast(ThreadRecord.source[key], String) == str(value))
            
            result = await session.execute(query)
            return [self._create_thread_from_record(record) for record in result.scalars().all()]

    async def list_recent(self, limit: Optional[int] = None) -> List[Thread]:
        """List recent threads ordered by updated_at timestamp."""
        async with self.async_session() as session:
            result = await session.execute(
                select(ThreadRecord)
                .options(selectinload(ThreadRecord.messages))
                .order_by(ThreadRecord.updated_at.desc())
                .limit(limit)
            )
            return [self._create_thread_from_record(record) for record in result.scalars().all()] 