# Tyler

<div align="center">
    <img src="docs/static/img/tyler-soap.png" alt="Tyler Logo" width="200" style="border-radius: 8px;"/>
</div>

### A development kit for manifesting AI agents with a complete lack of conventional limitations

Tyler makes it easy to start building effective AI agents in just a few lines of code. Tyler provides all the essential components needed to build production-ready AI agents that can understand context, manage conversations, and effectively use tools.

### Key Features

- **Multimodal support**: Process and understand images, audio, PDFs, and more out of the box
- **Ready-to-use tools**: Comprehensive set of built-in tools with easy integration of custom built tools
- **MCP compatibility**: Seamless integration with [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) compatible servers and tools
- **Real-time streaming**: Build interactive applications with streaming responses from both the assistant and tools
- **Structured data model**: Built-in support for threads, messages, and attachments to maintain conversation context
- **Persistent storage**: Choose between in-memory, SQLite, or PostgreSQL to store conversation history and files
- **Advanced debugging**: Integration with [W&B Weave](https://weave-docs.wandb.ai/) for powerful tracing and debugging capabilities
- **Flexible model support**: Use any LLM provider supported by LiteLLM (100+ providers including OpenAI, Anthropic, etc.)

![Tyler Chat UI Demo](docs/static/img/tyler_chat_UI_demo_short.gif)

---

<div style="display: flex; align-items: center; gap: 20px;">
    <span style="font-size: 1em;">Sponsored by</span>
    <a href="https://weave-docs.wandb.ai/"><img src="docs/static/img/weave_logo.png" alt="Weights & Biases Logo" height="40"/></a>
</div>

---

### For detailed documentation and guides, visit our [Docs](https://adamwdraper.github.io/tyler/).

While Tyler can be used as a library, it comes with two interactive interfaces:
1. A web-based chat interface available as a separate repository at [tyler-chat](https://github.com/adamwdraper/tyler-chat)
2. A built-in command-line interface (CLI) accessible via the `tyler-chat` command after installation. See the [Chat with Tyler](https://adamwdraper.github.io/tyler/docs/chat-with-tyler) documentation for details on both interfaces.


&nbsp;

![Workflow Status](https://github.com/adamwdraper/tyler/actions/workflows/pytest.yml/badge.svg)
[![PyPI version](https://img.shields.io/pypi/v/tyler-agent.svg?style=social)](https://pypi.org/project/tyler-agent/)


## Overview

### Core Components

### Agent

The central component that:
- Manages conversations through threads
- Processes messages using LLMs (GPT-4.1 by default)
- Executes tools when needed
- Maintains conversation state
- Supports streaming responses
- Handles file attachments and processing
- Integrates with Weave for monitoring

### Thread

Manages conversations and maintains:
- Message history with proper sequencing
- System prompts
- Conversation metadata and analytics
- Source tracking (e.g., Slack, web)
- Token usage statistics
- Performance metrics

### Message

Basic units of conversation containing:
- Content (text or multimodal)
- Role (user, assistant, system, tool)
- Sequence number for ordering
- Attachments (files with automatic processing)
- Metrics (token usage, timing, model info)
- Source information
- Custom attributes

### Attachment

Handles files in conversations:
- Support for binary and base64 encoded content
- Automatic storage management
- Content processing and extraction
- Status tracking (pending, stored, failed)
- URL generation for stored files
- Secure backend storage integration

### Tools

Extend agent capabilities with:
- Web browsing and downloads (WEB_TOOLS)
- Slack integration (SLACK_TOOLS)
- Notion integration (NOTION_TOOLS)
- Image processing (IMAGE_TOOLS)
- Audio processing (AUDIO_TOOLS)
- File operations (FILES_TOOLS)
- Document processing (DOCUMENTS_TOOLS)
- Shell commands (COMMAND_LINE_TOOLS)

### MCP

Integrates with the Model Context Protocol for:
- Seamless connection to MCP-compatible servers
- Automatic tool discovery from MCP servers
- Support for multiple transport protocols (WebSocket, SSE, STDIO)
- Server lifecycle management
- Dynamic tool invocation
- Integration with any MCP-compatible tool ecosystem

### Storage

Multiple storage backends for:
- Thread Storage:
  - Memory Store: Fast, in-memory storage for development
  - Database Store: PostgreSQL/SQLite for production
- File Storage:
  - Local filesystem
  - Cloud storage (S3, GCS)
  - Configurable via environment variables

## User Guide

### Prerequisites

- Python 3.12.8
- uv (modern Python package manager)

### Installation

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install required libraries for PDF and image processing
brew install libmagic poppler

# Install Tyler (includes all core dependencies)
uv add tyler-agent
```

# For development installation:
```bash
uv add tyler-agent --dev
```

When you install Tyler using uv, all required runtime dependencies will be installed automatically, including:
- LLM support (LiteLLM, OpenAI)
- Database support (PostgreSQL, SQLite)
- Monitoring and metrics (Weave, Wandb)
- File processing (PDF, images)
- All core utilities and tools

### Basic Setup

Create a `.env` file in your project directory with the following configuration:
```bash
# Database Configuration
TYLER_DB_TYPE=postgresql
TYLER_DB_HOST=localhost
TYLER_DB_PORT=5432
TYLER_DB_NAME=tyler
TYLER_DB_USER=tyler
TYLER_DB_PASSWORD=tyler_dev

# Optional Database Settings
TYLER_DB_ECHO=false
TYLER_DB_POOL_SIZE=5
TYLER_DB_MAX_OVERFLOW=10
TYLER_DB_POOL_TIMEOUT=30
TYLER_DB_POOL_RECYCLE=1800

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key

# Logging Configuration
WANDB_API_KEY=your-wandb-api-key

# Optional Integrations
NOTION_TOKEN=your-notion-token
SLACK_BOT_TOKEN=your-slack-bot-token
SLACK_SIGNING_SECRET=your-slack-signing-secret

# File storage configuration
TYLER_FILE_STORAGE_TYPE=local
TYLER_FILE_STORAGE_PATH=/path/to/files  # Optional, defaults to ~/.tyler/files

# Other settings
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

Only the `OPENAI_API_KEY` (or whatever LLM provider you're using) is required for core functionality. Other environment variables are required only when using specific features:
- For Weave monitoring: `WANDB_API_KEY` is required (You will want to use this for monitoring and debugging) [https://weave-docs.wandb.ai/](Weave Docs)
- For Slack integration: `SLACK_BOT_TOKEN` is required
- For Notion integration: `NOTION_TOKEN` is required
- For database storage:
  - By default uses in-memory storage (perfect for scripts and testing)
  - For PostgreSQL: Database configuration variables are required
  - For SQLite: Will be used as fallback if PostgreSQL settings are incomplete
- For file storage: Defaults will be used if not specified

For more details about each setting, see the [Environment Variables](#environment-variables) section.

### LLM Provider Support

Tyler uses LiteLLM under the hood, which means you can use any of the 100+ supported LLM providers by simply configuring the appropriate environment variables. Some popular options include:

```bash
# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key

# Azure OpenAI
AZURE_API_KEY=your-azure-api-key
AZURE_API_BASE=your-azure-endpoint
AZURE_API_VERSION=2023-07-01-preview

# Google VertexAI
VERTEX_PROJECT=your-project-id
VERTEX_LOCATION=your-location

# AWS Bedrock
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION_NAME=your-region
```

When initializing an Agent, you can specify any supported model using the standard model identifier:

```python
# OpenAI
agent = Agent(model_name="gpt-4")

# Anthropic
agent = Agent(model_name="claude-2")

# Azure OpenAI
agent = Agent(model_name="azure/your-deployment-name")

# Google VertexAI
agent = Agent(model_name="chat-bison")

# AWS Bedrock
agent = Agent(model_name="anthropic.claude-v2")
```

For a complete list of supported providers and models, see the [LiteLLM documentation](https://docs.litellm.ai/).

### Quick Start

This example uses in-memory storage which is perfect for scripts and testing. 

```python
from dotenv import load_dotenv 
from tyler import Agent, Thread, Message
import asyncio
import os

# Load environment variables from .env file
load_dotenv()

# Initialize the agent (uses in-memory storage by default)
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with general questions"
)

async def main():
    # Create a new thread
    thread = Thread()

    # Add a user message
    message = Message(
        role="user",
        content="What can you help me with?"
    )
    thread.add_message(message)

    # Process the thread
    processed_thread, new_messages = await agent.go(thread)

    # Print the assistant's response
    for message in new_messages:
        if message.role == "assistant":
            print(f"Assistant: {message.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

See the complete examples in the documentation.

## Running Examples and Tests

Tyler comes with a variety of examples in the `examples/` directory that demonstrate different features and capabilities. These examples can also be run as integration tests to ensure everything is working correctly.

### Running Examples as Tests

The examples are integrated into the test suite with special markers to allow running them separately from unit tests:

```bash
# Run only the example tests
pytest -m examples

# Run only unit tests (excluding examples)
pytest -k "not examples"

# Run all tests (unit tests and examples)
pytest
```

This separation is particularly useful during development, allowing you to run the faster unit tests while making changes, and run the full test suite including examples before committing.

### Example Categories

The examples directory includes demonstrations of:

- Basic agent conversations
- Using built-in and custom tools
- Working with file attachments
- Image and audio processing
- Streaming responses
- MCP (Model Context Protocol) integration

Each example is a standalone Python script that can be run directly or as part of the test suite.

## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0) - see the [LICENSE](LICENSE) file for details.

This means you are free to:
- Share and adapt the work for non-commercial purposes
- Use the software for personal projects
- Modify and distribute the code

But you cannot:
- Use the software for commercial purposes without permission
- Sublicense the code
- Hold the author liable

For commercial use, please contact the author.
