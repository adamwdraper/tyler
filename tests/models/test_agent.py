import pytest
from unittest.mock import patch, MagicMock, create_autospec, Mock, AsyncMock
from tyler.models.agent import Agent, AgentPrompt
from tyler.models.thread import Thread
from tyler.models.message import Message
from tyler.utils.tool_runner import tool_runner
from tyler.database.thread_store import ThreadStore
from openai import OpenAI
from litellm import ModelResponse
import base64
from tyler.utils.file_processor import FileProcessor
import asyncio
from tyler.models.attachment import Attachment
from datetime import datetime, UTC
import os

@pytest.fixture
def mock_tool_runner():
    return create_autospec(tool_runner, instance=True)

@pytest.fixture
def mock_thread_store():
    return create_autospec(ThreadStore, instance=True)

@pytest.fixture
def mock_prompt():
    mock = create_autospec(AgentPrompt, instance=True)
    mock.system_prompt.return_value = "Test system prompt"
    return mock

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

class MockFileProcessor(FileProcessor):
    def __init__(self):
        self.supported_types = {
            'application/pdf': self._process_pdf,
        }
        self.client = MagicMock()
        self.process_file = MagicMock(return_value={"content": "processed content"})

@pytest.fixture
def mock_file_processor():
    return MockFileProcessor()

@pytest.fixture
def mock_openai():
    with patch("tyler.utils.file_processor.OpenAI") as mock:
        yield mock

@pytest.fixture
def agent(mock_thread_store, mock_prompt, mock_litellm, mock_file_processor, mock_openai):
    with patch('tyler.models.agent.tool_runner', mock_tool_runner), \
         patch('tyler.models.agent.AgentPrompt', return_value=mock_prompt), \
         patch('tyler.models.agent.FileProcessor', return_value=mock_file_processor), \
         patch('tyler.utils.file_processor.OpenAI'), \
         patch('litellm.acompletion', mock_litellm), \
         patch('tyler.models.agent.acompletion', mock_litellm), \
         patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
        agent = Agent(
            model_name="gpt-4",
            temperature=0.5,
            purpose="test purpose",
            notes="test notes",
            thread_store=mock_thread_store
        )
        agent._iteration_count = 0
        agent._file_processor = mock_file_processor
        agent._prompt = mock_prompt
        
        # Mock the weave operation
        mock_get_completion = AsyncMock()
        mock_get_completion.call = AsyncMock()
        agent._get_completion = mock_get_completion
        return agent

def test_init(agent):
    """Test Agent initialization"""
    assert agent.model_name == "gpt-4"
    assert agent.temperature == 0.5
    assert agent.purpose == "test purpose"
    assert agent.notes == "test notes"
    assert len(agent.tools) == 0
    assert agent.max_tool_iterations == 10
    assert agent._iteration_count == 0

@pytest.mark.asyncio
async def test_go_thread_not_found(agent, mock_thread_store):
    """Test go() with non-existent thread"""
    mock_thread_store.get.return_value = None
    
    with pytest.raises(ValueError, match="Thread with ID test-conv not found"):
        await agent.go("test-conv")

@pytest.mark.asyncio
async def test_go_max_recursion(agent, mock_thread_store):
    """Test go() with maximum iteration count reached"""
    thread = Thread(id="test-conv", title="Test Thread")
    mock_thread_store.get.return_value = thread
    agent._iteration_count = agent.max_tool_iterations
    
    result_thread, new_messages = await agent.go("test-conv")
    
    assert len(new_messages) == 1
    assert new_messages[0].role == "assistant"
    assert new_messages[0].content == "Maximum tool iteration count reached. Stopping further tool calls."
    mock_thread_store.save.assert_called_once_with(result_thread)

@pytest.mark.asyncio
async def test_go_no_tool_calls(agent, mock_thread_store, mock_prompt, mock_litellm):
    """Test go() with a response that doesn't include tool calls"""
    thread = Thread(id="test-conv", title="Test Thread")
    mock_prompt.system_prompt.return_value = "Test system prompt"
    thread.messages = []
    thread.ensure_system_prompt("Test system prompt")
    mock_thread_store.get.return_value = thread
    agent._iteration_count = 0
    
    # Create a mock response
    mock_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Test response",
                "role": "assistant"
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })
    
    # Mock the weave operation
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    agent._get_completion.call.return_value = (mock_response, mock_weave_call)
    
    result_thread, new_messages = await agent.go("test-conv")
    
    assert result_thread.messages[0].role == "system"
    assert result_thread.messages[0].content == "Test system prompt"
    assert result_thread.messages[1].role == "assistant"
    assert result_thread.messages[1].content == "Test response"
    assert len(new_messages) == 1
    assert new_messages[0].role == "assistant"
    assert "metrics" in new_messages[0].model_dump()
    assert "timing" in new_messages[0].metrics
    assert "usage" in new_messages[0].metrics
    mock_thread_store.save.assert_called_with(result_thread)
    assert agent._iteration_count == 0

@pytest.mark.asyncio
async def test_go_with_tool_calls(agent, mock_thread_store, mock_prompt, mock_litellm):
    """Test go() with a response that includes tool calls"""
    thread = Thread(id="test-conv", title="Test Thread")
    mock_prompt.system_prompt.return_value = "Test system prompt"
    thread.messages = []
    thread.ensure_system_prompt("Test system prompt")
    mock_thread_store.get.return_value = thread
    agent._iteration_count = 0
    
    # First response with tool call
    tool_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": "Test response with tool",
                "role": "assistant",
                "tool_calls": [{
                    "id": "test-call-id",
                    "type": "function",
                    "function": {
                        "name": "test-tool",
                        "arguments": '{"arg": "value"}'
                    }
                }]
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })
    
    # Final response without tool calls
    final_response = ModelResponse(**{
        "id": "test-id-2",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Final response",
                "role": "assistant",
                "tool_calls": None
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 5,
            "prompt_tokens": 25,
            "total_tokens": 30
        }
    })
    
    # Mock the weave operation
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    agent._get_completion.call.side_effect = [(tool_response, mock_weave_call), (final_response, mock_weave_call)]
    
    with patch('tyler.models.agent.tool_runner') as patched_tool_runner:
        patched_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test-tool",
            "content": "Tool result"
        })
        
        result_thread, new_messages = await agent.go("test-conv")
    
    messages = result_thread.messages
    assert len(messages) == 4
    assert messages[0].role == "system"
    assert messages[0].content == "Test system prompt"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Test response with tool"
    
    expected_tool_call = {
        "id": "test-call-id",
        "type": "function",
        "function": {
            "name": "test-tool",
            "arguments": '{"arg": "value"}'
        }
    }
    assert messages[1].tool_calls == [expected_tool_call]
    
    assert messages[2].role == "tool"
    assert messages[2].content == "Tool result"
    assert messages[2].name == "test-tool"
    assert messages[2].tool_call_id == "test-call-id"
    assert messages[3].role == "assistant"
    assert messages[3].content == "Final response"
    
    assert len(new_messages) == 3
    assert [m.role for m in new_messages] == ["assistant", "tool", "assistant"]
    
    # Verify metrics are present
    for message in new_messages:
        if message.role in ["assistant", "tool"]:
            assert "metrics" in message.model_dump()
            if message.role == "assistant":
                assert "usage" in message.metrics
                assert "timing" in message.metrics
            if message.role == "tool":
                assert "timing" in message.metrics

@pytest.mark.asyncio
async def test_process_message_files(agent):
    """Test processing message files with attachments"""
    message = Message(role="user", content="Test with attachments")
    
    # Create a mock attachment with the content already set
    attachment = Attachment(
        id="test-attachment",
        filename="test.pdf",
        mime_type=None,
        size=100,
        storage_path="test/path",
        content=b"test content"  # Set the content directly
    )
    
    message.attachments = [attachment]
    
    with patch('magic.from_buffer', return_value='application/pdf'):
        await agent._process_message_files(message)
    
    assert attachment.mime_type == 'application/pdf'
    assert attachment.processed_content == {"content": "processed content"}

@pytest.mark.asyncio
async def test_process_message_files_with_error(agent):
    """Test processing message files with an error"""
    message = Message(role="user", content="Test with error")
    
    # Create a mock attachment that will raise an error when getting content
    attachment = Attachment(
        id="test-attachment",
        filename="test.doc",
        mime_type=None,
        size=100,
        storage_path="test/path",
        content=None  # This will cause an error when trying to process
    )
    
    message.attachments = [attachment]
    
    await agent._process_message_files(message)
    
    assert "Failed to process file" in attachment.processed_content["error"]

@pytest.mark.asyncio
async def test_init_with_tools(mock_thread_store, mock_prompt, mock_litellm, mock_file_processor, mock_openai):
    """Test Agent initialization with both string and dict tools"""
    with patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        # Mock the tool module loading
        mock_tool_runner.load_tool_module.return_value = [
            {"type": "function", "function": {"name": "module_tool", "parameters": {}}}
        ]
        
        # Create a custom tool
        custom_tool = {
            'definition': {
                'function': {
                    'name': 'custom_tool',
                    'parameters': {}
                }
            },
            'implementation': lambda: None,
            'attributes': {'type': 'custom'}
        }
        
        agent = Agent(
            tools=['web', custom_tool],  # Mix of string module and custom tool
            thread_store=mock_thread_store
        )
        
        # Verify tool loading
        mock_tool_runner.load_tool_module.assert_called_once_with('web')
        mock_tool_runner.register_tool.assert_called_once()
        mock_tool_runner.register_tool_attributes.assert_called_once_with('custom_tool', {'type': 'custom'})
        
        # Verify processed tools
        assert len(agent._processed_tools) == 2

@pytest.mark.asyncio
async def test_init_invalid_custom_tool():
    """Test Agent initialization with invalid custom tool"""
    invalid_tool = {
        'implementation': lambda: None  # Missing definition
    }
    
    with pytest.raises(ValueError, match="Custom tools must be dictionaries with 'definition' and 'implementation' keys"):
        Agent(tools=[invalid_tool])

@pytest.mark.asyncio
async def test_process_message_files_image(agent):
    """Test processing message files with an image attachment"""
    # Create a mock image content
    image_content = b'fake_image_data'
    
    # Create a message with an image attachment
    attachment = Attachment(
        filename='test.jpg',
        mime_type='image/jpeg'
    )
    
    # Mock get_content_bytes at the class level
    with patch('tyler.models.attachment.Attachment.get_content_bytes', new_callable=AsyncMock) as mock_get_content:
        mock_get_content.return_value = image_content
        message = Message(
            role='user',
            content='Test message with image',
            attachments=[attachment]
        )
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            await agent._process_message_files(message)
        
        # Verify the image was processed correctly
        assert attachment.processed_content['type'] == 'image'
        assert attachment.processed_content['mime_type'] == 'image/jpeg'
        assert attachment.processed_content['content'] == base64.b64encode(image_content).decode('utf-8')

@pytest.mark.asyncio
async def test_step_with_metrics(agent, mock_thread_store):
    """Test getting completion with metrics tracking"""
    thread = Thread(id="test-thread")
    thread.messages = []
    
    # Add a test message
    thread.add_message(Message(role="user", content="test message"))
    
    # Create a mock response
    mock_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Test response",
                "role": "assistant"
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })
    
    # Mock _get_completion.call to return the response and weave call
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    
    # Set up the mock return value
    agent._get_completion.call.return_value = (mock_response, mock_weave_call)
    
    response, metrics = await agent.step(thread)
    
    assert response == mock_response
    assert metrics['model'] == 'gpt-4'
    assert 'timing' in metrics
    assert metrics['usage'] == {
        'completion_tokens': 10,
        'prompt_tokens': 20,
        'total_tokens': 30
    }
    assert metrics['weave_call']['id'] == "test-weave-id"
    assert metrics['weave_call']['ui_url'] == "https://weave.ui/test"

@pytest.mark.asyncio
async def test_step_error(agent):
    """Test error handling in step"""
    thread = Thread(id="test-thread")
    thread.messages = []
    
    # Create a mock error that will be raised
    api_error = Exception("API Error")
    
    # Set up the mock to raise the error
    agent._get_completion.call.side_effect = api_error
    
    with pytest.raises(Exception) as exc_info:
        await agent.step(thread)
    
    assert str(exc_info.value) == "API Error"

@pytest.mark.asyncio
async def test_step_no_weave(agent):
    """Test step metrics when weave call info is not available"""
    thread = Thread(id="test-thread")
    thread.messages = []
    
    # Create a mock response without weave call info
    mock_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Test response",
                "role": "assistant"
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })
    
    # Set up the mock to return just the response and no weave call
    agent._get_completion.call.return_value = (mock_response, None)
    
    response, metrics = await agent.step(thread)
    
    assert 'weave_call' not in metrics
    assert metrics['model'] == 'gpt-4'
    assert 'timing' in metrics
    assert metrics['usage'] == {
        'completion_tokens': 10,
        'prompt_tokens': 20,
        'total_tokens': 30
    }

@pytest.mark.asyncio
async def test_handle_max_iterations(agent, mock_thread_store):
    """Test handling of max iterations reached"""
    thread = Thread(id="test-thread")
    new_messages = [Message(role="user", content="test")]
    
    result_thread, filtered_messages = await agent._handle_max_iterations(thread, new_messages)
    
    assert len(filtered_messages) == 1
    assert filtered_messages[0].role == "assistant"
    assert filtered_messages[0].content == "Maximum tool iteration count reached. Stopping further tool calls."
    mock_thread_store.save.assert_called_once_with(result_thread)

@pytest.mark.asyncio
async def test_get_thread_direct(agent):
    """Test getting thread directly without thread store"""
    thread = Thread(id="test-thread")
    result = await agent._get_thread(thread)
    assert result == thread

@pytest.mark.asyncio
async def test_get_thread_missing_store(agent):
    """Test getting thread by ID without thread store"""
    agent.thread_store = None
    with pytest.raises(ValueError, match="Thread store is required when passing thread ID"):
        await agent._get_thread("test-thread-id")

@pytest.mark.asyncio
async def test_process_message_files_unsupported_type(agent):
    """Test processing message files with unsupported mime type"""
    content = b"test content"
    attachment = Attachment(filename="test.txt")
    message = Message(role="user", content="test", attachments=[attachment])
    
    with patch('tyler.models.attachment.Attachment.get_content_bytes', new_callable=AsyncMock) as mock_get_content:
        mock_get_content.return_value = content
        with patch('magic.from_buffer', return_value='text/plain'):
            await agent._process_message_files(message)
            
    assert attachment.mime_type == 'text/plain'
    assert attachment.processed_content["content"] == "processed content"

@pytest.mark.asyncio
async def test_process_message_files_get_content_error(agent):
    """Test handling of errors when getting file content"""
    attachment = Attachment(filename="test.txt")
    message = Message(role="user", content="test", attachments=[attachment])
    
    # Mock get_content_bytes at the class level
    with patch('tyler.models.attachment.Attachment.get_content_bytes', new_callable=AsyncMock) as mock_get_content:
        mock_get_content.side_effect = Exception("Failed to read file")
        await agent._process_message_files(message)
        
    assert attachment.processed_content["error"] == "Failed to process file: Failed to read file"

@pytest.mark.asyncio
async def test_tool_execution_error(agent):
    """Test handling of tool execution errors"""
    thread = Thread(id="test-thread")
    new_messages = []
    tool_call = {
        "id": "test-id",
        "type": "function",
        "function": {
            "name": "test-tool",
            "arguments": "{}"
        }
    }

    with patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_tool_runner.execute_tool_call = AsyncMock(side_effect=Exception("Tool error"))
        mock_tool_runner.get_tool_attributes.return_value = None

        # Should return True to indicate processing should stop after error
        should_break = await agent._process_tool_call(tool_call, thread, new_messages)

        assert should_break is True
        assert len(new_messages) == 1
        assert new_messages[0].role == "tool"
        assert new_messages[0].name == "test-tool"
        assert "Error executing tool: Tool error" in new_messages[0].content

@pytest.mark.asyncio
async def test_process_tool_call_with_interrupt(agent):
    """Test processing a tool call that is marked as an interrupt"""
    tool_call = MagicMock()
    tool_call.id = "test-call-id"
    tool_call.function.name = "interrupt_tool"
    tool_call.function.arguments = "{}"
    
    thread = Thread(id="test-thread")
    new_messages = []
    
    with patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        # Mock tool attributes to indicate it's an interrupt tool
        mock_tool_runner.get_tool_attributes.return_value = {'type': 'interrupt'}
        
        # Mock tool execution
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "interrupt_tool",
            "content": "Interrupting execution"
        })
        
        should_break = await agent._process_tool_call(tool_call, thread, new_messages)
        
        assert should_break is True
        assert len(new_messages) == 1
        assert new_messages[0].role == "tool"
        assert new_messages[0].name == "interrupt_tool"
        assert new_messages[0].tool_call_id == "test-call-id"
        assert "metrics" in new_messages[0].model_dump()

@pytest.mark.asyncio
async def test_serialize_tool_calls():
    """Test serialization of tool calls"""
    agent = Agent()
    
    # Create a mock tool call
    tool_call = MagicMock()
    tool_call.id = "test-id"
    tool_call.type = "function"
    tool_call.function.name = "test_function"
    tool_call.function.arguments = '{"arg": "value"}'
    
    serialized = agent._serialize_tool_calls([tool_call])
    
    assert len(serialized) == 1
    assert serialized[0]["id"] == "test-id"
    assert serialized[0]["type"] == "function"
    assert serialized[0]["function"]["name"] == "test_function"
    assert serialized[0]["function"]["arguments"] == '{"arg": "value"}'
    
    # Test with None
    assert agent._serialize_tool_calls(None) is None

@pytest.mark.asyncio
async def test_go_with_weave_metrics(agent, mock_thread_store, mock_prompt):
    """Test go() with weave metrics tracking"""
    thread = Thread(id="test-conv", title="Test Thread")
    thread.messages = []
    thread.ensure_system_prompt("Test system prompt")
    mock_thread_store.get.return_value = thread
    
    # Create a mock weave call with metrics
    mock_weave_call = MagicMock()
    mock_weave_call.id = "weave-call-id"
    mock_weave_call.ui_url = "https://weave.ui/call-id"
    
    # Create the mock response
    mock_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Test response",
                "role": "assistant"
            }
        }],
        "model": "gpt-4",
        "usage": {"completion_tokens": 10, "prompt_tokens": 20, "total_tokens": 30}
    })
    
    # Create a mock for step
    async def mock_step_metrics(*args, **kwargs):
        return mock_response, {
            'model': 'gpt-4',
            'timing': {
                'started_at': '2024-03-20T00:00:00+00:00',
                'ended_at': '2024-03-20T00:00:01+00:00',
                'latency': 1000
            },
            'usage': {
                'completion_tokens': 10,
                'prompt_tokens': 20,
                'total_tokens': 30
            },
            'weave_call': {
                'id': mock_weave_call.id,
                'ui_url': mock_weave_call.ui_url
            }
        }
    
    # Patch the method that actually generates the metrics
    with patch.object(agent, 'step', side_effect=mock_step_metrics):
        result_thread, new_messages = await agent.go(thread)
        
        assert len(new_messages) == 1
        message = new_messages[0]
        assert 'model' in message.metrics
        assert 'timing' in message.metrics
        assert 'usage' in message.metrics
        assert message.metrics['usage'] == {
            'completion_tokens': 10,
            'prompt_tokens': 20,
            'total_tokens': 30
        }
        assert message.metrics['weave_call']['id'] == "weave-call-id"
        assert message.metrics['weave_call']['ui_url'] == "https://weave.ui/call-id"

@pytest.mark.asyncio
async def test_get_thread_no_store():
    """Test get_thread with no thread store"""
    agent = Agent()  # Create without thread store
    thread = Thread(id="test-thread")
    
    # Should work with direct thread object
    result = await agent._get_thread(thread)
    assert result == thread
    
    # Should fail with thread ID
    agent.thread_store = None  # Ensure thread store is None
    with pytest.raises(ValueError) as exc_info:
        await agent._get_thread("test-thread-id")
    assert str(exc_info.value) == "Thread store is required when passing thread ID"

@pytest.mark.asyncio
async def test_go_with_multiple_tool_call_iterations(agent, mock_thread_store, mock_prompt, mock_litellm):
    """Test go() with multiple iterations of tool calls"""
    thread = Thread(id="test-conv", title="Test Thread")
    mock_prompt.system_prompt.return_value = "Test system prompt"
    thread.messages = []
    thread.ensure_system_prompt("Test system prompt")
    mock_thread_store.get.return_value = thread
    agent._iteration_count = 0
    
    # First response with tool call
    first_response = ModelResponse(**{
        "id": "test-id-1",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": "First response with tool",
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "tool_one",
                        "arguments": '{"arg": "first"}'
                    }
                }]
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })
    
    # Second response with another tool call
    second_response = ModelResponse(**{
        "id": "test-id-2",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": "Second response with tool",
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-2",
                    "type": "function",
                    "function": {
                        "name": "tool_two",
                        "arguments": '{"arg": "second"}'
                    }
                }]
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 8,
            "prompt_tokens": 25,
            "total_tokens": 33
        }
    })
    
    # Final response without tool calls
    final_response = ModelResponse(**{
        "id": "test-id-3",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Final response after tools",
                "role": "assistant",
                "tool_calls": None
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 5,
            "prompt_tokens": 30,
            "total_tokens": 35
        }
    })
    
    # Mock the weave operation
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    agent._get_completion.call.side_effect = [
        (first_response, mock_weave_call),
        (second_response, mock_weave_call),
        (final_response, mock_weave_call)
    ]
    
    with patch('tyler.models.agent.tool_runner') as patched_tool_runner:
        # Mock tool executions with different results
        patched_tool_runner.execute_tool_call = AsyncMock(side_effect=[
            {"name": "tool_one", "content": "First tool result"},
            {"name": "tool_two", "content": "Second tool result"}
        ])
        patched_tool_runner.get_tool_attributes.return_value = None
        
        result_thread, new_messages = await agent.go("test-conv")
    
    # Verify the sequence of messages
    assert len(new_messages) == 5  # 3 assistant messages + 2 tool messages
    
    # First assistant message with tool call
    assert new_messages[0].role == "assistant"
    assert new_messages[0].content == "First response with tool"
    assert len(new_messages[0].tool_calls) == 1
    assert new_messages[0].tool_calls[0]["id"] == "call-1"
    
    # First tool response
    assert new_messages[1].role == "tool"
    assert new_messages[1].content == "First tool result"
    assert new_messages[1].name == "tool_one"
    
    # Second assistant message with tool call
    assert new_messages[2].role == "assistant"
    assert new_messages[2].content == "Second response with tool"
    assert len(new_messages[2].tool_calls) == 1
    assert new_messages[2].tool_calls[0]["id"] == "call-2"
    
    # Second tool response
    assert new_messages[3].role == "tool"
    assert new_messages[3].content == "Second tool result"
    assert new_messages[3].name == "tool_two"
    
    # Final assistant message
    assert new_messages[4].role == "assistant"
    assert new_messages[4].content == "Final response after tools"
    assert new_messages[4].tool_calls is None
    
    # Verify that _get_completion was called three times
    assert agent._get_completion.call.call_count == 3

@pytest.mark.asyncio
async def test_go_with_tool_calls_no_content(agent, mock_thread_store, mock_prompt, mock_litellm):
    """Test go() with a response that includes only tool calls (no content)"""
    thread = Thread(id="test-conv", title="Test Thread")
    mock_prompt.system_prompt.return_value = "Test system prompt"
    thread.messages = []
    thread.ensure_system_prompt("Test system prompt")
    mock_thread_store.get.return_value = thread
    agent._iteration_count = 0
    
    # Response with only tool call, no content
    tool_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": None,  # No content
                "role": "assistant",
                "tool_calls": [{
                    "id": "test-call-id",
                    "type": "function",
                    "function": {
                        "name": "test-tool",
                        "arguments": '{"arg": "value"}'
                    }
                }]
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })
    
    # Final response after tool call
    final_response = ModelResponse(**{
        "id": "test-id-2",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Final response",
                "role": "assistant",
                "tool_calls": None
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 5,
            "prompt_tokens": 25,
            "total_tokens": 30
        }
    })
    
    # Mock the weave operation
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    agent._get_completion.call.side_effect = [(tool_response, mock_weave_call), (final_response, mock_weave_call)]
    
    with patch('tyler.models.agent.tool_runner') as patched_tool_runner:
        patched_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test-tool",
            "content": "Tool result"
        })
        
        result_thread, new_messages = await agent.go("test-conv")
    
    # Verify the sequence of messages
    messages = result_thread.messages
    assert len(messages) == 4  # system, assistant with tool call, tool result, final assistant
    
    # First assistant message should have empty content but tool calls
    assistant_msg = messages[1]
    assert assistant_msg.role == "assistant"
    assert assistant_msg.content == ""  # Empty content
    assert assistant_msg.tool_calls is not None
    assert len(assistant_msg.tool_calls) == 1
    assert assistant_msg.tool_calls[0]["id"] == "test-call-id"
    
    # Tool message
    tool_msg = messages[2]
    assert tool_msg.role == "tool"
    assert tool_msg.content == "Tool result"
    assert tool_msg.name == "test-tool"
    assert tool_msg.tool_call_id == "test-call-id"
    
    # Final assistant message
    final_msg = messages[3]
    assert final_msg.role == "assistant"
    assert final_msg.content == "Final response"
    assert final_msg.tool_calls is None

@pytest.mark.asyncio
async def test_go_stops_after_tool_error(agent, mock_thread_store, mock_prompt, mock_litellm):
    """Test that go() stops processing after a tool error and returns an appropriate message"""
    thread = Thread(id="test-conv", title="Test Thread")
    mock_prompt.system_prompt.return_value = "Test system prompt"
    thread.messages = []
    thread.ensure_system_prompt("Test system prompt")
    mock_thread_store.get.return_value = thread
    agent._iteration_count = 0
    
    # First response with tool call
    tool_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": "Let me check that for you",
                "role": "assistant",
                "tool_calls": [{
                    "id": "test-call-id",
                    "type": "function",
                    "function": {
                        "name": "test-tool",
                        "arguments": '{"arg": "value"}'
                    }
                }]
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })
    
    # Final response that should be used after tool error
    final_response = ModelResponse(**{
        "id": "test-id-2",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "I'm currently unable to help with that due to a technical issue. Is there anything else I can assist you with?",
                "role": "assistant",
                "tool_calls": None
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 5,
            "prompt_tokens": 25,
            "total_tokens": 30
        }
    })
    
    # Mock the weave operation
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    agent._get_completion.call.side_effect = [(tool_response, mock_weave_call), (final_response, mock_weave_call)]
    
    with patch('tyler.models.agent.tool_runner') as patched_tool_runner:
        # Mock tool execution to raise an error
        patched_tool_runner.execute_tool_call = AsyncMock(side_effect=Exception("Tool execution failed"))
        patched_tool_runner.get_tool_attributes.return_value = None
        
        result_thread, new_messages = await agent.go("test-conv")
    
    # Verify we only got the initial messages and error handling
    assert len(new_messages) == 3
    assert new_messages[0].role == "assistant"
    assert new_messages[0].content == "Let me check that for you"
    assert new_messages[1].role == "tool"
    assert "Error executing tool" in new_messages[1].content
    assert new_messages[2].role == "assistant"
    assert "I'm currently unable to help with that due to a technical issue" in new_messages[2].content
    
    # Verify that _get_completion was called exactly twice
    assert agent._get_completion.call.call_count == 2
    
    # Verify the thread store was updated
    mock_thread_store.save.assert_called_with(result_thread)

@pytest.mark.asyncio
async def test_process_tool_call_returns_true_on_error(agent):
    """Test that _process_tool_call returns True when a tool errors to stop further processing"""
    thread = Thread(id="test-thread")
    new_messages = []
    tool_call = {
        "id": "test-id",
        "type": "function",
        "function": {
            "name": "test-tool",
            "arguments": "{}"
        }
    }

    with patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_tool_runner.execute_tool_call = AsyncMock(side_effect=Exception("Tool error"))
        mock_tool_runner.get_tool_attributes.return_value = None

        # Should return True to indicate processing should stop
        should_break = await agent._process_tool_call(tool_call, thread, new_messages)

        assert should_break is True
        assert len(new_messages) == 1
        assert new_messages[0].role == "tool"
        assert "Error executing tool" in new_messages[0].content

class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs) 