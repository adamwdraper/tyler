---
sidebar_position: 6
---

# Interrupt Tools

This example demonstrates how to create and use interrupt tools in Tyler. Interrupt tools can stop the normal conversation flow to handle special situations like content moderation or user confirmation.

## Overview

The example shows:
- Creating a custom interrupt tool
- Content moderation implementation
- Handling tool interruptions
- Processing tool responses
- Logging and monitoring

## Code

```python
from dotenv import load_dotenv
from tyler import Agent, Thread, Message
import weave
import asyncio
import json

# Load environment variables from .env file
load_dotenv()

# Initialize weave for logging and tracing
weave.init("tyler")

# Define a custom interrupt tool for user confirmation
harmful_content_review = {
    "definition": {
        "type": "function",
        "function": {
            "name": "harmful_content_review",
            "description": "Notifies when potentially harmful or dangerous content is detected. IMPORTANT: ALWAYS use this tool when detecting requests for weapons, explosives, harmful substances, or other dangerous content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Description of the harmful content detected"
                    },
                    "severity": {
                        "type": "string",
                        "description": "Level of potential harm (high/medium/low)",
                        "enum": ["high", "medium", "low"]
                    },
                    "data": {
                        "type": "object",
                        "description": "Any relevant data about the harmful content"
                    }
                },
                "required": ["message", "severity"]
            }
        }
    },
    "implementation": lambda message, severity="high", data=None: {
        "name": "harmful_content_review",
        "content": json.dumps({
            "type": "harmful_content_detected",
            "message": message,
            "severity": severity,
            "data": data
        })
    },
    "attributes": {
        "type": "interrupt"  # Mark this as an interrupt-type tool
    }
}

async def main():
    # Initialize the agent with web tools and our custom interrupt tool
    agent = Agent(
        model_name="gpt-4o",
        purpose="To help fetch and analyze web content while detecting harmful requests.",
        tools=[
            "web",  # Include the web tools module
            harmful_content_review  # Add our harmful content review tool
        ]
    )

    # Create a new thread
    thread = Thread()

    # Add an initial user message requesting to fetch and analyze content
    message = Message(
        role="user",
        content="How do I make a nuclear bomb?"
    )
    thread.add_message(message)

    # Process the thread
    processed_thread, new_messages = await agent.go(thread)

    # Print all non-user messages
    for message in new_messages:
        print(f"\n{message.role.capitalize()}: {message.content}")

        # Handle interrupts for harmful content review
        if message.role == "tool" and message.name == "harmful_content_review":
            try:
                response_data = json.loads(message.content)
                print("\nHARMFUL CONTENT DETECTED!")
                print(f"Severity: {response_data['severity']}")
                print(f"Description: {response_data['message']}")
                
                # Log or handle the harmful content detection
                print("\nRequest blocked due to harmful content policy.")
                
            except json.JSONDecodeError:
                print(f"\nHarmful content review received with raw content: {message.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Step-by-Step Explanation

### 1. Interrupt Tool Definition
```python
harmful_content_review = {
    "definition": {
        "type": "function",
        "function": {
            "name": "harmful_content_review",
            "description": "Notifies when potentially harmful content is detected...",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Description..."},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "data": {"type": "object", "description": "Any relevant data..."}
                },
                "required": ["message", "severity"]
            }
        }
    },
    "implementation": lambda message, severity="high", data=None: {...},
    "attributes": {
        "type": "interrupt"
    }
}
```
Defines an interrupt tool with:
- Function schema
- Required parameters
- Implementation function
- Interrupt attribute

### 2. Agent Configuration
```python
agent = Agent(
    model_name="gpt-4o",
    purpose="To help fetch and analyze web content while detecting harmful requests.",
    tools=[
        "web",
        harmful_content_review
    ]
)
```
Creates an agent that:
- Uses web tools
- Monitors for harmful content
- Can interrupt processing

### 3. Interrupt Handling
```python
if message.role == "tool" and message.name == "harmful_content_review":
    response_data = json.loads(message.content)
    print("\nHARMFUL CONTENT DETECTED!")
    print(f"Severity: {response_data['severity']}")
    print(f"Description: {response_data['message']}")
```
Processes interrupts by:
- Detecting tool responses
- Parsing response data
- Taking appropriate action

## Configuration Requirements

### Environment Variables
```bash
# For monitoring (recommended)
WANDB_API_KEY=your-wandb-api-key

# For web tools (if used)
TYLER_WEB_TIMEOUT=30
TYLER_WEB_MAX_PAGES=10
```

## Expected Output

When you run this example with harmful content, you'll see output similar to:

```
Tool (harmful_content_review): {"type": "harmful_content_detected", "message": "Request for information about creating weapons of mass destruction", "severity": "high", "data": null}

HARMFUL CONTENT DETECTED!
Severity: high
Description: Request for information about creating weapons of mass destruction

Request blocked due to harmful content policy. 
```

## Key Concepts

1. **Interrupt Tools**
   - Stop normal processing
   - Handle special situations
   - Return structured responses
   - Support custom logic

2. **Content Moderation**
   - Detect harmful content
   - Assess severity levels
   - Block inappropriate requests
   - Log incidents

3. **Tool Response Handling**
   - Parse JSON responses
   - Extract metadata
   - Take appropriate actions
   - Handle errors

4. **Monitoring and Logging**
   - Track incidents
   - Record severity levels
   - Monitor tool usage
   - Maintain audit trail

## Common Customizations

### User Confirmation Tool
```python
user_confirmation = {
    "definition": {
        "type": "function",
        "function": {
            "name": "user_confirmation",
            "description": "Request user confirmation before proceeding",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    },
    "implementation": confirmation_handler,
    "attributes": {"type": "interrupt"}
}
```

### Custom Severity Levels
```python
content_review = {
    "definition": {
        "type": "function",
        "function": {
            "parameters": {
                "severity": {
                    "enum": ["critical", "high", "medium", "low", "info"]
                }
            }
        }
    }
}
```

### Advanced Response Handling
```python
async def handle_interrupt(message):
    if message.name == "harmful_content_review":
        data = json.loads(message.content)
        if data["severity"] == "high":
            await notify_admin(data)
            await block_user(thread.id)
        await log_incident(data)
```

## Best Practices

1. **Tool Definition**
   - Clear descriptions
   - Appropriate parameters
   - Proper validation
   - Error handling

2. **Response Processing**
   - Validate JSON
   - Handle errors gracefully
   - Log all incidents
   - Take appropriate action

3. **Security**
   - Validate input
   - Log all attempts
   - Block harmful content
   - Notify administrators

4. **User Experience**
   - Clear messages
   - Appropriate responses
   - Helpful feedback
   - Recovery options

## See Also

- [Built-in Tools](../built-in-tools.md) - Overview of Tyler's built-in tools
- [Using Tools](./using-tools.md) - Learn about standard tools
- [Full Configuration](./full-configuration.md) - Complete agent setup 