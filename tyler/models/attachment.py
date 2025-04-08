from typing import Dict, Optional, Any, Union, Literal
from pydantic import BaseModel
import base64
import io
import magic
from tyler.utils.logging import get_logger
from pathlib import Path
from tyler.storage.file_store import FileStore

# Get configured logger
logger = get_logger(__name__)

class Attachment(BaseModel):
    """Represents a file attached to a message"""
    filename: str
    content: Optional[Union[bytes, str]] = None  # Can be either bytes or base64 string
    mime_type: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None  # Renamed from processed_content
    file_id: Optional[str] = None  # Reference to stored file
    storage_path: Optional[str] = None  # Path in storage backend
    storage_backend: Optional[str] = None  # Storage backend type
    status: Literal["pending", "stored", "failed"] = "pending"

    def model_dump(self, mode: str = "json") -> Dict[str, Any]:
        """Convert attachment to a dictionary suitable for JSON serialization
        
        Args:
            mode: Serialization mode, either "json" or "python". 
                 "json" converts datetimes to ISO strings (default).
                 "python" keeps datetimes as datetime objects.
        """
        data = {
            "filename": self.filename,
            "mime_type": self.mime_type,
            "attributes": self.attributes,  # Renamed from processed_content
            "file_id": self.file_id,
            "storage_path": self.storage_path,
            "storage_backend": self.storage_backend,
            "status": self.status
        }
        
        # Only include content if no file_id (backwards compatibility)
        if not self.file_id and self.content is not None:
            # Convert bytes to base64 string for JSON serialization
            if isinstance(self.content, bytes):
                data["content"] = base64.b64encode(self.content).decode('utf-8')
            else:
                data["content"] = self.content
                
        return data
        
    async def get_content_bytes(self, file_store: Optional[FileStore] = None) -> bytes:
        """Get the content as bytes, converting from base64 if necessary
        
        If file_id is present, retrieves content from file storage.
        Otherwise falls back to content field.
        
        Args:
            file_store: Optional FileStore instance to use for retrieving file content.
                       If not provided, the content must be available in the attachment.
        """
        logger.debug(f"Getting content bytes for {self.filename}")
        
        if self.file_id:
            logger.debug(f"Retrieving content from file store for file_id: {self.file_id}")
            if file_store is None:
                raise ValueError("FileStore instance required to retrieve content for file_id")
            return await file_store.get(self.file_id, storage_path=self.storage_path)
            
        if isinstance(self.content, bytes):
            logger.debug(f"Content is already in bytes format for {self.filename}")
            return self.content
        elif isinstance(self.content, str):
            logger.debug(f"Converting string content for {self.filename}")
            if self.content.startswith('data:'):
                # Handle data URLs
                logger.debug("Detected data URL format")
                header, encoded = self.content.split(",", 1)
                logger.debug(f"Data URL header: {header}")
                try:
                    decoded = base64.b64decode(encoded)
                    logger.debug(f"Successfully decoded data URL content, size: {len(decoded)} bytes")
                    return decoded
                except Exception as e:
                    logger.error(f"Failed to decode data URL content: {e}")
                    raise
            else:
                try:
                    # Try base64 decode
                    logger.debug("Attempting base64 decode")
                    decoded = base64.b64decode(self.content)
                    logger.debug(f"Successfully decoded base64 content, size: {len(decoded)} bytes")
                    return decoded
                except:
                    logger.debug("Not base64, treating as UTF-8 text")
                    # If not base64, try encoding as UTF-8
                    return self.content.encode('utf-8')
                
        raise ValueError("No content available - attachment has neither file_id nor content")

    def update_attributes_with_url(self) -> None:
        """Update attributes with URL after storage_path is set."""
        if self.storage_path:
            if not self.attributes:
                self.attributes = {}
            
            try:
                # Get the file URL from FileStore
                from tyler.storage.file_store import FileStore
                self.attributes["url"] = FileStore.get_file_url(self.storage_path)
                logger.debug(f"Updated attributes with URL: {self.attributes['url']}")
            except Exception as e:
                # Log the error but don't fail - the URL will be missing but that's better than crashing
                logger.error(f"Failed to construct URL for attachment: {e}")
                self.attributes["error"] = f"Failed to construct URL: {str(e)}"

    async def process_and_store(self, file_store: FileStore, force: bool = False) -> None:
        """Process the attachment content and store it in the file store.
        
        Args:
            file_store: FileStore instance to use for storing files
            force: Whether to force processing even if already stored
        """
        logger.debug(f"Starting process_and_store for {self.filename} (force={force})")
        logger.debug(f"Initial state - mime_type: {self.mime_type}, status: {self.status}, content type: {type(self.content)}")
        
        if not force and self.status == "stored":
            logger.info(f"Skipping process_and_store for {self.filename} - already stored")
            return

        if self.content is None:
            logger.error(f"Cannot process attachment {self.filename}: no content provided")
            self.status = "failed"
            raise RuntimeError(f"Cannot process attachment {self.filename}: no content provided")

        try:
            # Get content as bytes first
            logger.debug("Converting content to bytes")
            content_bytes = await self.get_content_bytes(file_store=file_store)
            logger.debug(f"Successfully converted content to bytes, size: {len(content_bytes)} bytes")

            # Detect/verify MIME type
            logger.debug("Detecting MIME type")
            detected_mime_type = magic.from_buffer(content_bytes, mime=True)
            logger.debug(f"Detected MIME type: {detected_mime_type}")
            
            if not self.mime_type:
                self.mime_type = detected_mime_type
                logger.debug(f"Set MIME type to detected type: {self.mime_type}")
            elif self.mime_type != detected_mime_type:
                logger.warning(f"Provided MIME type {self.mime_type} doesn't match detected type {detected_mime_type}")

            # Initialize attributes
            if not self.attributes:
                self.attributes = {}

            # Process content based on MIME type
            logger.debug(f"Processing content based on MIME type: {self.mime_type}")
            
            if self.mime_type.startswith('image/'):
                logger.debug("Processing as image")
                self.attributes.update({
                    "type": "image",
                    "description": f"Image file {self.filename}",
                    "mime_type": self.mime_type
                })

            elif self.mime_type.startswith('audio/'):
                logger.debug("Processing as audio")
                self.attributes.update({
                    "type": "audio",
                    "description": f"Audio file {self.filename}",
                    "mime_type": self.mime_type
                })

            elif self.mime_type == 'application/pdf':
                logger.debug("Processing as PDF")
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(content_bytes))
                text = ""
                for page in reader.pages:
                    try:
                        extracted = page.extract_text()
                        if extracted:
                            text += extracted + "\n"
                    except Exception as e:
                        logger.warning(f"Error extracting text from PDF page: {e}")
                        continue
                self.attributes.update({
                    "type": "document",
                    "text": text.strip(),
                    "overview": f"Extracted text from {self.filename}",
                    "mime_type": self.mime_type
                })

            elif self.mime_type.startswith('text/'):
                logger.debug("Processing as text")
                try:
                    text = content_bytes.decode('utf-8')
                    self.attributes.update({
                        "type": "text",
                        "text": text[:500],  # First 500 chars as preview
                        "mime_type": self.mime_type
                    })
                except UnicodeDecodeError:
                    logger.warning("UTF-8 decode failed, trying alternative encodings")
                    # Try alternative encodings
                    for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                        try:
                            text = content_bytes.decode(encoding)
                            self.attributes.update({
                                "type": "text",
                                "text": text[:500],
                                "encoding": encoding,
                                "mime_type": self.mime_type
                            })
                            logger.debug(f"Successfully decoded text using {encoding}")
                            break
                        except UnicodeDecodeError:
                            continue

            elif self.mime_type == 'application/json':
                logger.debug("Processing as JSON")
                import json
                try:
                    json_text = content_bytes.decode('utf-8')
                    json_data = json.loads(json_text)
                    self.attributes.update({
                        "type": "json",
                        "overview": "JSON data structure",
                        "parsed_content": json_data,
                        "mime_type": self.mime_type
                    })
                except Exception as e:
                    logger.warning(f"Error parsing JSON content: {e}")
                    self.attributes.update({
                        "type": "json",
                        "error": f"Failed to parse JSON: {str(e)}",
                        "mime_type": self.mime_type
                    })

            else:
                logger.debug(f"Processing as binary file with MIME type: {self.mime_type}")
                self.attributes.update({
                    "type": "binary",
                    "description": f"Binary file {self.filename}",
                    "mime_type": self.mime_type
                })

            # Store the file
            logger.debug("Storing file in FileStore")
            
            try:
                logger.debug(f"Saving file to storage, content size: {len(content_bytes)} bytes")
                result = await file_store.save(content_bytes, self.filename, self.mime_type)
                logger.debug(f"Successfully saved file. Result: {result}")
                
                self.file_id = result['id']
                self.storage_backend = result['storage_backend']
                self.storage_path = result['storage_path']
                self.status = "stored"
                
                # Update filename to match the one created by the file store
                # Extract the actual filename from the storage path
                new_filename = Path(self.storage_path).name
                logger.debug(f"Updating attachment filename from {self.filename} to {new_filename}")
                self.filename = new_filename
                
                # Add storage info to attributes
                self.attributes["storage_path"] = self.storage_path
                self.update_attributes_with_url()
                
                logger.debug(f"Successfully processed and stored attachment {self.filename}")
                
            except Exception as e:
                logger.error(f"Error processing attachment {self.filename}: {e}")
                self.status = "failed"
                raise

        except Exception as e:
            logger.error(f"Failed to process attachment {self.filename}: {str(e)}")
            self.status = "failed"
            raise RuntimeError(f"Failed to process attachment {self.filename}: {str(e)}") from e 