import asyncio
from tyler import Agent, Thread, Message, ThreadStore, FileStore

async def main():
    """
    Demonstrates explicitly creating and setting stores for an Agent.
    """
    # 1. Create default in-memory stores individually.
    #    Calling .create() without arguments defaults to in-memory.
    thread_store = await ThreadStore.create()
    file_store = await FileStore.create()
    print(f"Created in-memory stores:")
    print(f"  Thread Store: {type(thread_store)}")
    print(f"  File Store: {type(file_store)}")
    
    # 2. Initialize the agent with explicit stores.
    #    Pass the store instances directly to the Agent constructor.
    agent = Agent(
        name="StoreAwareAssistant",
        purpose="Answer questions concisely using explicitly set stores.",
        model_name="gpt-4.1", # Using preferred model
        thread_store=thread_store,  # Pass store instance directly
        file_store=file_store       # Pass store instance directly
    )
    print(f"Initialized agent: {agent.name}")
    print("Agent configured with explicit stores.")

    # 3. Create a new thread. Because the agent is configured with stores,
    #    operations like saving the thread will use the provided stores.
    thread = Thread()
    print(f"Created new thread with ID: {thread.id}")

    # 4. Add a user message
    user_message = Message(role="user", content="What is the capital of Spain?")
    thread.add_message(user_message)
    print(f"Added user message: '{user_message.content}'")

    # 5. Run the agent. It will use the configured stores internally.
    print("Running agent...")
    final_thread, new_messages = await agent.go(thread)
    print("Agent finished processing.")

    # 6. Print the assistant's response
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

    # 7. Demonstrate sharing stores between multiple agents
    print("\n--- Sharing Stores Between Agents ---")
    
    # Create a second agent that uses the same stores
    second_agent = Agent(
        name="SecondAssistant", 
        purpose="Another assistant that shares the same storage.",
        model_name="gpt-4.1",
        thread_store=thread_store,  # Same store instance
        file_store=file_store       # Same store instance
    )
    print(f"Created second agent: {second_agent.name}")
    print("Both agents now share the same thread and file stores!")

    # Note: Since the stores are in-memory, the thread data still only exists
    # for the duration of this script run. To persist data, you would provide
    # a database URL to ThreadStore.create and a directory path to FileStore.create
    # 
    # For persistent storage:
    # thread_store = await ThreadStore.create("sqlite+aiosqlite:///threads.db")
    # file_store = await FileStore.create(base_path="./stored_files")

if __name__ == "__main__":
    # Added basic error handling for asyncio run
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}") 