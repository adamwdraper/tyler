#!/usr/bin/env python3
"""
Example demonstrating the use of the audio tools for text-to-speech and speech-to-text.
"""
# Load environment variables and configure logging first
from dotenv import load_dotenv
load_dotenv()

# Configure logging before other imports
from tyler.utils.logging import get_logger
logger = get_logger(__name__)

# Now import everything else
import os
import asyncio
import weave
import sys
import json
import base64
from pathlib import Path
from tyler import Agent, Thread, Message, ThreadStore

try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Create thread store (will initialize automatically when needed)
thread_store = ThreadStore()

async def init():
    # Initialize the agent with audio tools and thread store
    return Agent(
        model_name="gpt-4.1",
        purpose="To help convert text to speech and transcribe speech to text.",
        tools=["audio"],  # Load the audio tools module
        temperature=0.7,
        thread_store=thread_store  # Pass thread store to agent
    )

async def text_to_speech_example():
    """Example of text-to-speech conversion"""
    # Initialize agent with thread store
    agent = await init()
    
    # Create a thread
    thread = Thread()

    # Example text-to-speech request
    user_input = (
        "Please convert the following text to speech using the 'nova' voice: "
        "'Hello! This is a demonstration of the text-to-speech capability. "
        "I hope you find this useful for your applications.'"
    )

    logger.info("User: %s", user_input)
    
    # Add user message
    message = Message(
        role="user",
        content=user_input
    )
    thread.add_message(message)

    # Process the thread - agent will handle saving
    processed_thread, new_messages = await agent.go(thread)

    # Track the generated audio file details
    generated_audio = None

    # Log responses
    for message in new_messages:
        if message.role == "assistant":
            logger.info("Assistant: %s", message.content)
            if message.tool_calls:
                tool_calls_info = [{
                    "name": tc.get('function', {}).get('name'),
                    "arguments": tc.get('function', {}).get('arguments')
                } for tc in message.tool_calls]
                logger.info("Tool Calls: %s", tool_calls_info)
        elif message.role == "tool":
            try:
                content = json.loads(message.content)
                if content.get("success"):
                    logger.info("Tool (%s): Audio generated successfully", message.name)
                    logger.info("Description: %s", content.get("description"))
                    logger.info("Details: %s", content.get("details"))
                    
                    # Store the first audio attachment we find
                    if message.attachments and not generated_audio:
                        attachment = message.attachments[0]
                        generated_audio = attachment
                        logger.info("Generated audio file: %s (ID: %s)", attachment.filename, attachment.file_id)
                else:
                    logger.error("Tool (%s): Error - %s", message.name, content.get("error", "Unknown error"))
            except json.JSONDecodeError:
                logger.debug("Tool (%s): %s", message.name, message.content)
    
    logger.info("-" * 50)
    return generated_audio

async def speech_to_text_example(audio_attachment):
    """Example of speech-to-text transcription"""
    # Initialize agent with thread store
    agent = await init()
    
    # Create a thread
    thread = Thread()

    # Add user message with audio attachment
    message = Message(
        role="user",
        content="Please transcribe this audio file to text.",
        attachments=[audio_attachment]
    )
    thread.add_message(message)

    # Process the thread
    processed_thread, new_messages = await agent.go(thread)

    # Log responses
    for message in new_messages:
        if message.role == "assistant":
            logger.info("Assistant: %s", message.content)
            if message.tool_calls:
                tool_calls_info = [{
                    "name": tc.get('function', {}).get('name'),
                    "arguments": tc.get('function', {}).get('arguments')
                } for tc in message.tool_calls]
                logger.info("Tool Calls: %s", tool_calls_info)
        elif message.role == "tool":
            try:
                content = json.loads(message.content)
                if content.get("success"):
                    logger.info("Tool (%s): Transcription successful", message.name)
                    logger.info("Transcribed Text: %s", content.get("text"))
                    logger.info("Details: %s", content.get("details"))
                else:
                    logger.error("Tool (%s): Error - %s", message.name, content.get("error", "Unknown error"))
            except json.JSONDecodeError:
                logger.debug("Tool (%s): %s", message.name, message.content)
    
    logger.info("-" * 50)

async def main():
    try:
        # Run text-to-speech example
        logger.info("Running text-to-speech example...")
        audio_file = await text_to_speech_example()
        if not audio_file:
            logger.error("No audio file was generated")
            return
            
        # Run speech-to-text example
        logger.info("Running speech-to-text example...")
        await speech_to_text_example(audio_file)
    except Exception as e:
        logger.error(f"Error in examples: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0) 