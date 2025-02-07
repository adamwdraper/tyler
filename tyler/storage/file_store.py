"""File storage implementation"""
from typing import Optional, Dict, Any, Set, List, Tuple
from pathlib import Path
import os
import uuid
import shutil
import logging
from datetime import datetime, UTC
import mimetypes
import asyncio
from sqlalchemy import select

logger = logging.getLogger(__name__)

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
    """File storage implementation using local filesystem
    
    Features:
    - File validation (size and type)
    - Sharded directory structure
    - Configurable limits
    - File cleanup
    - Health checks
    """

    # Default configuration
    DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
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
    }
    
    def __init__(
        self,
        base_path: Optional[str] = None,
        max_file_size: Optional[int] = None,
        allowed_mime_types: Optional[Set[str]] = None,
        max_storage_size: Optional[int] = None
    ):
        """Initialize file store with configuration
        
        Args:
            base_path: Base directory for file storage. If not provided,
                      uses TYLER_FILE_STORAGE_PATH env var or defaults to
                      ~/.tyler/files
            max_file_size: Maximum allowed file size in bytes
            allowed_mime_types: Set of allowed MIME types
            max_storage_size: Maximum total storage size in bytes
        """
        self.max_file_size = max_file_size or self.DEFAULT_MAX_FILE_SIZE
        self.allowed_mime_types = allowed_mime_types or self.DEFAULT_ALLOWED_MIME_TYPES
        self.max_storage_size = max_storage_size

        if base_path:
            self.base_path = Path(base_path).expanduser().resolve()
        else:
            env_path = os.getenv('TYLER_FILE_STORAGE_PATH')
            if env_path:
                self.base_path = Path(env_path).expanduser().resolve()
            else:
                # Default to ~/.tyler/files
                self.base_path = Path.home() / '.tyler' / 'files'
                
        # Ensure base directory exists with proper permissions
        self.base_path.mkdir(parents=True, exist_ok=True, mode=0o755)
        logger.info(f"Initialized FileStore at {self.base_path}")

    def _get_file_path(self, file_id: str) -> Path:
        """Get full path for file ID using sharded directory structure"""
        # Use first 2 chars of ID as subdirectory to avoid too many files in one dir
        return self.base_path / file_id[:2] / file_id[2:]

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
                import magic
                mime_type = magic.from_buffer(content, mime=True)

        if mime_type not in self.allowed_mime_types:
            raise UnsupportedFileTypeError(f"Unsupported file type: {mime_type}")

        return mime_type
        
    async def save(self, content: bytes, filename: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """Save file to local filesystem"""
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
        
        # Get sharded path
        file_path = self._get_file_path(file_id)
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
        return metadata
    
    async def get(self, file_id: str) -> bytes:
        """Get file content from local filesystem"""
        file_path = self._get_file_path(file_id)
        if not file_path.exists():
            raise FileNotFoundError(f"File {file_id} not found at {file_path}")
            
        return file_path.read_bytes()
    
    async def delete(self, file_id: str) -> None:
        """Delete file from local filesystem"""
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
        # Import here to avoid circular import
        from tyler.database.models import MessageRecord
        
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
                # Reconstruct file ID from path
                file_id = path.parent.name + path.name
                files.append(file_id)
        return files 