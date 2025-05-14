---
sidebar_position: 2
---

# Installation Guide

This guide will walk you through the process of installing Tyler and setting up your development environment on macOS.

## System Requirements

### Python Version
Tyler requires Python 3.12.8 or later. You can check your Python version by running:

```bash
python --version
```

If you need to install or update Python, visit the [official Python website](https://www.python.org/downloads/).

### System Dependencies
Tyler requires some system libraries for processing PDFs and images. Install them using Homebrew:

```bash
brew install libmagic poppler
```

## Installation Methods

### From PyPI (Recommended)
Install the latest version from PyPI:

```bash
pip install tyler-agent
```

### Development Installation
For contributing or development:

```bash
# Clone the repository
git clone https://github.com/adamwdraper/tyler.git
cd tyler

# Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate

# Install in development mode with all dependencies
pip install -e ".[dev]"
```

## Configuration

### Environment Variables
Create a `.env` file in your project directory. You can start by copying the example:

```bash
curl -O https://raw.githubusercontent.com/adamwdraper/tyler/main/.env.example
cp .env.example .env
```

Edit the `.env` file with your settings. The minimal required configuration is:

```bash
# OpenAI API Key (or other LLM provider)
OPENAI_API_KEY=your-api-key-here
```

For a complete list of available configuration options, see the [Configuration Guide](./configuration.md).

## Verifying Installation

You can verify your installation by running a simple test:

```python
from tyler import Agent, Thread, Message
import asyncio

async def test_installation():
    agent = Agent(
        model_name="gpt-4.1",
        purpose="To test the installation"
    )
    thread = Thread()
    message = Message(
        role="user",
        content="Hello! Are you working correctly?"
    )
    thread.add_message(message)
    
    processed_thread, new_messages = await agent.go(thread)
    
    for message in new_messages:
        if message.role == "assistant":
            print(f"Assistant: {message.content}")

if __name__ == "__main__":
    asyncio.run(test_installation())
```

If everything is set up correctly, you should see a response from the AI assistant.

## Next Steps

Now that you have Tyler installed, head over to the [Quickstart guide](./quickstart.md) to learn how to create your first AI agent. 