#!/usr/bin/env python3

from dotenv import load_dotenv
from tyler.models.agent import Agent, StreamUpdate
from tyler.models.thread import Thread
from tyler.models.message import Message
import asyncio
import weave
import os
import logging
import sys

# Load environment variables from .env file
load_dotenv()

# Configure logging based on LOG_LEVEL environment variable
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

# Set log level for all tyler loggers
for logger_name in ['tyler', 'tyler.models.agent', 'tyler.utils.tool_runner', '__main__']:
    logging.getLogger(logger_name).setLevel(log_level)

try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.info("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Initialize the agent with streaming enabled
agent = Agent(
    model_name="gpt-4o",  # Using latest GPT-4o model
    purpose="To be a helpful assistant that can answer questions and perform tasks.",
    tools=[
        "web",  # Enable web tools for fetching and processing web content
        "command_line"  # Enable command line tools for system operations
    ],
    temperature=0.7,  # Control randomness in responses
    stream=True  # Enable streaming responses
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