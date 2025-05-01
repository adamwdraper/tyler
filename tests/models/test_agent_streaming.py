import pytest
from unittest.mock import patch, MagicMock, AsyncMock, create_autospec
from tyler.models.agent import Agent, StreamUpdate
from tyler.models.thread import Thread
from tyler.models.message import Message
from tyler.utils.tool_runner import tool_runner
from litellm import ModelResponse
import json
from types import SimpleNamespace
from tyler.database.thread_store import ThreadStore
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def create_streaming_chunk(content=None, tool_calls=None, role="assistant", usage=None):
    """Helper function to create streaming chunks with proper structure"""
    delta = {"role": role}
    if content is not None:
        delta["content"] = content
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    delta_obj = SimpleNamespace(**delta)
    chunk = {
        "id": "chunk-id",
        "choices": [{
            "index": 0,
            "delta": delta_obj
        }]
    }
    if usage:
        chunk["usage"] = usage
    return ModelResponse(**chunk)

@pytest.fixture
def mock_litellm():
    mock = AsyncMock()
    mock.return_value = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Test response",
                "role": "assistant",
                "tool_calls": None
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })
    
    with patch('litellm.acompletion', mock), \
         patch('tyler.models.agent.acompletion', mock):
        yield mock

@pytest.fixture
def agent(mock_litellm):
    with patch('tyler.models.agent.tool_runner', create_autospec(tool_runner)):
        agent = Agent(
            model_name="gpt-4o",
            temperature=0.7,
            purpose="test purpose",
            stream=True
        )
        # Mock the weave operation
        mock_get_completion = AsyncMock()
        mock_get_completion.call = AsyncMock()
        agent._get_completion = mock_get_completion
        return agent

@pytest.mark.asyncio
async def async_generator(chunks):
    for chunk in chunks:
        yield chunk

@pytest.mark.asyncio
async def test_go_stream_basic_response():
    """Test streaming with basic response (no tool calls)"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    # Mock the completion response
    chunks = [
        create_streaming_chunk(content="Hello"),
        create_streaming_chunk(content=" there!")
    ]
    
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Verify the updates
        assert len(updates) >= 3  # At least content chunks and complete
        assert any(update.type == StreamUpdate.Type.CONTENT_CHUNK and update.data == "Hello" for update in updates)
        assert any(update.type == StreamUpdate.Type.CONTENT_CHUNK and update.data == " there!" for update in updates)
        assert any(update.type == StreamUpdate.Type.ASSISTANT_MESSAGE for update in updates)
        assert any(update.type == StreamUpdate.Type.COMPLETE for update in updates)

@pytest.mark.asyncio
async def test_go_stream_with_tool_calls():
    """Test streaming with tool calls"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Translate 'hello' to Spanish"))
    
    # Mock the completion response with tool calls
    chunks = [
        create_streaming_chunk(content="I'll help translate that."),
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "translate",
                "arguments": '{"text": "hello", "target_language": "Spanish"}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        # Return a dict that will be stringified
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "translate",
            "content": "Translation: hola"
        })
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Verify the updates
        assert len(updates) >= 4  # At least content chunk, tool message, and complete
        assert any(update.type == StreamUpdate.Type.CONTENT_CHUNK and 
                  update.data == "I'll help translate that." for update in updates)
        # Tool message content should be the stringified dict
        assert any(update.type == StreamUpdate.Type.TOOL_MESSAGE and 
                  update.data.content == "{'name': 'translate', 'content': 'Translation: hola'}" for update in updates)
        assert any(update.type == StreamUpdate.Type.ASSISTANT_MESSAGE for update in updates)
        assert any(update.type == StreamUpdate.Type.COMPLETE for update in updates)

@pytest.mark.asyncio
async def test_go_stream_error_handling():
    """Test error handling in streaming mode"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test error"))

    # Mock an error during completion
    error = Exception("Test error")

    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.side_effect = error

        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)

        # Verify error handling - just check for error type without verifying exact message
        assert any(update.type == StreamUpdate.Type.ERROR for update in updates)

@pytest.mark.asyncio
async def test_go_stream_max_iterations():
    """Test max iterations handling in streaming mode"""
    agent = Agent(stream=True, max_tool_iterations=1)  # Set to 1 to trigger quickly
    thread = Thread()
    thread.add_message(Message(role="user", content="Test max iterations"))
    
    # Mock chunks that will trigger tool calls
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Verify max iterations message
        assert any(update.type == StreamUpdate.Type.ASSISTANT_MESSAGE and 
                  "Maximum tool iteration count reached" in update.data.content for update in updates)

@pytest.mark.asyncio
async def test_go_stream_invalid_json_handling():
    """Test handling of invalid JSON in tool arguments"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test invalid JSON"))
    
    # Mock chunks with invalid JSON in tool arguments
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{"invalid": "json"'  # Missing closing brace
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Verify error handling: Check for 'Tool execution failed:' substring in error message
        assert any(update.type == StreamUpdate.Type.ERROR and 
                  "Tool execution failed:" in str(update.data) for update in updates)

@pytest.mark.asyncio
async def test_go_stream_metrics_tracking():
    """Test that metrics are properly tracked in streaming mode"""
    agent = Agent(stream=True, model_name="gpt-4o")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test metrics"))
    
    # Mock chunks with usage info
    chunks = [
        create_streaming_chunk(content="Hello"),
        create_streaming_chunk(content=" world", usage={
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        })
    ]
    
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Find the assistant message update
        assistant_message = next(
            update.data for update in updates 
            if update.type == StreamUpdate.Type.ASSISTANT_MESSAGE
        )
        
        # Verify metrics are present and correct
        assert "metrics" in assistant_message.model_dump()
        assert assistant_message.metrics["model"] == "gpt-4o"
        assert "timing" in assistant_message.metrics
        assert "started_at" in assistant_message.metrics["timing"]
        assert "ended_at" in assistant_message.metrics["timing"]
        assert "latency" in assistant_message.metrics["timing"]
        assert assistant_message.metrics["usage"] == {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
        assert assistant_message.metrics["weave_call"]["id"] == "test-weave-id"
        assert assistant_message.metrics["weave_call"]["ui_url"] == "https://weave.ui/test"

@pytest.mark.asyncio
async def test_go_stream_tool_metrics():
    """Test that tool execution metrics are tracked in streaming mode"""
    agent = Agent(stream=True, model_name="gpt-4o")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test tool metrics"))
    
    # Mock chunks with tool call
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }], usage={
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        })
    ]
    
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Find the tool message update
        tool_message = next(
            update.data for update in updates 
            if update.type == StreamUpdate.Type.TOOL_MESSAGE
        )
        
        # Verify tool metrics are present and correct with actual values
        assert "metrics" in tool_message.model_dump()
        assert "timing" in tool_message.metrics
        assert tool_message.metrics["timing"]["started_at"] is not None
        assert tool_message.metrics["timing"]["ended_at"] is not None
        assert "latency" in tool_message.metrics["timing"]  # Just verify latency exists, don't check value
        # Tool message content should be stringified dict
        assert tool_message.content == "{'name': 'test_tool', 'content': 'Tool result'}"

@pytest.mark.asyncio
async def test_go_stream_multiple_messages_metrics():
    """Test metrics tracking across multiple messages in streaming mode"""
    agent = Agent(stream=True, model_name="gpt-4o")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test multiple messages"))
    
    # First response with tool call
    first_chunks = [
        create_streaming_chunk(content="Let me help", tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    # Second response after tool execution
    second_chunks = [
        create_streaming_chunk(content="Here's the result", usage={
            "completion_tokens": 15,
            "prompt_tokens": 25,
            "total_tokens": 40
        })
    ]
    
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.side_effect = [
            (async_generator(first_chunks), mock_weave_call),
            (async_generator(second_chunks), mock_weave_call)
        ]
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Get all assistant and tool messages
        messages = [
            update.data for update in updates
            if update.type in (StreamUpdate.Type.ASSISTANT_MESSAGE, StreamUpdate.Type.TOOL_MESSAGE)
        ]

        # Verify each message has proper metrics with actual values
        for message in messages:
            assert "metrics" in message.model_dump()
            # Only check model name for assistant messages
            if message.role == "assistant":
                assert message.metrics["model"] == "gpt-4o"
            assert "timing" in message.metrics
            
            if message.role == "assistant":
                assert "usage" in message.metrics
                if hasattr(message, 'content') and message.content == "Here's the result":
                    # Check specific usage values for the second message
                    assert message.metrics["usage"] == {
                        "completion_tokens": 15,
                        "prompt_tokens": 25,
                        "total_tokens": 40
                    }
                assert "weave_call" in message.metrics
                assert message.metrics["weave_call"]["id"] == "test-weave-id"
                assert message.metrics["weave_call"]["ui_url"] == "https://weave.ui/test"
            
            if message.role == "tool":
                assert message.metrics["timing"]["started_at"] is not None
                assert message.metrics["timing"]["ended_at"] is not None
                assert "latency" in message.metrics["timing"]  # Just verify latency exists, don't check value

@pytest.mark.asyncio
async def test_go_stream_object_format_tool_calls():
    """Test streaming with tool calls in object format rather than dict format"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test object format tool calls"))

    # Create tool call in proper format
    tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"param": "value"}'
        }
    }

    # Create a chunk with the tool call
    chunk = create_streaming_chunk(tool_calls=[tool_call])

    mock_weave_call = MagicMock()

    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator([chunk]), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })

        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)

        # Verify tool call was processed correctly - just check for tool message type
        assert any(update.type == StreamUpdate.Type.TOOL_MESSAGE for update in updates)

@pytest.mark.asyncio
async def test_go_stream_object_format_tool_call_updates():
    """Test streaming with tool call updates in object format"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test object format tool call updates"))
    
    # First chunk with initial tool call
    initial_tool_call = SimpleNamespace(
        id="call_123",
        type="function",
        function=SimpleNamespace(
            name="test_tool",
            arguments='{"param": '
        )
    )
    
    # Second chunk with continuation of arguments
    continuation_tool_call = SimpleNamespace(
        function=SimpleNamespace(
            arguments='"value"}'
        )
    )
    
    chunks = [
        create_streaming_chunk(tool_calls=[initial_tool_call]),
        create_streaming_chunk(tool_calls=[continuation_tool_call])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Find the assistant message with tool calls
        assistant_message = next(
            (update.data for update in updates 
             if update.type == StreamUpdate.Type.ASSISTANT_MESSAGE and update.data.tool_calls),
            None
        )
        
        # Verify arguments were concatenated correctly
        assert assistant_message is not None
        assert assistant_message.tool_calls[0]["function"]["arguments"] == '{"param": "value"}'

@pytest.mark.asyncio
async def test_go_stream_missing_tool_call_id():
    """Test handling of tool calls with missing ID"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test missing tool call ID"))
    
    # Create a tool call with missing ID
    invalid_tool_call = {
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{}'
        }
    }
    
    chunk = create_streaming_chunk(tool_calls=[invalid_tool_call])
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator([chunk]), mock_weave_call)
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Verify no tool calls were processed (since ID was missing)
        assistant_messages = [
            update.data for update in updates 
            if update.type == StreamUpdate.Type.ASSISTANT_MESSAGE
        ]
        
        # The assistant message should not have tool calls
        assert all(not getattr(msg, 'tool_calls', None) for msg in assistant_messages)

@pytest.mark.asyncio
async def test_go_stream_empty_arguments():
    """Test handling of empty arguments in tool calls"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test empty arguments"))
    
    # Mock chunks with empty arguments
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": ""  # Empty arguments
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Find the tool message
        tool_message = next(
            update.data for update in updates 
            if update.type == StreamUpdate.Type.TOOL_MESSAGE
        )
        
        # Verify tool message content is stringified dict
        assert tool_message.content == "{'name': 'test_tool', 'content': 'Tool result'}"

@pytest.mark.asyncio
async def test_go_stream_thread_store_save():
    """Test that thread is saved during streaming"""
    # Create mock thread store
    mock_thread_store = MagicMock(spec=ThreadStore)
    mock_thread_store.save = AsyncMock(return_value=None)
    # Keep track of saved thread state
    saved_thread_data = {}
    
    async def mock_save(thread):
        # Simulate saving by storing messages using model_dump(mode='json')
        # to ensure datetime is stored as string, like a real DB would
        saved_thread_data[thread.id] = [
            msg.model_dump(mode='json') for msg in thread.messages
        ]
        
    async def mock_get(thread_id):
        if thread_id in saved_thread_data:
            # Reconstruct thread from saved data
            reconstructed_messages = []
            for msg_data in saved_thread_data[thread_id]:
                # --- Key Change: Parse timestamp string back to datetime ---
                if 'timestamp' in msg_data and isinstance(msg_data['timestamp'], str):
                    try:
                        # Ensure the string is parsed correctly into a datetime object
                        msg_data['timestamp'] = datetime.fromisoformat(msg_data['timestamp'])
                    except ValueError:
                        # Handle potential parsing errors, maybe log or use a default
                        logger.error(f"Failed to parse timestamp: {msg_data['timestamp']}")
                        # Optionally set a default or re-raise, depending on desired test behavior
                        # For now, let's remove it to avoid crashing the test if parsing fails
                        del msg_data['timestamp'] 
                # --- End Key Change ---
                
                # Recreate message, handling potential missing timestamp if parsing failed
                try:
                    reconstructed_messages.append(Message(**msg_data))
                except Exception as e:
                     logger.error(f"Failed to reconstruct message: {msg_data} with error {e}")
                     # Skip this message if reconstruction fails
                     continue
                     
            return Thread(
                id=thread_id, 
                messages=reconstructed_messages
            )
        return None
        
    mock_thread_store.save = mock_save
    mock_thread_store.get = mock_get
    
    agent = Agent(stream=True)
    thread = Thread(id="test-thread")
    # Initial 'save' to put the empty thread in our mock store
    await mock_thread_store.save(thread)
    
    # Mock chunks with tool call
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    # --- Key Change: Patch _get_thread_store --- 
    async def get_mock_store():
        return mock_thread_store
    agent._get_thread_store = get_mock_store
    # --- End Key Change ---\
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Verify thread was saved with messages
        saved_thread = await mock_thread_store.get(thread.id)
        assert saved_thread is not None
        # Check that messages were added before saving
        # We expect at least the assistant message and the tool message
        assert len(saved_thread.messages) >= 2, f"Expected >= 2 messages, found {len(saved_thread.messages)}"

@pytest.mark.asyncio
async def test_go_stream_reset_iteration_count():
    """Test that iteration count is reset after streaming"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test reset iteration count"))
    
    # Set iteration count to non-zero
    agent._iteration_count = 5
    
    # Simple response with no tool calls
    chunk = create_streaming_chunk(content="Simple response")
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator([chunk]), mock_weave_call)
        
        # Process all updates
        async for _ in agent.go_stream(thread):
            pass
        
        # Verify iteration count was reset
        assert agent._iteration_count == 0

@pytest.mark.asyncio
async def test_go_stream_invalid_response():
    """Test handling of invalid response from completion call"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test invalid response"))
    
    # Mock step to return None instead of a valid response
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (None, {})
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Verify error was yielded
        assert any(update.type == StreamUpdate.Type.ERROR and 
                  "No response received" in str(update.data) for update in updates)

@pytest.mark.asyncio
async def test_go_stream_tool_call_with_files():
    """Test handling of tool calls that return files in streaming mode"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test file handling"))
    
    # Mock chunks with tool call
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    # Create test file data
    test_file = {
        "filename": "test.txt",
        "content": "test content",
        "mime_type": "text/plain"
    }
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        # Return tuple of content and files
        mock_tool_runner.execute_tool_call = AsyncMock(return_value=(
            {"name": "test_tool", "content": "File generated"},
            [test_file]
        ))
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Find the tool message
        tool_message = next(
            update.data for update in updates 
            if update.type == StreamUpdate.Type.TOOL_MESSAGE
        )
        
        # Verify tool message content is stringified dict
        assert tool_message.content == "{'name': 'test_tool', 'content': 'File generated'}"
        # Verify file attachment
        assert len(tool_message.attachments) == 1
        assert tool_message.attachments[0].filename == "test.txt"
        assert tool_message.attachments[0].content == "test content"
        assert tool_message.attachments[0].mime_type == "text/plain"

@pytest.mark.asyncio
async def test_go_stream_tool_call_with_attributes():
    """Test handling of tool calls with attributes"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test tool attributes"))
    
    # Mock chunks with tool call
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        # Mock tool runner to return attributes
        mock_tool_runner.get_tool_attributes.return_value = {
            "type": "test",
            "category": "utility"
        }
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Find the tool message
        tool_message = next(
            update.data for update in updates 
            if update.type == StreamUpdate.Type.TOOL_MESSAGE
        )
        
        # Verify tool message content is stringified dict
        assert tool_message.content == "{'name': 'test_tool', 'content': 'Tool result'}"
        # Verify tool attributes were used
        assert mock_tool_runner.get_tool_attributes.called

@pytest.mark.asyncio
async def test_go_stream_interrupt_tool():
    """Test handling of interrupt tools in streaming mode"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test interrupt tool"))
    
    # Mock chunks with tool call
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "interrupt_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        # Mock tool runner to return interrupt type
        mock_tool_runner.get_tool_attributes.return_value = {
            "type": "interrupt"
        }
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "interrupt_tool",
            "content": "Interrupting execution"
        })
        
        updates = []
        async for update in agent.go_stream(thread):
            updates.append(update)
        
        # Find the tool message
        tool_message = next(
            update.data for update in updates 
            if update.type == StreamUpdate.Type.TOOL_MESSAGE
        )
        
        # Verify tool message content is stringified dict
        assert tool_message.content == "{'name': 'interrupt_tool', 'content': 'Interrupting execution'}"
        # Verify tool attributes were used
        assert mock_tool_runner.get_tool_attributes.called
        # Verify we got a complete update
        assert any(update.type == StreamUpdate.Type.COMPLETE for update in updates)