# Notion integration

The Notion module provides tools for interacting with Notion workspaces, allowing you to search, create, and manage content.

## Configuration

Before using Notion tools, you need to set up the following environment variables:

```bash
NOTION_API_KEY=your-api-key
NOTION_VERSION=2022-06-28  # Or latest supported version
```

To get these credentials:
1. Create a Notion integration at https://www.notion.so/my-integrations
2. Copy the integration token (API key)
3. Share the pages/databases you want to access with your integration

## Available tools

### Notion-search

Searches all titles of pages and databases in Notion that have been shared with the integration.

#### Parameters

- `query` (string, optional)
  - The search query to find in page/database titles
  - Query should focus on subject matter likely to be in titles
  - If not provided, returns all accessible pages/databases
  - Case-insensitive
  - Supports partial matches

- `filter` (object, optional)
  - Filter to only return specific types of content
  - Properties:
    - `value`: Type of content to filter
      - "page": Only return pages
      - "database": Only return databases
    - `property`: Must be "object"

- `start_cursor` (string, optional)
  - Cursor for pagination
  - Use to fetch next page of results
  - Obtained from previous search response

- `page_size` (integer, optional)
  - Number of results to return
  - Default: 100
  - Range: 1-100
  - Use with start_cursor for pagination

#### Response format

The tool returns a dictionary with:
- `results`: Array of found pages/databases
  - Each result includes:
    - `id`: Notion page/database ID
    - `title`: Content title
    - `url`: Notion URL
    - `object`: Type ("page" or "database")
    - `created_time`: Creation timestamp
    - `last_edited_time`: Last edit timestamp
- `next_cursor`: Cursor for next page (if more results)
- `has_more`: Boolean indicating if more results exist

#### Example Usage

```python
from tyler.models import Agent, Thread, Message

# Create an agent with Notion tools
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with Notion content",
    tools=["notion"]
)

# Create a thread with a search request
thread = Thread()
message = Message(
    role="user",
    content="Find all project planning documents in Notion"
)
thread.add_message(message)

# Process the thread - agent will use notion-search tool
processed_thread, new_messages = await agent.go(thread)
```

## Best practices

1. **Search Optimization**
   - Use specific search terms
   - Consider title patterns
   - Handle pagination for large results

2. **Error Handling**
   - Check API responses
   - Handle rate limits
   - Validate permissions

3. **Content Access**
   - Share pages explicitly
   - Manage integration permissions
   - Track accessed content

4. **Performance**
   - Use appropriate page sizes
   - Implement pagination
   - Cache results when appropriate

## Common use cases

1. **Content Discovery**
   - Find relevant documents
   - Locate databases
   - Search project resources

2. **Content Organization**
   - Audit page access
   - Track document changes
   - Manage workspaces

3. **Integration**
   - Connect with other tools
   - Automate workflows
   - Sync content

## Security considerations

1. **Access Control**
   - Share only necessary content
   - Review integration permissions
   - Monitor access patterns

2. **API Keys**
   - Secure storage of keys
   - Regular key rotation
   - Access logging

3. **Content Security**
   - Validate content access
   - Handle sensitive data
   - Respect workspace boundaries

## Limitations

1. **API Constraints**
   - Rate limits apply
   - Maximum page size of 100
   - Some operations require specific permissions

2. **Search Limitations**
   - Title-only search
   - No full-text search
   - Limited filter options

3. **Integration Scope**
   - Access limited to shared content
   - Some operations restricted
   - Workspace boundaries enforced

## Error handling

Common issues and solutions:

1. **Authentication Errors**
   - Verify API key is set
   - Check environment variables
   - Validate API version

2. **Access Denied**
   - Confirm page is shared
   - Check integration permissions
   - Verify workspace access

3. **Rate Limiting**
   - Implement backoff
   - Monitor usage
   - Optimize requests 