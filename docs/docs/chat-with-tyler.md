---
sidebar_position: 4
---

# Chat with Tyler

Tyler provides two interactive interfaces for chatting with your agent:
1. A web-based chat interface
2. A command-line interface (CLI)

## Web interface

The web interface is available as a separate repository at [tyler-chat](https://github.com/adamwdraper/tyler-chat).

### Features

- Modern, responsive design
- Real-time streaming responses
- File attachment support
- Message history
- Tool execution visualization
- Weave monitoring integration

### Installation

```bash
# Clone the repository
git clone https://github.com/adamwdraper/tyler-chat.git
cd tyler-chat

# Install dependencies
npm install

# Start the development server
npm run dev
```

### Configuration

Create a `.env` file in the project root:

```bash
# Tyler API configuration
TYLER_API_URL=http://localhost:8000
TYLER_API_KEY=your-api-key

# Optional Weave configuration
WANDB_API_KEY=your-wandb-api-key
```

### Usage

1. Start the development server:
```bash
npm run dev
```

2. Open your browser to `http://localhost:3000`

3. Start chatting with your agent!

## Command line interface

The CLI is included with the Tyler package and provides a simple way to interact with your agent from the terminal.

### Installation

The CLI is installed automatically when you install Tyler:

```bash
pip install tyler-agent
```

### Basic usage

Start a chat session:

```bash
tyler-chat
```

With custom configuration:

```bash
tyler-chat --model gpt-4.1 --purpose "Technical support"
```

### Available commands

During a chat session:
- `/help` - Show available commands
- `/clear` - Clear the conversation
- `/exit` - End the chat session
- `/save` - Save the conversation
- `/load` - Load a saved conversation
- `/tools` - List available tools
- `/purpose` - Show/set agent purpose
- `/model` - Show/change model
- `/system` - Show/set system prompt

### Configuration

The CLI uses the same configuration as the main Tyler package. Set your environment variables in a `.env` file:

```bash
# Required
OPENAI_API_KEY=your-openai-api-key

# Optional
WANDB_API_KEY=your-wandb-api-key
TYLER_DB_TYPE=postgresql
TYLER_DB_URL=postgresql://user:pass@localhost/db
```

## Next steps

- Learn about [Configuration](./configuration.md)
- Explore [Examples](./category/examples)
- Read the [API reference](./category/api-reference)

## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0).

For commercial use, please contact the author.