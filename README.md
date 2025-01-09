# Tyler

Tyler is an AI chat assistant built with Streamlit and powered by GPT-4. It can converse with users, answer questions, and create plans to perform tasks.

## Prerequisites

- Python 3.12+
- pyenv (for Python version management)
- pip (Python package manager)

## Development Setup

1. **Install pyenv** (if not already installed)

   ```bash
   curl https://pyenv.run | bash
   ```

   Add to your shell configuration file (~/.bashrc, ~/.zshrc, etc.):
   ```bash
   export PATH="$HOME/.pyenv/bin:$PATH"
   eval "$(pyenv init -)"
   eval "$(pyenv virtualenv-init -)"
   ```

2. **Install Python with pyenv**
   ```bash
   pyenv install 3.12.8
   ```

3. **Create a virtual environment**
   ```bash
   # Create and activate a new virtual environment for Tyler
   pyenv virtualenv 3.12.8 tyler-env
   pyenv local tyler-env
   ```

4. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/tyler.git
   cd tyler
   ```

5. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

6. **Set up secrets**
   
   Create a `.streamlit/secrets.toml` file:
   ```toml
   OPENAI_API_KEY = "your-openai-api-key"
   NOTION_TOKEN = "your-notion-token"  # Optional: Only if using Notion integration
   WANDB_API_KEY = "your-wandb-api-key"  # Optional: Only if using Weights & Biases
   SLACK_BOT_TOKEN = "your-slack-bot-token"  # Optional: Only if using Slack integration
   SLACK_SIGNING_SECRET = "your-slack-signing-secret"  # Optional: Only if using Slack integration
   ```

   Note: Make sure to add `.streamlit/secrets.toml` to your `.gitignore` file to keep your secrets secure.

7. **Run the application**
   ```bash
   streamlit run app_streamlit_chat.py
   ```

   The application will be available at `http://localhost:8501`

## Project Structure

```
tyler/
├── app_streamlit_chat.py    # Main Streamlit application
├── api.py                  # API server implementation
├── models/
│   ├── Agent.py           # Base agent class for handling conversations and tool execution
│   ├── RouterAgent.py     # Specialized agent for routing messages to appropriate agents
│   ├── Registry.py        # Registry for managing and accessing available agents
│   ├── Thread.py          # Thread model for managing conversation threads
│   └── Message.py         # Message model for individual messages in threads
├── prompts/
│   └── TylerPrompt.py     # Prompt templates and configurations
├── tools/                 # Tool implementations
│   ├── command_line.py
│   ├── notion.py
│   └── slack.py
├── utils/                 # Utility functions
│   ├── helpers.py
│   └── tool_runner.py
├── datasets/             # Data storage
├── tests/               # Test suite
└── .github/            # GitHub workflows and configurations
```

## Core Models

### Agent (`models/Agent.py`)
The base agent class that handles conversations and tool execution. Key features:
- Processes messages using GPT-4 model
- Manages conversation threads and message history
- Executes tools based on conversation context
- Handles recursive tool calls with depth limiting
- Uses a customizable system prompt for different agent purposes

### RouterAgent (`models/RouterAgent.py`)
A specialized agent responsible for directing incoming messages to appropriate specialized agents:
- Analyzes message content and intent
- Identifies explicit @mentions of agents
- Routes messages to the most suitable agent
- Creates and manages conversation threads
- Maintains thread history and agent assignments

### Registry (`models/Registry.py`)
Manages the registration and access of available agents in the system:
- Stores both agent classes and instances
- Handles agent registration with optional configuration
- Provides methods to access and verify agent availability
- Supports dynamic agent instantiation

### Thread (`models/Thread.py`)
Represents a conversation thread containing multiple messages:
- Manages message history and ordering
- Handles system prompts
- Tracks thread metadata (creation time, updates)
- Supports source tracking (e.g., Slack threads)
- Provides chat completion API compatibility

### Message (`models/Message.py`)
Represents individual messages within a thread:
- Supports multiple message roles (system, user, assistant, tool)
- Handles tool calls and results
- Generates unique message IDs
- Tracks message metadata and source information
- Manages message attributes and timestamps

## Running Tests

```bash
pytest
```

## Available Tools

### Notion Integration (`tools/notion.py`)
Enables interaction with Notion workspaces and databases.

- **create_page**: Creates a new page in a specified Notion database
- **search_pages**: Searches for pages in Notion using provided query parameters
- **update_page**: Updates the content of an existing Notion page
- **delete_page**: Deletes a specified page from Notion

### Slack Integration (`tools/slack.py`) 
Provides functionality to interact with Slack workspaces.

#### Local Development Setup
```bash
# Install Node.js and npm
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install LocalTunnel
npm install -g localtunnel
```

#### Starting the api server

```bash
# Terminal 1: Start the Flask server
python api.py
```

#### Starting LocalTunnel

```bash
# Terminal 2: Start LocalTunnel to receive events from Slack
lt --port 3000 --subdomain company-of-agents-local-tyler
```

Use the provided LocalTunnel URL (https://xxxx.loca.lt/slack/events) in your Slack App's Event Subscriptions settings.

### Command Line Tools (`tools/command_line.py`)
Enables execution of system commands and file operations.

- **execute_command**: Runs shell commands safely in a controlled environment
- **read_file**: Reads contents from specified files
- **write_file**: Writes or updates file contents
- **list_directory**: Lists files and directories in a specified path

## Feedback Logging

The application supports feedback logging through Weights & Biases (wandb). Users can provide feedback on AI responses using thumbs up (👍) or thumbs down (👍) buttons. This feedback is logged and can be used to improve the model's performance over time.

### How it works:
1. Each AI response includes feedback buttons
2. Clicking a feedback button logs the reaction to Weights & Biases
3. Feedback is associated with the specific model call for tracking and analysis

### Command Line Tools (`tools/command_line.py`)
Enables execution of system commands and file operations.

## Architecture Overview

Tyler uses a modular architecture built around a few key concepts:

1. **Agents**: The core processing units that handle conversations and execute tasks
   - Base Agent: Handles general conversation and tool execution
   - Router Agent: Routes messages to specialized agents based on content and @mentions
   - Specialized Agents: Handle specific types of tasks (can be added as needed)

2. **Threads**: Conversation containers that maintain message history and context
   - Each thread represents a distinct conversation
   - Threads can be sourced from different platforms (Slack, Web UI, etc.)
   - Messages within threads maintain order and relationships

3. **Tools**: Modular components that agents can use to perform tasks
   - Each tool has a specific purpose and interface
   - Tools can be added or modified without changing agent logic
   - Tools are executed through a standardized tool runner

## Development Guidelines

### Adding New Agents

1. Create a new agent class inheriting from `Agent`
2. Define the agent's purpose and system prompt
3. Register the agent in the `Registry`
4. Add any specialized tools the agent needs

Example:
```python
from models.Agent import Agent

class CustomAgent(Agent):
    def __init__(self, **data):
        super().__init__(
            purpose="To handle specific tasks",
            notes="Additional context for the agent",
            **data
        )

### Adding New Tools

1. Create a new tool file in the `tools/` directory
2. Define the tool's interface and parameters
3. Register the tool with the tool runner
4. Add tests for the tool functionality

## Testing

### Test Structure
- Unit tests for individual components
- Integration tests for agent-tool interactions
- End-to-end tests for complete workflows

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/models/test_agent.py

# Run with coverage report
pytest --cov=./ --cov-report=html
```

## Deployment

### Production Setup
1. Set up a production server with Python 3.12+
2. Configure environment variables for all integrations
3. Set up a process manager (e.g., supervisord)
4. Configure SSL/TLS for secure communications
5. Set up monitoring and logging

### Environment Variables
Required:
- `OPENAI_API_KEY`: OpenAI API key for GPT-4 access
- `DATABASE_URL`: URL for the thread database

Optional:
- `NOTION_TOKEN`: For Notion integration
- `SLACK_BOT_TOKEN`: For Slack bot functionality
- `SLACK_SIGNING_SECRET`: For Slack event verification
- `WANDB_API_KEY`: For logging feedback with Weights & Biases
- `LOG_LEVEL`: Logging level (default: INFO)

