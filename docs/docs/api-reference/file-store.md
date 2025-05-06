---
sidebar_position: 5
---

# FileStore API

The `FileStore` class provides a unified interface for storing and retrieving files in Tyler. It handles file validation, storage, and retrieval, supporting local file system storage with configurable limits and security features.

## Initialization

### Factory Pattern

```python
from tyler import FileStore

# Create a FileStore instance with factory pattern
file_store = await FileStore.create(
    base_path="/path/to/files",
    max_file_size=100 * 1024 * 1024,  # 100MB
    max_storage_size=10 * 1024 * 1024 * 1024  # 10GB
)

# Or use default settings from environment variables
file_store = await FileStore.create()

# Pass the file_store to an Agent
from tyler import Agent

agent = Agent(
    model_name="gpt-4o",
    purpose="To help with tasks",
    thread_store=thread_store,
    file_store=file_store  # Explicitly pass file_store instance
)
```

The factory pattern immediately validates storage access, allowing your application to:
- Fail fast if storage isn't accessible
- Validate configuration at startup
- Ensure storage is ready for use

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `base_path` | str | No | TYLER_FILE_STORAGE_PATH or ~/.tyler/files | Base directory for file storage |
| `max_file_size` | int | No | 50MB | Maximum allowed file size in bytes |
| `max_storage_size` | int | No | 5GB | Maximum total storage size in bytes |
| `allowed_mime_types` | Set[str] | No | Common types | Set of allowed MIME types |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TYLER_FILE_STORAGE_PATH` | Base directory for file storage | ~/.tyler/files |
| `TYLER_MAX_FILE_SIZE` | Maximum allowed file size in bytes | 50MB |
| `TYLER_MAX_STORAGE_SIZE` | Maximum total storage size in bytes | 5GB |
| `TYLER_ALLOWED_MIME_TYPES` | Comma-separated list of allowed MIME types | Common types |

## Methods

### save

Save a file to storage.

```python
async def save(
    self,
    content: bytes,
    filename: str,
    mime_type: Optional[str] = None
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | bytes | Yes | - | File content as bytes |
| `filename` | str | Yes | - | Original filename |
| `mime_type` | Optional[str] | No | None | MIME type (auto-detected if not provided) |

#### Returns

```python
{
    "id": str,                 # Unique file ID
    "filename": str,           # Original filename
    "mime_type": str,          # Detected/validated MIME type
    "storage_path": str,       # Relative path in storage
    "storage_backend": str,    # Always "local" for FileStore
    "created_at": datetime,    # Creation timestamp
    "metadata": {
        "size": int            # File size in bytes
    }
}
```

#### Exceptions

- `UnsupportedFileTypeError`: If file type is not allowed
- `FileTooLargeError`: If file exceeds size limit
- `StorageFullError`: If storage capacity is exceeded

### get

Get file content from storage.

```python
async def get(
    self,
    file_id: str,
    storage_path: Optional[str] = None
) -> bytes
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_id` | str | Yes | - | Unique file ID |
| `storage_path` | Optional[str] | No | None | Storage path (preferred if available) |

#### Returns

File content as bytes.

#### Exceptions

- `FileNotFoundError`: If file cannot be found

### delete

Delete a file from storage.

```python
async def delete(
    self,
    file_id: str,
    storage_path: Optional[str] = None
) -> None
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_id` | str | Yes | - | Unique file ID |
| `storage_path` | Optional[str] | No | None | Storage path (preferred if available) |

#### Exceptions

- `FileNotFoundError`: If file cannot be found

### create

Factory method to create and validate a FileStore instance.

```python
@classmethod
async def create(
    cls,
    base_path: Optional[str] = None,
    max_file_size: Optional[int] = None,
    allowed_mime_types: Optional[Set[str]] = None,
    max_storage_size: Optional[int] = None
) -> FileStore
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `base_path` | Optional[str] | No | None | Base directory for file storage |
| `max_file_size` | Optional[int] | No | None | Maximum allowed file size in bytes |
| `allowed_mime_types` | Optional[Set[str]] | No | None | Set of allowed MIME types |
| `max_storage_size` | Optional[int] | No | None | Maximum total storage size in bytes |

#### Returns

Initialized FileStore instance.

#### Exceptions

- `FileStoreError`: If storage directory cannot be created or accessed

### validate_file

Validate file content and type.

```python
async def validate_file(
    self,
    content: bytes,
    filename: str,
    mime_type: Optional[str] = None
) -> str
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | bytes | Yes | - | File content as bytes |
| `filename` | str | Yes | - | Original filename |
| `mime_type` | Optional[str] | No | None | MIME type (auto-detected if not provided) |

#### Returns

Validated MIME type.

#### Exceptions

- `UnsupportedFileTypeError`: If file type is not allowed
- `FileTooLargeError`: If file exceeds size limit

### get_storage_size

Get total size of all files in storage.

```python
async def get_storage_size(self) -> int
```

#### Returns

Total size in bytes.

### get_file_count

Get total number of files in storage.

```python
async def get_file_count(self) -> int
```

#### Returns

Number of files.

### check_health

Check health of storage system.

```python
async def check_health(self) -> Dict[str, Any]
```

#### Returns

```python
{
    "status": str,             # "healthy" or "unhealthy"
    "storage_size": int,       # Total storage size in bytes
    "file_count": int,         # Number of files
    "available_space": int,    # Available space in bytes
    "max_storage_size": int,   # Maximum storage size in bytes
    "usage_percent": float     # Storage usage percentage
}
```

### batch_save

Save multiple files in a single operation.

```python
async def batch_save(
    self,
    files: List[Tuple[bytes, str, str]]
) -> List[Dict[str, Any]]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `files` | List[Tuple[bytes, str, str]] | Yes | - | List of (content, filename, mime_type) tuples |

#### Returns

List of metadata dictionaries (same format as `save`).

### batch_delete

Delete multiple files in a single operation.

```python
async def batch_delete(
    self,
    file_ids: List[str]
) -> None
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_ids` | List[str] | Yes | - | List of file IDs to delete |

### list_files

List all file IDs in storage.

```python
async def list_files(self) -> List[str]
```

#### Returns

List of file IDs.

## Class Methods

### get_file_url

Get the full URL for a file based on its relative path.

```python
@classmethod
def get_file_url(cls, relative_path: str) -> str
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `relative_path` | str | Yes | - | Path relative to the base storage path |

#### Returns

The full URL for the file.

### get_default_path

Get the default file storage path based on environment or defaults.

```python
@classmethod
def get_default_path(cls) -> Path
```

#### Returns

Path object for the default storage location.

### initialize_storage

Initialize the file storage directory.

```python
@classmethod
def initialize_storage(cls) -> Path
```

#### Returns

Path to the initialized storage directory.

## Integration with Attachment Model

The `FileStore` class works seamlessly with the `Attachment` model:

```python
from tyler import Attachment, FileStore

# Create a FileStore instance
file_store = await FileStore.create()

# Create an attachment
attachment = Attachment(
    filename="document.pdf",
    content=pdf_bytes,
    mime_type="application/pdf"
)

# Process and store the attachment with the file_store instance
await attachment.process_and_store(file_store)

# The attachment now has:
# - file_id: Unique identifier in the file store
# - storage_path: Path within the storage system
# - storage_backend: "local" for FileStore
# - status: "stored" if successful
# - attributes: Contains processed content and metadata

# The attributes field includes:
# - type: File type (e.g., "document", "image")
# - url: URL to access the file
# - Additional type-specific information (text extraction, image analysis, etc.)
```

### URL Generation

When an attachment is stored, the `FileStore.get_file_url()` method is used to generate a URL for the file:

```python
# In Attachment.update_attributes_with_url():
url = FileStore.get_file_url(self.storage_path)
self.attributes["url"] = url
```

This URL is then used in the `Message.to_chat_completion_message()` method to include file references in the message content.

## Exceptions

| Exception | Description |
|-----------|-------------|
| `FileStoreError` | Base exception for file store errors |
| `FileNotFoundError` | Raised when a file is not found in storage |
| `StorageFullError` | Raised when storage capacity is exceeded |
| `UnsupportedFileTypeError` | Raised when file type is not allowed |
| `FileTooLargeError` | Raised when file exceeds size limit |

## Best Practices

1. **Configuration**
   ```python
   # Use environment variables for configuration
   os.environ["TYLER_FILE_STORAGE_PATH"] = "/path/to/files"
   os.environ["TYLER_MAX_FILE_SIZE"] = "100000000"  # 100MB
   
   # Initialize once and reuse
   store = await FileStore.create()
   ```

2. **Error Handling**
   ```python
   try:
       result = await store.save(content, filename)
   except UnsupportedFileTypeError:
       print("File type not allowed")
   except FileTooLargeError:
       print("File too large")
   except StorageFullError:
       print("Storage full")
   ```

3. **Path Handling**
   ```python
   # Always use storage_path when available
   content = await store.get(file_id, storage_path)
   
   # Generate URLs using the class method
   url = FileStore.get_file_url(storage_path)
   ```

4. **Batch Operations**
   ```python
   # More efficient for multiple files
   results = await store.batch_save([
       (pdf_bytes, "doc1.pdf", "application/pdf"),
       (image_bytes, "image.jpg", "image/jpeg")
   ])
   ```

## See Also

- [Attachment API](./attachment.md)
- [Message API](./message.md)
- [File Storage Examples](../examples/file-storage.md)