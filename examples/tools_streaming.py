#!/usr/bin/env python3

import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

print("DEBUG: Environment check:")
print(f"DEBUG: LOG_LEVEL from env: {os.getenv('LOG_LEVEL')}")
print(f"DEBUG: Current working directory: {os.getcwd()}")

# Configure logging before any other imports
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Force reconfiguration of the root logger
)

# Set root logger level
root_logger = logging.getLogger()
root_logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

from tyler.models.agent import Agent
from tyler.models.thread import Thread
from tyler.models.message import Message
import asyncio
import weave
import sys

logger = logging.getLogger(__name__)

logger.debug("Starting tools_streaming.py with debug logging enabled")
logger.debug(f"Current LOG_LEVEL: {os.getenv('LOG_LEVEL')}")

try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.info("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

def custom_weather_implementation(city: str) -> str:
    """
    Implementation of a mock weather tool.
    In a real application, this would retrieve live weather data.
    """
    
    logger.debug(f"Weather tool called with city: {city}")
    
    try:
        if not isinstance(city, str):
            logger.error(f"Invalid city type: {type(city)}")
            raise ValueError(f"city must be a string, got {type(city)}")
        
        # Log the city string after any potential whitespace stripping
        city = city.strip()
        logger.debug(f"Processed city parameter: {city}")
            
        if city.lower() == "phoenix":
            return "The weather in Phoenix is sunny, 95°F, with a light breeze."
        else:
            raise ValueError(f"Weather data for {city} is not available.")
    except Exception as e:
        logger.error(f"Error in weather tool: {str(e)}")
        raise  # Re-raise the error to ensure it's handled as a tool error

# Define custom weather tool
custom_weather_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather information for a given city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Name of the city for which to fetch the weather"
                    }
                },
                "required": ["city"]
            }
        }
    },
    "implementation": custom_weather_implementation,
    "attributes": {
        "category": "weather",
        "version": "1.0"
    }
}

# Initialize the agent with streaming enabled
agent = Agent(
    model_name="gpt-4o",
    purpose="To help with weather queries and web searches",
    tools=[
        "web",                     # Load the web tools module
        custom_weather_tool,         # Add our weather tool
    ],
    temperature=0.7,
    stream=True  # Enable streaming responses
)

async def main():
    # Example conversation with a question that can be answered without a tool, and one that requires the weather tool
    conversations = [
        "How do you say 'hello' in Spanish?",
        "What's the current weather in Phoenix?"
    ]

    # Create a new thread for
    thread = Thread()

    for user_input in conversations:
        print(f"\nUser: {user_input}")

        message = Message(role="user", content=user_input)
        thread.add_message(message)

        # Process the thread using the agent's go() method so that it aggregates the response
        thread, new_messages = await agent.go(thread)

        # Print the new messages aggregated by the agent
        for msg in new_messages:
            if msg.role == "assistant":
                print(f"\nAssistant: {msg.content}")
            elif msg.role == "tool":
                print(f"\nTool ({msg.name}): {msg.content}")
        print("\n" + "-" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        sys.exit(0) 