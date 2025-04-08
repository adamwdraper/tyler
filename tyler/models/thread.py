from typing import List, Dict, Optional, Literal, Any
from datetime import datetime, UTC
from pydantic import BaseModel, Field, field_validator
from tyler.models.message import Message
from tyler.storage.file_store import FileStore
from litellm import completion
import uuid
import weave

class Thread(BaseModel):
    """Represents a thread containing multiple messages"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: Optional[str] = Field(default="Untitled Thread")
    messages: List[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    attributes: Dict = Field(default_factory=dict)
    source: Optional[Dict[str, Any]] = None  # {"name": "slack", "thread_id": "..."}
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "thread-123",
                    "title": "Example Thread",
                    "messages": [],
                    "created_at": "2024-02-07T00:00:00+00:00",
                    "updated_at": "2024-02-07T00:00:00+00:00",
                    "attributes": {},
                    "source": {
                        "name": "slack",
                        "channel": "C123",
                        "thread_ts": "1234567890.123"
                    }
                }
            ]
        }
    }
    
    @field_validator("created_at", "updated_at", mode="before")
    def ensure_timezone(cls, value: datetime) -> datetime:
        """Ensure all datetime fields are timezone-aware UTC"""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    def model_dump(self, mode: str = "json") -> Dict[str, Any]:
        """Convert thread to a dictionary suitable for JSON serialization
        
        Args:
            mode: Serialization mode, either "json" or "python". 
                 "json" converts datetimes to ISO strings (default).
                 "python" keeps datetimes as datetime objects.
        """
        return {
            "id": self.id,
            "title": self.title,
            "messages": [msg.model_dump(mode=mode) for msg in self.messages],
            "created_at": self.created_at.isoformat() if mode == "json" else self.created_at,
            "updated_at": self.updated_at.isoformat() if mode == "json" else self.updated_at,
            "attributes": self.attributes,
            "source": self.source
        }
    
    def ensure_system_prompt(self, prompt: str) -> None:
        """Ensures a system prompt exists as the first message in the thread.
        
        If no system message exists at the start of the thread, adds one.
        Does not modify any existing system messages.
        """
        if not self.messages or self.messages[0].role != "system":
            self.add_message(Message(role="system", content=prompt))

    def add_message(self, message: Message) -> None:
        """Add a new message to the thread and update analytics"""
        # Set message sequence - system messages always get 0, others get next available number starting at 1
        if message.role == "system":
            message.sequence = 0
            # Insert at beginning to maintain system message first
            self.messages.insert(0, message)
        else:
            # Find highest sequence number and increment
            max_sequence = max((m.sequence for m in self.messages if m.role != "system"), default=0)
            message.sequence = max_sequence + 1
            self.messages.append(message)
        
        self.updated_at = datetime.now(UTC)

    async def get_messages_for_chat_completion(self, file_store: Optional[FileStore] = None) -> List[Dict[str, Any]]:
        """Return messages in the format expected by chat completion APIs
        
        Args:
            file_store: Optional FileStore instance to pass to messages for file URL access
        """
        return [msg.to_chat_completion_message(file_store=file_store) for msg in self.messages]

    def clear_messages(self) -> None:
        """Clear all messages from the thread"""
        self.messages = []
        self.updated_at = datetime.now(UTC)

    def get_last_message_by_role(self, role: Literal["user", "assistant", "system", "tool"]) -> Optional[Message]:
        """Return the last message with the specified role, or None if no messages exist with that role"""
        messages = [m for m in self.messages if m.role == role]
        return messages[-1] if messages else None
        
    @weave.op()
    def generate_title(self) -> str:
        """Generate a concise title for the thread using GPT-4o"""
        if not self.messages:
            return "Empty Thread"
        
        # Prepare messages for the title generation
        system_prompt = "You are a title generator. Generate a clear, concise title (less than 10 words) that captures the main topic or purpose of this conversation. Return only the title, nothing else."
        
        # Get thread messages excluding system prompt and combine them into a single conversation string
        thread_messages = [msg.to_chat_completion_message() for msg in self.messages if msg.role != "system"]
        conversation = "\n".join([f"{msg['role']}: {msg['content']}" for msg in thread_messages])
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate a title for this conversation:\n\n{conversation}"}
        ]
        
        response = completion(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=50
        )
        
        new_title = response.choices[0].message.content.strip()
        self.title = new_title
        self.updated_at = datetime.now(UTC)
        return new_title

    def get_total_tokens(self) -> Dict[str, Any]:
        """Get total token usage across all messages in the thread
        
        Returns:
            Dictionary containing:
            - overall: Total token counts across all models
            - by_model: Token counts broken down by model
        """
        overall = {
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "total_tokens": 0
        }
        
        by_model = {}
        
        for message in self.messages:
            metrics = message.metrics
            if not metrics:
                continue
                
            # Update overall counts
            if "usage" in metrics:
                overall["completion_tokens"] += metrics["usage"].get("completion_tokens", 0)
                overall["prompt_tokens"] += metrics["usage"].get("prompt_tokens", 0)
                overall["total_tokens"] += metrics["usage"].get("total_tokens", 0)
            
            # Update per-model counts
            model = metrics.get("model")
            if model:
                if model not in by_model:
                    by_model[model] = {
                        "completion_tokens": 0,
                        "prompt_tokens": 0,
                        "total_tokens": 0
                    }
                
                if "usage" in metrics:
                    by_model[model]["completion_tokens"] += metrics["usage"].get("completion_tokens", 0)
                    by_model[model]["prompt_tokens"] += metrics["usage"].get("prompt_tokens", 0)
                    by_model[model]["total_tokens"] += metrics["usage"].get("total_tokens", 0)
            
        return {
            "overall": overall,
            "by_model": by_model
        }

    def get_model_usage(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics for a specific model or all models
        
        Args:
            model_name: Optional name of model to get stats for. If None, returns all models.
            
        Returns:
            Dictionary containing model usage statistics
        """
        model_usage = {}
        
        for message in self.messages:
            metrics = message.metrics
            if not metrics or not metrics.get("model"):
                continue
                
            model = metrics["model"]
            if model not in model_usage:
                model_usage[model] = {
                    "calls": 0,
                    "completion_tokens": 0,
                    "prompt_tokens": 0,
                    "total_tokens": 0
                }
            
            model_usage[model]["calls"] += 1
            if "usage" in metrics:
                model_usage[model]["completion_tokens"] += metrics["usage"].get("completion_tokens", 0)
                model_usage[model]["prompt_tokens"] += metrics["usage"].get("prompt_tokens", 0)
                model_usage[model]["total_tokens"] += metrics["usage"].get("total_tokens", 0)
        
        if model_name:
            return model_usage.get(model_name, {
                "calls": 0,
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "total_tokens": 0
            })
            
        return model_usage

    def get_message_timing_stats(self) -> Dict[str, Any]:
        """Calculate timing statistics across all messages
        
        Returns:
            Dictionary containing:
            - total_latency: Total processing time across all messages (in milliseconds)
            - average_latency: Average processing time per message (in milliseconds)
            - message_count: Total number of messages with timing data
        """
        total_latency = 0
        message_count = 0
        
        for message in self.messages:
            if message.metrics and message.metrics.get("timing", {}).get("latency"):
                total_latency += message.metrics["timing"]["latency"]
                message_count += 1
        
        return {
            "total_latency": total_latency,
            "average_latency": total_latency / message_count if message_count > 0 else 0,
            "message_count": message_count
        }

    def get_message_counts(self) -> Dict[str, int]:
        """Get count of messages by role
        
        Returns:
            Dictionary with counts for each role (system, user, assistant, tool)
        """
        counts = {
            "system": 0,
            "user": 0,
            "assistant": 0,
            "tool": 0
        }
        
        for message in self.messages:
            counts[message.role] += 1
            
        return counts

    def get_tool_usage(self) -> Dict[str, Any]:
        """Get count of tool function calls in the thread
        
        Returns:
            Dictionary containing:
            - tools: Dictionary of tool names and their call counts
            - total_calls: Total number of tool calls made
        """
        tool_counts = {}  # {"tool_name": count}
        
        for message in self.messages:
            if message.role == "assistant" and message.tool_calls:
                for call in message.tool_calls:
                    if isinstance(call, dict):
                        tool_name = call.get("function", {}).get("name")
                    else:
                        # Handle OpenAI tool call objects
                        tool_name = getattr(call.function, "name", None)
                        
                    if tool_name:
                        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
        
        return {
            "tools": tool_counts,
            "total_calls": sum(tool_counts.values())
        }

    def get_system_message(self) -> Optional[Message]:
        """Get the system message from the thread if it exists"""
        for message in self.messages:
            if message.role == "system":
                return message
        return None

    def get_messages_in_sequence(self) -> List[Message]:
        """Get messages sorted by sequence number"""
        return sorted(self.messages, key=lambda m: m.sequence if m.sequence is not None else float('inf'))