"""File storage implementation"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Set, List, Tuple
from pathlib import Path
import os
import uuid
import shutil
import hashlib
import asyncio
import mimetypes
from datetime import datetime, UTC
from sqlalchemy import select
from tyler.utils.logging import get_logger
import magic
import base64

# Get configured logger
logger = get_logger(__name__)

class FileStoreError(Exception):
    """Base exception for file store errors"""
    pass

class FileNotFoundError(FileStoreError):
    """Raised when a file is not found in storage"""
    pass

class StorageFullError(FileStoreError):
    """Raised when storage capacity is exceeded"""
    pass

class UnsupportedFileTypeError(FileStoreError):
    """Raised when file type is not allowed"""
    pass

class FileTooLargeError(FileStoreError):
    """Raised when file exceeds size limit"""
    pass

class FileStore:
    """
    File storage implementation
    
    The recommended way to create a FileStore is using the factory method:
    
    ```python
    # Create with default settings
    store = await FileStore.create()
    
    # Specify custom path
    store = await FileStore.create("/path/to/files")
    
    # Customize all settings
    store = await FileStore.create(
        base_path="/path/to/files",
        max_file_size=100*1024*1024,  # 100MB
        allowed_mime_types={"image/jpeg", "image/png"},
        max_storage_size=10*1024*1024*1024  # 10GB
    )
    ```
    
    The factory method validates storage configuration immediately, allowing
    early detection of storage access issues.
    """

    # Default configuration
    DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    DEFAULT_MAX_STORAGE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB
    DEFAULT_ALLOWED_MIME_TYPES = {
        # Documents
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'text/csv',
        'application/json',
        # Images
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp',
        'image/svg+xml',
        # Archives
        'application/zip',
        'application/x-tar',
        'application/gzip',
        # Audio formats
        'audio/mpeg',
        'audio/mp3',
        'audio/mp4',
        'audio/opus',
        'audio/ogg',
        'audio/wav',
        'audio/webm',
        'audio/aac',
        'audio/flac',
        'audio/x-m4a',
    }
    
    @classmethod
    async def create(cls, base_path: Optional[str] = None, max_file_size: Optional[int] = None, 
                    allowed_mime_types: Optional[Set[str]] = None, max_storage_size: Optional[int] = None) -> 'FileStore':
        """
        Factory method to create and validate a FileStore instance.
        
        This method validates storage configuration immediately, allowing
        early detection of storage access issues.
        
        Args:
            base_path: Base directory for file storage
            max_file_size: Maximum allowed file size in bytes
            allowed_mime_types: Set of allowed MIME types
            max_storage_size: Maximum total storage size in bytes
            
        Returns:
            Initialized FileStore instance
            
        Raises:
            FileStoreError: If storage directory cannot be created or accessed
        """
        # Create instance 
        store = cls(base_path, max_file_size, allowed_mime_types, max_storage_size)
        
        try:
            # Validate storage by writing and reading a test file
            test_id = str(uuid.uuid4())
            test_path = store._get_file_path(test_id)
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_content = b"storage validation"
            test_path.write_bytes(test_content)
            read_content = test_path.read_bytes()
            test_path.unlink()  # Clean up
            
            # Ensure content matches what we wrote
            if read_content != test_content:
                raise FileStoreError("Storage validation failed: content mismatch")
                
            # Check that we can create storage stats
            storage_size = await store.get_storage_size()
            logger.debug(f"Storage validation successful. Current storage size: {storage_size} bytes")
            
            return store
        except Exception as e:
            logger.error(f"Storage validation failed: {e}")
            raise FileStoreError(f"Storage validation failed: {e}")
    
    def __init__(self, base_path: Optional[str] = None, max_file_size: Optional[int] = None, 
                 allowed_mime_types: Optional[Set[str]] = None, max_storage_size: Optional[int] = None):
        """Initialize file store
        
        For production use, prefer the async factory method:
        `store = await FileStore.create(base_path, ...)`
        
        Args:
            base_path: Base directory for file storage. If not provided,
                      uses TYLER_FILE_STORAGE_PATH env var or defaults to
                      ~/.tyler/files
            max_file_size: Maximum allowed file size in bytes. If not provided,
                          uses TYLER_MAX_FILE_SIZE env var or defaults to 50MB
            allowed_mime_types: Set of allowed MIME types
            max_storage_size: Maximum total storage size in bytes. If not provided,
                            uses TYLER_MAX_STORAGE_SIZE env var or defaults to 5GB
        """
        # Get max file size from env var or default
        env_max_file_size = os.getenv('TYLER_MAX_FILE_SIZE')
        if max_file_size is not None:
            self.max_file_size = max_file_size
        elif env_max_file_size is not None:
            try:
                self.max_file_size = int(env_max_file_size)
            except ValueError:
                logger.warning(f"Invalid TYLER_MAX_FILE_SIZE value: {env_max_file_size}. Using default.")
                self.max_file_size = self.DEFAULT_MAX_FILE_SIZE
        else:
            self.max_file_size = self.DEFAULT_MAX_FILE_SIZE

        # Get max storage size from env var or default
        env_max_storage_size = os.getenv('TYLER_MAX_STORAGE_SIZE')
        if max_storage_size is not None:
            self.max_storage_size = max_storage_size
        elif env_max_storage_size is not None:
            try:
                self.max_storage_size = int(env_max_storage_size)
            except ValueError:
                logger.warning(f"Invalid TYLER_MAX_STORAGE_SIZE value: {env_max_storage_size}. Using default.")
                self.max_storage_size = self.DEFAULT_MAX_STORAGE_SIZE
        else:
            self.max_storage_size = self.DEFAULT_MAX_STORAGE_SIZE

        # Get allowed MIME types from env var or default
        env_mime_types = os.getenv('TYLER_ALLOWED_MIME_TYPES')
        if allowed_mime_types is not None:
            self.allowed_mime_types = allowed_mime_types
        elif env_mime_types is not None:
            try:
                # Split comma-separated list and strip whitespace
                mime_types = {mime.strip() for mime in env_mime_types.split(',')}
                # Validate each MIME type
                invalid_types = [mime for mime in mime_types if '/' not in mime]
                if invalid_types:
                    logger.warning(f"Invalid MIME types in TYLER_ALLOWED_MIME_TYPES: {invalid_types}. Using default.")
                    self.allowed_mime_types = self.DEFAULT_ALLOWED_MIME_TYPES
                else:
                    self.allowed_mime_types = mime_types
            except Exception as e:
                logger.warning(f"Error parsing TYLER_ALLOWED_MIME_TYPES: {e}. Using default.")
                self.allowed_mime_types = self.DEFAULT_ALLOWED_MIME_TYPES
        else:
            self.allowed_mime_types = self.DEFAULT_ALLOWED_MIME_TYPES

        if base_path:
            self.base_path = Path(base_path)
        else:
            env_path = os.getenv('TYLER_FILE_STORAGE_PATH')
            if env_path:
                self.base_path = Path(env_path).expanduser()
            else:
                # Default to ~/.tyler/files
                self.base_path = Path.home() / '.tyler' / 'files'
                
        # Ensure base directory exists with proper permissions
        self._ensure_directory()
        logger.debug(
            f"Initialized FileStore at {self.base_path} ("
            f"max_file_size={self.max_file_size}, "
            f"max_storage_size={self.max_storage_size}, "
            f"allowed_mime_types={sorted(self.allowed_mime_types)})"
        )

    def _ensure_directory(self) -> None:
        """Ensure the storage directory exists with proper permissions"""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            # Set directory permissions to 755 (rwxr-xr-x)
            self.base_path.chmod(0o755)
        except Exception as e:
            logger.error(f"Failed to create or set permissions on storage directory {self.base_path}: {e}")
            raise FileStoreError(f"Storage directory initialization failed: {e}")

    @classmethod
    def get_default_path(cls) -> Path:
        """Get the default file storage path based on environment or defaults"""
        env_path = os.getenv('TYLER_FILE_STORAGE_PATH')
        if env_path:
            return Path(env_path).expanduser()
        return Path.home() / '.tyler' / 'files'

    @classmethod
    def initialize_storage(cls) -> Path:
        """Initialize the file storage directory
        
        This can be called during application setup to ensure the storage
        directory exists before the FileStore is instantiated.
        
        Returns:
            Path to the initialized storage directory
        """
        storage_path = cls.get_default_path()
        storage_path.mkdir(parents=True, exist_ok=True)
        storage_path.chmod(0o755)
        return storage_path

    async def validate_file(self, content: bytes, filename: str, mime_type: Optional[str] = None) -> str:
        """Validate file content and type
        
        Args:
            content: File content as bytes
            filename: Original filename
            mime_type: Optional MIME type (will be detected if not provided)
            
        Returns:
            Validated MIME type
            
        Raises:
            UnsupportedFileTypeError: If file type is not allowed
            FileTooLargeError: If file exceeds size limit
        """
        # Check file size
        if len(content) > self.max_file_size:
            raise FileTooLargeError(
                f"File too large: {len(content)} bytes. Maximum allowed: {self.max_file_size} bytes"
            )

        # Detect or validate MIME type
        if not mime_type:
            mime_type = mimetypes.guess_type(filename)[0]
            if not mime_type:
                # Try to detect from content
                mime_type = magic.from_buffer(content, mime=True)
                logger.debug(f"Detected MIME type for {filename}: {mime_type}")

        if mime_type not in self.allowed_mime_types:
            raise UnsupportedFileTypeError(f"Unsupported file type: {mime_type}")

        return mime_type

    def _get_file_path(self, file_id: str, extension: Optional[str] = None) -> Path:
        """Get full path for file ID using sharded directory structure"""
        # Use first 2 chars of ID as subdirectory to avoid too many files in one dir
        filename = file_id[2:]
        if extension:
            filename = f"{filename}.{extension.lstrip('.')}"
        return self.base_path / file_id[:2] / filename

    async def save(self, content: bytes, filename: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """Save file to storage"""
        # Validate file
        mime_type = await self.validate_file(content, filename, mime_type)

        # Check storage capacity if limit set
        if self.max_storage_size:
            current_size = await self.get_storage_size()
            if len(content) + current_size > self.max_storage_size:
                raise StorageFullError(
                    f"Storage full: {current_size} bytes used, {len(content)} bytes needed, "
                    f"{self.max_storage_size} bytes maximum"
                )

        # Generate unique ID
        file_id = str(uuid.uuid4())
        
        # Get file extension from original filename
        extension = Path(filename).suffix.lstrip('.')
        
        # Get sharded path with extension
        file_path = self._get_file_path(file_id, extension)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content
        file_path.write_bytes(content)
        
        metadata = {
            'id': file_id,
            'filename': filename,
            'mime_type': mime_type,
            'storage_path': str(file_path.relative_to(self.base_path)),
            'storage_backend': 'local',
            'created_at': datetime.now(UTC),
            'metadata': {
                'size': len(content)
            }
        }
        
        logger.debug(f"Saved file {filename} ({len(content)} bytes) to {file_path}")
        logger.debug(f"Successfully stored attachment {filename} with MIME type {mime_type}")
        return metadata
    
    async def get(self, file_id: str, storage_path: Optional[str] = None) -> bytes:
        """Get file content from storage
        
        Args:
            file_id: The unique file identifier
            storage_path: Optional storage path from metadata (preferred if available)
            
        Returns:
            File content as bytes
            
        Raises:
            FileNotFoundError: If file cannot be found
        """
        if storage_path:
            # Use the exact path from metadata if available
            file_path = self.base_path / storage_path
        else:
            # Fallback to constructing path from ID (legacy support)
            file_path = self._get_file_path(file_id)
            
        if not file_path.exists():
            raise FileNotFoundError(f"File {file_id} not found at {file_path}")
            
        return file_path.read_bytes()
    
    async def delete(self, file_id: str, storage_path: Optional[str] = None) -> None:
        """Delete file from storage"""
        if storage_path:
            # Use the exact path from metadata if available
            file_path = self.base_path / storage_path
        else:
            # Fallback to constructing path from ID (legacy support)
            file_path = self._get_file_path(file_id)
            
        if not file_path.exists():
            raise FileNotFoundError(f"File {file_id} not found at {file_path}")
            
        file_path.unlink()
        
        # Try to remove parent directory if empty
        try:
            file_path.parent.rmdir()
        except OSError:
            # Directory not empty, ignore
            pass

    async def get_storage_size(self) -> int:
        """Get total storage size in bytes"""
        total = 0
        for path in self.base_path.rglob('*'):
            if path.is_file():
                total += path.stat().st_size
        return total

    async def get_file_count(self) -> int:
        """Get total number of files"""
        return len(list(self.base_path.rglob('*')))

    async def check_health(self) -> Dict[str, Any]:
        """Check storage health and return metrics"""
        try:
            total_size = await self.get_storage_size()
            file_count = await self.get_file_count()
            return {
                'healthy': True,
                'total_size': total_size,
                'file_count': file_count,
                'errors': []
            }
        except Exception as e:
            return {
                'healthy': False,
                'errors': [str(e)]
            }

    async def batch_save(self, files: List[Tuple[bytes, str, str]]) -> List[Dict[str, Any]]:
        """Save multiple files in one operation
        
        Args:
            files: List of tuples (content, filename, mime_type)
            
        Returns:
            List of file metadata dictionaries
        """
        return [await self.save(content, filename, mime_type) 
                for content, filename, mime_type in files]

    async def batch_delete(self, file_ids: List[str]) -> None:
        """Delete multiple files in one operation"""
        await asyncio.gather(*[self.delete(file_id) for file_id in file_ids])

    async def cleanup_orphaned_files(self, session) -> Tuple[int, List[str]]:
        """Clean up files that aren't referenced in the database
        
        Args:
            session: SQLAlchemy async session
            
        Returns:
            Tuple of (number of files deleted, list of errors)
        """
        # Import here to avoid circular dependency
        from tyler.database.thread_store import MessageRecord
        
        # Get all file IDs from messages
        query = select(MessageRecord.attachments)
        result = await session.execute(query)
        db_files = set()
        for row in result.scalars():
            if row:
                for attachment in row:
                    if attachment.get('file_id'):
                        db_files.add(attachment['file_id'])

        # Get all files in storage
        stored_files = await self.list_files()
        
        # Find orphaned files
        orphaned = set(stored_files) - db_files
        
        # Delete orphaned files
        errors = []
        deleted = 0
        for file_id in orphaned:
            try:
                await self.delete(file_id)
                deleted += 1
            except Exception as e:
                errors.append(f"Failed to delete {file_id}: {str(e)}")
                
        return deleted, errors

    async def list_files(self) -> List[str]:
        """List all file IDs in storage"""
        files = []
        for path in self.base_path.rglob('*'):
            if path.is_file():
                # Reconstruct file ID from path - include parent dir name and full filename
                file_id = path.parent.name + path.stem
                files.append(file_id)
        return files

    def _handle_data_url(self, content: bytes) -> bytes:
        """Handle data URLs"""
        if self.content.startswith('data:'):
            # Handle data URLs
            header, encoded = self.content.split(",", 1)
            return base64.b64decode(encoded)
        return content

    @classmethod
    def get_base_path(cls) -> str:
        """Get the base storage path from environment variable"""
        env_path = os.getenv('TYLER_FILE_STORAGE_PATH')
        if not env_path:
            raise ValueError("TYLER_FILE_STORAGE_PATH environment variable is not set. This is required for file storage.")
        return env_path
        
    @classmethod
    def get_file_url(cls, relative_path: str) -> str:
        """
        Get the full URL for a file based on its relative path.
        
        Args:
            relative_path: The path relative to the base storage path
            
        Returns:
            The full URL for the file
        """
        # Get the base path
        base_path = cls.get_base_path()
        
        # Construct the full URL by combining the base path and relative path
        # Make sure there's exactly one slash between them
        if base_path.endswith('/'):
            base_path = base_path[:-1]
        if relative_path.startswith('/'):
            relative_path = relative_path[1:]
            
        return f"{base_path}/{relative_path}"