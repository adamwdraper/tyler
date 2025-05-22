# File and Document Operations

The files module provides tools for reading, processing, and analyzing various file types and documents, with automatic content extraction and format-specific handling.

## Available tools

### Read-file

Reads and extracts content from files with automatic format detection and processing. Supports PDFs, CSVs, JSON, and text files.

#### Parameters

- `file_url` (string, required)
  - URL or path to the file
  - Must be a valid local file path

- `mime_type` (string, optional)
  - Optional MIME type hint for file processing
  - If not provided, will be auto-detected

#### Returns

A dictionary containing:
- `success`: Boolean indicating success
- `text`: Extracted text content (for text files)
- `type`: File type detected
- `file_url`: Original file path
- `mime_type`: Detected MIME type
- `error`: Error message if failed

For PDFs, additional fields:
- `pages`: Number of pages
- `empty_pages`: List of pages with no text
- `processing_method`: Method used ("text" or "vision")

For CSVs, additional fields:
- `statistics`: Dictionary containing:
  - `total_rows`: Number of rows
  - `total_columns`: Number of columns
  - `columns`: List of column names
  - `column_types`: Dictionary of column data types
- `preview`: Array of preview rows

For JSON, additional fields:
- `data`: Parsed JSON data or extracted value

### Write-file

Writes content to a file with automatic format handling based on content type and file extension.

#### Parameters

- `content` (any, required)
  - Content to write - can be dict/list (JSON), list of dicts (CSV), string (text), or bytes (binary)

- `file_url` (string, required)
  - Path where to write the file

- `mime_type` (string, optional)
  - Optional MIME type hint
  - If not provided, will be detected from extension or content type

#### Returns

A dictionary containing:
- `success`: Boolean indicating success
- `mime_type`: MIME type of the written file
- `file_url`: Path where the file was written
- `size`: Size of the written file in bytes
- `error`: Error message if failed

## Example usage

```python
from tyler.models import Agent, Thread, Message

# Create an agent with file tools
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with file processing",
    tools=["files"]
)

# Create a thread to read a PDF file
thread = Thread()
message = Message(
    role="user",
    content="Please read and extract the content from document.pdf"
)
thread.add_message(message)

# Process the thread - agent will use read-file tool
processed_thread, new_messages = await agent.go(thread)

# Example of CSV analysis
csv_thread = Thread()
message = Message(
    role="user",
    content="Analyze the contents of data.csv and show me a preview"
)
csv_thread.add_message(message)

# Process the thread - agent will use read-file tool with CSV handling
processed_csv, new_messages = await agent.go(csv_thread)

# Example of writing a file
write_thread = Thread()
message = Message(
    role="user",
    content="Create a JSON file with the following data: {'name': 'John', 'age': 30}"
)
write_thread.add_message(message)

# Process the thread - agent will use write-file tool
processed_write, new_messages = await agent.go(write_thread)
```

## Best practices

1. **File Access**
   - Ensure file permissions are correct
   - Use absolute paths when possible
   - Verify file existence before processing
   - Handle large files appropriately

2. **Content Processing**
   - Let MIME type be auto-detected when possible
   - Handle text encoding properly
   - Consider file size limitations
   - Process files in chunks if needed

3. **PDF Processing**
   - Extract specific pages when possible
   - Handle large documents in chunks
   - Consider text encoding
   - Preserve document structure

4. **CSV Handling**
   - Verify delimiter settings
   - Handle header rows properly
   - Check data types
   - Validate data consistency

5. **JSON Processing**
   - Validate JSON structure
   - Use specific paths for large files
   - Handle nested data carefully
   - Consider memory usage

6. **Error Handling**
   - Check file existence
   - Handle permission issues
   - Manage encoding errors
   - Process format-specific errors

7. **Security**
   - Validate file paths
   - Check file permissions
   - Scan for malicious content
   - Limit file sizes

## Common use cases

1. **Document Processing**
   - Reading text files
   - Extracting PDF content
   - Processing configuration files
   - Analyzing log files

2. **Data Analysis**
   - CSV data analysis
   - JSON data parsing
   - Statistical processing
   - Data validation

3. **Content Extraction**
   - Text extraction
   - Document parsing
   - Data extraction
   - Format conversion

4. **File Management**
   - Format detection
   - Content validation
   - Structure analysis
   - Encoding detection

5. **Data Processing**
   - Format conversion
   - Data transformation
   - Content extraction
   - Statistical analysis

## Limitations

1. **File Support**
   - Limited to supported formats
   - PDF processing may require OCR
   - Binary files not fully supported
   - Size limitations apply

2. **Processing Constraints**
   - Memory usage for large files
   - Processing time for complex files
   - OCR accuracy varies
   - Encoding detection limits

3. **PDF Processing**
   - Complex layouts may affect accuracy
   - Large file handling
   - Font dependency

4. **CSV Processing**
   - Memory constraints for large files
   - Encoding limitations
   - Type inference accuracy
   - Special character handling

5. **JSON Processing**
   - Memory usage for large files
   - Deep nesting limitations
   - Path complexity
   - Schema validation

## Error handling

Common errors and solutions:

1. **File Access**
   - Check file existence
   - Verify permissions
   - Validate paths
   - Handle timeouts

2. **Processing Errors**
   - Handle corrupt files
   - Manage encoding issues
   - Process format errors
   - Handle extraction failures

3. **Resource Issues**
   - Monitor memory usage
   - Handle timeout errors
   - Manage concurrent access
   - Control file handles 