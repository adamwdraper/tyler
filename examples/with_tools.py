from tyler.models.agent import Agent
from tyler.models.thread import Thread, Message

def get_weather_implementation(location: str) -> str:
    """
    Implementation of the weather tool.
    In a real application, this would call a weather API.
    """
    # This is a mock implementation
    return f"The weather in {location} is sunny with a temperature of 72°F"

# Define custom weather tool with both definition and implementation
weather_tool = {
    # The OpenAI function definition that the LLM will use
    "definition": {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and country"
                    }
                },
                "required": ["location"]
            }
        }
    },
    # The actual implementation that will be called
    "implementation": get_weather_implementation
}

# Initialize agent with both built-in and custom tools in a single list
agent = Agent(
    model_name="gpt-4",
    purpose="To help with weather information and web browsing",
    # Combine built-in module names and custom tools with implementations
    tools=["web", weather_tool]
)

# Create a thread with a user question
thread = Thread()
message = Message(
    role="user",
    content="What's the weather like in San Francisco? Also, can you check the top news from bbc.com?"
)
thread.add_message(message)

# Process the thread - the agent will use both the weather tool and web tools
processed_thread, new_messages = agent.go(thread.id)

# Print all non-user messages (assistant responses and tool results)
for message in new_messages:
    print(f"{message.role.capitalize()}: {message.content}") 