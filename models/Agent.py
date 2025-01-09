from typing import List, Optional, Tuple
from weave import Model, Prompt
import weave
from litellm import completion
from models.Thread import Thread, Message
from utils.tool_runner import tool_runner
from database.thread_store import ThreadStore
import json
from pydantic import Field
from datetime import datetime

class AgentPrompt(Prompt):
    system_template: str = Field(default="""You are an LLM agent with a specific purpose that can converse with users, answer questions, and when necessary, use tools to perform tasks.
Current date: {current_date}
                                 
Your purpose is: {purpose}

Some are some relevant notes to help you accomplish your purpose:
```
{notes}
```

Based on the user's input, follow this routine:
1. If the user makes a statement or shares information, respond appropriately with acknowledgment.
2. If the user's request is vague, incomplete, or missing information needed to complete the task, use the relevant context to understand the user's request. If you don't find an answer in the context, ask probing questions to understand the user's request deeper. You can ask a maximum of 5 probing questions.
3. If you can answer the user's request using the relevant context or your knowledge (you are a powerful AI model with a large knowledge base), then provide a clear and concise answer.  
4. If the request requires gathering information or performing actions beyond your chat completion capabilities use the tools provided to you. After the tool is executed, you will automatically receive the results and can then formulate the next step to take.
                                 
Important: Always include a sentence explaining how you arrived at your answer in your response.  Take your time to think about the answer and include a sentence explaining your thought process.
""")

    @weave.op()
    def system_prompt(self, purpose: str, notes: str = "") -> str:
        return self.system_template.format(
            current_date=datetime.now().strftime("%Y-%m-%d %A"),
            purpose=purpose,
            notes=notes
        )

class Agent(Model):
    model_name: str = Field(default="gpt-4o")
    temperature: float = Field(default=0.7)
    purpose: str = Field(default="To be a helpful assistant.")
    notes: str = Field(default="")
    prompt: AgentPrompt = Field(default_factory=AgentPrompt)
    tools: List[dict] = Field(default_factory=list)
    max_tool_recursion: int = Field(default=10)
    current_recursion_depth: int = Field(default=0)
    thread_store: ThreadStore = Field(default_factory=ThreadStore)

    def __init__(self, **data):
        super().__init__(**data)
        # Initialize tools from tool_runner
        self.tools = tool_runner.get_tools_for_chat_completion()

    @weave.op()
    def go(self, thread_id: str, new_messages: Optional[List[Message]] = None) -> Tuple[Thread, List[Message]]:
        """
        Process the next step in the thread by generating a response and handling any tool calls.
        
        Args:
            thread_id (str): The ID of the thread to process
            new_messages (List[Message], optional): Messages added during this processing round
            
        Returns:
            Tuple[Thread, List[Message]]: The processed thread and list of new non-user messages
        """
        # Initialize new messages if not provided
        if new_messages is None:
            new_messages = []
            
        thread = self.thread_store.get(thread_id)
        if not thread:
            raise ValueError(f"Thread with ID {thread_id} not found")
            
        # Reset recursion depth on new thread turn
        if self.current_recursion_depth == 0:
            thread.ensure_system_prompt(self.prompt.system_prompt(self.purpose, self.notes))
        elif self.current_recursion_depth >= self.max_tool_recursion:
            message = Message(
                role="assistant",
                content="Maximum tool recursion depth reached. Stopping further tool calls."
            )
            thread.add_message(message)
            new_messages.append(message)
            self.thread_store.save(thread)
            return thread, [m for m in new_messages if m.role != "user"]
            
        # Get completion with tools
        response = completion(
            model=self.model_name,
            messages=thread.get_messages_for_chat_completion(),
            temperature=self.temperature,
            tools=self.tools
        )
        
        return self._process_response(response, thread, new_messages)
    
    @weave.op()
    def _process_response(self, response, thread: Thread, new_messages: List[Message]) -> Tuple[Thread, List[Message]]:
        """
        Handle the model response and process any tool calls recursively.
        
        Args:
            response: The completion response object from the language model
            thread (Thread): The thread object to update
            new_messages (List[Message]): Messages added during this processing round
            
        Returns:
            Tuple[Thread, List[Message]]: The processed thread and list of new non-user messages
        """
        message_content = response.choices[0].message.content or ""
        tool_calls = getattr(response.choices[0].message, 'tool_calls', None)
        has_tool_calls = tool_calls is not None and len(tool_calls) > 0
        
        if not has_tool_calls:
            self.current_recursion_depth = 0  # Reset depth when done with tools
            message = Message(
                role="assistant",
                content=message_content
            )
            thread.add_message(message)
            new_messages.append(message)
            self.thread_store.save(thread)
            return thread, [m for m in new_messages if m.role != "user"]
            
        # Add assistant message with tool calls only if there's content
        if message_content.strip():
            message = Message(
                role="assistant",
                content=message_content,
                attributes={"tool_calls": tool_calls}
            )
            thread.add_message(message)
            new_messages.append(message)
        
        # Process tools and add results
        for tool_call in tool_calls:
            result = self._handle_tool_execution(tool_call)
            message = Message(
                role="function",
                content=result["content"],
                name=result["name"],
                attributes={
                    "tool_call_id": result["tool_call_id"],
                    "tool_name": result["name"]
                }
            )
            thread.add_message(message)
            new_messages.append(message)
        
        self.thread_store.save(thread)
        
        # Continue processing with tool results
        self.current_recursion_depth += 1
        return self.go(thread.id, new_messages)

    @weave.op()
    def _handle_tool_execution(self, tool_call) -> dict:
        """
        Execute a single tool call and format the result message
        
        Args:
            tool_call: The tool call object from the model response
            
        Returns:
            dict: Formatted tool result message
        """
        return tool_runner.execute_tool_call(tool_call) 