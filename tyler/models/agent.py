from typing import List, Optional, Tuple, Union, Dict, Any
from weave import Model, Prompt
import weave
from litellm import acompletion  # Use async completion
from tyler.models.thread import Thread, Message
from tyler.utils.tool_runner import tool_runner
from tyler.database.memory_store import MemoryThreadStore
from pydantic import Field, PrivateAttr
from datetime import datetime, UTC
from tyler.utils.file_processor import FileProcessor
import magic
import base64
import os
from tyler.storage import get_file_store
import logging

logger = logging.getLogger(__name__)

class AgentPrompt(Prompt):
    system_template: str = Field(default="""You are {name}, an LLM agent with a specific purpose that can converse with users, answer questions, and when necessary, use tools to perform tasks.

Current date: {current_date}
                                 
Your purpose is: {purpose}

Some are some relevant notes to help you accomplish your purpose:
```
{notes}
```
""")

    @weave.op()
    def system_prompt(self, purpose: str, name: str, notes: str = "") -> str:
        return self.system_template.format(
            current_date=datetime.now().strftime("%Y-%m-%d %A"),
            purpose=purpose,
            name=name,
            notes=notes
        )

class Agent(Model):
    model_name: str = Field(default="gpt-4o")
    temperature: float = Field(default=0.7)
    name: str = Field(default="Tyler")
    purpose: str = Field(default="To be a helpful assistant.")
    notes: str = Field(default="")
    tools: List[Union[str, Dict]] = Field(default_factory=list, description="List of tools available to the agent. Can include built-in tool module names (as strings) and custom tools (as dicts with required 'definition' and 'implementation' keys, and an optional 'attributes' key for tool metadata).")
    max_tool_iterations: int = Field(default=10)
    thread_store: Optional[object] = Field(default_factory=MemoryThreadStore, description="Thread storage implementation. Uses in-memory storage by default.")
    stream: bool = Field(default=False, description="Whether to stream responses from the LLM.")
    
    _prompt: AgentPrompt = PrivateAttr(default_factory=AgentPrompt)
    _iteration_count: int = PrivateAttr(default=0)
    _file_processor: FileProcessor = PrivateAttr(default_factory=FileProcessor)
    _processed_tools: List[Dict] = PrivateAttr(default_factory=list)

    model_config = {
        "arbitrary_types_allowed": True,
        "extra": "allow"
    }

    def __init__(self, **data):
        super().__init__(**data)
        
        # Process tools parameter to handle both module names and custom tools
        processed_tools = []
        
        for tool in self.tools:
            if isinstance(tool, str):
                # If tool is a string, treat it as a module name
                module_tools = tool_runner.load_tool_module(tool)
                processed_tools.extend(module_tools)
            elif isinstance(tool, dict):
                # If tool is a dict, it should have both definition and implementation
                if 'definition' not in tool or 'implementation' not in tool:
                    raise ValueError(
                        "Custom tools must be dictionaries with 'definition' and 'implementation' keys. "
                        "The 'definition' should be the OpenAI function definition, and "
                        "'implementation' should be the callable that implements the tool."
                    )
                # Register the implementation with the tool runner
                tool_name = tool['definition']['function']['name']
                tool_runner.register_tool(
                    name=tool_name,
                    implementation=tool['implementation'],
                    definition=tool['definition']['function']
                )
                
                # Store tool attributes if present at top level
                if 'attributes' in tool:
                    tool_runner.register_tool_attributes(tool_name, tool['attributes'])
                    
                # Add only the OpenAI function definition to processed tools
                # Strip any extra fields that aren't part of the OpenAI spec
                processed_tools.append({
                    "type": "function",
                    "function": tool['definition']['function']
                })
                
        # Store the processed tools for use in chat completion
        self._processed_tools = processed_tools

    def _normalize_tool_call(self, tool_call):
        """Convert a tool_call dict to an object with attributes so it can be used by tool_runner."""
        if isinstance(tool_call, dict):
            from types import SimpleNamespace
            function_data = tool_call.get("function", {})
            normalized_function = SimpleNamespace(**function_data)
            normalized = SimpleNamespace(
                id=tool_call.get("id"),
                type=tool_call.get("type", "function"),
                function=normalized_function
            )
            return normalized
        return tool_call

    async def _handle_tool_execution(self, tool_call) -> dict:
        """
        Execute a single tool call and format the result message
        
        Args:
            tool_call: The tool call object from the model response
        
        Returns:
            dict: Formatted tool result message
        """
        normalized_tool_call = self._normalize_tool_call(tool_call)
        # If the arguments string is empty or only whitespace, replace it with '{}'
        if not normalized_tool_call.function.arguments or normalized_tool_call.function.arguments.strip() == "":
            normalized_tool_call.function.arguments = "{}"
        
        return await tool_runner.execute_tool_call(normalized_tool_call)

    async def _process_streaming_chunks(self, chunks) -> Tuple[str, str, List[Dict], Dict]:
        """Process streaming chunks from the LLM.
        
        Args:
            chunks: Async generator of completion chunks
        
        Returns:
            Tuple[str, str, List[Dict], Dict]: A tuple containing:
                - pre_tool_content: aggregated content prior to any tool call
                - post_tool_content: aggregated content after the first tool call
                - tool_calls: list of tool calls encountered (from the first chunk with tool calls)
                - usage_metrics: taken from the final chunk
        """
        if chunks is None or not hasattr(chunks, '__aiter__'):
            raise TypeError(f"'async for' requires an object with __aiter__ method, got {type(chunks).__name__}")

        pre_tool_content = ""
        post_tool_content = ""
        tool_calls = []
        encountered_tool = False
        final_chunk = None

        async for chunk in chunks:
            final_chunk = chunk
            delta = chunk.choices[0].delta
            if hasattr(delta, 'tool_calls') and delta.tool_calls:
                if not encountered_tool:
                    # Record tool calls from this chunk
                    for tc in delta.tool_calls:
                        if isinstance(tc, dict):
                            normalized = tc
                        else:
                            normalized = {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                        tool_calls.append(normalized)
                    encountered_tool = True
                # Either way, if tool_calls present and content exists, treat it as post_tool_content
                if hasattr(delta, 'content') and delta.content is not None:
                    post_tool_content += delta.content
            else:
                if not encountered_tool:
                    if hasattr(delta, 'content') and delta.content is not None:
                        pre_tool_content += delta.content
                else:
                    if hasattr(delta, 'content') and delta.content is not None:
                        post_tool_content += delta.content

        usage_metrics = {}
        if final_chunk and hasattr(final_chunk, 'usage') and final_chunk.usage:
            usage_metrics = {
                "completion_tokens": final_chunk.usage.completion_tokens,
                "prompt_tokens": final_chunk.usage.prompt_tokens,
                "total_tokens": final_chunk.usage.total_tokens
            }

        return pre_tool_content, post_tool_content, tool_calls, usage_metrics

    async def _process_message_files(self, message: Message) -> None:
        """Process any files attached to the message"""
        for attachment in message.attachments:
            try:
                # Get content as bytes
                content = await attachment.get_content_bytes()
                
                # Check if it's an image
                mime_type = magic.from_buffer(content, mime=True)
                
                if mime_type.startswith('image/'):
                    # Store the image content in the attachment
                    attachment.processed_content = {
                        "type": "image",
                        "content": base64.b64encode(content).decode('utf-8'),
                        "mime_type": mime_type
                    }
                else:
                    # Use file processor for PDFs and other supported types
                    result = self._file_processor.process_file(content, attachment.filename)
                    attachment.processed_content = result
                    
                # Store the detected mime type if not already set
                if not attachment.mime_type:
                    attachment.mime_type = mime_type
                    
            except Exception as e:
                attachment.processed_content = {"error": f"Failed to process file: {str(e)}"}
        
        # After processing all attachments, update the message content if there are images
        image_attachments = [
            att for att in message.attachments 
            if att.processed_content and att.processed_content.get("type") == "image"
        ]
        
        # Don't modify the content - it should stay as text only
        # The Message.to_chat_completion_message() method will handle creating the multimodal format
    
    @weave.op()
    async def _get_completion(self, **completion_params) -> Any:
        """Get a completion from the LLM with weave tracing.
        
        Returns:
            Any: The completion response. When called with .call(), also returns weave_call info.
            If streaming is enabled, returns an async generator of completion chunks.
        """
        # Add stream parameter if enabled
        if self.stream:
            completion_params["stream"] = True
            
        # Call completion directly first to get the response
        response = await acompletion(**completion_params)
        return response
    
    @weave.op()
    async def step(self, thread: Thread) -> Tuple[Any, Dict]:
        """Execute a single step of the agent's processing.
        
        A step consists of:
        1. Getting a completion from the LLM
        2. Collecting metrics about the completion
        3. Processing any tool calls if present
        
        Args:
            thread: The thread to process
            
        Returns:
            Tuple[Any, Dict]: The completion response and metrics. If streaming is enabled,
            returns a tuple of (async generator of completion chunks, metrics).
        """
        completion_params = {
            "model": self.model_name,
            "messages": thread.get_messages_for_chat_completion(),
            "temperature": self.temperature,
        }
        
        if len(self._processed_tools) > 0:
            completion_params["tools"] = self._processed_tools
        
        # Add stream parameter if enabled
        if self.stream:
            completion_params["stream"] = True
        
        # Track API call time
        api_start_time = datetime.now(UTC)
        
        try:
            # Get completion with weave call tracking
            response, call = await self._get_completion.call(self, **completion_params)
            
            # Create metrics dict with essential data
            metrics = {
                "model": self.model_name,  # Use model_name since streaming responses don't include model
                "timing": {
                    "started_at": api_start_time.isoformat(),
                    "ended_at": datetime.now(UTC).isoformat(),
                    "latency": (datetime.now(UTC) - api_start_time).total_seconds() * 1000
                }
            }

            # Add weave-specific metrics if available
            try:
                if hasattr(call, 'id') and call.id:
                    metrics["weave_call"] = {
                        "id": str(call.id),
                        "ui_url": str(call.ui_url)
                    }
            except (AttributeError, ValueError):
                pass
            
            # For non-streaming responses, get usage directly
            if not self.stream:
                metrics["usage"] = {
                    "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0)
                }
                    
            return response, metrics
        except Exception as e:
            # Re-raise the original exception
            raise e

    async def _get_thread(self, thread_or_id: Union[str, Thread]) -> Thread:
        """Get thread object from ID or return the thread object directly."""
        if isinstance(thread_or_id, str):
            if not self.thread_store:
                raise ValueError("Thread store is required when passing thread ID")
            thread = await self.thread_store.get(thread_or_id)
            if not thread:
                raise ValueError(f"Thread with ID {thread_or_id} not found")
            return thread
        return thread_or_id

    def _serialize_tool_calls(self, tool_calls: Optional[List[Any]]) -> Optional[List[Dict]]:
        """Serialize tool calls to a list of dictionaries.

        Args:
            tool_calls: List of tool calls to serialize, or None

        Returns:
            Optional[List[Dict]]: Serialized tool calls, or None if input is None
        """
        if tool_calls is None:
            return None
            
        serialized = []
        for tool_call in tool_calls:
            if isinstance(tool_call, dict):
                serialized.append(tool_call)
            else:
                serialized.append({
                    "id": str(tool_call.id),
                    "type": str(tool_call.type),
                    "function": {
                        "name": str(tool_call.function.name),
                        "arguments": str(tool_call.function.arguments)
                    }
                })
        return serialized

    async def _process_tool_call(self, tool_call, thread: Thread, new_messages: List[Message]) -> bool:
        """Process a single tool call and return whether to break the iteration."""
        # Get tool name based on tool_call type
        tool_name = tool_call['function']['name'] if isinstance(tool_call, dict) else tool_call.function.name
        
        # Get tool attributes before execution
        tool_attributes = tool_runner.get_tool_attributes(tool_name)

        # Execute the tool
        tool_start_time = datetime.now(UTC)
        try:
            result = await self._handle_tool_execution(tool_call)
        except Exception as e:
            # Handle tool execution error
            result = {
                "name": tool_name,
                "content": f"Error executing tool: {str(e)}"
            }
            # Return True to stop further processing after a tool error
            should_break = True
        else:
            # Only check interrupt attribute if tool executed successfully
            should_break = tool_attributes and tool_attributes.get('type') == 'interrupt'

        # Create tool metrics
        tool_metrics = {
            "timing": {
                "started_at": tool_start_time.isoformat(),
                "ended_at": datetime.now(UTC).isoformat(),
                "latency": (datetime.now(UTC) - tool_start_time).total_seconds() * 1000
            }
        }

        # Add tool result message
        message = Message(
            role="tool",
            content=result["content"],
            name=str(result.get("name", tool_name)),
            tool_call_id=str(tool_call['id'] if isinstance(tool_call, dict) else tool_call.id),
            attributes={"tool_attributes": tool_attributes or {}},
            metrics=tool_metrics
        )
        thread.add_message(message)
        new_messages.append(message)

        return should_break

    async def _handle_max_iterations(self, thread: Thread, new_messages: List[Message]) -> Tuple[Thread, List[Message]]:
        """Handle the case when max iterations is reached."""
        message = Message(
            role="assistant",
            content="Maximum tool iteration count reached. Stopping further tool calls."
        )
        thread.add_message(message)
        new_messages.append(message)
        if self.thread_store:
            await self.thread_store.save(thread)
        return thread, [m for m in new_messages if m.role != "user"]

    @weave.op()
    async def go(self, thread_or_id: Union[str, Thread], new_messages: Optional[List[Message]] = None) -> Tuple[Thread, List[Message]]:
        """
        Process the next step in the thread by generating a response and handling any tool calls.
        Uses an iterative approach to handle multiple tool calls.
        
        Args:
            thread_or_id (Union[str, Thread]): Either a Thread object or thread ID to process
            new_messages (List[Message], optional): Messages added during this processing round
            
        Returns:
            Tuple[Thread, List[Message]]: The processed thread and list of new non-user messages
        """
        # Initialize new messages if not provided
        if new_messages is None:
            new_messages = []
            
        # Get and initialize thread
        thread = await self._get_thread(thread_or_id)
        system_prompt = self._prompt.system_prompt(self.purpose, self.name, self.notes)
        thread.ensure_system_prompt(system_prompt)
        
        # Check if we've already hit max iterations
        if self._iteration_count >= self.max_tool_iterations:
            return await self._handle_max_iterations(thread, new_messages)
        
        # Process any files in the last user message
        last_message = thread.get_last_message_by_role("user")
        if last_message and last_message.attachments:
            await self._process_message_files(last_message)
            if self.thread_store:
                await self.thread_store.save(thread)

        # Main iteration loop
        while self._iteration_count < self.max_tool_iterations:
            # Get completion and process response
            response, metrics = await self.step(thread)
            
            if self.stream:
                # For streaming responses, process the chunks and stream content
                pre_tool, post_tool, tool_calls, usage_metrics = await self._process_streaming_chunks(response)
                metrics["usage"] = usage_metrics
                has_tool_calls = bool(tool_calls)
            else:
                # For non-streaming responses, get content and tool calls directly
                assistant_message = response.choices[0].message
                pre_tool = assistant_message.content or ""
                tool_calls = getattr(assistant_message, 'tool_calls', None)
                has_tool_calls = tool_calls is not None and len(tool_calls) > 0
                post_tool = ""

            # Create and add assistant message for pre-tool content if any
            if pre_tool or has_tool_calls:
                message = Message(
                    role="assistant",
                    content=pre_tool,
                    tool_calls=self._serialize_tool_calls(tool_calls) if has_tool_calls else None,
                    metrics=metrics
                )
                thread.add_message(message)
                new_messages.append(message)

            # Process tool calls if any
            if has_tool_calls:
                for tool_call in tool_calls:
                    should_break = await self._process_tool_call(tool_call, thread, new_messages)
                    if should_break:
                        # Add a final message indicating we can't help due to the error
                        error_response, error_metrics = await self.step(thread)
                        if self.stream:
                            error_content = ""
                            final_chunk = None
                            async for chunk in error_response:
                                final_chunk = chunk
                                if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                                    error_content += chunk.choices[0].delta.content
                            
                            # Add usage metrics from final chunk if available
                            if final_chunk and hasattr(final_chunk, 'usage') and final_chunk.usage:
                                error_metrics["usage"] = {
                                    "completion_tokens": final_chunk.usage.completion_tokens,
                                    "prompt_tokens": final_chunk.usage.prompt_tokens,
                                    "total_tokens": final_chunk.usage.total_tokens
                                }
                        else:
                            error_content = error_response.choices[0].message.content
                        
                        message = Message(
                            role="assistant",
                            content=error_content or "I'm currently unable to help with that due to a technical issue. Is there anything else I can assist you with?",
                            metrics=error_metrics
                        )
                        thread.add_message(message)
                        new_messages.append(message)
                        
                        # Save state and return immediately after error
                        if self.thread_store:
                            await self.thread_store.save(thread)
                        return thread, [m for m in new_messages if m.role != "user"]

            # Create and add assistant message for post-tool content if any
            if post_tool:
                message = Message(
                    role="assistant",
                    content=post_tool,
                    tool_calls=None,
                    metrics=metrics
                )
                thread.add_message(message)
                new_messages.append(message)
            
            # If no tool calls and no post content, we are done
            if not has_tool_calls and not post_tool:
                break
                
            self._iteration_count += 1
            
        # Handle max iterations if needed
        if self._iteration_count >= self.max_tool_iterations:
            message = Message(
                role="assistant",
                content="Maximum tool iteration count reached. Stopping further tool calls."
            )
            thread.add_message(message)
            new_messages.append(message)
            
        # Reset iteration count before returning
        self._iteration_count = 0
            
        # Save the final state
        if self.thread_store:
            await self.thread_store.save(thread)
            
        return thread, [m for m in new_messages if m.role != "user"] 