#!/usr/bin/env python3
"""
Example demonstrating the use of the files tool for PDF processing.

This script:
1. Initializes an agent with the files tools
2. Processes a sample PDF file and demonstrates text extraction
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
from pathlib import Path
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
    # Initialize the agent with files tools and thread store
    agent = Agent(
        model_name="gpt-4o",
        purpose="To help extract and analyze content from PDF files.",
        tools=["files"],  # Use the files module
        temperature=0.7,
        thread_store=thread_store  # Thread store will initialize automatically when needed
    )
    
    # Detailed debugging of tools
    if hasattr(agent, '_processed_tools'):
        tools = agent._processed_tools
        logger.info(f"Number of tools loaded: {len(tools)}")
        for tool in tools:
            logger.info(f"Tool: {tool['function']['name']}")
            logger.info(f"Description: {tool['function'].get('description', 'No description')}")
    else:
        logger.error("No _processed_tools found on agent")
        
    # Also check the raw tools list
    from tyler.tools import FILES_TOOLS
    logger.info(f"FILES_TOOLS contains {len(FILES_TOOLS)} tools")
    for tool in FILES_TOOLS:
        logger.info(f"Found tool definition: {tool['definition']['function']['name']}")
    
    return agent

async def main():
    """Run the example."""
    # Create agent with file tools
    agent = await init()
    
    # Create a thread
    thread = Thread()
    
    # Add a user message
    message = Message(
        role="user",
        content="Can you help me create a file with some sample text?"
    )
    thread.add_message(message)
    
    # Process the thread
    processed_thread, new_messages = await agent.go(thread)

    # Log available tools for debugging
    if hasattr(agent, '_processed_tools'):
        logger.debug(f"Agent initialized with tools: {[tool['function']['name'] for tool in agent._processed_tools]}")
    else:
        logger.warning("Agent does not have processed tools attribute. This may indicate an initialization issue.")
    
    # Use the specified sample PDF - path relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(script_dir, "assets", "sample_pdf.pdf")
    
    # Ensure the file exists
    if not os.path.exists(pdf_path):
        logger.error(f"Sample PDF file not found at {pdf_path}")
        sys.exit(1)
    
    logger.info(f"Using sample PDF file: {pdf_path}")

    # Read the PDF file
    with open(pdf_path, 'rb') as f:
        pdf_content = f.read()

    # Example PDF processing requests
    conversations = [
        "Please analyze this PDF document and give me a summary of its contents.",
        "What are the main topics or sections in this document?"
    ]

    for i, user_input in enumerate(conversations):
        logger.info("User: %s", user_input)
        
        # Create message with attachment for the first message only
        message = Message(
            role="user",
            content=user_input
        )
        
        # Add PDF attachment to first message only
        if i == 0:
            attachment = Attachment(
                filename="sample.pdf",
                content=pdf_content,
                mime_type="application/pdf"
            )
            message.add_attachment(attachment)
            logger.info("Added PDF attachment to first message")

        thread.add_message(message)

        # Process the thread - agent will handle saving
        processed_thread, new_messages = await agent.go(thread)

        # Log responses
        for message in new_messages:
            if message.role == "assistant":
                logger.info("Assistant: %s", message.content)
                if message.tool_calls:
                    # Only log tool call metadata, not the full content
                    tool_calls_info = [{
                        "name": tc.get('function', {}).get('name'),
                        "arguments": tc.get('function', {}).get('arguments')
                    } for tc in message.tool_calls]
                    logger.info("Tool Calls: %s", tool_calls_info)
            elif message.role == "tool":
                try:
                    # Parse the content as JSON since it's now serialized
                    content = json.loads(message.content)
                    # Handle tuple structure (metadata, files)
                    if isinstance(content, list) and len(content) == 2:
                        metadata, files = content
                        if metadata.get("success"):
                            logger.info("Tool (%s): Operation successful", message.name)
                            if metadata.get("type") == "pdf":
                                logger.info("Pages: %s", metadata.get("pages", "Unknown"))
                                # Show sample of text if available
                                text = metadata.get("text", "")
                                sample_text = text[:200] + "..." if len(text) > 200 else text
                                logger.info("Sample text: %s", sample_text)
                            
                            if files:
                                logger.info("Generated files: %s", [f.get("filename") for f in files])
                        else:
                            logger.error("Tool (%s): Error - %s", message.name, metadata.get("error", "Unknown error"))
                    else:
                        logger.info("Tool (%s): %s", message.name, content)
                except json.JSONDecodeError:
                    # Handle legacy format or non-JSON content
                    logger.debug("Tool (%s): %s", message.name, message.content)
        
        logger.info("-" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0) 