"""Thread storage implementation."""
from typing import Optional, Dict, Any, List
from tyler.models.thread import Thread
from tyler.utils.logging import get_logger
from .storage_backend import MemoryBackend, SQLBackend
import os

logger = get_logger(__name__)

class ThreadStore:
    """
    Thread storage implementation with pluggable backends.
    Supports both in-memory and SQL (SQLite/PostgreSQL) storage.
    
    Key characteristics:
    - Unified interface for all storage types
    - Automatic backend selection based on configuration
    - Memory backend for development/testing
    - SQLite for local persistence
    - PostgreSQL for production
    - Built-in connection pooling for SQLBackend
    
    Usage:
        # Memory storage (default when no environment variables or URL provided)
        store = ThreadStore()
        
        # Environment variable configuration (if TYLER_DB_TYPE is set)
        # Set TYLER_DB_TYPE to 'postgresql' or 'sqlite'
        # For PostgreSQL, also set TYLER_DB_HOST, TYLER_DB_PORT, TYLER_DB_NAME, TYLER_DB_USER, TYLER_DB_PASSWORD
        # For SQLite, also set TYLER_DB_PATH
        store = ThreadStore()
        
        # Explicit SQLite configuration
        store = ThreadStore(database_url="sqlite+aiosqlite:///path/to/db.sqlite")
        
        # Explicit PostgreSQL configuration
        store = ThreadStore(database_url="postgresql+asyncpg://user:pass@localhost/dbname")
        
        # Thread operations
        thread = Thread()
        await store.save(thread)
        result = await store.get(thread.id)
        
    Connection pooling settings can be configured via environment variables:
        - TYLER_DB_POOL_SIZE: Max number of connections to keep open (default: 5)
        - TYLER_DB_MAX_OVERFLOW: Max number of connections to create above pool_size (default: 10)
        - TYLER_DB_POOL_TIMEOUT: Seconds to wait for a connection from pool (default: 30)
        - TYLER_DB_POOL_RECYCLE: Seconds after which a connection is recycled (default: 300)
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize thread store with optional database URL.
        If no URL is provided, checks environment variables for configuration.
        If no environment variables are set, uses in-memory storage.
        
        Args:
            database_url: SQLAlchemy async database URL. Examples:
                - "postgresql+asyncpg://user:pass@localhost/dbname"
                - "sqlite+aiosqlite:///path/to/db.sqlite"
                - None to use environment variables or in-memory storage
                
        Raises:
            ValueError: If TYLER_DB_TYPE is set but required environment variables are missing
        """
        if database_url is None:
            # Check for environment variables
            db_type = os.getenv("TYLER_DB_TYPE")
            if db_type in ["postgresql", "postgres"]:
                # Validate required PostgreSQL environment variables
                required_vars = ["TYLER_DB_USER", "TYLER_DB_PASSWORD", "TYLER_DB_HOST", "TYLER_DB_PORT", "TYLER_DB_NAME"]
                missing_vars = [var for var in required_vars if not os.getenv(var)]
                
                if missing_vars:
                    error_msg = f"PostgreSQL database type specified but missing required environment variables: {', '.join(missing_vars)}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                # Construct PostgreSQL URL from environment variables
                db_user = os.getenv("TYLER_DB_USER")
                db_password = os.getenv("TYLER_DB_PASSWORD")
                db_host = os.getenv("TYLER_DB_HOST")
                db_port = os.getenv("TYLER_DB_PORT")
                db_name = os.getenv("TYLER_DB_NAME")
                
                database_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
                logger.info(f"Using PostgreSQL database from environment variables: {db_host}:{db_port}/{db_name}")
                self._backend = SQLBackend(database_url)
            elif db_type == "sqlite":
                # Validate required SQLite environment variables
                if not os.getenv("TYLER_DB_PATH"):
                    error_msg = "SQLite database type specified but TYLER_DB_PATH environment variable is missing"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                # Construct SQLite URL
                db_path = os.getenv("TYLER_DB_PATH")
                database_url = f"sqlite+aiosqlite:///{db_path}"
                logger.info(f"Using SQLite database from environment variables: {db_path}")
                self._backend = SQLBackend(database_url)
            else:
                # Default to in-memory storage
                logger.info("No database configuration found. Using in-memory storage.")
                self._backend = MemoryBackend()
        else:
            # Use SQLBackend with the provided URL
            logger.info(f"Using explicitly provided database URL: {database_url}")
            self._backend = SQLBackend(database_url)
        
        # Add initialization flag
        self._initialized = False
    
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
        """Save a thread to storage."""
        await self._ensure_initialized()
        return await self._backend.save(thread)
    
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
        
        def __init__(self, database_url: str):
            if not database_url.startswith('postgresql+asyncpg://'):
                database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
            super().__init__(database_url)
        
except ImportError:
    pass 