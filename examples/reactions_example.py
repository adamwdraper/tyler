#!/usr/bin/env python3
"""
Example demonstrating how to use message reactions in Tyler.

This example shows how to:
1. Add reactions to messages
2. Remove reactions from messages
3. Get reactions for a message
4. Save/load threads with reactions to/from the database
"""

import asyncio
from typing import Dict, List
from tyler import Thread, Message, ThreadStore

async def main():
    # Create an in-memory ThreadStore for this example
    thread_store = await ThreadStore.create()
    
    # Create a new thread with some messages
    thread = Thread(title="Reactions Example")
    
    # Add some messages to the thread
    user_msg = Message(role="user", content="Hello! I have a question about reactions.")
    thread.add_message(user_msg)
    
    assistant_msg = Message(role="assistant", content="Sure, I'd be happy to help with reactions!")
    thread.add_message(assistant_msg)
    
    user_msg2 = Message(role="user", content="How do I add a thumbs up?")
    thread.add_message(user_msg2)
    
    assistant_msg2 = Message(role="assistant", content="It's easy! Just click the emoji button.")
    thread.add_message(assistant_msg2)
    
    # Print the thread messages
    print(f"Thread '{thread.title}' has {len(thread.messages)} messages:")
    for msg in thread.messages:
        print(f"  - {msg.role}: {msg.content}")
    print()
    
    # Add reactions to messages
    print("Adding reactions...")
    
    # User 1 adds thumbs up to assistant's first message
    thread.add_reaction(assistant_msg.id, ":thumbsup:", "user1")
    
    # User 2 also adds thumbs up to the same message
    thread.add_reaction(assistant_msg.id, ":thumbsup:", "user2")
    
    # User 1 adds heart to assistant's second message
    thread.add_reaction(assistant_msg2.id, ":heart:", "user1")
    
    # User 3 adds rocket to assistant's second message
    thread.add_reaction(assistant_msg2.id, ":rocket:", "user3")
    
    # Display reactions
    print("\nReactions after adding:")
    for msg in thread.messages:
        if msg.reactions:
            print(f"Message '{msg.content}' has reactions:")
            for emoji, users in msg.reactions.items():
                print(f"  - {emoji}: {', '.join(users)}")
    
    # Remove a reaction
    print("\nRemoving User 1's heart reaction from second message...")
    thread.remove_reaction(assistant_msg2.id, ":heart:", "user1")
    
    # Display reactions after removal
    print("\nReactions after removal:")
    for msg in thread.messages:
        if msg.reactions:
            print(f"Message '{msg.content}' has reactions:")
            for emoji, users in msg.reactions.items():
                print(f"  - {emoji}: {', '.join(users)}")
    
    # Save thread to database
    print("\nSaving thread to database...")
    await thread_store.save(thread)
    
    # Retrieve thread from database
    print("Retrieving thread from database...")
    retrieved_thread = await thread_store.get(thread.id)
    
    # Display reactions from retrieved thread
    print("\nReactions in retrieved thread:")
    for msg in retrieved_thread.messages:
        if msg.reactions:
            print(f"Message '{msg.content}' has reactions:")
            for emoji, users in msg.reactions.items():
                print(f"  - {emoji}: {', '.join(users)}")
    
    print("\nExample completed successfully!")


if __name__ == "__main__":
    asyncio.run(main()) 