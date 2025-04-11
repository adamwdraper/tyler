import pytest
from datetime import datetime, UTC, timedelta
from tyler.models.thread import Thread
from tyler.models.message import Message
from tyler.models.attachment import Attachment
from unittest.mock import patch, AsyncMock
import os
from litellm import ModelResponse

@pytest.fixture
def sample_thread():
    """Create a sample thread for testing."""
    thread = Thread(
        id="test-thread",
        title="Test Thread",
        attributes={"category": "test"},
        source={"name": "slack", "channel": "general"}
    )
    # Add messages - they'll get sequence numbers 1 and 2 automatically
    thread.add_message(Message(role="user", content="Hello"))
    thread.add_message(Message(role="assistant", content="Hi there!"))
    return thread

def test_create_thread():
    """Test creating a new thread"""
    thread = Thread(id="test-thread", title="Test Thread")
    assert thread.id == "test-thread"
    assert thread.title == "Test Thread"
    assert isinstance(thread.created_at, datetime)
    assert thread.created_at.tzinfo == UTC
    assert isinstance(thread.updated_at, datetime)
    assert thread.updated_at.tzinfo == UTC
    assert thread.messages == []
    assert thread.attributes == {}
    assert thread.source is None

def test_add_message():
    """Test adding a message to a thread"""
    thread = Thread(id="test-thread")
    message = Message(role="user", content="Hello")
    thread.add_message(message)
    assert len(thread.messages) == 1
    assert thread.messages[0].role == "user"
    assert thread.messages[0].content == "Hello"
    assert thread.messages[0].sequence == 1

def test_thread_serialization(sample_thread):
    """Test thread serialization to/from dict"""
    # Test model_dump() with JSON mode (default)
    data = sample_thread.model_dump(mode="json")
    assert data["id"] == "test-thread"
    assert data["title"] == "Test Thread"
    assert data["attributes"] == {"category": "test"}
    assert data["source"] == {"name": "slack", "channel": "general"}
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"
    assert isinstance(data["created_at"], str)  # Expect ISO-formatted string
    assert isinstance(data["updated_at"], str)  # Expect ISO-formatted string
    
    # Test model_dump() with Python mode
    data_with_dates = sample_thread.model_dump(mode="python")
    assert isinstance(data_with_dates["created_at"], datetime)  # Expect datetime objects
    assert isinstance(data_with_dates["updated_at"], datetime)  # Expect datetime objects
    
    # Test model_validate() with datetime objects
    new_thread = Thread.model_validate(data_with_dates)
    assert new_thread.id == sample_thread.id
    assert new_thread.title == sample_thread.title
    assert new_thread.attributes == sample_thread.attributes
    assert new_thread.source == sample_thread.source
    assert len(new_thread.messages) == len(sample_thread.messages)
    for orig_msg, new_msg in zip(sample_thread.messages, new_thread.messages):
        assert new_msg.role == orig_msg.role
        assert new_msg.content == orig_msg.content
        assert new_msg.sequence == orig_msg.sequence

@pytest.mark.asyncio
async def test_get_messages_for_chat_completion(sample_thread):
    """Test getting messages in chat completion format"""
    messages = sample_thread.get_messages_for_chat_completion()
    assert len(messages) == 2
    assert messages[0] == {
        "role": "user",
        "content": "Hello",
        "sequence": 1
    }
    assert messages[1] == {
        "role": "assistant",
        "content": "Hi there!",
        "sequence": 2
    }

def test_message_sequencing():
    """Test message sequence numbering"""
    thread = Thread(id="test-thread")
    
    # Add messages in different order
    msg1 = Message(role="user", content="First user message")
    msg2 = Message(role="assistant", content="First assistant message")
    msg3 = Message(role="user", content="Second user message")
    msg4 = Message(role="user", content="Third user message")
    
    thread.add_message(msg1)  # Should get sequence 1
    thread.add_message(msg2)  # Should get sequence 2
    thread.add_message(msg3)  # Should get sequence 3
    thread.add_message(msg4)  # Should get sequence 4
    
    # Verify sequences
    assert len(thread.messages) == 4
    assert thread.messages[0].role == "user"
    assert thread.messages[0].sequence == 1
    
    # Get messages in order
    assert thread.messages[0].content == "First user message"
    assert thread.messages[0].sequence == 1
    assert thread.messages[1].content == "First assistant message"
    assert thread.messages[1].sequence == 2
    assert thread.messages[2].content == "Second user message"
    assert thread.messages[2].sequence == 3
    assert thread.messages[3].content == "Third user message"
    assert thread.messages[3].sequence == 4

def test_thread_with_attachments():
    """Test thread with message attachments"""
    thread = Thread(id="test-thread")
    
    # Create message with attachment
    attachment = Attachment(
        filename="test.txt",
        content=b"Test content"
    )
    message = Message(
        role="user",
        content="Message with attachment",
        attachments=[attachment]
    )
    
    thread.add_message(message)
    assert len(thread.messages) == 1
    assert len(thread.messages[0].attachments) == 1
    assert thread.messages[0].attachments[0].filename == "test.txt"
    assert thread.messages[0].attachments[0].content == b"Test content"

def test_thread_with_tool_calls():
    """Test thread with tool call messages"""
    thread = Thread(id="test-thread")
    
    # Add assistant message with tool call
    tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"arg": "value"}'
        }
    }
    
    assistant_msg = Message(
        role="assistant",
        content="Using tool",
        tool_calls=[tool_call]
    )
    thread.add_message(assistant_msg)
    
    # Add tool response
    tool_msg = Message(
        role="tool",
        content="Tool result",
        tool_call_id="call_123",
        name="test_tool"
    )
    thread.add_message(tool_msg)
    
    assert len(thread.messages) == 2
    assert thread.messages[0].tool_calls == [tool_call]
    assert thread.messages[1].tool_call_id == "call_123"
    assert thread.messages[1].name == "test_tool"

def test_thread_usage_stats():
    """Test thread usage statistics"""
    thread = Thread(id="test-thread")
    
    # Add messages with metrics
    msg1 = Message(
        role="assistant",
        content="First response",
        metrics={
            "model": "gpt-4",
            "usage": {
                "completion_tokens": 100,
                "prompt_tokens": 50,
                "total_tokens": 150
            }
        }
    )
    msg2 = Message(
        role="assistant",
        content="Second response",
        metrics={
            "model": "gpt-4",
            "usage": {
                "completion_tokens": 150,
                "prompt_tokens": 75,
                "total_tokens": 225
            }
        }
    )
    
    thread.add_message(msg1)
    thread.add_message(msg2)
    
    # Get usage stats
    usage = thread.get_total_tokens()
    assert usage["overall"]["completion_tokens"] == 250  # 100 + 150
    assert usage["overall"]["prompt_tokens"] == 125  # 50 + 75
    assert usage["overall"]["total_tokens"] == 375  # 150 + 225
    
    # Check model-specific stats
    assert "gpt-4" in usage["by_model"]
    assert usage["by_model"]["gpt-4"]["completion_tokens"] == 250
    assert usage["by_model"]["gpt-4"]["prompt_tokens"] == 125
    assert usage["by_model"]["gpt-4"]["total_tokens"] == 375

def test_thread_timestamps():
    """Test thread timestamp handling"""
    thread = Thread(id="test-thread")
    initial_created = thread.created_at
    initial_updated = thread.updated_at
    
    # Wait a moment and add a message
    import time
    time.sleep(0.1)
    
    thread.add_message(Message(role="user", content="Hello"))
    
    # created_at should not change
    assert thread.created_at == initial_created
    # updated_at should be later
    assert thread.updated_at > initial_updated

def test_thread_validation():
    """Test thread validation"""
    # Test missing required fields
    with pytest.raises(ValueError):
        Thread(id=None)  # id is required
    
    # Test valid minimal thread
    thread = Thread(id="test-thread")
    assert thread.id == "test-thread"
    assert thread.title == "Untitled Thread"  # default title

def test_thread_message_ordering():
    """Test message ordering in thread"""
    thread = Thread(id="test-thread")
    
    # Add messages with explicit timestamps
    base_time = datetime.now(UTC)
    msg1 = Message(role="user", content="First", timestamp=base_time)
    msg2 = Message(role="assistant", content="Second", timestamp=base_time + timedelta(minutes=1))
    msg3 = Message(role="user", content="Third", timestamp=base_time + timedelta(minutes=2))
    
    # Add in random order
    thread.add_message(msg2)
    thread.add_message(msg3)
    thread.add_message(msg1)
    
    # Messages should maintain sequence order
    messages = [m for m in thread.messages if m.role != "system"]
    assert len(messages) == 3
    assert messages[0].sequence == 1
    assert messages[1].sequence == 2
    assert messages[2].sequence == 3 

def test_get_total_tokens():
    """Test getting total token usage across all messages"""
    thread = Thread(id="test-thread")
    
    # Add messages with metrics
    msg1 = Message(
        role="user",
        content="Hello",
        metrics={
            "model": "gpt-4o",
            "usage": {
                "completion_tokens": 10,
                "prompt_tokens": 5,
                "total_tokens": 15
            }
        }
    )
    msg2 = Message(
        role="assistant",
        content="Hi there!",
        metrics={
            "model": "gpt-4o",
            "usage": {
                "completion_tokens": 20,
                "prompt_tokens": 15,
                "total_tokens": 35
            }
        }
    )
    
    thread.add_message(msg1)
    thread.add_message(msg2)
    
    token_usage = thread.get_total_tokens()
    assert token_usage["overall"]["completion_tokens"] == 30
    assert token_usage["overall"]["prompt_tokens"] == 20
    assert token_usage["overall"]["total_tokens"] == 50
    
    assert "gpt-4o" in token_usage["by_model"]
    assert token_usage["by_model"]["gpt-4o"]["completion_tokens"] == 30
    assert token_usage["by_model"]["gpt-4o"]["prompt_tokens"] == 20
    assert token_usage["by_model"]["gpt-4o"]["total_tokens"] == 50

def test_get_model_usage():
    """Test getting model usage statistics"""
    thread = Thread(id="test-thread")
    
    # Add messages with different models
    msg1 = Message(
        role="user",
        content="Hello",
        metrics={
            "model": "gpt-4o",
            "usage": {
                "completion_tokens": 10,
                "prompt_tokens": 5,
                "total_tokens": 15
            }
        }
    )
    msg2 = Message(
        role="assistant",
        content="Hi there!",
        metrics={
            "model": "gpt-3.5-turbo",
            "usage": {
                "completion_tokens": 20,
                "prompt_tokens": 15,
                "total_tokens": 35
            }
        }
    )
    
    thread.add_message(msg1)
    thread.add_message(msg2)
    
    # Test getting all model usage
    all_usage = thread.get_model_usage()
    assert "gpt-4o" in all_usage
    assert "gpt-3.5-turbo" in all_usage
    assert all_usage["gpt-4o"]["calls"] == 1
    assert all_usage["gpt-3.5-turbo"]["calls"] == 1
    
    # Test getting specific model usage
    gpt4_usage = thread.get_model_usage("gpt-4o")
    assert gpt4_usage["calls"] == 1
    assert gpt4_usage["completion_tokens"] == 10
    assert gpt4_usage["prompt_tokens"] == 5
    assert gpt4_usage["total_tokens"] == 15

def test_get_message_timing_stats():
    """Test getting message timing statistics"""
    thread = Thread(id="test-thread")
    
    # Add messages with timing metrics
    msg1 = Message(
        role="user",
        content="Hello",
        metrics={
            "timing": {
                "started_at": "2024-02-07T00:00:00+00:00",
                "ended_at": "2024-02-07T00:00:01+00:00",
                "latency": 1000.0  # 1 second = 1000 milliseconds
            }
        }
    )
    msg2 = Message(
        role="assistant",
        content="Hi there!",
        metrics={
            "timing": {
                "started_at": "2024-02-07T00:00:02+00:00",
                "ended_at": "2024-02-07T00:00:04+00:00",
                "latency": 2000.0  # 2 seconds = 2000 milliseconds
            }
        }
    )
    
    thread.add_message(msg1)
    thread.add_message(msg2)
    
    timing_stats = thread.get_message_timing_stats()
    assert timing_stats["total_latency"] == 3000.0  # 3 seconds = 3000 milliseconds
    assert timing_stats["average_latency"] == 1500.0  # 1.5 seconds = 1500 milliseconds
    assert timing_stats["message_count"] == 2

def test_get_message_counts():
    """Test getting message counts by role"""
    thread = Thread(id="test-thread")
    
    # Add messages with different roles
    thread.add_message(Message(role="user", content="User message 1"))
    thread.add_message(Message(role="user", content="User message 2"))
    thread.add_message(Message(role="assistant", content="Assistant message"))
    thread.add_message(Message(role="tool", content="Tool message", tool_call_id="123"))
    
    counts = thread.get_message_counts()
    assert counts["user"] == 2
    assert counts["assistant"] == 1
    assert counts["tool"] == 1

def test_get_tool_usage():
    """Test getting tool usage statistics"""
    thread = Thread(id="test-thread")
    
    # Add messages with tool calls
    tool_call1 = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"arg": "value"}'
        }
    }
    tool_call2 = {
        "id": "call_456",
        "type": "function",
        "function": {
            "name": "another_tool",
            "arguments": '{"arg": "value"}'
        }
    }
    
    thread.add_message(Message(
        role="assistant",
        content="Using tools",
        tool_calls=[tool_call1, tool_call2]
    ))
    thread.add_message(Message(
        role="assistant",
        content="Using tool again",
        tool_calls=[tool_call1]
    ))
    
    tool_usage = thread.get_tool_usage()
    assert tool_usage["total_calls"] == 3
    assert tool_usage["tools"]["test_tool"] == 2
    assert tool_usage["tools"]["another_tool"] == 1

def test_thread_with_multimodal_messages():
    """Test thread with multimodal messages (text and images)"""
    thread = Thread(id="test-thread")
    
    # Create a message with both text and image content
    image_content = {
        "type": "image_url",
        "image_url": {
            "url": "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
        }
    }
    text_content = {
        "type": "text",
        "text": "Check out this image"
    }
    
    message = Message(
        role="user",
        content=[text_content, image_content]
    )
    
    thread.add_message(message)
    assert len(thread.messages) == 1
    assert isinstance(thread.messages[0].content, list)
    assert len(thread.messages[0].content) == 2
    assert thread.messages[0].content[0]["type"] == "text"
    assert thread.messages[0].content[1]["type"] == "image_url"

def test_thread_with_weave_metrics():
    """Test thread with weave call metrics"""
    thread = Thread(id="test-thread")
    
    message = Message(
        role="assistant",
        content="Hello",
        metrics={
            "model": "gpt-4o",
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
    
    thread.add_message(message)
    assert thread.messages[0].metrics["weave_call"]["id"] == "call-123"
    assert thread.messages[0].metrics["weave_call"]["ui_url"] == "https://weave.ui/call-123" 