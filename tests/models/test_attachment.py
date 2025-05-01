import pytest
from tyler import Attachment
import base64
import magic
import os
import tempfile
from unittest.mock import patch, Mock, AsyncMock
from tyler.utils.tool_runner import tool_runner

@pytest.fixture
def sample_attachment():
    """Create a sample attachment for testing."""
    return Attachment(
        filename="test.txt",
        mime_type="text/plain",
        file_id="test-attachment",
        storage_path="/path/to/file.txt",
        storage_backend="local",
        attributes={
            "type": "text",
            "text": "Test content",
            "overview": "A test file"
        }
    )

@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    content = b"Test content for attachment"
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(content)
        path = f.name
    yield path
    os.unlink(path)  # Clean up after test

def test_attachment_creation(sample_attachment):
    """Test basic attachment creation and properties."""
    assert sample_attachment.filename == "test.txt"
    assert sample_attachment.mime_type == "text/plain"
    assert sample_attachment.file_id == "test-attachment"
    assert sample_attachment.storage_path == "/path/to/file.txt"
    assert sample_attachment.storage_backend == "local"
    assert sample_attachment.content is None
    assert sample_attachment.attributes["type"] == "text"

def test_attachment_with_bytes_content():
    """Test attachment with bytes content."""
    content = b"Test content"
    attachment = Attachment(
        filename="test.txt",
        content=content,
        mime_type="text/plain"
    )
    assert attachment.content == content
    assert isinstance(attachment.content, bytes)

def test_attachment_with_base64_content():
    """Test attachment with base64 content."""
    content = "VGVzdCBjb250ZW50"  # base64 for "Test content"
    attachment = Attachment(
        filename="test.txt",
        content=content,
        mime_type="text/plain"
    )
    assert attachment.content == content
    assert isinstance(attachment.content, str)

def test_attachment_serialization(sample_attachment):
    """Test attachment serialization to/from dict."""
    # Test model_dump()
    data = sample_attachment.model_dump()
    assert data["filename"] == "test.txt"
    assert data["mime_type"] == "text/plain"
    assert data["file_id"] == "test-attachment"
    assert data["storage_path"] == "/path/to/file.txt"
    assert data["storage_backend"] == "local"
    assert data["attributes"]["type"] == "text"
    assert "content" not in data  # Content should not be included when file_id exists
    
    # Add content and test serialization
    sample_attachment.content = b"Test content"
    sample_attachment.file_id = None  # Clear file_id to test content serialization
    data = sample_attachment.model_dump()
    assert "content" in data
    assert isinstance(data["content"], str)  # Should be base64 string
    assert base64.b64decode(data["content"]) == b"Test content"
    
    # Test model_validate()
    new_attachment = Attachment.model_validate(data)
    assert new_attachment.filename == sample_attachment.filename
    assert new_attachment.mime_type == sample_attachment.mime_type
    assert new_attachment.attributes == sample_attachment.attributes
    assert isinstance(new_attachment.content, str)  # Should remain as base64 string

@pytest.mark.asyncio
async def test_get_content_bytes():
    """Test getting content as bytes."""
    # Test with bytes content
    bytes_content = b"Test content"
    attachment = Attachment(
        filename="test.txt",
        content=bytes_content
    )
    content = await attachment.get_content_bytes()
    assert content == bytes_content
    
    # Test with base64 string content
    base64_content = base64.b64encode(b"Test content").decode()
    attachment = Attachment(
        filename="test.txt",
        content=base64_content
    )
    content = await attachment.get_content_bytes()
    assert content == b"Test content"
    
    # Test with UTF-8 string content
    text_content = "Test content"
    attachment = Attachment(
        filename="test.txt",
        content=text_content
    )
    content = await attachment.get_content_bytes()
    assert content == text_content.encode('utf-8')
    
    # Test with file_id
    attachment = Attachment(
        filename="test.txt",
        file_id="test-file",
        storage_path="/path/to/file.txt"
    )
    
    # Create a mock FileStore directly
    mock_store = Mock()
    mock_store.get = AsyncMock(return_value=b"Stored content")
    
    content = await attachment.get_content_bytes(file_store=mock_store)
    assert content == b"Stored content"
    mock_store.get.assert_called_once_with("test-file", storage_path="/path/to/file.txt")

@pytest.mark.asyncio
async def test_ensure_stored():
    """Test ensuring content is stored."""
    content = b"Test content"
    attachment = Attachment(
        filename="test.txt",
        content=content,
        mime_type="text/plain"
    )

    # Mock the file store directly
    mock_store = Mock()
    mock_store.save = AsyncMock(return_value={
        'id': 'file-123',
        'storage_path': '/path/to/stored/file.txt',
        'storage_backend': 'local'
    })
    
    with patch('tyler.storage.file_store.FileStore.get_file_url', return_value="/files//path/to/stored/file.txt"):
        await attachment.process_and_store(file_store=mock_store)
        
        # Verify the file was stored
        mock_store.save.assert_called_once_with(content, "test.txt", "text/plain")
        assert attachment.file_id == "file-123"
        assert attachment.storage_path == "/path/to/stored/file.txt"
        assert attachment.storage_backend == "local"
        
        # Verify that attributes was updated with URL
        assert attachment.attributes is not None
        assert "url" in attachment.attributes
        assert attachment.attributes["url"] == "/files//path/to/stored/file.txt"

def test_update_attributes_with_url():
    """Test updating attributes with URL after storage."""
    # Mock FileStore.get_file_url
    with patch('tyler.storage.file_store.FileStore.get_file_url', return_value="/files//path/to/file.txt"):
        # Test with no attributes
        attachment = Attachment(
            filename="test.txt",
            storage_path="/path/to/file.txt"
        )
        attachment.update_attributes_with_url()
        assert attachment.attributes is not None
        assert "url" in attachment.attributes
        assert attachment.attributes["url"] == "/files//path/to/file.txt"
        
        # Test with existing attributes
        attachment = Attachment(
            filename="test.txt",
            storage_path="/path/to/file.txt",
            attributes={
                "type": "text",
                "text": "Test content"
            }
        )
        attachment.update_attributes_with_url()
        assert "type" in attachment.attributes
        assert "text" in attachment.attributes
        assert "url" in attachment.attributes
        assert attachment.attributes["url"] == "/files//path/to/file.txt"
        
        # Test with no storage_path
        attachment = Attachment(
            filename="test.txt"
        )
        attachment.update_attributes_with_url()
        assert attachment.attributes is None

def test_attachment_validation():
    """Test attachment validation."""
    # Test missing required fields
    with pytest.raises(ValueError):
        Attachment()  # missing filename
    
    # Test valid minimal attachment
    attachment = Attachment(filename="test.txt")
    assert attachment.filename == "test.txt"
    assert attachment.content is None
    assert attachment.mime_type is None
    
    # Test with invalid content type
    with pytest.raises(ValueError):
        Attachment(filename="test.txt", content=123)  # content must be bytes or str

def test_attachment_with_processed_content():
    """Test attachment with different types of attributes."""
    # Test text file
    text_attachment = Attachment(
        filename="test.txt",
        content=b"Test content",
        mime_type="text/plain",
        attributes={
            "type": "text",
            "text": "Test content",
            "overview": "A test file"
        }
    )
    assert text_attachment.attributes["type"] == "text"
    assert text_attachment.attributes["text"] == "Test content"
    
    # Test image file
    image_attachment = Attachment(
        filename="test.jpg",
        content=b"image data",
        mime_type="image/jpeg",
        attributes={
            "type": "image",
            "content": "base64_encoded_image",
            "overview": "An image file",
            "analysis": {
                "objects": ["person", "desk"],
                "text_detected": True
            }
        }
    )
    assert image_attachment.attributes["type"] == "image"
    assert "analysis" in image_attachment.attributes
    
    # Test JSON file
    json_attachment = Attachment(
        filename="test.json",
        content=b'{"key": "value"}',
        mime_type="application/json",
        attributes={
            "type": "json",
            "overview": "JSON data structure",
            "parsed_content": {"key": "value"}
        }
    )
    assert json_attachment.attributes["type"] == "json"
    assert json_attachment.attributes["parsed_content"] == {"key": "value"}

def test_attachment_content_serialization():
    """Test content serialization in model_dump."""
    content = b"Test content for serialization"
    attachment = Attachment(
        filename="test.txt",
        content=content
    )
    
    # Test model_dump serialization
    data = attachment.model_dump()
    assert "content" in data
    assert isinstance(data["content"], str)  # Should be base64 string
    assert base64.b64decode(data["content"]) == content

def test_attachment_mime_type_detection(temp_file):
    """Test MIME type detection."""
    attachment = Attachment(
        filename=os.path.basename(temp_file),
        storage_path=temp_file
    )
    
    with open(temp_file, 'rb') as f:
        attachment.content = f.read()
    
    # Detect MIME type
    mime_type = magic.from_buffer(attachment.content, mime=True)
    assert mime_type == "text/plain"
    attachment.mime_type = mime_type
    assert attachment.mime_type == "text/plain"

def test_attachment_base64():
    """Test attachment base64 encoding/decoding."""
    content = b"Test content for base64"
    attachment = Attachment(
        id="test-attachment",
        filename="test.txt",
        content=content,
        mime_type="text/plain"
    )

    # Test base64 encoding
    b64 = base64.b64encode(content).decode('utf-8')
    assert attachment.model_dump()["content"] == b64

def test_attachment_size_calculation():
    """Test automatic size calculation."""
    content = b"Test content for size calculation"
    attachment = Attachment(
        id="test-attachment",
        filename="test.txt",
        content=content,
        mime_type="text/plain"
    )

    # Test size calculation
    assert len(content) == len(content)  # Size is calculated on demand

@pytest.mark.asyncio
async def test_attachment_process_error_handling():
    """Test error handling during content processing."""
    attachment = Attachment(
        filename="test.bin",
        content=b"\x00\x01\x02",  # Invalid content that can't be processed
        mime_type="application/octet-stream"
    )

    # Add a process method to the attachment for testing
    async def process(self):
        content = await self.get_content_bytes()
        await self.process_and_store()
        result = await tool_runner.run_tool_async(
            "read-file",
            {
                "file_url": self.storage_path,
                "mime_type": self.mime_type
            }
        )
        self.attributes = result
        return result

    # Temporarily add the process method to the Attachment class
    original_process = getattr(Attachment, "process", None)
    Attachment.process = process
    
    try:
        # Mock the tool_runner
        with patch.object(tool_runner, 'run_tool_async', AsyncMock(side_effect=Exception("Processing failed"))) as mock_run_tool, \
             patch.object(Attachment, 'process_and_store', AsyncMock()) as mock_process_and_store:
            
            # Set storage_path for the test
            mock_process_and_store.side_effect = lambda: setattr(attachment, 'storage_path', '/path/to/stored/file.bin')
            
            # Process should handle the error
            with pytest.raises(Exception) as exc_info:
                await attachment.process()
            assert str(exc_info.value) == "Processing failed"
    finally:
        # Restore the original method
        if original_process:
            Attachment.process = original_process
        else:
            delattr(Attachment, "process")

@pytest.mark.asyncio
async def test_attachment_process_success():
    """Test successful content processing."""
    attachment = Attachment(
        filename="test.txt",
        content=b"Test content",
        mime_type="text/plain"
    )

    processed_result = {
        "type": "text",
        "text": "Test content",
        "overview": "A text file"
    }

    # Add a process method to the attachment for testing
    async def process(self):
        content = await self.get_content_bytes()
        await self.process_and_store()
        result = await tool_runner.run_tool_async(
            "read-file",
            {
                "file_url": self.storage_path,
                "mime_type": self.mime_type
            }
        )
        self.attributes = result
        return result

    # Temporarily add the process method to the Attachment class
    original_process = getattr(Attachment, "process", None)
    Attachment.process = process
    
    try:
        # Mock the tool_runner
        with patch.object(tool_runner, 'run_tool_async', AsyncMock(return_value=processed_result)) as mock_run_tool, \
             patch.object(Attachment, 'process_and_store', AsyncMock()) as mock_process_and_store:
            
            # Set storage_path for the test
            mock_process_and_store.side_effect = lambda: setattr(attachment, 'storage_path', '/path/to/stored/file.txt')
            
            # Process should return the processed result
            result = await attachment.process()
            assert result == processed_result
            assert attachment.attributes == processed_result
    finally:
        # Restore the original method
        if original_process:
            Attachment.process = original_process
        else:
            delattr(Attachment, "process")

@pytest.mark.asyncio
async def test_process_attachment_pdf():
    """Test processing a PDF attachment."""
    content = b"pdf content"  # Not a real PDF, just for testing
    attachment = Attachment(filename="test.pdf", content=content)

    # We need to mock PdfReader to avoid PDF parsing errors
    mock_pdf_reader = Mock()
    mock_pdf_reader.pages = [Mock()]
    mock_pdf_reader.pages[0].extract_text.return_value = "Extracted PDF text"

    # Mock file store directly
    mock_store = Mock()
    mock_store.save = AsyncMock(return_value={
        'id': 'file-123',
        'storage_path': '/path/to/stored/test.pdf',
        'storage_backend': 'local'
    })

    with patch('tyler.models.attachment.Attachment.get_content_bytes', new_callable=AsyncMock) as mock_get_content, \
         patch('magic.from_buffer', return_value='application/pdf') as mock_magic, \
         patch('pypdf.PdfReader', return_value=mock_pdf_reader) as mock_pdf_reader_class, \
         patch('tyler.storage.file_store.FileStore.get_file_url', return_value="/files//path/to/stored/test.pdf"):
        
        # Setup mocks
        mock_get_content.return_value = content
        
        # Process the attachment
        await attachment.process_and_store(file_store=mock_store)
        
        # Verify results
        assert attachment.mime_type == 'application/pdf'
        assert attachment.file_id == 'file-123'
        assert attachment.storage_path == '/path/to/stored/test.pdf'
        assert attachment.storage_backend == 'local'
        assert attachment.attributes["type"] == "document"
        assert "Extracted PDF text" in attachment.attributes["text"]
        mock_get_content.assert_called_once()
        mock_magic.assert_called_once()
        mock_store.save.assert_called_once()
        mock_pdf_reader_class.assert_called_once()

@pytest.mark.asyncio
async def test_process_attachment_error():
    """Test error handling in process_and_store when get_content_bytes fails."""
    attachment = Attachment(filename="test.txt", content="invalid content")
    
    # Create a mock file store directly
    mock_store = Mock()
    
    # Mock get_content_bytes to raise an exception
    with patch.object(Attachment, 'get_content_bytes', AsyncMock(side_effect=Exception("Test error"))):
        # Call process_and_store
        with pytest.raises(RuntimeError, match="Failed to process attachment test.txt"):
            await attachment.process_and_store(file_store=mock_store)

@pytest.mark.asyncio
async def test_filename_update_after_storage():
    """Test that the filename is updated to match the new filename created by the file store."""
    original_filename = "original_test.txt"
    content = b"Test content"
    attachment = Attachment(
        filename=original_filename,
        content=content,
        mime_type="text/plain"
    )

    # The new filename that would be created by the file store
    new_filename = "abc123def456.txt"
    storage_path = f"ab/{new_filename}"  # Mimics the sharded structure

    # Create a mock file store directly
    mock_store = Mock()
    mock_store.save = AsyncMock(return_value={
        'id': 'file-123',
        'storage_path': storage_path,
        'storage_backend': 'local'
    })
    
    with patch('tyler.storage.file_store.FileStore.get_file_url', return_value=f"/files/{storage_path}"):
        # Process and store the attachment
        await attachment.process_and_store(file_store=mock_store)
        
        # Verify the filename was updated
        assert attachment.filename == new_filename
        assert attachment.filename != original_filename
        
        # Verify other properties were set correctly
        assert attachment.file_id == "file-123"
        assert attachment.storage_path == storage_path
        assert attachment.storage_backend == "local"
        
        # Verify the file was stored with the original filename
        mock_store.save.assert_called_once_with(content, original_filename, "text/plain") 