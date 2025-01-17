from flask import Flask, request, make_response, jsonify
from slack_sdk.signature import SignatureVerifier
import os
import streamlit as st
from tools.slack import SlackClient
import logging
from models.agent import Agent
from models.router_agent import RouterAgent
from models.registry import Registry
from database.thread_store import ThreadStore
from utils.helpers import get_tools
import weave
from config import WEAVE_PROJECT, API_HOST, API_PORT
import uuid
import requests
from models.message import Message, Attachment
from models.thread import Thread

# Initialize Weave
weave.init(WEAVE_PROJECT)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load secrets from environment variables or .streamlit/secrets.toml
def get_secret(key):
    return os.environ.get(key) or st.secrets.get(key)

# Set environment variables from secrets
os.environ["SLACK_BOT_TOKEN"] = get_secret("SLACK_BOT_TOKEN")
os.environ["SLACK_SIGNING_SECRET"] = get_secret("SLACK_SIGNING_SECRET")

app = Flask(__name__)

# Initialize shared instances after environment variables are set
slack_client = SlackClient()
thread_store = ThreadStore()

# Initialize agent registry and register agents
agent_registry = Registry()

# Register Ethan, our engineering manager agent
ethan = Agent(
    purpose="Your name is Ethan. You are an enginneering manager at our company.  You are responsible for ensuring that the company's engineering policies are up to date and accurate.  You can also search for information in Notion.",
    notes="""
Some relevant information to help you:
- Our company policies are found in Notion
- Updates to company policies are frequently announced in Notion
- When searching for information in Notion, generalize your search query to find the most relevant information and compare several pages to ensure you have the most accurate information.

You can also edit or comment on engineering policies in Notion.""",
    tools=get_tools("notion")
)
agent_registry.register_agent("Ethan", ethan)

# Register Allan, our financial expert agent
allan = Agent(
    purpose="Your name is Allan. You are an accountant and financial expert at our company. You are responsible for answering financial questions, explaining company financial policies, and providing guidance on financial matters.",
    notes="""
Some relevant information to help you:
- Company financial policies and procedures are documented in Notion
- You can help with questions about:
  - Company financial policies
  - Expense reports and reimbursements
  - Benefits and compensation
  - Budget planning and forecasting
  - Financial reporting and metrics
- When searching for financial information in Notion, make sure to:
  - Cross-reference multiple sources to ensure accuracy
  - Consider the most recent updates to policies
  - Clarify any ambiguities in financial policies
  - Provide clear explanations of complex financial terms

You can search and reference financial documents in Notion to provide accurate information.""",
    tools=get_tools("notion")
)
agent_registry.register_agent("Allan", allan)

# Register Harper agent our HR agent
harper = Agent(
    purpose="""You are a head of HR, and you are responsible for:
- answering questions about the company's HR policies.
- ensuring that the company's HR policies are up to date and accurate.
- giving advice on how to handle HR related issues.""",
    notes="""
Some relevant information to help you:
- Our company policies are found in Notion
- Updates to company policies are frequently announced in Notion
- When searching for information in Notion, generalize your search query to find the most relevant information and compare several pages to ensure you have the most accurate information.

You can also edit or comment on HR policies in Notion.""",
    tools=get_tools("notion")
)
agent_registry.register_agent("Harper", harper)

# Register Maya, our product designer agent
maya = Agent(
    purpose="""You are Maya, the Head of Design at our company. You are responsible for:
- leading and setting the strategic direction for design across the company
- establishing and maintaining UI/UX design best practices
- overseeing our design system and ensuring its consistent implementation
- making key decisions about design patterns and methodologies
- mentoring the design team and reviewing design work
- ensuring all products meet our quality and accessibility standards
- collaborating with engineering and product teams on design implementation""",
    notes="""
Some relevant information to help you:
- Our design system documentation and guidelines are stored in Notion
- Design processes, workflows, and team standards are documented in Notion
- When searching for design information in Notion:
  - Look for established patterns and components
  - Reference our design principles and guidelines
  - Consider accessibility requirements
  - Check for recent design system updates
  - Cross-reference design documentation
  - Review team processes and design review guidelines

As Head of Design, you can make authoritative decisions about design direction and provide strategic guidance based on our established design system.""",
    tools=get_tools("notion")
)
agent_registry.register_agent("Maya", maya)

# Initialize router agent with registry
router_agent = RouterAgent(registry=agent_registry)

# Initialize Slack signature verifier
slack_signature_verifier = SignatureVerifier(os.environ["SLACK_SIGNING_SECRET"])

@app.route("/slack/events", methods=["POST"])
def slack_events():
    """Handle incoming Slack events.
    
    Validates Slack signatures and processes events into the standard message format
    before forwarding to /process/message.
    """
    try:
        data = request.json
        event_type = data.get("type")
        event_id = data.get("event_id")
        event = data.get("event", {})
        
        logger.info(f"Received Slack event - ID: {event_id}, Type: {event_type}, Event: {event.get('type')}, Channel: {event.get('channel')}, Thread: {event.get('thread_ts', event.get('ts'))}, User: {event.get('user')}")
        
        # Verify Slack signature
        if not slack_signature_verifier.is_valid_request(request.get_data(), request.headers):
            logger.warning("Invalid Slack signature received")
            return make_response("Invalid request signature", 403)
            
        # Handle URL verification
        if event_type == "url_verification":
            logger.info("Handling Slack URL verification challenge")
            return jsonify({"challenge": data.get("challenge")})
            
        # Handle event callbacks
        if event_type == "event_callback":
            event = data.get("event", {})
            event_subtype = event.get("type")
            
            # Process both app_mention and message events
            if event_subtype in ["app_mention", "message"] and not event.get("bot_id") and not event.get("subtype"):
                channel = event.get('channel')
                thread_ts = event.get('thread_ts', event.get('ts'))
                user = event.get('user')
                text = event.get('text')
                files = event.get('files', [])  # Get any attached files

                logger.info(f"Processing Slack message - Channel: {channel}, Thread: {thread_ts}, User: {user}, Files: {len(files)}")

                if not all([channel, text, user]):
                    logger.error("Missing required Slack event data", extra={
                        "channel": channel,
                        "text": bool(text),
                        "user": user
                    })
                    return make_response("", 200)

                # Format message for processing
                message_data = {
                    "message": text,
                    "source": {
                        "name": "slack",
                        "thread_id": thread_ts,
                        "channel": channel
                    }
                }

                # Download and attach any files
                if files:
                    message_data["attachments"] = []
                    for file in files:
                        try:
                            # Get file info
                            file_id = file.get('id')
                            filename = file.get('name')
                            mime_type = file.get('mimetype')
                            
                            # Download file content
                            response = slack_client.client.files_info(file=file_id)
                            if response['ok']:
                                file_url = response['file']['url_private']
                                # Download using the bot token for authentication
                                file_response = requests.get(file_url, headers={'Authorization': f'Bearer {slack_client.token}'})
                                if file_response.ok:
                                    message_data["attachments"].append({
                                        "filename": filename,
                                        "content": file_response.content,
                                        "mime_type": mime_type
                                    })
                                else:
                                    logger.error(f"Failed to download file {filename}: {file_response.status_code}")
                            else:
                                logger.error(f"Failed to get file info for {filename}")
                        except Exception as e:
                            logger.error(f"Error processing file attachment: {str(e)}")
                
                # Forward to go
                try:
                    logger.info(f"Forwarding message to go - Thread: {thread_ts}")
                    response = go(message_data)
                    
                    # Check if response is valid
                    if response.status_code != 200:
                        logger.error(f"Error response from go: {response.status_code}")
                        return make_response("", 200)  # Return 200 to Slack but log the error
                        
                    response_data = response.json
                    if not isinstance(response_data, dict):
                        logger.error("Invalid response format from go")
                        return make_response("", 200)
                    
                    # Send new assistant messages to Slack
                    new_messages = response_data.get("new_messages", [])
                    for msg in new_messages:
                        # Skip function messages and messages without content
                        if msg.get("role") == "tool" or not msg.get("content"):
                            continue
                            
                        logger.info(f"Sending response to Slack - Thread: {thread_ts}")
                        slack_client.client.chat_postMessage(
                            channel=channel,
                            text=msg["content"],
                            thread_ts=thread_ts
                        )
                        
                    return make_response("", 200)
                except Exception as e:
                    logger.error(f"Error processing Slack message: {str(e)}", exc_info=True)
                    return make_response("", 200)  # Return 200 to Slack but log the error
    
    except Exception as e:
        logger.error(f"Error handling Slack event: {str(e)}", exc_info=True)
        return make_response("", 200)  # Always return 200 to Slack
        
    return make_response("", 200)

@app.route("/go", methods=["POST"])
def go(message_data=None):
    """Process an incoming message from any source."""
    try:
        # Get message data from request if not provided
        if message_data is None:
            message_data = request.json
            
        logger.info("Processing message", extra={
            "source": message_data.get("source", {}).get("name"),
            "thread_id": message_data.get("source", {}).get("thread_id")
        })
            
        # Validate required fields
        if not isinstance(message_data, dict):
            logger.error("Invalid message_data format")
            return make_response("Invalid request format", 400)
            
        message = message_data.get("message")
        source = message_data.get("source")
        attachments = message_data.get("attachments", [])
        
        # Validate source object
        if not isinstance(source, dict) or not all(k in source for k in ["name", "thread_id"]):
            logger.error("Invalid source format in message_data")
            return make_response("Source must be an object with 'name' and 'thread_id' properties", 400)
            
        if not all([message, source["name"], source["thread_id"]]):
            logger.error("Missing required fields in message_data")
            return make_response("Missing required fields: message, source.name, and source.thread_id", 400)
            
        # Check for duplicate messages by looking up the thread
        thread = thread_store.get(source["thread_id"])
        if thread:
            # Check if the last user message matches this one
            last_user_message = next((msg for msg in reversed(thread.messages) 
                                   if msg.role == "user" and 
                                   msg.source.get("name") == source["name"] and
                                   msg.content == message), None)
            if last_user_message:
                logger.info(f"Duplicate message detected in thread {source['thread_id']} - skipping processing")
                return jsonify({
                    "thread": thread.to_dict(),
                    "new_messages": []
                })
            
        # Always get or create thread first
        if not thread:
            thread = Thread(
                id=source["thread_id"],
                title=message[:30].capitalize() + "..." if len(message) > 30 else message.capitalize(),
                source=source
            )
            logger.info(f"Created new thread with ID: {thread.id}")
        else:
            logger.info(f"Found existing thread with ID: {thread.id}")
        
        # Always create and add the user message to the thread
        user_message = Message(
            role="user",
            content=message,
            source=source,
            attachments=[
                Attachment(
                    filename=att["filename"],
                    content=att["content"],
                    mime_type=att.get("mime_type")
                ) for att in attachments
            ] if attachments else []
        )
        
        thread.add_message(user_message)
        thread_store.save(thread)
        logger.info(f"Added user message to thread {thread.id}")
        
        # Get the appropriate agent from the router
        logger.info(f"Routing message to get appropriate agent")
        agent_name = router_agent.route(thread.id)
        
        if agent_name:
            # Get the agent
            agent = agent_registry.get_agent(agent_name)
            if agent:
                logger.info(f"Selected agent: {agent_name}")
                
                # Process with the agent
                logger.info(f"Processing thread {thread.id} with agent {agent_name}")
                processed_thread, new_messages = agent.go(thread.id)
                
                logger.info(f"Message processing complete - Thread ID: {processed_thread.id}, New messages: {len(new_messages)}")
                
                # Return JSON response with both thread and new messages
                return jsonify({
                    "thread": processed_thread.to_dict(),
                    "new_messages": [msg.model_dump() for msg in new_messages]
                })
            else:
                logger.error(f"Agent {agent_name} not found in registry")
                return make_response(f"Agent {agent_name} not found", 404)
        else:
            logger.info("No appropriate agent found for message")
            # Still return the thread even though no agent was found
            return jsonify({
                "thread": thread.to_dict(),
                "new_messages": []
            })
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return make_response(f"Error: {str(e)}", 500)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    args = parser.parse_args()
    
    app.run(host=API_HOST, port=API_PORT, debug=args.debug) 