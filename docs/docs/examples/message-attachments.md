---
sidebar_position: 7
---

# Message Attachments

This example demonstrates how to work with file attachments in Tyler messages, including adding files, automatic processing, and storage management.

## Overview

The example shows:
- Adding attachments to messages
- Automatic file processing and storage
- File store configuration
- Working with different file types
- Handling multiple attachments
- Accessing stored files via URLs

## Code

```python
from dotenv import load_dotenv
from tyler import Agent, Thread, Message, Attachment, ThreadStore
import asyncio
import os
import weave

# Load environment variables from .env file
load_dotenv()

# Initialize weave for tracing (optional)
if os.getenv("WANDB_API_KEY"):
    weave.init("tyler")

async def example_basic_attachment():
    """
    Demonstrates basic attachment functionality with different file types.
    """
    print("\n=== Basic Attachment Example ===")
    
    # Create thread store (will initialize automatically when needed)
    thread_store = ThreadStore()
    
    # Create agent with thread store
    agent = Agent(
        model_name="gpt-4o",
        purpose="To help analyze documents",
        thread_store=thread_store
    )
    
    # Create thread with PDF attachment
    thread = Thread()
    message = Message(role="user", content="Can you analyze these files?")
    
    # Add a PDF using add_attachment with bytes
    pdf_content = b"This is example PDF content for testing attachments."
    message.add_attachment(pdf_content, filename="document.pdf")
    
    # Add a text file using Attachment object
    text_attachment = Attachment(
        filename="notes.txt",
        content=b"Important meeting notes:\n1. Review project timeline\n2. Update documentation",
        mime_type="text/plain"
    )
    message.add_attachment(text_attachment)
    
    # Add message to thread
    thread.add_message(message)
    
    # Save thread - attachments are automatically processed and stored
    await thread_store.save(thread)
    
    # Process thread - files will be automatically processed
    processed_thread, new_messages = await agent.go(thread)
    
    print("\nAssistant's response:")
    for message in new_messages:
        if message.role == "assistant":
            print(message.content)

async def example_multiple_attachments():
    """
    Demonstrates handling multiple attachments in a single message.
    """
    print("\n=== Multiple Attachments Example ===")
    
    # Create thread store (will initialize automatically when needed)
    thread_store = ThreadStore()
    
    agent = Agent(
        model_name="gpt-4o",
        thread_store=thread_store
    )
    
    thread = Thread()
    message = Message(
        role="user",
        content="Please analyze these reports"
    )
    
    # Add multiple files using add_attachment
    files = [
        ("report.txt", b"Q1 sales increased by 15%"),
        ("data.json", b'{"customer_satisfaction": 4.5}'),
        ("notes.md", b"# Project Updates\n- Timeline on track\n- Budget approved")
    ]
    
    for filename, content in files:
        message.add_attachment(content, filename=filename)
    
    # Add message to thread
    thread.add_message(message)
    
    # Save thread - all attachments are automatically processed and stored
    await thread_store.save(thread)
    
    # Process thread with multiple attachments
    processed_thread, new_messages = await agent.go(thread)
    
    print("\nAssistant's response:")
    for message in new_messages:
        if message.role == "assistant":
            print(message.content)
            # Access processed content for each attachment
            if message.attachments:
                for attachment in message.attachments:
                    if attachment.attributes:
                        print(f"\nProcessed content for {attachment.filename}:")
                        print(attachment.attributes)

async def example_attachment_processing():
    """
    Demonstrates attachment processing and storage.
    """
    print("\n=== Attachment Processing Example ===")
    
    # Create thread store (will initialize automatically when needed)
    thread_store = ThreadStore()
    
    agent = Agent(
        model_name="gpt-4o",
        thread_store=thread_store
    )

async def image_attachment_example():
    """
    Demonstrates image attachment functionality with vision model.
    """
    print("\n=== Image Attachment Example ===")
    
    # Create thread store (will initialize automatically when needed)
    thread_store = ThreadStore()
    
    # Create agent with thread store and vision capability
    agent = Agent(
        model_name="gpt-4o",
        purpose="To analyze images",
        thread_store=thread_store
    )
    
    # Create a message with an image attachment
    message = Message(
        role="user",
        content="What's in this image?"
    )
    
    # Add an image using add_attachment
    with open("example.jpg", "rb") as f:
        image_bytes = f.read()
    message.add_attachment(image_bytes, filename="example.jpg")
    
    # Add message to thread
    thread = Thread()
    thread.add_message(message)
    
    # Save thread - image attachment is automatically processed and stored
    await thread_store.save(thread)
    
    # Process thread - image will be automatically analyzed
    processed_thread, new_messages = await agent.go(thread)
    
    print("\nAssistant's response (with image analysis):")
    for message in new_messages:
        if message.role == "assistant":
            print(message.content)
            # Access image analysis results
            if message.attachments:
                for attachment in message.attachments:
                    if attachment.attributes:
                        print(f"\nImage analysis for {attachment.filename}:")
                        print(attachment.attributes)

async def audio_attachment_example():
    """
    Demonstrates audio attachment functionality.
    """
    print("\n=== Audio Attachment Example ===")
    
    # Create thread store (will initialize automatically when needed)
    thread_store = ThreadStore()
    
    # Create agent with thread store
    agent = Agent(
        model_name="gpt-4o",
        purpose="To transcribe and analyze audio",
        thread_store=thread_store
    )
    
    # Create a message with an audio attachment
    message = Message(
        role="user",
        content="Please transcribe this audio"
    )
    
    # Add an audio file using add_attachment
    with open("example.wav", "rb") as f:
        audio_bytes = f.read()
    message.add_attachment(audio_bytes, filename="example.wav")
    
    # Add message to thread
    thread = Thread()
    thread.add_message(message)
    
    # Save thread - audio attachment is automatically processed and stored
    await thread_store.save(thread)
    
    # Process thread - audio will be automatically transcribed
    processed_thread, new_messages = await agent.go(thread)
    
    print("\nAssistant's response (with audio transcription):")
    for message in new_messages:
        if message.role == "assistant":
            print(message.content)
            # Access audio transcription results
            if message.attachments:
                for attachment in message.attachments:
                    if attachment.attributes:
                        print(f"\nAudio transcription for {attachment.filename}:")
                        print(attachment.attributes)

async def main():
    # Run all examples
    await example_basic_attachment()
    await example_multiple_attachments()
    await example_attachment_processing()
    await image_attachment_example()
    await audio_attachment_example()

if __name__ == "__main__":
    asyncio.run(main())
```

## Examples

### 1. Basic Attachment
```python
# Add attachment using bytes
message.add_attachment(pdf_bytes, filename="document.pdf")

# Add attachment using Attachment object
attachment = Attachment(
    filename="data.json",
    content=json_bytes,
    mime_type="application/json"
)
message.add_attachment(attachment)

# Add message to thread
thread.add_message(message)

# Save thread - attachments are automatically processed and stored
await thread_store.save(thread)
```
Demonstrates:
- Adding single files
- Using different methods
- Automatic storage and processing
- Thread store integration

### 2. Multiple Attachments
```python
# Add multiple files
files = [
    ("report.txt", b"Report content"),
    ("data.json", b'{"data": "value"}')
]

for filename, content in files:
    message.add_attachment(content, filename=filename)

# Add message to thread
thread.add_message(message)

# Save thread - all attachments are automatically processed and stored
await thread_store.save(thread)

# Access processed content
for attachment in message.attachments:
    if attachment.attributes:
        print(f"File URL: {attachment.attributes.get('url')}")
        print(f"Content: {attachment.attributes}")
```
Shows how to:
- Add multiple files
- Store efficiently
- Access processed content
- Get file URLs

### 3. Image Attachment
```python
# Image attachment with automatic analysis
message.add_attachment(image_bytes, filename="photo.jpg")

# Add message to thread
thread.add_message(message)

# Save thread - image attachment is automatically processed and stored
await thread_store.save(thread)

# Access processed content
for attachment in message.attachments:
    if attachment.attributes:
        print(f"Storage path: {attachment.storage_path}")
        print(f"File URL: {attachment.attributes.get('url')}")
        print(f"Analysis: {attachment.attributes}")
```
Features:
- Automatic processing
- Content extraction
- Image analysis
- Storage management
- URL generation

### 4. Audio Attachment
```python
# Audio attachment with automatic transcription
message.add_attachment(audio_bytes, filename="audio.wav")

# Add message to thread
thread.add_message(message)

# Save thread - audio attachment is automatically processed and stored
await thread_store.save(thread)

# Access processed content
for attachment in message.attachments:
    if attachment.attributes:
        print(f"Storage path: {attachment.storage_path}")
        print(f"File URL: {attachment.attributes.get('url')}")
        print(f"Transcription: {attachment.attributes}")
```
Features:
- Automatic transcription
- Content extraction
- Storage management
- URL generation

## Configuration

### Environment Variables
```bash
# File Storage Configuration
TYLER_FILE_STORAGE_TYPE=local  # or 's3', etc.
TYLER_FILE_STORAGE_PATH=/path/to/files  # for local storage
```

### Storage Types

#### Local Storage (Default)
```python
from tyler.storage import get_file_store

# Get the default file store
store = get_file_store()

# Or configure with custom path
from tyler.storage import init_file_store
init_file_store('local', base_path='/path/to/files')
```

## Processed Content Structure

Attachments include attributes based on file type:

### Document Files
```python
{
    "type": "document",
    "text": "Extracted text content",
    "overview": "Brief summary",
    "url": "/files/path/to/file.pdf"
}
```

### Image Files
```python
{
    "type": "image",
    "text": "OCR extracted text (if applicable)",
    "overview": "Description of image contents",
    "analysis": {
        "objects": ["person", "desk", "computer"],
        "text_detected": True,
        "dominant_colors": ["blue", "white"]
    },
    "url": "/files/path/to/image.jpg"
}
```

### JSON Files
```python
{
    "type": "json",
    "overview": "JSON data structure description",
    "parsed_content": {"key": "value"},
    "url": "/files/path/to/data.json"
}
```

## Best Practices

1. **Storage Management**
   - Add attachments to messages, add messages to threads, then save the thread
   - Use appropriate file types and extensions
   - Monitor storage usage
   - Clean up unused files

2. **Content Processing**
   - Let automatic processing handle file analysis
   - Check attributes for extracted information
   - Use URLs for file access
   - Handle large files appropriately

3. **Error Handling**
   ```python
   try:
       await thread_store.save(thread)
   except RuntimeError as e:
       print(f"Failed to store attachments: {e}")
   ```

4. **Performance**
   - Add multiple attachments before saving the thread
   - Use appropriate file formats
   - Monitor processing time
   - Cache processed results

## See Also

- [File Storage](./file-storage.md) - Detailed file storage configuration
- [Database Storage](./database-storage.md) - Persistent thread storage
- [Full Configuration](./full-configuration.md) - Complete agent setup 