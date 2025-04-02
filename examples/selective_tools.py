#!/usr/bin/env python3
"""
Example demonstrating the use of selective tools loading from built-in modules.
"""
# Load environment variables and configure logging first
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

# Now import everything else
import os
import asyncio
import weave
import sys
from tyler.models.agent import Agent
from tyler.models.thread import Thread, Message

# Initialize weave for tracing if configured
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Initialize an agent with selective tools from the notion module
# This agent can only search Notion but can't create/edit pages
agent = Agent(
    model_name="gpt-4o",
    purpose="To help with searching Notion without being able to modify anything",
    tools=[
        "notion:notion-search,notion-get_page",  # Only include search and get_page tools
        "web",  # Include all web tools
    ]
)

# For demonstration, let's display what tools were actually loaded
logger.info("Available tools:")
for tool_name in agent._processed_tools:
    logger.info(f"- {tool_name['function']['name']}")

async def main():
    # Create a thread
    thread = Thread()

    # Example conversation
    user_input = "What tools do you have available to interact with Notion? Can you create a new Notion page?"
    logger.info("User: %s", user_input)
    
    # Add user message
    message = Message(
        role="user",
        content=user_input
    )
    thread.add_message(message)

    # Process the thread
    processed_thread, new_messages = await agent.go(thread)

    # Log responses
    for message in new_messages:
        if message.role == "assistant":
            logger.info("Assistant: %s", message.content)
    
    logger.info("-" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0) 