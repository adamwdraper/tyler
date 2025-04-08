"""File storage module for Tyler"""
import os
from typing import Optional, Set
from .file_store import FileStore
import warnings
import logging

# Get logger
logger = logging.getLogger(__name__)

class FileStoreManager:
    """Manages file store instance and configuration"""
    _instance: Optional[FileStore] = None
    
    @classmethod
    def get_instance(cls) -> FileStore:
        """Get the initialized file store instance
        
        Returns:
            The initialized FileStore
            
        Raises:
            RuntimeError: If file store hasn't been initialized
        """
        if cls._instance is None:
            # Auto-initialize with defaults
            warnings.warn(
                "FileStore hasn't been initialized yet. Using default configuration. "
                "For production use, call 'await initialize_file_store()' during application startup.",
                RuntimeWarning,
                stacklevel=2
            )
            cls._instance = FileStore()
        return cls._instance
    
    @classmethod
    def set_instance(cls, store: FileStore) -> None:
        """Set the file store instance"""
        cls._instance = store

# Convenience function for backwards compatibility
def get_file_store() -> FileStore:
    """Get the initialized file store instance"""
    return FileStoreManager.get_instance()

async def initialize_file_store(base_path: Optional[str] = None, 
                             max_file_size: Optional[int] = None,
                             allowed_mime_types: Optional[Set[str]] = None, 
                             max_storage_size: Optional[int] = None) -> FileStore:
    """
    Initialize the global file store instance using the factory pattern.
    
    This function should be called during application startup to ensure
    the file store is properly initialized and storage is accessible.
    
    Args:
        base_path: Base directory for file storage
        max_file_size: Maximum allowed file size in bytes
        allowed_mime_types: Set of allowed MIME types
        max_storage_size: Maximum total storage size in bytes
        
    Returns:
        The initialized FileStore instance
        
    Raises:
        FileStoreError: If storage directory cannot be created or accessed
    """
    try:
        # Create and validate file store
        store = await FileStore.create(
            base_path=base_path,
            max_file_size=max_file_size,
            allowed_mime_types=allowed_mime_types,
            max_storage_size=max_storage_size
        )
        
        # Set as global instance
        FileStoreManager.set_instance(store)
        logger.info(f"FileStore initialized successfully at {store.base_path}")
        
        return store
    except Exception as e:
        logger.error(f"Failed to initialize FileStore: {e}")
        raise 