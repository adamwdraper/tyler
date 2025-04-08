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
from tyler.storage.file_store import FileStore
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
    """SQL storage backend supporting both SQLite and PostgreSQL with proper connection pooling."""
    
    def __init__(self, database_url: Optional[str] = None):
        if database_url is None:
            # Create a temporary directory that persists until program exit
            tmp_dir = Path(tempfile.gettempdir()) / "tyler_threads"
            tmp_dir.mkdir(exist_ok=True)
            database_url = f"sqlite+aiosqlite:///{tmp_dir}/threads.db"
        elif database_url == ":memory:":
            database_url = "sqlite+aiosqlite:///:memory:"
            
        self.database_url = database_url
        
        # Configure engine options with better defaults for connection pooling
        engine_kwargs = {
            'echo': os.environ.get("TYLER_DB_ECHO", "").lower() == "true"
        }
        
        # Add pool configuration if not using SQLite
        if not self.database_url.startswith('sqlite'):
            # Default connection pool settings if not specified
            pool_size = int(os.environ.get("TYLER_DB_POOL_SIZE", "5"))
            max_overflow = int(os.environ.get("TYLER_DB_MAX_OVERFLOW", "10"))
            pool_timeout = int(os.environ.get("TYLER_DB_POOL_TIMEOUT", "30"))
            pool_recycle = int(os.environ.get("TYLER_DB_POOL_RECYCLE", "300"))
            
            engine_kwargs.update({
                'pool_size': pool_size,
                'max_overflow': max_overflow, 
                'pool_timeout': pool_timeout,
                'pool_recycle': pool_recycle,
                'pool_pre_ping': True  # Check connection validity before using from pool
            })
            
            logger.info(f"Configuring database connection pool: size={pool_size}, "
                       f"max_overflow={max_overflow}, timeout={pool_timeout}, "
                       f"recycle={pool_recycle}")
            
        self.engine = create_async_engine(self.database_url, **engine_kwargs)
        # Create session_maker even though we don't use it directly in our implementation,
        # to support backward compatibility with tests
        self._session_maker = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        
    @property
    def async_session(self):
        """
        Provides backward compatibility with tests that directly access backend.async_session
        
        Returns the session factory for creating new database sessions.
        
        NOTE: This is kept for backward compatibility with existing tests but should 
        not be used in new code. Use _get_session() method instead which properly
        creates a session for each database operation.
        """
        return self._session_maker

    async def initialize(self) -> None:
        """Initialize the database by creating tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info(f"Database initialized with tables: {Base.metadata.tables.keys()}")

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
    
    async def _get_session(self) -> AsyncSession:
        """Create and return a new session for database operations."""
        return self._session_maker()

    async def _cleanup_failed_attachments(self, thread: Thread) -> None:
        """Helper to clean up attachment files if thread save fails"""
        for message in thread.messages:
            if message.attachments:
                for attachment in message.attachments:
                    if hasattr(attachment, 'cleanup') and callable(attachment.cleanup):
                        await attachment.cleanup()

    async def save(self, thread: Thread) -> Thread:
        """Save a thread and its messages to the database."""
        session = await self._get_session()
        
        # Create a FileStore instance for attachment storage
        file_store = FileStore()
        
        try:
            # First process and store all attachments
            logger.info(f"Starting to process attachments for thread {thread.id}")
            try:
                for message in thread.messages:
                    if message.attachments:
                        logger.info(f"Processing {len(message.attachments)} attachments for message {message.id}")
                        for attachment in message.attachments:
                            logger.info(f"Processing attachment {attachment.filename} with status {attachment.status}")
                            await attachment.process_and_store(file_store)
                            logger.info(f"Finished processing attachment {attachment.filename}, new status: {attachment.status}")
            except Exception as e:
                # Handle attachment processing failures
                logger.error(f"Failed to process attachment: {str(e)}")
                await self._cleanup_failed_attachments(thread)
                raise RuntimeError(f"Failed to save thread: {str(e)}") from e

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
                try:
                    await session.commit()
                except Exception as e:
                    # For test compatibility - convert database errors to RuntimeError
                    # This helps maintain backward compatibility with tests expecting RuntimeError
                    logger.error(f"Database error during commit: {str(e)}")
                    raise RuntimeError(f"Failed to save thread: Database error") from e
                return thread
                
        except Exception as e:
            # If this is not already a RuntimeError, wrap it
            if not isinstance(e, RuntimeError):
                raise RuntimeError(f"Failed to save thread: {str(e)}") from e
            raise e
        finally:
            await session.close()

    async def get(self, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID."""
        session = await self._get_session()
        try:
            stmt = select(ThreadRecord).options(selectinload(ThreadRecord.messages)).where(ThreadRecord.id == thread_id)
            result = await session.execute(stmt)
            thread_record = result.scalar_one_or_none()
            return self._create_thread_from_record(thread_record) if thread_record else None
        finally:
            await session.close()

    async def delete(self, thread_id: str) -> bool:
        """Delete a thread by ID."""
        session = await self._get_session()
        try:
            async with session.begin():
                record = await session.get(ThreadRecord, thread_id)
                if record:
                    await session.delete(record)
                    return True
                return False
        finally:
            await session.close()

    async def list(self, limit: int = 100, offset: int = 0) -> List[Thread]:
        """List threads with pagination."""
        session = await self._get_session()
        try:
            result = await session.execute(
                select(ThreadRecord)
                .options(selectinload(ThreadRecord.messages))
                .order_by(ThreadRecord.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return [self._create_thread_from_record(record) for record in result.scalars().all()]
        finally:
            await session.close()

    async def find_by_attributes(self, attributes: Dict[str, Any]) -> List[Thread]:
        """Find threads by matching attributes."""
        session = await self._get_session()
        try:
            query = select(ThreadRecord).options(selectinload(ThreadRecord.messages))
            
            for key, value in attributes.items():
                if self.database_url.startswith('sqlite'):
                    # Use SQLite json_extract
                    query = query.where(text(f"json_extract(attributes, '$.{key}') = :value").bindparams(value=str(value)))
                else:
                    # Use PostgreSQL JSONB operators via text() for direct SQL control
                    logger.info(f"Searching for attribute[{key}] = {value} (type: {type(value)})")
                    
                    # Handle different value types appropriately
                    if value is None:
                        # Check for null/None values
                        query = query.where(text(f"attributes->>'{key}' IS NULL"))
                    else:
                        # Convert value to string for text comparison
                        str_value = str(value)
                        if isinstance(value, bool):
                            # Convert boolean to lowercase string
                            str_value = str(value).lower()
                        
                        # Use PostgreSQL's JSONB operators for direct string comparison
                        param_name = f"attr_{key}"
                        query = query.where(
                            text(f"attributes->>'{key}' = :{param_name}").bindparams(**{param_name: str_value})
                        )
            
            # Log the final query for debugging
            logger.info(f"Executing find_by_attributes query: {query}")
            
            result = await session.execute(query)
            threads = [self._create_thread_from_record(record) for record in result.scalars().all()]
            logger.info(f"Found {len(threads)} matching threads")
            return threads
        except Exception as e:
            logger.error(f"Error in find_by_attributes: {str(e)}")
            raise
        finally:
            await session.close()

    async def find_by_source(self, source_name: str, properties: Dict[str, Any]) -> List[Thread]:
        """Find threads by source name and properties."""
        session = await self._get_session()
        try:
            query = select(ThreadRecord).options(selectinload(ThreadRecord.messages))
            
            if self.database_url.startswith('sqlite'):
                # Use SQLite json_extract for source name
                query = query.where(text("json_extract(source, '$.name') = :name").bindparams(name=source_name))
                # Add property conditions
                for key, value in properties.items():
                    query = query.where(text(f"json_extract(source, '$.{key}') = :value_{key}").bindparams(**{f"value_{key}": str(value)}))
            else:
                # Use PostgreSQL JSONB operators via text() to ensure proper SQL generation
                query = query.where(text("source->>'name' = :source_name").bindparams(source_name=source_name))
                
                # Add property conditions with text() for proper PostgreSQL JSONB syntax
                for key, value in properties.items():
                    # Log the query parameters for debugging
                    logger.info(f"Searching for source[{key}] = {value} (type: {type(value)})")
                    
                    # Handle different value types appropriately
                    if value is None:
                        # Check for null/None values
                        query = query.where(text(f"source->>'{key}' IS NULL"))
                    else:
                        # Convert value to string for text comparison
                        str_value = str(value)
                        if isinstance(value, bool):
                            # Convert boolean to lowercase string
                            str_value = str(value).lower()
                        
                        # Use PostgreSQL's JSONB operators for direct string comparison
                        param_name = f"source_{key}"
                        query = query.where(
                            text(f"source->>'{key}' = :{param_name}").bindparams(**{param_name: str_value})
                        )
            
            # Log the final query for debugging
            logger.info(f"Executing find_by_source query: {query}")
            
            result = await session.execute(query)
            threads = [self._create_thread_from_record(record) for record in result.scalars().all()]
            logger.info(f"Found {len(threads)} matching threads")
            return threads
        except Exception as e:
            logger.error(f"Error in find_by_source: {str(e)}")
            raise
        finally:
            await session.close()

    async def list_recent(self, limit: Optional[int] = None) -> List[Thread]:
        """List recent threads ordered by updated_at timestamp."""
        session = await self._get_session()
        try:
            result = await session.execute(
                select(ThreadRecord)
                .options(selectinload(ThreadRecord.messages))
                .order_by(ThreadRecord.updated_at.desc())
                .limit(limit)
            )
            return [self._create_thread_from_record(record) for record in result.scalars().all()] 
        finally:
            await session.close() 