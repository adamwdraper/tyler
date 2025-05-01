#!/usr/bin/env python3
"""
Example demonstrating the use of the image generation tool.
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
from tyler import Agent, Thread, Message, Attachment, ThreadStore

try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Create thread store (will initialize automatically when needed)
thread_store = ThreadStore()

async def init():
    # Initialize the agent with image tools and thread store
    return Agent(
        model_name="gpt-4o",
        purpose="To help create and generate images based on text descriptions.",
        tools=["image"],  # Load the image tools module
        temperature=0.7,
        thread_store=thread_store  # Pass thread store to agent
    )

async def main():
    # Initialize agent with thread store
    agent = await init()
    
    # Log available tools for debugging
    logger.debug(f"Agent initialized with tools: {[tool['function']['name'] for tool in agent._processed_tools]}")
    
    # Create first thread for image generation
    generation_thread = Thread()

    # Track the generated image path and content
    generated_image_path = None
    generated_image_content = None

    # Image generation request
    generation_prompt = (
        "Please generate a image in the style of a wood block print of a serene Japanese garden "
        "with a traditional wooden bridge over a koi pond, cherry blossoms in full bloom, "
        "and a small tea house in the background."
    )

    logger.info("User (Thread 1): %s", generation_prompt)
    
    # Add user message for generation
    message = Message(
        role="user",
        content=generation_prompt
    )
    generation_thread.add_message(message)

    # Process the generation thread
    processed_thread, new_messages = await agent.go(generation_thread)

    # Log responses and track generated image
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
                    logger.info("Tool (%s): Operation successful", message.name)
                    
                    if message.name == "image-generate":
                        logger.info("Description: %s", content.get("description"))
                        logger.info("Details: %s", content.get("details"))
                    
                    # Track generated image info
                    if message.attachments:
                        for attachment in message.attachments:
                            file_info = {
                                "filename": attachment.filename,
                                "mime_type": attachment.mime_type,
                                "file_id": attachment.file_id,
                                "storage_path": attachment.storage_path,
                                "description": attachment.processed_content.get("description") if attachment.processed_content else None
                            }
                            logger.info("File: %s", file_info)
                            
                            # Track the image path and get content for analysis
                            if message.name == "image-generate" and attachment.storage_path:
                                generated_image_path = attachment.storage_path
                                # Get the image content
                                generated_image_content = await attachment.get_content_bytes()
                else:
                    logger.error("Tool (%s): Error - %s", message.name, content.get("error", "Unknown error"))
            except json.JSONDecodeError:
                logger.debug("Tool (%s): %s", message.name, message.content)
    
    logger.info("-" * 50)

    # Create second thread for analysis if we have a generated image
    if generated_image_content and generated_image_path:
        analysis_thread = Thread()
        
        # Create attachment with proper storage path
        attachment = Attachment(
            filename=os.path.basename(generated_image_path),
            content=generated_image_content,
            storage_path=generated_image_path
        )
        
        # Create message with image attachment
        analysis_message = Message(
            role="user",
            content="Is there a bridge in this image?"
        )
        
        # Add the attachment to the message
        analysis_message.add_attachment(attachment)
        
        analysis_thread.add_message(analysis_message)
        
        logger.info("User (Thread 2): Analyzing image for bridge presence")
        
        # Process the analysis thread
        processed_thread, new_messages = await agent.go(analysis_thread)
        
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
                        logger.info("Tool (%s): Operation successful", message.name)
                        if message.name == "analyze-image":
                            logger.info("Analysis: %s", content.get("analysis"))
                    else:
                        logger.error("Tool (%s): Error - %s", message.name, content.get("error", "Unknown error"))
                except json.JSONDecodeError:
                    logger.debug("Tool (%s): %s", message.name, message.content)
        
        logger.info("-" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0) 