# Command line operations

The command line module provides safe access to system commands, allowing you to execute whitelisted operations.

## Security model

The command line tools follow strict security principles:

1. **Whitelisted Commands**
   - Only pre-approved commands are allowed
   - Commands are categorized by risk level
   - Workspace-modifying operations are restricted

2. **Workspace Containment**
   - File operations are restricted to the workspace
   - Absolute paths are resolved relative to workspace
   - Parent directory traversal is prevented

3. **Permission Model**
   - Read operations are generally unrestricted
   - Write operations are workspace-scoped
   - System operations are limited

## Available tools

### Command line-run command

Executes whitelisted command line operations safely.

#### Parameters

- `command` (string, required)
  - The command to execute
  - Must start with a whitelisted command
  - Arguments are validated
  - Workspace paths are enforced

- `working_dir` (string, optional)
  - Working directory for the command
  - Default: "." (current directory)
  - Must be within workspace
  - Relative paths preferred

#### Whitelisted commands

**Navigation & read operations** (unrestricted):
- `ls`: List directory contents
  ```bash
  ls          # List current directory
  ls -la      # List with details
  ls path/    # List specific directory
  ```

- `pwd`: Print working directory
  ```bash
  pwd         # Show current path
  ```

- `cd`: Change directory
  ```bash
  cd path/    # Change to directory
  cd ..       # Go up one level
  cd          # Go to home directory
  ```

- `cat`: Display file contents
  ```bash
  cat file.txt          # Show file
  cat file1.txt file2.txt  # Show multiple files
  ```

- `find`: Search for files by name
  ```bash
  find . -name "*.py"   # Find Python files
  find . -type d        # Find directories
  ```

- `grep`: Search for patterns in files
  ```bash
  grep "pattern" file.txt    # Search in file
  grep -r "pattern" .        # Recursive search
  ```

- `tree`: Display directory structure
  ```bash
  tree         # Show directory tree
  tree -L 2    # Limit to 2 levels
  ```

- `wc`: Count lines/words/characters
  ```bash
  wc file.txt           # Count all
  wc -l file.txt        # Count lines
  ```

- `head/tail`: Show start/end of files
  ```bash
  head file.txt         # Show first 10 lines
  tail -n 20 file.txt   # Show last 20 lines
  ```

- `diff`: Compare files
  ```bash
  diff file1.txt file2.txt  # Show differences
  ```

**File operations** (workspace-restricted):
- `mkdir`: Create directory
  ```bash
  mkdir new_dir         # Create directory
  mkdir -p a/b/c        # Create nested dirs
  ```

- `touch`: Create empty file
  ```bash
  touch file.txt        # Create/update file
  ```

- `rm`: Remove file/empty dir
  ```bash
  rm file.txt          # Remove file
  rm -r dir/           # Remove directory
  ```

- `cp`: Copy file
  ```bash
  cp source.txt dest.txt   # Copy file
  cp -r src/ dest/         # Copy directory
  ```

- `mv`: Move/rename file
  ```bash
  mv old.txt new.txt      # Rename file
  mv file.txt dir/        # Move file
  ```

- `echo`: Write to file
  ```bash
  echo "text" > file.txt   # Write to file
  echo "text" >> file.txt  # Append to file
  ```

- `sed`: Edit file content
  ```bash
  sed 's/old/new/' file.txt  # Replace text
  sed -i '' 's/old/new/' file.txt  # In-place edit
  ```

## Example usage

```python
from tyler.models import Agent, Thread, Message

# Create an agent with command line tools
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with file operations",
    tools=["command_line"]
)

# Create a thread with a command request
thread = Thread()
message = Message(
    role="user",
    content="Can you list all Python files in the current directory?"
)
thread.add_message(message)

# Process the thread - agent will use command_line-run_command tool
processed_thread, new_messages = await agent.go(thread)
```

## Best practices

1. **Path Handling**
   - Use relative paths when possible
   - Validate paths before operations
   - Handle path resolution carefully

2. **File Operations**
   - Check file existence before operations
   - Handle file permissions appropriately
   - Use safe file operation patterns

3. **Command Construction**
   - Validate command syntax
   - Escape special characters
   - Use appropriate flags

4. **Error Handling**
   - Check command exit codes
   - Handle common error cases
   - Provide meaningful error messages

## Common use cases

1. **File Management**
   - Organize project files
   - Clean up directories
   - Batch file operations

2. **Content Search**
   - Find specific files
   - Search file contents
   - Pattern matching

3. **Directory Navigation**
   - Browse project structure
   - Locate resources
   - Manage paths

4. **File Analysis**
   - Compare file versions
   - Analyze file contents
   - Count lines/words

## Security considerations

1. **Command Injection**
   - Validate all inputs
   - Escape special characters
   - Use safe command construction

2. **File Access**
   - Respect workspace boundaries
   - Check file permissions
   - Validate file operations

3. **Resource Usage**
   - Monitor command execution
   - Handle timeouts
   - Prevent resource exhaustion 