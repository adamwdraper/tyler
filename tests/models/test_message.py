import pytest
from datetime import datetime, UTC
from tyler.models.message import Message, TextContent, ImageContent
from tyler.models.attachment import Attachment
import json
import base64
from unittest.mock import patch, Mock, AsyncMock
import pydantic

@pytest.fixture
def sample_message():
    """Create a sample message for testing."""
    return Message(
        role="user",
        content="Hello, world!",
        name="test_user",
        attributes={"sentiment": "positive"},
        timestamp=datetime.now(UTC),
        metrics={
            "model": "gpt-4o",
            "timing": {
                "started_at": "2024-02-07T00:00:00+00:00",
                "ended_at": "2024-02-07T00:00:01+00:00",
                "latency": 1.0
            },
            "usage": {
                "completion_tokens": 10,
                "prompt_tokens": 5,
                "total_tokens": 15
            },
            "weave_call": {
                "id": "call-123",
                "ui_url": "https://weave.ui/call-123"
            }
        }
    )

def test_message_creation(sample_message):
    """Test basic message creation and properties."""
    assert sample_message.role == "user"
    assert sample_message.content == "Hello, world!"
    assert sample_message.name == "test_user"
    assert sample_message.attributes == {"sentiment": "positive"}
    assert isinstance(sample_message.timestamp, datetime)
    assert sample_message.timestamp.tzinfo == UTC
    assert sample_message.metrics["model"] == "gpt-4o"
    assert sample_message.metrics["weave_call"]["id"] == "call-123"

def test_message_with_multimodal_content():
    """Test message with multimodal content (text and images)."""
    text_content = TextContent(type="text", text="Check out this image")
    image_content = ImageContent(
        type="image_url",
        image_url={"url": "data:image/jpeg;base64,/9j/4AAQSkZJRg=="}
    )
    
    message = Message(
        role="user",
        content=[text_content, image_content]
    )
    
    assert isinstance(message.content, list)
    assert len(message.content) == 2
    assert message.content[0]["type"] == "text"
    assert message.content[0]["text"] == "Check out this image"
    assert message.content[1]["type"] == "image_url"
    assert message.content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")

def test_message_serialization(sample_message):
    """Test message serialization to/from dict"""
    # Add some tool calls and attachments for comprehensive testing
    sample_message.tool_calls = [{
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"arg": "value"}'
        }
    }]
    
    attachment = Attachment(
        filename="test.txt",
        content=b"Test content",
        mime_type="text/plain",
        processed_content={
            "type": "text",
            "text": "Test content",
            "overview": "A test file"
        }
    )
    sample_message.attachments = [attachment]
    
    # Test model_dump()
    data = sample_message.model_dump()
    assert data["role"] == "user"
    assert data["content"] == "Hello, world!"
    assert data["name"] == "test_user"
    assert data["attributes"] == {"sentiment": "positive"}
    assert isinstance(data["timestamp"], str)  # Should be ISO format string
    assert data["tool_calls"] == sample_message.tool_calls
    assert len(data["attachments"]) == 1
    assert data["attachments"][0]["filename"] == "test.txt"
    assert data["attachments"][0]["mime_type"] == "text/plain"
    assert data["attachments"][0]["processed_content"]["type"] == "text"
    
    # Test metrics serialization
    assert data["metrics"]["model"] == "gpt-4o"
    assert data["metrics"]["weave_call"]["id"] == "call-123"
    assert data["metrics"]["timing"]["latency"] == 1.0
    assert data["metrics"]["usage"]["total_tokens"] == 15
    
    # Convert timestamp back to datetime for validation
    data["timestamp"] = datetime.fromisoformat(data["timestamp"])
    
    # Test model_validate()
    new_message = Message.model_validate(data)
    assert new_message.role == sample_message.role
    assert new_message.content == sample_message.content
    assert new_message.name == sample_message.name
    assert new_message.attributes == sample_message.attributes
    assert new_message.tool_calls == sample_message.tool_calls
    assert len(new_message.attachments) == 1
    assert new_message.attachments[0].filename == "test.txt"
    assert new_message.metrics["weave_call"]["id"] == "call-123"

def test_to_chat_completion_message():
    """Test conversion to chat completion format"""
    # Test with text-only content
    message = Message(
        role="user",
        content="Hello",
        sequence=1
    )
    chat_msg = message.to_chat_completion_message()
    assert chat_msg["role"] == "user"
    assert chat_msg["content"] == "Hello"
    assert chat_msg["sequence"] == 1

    # Test with multimodal content
    multimodal_message = Message(
        role="user",
        content="Check out this image",
        sequence=2,
        attachments=[
            Attachment(
                filename="test.jpg",
                content=b"image data",
                mime_type="image/jpeg",
                processed_content={
                    "type": "image",
                    "content": "base64_encoded_image",
                    "overview": "An image file"
                }
            )
        ]
    )

    chat_msg = multimodal_message.to_chat_completion_message()
    assert chat_msg["role"] == "user"
    assert isinstance(chat_msg["content"], list)
    assert len(chat_msg["content"]) == 2
    assert chat_msg["content"][0]["type"] == "text"
    assert chat_msg["content"][0]["text"] == "Check out this image"
    assert chat_msg["content"][1]["type"] == "image_url"
    assert "data:image/jpeg;base64," in chat_msg["content"][1]["image_url"]["url"]

def test_message_with_attachments():
    """Test message with attachments"""
    # Test with text file
    text_attachment = Attachment(
        filename="test.txt",
        content=b"Test content",
        mime_type="text/plain",
        processed_content={
            "type": "text",
            "text": "Test content",
            "overview": "A test file"
        }
    )

    # Test with image file
    image_attachment = Attachment(
        filename="test.jpg",
        content=b"image data",
        mime_type="image/jpeg",
        processed_content={
            "type": "image",
            "content": "base64_encoded_image",
            "overview": "An image file"
        }
    )

    # Test user message with mixed attachments - when there's an image, text content should be separate
    user_message = Message(
        role="user",
        content="Here are some files",
        attachments=[text_attachment, image_attachment]
    )

    # Test chat completion format with user attachments
    chat_msg = user_message.to_chat_completion_message()
    assert isinstance(chat_msg["content"], list)
    assert len(chat_msg["content"]) == 3  # Text + text file + image
    assert chat_msg["content"][0]["type"] == "text"
    assert chat_msg["content"][0]["text"] == "Here are some files"
    assert chat_msg["content"][1]["type"] == "text"
    assert "--- File: test.txt ---" in chat_msg["content"][1]["text"]
    assert "Test content" in chat_msg["content"][1]["text"]
    assert chat_msg["content"][2]["type"] == "image_url"
    assert "data:image/jpeg;base64," in chat_msg["content"][2]["image_url"]["url"]

    # Test user message with only text attachments
    user_text_only = Message(
        role="user",
        content="Here's a text file",
        attachments=[text_attachment]
    )
    chat_msg = user_text_only.to_chat_completion_message()
    assert isinstance(chat_msg["content"], str)
    assert "Here's a text file" in chat_msg["content"]
    assert "--- File: test.txt ---" in chat_msg["content"]
    assert "Test content" in chat_msg["content"]
    assert "A test file" in chat_msg["content"]

    # Test assistant message with attachments
    assistant_message = Message(
        role="assistant",
        content="I generated some files for you",
        attachments=[text_attachment, image_attachment]
    )
    chat_msg = assistant_message.to_chat_completion_message()
    assert isinstance(chat_msg["content"], str)
    assert "I generated some files for you" in chat_msg["content"]
    assert "Generated Files:" in chat_msg["content"]
    assert "- test.txt (text/plain)" in chat_msg["content"]
    assert "- test.jpg (image/jpeg)" in chat_msg["content"]
    # Verify that file contents are NOT included
    assert "Test content" not in chat_msg["content"]
    assert "base64_encoded_image" not in chat_msg["content"]

    # Test tool message with attachments - should not modify content
    tool_message = Message(
        role="tool",
        content="Tool result",
        tool_call_id="call_123",
        attachments=[text_attachment]
    )
    chat_msg = tool_message.to_chat_completion_message()
    assert chat_msg["content"] == "Tool result"
    assert "test.txt" not in chat_msg["content"]
    assert "Test content" not in chat_msg["content"]

def test_message_with_error_attachments():
    """Test handling of attachments with errors in their processed content"""
    error_attachment = Attachment(
        filename="error.txt",
        content=b"Error content",
        mime_type="text/plain",
        processed_content={
            "type": "text",
            "error": "Failed to process file"
        }
    )

    # Test user message with error attachment
    user_message = Message(
        role="user",
        content="Here's a problematic file",
        attachments=[error_attachment]
    )
    chat_msg = user_message.to_chat_completion_message()
    assert isinstance(chat_msg["content"], str)
    assert "Here's a problematic file" in chat_msg["content"]
    assert "--- File: error.txt ---" in chat_msg["content"]
    assert "Failed to process file" in chat_msg["content"]

    # Test assistant message with error attachment
    assistant_message = Message(
        role="assistant",
        content="I tried to generate a file",
        attachments=[error_attachment]
    )
    chat_msg = assistant_message.to_chat_completion_message()
    assert isinstance(chat_msg["content"], str)
    assert "I tried to generate a file" in chat_msg["content"]
    assert "Generated Files:" in chat_msg["content"]
    assert "- error.txt (text/plain)" in chat_msg["content"]
    # Verify error is not included
    assert "Failed to process file" not in chat_msg["content"]

def test_message_with_multiple_image_attachments():
    """Test handling of multiple image attachments in user messages"""
    image1 = Attachment(
        filename="image1.jpg",
        content=b"image1 data",
        mime_type="image/jpeg",
        processed_content={
            "type": "image",
            "content": "base64_encoded_image1",
            "overview": "First image"
        }
    )
    image2 = Attachment(
        filename="image2.png",
        content=b"image2 data",
        mime_type="image/png",
        processed_content={
            "type": "image",
            "content": "base64_encoded_image2",
            "overview": "Second image"
        }
    )

    # Test user message with multiple images
    user_message = Message(
        role="user",
        content="Here are multiple images",
        attachments=[image1, image2]
    )
    chat_msg = user_message.to_chat_completion_message()
    assert isinstance(chat_msg["content"], list)
    assert len(chat_msg["content"]) == 3  # Text + 2 images
    assert chat_msg["content"][0]["type"] == "text"
    assert chat_msg["content"][0]["text"] == "Here are multiple images"
    assert chat_msg["content"][1]["type"] == "image_url"
    assert "data:image/jpeg;base64," in chat_msg["content"][1]["image_url"]["url"]
    assert chat_msg["content"][2]["type"] == "image_url"
    assert "data:image/png;base64," in chat_msg["content"][2]["image_url"]["url"]

def test_message_with_mixed_content_types():
    """Test handling of messages with both image and non-image attachments"""
    image = Attachment(
        filename="image.jpg",
        content=b"image data",
        mime_type="image/jpeg",
        processed_content={
            "type": "image",
            "content": "base64_encoded_image",
            "overview": "An image"
        }
    )
    text = Attachment(
        filename="doc.txt",
        content=b"text data",
        mime_type="text/plain",
        processed_content={
            "type": "text",
            "text": "Document content",
            "overview": "A document"
        }
    )

    # Test user message with mixed content
    user_message = Message(
        role="user",
        content="Here's an image and a document",
        attachments=[image, text]
    )
    chat_msg = user_message.to_chat_completion_message()
    assert isinstance(chat_msg["content"], list)
    assert len(chat_msg["content"]) == 3  # Base text + text file + image
    assert chat_msg["content"][0]["type"] == "text"
    assert chat_msg["content"][0]["text"] == "Here's an image and a document"
    assert chat_msg["content"][1]["type"] == "text"
    assert "--- File: doc.txt ---" in chat_msg["content"][1]["text"]
    assert "Document content" in chat_msg["content"][1]["text"]
    assert chat_msg["content"][2]["type"] == "image_url"  # Image in multimodal format

def test_message_validation():
    """Test message validation"""
    # Test missing required fields
    with pytest.raises(pydantic.ValidationError) as exc_info:
        Message(content="test")
    assert "role" in str(exc_info.value)

    # Test invalid role
    with pytest.raises(pydantic.ValidationError) as exc_info:
        Message(role="invalid", content="test")
    assert "role" in str(exc_info.value)

    # Test valid minimal message
    message = Message(role="user", content="test")
    assert message.role == "user"
    assert message.content == "test"

    # Test tool message validation - should raise error when tool_call_id is missing
    with pytest.raises(pydantic.ValidationError) as exc_info:
        Message(role="tool", content="test")
    assert "tool_call_id is required for tool messages" in str(exc_info.value)

    # Test valid tool message
    message = Message(role="tool", content="test", tool_call_id="call_123")
    assert message.role == "tool"
    assert message.tool_call_id == "call_123"

def test_message_with_tool_calls():
    """Test message with tool calls"""
    tool_calls = [{
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"arg": "value"}'
        }
    }]

    message = Message(
        role="assistant",
        content="Using tool",
        tool_calls=tool_calls
    )

    assert message.tool_calls == tool_calls

    # Test invalid tool call format
    with pytest.raises(pydantic.ValidationError) as exc_info:
        Message(
            role="assistant",
            content="Using tool",
            tool_calls=[{"invalid": "format"}]
        )
    assert "tool_calls" in str(exc_info.value)

def test_message_with_source():
    """Test message with source information"""
    source = {
        "type": "slack",
        "channel": "general",
        "user": "U123456"
    }
    
    message = Message(
        role="user",
        content="From Slack",
        source=source
    )
    
    assert message.source == source
    assert message.source["type"] == "slack"
    assert message.source["channel"] == "general"

def test_message_with_metrics():
    """Test message with metrics"""
    metrics = {
        "model": "gpt-4",
        "timing": {
            "started_at": "2024-02-10T12:00:00Z",
            "ended_at": "2024-02-10T12:00:01Z",
            "latency": 1.0
        },
        "usage": {
            "completion_tokens": 100,
            "prompt_tokens": 50,
            "total_tokens": 150
        }
    }
    
    message = Message(
        role="assistant",
        content="With metrics",
        metrics=metrics
    )
    
    assert message.metrics["model"] == "gpt-4"
    assert message.metrics["timing"]["latency"] == 1.0
    assert message.metrics["usage"]["total_tokens"] == 150

def test_message_sequence_handling():
    """Test message sequence handling"""
    message = Message(
        role="user",
        content="Test sequence",
        sequence=5
    )
    
    assert message.sequence == 5
    
    # Test default sequence
    default_message = Message(role="user", content="No sequence")
    assert default_message.sequence is None

def test_message_to_chat_completion():
    """Test converting message to chat completion format"""
    message = Message(
        role="user",
        content="Test message",
        name="test_user"
    )
    
    chat_msg = message.to_chat_completion_message()
    assert chat_msg["role"] == "user"
    assert chat_msg["content"] == "Test message"
    assert chat_msg["sequence"] is None

def test_message_default_metrics():
    """Test default metrics structure when creating a new message"""
    message = Message(role="user", content="Test")
    
    # Check default metrics structure
    assert message.metrics["model"] is None
    assert message.metrics["timing"]["started_at"] is None
    assert message.metrics["timing"]["ended_at"] is None
    assert message.metrics["timing"]["latency"] == 0
    assert message.metrics["usage"]["completion_tokens"] == 0
    assert message.metrics["usage"]["prompt_tokens"] == 0
    assert message.metrics["usage"]["total_tokens"] == 0
    assert message.metrics["weave_call"]["id"] == ""
    assert message.metrics["weave_call"]["ui_url"] == ""

def test_message_custom_metrics():
    """Test setting custom metrics values"""
    custom_metrics = {
        "model": "gpt-4o",
        "timing": {
            "started_at": "2024-02-10T12:00:00Z",
            "ended_at": "2024-02-10T12:00:01Z",
            "latency": 1000.0
        },
        "usage": {
            "completion_tokens": 150,
            "prompt_tokens": 50,
            "total_tokens": 200
        },
        "weave_call": {
            "id": "call-123",
            "ui_url": "https://weave.ui/call-123"
        }
    }
    
    message = Message(
        role="assistant",
        content="Response with metrics",
        metrics=custom_metrics
    )
    
    # Verify all metrics values
    assert message.metrics["model"] == "gpt-4o"
    assert message.metrics["timing"]["started_at"] == "2024-02-10T12:00:00Z"
    assert message.metrics["timing"]["ended_at"] == "2024-02-10T12:00:01Z"
    assert message.metrics["timing"]["latency"] == 1000.0
    assert message.metrics["usage"]["completion_tokens"] == 150
    assert message.metrics["usage"]["prompt_tokens"] == 50
    assert message.metrics["usage"]["total_tokens"] == 200
    assert message.metrics["weave_call"]["id"] == "call-123"
    assert message.metrics["weave_call"]["ui_url"] == "https://weave.ui/call-123"

def test_message_metrics_serialization():
    """Test that metrics are properly serialized and deserialized"""
    original_metrics = {
        "model": "gpt-4o",
        "timing": {
            "started_at": "2024-02-10T12:00:00+00:00",
            "ended_at": "2024-02-10T12:00:01+00:00",
            "latency": 1000.0
        },
        "usage": {
            "completion_tokens": 150,
            "prompt_tokens": 50,
            "total_tokens": 200
        },
        "weave_call": {
            "id": "call-123",
            "ui_url": "https://weave.ui/call-123"
        }
    }
    
    message = Message(
        role="assistant",
        content="Test metrics serialization",
        metrics=original_metrics,
        timestamp=datetime.now(UTC)  # Explicitly set timestamp with timezone
    )
    
    # Test serialization
    serialized = message.model_dump()
    
    # Convert timestamp back to datetime for validation
    serialized["timestamp"] = datetime.fromisoformat(serialized["timestamp"])
    
    # Test deserialization
    new_message = Message.model_validate(serialized)
    
    # Compare metrics
    assert new_message.metrics["model"] == original_metrics["model"]
    assert new_message.metrics["timing"] == original_metrics["timing"]
    assert new_message.metrics["usage"] == original_metrics["usage"]
    assert new_message.metrics["weave_call"] == original_metrics["weave_call"]

def test_message_partial_metrics():
    """Test handling of partial metrics data"""
    partial_metrics = {
        "model": "gpt-4o",
        "timing": {
            "latency": 1000.0  # Only providing latency
        },
        "usage": {
            "total_tokens": 200  # Only providing total tokens
        }
    }
    
    message = Message(
        role="assistant",
        content="Partial metrics",
        metrics=partial_metrics
    )
    
    # Verify only the provided values are set
    assert message.metrics["model"] == "gpt-4o"
    assert message.metrics["timing"]["latency"] == 1000.0
    assert message.metrics["usage"]["total_tokens"] == 200
    
    # Verify the structure matches exactly what was provided
    assert set(message.metrics.keys()) == {"model", "timing", "usage"}
    assert set(message.metrics["timing"].keys()) == {"latency"}
    assert set(message.metrics["usage"].keys()) == {"total_tokens"}

def test_message_metrics_in_chat_completion():
    """Test that metrics are properly handled when converting to chat completion format"""
    metrics = {
        "model": "gpt-4o",
        "timing": {
            "started_at": "2024-02-10T12:00:00Z",
            "ended_at": "2024-02-10T12:00:01Z",
            "latency": 1000.0
        },
        "usage": {
            "completion_tokens": 150,
            "prompt_tokens": 50,
            "total_tokens": 200
        },
        "weave_call": {
            "id": "call-123",
            "ui_url": "https://weave.ui/call-123"
        }
    }
    
    message = Message(
        role="assistant",
        content="Test metrics in chat completion",
        metrics=metrics
    )
    
    # Metrics should not appear in chat completion format
    chat_msg = message.to_chat_completion_message()
    assert "metrics" not in chat_msg 

def test_add_attachment():
    """Test adding attachments using add_attachment method"""
    message = Message(role="user", content="Test message")
    
    # Test adding attachment from bytes
    message.add_attachment(b"Test content", "test.txt")
    assert len(message.attachments) == 1
    assert message.attachments[0].filename == "test.txt"
    assert message.attachments[0].content == b"Test content"
    
    # Test adding pre-created attachment
    attachment = Attachment(
        filename="test2.txt",
        content=b"More content",
        mime_type="text/plain"
    )
    message.add_attachment(attachment)
    assert len(message.attachments) == 2
    assert message.attachments[1].filename == "test2.txt"
    
    # Test adding bytes without filename
    with pytest.raises(ValueError) as exc_info:
        message.add_attachment(b"Test content")
    assert "filename is required when adding raw bytes" in str(exc_info.value)
    
    # Test adding invalid type
    with pytest.raises(ValueError) as exc_info:
        message.add_attachment("not bytes or attachment")
    assert "attachment must be either Attachment object or bytes" in str(exc_info.value)

def test_message_metrics_in_chat_completion():
    """Test that metrics are properly handled when converting to chat completion format"""
    metrics = {
        "model": "gpt-4o",
        "timing": {
            "started_at": "2024-02-10T12:00:00Z",
            "ended_at": "2024-02-10T12:00:01Z",
            "latency": 1000.0
        },
        "usage": {
            "completion_tokens": 150,
            "prompt_tokens": 50,
            "total_tokens": 200
        },
        "weave_call": {
            "id": "call-123",
            "ui_url": "https://weave.ui/call-123"
        }
    }
    
    message = Message(
        role="assistant",
        content="Test metrics in chat completion",
        metrics=metrics
    )
    
    # Metrics should not appear in chat completion format
    chat_msg = message.to_chat_completion_message()
    assert "metrics" not in chat_msg 