# Streaming Responses

Tyler supports streaming responses from the agent, allowing you to build highly interactive applications that show responses in real-time. This example demonstrates how to use streaming with both basic responses and tool execution.

## Basic Streaming Example

Here's a complete example that shows how to use streaming responses with multiple conversation turns:

```python
from dotenv import load_dotenv
from tyler.models.agent import Agent, StreamUpdate, Thread, Message
import asyncio
import weave
import os
import logging
import sys

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.info("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Initialize the agent
agent = Agent(
    model_name="gpt-4.1",  # Using latest GPT-4.1 model
    purpose="To be a helpful assistant that can answer questions and perform tasks.",
    tools=[
        "web",  # Enable web tools for fetching and processing web content
        "command_line"  # Enable command line tools for system operations
    ],
    temperature=0.7
)

async def main():
    # Example conversation with multiple turns
    conversations = [
        "Tell me about the benefits of exercise.",
        "What specific exercises are good for beginners?",
        "How often should beginners exercise?"
    ]

    # Create a single thread for the entire conversation
    thread = Thread()

    for user_input in conversations:
        print(f"\nUser: {user_input}")
        
        # Add user message to thread
        message = Message(
            role="user",
            content=user_input
        )
        thread.add_message(message)

        print("\nAssistant: ", end='', flush=True)

        # Process the thread using go_stream
        async for update in agent.go_stream(thread):
            if update.type == StreamUpdate.Type.CONTENT_CHUNK:
                # Print content chunks as they arrive
                print(update.data, end='', flush=True)
            elif update.type == StreamUpdate.Type.TOOL_MESSAGE:
                # Print tool results on new lines
                tool_message = update.data
                print(f"\nTool ({tool_message.name}): {tool_message.content}")
            elif update.type == StreamUpdate.Type.ERROR:
                # Print any errors that occur
                print(f"\nError: {update.data}")
            elif update.type == StreamUpdate.Type.COMPLETE:
                # Final update contains (thread, new_messages)
                print()  # Add newline after completion
        
        print("\n" + "-"*50)  # Separator between conversations

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        sys.exit(0)

## How It Works

1. **Environment Setup**:
   - Loads environment variables from `.env`
   - Initializes Weave tracing if configured
   - Sets up logging

2. **Agent Configuration**:
   - Uses the latest GPT-4.1 model
   - Enables web and command line tools
   - Sets a specific purpose and temperature

3. **Conversation Management**:
   - Creates a single thread for the entire conversation
   - Handles multiple conversation turns
   - Maintains context between messages

4. **Streaming Updates**:
   - Processes content chunks in real-time
   - Handles tool execution results
   - Manages errors and completion states

## Best Practices

1. **Environment Management**:
   - Use `.env` for configuration
   - Handle missing environment variables gracefully
   - Set up proper logging

2. **Error Handling**:
   - Catch and log initialization errors
   - Handle streaming errors appropriately
   - Provide graceful shutdown

3. **User Experience**:
   - Show clear user/assistant separation
   - Use proper output formatting
   - Maintain conversation context

4. **Tool Integration**:
   - Enable relevant tools for the use case
   - Handle tool results appropriately
   - Display tool output clearly

## Running the Example

1. Install Tyler and dependencies:
```bash
uv add tyler-agent
```

2. Set up your environment variables in `.env`:
```bash
OPENAI_API_KEY=your_api_key_here
WANDB_API_KEY=your_wandb_key_here  # Optional, for tracing
```

3. Run the example:
```bash
python examples/streaming.py
```

## Expected Output

```
User: Tell me about the benefits of exercise. 