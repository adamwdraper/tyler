"""Unified file operations module combining file reading and document processing capabilities"""

import os
import weave
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
import mimetypes
import base64
import io
import magic
import pandas as pd
import json
from pypdf import PdfReader
from pdf2image import convert_from_bytes
from litellm import completion
from tyler.utils.logging import get_logger

# Get configured logger
logger = get_logger(__name__)

class Files:
    """Unified file operations system that handles both basic file operations
    and specialized document processing"""

    @weave.op(name="read-file")
    async def read_file(self, file_url: str, mime_type: Optional[str] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Smart file reading with automatic format detection and processing
        
        Args:
            file_url: Path to the file to read
            mime_type: Optional MIME type hint. If not provided, will be detected
            
        Returns:
            Tuple containing:
            - Dict with success status and metadata
            - List of file dictionaries with content and metadata
        """
        try:
            # Read file content
            file_path = Path(file_url)
            if not file_path.exists():
                return (
                    {"success": False, "error": f"File not found: {file_url}"},
                    []
                )
            
            content = file_path.read_bytes()

            # Detect MIME type if not provided
            if not mime_type:
                mime_type = magic.from_buffer(content, mime=True)

            # Route to appropriate handler based on MIME type
            if mime_type == 'application/pdf':
                return await self.process_pdf(content, file_url)
            elif mime_type == 'text/csv':
                return await self.parse_csv(content, file_url)
            elif mime_type == 'application/json':
                return await self.parse_json(content, file_url)
            elif mime_type.startswith('text/'):
                return await self.process_text(content, file_url)
            else:
                # For unknown types, return as binary attachment
                return (
                    {
                        "success": True,
                        "mime_type": mime_type,
                        "file_url": file_url
                    },
                    [{
                        "content": base64.b64encode(content).decode('utf-8'),
                        "filename": file_path.name,
                        "mime_type": mime_type
                    }]
                )

        except Exception as e:
            logger.error(f"Error reading file {file_url}: {str(e)}")
            return (
                {"success": False, "error": str(e), "file_url": file_url},
                []
            )

    async def process_pdf(self, content: bytes, file_url: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Process PDF with smart fallback to Vision API"""
        try:
            pdf_reader = PdfReader(io.BytesIO(content))
            text = ""
            empty_pages = []
            
            for i, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if not page_text.strip():
                        empty_pages.append(i + 1)
                    text += page_text + "\n"
                except Exception:
                    empty_pages.append(i + 1)
                    continue
                    
            text = text.strip()
            
            # If no text extracted, try Vision API
            if not text:
                return await self._process_pdf_with_vision(content, file_url)
                
            return (
                {
                    "success": True,
                    "text": text,
                    "type": "pdf",
                    "pages": len(pdf_reader.pages),
                    "empty_pages": empty_pages,
                    "processing_method": "text",
                    "file_url": file_url
                },
                [{
                    "content": base64.b64encode(content).decode('utf-8'),
                    "filename": Path(file_url).name,
                    "mime_type": "application/pdf"
                }]
            )

        except Exception as e:
            logger.error(f"Error processing PDF {file_url}: {str(e)}")
            return (
                {"success": False, "error": str(e), "file_url": file_url},
                []
            )

    async def _process_pdf_with_vision(self, content: bytes, file_url: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Process PDF using Vision API when text extraction fails"""
        try:
            # Convert PDF to images
            images = convert_from_bytes(content)
            pages_text = []
            empty_pages = []
            
            for i, image in enumerate(images, 1):
                # Save image to bytes
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                
                # Convert to base64
                b64_image = base64.b64encode(img_byte_arr).decode('utf-8')
                
                # Process with Vision API
                response = completion(
                    model="gpt-4.1",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Extract all text from this page, preserving the structure and layout. Include any relevant formatting or visual context that helps understand the text organization."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{b64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=4096,
                    temperature=0.2
                )
                
                page_text = response.choices[0].message.content
                if not page_text.strip():
                    empty_pages.append(i)
                pages_text.append(f"--- Page {i} ---\n{page_text}")
            
            return (
                {
                    "success": True,
                    "text": "\n\n".join(pages_text),
                    "type": "pdf",
                    "pages": len(images),
                    "empty_pages": empty_pages,
                    "processing_method": "vision",
                    "file_url": file_url
                },
                [{
                    "content": base64.b64encode("\n\n".join(pages_text).encode('utf-8')).decode('utf-8'),
                    "filename": Path(file_url).name,
                    "mime_type": "application/pdf"
                }]
            )
                
        except Exception as e:
            logger.error(f"Error processing PDF with Vision API {file_url}: {str(e)}")
            return (
                {"success": False, "error": str(e), "file_url": file_url},
                []
            )

    async def parse_csv(self, content: bytes, file_url: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Parse CSV with statistics and preview"""
        try:
            # Use StringIO to create file-like object from bytes
            csv_data = io.StringIO(content.decode('utf-8'))
            df = pd.read_csv(csv_data)
            
            stats = {
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "columns": list(df.columns),
                "column_types": {col: str(df[col].dtype) for col in df.columns}
            }

            preview = df.head(5).to_dict(orient='records')

            return (
                {
                    "success": True,
                    "statistics": stats,
                    "preview": preview,
                    "file_url": file_url
                },
                [{
                    "content": base64.b64encode(content).decode('utf-8'),
                    "filename": Path(file_url).name,
                    "mime_type": "text/csv"
                }]
            )

        except Exception as e:
            logger.error(f"Error parsing CSV {file_url}: {str(e)}")
            return (
                {"success": False, "error": str(e), "file_url": file_url},
                []
            )

    async def parse_json(self, content: bytes, file_url: str, path: Optional[str] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Parse JSON with optional path extraction"""
        try:
            data = json.loads(content)

            if path:
                try:
                    parts = path.split('.')
                    current = data
                    for part in parts:
                        if '[' in part:
                            name, index = part.split('[')
                            index = int(index.rstrip(']'))
                            current = current[name][index]
                        else:
                            current = current[part]
                    data = current
                except (KeyError, IndexError) as e:
                    return (
                        {
                            "success": False,
                            "error": f"Invalid JSON path: {str(e)}",
                            "file_url": file_url
                        },
                        []
                    )

            return (
                {
                    "success": True,
                    "data": data,
                    "file_url": file_url
                },
                [{
                    "content": base64.b64encode(content).decode('utf-8'),
                    "filename": Path(file_url).name,
                    "mime_type": "application/json"
                }]
            )

        except json.JSONDecodeError as e:
            return (
                {
                    "success": False,
                    "error": f"Invalid JSON format: {str(e)}",
                    "file_url": file_url
                },
                []
            )
        except Exception as e:
            logger.error(f"Error parsing JSON {file_url}: {str(e)}")
            return (
                {"success": False, "error": str(e), "file_url": file_url},
                []
            )

    async def process_text(self, content: bytes, file_url: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Process plain text files"""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    text = content.decode(encoding)
                    return (
                        {
                            "success": True,
                            "text": text,
                            "encoding": encoding,
                            "file_url": file_url
                        },
                        [{
                            "content": base64.b64encode(content).decode('utf-8'),
                            "filename": Path(file_url).name,
                            "mime_type": "text/plain"
                        }]
                    )
                except UnicodeDecodeError:
                    continue
            
            return (
                {
                    "success": False,
                    "error": "Could not decode text with any supported encoding",
                    "file_url": file_url
                },
                []
            )

        except Exception as e:
            logger.error(f"Error processing text file {file_url}: {str(e)}")
            return (
                {"success": False, "error": str(e), "file_url": file_url},
                []
            )

    @weave.op(name="write-file")
    async def write_file(self, content: Any, file_url: str, mime_type: Optional[str] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Write content to a file with automatic format handling based on type
        
        Args:
            content: Content to write - can be dict/list (JSON), list of dicts (CSV),
                    string (text), or bytes (binary)
            file_url: Path where to write the file
            mime_type: Optional MIME type hint. If not provided, will be detected
            
        Returns:
            Tuple containing:
            - Dict with success status and metadata
            - List of file dictionaries with content and metadata
        """
        try:
            # Detect MIME type if not provided
            if not mime_type:
                mime_type = mimetypes.guess_type(file_url)[0]
                if not mime_type:
                    # Try to infer from content type
                    if isinstance(content, (dict, list)):
                        mime_type = 'application/json'
                    elif isinstance(content, str):
                        mime_type = 'text/plain'
                    elif isinstance(content, bytes):
                        mime_type = 'application/octet-stream'
                    else:
                        raise ValueError(f"Could not determine MIME type for content type: {type(content)}")

            # Convert content to appropriate format based on MIME type
            if mime_type == 'application/json':
                processed_content = await self._write_json(content)
            elif mime_type == 'text/csv':
                processed_content = await self._write_csv(content)
            elif mime_type.startswith('text/'):
                processed_content = await self._write_text(content)
            elif isinstance(content, bytes):
                processed_content = content
            else:
                raise ValueError(f"Unsupported MIME type for writing: {mime_type}")

            return (
                {
                    "success": True,
                    "mime_type": mime_type,
                    "file_url": file_url,
                    "size": len(processed_content)
                },
                [{
                    "content": base64.b64encode(processed_content).decode('utf-8'),
                    "filename": Path(file_url).name,
                    "mime_type": mime_type
                }]
            )

        except Exception as e:
            logger.error(f"Error writing file {file_url}: {str(e)}")
            return (
                {
                    "success": False,
                    "error": str(e),
                    "file_url": file_url
                },
                []
            )

    async def _write_json(self, content: Any) -> bytes:
        """Convert content to JSON and return as bytes"""
        try:
            # Ensure content is JSON serializable
            json_str = json.dumps(content, indent=2, ensure_ascii=False)
            return json_str.encode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to serialize content to JSON: {str(e)}")

    async def _write_csv(self, content: Any) -> bytes:
        """Convert content to CSV and return as bytes"""
        try:
            # Handle different input types
            if isinstance(content, pd.DataFrame):
                csv_buffer = io.StringIO()
                content.to_csv(csv_buffer, index=False)
                return csv_buffer.getvalue().encode('utf-8')
            elif isinstance(content, (list, dict)):
                # Convert to DataFrame first
                df = pd.DataFrame(content)
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                return csv_buffer.getvalue().encode('utf-8')
            else:
                raise ValueError(f"Unsupported content type for CSV: {type(content)}")
        except Exception as e:
            raise ValueError(f"Failed to convert content to CSV: {str(e)}")

    async def _write_text(self, content: Any) -> bytes:
        """Convert content to text and return as bytes"""
        try:
            # Handle different input types
            if isinstance(content, bytes):
                return content
            elif isinstance(content, str):
                return content.encode('utf-8')
            else:
                # Try to convert to string
                return str(content).encode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to convert content to text: {str(e)}")

# Define the tools list
TOOLS = [
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "read-file",
                "description": "Smart file reading and processing with automatic format detection. Handles PDF (with Vision API fallback), CSV (with statistics), JSON (with path extraction), and text files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_url": {
                            "type": "string",
                            "description": "Path to the file to read"
                        },
                        "mime_type": {
                            "type": "string",
                            "description": "Optional MIME type hint. If not provided, will be detected",
                            "default": None
                        }
                    },
                    "required": ["file_url"]
                }
            }
        },
        "implementation": Files().read_file
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "write-file",
                "description": "Smart file writing with automatic format handling. Can write JSON, CSV, text files, and binary data with appropriate formatting.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "object",
                            "description": "Content to write - can be dict/list (JSON), list of dicts (CSV), string (text), or bytes (binary)"
                        },
                        "file_url": {
                            "type": "string",
                            "description": "Path where to write the file"
                        },
                        "mime_type": {
                            "type": "string",
                            "description": "Optional MIME type hint. If not provided, will be detected from extension or content type",
                            "default": None
                        }
                    },
                    "required": ["content", "file_url"]
                }
            }
        },
        "implementation": Files().write_file
    }
] 