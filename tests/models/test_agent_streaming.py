import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from tyler.models.agent import Agent
from tyler.models.thread import Thread
from tyler.models.message import Message


# Fake classes to simulate streaming responses
class FakeUsage:
    def __init__(self, completion_tokens, prompt_tokens, total_tokens):
        self.completion_tokens = completion_tokens
        self.prompt_tokens = prompt_tokens
        self.total_tokens = total_tokens

class FakeDelta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

class FakeChoice:
    def __init__(self, delta, finish_reason):
        self.delta = delta
        self.finish_reason = finish_reason

class FakeChunk:
    def __init__(self, choices, usage=None):
        self.choices = choices
        self.usage = usage

# Fake streaming generator for no tool calls case
async def fake_streaming_no_tool_calls():
    # First chunk with partial content
    yield FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Hello, "), finish_reason="")])
    # Second chunk completes the message, with usage info
    yield FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="world!"), finish_reason="stop")], 
                    usage=FakeUsage(completion_tokens=10, prompt_tokens=20, total_tokens=30))

# Fake streaming generator for tool calls case
async def fake_streaming_with_tool_calls():
    # First chunk with some content
    yield FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Output before tool call. "), finish_reason="")])
    # Second chunk with tool call info and usage
    tool_call = {
        "id": "tool_call_1",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"arg": "value"}'
        }
    }
    yield FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="", tool_calls=[tool_call]), finish_reason="tool_calls")], 
                    usage=FakeUsage(completion_tokens=5, prompt_tokens=15, total_tokens=20))

# Fake streaming generator for tool calls with continuation
async def fake_streaming_with_tool_calls_and_continuation():
    # First chunk with some content
    yield FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="First response. "), finish_reason="")])
    # Second chunk with tool call
    tool_call = {
        "id": "tool_call_1",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"arg": "value"}'
        }
    }
    yield FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="", tool_calls=[tool_call]), finish_reason="tool_calls")], 
                    usage=FakeUsage(completion_tokens=5, prompt_tokens=15, total_tokens=20))

# Fake streaming generator for the continuation after tool call
async def fake_streaming_continuation():
    # Response after tool execution
    yield FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Continuing after tool call. "), finish_reason="stop")],
                    usage=FakeUsage(completion_tokens=8, prompt_tokens=25, total_tokens=33))

# Fake streaming generator for tool calls with no content
async def fake_streaming_tool_calls_no_content():
    # Only tool call info, no content
    tool_call = {
        "id": "tool_call_1",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"arg": "value"}'
        }
    }
    yield FakeChunk(choices=[FakeChoice(delta=FakeDelta(content=None, tool_calls=[tool_call]), finish_reason="tool_calls")], 
                    usage=FakeUsage(completion_tokens=5, prompt_tokens=15, total_tokens=20))

# Dummy object to simulate the weave call info
class DummyCall:
    id = "dummy-id"
    ui_url = "http://dummy-url"

@pytest.fixture
def dummy_thread():
    # Create a dummy thread with a single user message
    thread = Thread(id="test-thread", title="Test Thread")
    thread.add_message(Message(role="user", content="Test"))
    return thread


@pytest.mark.asyncio
async def test_streaming_no_tool_calls(dummy_thread):
    # Create an Agent with streaming enabled
    agent = Agent(stream=True, model_name="gpt-4o")
    
    # Create a mock for _get_completion that returns our fake streaming generator
    mock_get_completion = AsyncMock()
    mock_get_completion.call = AsyncMock(return_value=(fake_streaming_no_tool_calls(), DummyCall()))
    
    # Patch the _get_completion method
    with patch.object(agent, '_get_completion', mock_get_completion):
        # Call go
        thread, new_messages = await agent.go(dummy_thread)

        # There should be an assistant message added
        assistant_msgs = [msg for msg in thread.messages if msg.role == "assistant"]
        assert len(assistant_msgs) == 1
        assistant_msg = assistant_msgs[0]

        # Verify that the combined content is as expected
        expected_content = "Hello, world!"
        assert assistant_msg.content == expected_content
        
        # Verify that there are no tool calls
        assert assistant_msg.tool_calls is None or assistant_msg.tool_calls == []

        # Verify usage metrics in the assistant message
        usage = assistant_msg.metrics.get("usage", {})
        assert usage.get("completion_tokens") == 10
        assert usage.get("prompt_tokens") == 20
        assert usage.get("total_tokens") == 30


@pytest.mark.asyncio
async def test_streaming_with_tool_calls(dummy_thread):
    # Create an Agent with streaming enabled
    agent = Agent(stream=True, model_name="gpt-4o")
    
    # Create a mock for _get_completion that returns our fake streaming generator
    mock_get_completion = AsyncMock()
    mock_get_completion.call = AsyncMock(return_value=(fake_streaming_with_tool_calls(), DummyCall()))
    
    # Patch the _get_completion method
    with patch.object(agent, '_get_completion', mock_get_completion):
        # Call go
        thread, new_messages = await agent.go(dummy_thread)

        # There should be an assistant message added
        assistant_msgs = [msg for msg in thread.messages if msg.role == "assistant"]
        assert len(assistant_msgs) == 1
        assistant_msg = assistant_msgs[0]

        # Verify that the combined content is as expected
        expected_content = "Output before tool call. "
        assert assistant_msg.content == expected_content

        # Verify that the tool call was captured
        tool_calls = assistant_msg.tool_calls
        assert tool_calls is not None
        assert isinstance(tool_calls, list)
        assert len(tool_calls) == 1
        call = tool_calls[0]
        assert call["id"] == "tool_call_1"
        assert call["type"] == "function"
        assert call["function"]["name"] == "test_tool"
        assert call["function"]["arguments"] == '{"arg": "value"}'
        
        # Verify usage metrics in the assistant message
        usage = assistant_msg.metrics.get("usage", {})
        assert usage.get("completion_tokens") == 5
        assert usage.get("prompt_tokens") == 15
        assert usage.get("total_tokens") == 20 

@pytest.mark.asyncio
async def test_streaming_continues_after_tool_calls(dummy_thread):
    """Test that streaming mode continues processing after tool calls are complete"""
    # Create an Agent with streaming enabled
    agent = Agent(stream=True, model_name="gpt-4o")
    
    # Create a mock for _get_completion that returns our fake streaming generators
    mock_get_completion = AsyncMock()
    mock_get_completion.call.side_effect = [
        (fake_streaming_with_tool_calls_and_continuation(), DummyCall()),  # First call with tool calls
        (fake_streaming_continuation(), DummyCall())  # Second call after tool execution
    ]
    
    # Mock the tool execution
    with patch.object(agent, '_get_completion', mock_get_completion), \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool execution result"
        })
        mock_tool_runner.get_tool_attributes.return_value = None
        
        # Call go
        thread, new_messages = await agent.go(dummy_thread)

        # There should be three messages: initial response with tool call, tool result, and continuation
        assert len(new_messages) == 3
        
        # Verify the sequence of messages
        assert new_messages[0].role == "assistant"
        assert new_messages[0].content == "First response. "
        assert new_messages[0].tool_calls is not None
        assert len(new_messages[0].tool_calls) == 1
        
        assert new_messages[1].role == "tool"
        assert new_messages[1].content == "Tool execution result"
        
        assert new_messages[2].role == "assistant"
        assert new_messages[2].content == "Continuing after tool call. "
        assert new_messages[2].tool_calls is None

        # Verify that _get_completion was called twice
        assert mock_get_completion.call.call_count == 2 

@pytest.mark.asyncio
async def test_streaming_tool_calls_no_content(dummy_thread):
    """Test that an assistant message is created when only a tool call is returned (no content)"""
    # Create an Agent with streaming enabled
    agent = Agent(stream=True, model_name="gpt-4o")
    
    # Create a mock for _get_completion that returns our fake streaming generator
    mock_get_completion = AsyncMock()
    mock_get_completion.call = AsyncMock(return_value=(fake_streaming_tool_calls_no_content(), DummyCall()))
    
    # Mock the tool execution
    with patch.object(agent, '_get_completion', mock_get_completion), \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool execution result"
        })
        mock_tool_runner.get_tool_attributes.return_value = None
        
        # Call go
        thread, new_messages = await agent.go(dummy_thread)

        # There should be an assistant message with empty content but tool calls
        assistant_msgs = [msg for msg in thread.messages if msg.role == "assistant"]
        assert len(assistant_msgs) == 1
        assistant_msg = assistant_msgs[0]
        
        # Content should be empty but tool calls should be present
        assert assistant_msg.content == ""
        assert assistant_msg.tool_calls is not None
        assert len(assistant_msg.tool_calls) == 1
        assert assistant_msg.tool_calls[0]["id"] == "tool_call_1"
        
        # Verify tool message was also created
        tool_msgs = [msg for msg in thread.messages if msg.role == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].content == "Tool execution result"
        
        # Verify usage metrics in the assistant message
        usage = assistant_msg.metrics.get("usage", {})
        assert usage.get("completion_tokens") == 5
        assert usage.get("prompt_tokens") == 15
        assert usage.get("total_tokens") == 20 

@pytest.mark.asyncio
async def test_streaming_none_chunks():
    """Test that streaming properly handles None chunks from litellm"""
    # Create an Agent with streaming enabled
    agent = Agent(stream=True, model_name="gpt-4o")
    
    # Create a mock for _get_completion that returns None for chunks
    mock_get_completion = AsyncMock()
    mock_get_completion.call = AsyncMock(return_value=(None, DummyCall()))
    
    # Create a thread with a message
    thread = Thread()
    thread.add_message(Message(role="user", content="Test message"))
    
    # Patch the _get_completion method
    with patch.object(agent, '_get_completion', mock_get_completion):
        with pytest.raises(TypeError, match="'async for' requires an object with __aiter__ method, got NoneType"):
            await agent.go(thread)

@pytest.mark.asyncio
async def test_streaming_invalid_chunks():
    """Test that streaming properly handles invalid chunks from litellm"""
    # Create an Agent with streaming enabled
    agent = Agent(stream=True, model_name="gpt-4o")
    
    # Create a mock for _get_completion that returns a non-async-iterable
    mock_get_completion = AsyncMock()
    mock_get_completion.call = AsyncMock(return_value=("not an async iterator", DummyCall()))
    
    # Create a thread with a message
    thread = Thread()
    thread.add_message(Message(role="user", content="Test message"))
    
    # Patch the _get_completion method
    with patch.object(agent, '_get_completion', mock_get_completion):
        with pytest.raises(TypeError, match="'async for' requires an object with __aiter__ method"):
            await agent.go(thread)

@pytest.mark.asyncio
async def test_streaming_litellm_response():
    """Test that streaming properly handles the expected litellm streaming response format"""
    # Create an Agent with streaming enabled
    agent = Agent(stream=True, model_name="gpt-4o")
    
    # Create a mock async iterator that matches litellm's format
    class MockStreamingResponse:
        def __init__(self):
            self.chunks = [
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Hello"), finish_reason="")]),
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content=" World"), finish_reason="stop")])
            ]
            self.current = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.current >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.current]
            self.current += 1
            return chunk
    
    # Create a mock for _get_completion
    mock_get_completion = AsyncMock()
    mock_get_completion.call = AsyncMock(return_value=(MockStreamingResponse(), DummyCall()))
    
    # Create a thread with a message
    thread = Thread()
    thread.add_message(Message(role="user", content="Test message"))
    
    # Patch the _get_completion method
    with patch.object(agent, '_get_completion', mock_get_completion):
        thread, new_messages = await agent.go(thread)
        
        # Verify the combined content
        assert len(new_messages) == 1
        assert new_messages[0].role == "assistant"
        assert new_messages[0].content == "Hello World" 

@pytest.mark.asyncio
async def test_streaming_with_custom_tool():
    """Test streaming with a custom tool, replicating the tools_streaming.py scenario"""
    # Create a custom translator tool like in the example
    def custom_translator_implementation(text: str, target_language: str) -> str:
        translations = {
            "spanish": {"hello": "hola"},
            "french": {"good morning": "bonjour"}
        }
        target_language = target_language.lower()
        text = text.lower()
        if target_language not in translations:
            return f"Error: Unsupported target language '{target_language}'"
        if text in translations[target_language]:
            return f"Translation: {translations[target_language][text]}"
        return f"Mock translation to {target_language}: [{text}]"

    custom_translator_tool = {
        "definition": {
            "type": "function",
            "function": {
                "name": "translate",
                "description": "Translate text to another language",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to translate"
                        },
                        "target_language": {
                            "type": "string",
                            "description": "The target language for translation",
                            "enum": ["Spanish", "French"]
                        }
                    },
                    "required": ["text", "target_language"]
                }
            }
        },
        "implementation": custom_translator_implementation,
        "attributes": {
            "category": "language",
            "version": "1.0"
        }
    }

    # Create an Agent with streaming enabled and the custom tool
    agent = Agent(
        model_name="gpt-4o",
        purpose="To help with translations",
        tools=[custom_translator_tool],
        temperature=0.7,
        stream=True
    )

    # Create a mock streaming response that includes tool calls
    class MockStreamingWithToolCalls:
        def __init__(self):
            self.chunks = [
                # First chunk with some content
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Let me translate that for you. "), finish_reason="")]),
                # Second chunk with tool call
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(
                    content="",
                    tool_calls=[{
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "translate",
                            "arguments": '{"text": "hello", "target_language": "Spanish"}'
                        }
                    }]
                ), finish_reason="tool_calls")]),
                # Final chunk after tool execution
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="The translation is complete."), finish_reason="stop")])
            ]
            self.current = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.current >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.current]
            self.current += 1
            return chunk

    # Create a mock for _get_completion
    mock_get_completion = AsyncMock()
    mock_get_completion.call = AsyncMock(return_value=(MockStreamingWithToolCalls(), DummyCall()))

    # Create a thread with a message
    thread = Thread()
    thread.add_message(Message(role="user", content="How do you say 'hello' in Spanish?"))

    # Patch the _get_completion method and tool runner
    with patch.object(agent, '_get_completion', mock_get_completion), \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "translate",
            "content": "Translation: hola"
        })
        mock_tool_runner.get_tool_attributes.return_value = None

        thread, new_messages = await agent.go(thread)

        # Verify the sequence of messages
        assert len(new_messages) == 3  # Initial response, tool result, final response
        
        # Check initial assistant message
        assert new_messages[0].role == "assistant"
        assert new_messages[0].content == "Let me translate that for you. "
        assert new_messages[0].tool_calls is not None
        assert len(new_messages[0].tool_calls) == 1
        assert new_messages[0].tool_calls[0]["function"]["name"] == "translate"
        
        # Check tool message
        assert new_messages[1].role == "tool"
        assert new_messages[1].content == "Translation: hola"
        
        # Check final assistant message
        assert new_messages[2].role == "assistant"
        assert new_messages[2].content == "The translation is complete." 

@pytest.mark.asyncio
async def test_streaming_tool_call_dict_format():
    """Test handling of tool calls that come back as dictionaries instead of objects"""
    agent = Agent(stream=True, model_name="gpt-4o")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test message"))

    # Mock a streaming response where tool calls come back as dictionaries
    class MockStreamingWithDictToolCalls:
        def __init__(self):
            self.chunks = [
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Let me help you with that. "), finish_reason="")]),
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(
                    content="",
                    tool_calls=[{
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "translate",
                            "arguments": '{"text": "hello", "target_language": "Spanish"}'
                        }
                    }]
                ), finish_reason="tool_calls")])
            ]
            self.current = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.current >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.current]
            self.current += 1
            return chunk

    # Mock _get_completion
    mock_get_completion = AsyncMock()
    mock_get_completion.call = AsyncMock(return_value=(MockStreamingWithDictToolCalls(), DummyCall()))
    
    # Patch the _get_completion method and tool runner
    with patch.object(agent, '_get_completion', mock_get_completion), \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "translate",
            "content": "Translation: hola"
        })
        mock_tool_runner.get_tool_attributes.return_value = None

        thread, new_messages = await agent.go(thread)

        # Verify we got the expected messages
        assert len(new_messages) == 2  # Initial response with tool call and tool result
        assert new_messages[0].content == "Let me help you with that. "
        assert new_messages[0].tool_calls is not None
        assert len(new_messages[0].tool_calls) == 1
        assert new_messages[0].tool_calls[0]["function"]["name"] == "translate"
        assert new_messages[1].role == "tool"
        assert new_messages[1].content == "Translation: hola"

@pytest.mark.asyncio
async def test_streaming_tool_call_error_handling():
    """Test that tool call errors are handled properly and don't repeat"""
    agent = Agent(stream=True, model_name="gpt-4o")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test message"))

    # Mock a streaming response with a tool call
    class MockStreamingWithToolCall:
        def __init__(self):
            self.chunks = [
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Processing your request. "), finish_reason="")]),
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(
                    content="",
                    tool_calls=[{
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "translate",
                            "arguments": '{"text": "hello", "target_language": "Spanish"}'
                        }
                    }]
                ), finish_reason="tool_calls")])
            ]
            self.current = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.current >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.current]
            self.current += 1
            return chunk

    class MockStreamingErrorResponse:
        def __init__(self):
            self.chunks = [
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="I'm currently unable to help with that due to a technical issue. "), finish_reason="")]),
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Is there anything else I can assist you with?"), finish_reason="stop")])
            ]
            self.current = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.current >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.current]
            self.current += 1
            return chunk

    # Mock _get_completion
    mock_get_completion = AsyncMock()
    mock_get_completion.call = AsyncMock(side_effect=[
        (MockStreamingWithToolCall(), DummyCall()),
        (MockStreamingErrorResponse(), DummyCall())
    ])
    
    # Patch the _get_completion method and tool runner
    with patch.object(agent, '_get_completion', mock_get_completion), \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        # Mock tool execution to raise an error
        mock_tool_runner.execute_tool_call = AsyncMock(side_effect=Exception("Tool execution failed"))
        mock_tool_runner.get_tool_attributes.return_value = None

        thread, new_messages = await agent.go(thread)

        # Verify error handling
        assert len(new_messages) == 3  # Initial response, error message, and final message
        assert new_messages[0].content == "Processing your request. "
        assert new_messages[1].role == "tool"
        assert "Error executing tool" in new_messages[1].content
        assert new_messages[2].role == "assistant"
        assert "I'm currently unable to help with that due to a technical issue" in new_messages[2].content
        
        # Verify we only got one error message
        error_messages = [m for m in new_messages if "Error executing tool" in m.content]
        assert len(error_messages) == 1

@pytest.mark.asyncio
async def test_streaming_stops_after_tool_error():
    """Test that streaming stops after a tool error and returns an appropriate message"""
    agent = Agent(stream=True, model_name="gpt-4o")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test message"))

    # Mock streaming responses
    class MockStreamingWithToolCall:
        def __init__(self):
            self.chunks = [
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Let me check that for you. "), finish_reason="")]),
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(
                    content="",
                    tool_calls=[{
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "arguments": '{"arg": "value"}'
                        }
                    }]
                ), finish_reason="tool_calls")])
            ]
            self.current = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.current >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.current]
            self.current += 1
            return chunk

    class MockStreamingFinalResponse:
        def __init__(self):
            self.chunks = [
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="I'm currently unable to help with that due to a technical issue. "), finish_reason="")]),
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Is there anything else I can assist you with?"), finish_reason="stop")])
            ]
            self.current = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.current >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.current]
            self.current += 1
            return chunk

    # Mock _get_completion
    mock_get_completion = AsyncMock()
    mock_get_completion.call.side_effect = [
        (MockStreamingWithToolCall(), DummyCall()),
        (MockStreamingFinalResponse(), DummyCall())
    ]
    
    # Patch the _get_completion method and tool runner
    with patch.object(agent, '_get_completion', mock_get_completion), \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        # Mock tool execution to raise an error
        mock_tool_runner.execute_tool_call = AsyncMock(side_effect=Exception("Tool execution failed"))
        mock_tool_runner.get_tool_attributes.return_value = None

        thread, new_messages = await agent.go(thread)

        # Verify we got the expected sequence of messages
        assert len(new_messages) == 3
        
        # Initial assistant message with tool call
        assert new_messages[0].role == "assistant"
        assert new_messages[0].content == "Let me check that for you. "
        assert new_messages[0].tool_calls is not None
        assert len(new_messages[0].tool_calls) == 1
        
        # Tool error message
        assert new_messages[1].role == "tool"
        assert "Error executing tool" in new_messages[1].content
        
        # Final assistant message
        assert new_messages[2].role == "assistant"
        assert "I'm currently unable to help with that due to a technical issue" in new_messages[2].content
        
        # Verify we only called _get_completion twice
        assert mock_get_completion.call.call_count == 2 

@pytest.mark.asyncio
async def test_streaming_tool_error_prevents_retries():
    """Test that a tool error in streaming mode prevents retries and returns appropriate error message"""
    agent = Agent(stream=True, model_name="gpt-4o")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test message"))

    # Mock streaming responses
    class MockStreamingWithToolCall:
        def __init__(self):
            self.chunks = [
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Let me check that for you. "), finish_reason="")]),
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(
                    content="",
                    tool_calls=[{
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "arguments": '{"arg": "value"}'
                        }
                    }]
                ), finish_reason="tool_calls")])
            ]
            self.current = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.current >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.current]
            self.current += 1
            return chunk

    class MockStreamingErrorResponse:
        def __init__(self):
            self.chunks = [
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="I'm currently unable to help with that due to a technical issue. "), finish_reason="")]),
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Is there anything else I can assist you with?"), finish_reason="stop")])
            ]
            self.current = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.current >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.current]
            self.current += 1
            return chunk

    # Mock _get_completion
    mock_get_completion = AsyncMock()
    mock_get_completion.call.side_effect = [
        (MockStreamingWithToolCall(), DummyCall()),
        (MockStreamingErrorResponse(), DummyCall())
    ]
    
    # Patch the _get_completion method and tool runner
    with patch.object(agent, '_get_completion', mock_get_completion), \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        # Mock tool execution to raise an error
        mock_tool_runner.execute_tool_call = AsyncMock(side_effect=ValueError("Tool execution failed"))
        mock_tool_runner.get_tool_attributes.return_value = None

        thread, new_messages = await agent.go(thread)

        # Verify we got exactly 3 messages (initial, error, final)
        assert len(new_messages) == 3
        
        # Initial assistant message with tool call
        assert new_messages[0].role == "assistant"
        assert new_messages[0].content == "Let me check that for you. "
        assert new_messages[0].tool_calls is not None
        assert len(new_messages[0].tool_calls) == 1
        
        # Tool error message
        assert new_messages[1].role == "tool"
        assert "Error executing tool" in new_messages[1].content
        
        # Final assistant message
        assert new_messages[2].role == "assistant"
        assert "I'm currently unable to help with that due to a technical issue" in new_messages[2].content
        
        # Verify we only called _get_completion twice (initial + error message)
        assert mock_get_completion.call.call_count == 2
        
        # Verify no additional tool calls were attempted
        assert mock_tool_runner.execute_tool_call.call_count == 1 

@pytest.mark.asyncio
async def test_streaming_prevents_multiple_tool_call_attempts():
    """Test that streaming mode properly stops after a tool error and doesn't make multiple attempts"""
    agent = Agent(stream=True, model_name="gpt-4o")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test message"))

    # Mock streaming responses that simulate multiple tool call attempts
    class MockStreamingFirstAttempt:
        def __init__(self):
            self.chunks = [
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Let me check that for you. "), finish_reason="")]),
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(
                    content="",
                    tool_calls=[{
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "arguments": '{"arg": "value"}'
                        }
                    }]
                ), finish_reason="tool_calls")])
            ]
            self.current = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.current >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.current]
            self.current += 1
            return chunk

    class MockStreamingSecondAttempt:
        def __init__(self):
            self.chunks = [
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Let me try that again. "), finish_reason="")]),
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(
                    content="",
                    tool_calls=[{
                        "id": "call-2",
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "arguments": '{"arg": "value2"}'
                        }
                    }]
                ), finish_reason="tool_calls")])
            ]
            self.current = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.current >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.current]
            self.current += 1
            return chunk

    class MockStreamingErrorResponse:
        def __init__(self):
            self.chunks = [
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="I'm currently unable to help with that due to a technical issue. "), finish_reason="")]),
                FakeChunk(choices=[FakeChoice(delta=FakeDelta(content="Is there anything else I can assist you with?"), finish_reason="stop")])
            ]
            self.current = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.current >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.current]
            self.current += 1
            return chunk

    # Mock _get_completion to simulate multiple attempts
    mock_get_completion = AsyncMock()
    mock_get_completion.call.side_effect = [
        (MockStreamingFirstAttempt(), DummyCall()),
        (MockStreamingErrorResponse(), DummyCall())
    ]
    
    # Patch the _get_completion method and tool runner
    with patch.object(agent, '_get_completion', mock_get_completion), \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        # Mock tool execution to raise an error
        mock_tool_runner.execute_tool_call = AsyncMock(side_effect=ValueError("Tool execution failed"))
        mock_tool_runner.get_tool_attributes.return_value = None

        thread, new_messages = await agent.go(thread)

        # Verify we got exactly 3 messages (initial, error, final)
        assert len(new_messages) == 3
        
        # Initial assistant message with tool call
        assert new_messages[0].role == "assistant"
        assert new_messages[0].content == "Let me check that for you. "
        assert new_messages[0].tool_calls is not None
        assert len(new_messages[0].tool_calls) == 1
        
        # Tool error message
        assert new_messages[1].role == "tool"
        assert "Error executing tool" in new_messages[1].content
        
        # Final assistant message
        assert new_messages[2].role == "assistant"
        assert "I'm currently unable to help with that due to a technical issue" in new_messages[2].content
        
        # Verify we only called _get_completion twice (initial + error message)
        assert mock_get_completion.call.call_count == 2
        
        # Verify no additional tool calls were attempted
        assert mock_tool_runner.execute_tool_call.call_count == 1
        
        # Verify we didn't try to process any more tool calls after the error
        tool_calls = [msg for msg in new_messages if msg.tool_calls is not None]
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_calls[0]["id"] == "call-1" 