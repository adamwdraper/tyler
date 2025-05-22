# Tools with Streaming

This example demonstrates how to combine tool execution with streaming responses, allowing you to build interactive applications that can perform actions while providing real-time feedback.

## Custom Translator Tool Example

In this example, we'll create a custom translator tool and use it with streaming responses:

```python
from dotenv import load_dotenv
from tyler.models.agent import Agent, StreamUpdate, Thread, Message
import asyncio
import logging

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

def custom_translator_implementation(text: str, target_language: str) -> str:
    """
    Implementation of a mock translator tool.
    In a real application, this would use a translation API.
    """
    translations = {
        "spanish": {
            "hello": "hola",
            "world": "mundo",
            "how are you": "¿cómo estás?",
            "good morning": "buenos días"
        },
        "french": {
            "hello": "bonjour",
            "world": "monde",
            "how are you": "comment allez-vous?",
            "good morning": "bonjour"
        }
    }
    
    target_language = target_language.lower()
    text = text.lower()
    
    if target_language not in translations:
        return f"Error: Unsupported target language '{target_language}'"
        
    if text in translations[target_language]:
        return f"Translation: {translations[target_language][text]}"
    else:
        return f"Mock translation to {target_language}: [{text}]"

# Define custom translator tool
custom_translator_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "translate",
            "description": "Translate text to another language",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to translate"
                    },
                    "target_language": {
                        "type": "string",
                        "description": "The target language for translation",
                        "enum": ["Spanish", "French"]
                    }
                },
                "required": ["text", "target_language"]
            }
        }
    },
    "implementation": custom_translator_implementation
}

# Initialize the agent
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with translations and web searches",
    tools=[
        "web",                     # Load the web tools module
        custom_translator_tool,    # Add our translator tool
    ],
    temperature=0.7
)

async def main():
    # Example conversation with translations
    conversations = [
        "How do you say 'hello' in Spanish?",
        "Now translate 'good morning' to French."
    ]

    # Create a single thread for the entire conversation
    thread = Thread()

    for user_input in conversations:
        print(f"\nUser: {user_input}")

        # Add user message to thread
        message = Message(role="user", content=user_input)
        thread.add_message(message)

        print("\nAssistant: ", end='', flush=True)

        # Process the thread using go_stream
        async for update in agent.go_stream(thread):
            if update.type == StreamUpdate.Type.CONTENT_CHUNK:
                # Print content chunks as they arrive
                print(update.data, end='', flush=True)
            elif update.type == StreamUpdate.Type.TOOL_MESSAGE:
                # Print translation results on new lines
                tool_message = update.data
                print(f"\nTranslation: {tool_message.content}")
            elif update.type == StreamUpdate.Type.ERROR:
                # Print any errors that occur
                print(f"\nError: {update.data}")
            elif update.type == StreamUpdate.Type.COMPLETE:
                # Final update contains (thread, new_messages)
                print()  # Add newline after completion

        print("\n" + "-"*50)  # Separator between conversations

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        sys.exit(0)
```

## How It Works

1. **Custom Tool Definition**: We define a custom translator tool with:
   - A function definition that specifies the tool's interface
   - An implementation that handles the actual translation
   - Metadata attributes for categorization

2. **Agent Configuration**: The agent is initialized with:
   - The custom translator tool
   - The web tools module for additional capabilities
   - A specific purpose focused on translations

3. **Streaming Updates**: The code handles different types of streaming updates:
   - `CONTENT_CHUNK`: Partial content from the assistant
   - `TOOL_MESSAGE`: Results from tool executions
   - `ERROR`: Any errors that occur
   - `COMPLETE`: Final state of the conversation

4. **Conversation Flow**:
   - User messages are added to the thread
   - The agent processes each message using `go_stream`
   - Tool results and assistant responses are displayed in real-time
   - The conversation continues with multiple turns

## Best Practices

1. **Tool Design**:
   - Keep tool implementations focused and simple
   - Provide clear parameter descriptions
   - Include error handling for edge cases

2. **Streaming Handling**:
   - Use `flush=True` when printing streamed content
   - Display tool results on new lines for clarity
   - Handle all update types appropriately

3. **Error Management**:
   - Always handle `StreamUpdate.Type.ERROR`
   - Provide graceful error messages
   - Include proper exception handling

4. **User Experience**:
   - Show clear separation between conversations
   - Maintain consistent output formatting
   - Provide immediate feedback for tool operations

## Running the Example

1. Ensure you have Tyler installed:
```bash
pip install tyler-agent
```

2. Set up your environment variables in `.env`:
```bash
OPENAI_API_KEY=your_api_key_here
```

3. Run the example:
```bash
python examples/tools_streaming.py
```

## Expected Output

```
User: How do you say 'hello' in Spanish? 