import os
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import AsyncGenerator
import uuid
import asyncio
from tyler.storage.file_store import (
    FileStore, 
    FileStoreError,
    FileNotFoundError,
    StorageFullError,
    UnsupportedFileTypeError,
    FileTooLargeError
)

@pytest.fixture
def temp_dir():
    """Create a temporary directory for file storage tests"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
async def file_store(temp_dir):
    """Create a FileStore instance for testing"""
    store = FileStore(
        base_path=temp_dir,
        max_file_size=1024 * 1024,  # 1MB
        allowed_mime_types={"text/plain", "application/json", "image/jpeg"},
        max_storage_size=10 * 1024 * 1024  # 10MB
    )
    yield store

@pytest.fixture
def temp_storage_path(tmp_path):
    """Create a temporary directory for file storage"""
    storage_path = tmp_path / "file_store"
    storage_path.mkdir()
    return storage_path

@pytest.fixture
async def temp_store() -> AsyncGenerator[FileStore, None]:
    """Create a temporary FileStore for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = FileStore(base_path=temp_dir)
        yield store

# Configuration Tests

def test_default_configuration(temp_storage_path):
    """Test FileStore initializes with default configuration"""
    store = FileStore(base_path=str(temp_storage_path))
    assert store.max_file_size == FileStore.DEFAULT_MAX_FILE_SIZE
    assert store.max_storage_size == FileStore.DEFAULT_MAX_STORAGE_SIZE
    assert store.allowed_mime_types == FileStore.DEFAULT_ALLOWED_MIME_TYPES

def test_env_var_configuration(temp_storage_path, monkeypatch):
    """Test FileStore respects environment variables"""
    # Set environment variables
    monkeypatch.setenv('TYLER_MAX_FILE_SIZE', '1048576')  # 1MB
    monkeypatch.setenv('TYLER_MAX_STORAGE_SIZE', '10485760')  # 10MB
    
    store = FileStore(base_path=str(temp_storage_path))
    assert store.max_file_size == 1048576
    assert store.max_storage_size == 10485760

def test_invalid_env_vars_use_defaults(temp_storage_path, monkeypatch):
    """Test FileStore handles invalid environment variables gracefully"""
    # Set invalid environment variables
    monkeypatch.setenv('TYLER_MAX_FILE_SIZE', 'invalid')
    monkeypatch.setenv('TYLER_MAX_STORAGE_SIZE', 'invalid')
    
    store = FileStore(base_path=str(temp_storage_path))
    assert store.max_file_size == FileStore.DEFAULT_MAX_FILE_SIZE
    assert store.max_storage_size == FileStore.DEFAULT_MAX_STORAGE_SIZE

def test_constructor_overrides_env_vars(temp_storage_path, monkeypatch):
    """Test constructor parameters override environment variables"""
    # Set environment variables
    monkeypatch.setenv('TYLER_MAX_FILE_SIZE', '1048576')  # 1MB
    monkeypatch.setenv('TYLER_MAX_STORAGE_SIZE', '10485760')  # 10MB
    
    # Constructor values should override env vars
    store = FileStore(
        base_path=str(temp_storage_path),
        max_file_size=2097152,  # 2MB
        max_storage_size=20971520  # 20MB
    )
    assert store.max_file_size == 2097152
    assert store.max_storage_size == 20971520

# MIME Type Tests

def test_env_var_mime_types(temp_storage_path, monkeypatch):
    """Test FileStore respects MIME type environment variables"""
    # Set environment variable
    monkeypatch.setenv('TYLER_ALLOWED_MIME_TYPES', 'image/jpeg,image/png,application/pdf')
    
    store = FileStore(base_path=str(temp_storage_path))
    assert store.allowed_mime_types == {'image/jpeg', 'image/png', 'application/pdf'}

def test_invalid_mime_types_use_defaults(temp_storage_path, monkeypatch):
    """Test FileStore handles invalid MIME types gracefully"""
    # Test with invalid format
    monkeypatch.setenv('TYLER_ALLOWED_MIME_TYPES', 'invalid,image/png,not-a-mime-type')
    
    store = FileStore(base_path=str(temp_storage_path))
    assert store.allowed_mime_types == FileStore.DEFAULT_ALLOWED_MIME_TYPES

def test_mime_types_constructor_override(temp_storage_path, monkeypatch):
    """Test constructor MIME types override environment variables"""
    # Set environment variable
    monkeypatch.setenv('TYLER_ALLOWED_MIME_TYPES', 'image/jpeg,image/png')
    
    # Constructor values should override env vars
    custom_types = {'application/pdf', 'text/plain'}
    store = FileStore(
        base_path=str(temp_storage_path),
        allowed_mime_types=custom_types
    )
    assert store.allowed_mime_types == custom_types

# File Operation Tests

@pytest.mark.asyncio
async def test_save_and_get(temp_store: FileStore):
    """Test basic file save and retrieval."""
    content = b'Hello, World!'
    filename = 'test.txt'
    
    # Test saving
    result = await temp_store.save(content=content, filename=filename)
    assert result['id'] is not None
    assert result['storage_path'] is not None
    assert result['filename'] == filename
    assert result['mime_type'] == 'text/plain'
    assert result['metadata']['size'] == len(content)
    
    # Test retrieval
    retrieved = await temp_store.get(result['id'], result['storage_path'])
    assert retrieved == content
    
    # Verify file exists on disk
    full_path = temp_store.base_path / result['storage_path']
    assert full_path.exists()
    assert full_path.stat().st_size == len(content)

@pytest.mark.asyncio
async def test_file_not_found(temp_store: FileStore):
    """Test handling of non-existent files."""
    with pytest.raises(FileNotFoundError):
        await temp_store.get('nonexistent-id')

@pytest.mark.asyncio
async def test_delete(temp_store: FileStore):
    """Test file deletion."""
    content = b'Delete me'
    result = await temp_store.save(content=content, filename='delete.txt')
    
    # Verify file exists
    file_path = temp_store.base_path / result['storage_path']
    assert file_path.exists()
    
    # Delete file using storage path
    await temp_store.delete(result['id'], result['storage_path'])
    
    # Verify file is gone
    assert not file_path.exists()
    with pytest.raises(FileNotFoundError):
        await temp_store.get(result['id'], result['storage_path'])

# Limit Enforcement Tests

@pytest.mark.asyncio
async def test_file_size_limit_enforcement(temp_storage_path):
    """Test FileStore enforces file size limits"""
    store = FileStore(
        base_path=str(temp_storage_path),
        max_file_size=100  # Very small limit for testing
    )
    
    # Small file should work
    small_content = b"small file"
    await store.save(small_content, "small.txt")
    
    # Large file should fail
    large_content = b"x" * 200
    with pytest.raises(FileTooLargeError):
        await store.save(large_content, "large.txt")

@pytest.mark.asyncio
async def test_storage_size_limit_enforcement(temp_storage_path):
    """Test FileStore enforces total storage size limits"""
    store = FileStore(
        base_path=str(temp_storage_path),
        max_storage_size=150  # Very small limit for testing
    )
    
    # First file should work
    content1 = b"x" * 100
    await store.save(content1, "file1.txt")
    
    # Second file should fail due to total size limit
    content2 = b"x" * 100
    with pytest.raises(StorageFullError):
        await store.save(content2, "file2.txt")

@pytest.mark.asyncio
async def test_mime_type_validation(temp_storage_path):
    """Test FileStore enforces MIME type restrictions"""
    store = FileStore(
        base_path=str(temp_storage_path),
        allowed_mime_types={'text/plain'}
    )
    
    # Create a text file
    text_content = b"text file"
    await store.save(text_content, "test.txt")
    
    # Try to save with unsupported MIME type
    pdf_content = b"%PDF-1.4"  # Simple PDF header
    with pytest.raises(UnsupportedFileTypeError):
        await store.save(pdf_content, "test.pdf")

# Metrics and Batch Operation Tests

@pytest.mark.asyncio
async def test_storage_metrics(temp_store: FileStore):
    """Test storage size and file count metrics."""
    content1 = b'File 1'
    content2 = b'File 2'
    
    # Save two files
    await temp_store.save(content=content1, filename='file1.txt')
    await temp_store.save(content=content2, filename='file2.txt')
    
    # Check metrics
    size = await temp_store.get_storage_size()
    count = await temp_store.get_file_count()
    
    # Only count actual files, not directories
    expected_size = len(content1) + len(content2)
    assert size == expected_size
    
    # Count should include both files and their parent directories
    # Each file is stored in a sharded directory structure: base_dir/xx/filename
    # So for each file we have: the file itself and its parent directory
    expected_count = 4  # 2 files + 2 parent directories
    assert count == expected_count

@pytest.mark.asyncio
async def test_batch_operations(temp_store: FileStore):
    """Test batch save and delete operations."""
    files = [
        (b'Content 1', 'file1.txt', 'text/plain'),
        (b'Content 2', 'file2.txt', 'text/plain')
    ]
    
    # Test batch save
    results = await temp_store.batch_save(files)
    assert len(results) == 2
    
    # Verify files exist
    for result in results:
        content = await temp_store.get(result['id'], result['storage_path'])
        assert content is not None
    
    # Test batch delete
    for result in results:
        await temp_store.delete(result['id'], result['storage_path'])
    
    # Verify files are gone
    for result in results:
        with pytest.raises(FileNotFoundError):
            await temp_store.get(result['id'], result['storage_path'])

@pytest.mark.asyncio
async def test_health_check(temp_store: FileStore):
    """Test health check functionality."""
    health = await temp_store.check_health()
    
    assert 'healthy' in health
    assert 'total_size' in health
    assert 'file_count' in health
    assert 'errors' in health
    assert health['healthy'] is True
    assert isinstance(health['total_size'], int)
    assert isinstance(health['file_count'], int)
    assert isinstance(health['errors'], list)

@pytest.mark.asyncio
async def test_create(temp_dir):
    """Test the factory pattern for creating FileStore instances"""
    # Create with factory pattern
    store = await FileStore.create(
        base_path=temp_dir,
        max_file_size=2048 * 1024,  # 2MB
        allowed_mime_types={"application/pdf", "image/png"},
        max_storage_size=20 * 1024 * 1024  # 20MB
    )
    
    # Verify store is configured correctly
    assert store.base_path == Path(temp_dir)
    assert store.max_file_size == 2048 * 1024
    assert store.allowed_mime_types == {"application/pdf", "image/png"}
    assert store.max_storage_size == 20 * 1024 * 1024
    
    # Test that we can use the store
    test_content = b"Test PDF content"
    # We'll use a mock PDF - it won't validate as real PDF but our test setup allows this MIME
    metadata = await store.save(test_content, "test.pdf", "application/pdf")
    
    # Verify content was saved
    content = await store.get(metadata["id"], metadata["storage_path"])
    assert content == test_content 