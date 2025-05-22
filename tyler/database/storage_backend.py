"""Storage backend implementations for ThreadStore."""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC
import json
import os
from pathlib import Path
import tempfile
import asyncio
from sqlalchemy import create_engine, select, cast, String, text, bindparam
from sqlalchemy.orm import sessionmaker, selectinload
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
# Direct imports
from tyler.models.thread import Thread
from tyler.models.message import Message
from tyler.models.attachment import Attachment
from tyler.storage.file_store import FileStore
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
    async def find_by_platform(self, platform_name: str, properties: Dict[str, Any]) -> List[Thread]:
        """Find threads by platform name and properties in the platforms structure."""
        pass
    
    @abstractmethod
    async def list_recent(self, limit: Optional[int] = None) -> List[Thread]:
        """List recent threads."""
        pass

    @abstractmethod
    async def find_messages_by_attribute(self, path: str, value: Any) -> List[MessageRecord]:
        """
        Find messages that have a specific attribute at a given JSON path.
        Uses efficient SQL JSON path queries for PostgreSQL and falls back to
        SQLite JSON functions when needed.
        
        Args:
            path: Dot-notation path to the attribute (e.g., "source.platform.attributes.ts")
            value: The value to search for
            
        Returns:
            List of messages matching the criteria (possibly empty)
        """
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
    
    async def find_by_platform(self, platform_name: str, properties: Dict[str, Any]) -> List[Thread]:
        matching_threads = []
        for thread in self._threads.values():
            platforms = getattr(thread, 'platforms', {})
            if (
                isinstance(platforms, dict) and
                platform_name in platforms and
                all(platforms[platform_name].get(k) == v for k, v in properties.items())
            ):
                matching_threads.append(thread)
        return matching_threads
    
    async def list_recent(self, limit: Optional[int] = None) -> List[Thread]:
        threads = list(self._threads.values())
        threads.sort(key=lambda t: t.updated_at or t.created_at, reverse=True)
        if limit is not None:
            threads = threads[:limit]
        return threads

    async def find_messages_by_attribute(self, path: str, value: Any) -> List[MessageRecord]:
        """
        Check if any messages exist with a specific attribute at a given JSON path.
        
        Args:
            path: Dot-notation path to the attribute (e.g., "source.platform.attributes.ts")
            value: The value to search for
            
        Returns:
            True if any messages match, False otherwise
        """
        # Traverse all threads and messages
        for thread in self._threads.values():
            for message in thread.messages:
                # Use the path to navigate to the target attribute
                current = message.model_dump(mode="python")
                
                # Navigate the nested structure
                parts = path.split('.')
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        current = None
                        break
                
                # Check if we found a match
                if current == value:
                    return [self._create_message_record(message, thread.id, 0)]
        
        return []

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
            platforms=msg_record.platforms or {},
            metrics=msg_record.metrics,
            reactions=msg_record.reactions or {}
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
            platforms=record.platforms or {},
            created_at=record.created_at,
            updated_at=record.updated_at,
            messages=[]
        )
        # Sort messages: system messages first, then others by sequence
        sorted_messages = sorted(record.messages, 
            key=lambda m: (0 if m.role == "system" else 1, m.sequence or 0))
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
            platforms=message.platforms,
            attachments=[a.model_dump() for a in message.attachments] if message.attachments else None,
            metrics=message.metrics,
            reactions=message.reactions
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
            # Log the platforms data being saved
            logger.info(f"SQLBackend.save: Attempting to save thread {thread.id}. Platforms data: {json.dumps(thread.platforms if thread.platforms is not None else {})}")
            
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
                    thread_record.platforms = thread.platforms
                    thread_record.updated_at = datetime.now(UTC)
                    thread_record.messages = []  # Clear existing messages
                else:
                    # Create new thread record
                    thread_record = ThreadRecord(
                        id=thread.id,
                        title=thread.title,
                        attributes=thread.attributes,
                        platforms=thread.platforms,
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
                    logger.info(f"Thread {thread.id} successfully committed to database.")
                except Exception as e:
                    # For test compatibility - convert database errors to RuntimeError
                    # This helps maintain backward compatibility with tests expecting RuntimeError
                    logger.error(f"Database error during commit: {str(e)}")
                    raise RuntimeError(f"Failed to save thread: Database error - {str(e)}") from e
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
                        bp = bindparam(param_name, str_value)
                        query = query.where(
                            text(f"attributes->>'{key}' = :{param_name}").bindparams(bp)
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

    async def find_by_platform(self, platform_name: str, properties: Dict[str, Any]) -> List[Thread]:
        """Find threads by platform name and properties in the platforms structure."""
        session = await self._get_session()
        try:
            query = select(ThreadRecord).options(selectinload(ThreadRecord.messages))
            
            if self.database_url.startswith('sqlite'):
                # Use SQLite json_extract for platform name
                query = query.where(text(f"json_extract(platforms, '$.{platform_name}') IS NOT NULL"))
                # Add property conditions
                for key, value in properties.items():
                    # Convert value to string for text comparison
                    str_value = str(value)
                    param_name = f"value_{platform_name}_{key}" # Ensure unique param name
                    bp = bindparam(param_name, str_value)
                    query = query.where(
                        text(f"json_extract(platforms, '$.{platform_name}.{key}') = :{param_name}")
                        .bindparams(bp)
                    )
            else:
                # Use PostgreSQL JSONB operators for platform checks
                query = query.where(text(f"platforms ? '{platform_name}'"))
                
                # Add property conditions with text() for proper PostgreSQL JSONB syntax
                for key, value in properties.items():
                    # Log the query parameters for debugging
                    logger.info(f"Searching for platforms[{platform_name}][{key}] = {value} (type: {type(value)})")
                    
                    # Handle different value types appropriately
                    if value is None:
                        # Check for null/None values
                        query = query.where(text(f"platforms->'{platform_name}'->'{key}' IS NULL"))
                    else:
                        # Convert value to string for text comparison
                        str_value = str(value)
                        if isinstance(value, bool):
                            # Convert boolean to lowercase string
                            str_value = str(value).lower()
                        
                        # Use PostgreSQL's JSONB ->> operator to extract as text for comparison
                        param_name = f"platform_{platform_name}_{key}"
                        bp = bindparam(param_name, str_value)
                        query = query.where(
                            text(f"platforms->'{platform_name}'->>'{key}' = :{param_name}")
                            .bindparams(bp)
                        )
            
            # Log the final query for debugging
            logger.info(f"Executing find_by_platform query: {query}")
            
            result = await session.execute(query)
            threads = [self._create_thread_from_record(record) for record in result.scalars().all()]
            logger.info(f"Found {len(threads)} matching threads")
            return threads
        except Exception as e:
            logger.error(f"Error in find_by_platform: {str(e)}")
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

    async def find_messages_by_attribute(self, path: str, value: Any) -> List[MessageRecord]:
        """
        Find messages that have a specific attribute at a given JSON path.
        Uses efficient SQL JSON path queries for PostgreSQL and falls back to
        SQLite JSON functions when needed.
        
        Args:
            path: Dot-notation path to the attribute (e.g., "source.platform.attributes.ts")
            value: The value to search for
            
        Returns:
            List of messages matching the criteria (possibly empty)
        """
        session = await self._get_session()
        try:
            # Convert path to the right format for SQL
            path_parts = path.split('.')
            
            # Convert value to string for comparison
            str_value = str(value) if value is not None else None
            
            # Build query based on database type
            if self.database_url.startswith('sqlite'):
                # Get the first part of the path to determine which JSON column to search
                path_parts = path.split('.')
                root = path_parts[0]
                
                # All JSON columns in the MessageRecord model
                json_columns = ["attributes", "source", "platforms", "attachments", "tool_calls", "metrics", "reactions"]
                
                # Check if the root is a valid JSON column
                if root in json_columns:
                    # Build SQLite JSON path (SQLite uses $ as root)
                    sqlite_path = "$"
                    for part in path_parts:
                        sqlite_path += f".{part}"
                    
                    # Log the query for debugging
                    logger.info(f"SQLite: Searching for JSON path: {path} = '{str_value}' using json_extract({root}, '{sqlite_path}')")
                    
                    # Use SQLite's json_extract function
                    query = text(f"""
                        SELECT id, thread_id, sequence, role, content, name, tool_call_id, tool_calls,
                               attributes, timestamp, source, attachments, metrics, reactions, platforms 
                        FROM messages 
                        WHERE json_extract({root}, :path) = :value
                    """).bindparams(path=sqlite_path, value=str_value)
                else:
                    # For non-JSON columns or unrecognized paths
                    logger.warning(f"Unrecognized JSON path root: {root} - not a valid JSON column in messages table")
                    query = text(f"""
                        SELECT id, thread_id, sequence, role, content, name, tool_call_id, tool_calls,
                               attributes, timestamp, source, attachments, metrics, reactions, platforms 
                        FROM messages 
                        WHERE id = 'no_match_placeholder'
                    """)  # This will return 0 matches
            else:
                # PostgreSQL JSON path
                # Start with the first part to determine which JSON column to search
                root = path_parts[0]
                
                # All JSON columns in the MessageRecord model
                json_columns = ["attributes", "source", "platforms", "attachments", "tool_calls", "metrics", "reactions"]
                
                # Check if the root is a valid JSON column
                if root in json_columns:
                    # For any JSON column, build the appropriate PostgreSQL JSON path expression
                    pg_path = root
                    for i, part in enumerate(path_parts[1:]):
                        if i == len(path_parts[1:]) - 1:
                            # Last part uses ->> to extract as text
                            pg_path += f"->>'{part}'"
                        else:
                            # Inner parts use -> to keep as JSON
                            pg_path += f"->'{part}'"
                    
                    # Query using PostgreSQL JSON operators with proper nesting
                    query = text(f"""
                        SELECT id, thread_id, sequence, role, content, name, tool_call_id, tool_calls,
                               attributes, timestamp, source, attachments, metrics, reactions, platforms 
                        FROM messages 
                        WHERE {pg_path} = :value
                    """).bindparams(value=str_value)
                    
                    # Log the query for debugging
                    logger.info(f"Searching for JSON path: {path} = '{str_value}' using query: {pg_path} = :value")
                else:
                    # For non-JSON columns or unrecognized paths
                    logger.warning(f"Unrecognized JSON path root: {root} - not a valid JSON column in messages table")
                    query = text(f"""
                        SELECT id, thread_id, sequence, role, content, name, tool_call_id, tool_calls,
                               attributes, timestamp, source, attachments, metrics, reactions, platforms 
                        FROM messages 
                        WHERE id = 'no_match_placeholder'
                    """)  # This will return 0 matches
            
            # Execute query and get message records
            result = await session.execute(query)
            rows = result.fetchall()
            
            # Convert rows to MessageRecord objects
            records = []
            for row in rows:
                # Create a MessageRecord from the row (mapping by column order)
                record = MessageRecord(
                    id=row[0],
                    thread_id=row[1], 
                    sequence=row[2],
                    role=row[3],
                    content=row[4],
                    name=row[5],
                    tool_call_id=row[6],
                    tool_calls=row[7],
                    attributes=row[8],
                    timestamp=row[9],
                    source=row[10],
                    attachments=row[11],
                    metrics=row[12],
                    reactions=row[13],
                    platforms=row[14]
                )
                records.append(record)
            
            # Log detailed results for debugging
            if records:
                logger.info(f"Found {len(records)} messages matching {path}={value}")
                for idx, record in enumerate(records):
                    logger.info(f"Match {idx+1}: Message ID {record.id} in thread {record.thread_id}, role={record.role}")
            else:
                logger.info(f"No messages found matching {path}={value}")
            
            return records
        except Exception as e:
            logger.error(f"Error in find_messages_by_attribute: {str(e)}")
            return []  # Return empty list on error
        finally:
            await session.close()

        
    async def get_thread_by_message_id(self, message_id: str) -> Optional[Thread]:
        """
        Find a thread containing a specific message ID.
        
        Args:
            message_id: The ID of the message to find
            
        Returns:
            The Thread containing the message, or None if not found
        """
        async with await self._get_session() as session:
            # First find the message record
            query = select(MessageRecord).where(MessageRecord.id == message_id)
            result = await session.execute(query)
            message_record = result.scalars().first()
            
            if not message_record:
                return None
                
            # Get the thread ID from the message record
            thread_id = message_record.thread_id
            
            # Get the complete thread
            query = select(ThreadRecord).where(ThreadRecord.id == thread_id)
            query = query.options(selectinload(ThreadRecord.messages))
            result = await session.execute(query)
            thread_record = result.scalars().first()
            
            if not thread_record:
                return None
                
            return self._create_thread_from_record(thread_record) 