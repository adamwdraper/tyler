"""Thread storage implementation."""
from typing import Optional, Dict, Any, List
from tyler.models.thread import Thread
from tyler.utils.logging import get_logger
from .storage_backend import MemoryBackend, SQLBackend

logger = get_logger(__name__)

class ThreadStore:
    """
    Thread storage implementation with pluggable backends.
    Supports both in-memory and SQL (SQLite/PostgreSQL) storage.
    
    Key characteristics:
    - Unified interface for all storage types
    - Memory backend for development/testing (default)
    - SQLite for local persistence
    - PostgreSQL for production
    - Built-in connection pooling for SQLBackend
    
    Usage:
        # RECOMMENDED: Factory pattern for immediate connection validation
        from tyler.database.thread_store import ThreadStore
        store = await ThreadStore.create("postgresql+asyncpg://user:pass@localhost/dbname")
        
        # Or for in-memory storage:
        store = await ThreadStore.create()  # Uses memory backend
        
        # For backward compatibility, you can also use the direct constructor
        # which will connect on first operation:
        store = ThreadStore("postgresql+asyncpg://user:pass@localhost/dbname")
        
        # Use with agent
        agent = Agent(thread_store=store)
        
    Connection pooling settings can be configured via environment variables:
        - TYLER_DB_POOL_SIZE: Max number of connections to keep open (default: 5)
        - TYLER_DB_MAX_OVERFLOW: Max number of connections to create above pool_size (default: 10)
        - TYLER_DB_POOL_TIMEOUT: Seconds to wait for a connection from pool (default: 30)
        - TYLER_DB_POOL_RECYCLE: Seconds after which a connection is recycled (default: 300)
    """
    
    def __init__(self, database_url = None):
        """
        Initialize thread store with optional database URL.
        If no URL is provided, uses in-memory storage by default.
        This constructor doesn't establish database connections - they happen on first use.
        
        For immediate connection validation, use the async factory method:
        `store = await ThreadStore.create(database_url)`
        
        Args:
            database_url: SQLAlchemy async database URL. Examples:
                - "postgresql+asyncpg://user:pass@localhost/dbname"
                - "sqlite+aiosqlite:///path/to/db.sqlite"
                - None for in-memory storage
        """
        if database_url is None:
            # Default to in-memory storage
            logger.info("No database URL provided. Using in-memory storage.")
            self._backend = MemoryBackend()
        else:
            # Use SQLBackend with the provided URL
            logger.info(f"Using database URL: {database_url}")
            self._backend = SQLBackend(database_url)
        
        # Add initialization flag
        self._initialized = False
    
    @classmethod
    async def create(cls, database_url = None):
        """
        Factory method to create and initialize a ThreadStore.
        This method connects to the database immediately, allowing early validation
        of connection parameters.
        
        Args:
            database_url: SQLAlchemy async database URL. Examples:
                - "postgresql+asyncpg://user:pass@localhost/dbname"
                - "sqlite+aiosqlite:///path/to/db.sqlite"
                - None for in-memory storage
                
        Returns:
            Initialized ThreadStore instance
            
        Raises:
            Exception: If database connection fails
        """
        # Create instance
        store = cls(database_url)
        
        # Initialize immediately
        try:
            await store.initialize()
        except Exception as e:
            # If a database URL was provided but initialization failed, we should raise the error
            # instead of silently falling back to memory storage
            if database_url is not None:
                raise RuntimeError(f"Failed to initialize database with URL {database_url}: {str(e)}") from e
            raise
        
        return store
    
    async def _ensure_initialized(self) -> None:
        """Ensure the storage backend is initialized."""
        if not self._initialized:
            await self.initialize()
            self._initialized = True
    
    async def initialize(self) -> None:
        """Initialize the storage backend."""
        await self._backend.initialize()
        self._initialized = True
    
    async def save(self, thread: Thread) -> Thread:
        """
        Save a thread to storage, filtering out system messages.
        
        System messages are not persisted to storage by design, but are kept
        in the original Thread object in memory.
        
        Args:
            thread: The Thread object to save
            
        Returns:
            The original Thread object (with system messages intact)
        """
        await self._ensure_initialized()
        
        # Create a filtered copy of the thread without system messages
        filtered_thread = Thread(
            id=thread.id,
            title=thread.title,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            attributes=thread.attributes.copy() if thread.attributes else {},
            source=thread.source.copy() if thread.source else None
        )
        
        # Only copy non-system messages to the filtered thread
        for message in thread.messages:
            if message.role != "system":
                # We create a shallow copy of the message to preserve the original
                filtered_thread.messages.append(message)
        
        # Save the filtered thread to storage
        await self._backend.save(filtered_thread)
        
        # Return the original thread (with system messages intact)
        return thread
    
    async def get(self, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID."""
        await self._ensure_initialized()
        return await self._backend.get(thread_id)
    
    async def delete(self, thread_id: str) -> bool:
        """Delete a thread by ID."""
        await self._ensure_initialized()
        return await self._backend.delete(thread_id)
    
    async def list(self, limit: int = 100, offset: int = 0) -> List[Thread]:
        """List threads with pagination."""
        await self._ensure_initialized()
        return await self._backend.list(limit, offset)
    
    async def find_by_attributes(self, attributes: Dict[str, Any]) -> List[Thread]:
        """Find threads by matching attributes."""
        await self._ensure_initialized()
        return await self._backend.find_by_attributes(attributes)
    
    async def find_by_source(self, source_name: str, properties: Dict[str, Any]) -> List[Thread]:
        """Find threads by source name and properties."""
        await self._ensure_initialized()
        return await self._backend.find_by_source(source_name, properties)
    
    async def list_recent(self, limit: Optional[int] = None) -> List[Thread]:
        """List recent threads."""
        await self._ensure_initialized()
        return await self._backend.list_recent(limit)
        
    async def find_messages_by_attribute(self, path: str, value: Any) -> bool:
        """
        Check if any messages exist with a specific attribute at a given JSON path.
        This is useful for checking if a message with specific metadata (like a Slack ts)
        has already been processed.
        
        Args:
            path: Dot-notation path to the attribute (e.g., "source.platform.attributes.ts")
            value: The value to search for
            
        Returns:
            True if any messages match, False otherwise
        """
        await self._ensure_initialized()
        if hasattr(self._backend, 'find_messages_by_attribute'):
            return await self._backend.find_messages_by_attribute(path, value)
        else:
            # Fallback implementation for backends that don't support this method
            # This is less efficient but provides compatibility
            threads = await self._backend.list_recent(100)  # Get recent threads
            
            # Check each thread's messages
            for thread in threads:
                for message in thread.messages:
                    # Navigate the path to get the value
                    current = message
                    parts = path.split('.')
                    
                    for part in parts:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        elif hasattr(current, part):
                            current = getattr(current, part)
                        else:
                            current = None
                            break
                    
                    # Check if we found a match
                    if current == value:
                        return True
            
            return False

    # Add properties to expose backend attributes
    @property
    def database_url(self):
        return getattr(self._backend, "database_url", None)

    @property
    def engine(self):
        return getattr(self._backend, "engine", None)

# Optional PostgreSQL-specific implementation
try:
    import asyncpg
    
    class SQLAlchemyThreadStore(ThreadStore):
        """PostgreSQL-based thread storage for production use."""
        
        def __init__(self, database_url):
            if not database_url.startswith('postgresql+asyncpg://'):
                database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
            super().__init__(database_url)
        
except ImportError:
    pass 