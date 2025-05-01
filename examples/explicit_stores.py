import asyncio
from tyler import Agent, Thread, Message, ThreadStore, FileStore
# Import the individual store classes and registration functions
from tyler.utils.registry import register_thread_store, register_file_store

async def main():
    """
    Demonstrates explicitly creating and setting default in-memory stores for an Agent.
    """
    # 1. Create default in-memory stores individually.
    #    Calling .create() without arguments defaults to in-memory.
    thread_store = await ThreadStore.create()
    file_store = await FileStore.create()
    print(f"Created in-memory stores:")
    print(f"  Thread Store: {type(thread_store)}")
    print(f"  File Store: {type(file_store)}")
    
    # 2. Register the stores in the global registry under the name "default".
    register_thread_store("default", thread_store)
    register_file_store("default", file_store)
    print(f"Registered stores with name 'default'")

    # 3. Initialize the agent.
    #    It doesn't know about the stores yet.
    agent = Agent(
        name="StoreAwareAssistant",
        purpose="Answer questions concisely using explicitly set stores.",
        model_name="gpt-4o" # Using preferred model
    )
    print(f"Initialized agent: {agent.name}")

    # 4. Explicitly configure the agent to use the stores named 'default'
    #    from the registry. The agent will now look these up when needed.
    agent.set_stores(thread_store_name="default", file_store_name="default")
    print("Agent configured to use 'default' stores from registry.")

    # 5. Create a new thread. Because the agent is configured,
    #    operations like saving the thread will use the registered 'default' ThreadStore.
    thread = Thread()
    print(f"Created new thread with ID: {thread.id}")

    # 6. Add a user message
    user_message = Message(role="user", content="What is the capital of Spain?")
    thread.add_message(user_message)
    print(f"Added user message: '{user_message.content}'")

    # 7. Run the agent. It will use the configured stores internally.
    print("Running agent...")
    final_thread, new_messages = await agent.go(thread)
    print("Agent finished processing.")

    # 8. Print the assistant's response
    if new_messages:
        # Filter for the actual assistant response (last non-tool message)
        assistant_message = next((msg for msg in reversed(new_messages) if msg.role == 'assistant'), None)
        if assistant_message:
            print(f"Assistant Response: {assistant_message.content}")
        else:
            print("No assistant message found in new messages.")
            print("All new messages:", new_messages)
    else:
        print("No new messages were generated.")

    # Note: Since the stores are in-memory, the thread data still only exists
    # for the duration of this script run. To persist data, you would provide
    # a database URL to ThreadStore.create and a directory path to FileStore.create

if __name__ == "__main__":
    # Added basic error handling for asyncio run
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}") 