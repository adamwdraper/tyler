# Built-in tools

Tyler comes with a set of built-in tools that provide common functionality for AI agents. These tools are ready to use out of the box and can be enabled or disabled as needed.

## Web tools

### Web search
Search the web using DuckDuckGo.
```python
web_search(query: str) -> List[SearchResult]
```

### Web browse
Visit a URL and extract its content.
```python
web_browse(url: str) -> WebPage
```

## File tools

### Read file
Read the contents of a file.
```python
read_file(path: str) -> str
```

### Write file
Write content to a file.
```python
write_file(path: str, content: str) -> None
```

### List directory
List contents of a directory.
```python
list_dir(path: str) -> List[str]
```

## System tools

### Run command
Execute a system command.
```python
run_command(command: str) -> CommandResult
```

### Get environment
Get environment variables.
```python
get_env(var_name: str) -> str
```

## Image tools

### Generate image
Generate an image using DALL-E.
```python
generate_image(prompt: str) -> bytes
```

### Analyze image
Analyze an image using GPT-4 Vision.
```python
analyze_image(image: bytes) -> str
```

## Code tools

### Execute code
Execute Python code in a sandbox.
```python
execute_code(code: str) -> CodeResult
```

### Format code
Format code using black.
```python
format_code(code: str) -> str
```

## Next steps

- See the individual tool documentation pages linked above for examples and detailed API references

## Web Tools

The web module provides tools for interacting with web content.

### web-fetch_page

Fetches content from a web page and returns it in a clean, readable format with preserved structure.

**Parameters:**
- `url` (string, required): The URL to fetch
- `format` (string, optional): Output format - either 'text' or 'html'. Default: 'text'
  - Use 'text' for getting the content of a page
  - Only use 'html' when you need the raw HTML content
- `headers` (object, optional): Optional headers to send with the request

## Slack Tools

The Slack module provides tools for interacting with Slack workspaces.

### slack-post_to_slack

Posts a message to Slack. The tool is careful about channel selection and requires explicit channel specification.

**Parameters:**
- `channel` (string, required): The Slack channel to post to
- `blocks` (array, required): The blocks to post to Slack
  - Each block is an object with:
    - `type` (string)
    - `text` (object)

### slack-create_channel

Creates a new Slack channel.

**Parameters:**
- `name` (string, required): The name of the channel to create (will be automatically converted to lowercase and hyphens)
- `is_private` (boolean, optional): Whether to create a private channel

### slack-invite_to_channel

Invites a user to a Slack channel.

**Parameters:**
- `channel` (string, required): The channel ID or name to invite the user to
- `user` (string, required): The user ID to invite to the channel

## Command Line Tools

The command line module provides safe access to system commands.

### command_line-run_command

Executes whitelisted command line operations safely.

**Parameters:**
- `command` (string, required): Command to execute (must start with a whitelisted command)
- `working_dir` (string, optional): Working directory for the command (defaults to current directory)

**Available Commands:**

Navigation & Read Operations (unrestricted):
- `ls`: List directory contents
- `pwd`: Print working directory
- `cd`: Change directory
- `cat`: Display file contents
- `find`: Search for files by name
- `grep`: Search for patterns in files
- `tree`: Display directory structure
- `wc`: Count lines/words/characters
- `head/tail`: Show start/end of files
- `diff`: Compare files

File Operations (restricted to workspace only):
- `mkdir`: Create directory
- `touch`: Create empty file
- `rm`: Remove file/empty dir
- `cp`: Copy file
- `mv`: Move/rename file
- `echo`: Write to file
- `sed`: Edit file content

## Notion Tools

The Notion module provides tools for interacting with Notion workspaces.

### notion-search

Searches all titles of pages and databases in Notion that have been shared with the integration.

**Parameters:**
- `query` (string, optional): The search query to find in page/database titles
- `filter` (object, optional): Filter to only return pages or databases
  - `value`: "page" or "database"
  - `property`: "object"
- `start_cursor` (string, optional): Cursor for pagination
- `page_size` (integer, optional): Number of results to return (1-100, default 100)

## Image Tools

The image module provides tools for generating and manipulating images.

### image-generate

Generates images based on text descriptions using DALL-E 3.

**Parameters:**
- `prompt` (string, required): Text description of the desired image (max 4000 characters)
- `size` (string, optional): Size of the generated image. Default: "1024x1024"
  - Options: "1024x1024", "1792x1024", "1024x1792"
- `quality` (string, optional): Quality of the image. Default: "standard"
  - "standard": Normal quality
  - "hd": Creates images with finer details and greater consistency
- `style` (string, optional): Style of the generated image. Default: "vivid"
  - "vivid": Hyper-real and dramatic
  - "natural": Less hyper-real

## Using Built-in Tools

To use these tools, include their module names in your agent's configuration:

```yaml
tools:
  - "web"           # Web tools
  - "slack"         # Slack tools
  - "notion"        # Notion tools
  - "command_line"  # Command line tools
  - "image"         # Image generation tools
```

Or when creating an agent programmatically:

```python
from tyler.models import Agent

agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with various tasks",
    tools=["web", "slack", "notion", "command_line", "image"]
)
```

## Required Environment Variables

Some tools require specific environment variables to be set:

### Slack Tools
- `SLACK_BOT_TOKEN`: Your Slack bot token
- `SLACK_SIGNING_SECRET`: Your Slack signing secret

### Notion Tools
- `NOTION_API_KEY`: Your Notion API key
- `NOTION_VERSION`: Notion API version (e.g., "2022-06-28")

### Image Tools
- `OPENAI_API_KEY`: Your OpenAI API key (for DALL-E 3)

## Additional Resources

- See the individual tool documentation pages linked above for examples and detailed API references 