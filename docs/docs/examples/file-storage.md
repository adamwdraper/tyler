# File Storage Example

This example demonstrates how to use Tyler's file storage capabilities to save and retrieve files.

## Configuration

First, set up the file storage configuration:

```python
from tyler.storage import get_file_store, FileStore

# Get default file store
file_store = get_file_store()

# Or create with custom configuration
file_store = FileStore(
    base_path="/path/to/files",
    max_file_size=100 * 1024 * 1024,  # 100MB
    max_storage_size=10 * 1024 * 1024 * 1024,  # 10GB
    allowed_mime_types={"application/pdf", "image/jpeg", "text/plain"}
)
```

## Saving Files

```python
# Save a file
file_content = b"Hello, World!"
result = await file_store.save("example.txt", file_content)

print(f"File ID: {result['id']}")
print(f"Storage path: {result['storage_path']}")
print(f"MIME type: {result['mime_type']}")
```

## Retrieving Files

```python
# Get file content using ID and storage path
file_id = result['id']
storage_path = result['storage_path']
content = await file_store.get(file_id, storage_path)

print(f"Content: {content.decode('utf-8')}")
```

## Deleting Files

```python
# Delete a file
await file_store.delete(file_id, storage_path)
```

## Working with Attachments

The FileStore integrates seamlessly with the Attachment model:

```python
from tyler.models.attachment import Attachment
from tyler.models.message import Message
from tyler.models.thread import Thread
from tyler.database.thread_store import ThreadStore

# Create an attachment
attachment = Attachment(
    filename="document.pdf",
    content=pdf_bytes,
    mime_type="application/pdf"
)

# Process and store the attachment directly
await attachment.process_and_store()

# Check the results
print(f"File ID: {attachment.file_id}")
print(f"Storage path: {attachment.storage_path}")
print(f"Status: {attachment.status}")
print(f"URL: {attachment.attributes.get('url')}")

# Or use with messages and threads (recommended approach)
message = Message(role="user", content="Here's a document")
message.add_attachment(pdf_bytes, filename="document.pdf")

thread = Thread()
thread.add_message(message)

thread_store = ThreadStore()
await thread_store.initialize()
await thread_store.save(thread)  # Automatically processes and stores attachments

# Access attachment information
for attachment in message.attachments:
    if attachment.status == "stored":
        print(f"File ID: {attachment.file_id}")
        print(f"Storage path: {attachment.storage_path}")
        print(f"URL: {attachment.attributes.get('url')}")
        
        # Access file-specific attributes
        file_type = attachment.attributes.get("type")
        if file_type == "document":
            print(f"Extracted text: {attachment.attributes.get('text')}")
        elif file_type == "image":
            print(f"Image description: {attachment.attributes.get('overview')}")
```

## Batch Operations

```python
# Save multiple files at once
files = [
    (b"File 1 content", "file1.txt", "text/plain"),
    (b"File 2 content", "file2.txt", "text/plain")
]
results = await file_store.batch_save(files)

# Delete multiple files
file_ids = [result["id"] for result in results]
await file_store.batch_delete(file_ids)
```

## Storage Management

```python
# Check storage health
health = await file_store.check_health()
print(f"Status: {health['status']}")
print(f"Storage size: {health['storage_size']} bytes")
print(f"File count: {health['file_count']}")
print(f"Usage: {health['usage_percent']}%")

# Get storage size
size = await file_store.get_storage_size()
print(f"Total storage size: {size} bytes")

# Get file count
count = await file_store.get_file_count()
print(f"Total files: {count}")
```

## URL Generation

```python
# Generate URL for a file
from tyler.storage import FileStore

storage_path = "ab/cdef1234.pdf"  # Example storage path
url = FileStore.get_file_url(storage_path)
print(f"File URL: {url}")
```

## Error Handling

```python
from tyler.storage import (
    FileStoreError,
    FileNotFoundError,
    StorageFullError,
    UnsupportedFileTypeError,
    FileTooLargeError
)

try:
    # Try to save a file
    result = await file_store.save(large_content, "large_file.bin")
except UnsupportedFileTypeError:
    print("File type not allowed")
except FileTooLargeError:
    print("File too large")
except StorageFullError:
    print("Storage full")
except FileStoreError as e:
    print(f"General storage error: {e}")
```

## Complete Example

```python
import asyncio
from tyler.storage import get_file_store

async def main():
    # Initialize file store
    file_store = get_file_store()
    
    # Save a file
    content = b"Hello, World!"
    result = await file_store.save(content, "example.txt")
    print(f"Saved file: {result['filename']}")
    print(f"Storage path: {result['storage_path']}")
    
    # Retrieve the file
    retrieved = await file_store.get(result['id'], result['storage_path'])
    print(f"Retrieved content: {retrieved.decode('utf-8')}")
    
    # Delete the file
    await file_store.delete(result['id'], result['storage_path'])
    print("File deleted")
    
    # Check storage health
    health = await file_store.check_health()
    print(f"Storage health: {health['status']}")
    print(f"Storage usage: {health['usage_percent']}%")

if __name__ == "__main__":
    asyncio.run(main())
``` 