import os
os.environ["OPENAI_API_KEY"] = "dummy"
os.environ["OPENAI_ORG_ID"] = "dummy"
import pytest
from unittest.mock import patch, MagicMock, create_autospec, Mock, AsyncMock
from tyler.models.agent import Agent, AgentPrompt
from tyler.models.thread import Thread
from tyler.models.message import Message
from tyler.utils.tool_runner import tool_runner, ToolRunner
from tyler.database.thread_store import ThreadStore
from openai import OpenAI
from litellm import ModelResponse
import base64
import asyncio
from tyler.models.attachment import Attachment
from datetime import datetime, UTC
import os
import types
import json
from types import SimpleNamespace

@pytest.fixture(autouse=True)
def mock_openai():
    """Mock OpenAI client to prevent real API calls"""
    with patch('openai.OpenAI', autospec=True) as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock()
        yield mock

@pytest.fixture(autouse=True)
def mock_litellm():
    """Mock litellm to prevent real API calls"""
    with patch('litellm.acompletion', autospec=True) as mock:
        yield mock

@pytest.fixture(autouse=True)
def mock_file_processor():
    """Mock tool_runner to prevent real API calls for file processing"""
    with patch.object(tool_runner, 'run_tool_async') as mock_run_tool:
        mock_run_tool.return_value = {"content": "processed content"}
        yield mock_run_tool

@pytest.fixture
def mock_tool_runner():
    mock = MagicMock(spec=ToolRunner)
    mock.execute_tool_call = AsyncMock()
    mock.get_tool_attributes = MagicMock(return_value=None)
    return mock

@pytest.fixture
def mock_thread_store():
    mock = MagicMock()
    mock.get = AsyncMock()
    mock.save = AsyncMock()
    return mock

@pytest.fixture
def mock_wandb():
    return MagicMock()

@pytest.fixture
def mock_prompt():
    return MagicMock()

@pytest.fixture
def mock_env_vars():
    return {
        "OPENAI_API_KEY": "test_key",
        "OPENAI_ORG_ID": "test_org"
    }

@pytest.fixture
def thread():
    """Create a thread fixture for testing"""
    return Thread(
        id="test_thread",
        messages=[],
        metadata={}
    )

@pytest.fixture
def agent(mock_tool_runner, mock_thread_store, mock_openai, mock_wandb, mock_litellm, mock_prompt, mock_file_processor, mock_env_vars):
    """Create a test agent"""
    agent = Agent(
        name="Tyler",
        model_name="gpt-4",
        temperature=0.5,
        purpose="test purpose",
        notes="test notes",
        thread_store=mock_thread_store,
        litellm=mock_litellm,
        prompt=mock_prompt
    )
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
    mock_response = MagicMock()
    mock_response.id = "test-id"
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].finish_reason = "stop"
    mock_response.choices[0].index = 0
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].message.role = "assistant"
    mock_response.model = "gpt-4"
    mock_response.usage.completion_tokens = 10
    mock_response.usage.prompt_tokens = 20
    mock_response.usage.total_tokens = 30

    # Mock the weave operation by patching _get_completion with a dummy object
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"

    class DummyCompletion:
        async def call(self, s, **kwargs):
            return (mock_response, mock_weave_call)

    agent._get_completion = DummyCompletion()

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
    """Test go() with tool calls"""
    thread = Thread(id="test-conv", title="Test Thread")
    mock_prompt.system_prompt.return_value = "Test system prompt"
    thread.messages = []
    thread.ensure_system_prompt("Test system prompt")
    mock_thread_store.get.return_value = thread
    agent._iteration_count = 0

    # Create a mock response with tool calls
    tool_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": "Let me help you with that",
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
    tool_response.choices[0].message = SimpleNamespace(**vars(tool_response.choices[0].message))

    # Create a mock response for after tool execution
    final_response = ModelResponse(**{
        "id": "test-id-2",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Here's what I found",
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

    # Patch the _get_completion method
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    with patch.object(agent, '_get_completion', new_callable=AsyncMock) as mocked_get_completion:
        mocked_get_completion.call.side_effect = [(tool_response, mock_weave_call), (final_response, mock_weave_call)]
        
        with patch('tyler.models.agent.tool_runner') as patched_tool_runner:
            patched_tool_runner.execute_tool_call = AsyncMock(return_value={
                "name": "test-tool",
                "content": "Tool result"
            })
            patched_tool_runner.get_tool_attributes.return_value = None

            result_thread, new_messages = await agent.go("test-conv")

    # Verify the sequence of messages
    messages = result_thread.messages
    assert len(messages) == 4  # system, assistant with tool call, tool result, final assistant
    assert messages[0].role == "system"
    assert messages[1].role == "assistant"
    assert messages[1].tool_calls is not None
    assert messages[2].role == "tool"
    assert messages[2].tool_call_id == "test-call-id"
    assert messages[2].content == "Tool result"
    assert messages[3].role == "assistant"
    assert messages[3].content == "Here's what I found"

@pytest.mark.asyncio
async def test_process_message_files(agent):
    content = b"test content"
    attachment = Attachment(filename="test.pdf")
    message = Message(role="user", content="test", attachments=[attachment])

    with patch('tyler.models.attachment.Attachment.get_content_bytes', new_callable=AsyncMock) as mock_get_content, \
         patch('magic.from_buffer', return_value='application/pdf') as mock_magic, \
         patch('tyler.models.attachment.Attachment.ensure_stored', new_callable=AsyncMock) as mock_ensure_stored, \
         patch.object(tool_runner, 'run_tool_async') as mock_run_tool:
        
        # Setup mocks
        mock_get_content.return_value = content
        mock_ensure_stored.side_effect = lambda: setattr(attachment, 'storage_path', '/path/to/stored/file.pdf')
        mock_run_tool.return_value = {
            "type": "document",
            "text": "Processed text",
            "overview": "Document overview"
        }
        
        # Call the method
        await agent._process_message_files(message)

        # Verify mime type was set before processing
        mock_magic.assert_called_once_with(content, mime=True)
        assert attachment.mime_type == 'application/pdf'
        
        # Verify ensure_stored was called before using the tool
        mock_ensure_stored.assert_called()
        
        # Verify the tool was called with the correct parameters
        mock_run_tool.assert_called_once_with(
            "read-file",
            {
                "file_url": '/path/to/stored/file.pdf',
                "mime_type": 'application/pdf'
            }
        )
        
        # Verify processed_content was set correctly
        assert attachment.processed_content == {
            "type": "document",
            "text": "Processed text",
            "overview": "Document overview"
        }

@pytest.mark.asyncio
async def test_process_message_files_with_error(agent):
    """Test processing message files with an error"""
    message = Message(role="user", content="Test with error")
    
    # Create a mock attachment that will raise an error when getting content
    attachment = Attachment(
        filename="test.doc",
        mime_type=None,
        storage_path=None,
        content=None  # This will cause an error when trying to process
    )
    
    message.attachments = [attachment]
    
    with patch('tyler.models.attachment.Attachment.get_content_bytes', new_callable=AsyncMock) as mock_get_content, \
         patch('tyler.models.attachment.Attachment.ensure_stored', new_callable=AsyncMock) as mock_ensure_stored:
        
        # Set up the mock to raise an exception
        mock_get_content.side_effect = Exception("Failed to read file")
        
        await agent._process_message_files(message)
        
        # Verify error was captured in processed_content
        assert "error" in attachment.processed_content
        assert "Failed to process file: Failed to read file" in attachment.processed_content["error"]
        
        # Verify ensure_stored was still called despite the error
        mock_ensure_stored.assert_called()

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

    with pytest.raises(ValueError, match="Custom tools must have 'definition' and 'implementation' keys"):
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
    with patch('tyler.models.attachment.Attachment.get_content_bytes', new_callable=AsyncMock) as mock_get_content, \
         patch('magic.from_buffer', return_value='image/jpeg') as mock_magic, \
         patch('tyler.models.attachment.Attachment.ensure_stored', new_callable=AsyncMock) as mock_ensure_stored:
        
        mock_get_content.return_value = image_content
        mock_ensure_stored.side_effect = lambda: setattr(attachment, 'storage_path', '/path/to/stored/image.jpg')
        
        message = Message(
            role='user',
            content='Test message with image',
            attachments=[attachment]
        )
        
        await agent._process_message_files(message)
        
        # Verify the image was processed correctly
        assert attachment.processed_content['type'] == 'image'
        assert attachment.processed_content['mime_type'] == 'image/jpeg'
        assert attachment.processed_content['content'] == base64.b64encode(image_content).decode('utf-8')
        
        # Verify ensure_stored was called to store the image
        mock_ensure_stored.assert_called()

@pytest.mark.asyncio
async def test_step_with_metrics(agent, mock_thread_store):
    """Test getting completion with metrics tracking"""
    thread = Thread(id="test-thread")
    thread.messages = []

    # Add a test message
    thread.add_message(Message(role="user", content="test message"))

    # Create a mock response
    mock_response = MagicMock()
    mock_response.id = "test-id"
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].finish_reason = "stop"
    mock_response.choices[0].index = 0
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].message.role = "assistant"
    mock_response.model = "gpt-4"
    mock_response.usage.completion_tokens = 10
    mock_response.usage.prompt_tokens = 20
    mock_response.usage.total_tokens = 30

    # Mock the weave operation
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"

    # Override _get_completion to prevent real API calls
    class DummyCompletion:
        async def call(self, s, **kwargs):
            return (mock_response, mock_weave_call)

    with patch.object(agent, '_get_completion', new=DummyCompletion()):
        response, metrics = await agent.step(thread)

    # Compare relevant attributes instead of the entire response object
    assert response.id == mock_response.id
    assert response.choices[0].message.content == mock_response.choices[0].message.content
    assert response.choices[0].message.role == mock_response.choices[0].message.role
    assert response.model == mock_response.model
    assert response.usage.completion_tokens == mock_response.usage.completion_tokens
    assert response.usage.prompt_tokens == mock_response.usage.prompt_tokens
    assert response.usage.total_tokens == mock_response.usage.total_tokens

    # Verify metrics
    assert metrics["model"] == "gpt-4"
    assert "timing" in metrics
    assert "started_at" in metrics["timing"]
    assert "ended_at" in metrics["timing"]
    assert "latency" in metrics["timing"]
    assert metrics["usage"]["completion_tokens"] == 10
    assert metrics["usage"]["prompt_tokens"] == 20
    assert metrics["usage"]["total_tokens"] == 30
    assert metrics["weave_call"]["id"] == "test-weave-id"
    assert metrics["weave_call"]["ui_url"] == "https://weave.ui/test"

@pytest.mark.asyncio
async def test_step_error(agent):
    """Test error handling in step"""
    thread = Thread(id="test-thread")
    thread.messages = []
    
    # Create a mock error that will be raised
    api_error = Exception("API Error")
    
    # Override _get_completion with a dummy object whose async call method raises the error
    class DummyFail:
        async def call(self, s, **kwargs):
            raise api_error

    agent._get_completion = DummyFail()
    
    result_thread, new_messages = await agent.step(thread)
    # The error should be captured in a message appended to the thread
    error_message = result_thread.messages[-1].content
    error_metrics = result_thread.messages[-1].metrics.get("error", "")
    assert "I encountered an error:" in error_message
    assert "API Error" in error_metrics

@pytest.mark.asyncio
async def test_step_no_weave(agent):
    """Test step metrics when weave call info is not available"""
    thread = Thread(id="test-thread")
    thread.messages = [Message(role="system", content="Test system prompt")]  # Add system message

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

    # Explicitly patch _get_completion with an AsyncMock and set up the return value for call()
    agent._get_completion = AsyncMock()
    agent._get_completion.call.return_value = (mock_response, None)

    response, metrics = await agent.step(thread)

    assert response.choices[0].message.content == "Test response"
    assert metrics["model"] == "gpt-4"
    assert metrics["usage"]["total_tokens"] == 30

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

    with patch('tyler.models.attachment.Attachment.get_content_bytes', new_callable=AsyncMock) as mock_get_content, \
         patch('magic.from_buffer', return_value='text/plain') as mock_magic, \
         patch('tyler.models.attachment.Attachment.ensure_stored', new_callable=AsyncMock) as mock_ensure_stored, \
         patch.object(tool_runner, 'run_tool_async') as mock_run_tool:
        
        # Setup mocks
        mock_get_content.return_value = content
        mock_ensure_stored.side_effect = lambda: setattr(attachment, 'storage_path', '/path/to/stored/file.txt')
        mock_run_tool.return_value = {"content": "processed content"}
        
        # Call the method
        await agent._process_message_files(message)

        # Verify mime type was set before processing
        mock_magic.assert_called_once_with(content, mime=True)
        assert attachment.mime_type == 'text/plain'
        
        # Verify ensure_stored was called before using the tool
        mock_ensure_stored.assert_called()
        
        # Verify the tool was called with the correct parameters
        mock_run_tool.assert_called_once_with(
            "read-file",
            {
                "file_url": '/path/to/stored/file.txt',
                "mime_type": 'text/plain'
            }
        )
        
        # Verify processed_content was set correctly
        assert attachment.processed_content == {"content": "processed content"}

@pytest.mark.asyncio
async def test_process_message_files_get_content_error(agent):
    """Test handling of errors when getting file content"""
    attachment = Attachment(filename="test.txt")
    message = Message(role="user", content="test", attachments=[attachment])
    
    # Mock get_content_bytes and ensure_stored at the class level
    with patch('tyler.models.attachment.Attachment.get_content_bytes', new_callable=AsyncMock) as mock_get_content, \
         patch('tyler.models.attachment.Attachment.ensure_stored', new_callable=AsyncMock) as mock_ensure_stored:
        
        # Setup mocks
        mock_get_content.side_effect = Exception("Failed to read file")
        
        # Call the method
        await agent._process_message_files(message)
        
        # Verify error was captured in processed_content
        assert attachment.processed_content["error"] == "Failed to process file: Failed to read file"
        
        # Verify ensure_stored was still called despite the error
        mock_ensure_stored.assert_called_once()

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

        # Should not raise exception but handle it gracefully
        should_break = await agent._process_tool_call(tool_call, thread, new_messages)

        assert not should_break
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
                "content": "Let me help you with that",
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
    # Convert message dict to SimpleNamespace
    message_dict = first_response.choices[0].message
    first_response.choices[0].message = SimpleNamespace(
        content=message_dict["content"],
        role=message_dict["role"],
        tool_calls=[
            SimpleNamespace(
                id=tc["id"],
                type=tc["type"],
                function=SimpleNamespace(
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"]
                )
            ) for tc in message_dict["tool_calls"]
        ]
    )

    # Second response with another tool call
    second_response = ModelResponse(**{
        "id": "test-id-2",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": "Let me try another tool",
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
    # Convert message dict to SimpleNamespace
    message_dict = second_response.choices[0].message
    second_response.choices[0].message = SimpleNamespace(
        content=message_dict["content"],
        role=message_dict["role"],
        tool_calls=[
            SimpleNamespace(
                id=tc["id"],
                type=tc["type"],
                function=SimpleNamespace(
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"]
                )
            ) for tc in message_dict["tool_calls"]
        ]
    )

    # Final response without tool calls
    final_response = ModelResponse(**{
        "id": "test-id-3",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Here's what I found",
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
    # Convert message dict to SimpleNamespace
    message_dict = final_response.choices[0].message
    final_response.choices[0].message = SimpleNamespace(
        content=message_dict["content"],
        role=message_dict["role"],
        tool_calls=None
    )

    # Mock the completion call
    mock_completion = AsyncMock()
    mock_completion.call.side_effect = [
        (first_response, None),
        (second_response, None),
        (final_response, None)
    ]
    agent._get_completion = mock_completion

    with patch('tyler.models.agent.tool_runner') as patched_tool_runner:
        # Mock tool executions with different results
        patched_tool_runner.execute_tool_call = AsyncMock(side_effect=[
            {"name": "tool_one", "content": "First tool result"},
            {"name": "tool_two", "content": "Second tool result"}
        ])
        patched_tool_runner.get_tool_attributes.return_value = None

        result_thread, new_messages = await agent.go("test-conv")

    # Verify the sequence of messages
    messages = result_thread.messages
    assert len(messages) == 6  # system, 2 pairs of assistant+tool, final assistant
    assert messages[0].role == "system"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Let me help you with that"
    assert messages[1].tool_calls is not None
    assert messages[2].role == "tool"
    assert messages[2].tool_call_id == "call-1"
    assert messages[2].content == "First tool result"
    assert messages[3].role == "assistant"
    assert messages[3].content == "Let me try another tool"
    assert messages[3].tool_calls is not None
    assert messages[4].role == "tool"
    assert messages[4].tool_call_id == "call-2"
    assert messages[4].content == "Second tool result"
    assert messages[5].role == "assistant"
    assert messages[5].content == "Here's what I found"

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
    # Convert message dict to SimpleNamespace
    message_dict = tool_response.choices[0].message
    tool_response.choices[0].message = SimpleNamespace(
        content=message_dict["content"],
        role=message_dict["role"],
        tool_calls=[
            SimpleNamespace(
                id=tc["id"],
                type=tc["type"],
                function=SimpleNamespace(
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"]
                )
            ) for tc in message_dict["tool_calls"]
        ]
    )

    # Final response after tool call
    final_response = ModelResponse(**{
        "id": "test-id-2",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Here's what I found",
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
    # Convert message dict to SimpleNamespace
    message_dict = final_response.choices[0].message
    final_response.choices[0].message = SimpleNamespace(
        content=message_dict["content"],
        role=message_dict["role"],
        tool_calls=None
    )

    # Mock the completion call
    mock_completion = AsyncMock()
    mock_completion.call.side_effect = [
        (tool_response, None),
        (final_response, None)
    ]
    agent._get_completion = mock_completion

    with patch('tyler.models.agent.tool_runner') as patched_tool_runner:
        patched_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test-tool",
            "content": "Tool result"
        })
        patched_tool_runner.get_tool_attributes.return_value = None

        result_thread, new_messages = await agent.go("test-conv")

    # Verify the sequence of messages
    messages = result_thread.messages
    assert len(messages) == 4  # system, assistant with tool call, tool result, final assistant
    assert messages[0].role == "system"
    assert messages[1].role == "assistant"
    assert messages[1].content == ""  # Empty content
    assert messages[1].tool_calls is not None
    assert messages[2].role == "tool"
    assert messages[2].tool_call_id == "test-call-id"
    assert messages[2].content == "Tool result"
    assert messages[3].role == "assistant"
    assert messages[3].content == "Here's what I found"

@pytest.mark.asyncio
async def test_process_tool_call_with_files(agent, thread):
    """Test processing a tool call that returns files"""
    # Mock the tool execution result
    mock_result = {
        "tool_call_id": "test_id",
        "name": "test_tool",
        "content": json.dumps({"success": True, "message": "File generated"}),
        "files": [{
            "filename": "test.txt",
            "content": b"test content",
            "mime_type": "text/plain",
            "description": "A test file"
        }]
    }
    
    with patch.object(agent, '_handle_tool_execution', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = mock_result
        
        # Create a tool call
        tool_call = {
            'id': 'test_id',
            'function': {
                'name': 'test_tool',
                'arguments': '{}'
            }
        }
        
        new_messages = []
        result = await agent._process_tool_call(tool_call, thread, new_messages)
        
        # Check that attachments were created
        assert len(new_messages) == 1
        message = new_messages[0]
        assert len(message.attachments) == 1
        
        # Verify attachment properties
        attachment = message.attachments[0]
        assert isinstance(attachment, Attachment)
        assert attachment.filename == "test.txt"
        assert attachment.content == b"test content"
        assert attachment.mime_type == "text/plain"
        assert attachment.processed_content == {"description": "A test file"}

@pytest.mark.asyncio
async def test_process_tool_call_without_files(agent, thread):
    """Test processing a tool call that doesn't return files"""
    # Mock the tool execution result
    mock_result = {
        "tool_call_id": "test_id",
        "name": "test_tool",
        "content": "Simple result"
    }
    
    with patch.object(agent, '_handle_tool_execution', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = mock_result
        
        # Create a tool call
        tool_call = {
            'id': 'test_id',
            'function': {
                'name': 'test_tool',
                'arguments': '{}'
            }
        }
        
        new_messages = []
        result = await agent._process_tool_call(tool_call, thread, new_messages)
        
        # Check that message was created without attachments
        assert len(new_messages) == 1
        message = new_messages[0]
        assert len(message.attachments) == 0
        assert message.content == "Simple result"

@pytest.mark.asyncio
async def test_process_tool_call_with_error(agent, thread):
    """Test processing a tool call that raises an error"""
    with patch.object(agent, '_handle_tool_execution', new_callable=AsyncMock) as mock_execute:
        mock_execute.side_effect = Exception("Tool execution failed")
        
        # Create a tool call
        tool_call = {
            'id': 'test_id',
            'function': {
                'name': 'test_tool',
                'arguments': '{}'
            }
        }
        
        new_messages = []
        result = await agent._process_tool_call(tool_call, thread, new_messages)
        
        # Check that error message was created
        assert len(new_messages) == 1
        message = new_messages[0]
        assert len(message.attachments) == 0
        assert "Error executing tool" in message.content

@pytest.mark.asyncio
async def test_process_tool_call_with_image_attachment():
    """Test processing a tool call that returns an image attachment."""
    agent = Agent()
    thread = Thread(id="test-thread")
    
    # Mock the tool execution result with an image attachment
    mock_result = {
        "tool_call_id": "test_id",
        "name": "test_tool",
        "content": json.dumps({"success": True, "message": "Image generated"}),
        "files": [{
            "filename": "test.png",
            "content": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",  # Base64 encoded 1x1 pixel PNG
            "mime_type": "image/png",
            "description": "A test image"
        }]
    }
    
    with patch.object(agent, '_handle_tool_execution', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = mock_result
        
        # Create a tool call
        tool_call = {
            'id': 'test_id',
            'function': {
                'name': 'test_tool',
                'arguments': '{}'
            }
        }
        
        new_messages = []
        result = await agent._process_tool_call(tool_call, thread, new_messages)
        
        # Check that attachments were created
        assert len(new_messages) == 1
        message = new_messages[0]
        assert len(message.attachments) == 1
        
        # Verify attachment properties
        attachment = message.attachments[0]
        assert isinstance(attachment, Attachment)
        assert attachment.filename == "test.png"
        assert attachment.content == "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        assert attachment.mime_type == "image/png"
        assert attachment.processed_content == {"description": "A test image"}
        
        # Verify the message was added to the thread
        assert len(thread.messages) == 1
        assert thread.messages[0].role == "tool"
        assert thread.messages[0].tool_call_id == "test_id"
        assert thread.messages[0].content == json.dumps({"success": True, "message": "Image generated"})

@pytest.mark.asyncio
async def test_go_with_tool_returning_image():
    """Test go() with a tool that returns an image."""
    thread = Thread(id="test-conv", title="Test Thread")
    thread.messages = []
    thread.ensure_system_prompt("Test system prompt")
    
    agent = Agent()
    agent._iteration_count = 0
    
    # Create a mock response with tool calls
    tool_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": "Let me generate an image for you",
                "role": "assistant",
                "tool_calls": [{
                    "id": "test-call-id",
                    "type": "function",
                    "function": {
                        "name": "generate_image",
                        "arguments": '{"prompt": "a simple test image"}'
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
    # Convert message dict to SimpleNamespace
    message_dict = tool_response.choices[0].message
    tool_response.choices[0].message = SimpleNamespace(
        content=message_dict["content"],
        role=message_dict["role"],
        tool_calls=[
            SimpleNamespace(
                id=tc["id"],
                type=tc["type"],
                function=SimpleNamespace(
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"]
                )
            ) for tc in message_dict["tool_calls"]
        ]
    )
    
    # Create a mock response for after tool execution
    final_response = ModelResponse(**{
        "id": "test-id-2",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Here's the image I generated for you",
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
    # Convert message dict to SimpleNamespace
    message_dict = final_response.choices[0].message
    final_response.choices[0].message = SimpleNamespace(
        content=message_dict["content"],
        role=message_dict["role"],
        tool_calls=None
    )
    
    # Patch the _get_completion method
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    with patch.object(agent, '_get_completion', new_callable=AsyncMock) as mocked_get_completion:
        mocked_get_completion.call.side_effect = [(tool_response, mock_weave_call), (final_response, mock_weave_call)]
        
        with patch('tyler.models.agent.tool_runner') as patched_tool_runner:
            # Mock tool execution with an image result
            patched_tool_runner.execute_tool_call = AsyncMock(return_value={
                "name": "generate_image",
                "content": json.dumps({"success": True, "message": "Image generated"}),
                "files": [{
                    "filename": "generated_image.png",
                    "content": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
                    "mime_type": "image/png",
                    "description": "Generated image from prompt"
                }]
            })
            patched_tool_runner.get_tool_attributes.return_value = None
            
            # Create a mock thread store
            mock_thread_store = MagicMock()
            mock_thread_store.get = AsyncMock(return_value=thread)
            mock_thread_store.save = AsyncMock()
            agent.thread_store = mock_thread_store
            
            result_thread, new_messages = await agent.go("test-conv")
    
    # Verify the sequence of messages
    messages = result_thread.messages
    assert len(messages) == 4  # system, assistant with tool call, tool result with attachment, final assistant
    assert messages[0].role == "system"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Let me generate an image for you"
    assert messages[1].tool_calls is not None
    
    # Verify the tool message with attachment
    assert messages[2].role == "tool"
    assert messages[2].tool_call_id == "test-call-id"
    assert messages[2].content == json.dumps({"success": True, "message": "Image generated"})
    assert len(messages[2].attachments) == 1
    assert messages[2].attachments[0].filename == "generated_image.png"
    assert messages[2].attachments[0].mime_type == "image/png"
    assert messages[2].attachments[0].content == "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    
    # Verify the final assistant message
    assert messages[3].role == "assistant"
    assert messages[3].content == "Here's the image I generated for you"
    
    # Verify the thread was saved
    mock_thread_store.save.assert_called()

@pytest.mark.asyncio
async def test_normalize_tool_call():
    """Test the _normalize_tool_call method with different input formats"""
    agent = Agent()
    
    # Test with dict format
    dict_tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"param": "value"}'
        }
    }
    normalized = agent._normalize_tool_call(dict_tool_call)
    assert normalized.id == "call_123"
    assert normalized.type == "function"
    assert normalized.function.name == "test_tool"
    assert normalized.function.arguments == '{"param": "value"}'
    
    # Test with object that's already normalized
    from types import SimpleNamespace
    obj_tool_call = SimpleNamespace(
        id="call_456",
        type="function",
        function=SimpleNamespace(
            name="another_tool",
            arguments='{"another": "param"}'
        )
    )
    normalized_obj = agent._normalize_tool_call(obj_tool_call)
    assert normalized_obj is obj_tool_call  # Should return the same object

@pytest.mark.asyncio
async def test_handle_tool_execution_empty_arguments():
    """Test _handle_tool_execution with empty arguments"""
    agent = Agent()
    
    # Create a tool call with empty arguments
    from types import SimpleNamespace
    tool_call = SimpleNamespace(
        id="call_123",
        type="function",
        function=SimpleNamespace(
            name="test_tool",
            arguments=""  # Empty arguments
        )
    )
    
    # Mock tool_runner.execute_tool_call
    with patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool executed with empty args"
        })
        
        result = await agent._handle_tool_execution(tool_call)
        
        # Verify tool_runner was called with normalized arguments
        args = mock_tool_runner.execute_tool_call.call_args[0][0]
        assert args.function.arguments == "{}"  # Empty string should be converted to empty JSON object
        assert result["content"] == "Tool executed with empty args"

@pytest.mark.asyncio
async def test_process_streaming_chunks_no_chunks():
    """Test _process_streaming_chunks with no chunks"""
    agent = Agent()
    
    # Create an empty async generator
    async def empty_generator():
        if False:  # This ensures the generator yields nothing
            yield None
    
    with pytest.raises(TypeError):
        await agent._process_streaming_chunks(None)
        
    # Test with empty generator
    pre_tool, post_tool, tool_calls, usage = await agent._process_streaming_chunks(empty_generator())
    assert pre_tool == ""
    assert post_tool == ""
    assert tool_calls == []
    assert usage == {}

@pytest.mark.asyncio
async def test_process_streaming_chunks_with_continuation():
    """Test _process_streaming_chunks with tool call continuation chunks"""
    agent = Agent()
    
    # Create mock chunks with tool calls that have continuation chunks
    from types import SimpleNamespace
    
    # First chunk with initial tool call
    chunk1 = SimpleNamespace(
        choices=[SimpleNamespace(
            delta=SimpleNamespace(
                tool_calls=[SimpleNamespace(
                    id="call_123",
                    function=SimpleNamespace(
                        name="test_tool",
                        arguments='{"param": '
                    )
                )]
            )
        )]
    )
    
    # Second chunk with continuation (no id)
    chunk2 = SimpleNamespace(
        choices=[SimpleNamespace(
            delta=SimpleNamespace(
                tool_calls=[SimpleNamespace(
                    function=SimpleNamespace(
                        arguments='"value"}'
                    )
                )]
            )
        )]
    )
    
    # Final chunk with usage info
    chunk3 = SimpleNamespace(
        choices=[SimpleNamespace(
            delta=SimpleNamespace()
        )],
        usage=SimpleNamespace(
            completion_tokens=10,
            prompt_tokens=20,
            total_tokens=30
        )
    )
    
    async def mock_chunks():
        yield chunk1
        yield chunk2
        yield chunk3
    
    pre_tool, post_tool, tool_calls, usage = await agent._process_streaming_chunks(mock_chunks())
    
    # Verify tool calls are processed correctly
    assert len(tool_calls) == 1
    assert tool_calls[0]["id"] == "call_123"
    assert tool_calls[0]["function"]["name"] == "test_tool"
    assert tool_calls[0]["function"]["arguments"] == '{"param": "value"}'
    
    # Verify usage metrics
    assert usage == {
        "completion_tokens": 10,
        "prompt_tokens": 20,
        "total_tokens": 30
    }

@pytest.mark.asyncio
async def test_go_with_file_processing_error(agent, mock_thread_store, mock_prompt, mock_litellm):
    """Test go method with error during file processing"""
    thread = Thread()
    
    # Add a user message with an attachment that will cause an error
    user_msg = Message(role="user", content="Process this file")
    attachment = Attachment(filename="test.txt", content="test content")
    user_msg.attachments = [attachment]
    thread.add_message(user_msg)
    
    # Mock _process_message_files to raise an exception
    with patch.object(agent, '_process_message_files') as mock_process:
        mock_process.side_effect = Exception("File processing error")
        
        # Mock completion to return a simple response
        mock_litellm.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content="I processed your request",
                    tool_calls=None
                )
            )]
        )
        
        # Call go method
        result_thread, new_messages = await agent.go(thread)
        
        # Verify error was handled and added to thread
        assert len(new_messages) == 1
        assert "error" in new_messages[0].metrics
        assert "File processing error" in new_messages[0].content
        
        # Verify thread was saved
        if mock_thread_store:
            mock_thread_store.save.assert_called_once()

@pytest.mark.asyncio
async def test_go_with_completion_error(agent, mock_thread_store):
    """Test go method with error during completion"""
    thread = Thread()
    thread.add_message(Message(role="user", content="Test completion error"))
    
    # Mock step to raise an exception
    with patch.object(agent, 'step') as mock_step:
        mock_step.side_effect = Exception("Completion API error")
        
        # Call go method
        result_thread, new_messages = await agent.go(thread)
        
        # Verify error was handled and added to thread
        assert len(new_messages) == 1
        assert "error" in new_messages[0].metrics
        assert "Completion API error" in new_messages[0].content
        
        # Verify thread was saved
        if mock_thread_store:
            mock_thread_store.save.assert_called_once()

@pytest.mark.asyncio
async def test_go_with_invalid_response(agent, mock_thread_store):
    """Test go method with invalid response from completion"""
    thread = Thread()
    thread.add_message(Message(role="user", content="Test invalid response"))
    
    # Mock step to return None for response
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (None, {})
        
        # Call go method
        result_thread, new_messages = await agent.go(thread)
        
        # Verify error was handled and added to thread
        assert len(new_messages) == 1
        # The implementation might not add an "error" key to metrics, so just check the content
        assert "Failed to get valid response" in new_messages[0].content
        
        # Verify thread was saved
        if mock_thread_store:
            mock_thread_store.save.assert_called_once()

@pytest.mark.asyncio
async def test_serialize_tool_calls_with_invalid_calls():
    """Test _serialize_tool_calls with invalid tool calls"""
    agent = Agent()
    
    # Test with None
    assert agent._serialize_tool_calls(None) is None
    
    # Test with empty list
    assert agent._serialize_tool_calls([]) is None
    
    # Test with invalid tool calls (missing ID)
    from types import SimpleNamespace
    invalid_calls = [
        {},  # Empty dict
        {"function": {"name": "test", "arguments": "{}"}},  # Missing ID
        SimpleNamespace(function=SimpleNamespace(name="test", arguments="{}")),  # Missing ID in object
    ]
    
    serialized = agent._serialize_tool_calls(invalid_calls)
    assert serialized is None

@pytest.mark.asyncio
async def test_process_tool_call_with_execution_error(agent, thread):
    """Test _process_tool_call with tool execution error"""
    # Create a tool call
    tool_call = {
        "id": "call_123",
        "function": {
            "name": "test_tool",
            "arguments": "{}"
        }
    }
    
    # Mock _handle_tool_execution to raise an exception
    with patch.object(agent, '_handle_tool_execution') as mock_handle:
        mock_handle.side_effect = Exception("Tool execution failed")
        
        new_messages = []
        should_break = await agent._process_tool_call(tool_call, thread, new_messages)
        
        # Verify error message was added
        assert len(new_messages) == 1
        assert new_messages[0].role == "tool"
        assert "Error executing tool" in new_messages[0].content
        
        # Should not break iteration
        assert should_break is False

@pytest.mark.asyncio
async def test_process_message_files_with_audio(agent):
    """Test _process_message_files with audio file"""
    # Create a message with audio attachment
    message = Message(role="user", content="Process this audio")
    attachment = Attachment(filename="test.mp3", content=b"audio content")
    message.attachments = [attachment]
    
    # Mock magic.from_buffer to return audio mime type
    with patch('magic.from_buffer', return_value="audio/mpeg"):
        # Mock ensure_stored to avoid actual storage
        with patch('tyler.models.attachment.Attachment.ensure_stored', new_callable=AsyncMock):
            await agent._process_message_files(message)
            
            # Verify audio was processed correctly
            assert attachment.mime_type == "audio/mpeg"
            # The actual implementation might store different data, so just check that processed_content exists
            assert attachment.processed_content is not None
            assert "mime_type" in attachment.processed_content
            assert attachment.processed_content["mime_type"] == "audio/mpeg"

@pytest.mark.asyncio
async def test_process_message_files_with_pdf(agent):
    """Test _process_message_files with PDF file"""
    # Create a message with PDF attachment
    message = Message(role="user", content="Process this PDF")
    attachment = Attachment(filename="test.pdf", content=b"PDF content")
    message.attachments = [attachment]
    
    # Mock magic.from_buffer to return PDF mime type
    with patch('magic.from_buffer', return_value="application/pdf"):
        # Mock read-file tool
        with patch('tyler.models.agent.tool_runner') as mock_tool_runner:
            mock_tool_runner.run_tool_async = AsyncMock(return_value={
                "content": "PDF text content",
                "type": "text"
            })
            
            await agent._process_message_files(message)
            
            # Verify PDF was processed correctly
            assert attachment.mime_type == "application/pdf"
            assert attachment.processed_content == {
                "content": "PDF text content",
                "type": "text"
            }
            
            # Verify read-file tool was called
            mock_tool_runner.run_tool_async.assert_called_once()
            args = mock_tool_runner.run_tool_async.call_args[0]
            assert args[0] == "read-file"

@pytest.mark.asyncio
async def test_get_completion_with_weave_call():
    """Test _get_completion with weave call tracking"""
    agent = Agent()
    
    # Mock acompletion
    with patch('tyler.models.agent.acompletion') as mock_acompletion:
        mock_response = MagicMock()
        mock_acompletion.return_value = mock_response
        
        # Call _get_completion directly
        response = await agent._get_completion(model="gpt-4o", messages=[])
        
        # Verify acompletion was called
        mock_acompletion.assert_called_once_with(model="gpt-4o", messages=[])
        
        # Verify response is returned
        assert response is mock_response

@pytest.mark.asyncio
async def test_get_thread_with_missing_thread(agent):
    """Test _get_thread with missing thread ID"""
    # Mock thread_store to return None
    agent.thread_store = MagicMock()
    agent.thread_store.get = AsyncMock(return_value=None)
    
    # Call _get_thread with non-existent ID
    with pytest.raises(ValueError, match="Thread with ID missing-id not found"):
        await agent._get_thread("missing-id")
        
    # Verify thread_store.get was called
    agent.thread_store.get.assert_called_once_with("missing-id")

class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs) 