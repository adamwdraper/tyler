---
sidebar_position: 1
---

# Examples

This section contains examples demonstrating various features and use cases of Tyler.

## Basic Examples

- [Using Tools](./using-tools.md) - Learn how to use built-in and custom tools
- [Basic Streaming](./streaming.md) - Build interactive applications with real-time streaming
- [Tools with Streaming](./tools-streaming.md) - Combine tools with streaming responses
- [Message Attachments](./message-attachments.md) - Work with file attachments in messages
- [Full Configuration](./full-configuration.md) - See all configuration options in action

## Advanced Examples

- [Database Storage](./database-storage.md) - Store threads in SQLite or PostgreSQL
- [File Storage](./file-storage.md) - Store and process files with Tyler
- [Interrupt Tools](./interrupt-tools.md) - Use tools that can interrupt the agent's processing

Each example includes complete code and explanations to help you understand and implement Tyler's features in your applications.

## Quick Links

1. [Using Tools](./using-tools.md) - Learn how to use and create custom tools
2. [Basic Streaming](./streaming.md) - Build real-time interactive applications
3. [Tools with Streaming](./tools-streaming.md) - Combine tools with streaming responses
4. [Full Configuration](./full-configuration.md) - Explore all configuration options
5. [Database Storage](./database-storage.md) - Set up persistent storage
6. [Interrupt Tools](./interrupt-tools.md) - Implement content moderation and control flow
7. [Message Attachments](./message-attachments.md) - Handle file attachments and processing

## Running the Examples

All examples are available in the [examples directory](https://github.com/adamwdraper/tyler/tree/main/examples) of the Tyler repository.

To run any example:

1. Clone the repository:
```bash
git clone https://github.com/adamwdraper/tyler.git
cd tyler
```

2. Install dependencies:
```bash
uv add tyler-agent --dev
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

4. Run an example:
```bash
python examples/2-using_tools.py
```

## Example Structure

Each example in this section includes:
- Complete source code
- Step-by-step explanation
- Key concepts covered
- Configuration requirements
- Expected output

## Prerequisites

Before running the examples, ensure you have:
- Python 3.12.8 or later
- Required system libraries (libmagic, poppler)
- API keys for services used (OpenAI, etc.)
- Database setup (if using PostgreSQL examples)

## Getting Help

If you encounter issues while running the examples:
1. Check the [Configuration Guide](../configuration.md)
2. Search [GitHub Issues](https://github.com/adamwdraper/tyler/issues)
3. Ask in [GitHub Discussions](https://github.com/adamwdraper/tyler/discussions) 