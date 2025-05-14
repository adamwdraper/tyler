import os
import json
import slack_sdk
import weave
from typing import List, Dict, Optional, Union
import litellm

class SlackClient:
    def __init__(self):
        self.token = os.environ.get("SLACK_BOT_TOKEN")
        if not self.token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is required")
        
        self.client = slack_sdk.WebClient(token=self.token)

@weave.op(name="slack-post_to_slack")
def post_to_slack(*, channel: str, blocks: List[Dict], text: str = None) -> bool:
    """
    Post blocks to a specified Slack channel.

    Args:
        channel (str): The Slack channel to post to. Can be either:
            - A channel ID starting with 'C'
            - A channel name (with or without '#' prefix)
        blocks (List[Dict]): A list of block kit blocks to be posted to Slack.
        text (str, optional): Text to use as fallback content and for notifications.

    Returns:
        bool: True if the message was posted successfully, False otherwise.
    """
    try:
        # If it's not a channel ID (doesn't start with 'C'), treat as channel name
        if not channel.startswith('C'):
            if not channel.startswith('#'):
                channel = f'#{channel}'

        # Extract fallback text from first text block if not provided
        fallback_text = text
        if not fallback_text and blocks:
            for block in blocks:
                if block.get('type') == 'section' and block.get('text', {}).get('text'):
                    fallback_text = block['text']['text']
                    break
        
        if not fallback_text:
            fallback_text = "Message with block content"

        client = SlackClient().client
        response = client.chat_postMessage(
            channel=channel, 
            blocks=blocks,
            text=fallback_text
        )
        return response['ok']
    except Exception as e:
        print(f"Error posting to Slack: {str(e)}")
        return False

@weave.op(name="slack-generate_slack_blocks")
async def generate_slack_blocks(*, content: str) -> dict:
    """
    Generate Slack blocks from the given content using a chat completion.

    Args:
        content (str): The content to be formatted for Slack.

    Returns:
        dict: A dictionary with 'blocks' containing Slack blocks and 'text' containing a plain text fallback.
    """
    prompt = f"""
    Convert the following content into Slack blocks format:
    ```
    {content}
    ```

    IMPORTANT GUIDELINES:
    - Use ONLY official Slack block types: section, context, divider, image, actions, header, input, file, video, markdown
    - For bullet points or lists, use a section block with markdown formatting using * or •
    - Do not use any custom or unsupported block types
    - When using mrkdwn text type in section or context blocks, format links as <URL|text> NOT as [text](URL)
    - The markdown block type does support standard markdown links [text](URL)

    Respond with JSON containing two fields:
    1. 'blocks': An array of Slack blocks where each block has a 'type' field
    2. 'text': A plain text version (no markdown) for accessibility/fallback

    Important: The 'blocks' array should contain properly formatted Slack blocks.
    """

    try:
        # Use the async version of litellm.completion
        response = await litellm.acompletion(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        raw_content = response.choices[0].message.content.strip()

        # Attempt to parse the JSON
        try:
            generated_response = json.loads(raw_content)
        except json.JSONDecodeError as json_err:            
            # Attempt to clean the content and parse again
            cleaned_content = raw_content.strip('`').strip()
            if cleaned_content.startswith('json'):
                cleaned_content = cleaned_content[4:].strip()
            
            try:
                generated_response = json.loads(cleaned_content)
            except json.JSONDecodeError:
                # If it still fails, return a simple block with error message
                return {
                    "blocks": [{
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Error: Unable to generate valid Slack blocks."
                        }
                    }],
                    "text": content  # Return original content as fallback
                }

        # Handle different response formats and ensure we return blocks and text
        blocks = None
        text_fallback = content  # Default to original content if extraction fails
        
        # First, try to extract the blocks based on the response format
        if isinstance(generated_response, dict):
            if 'blocks' in generated_response:
                blocks = generated_response['blocks']
                if 'text' in generated_response:
                    text_fallback = generated_response['text']
            elif 'type' in generated_response:
                # It's a single block
                blocks = [generated_response]
        elif isinstance(generated_response, list):
            if len(generated_response) > 0 and isinstance(generated_response[0], dict):
                if 'blocks' in generated_response[0]:
                    # It's like [{"blocks": [...]}]
                    blocks = generated_response[0]['blocks']
                    if 'text' in generated_response[0]:
                        text_fallback = generated_response[0]['text']
                elif 'type' in generated_response[0]:
                    # It's a list of blocks
                    blocks = generated_response
        
        # If we couldn't extract blocks, create a simple text section
        if not blocks:
            blocks = [{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": content
                }
            }]
            
        # Validate and transform blocks
        valid_block_types = ["section", "context", "divider", "image", "actions", "header", "input", "file", "video", "markdown"]
        for i, block in enumerate(blocks):
            if not isinstance(block, dict) or 'type' not in block:
                # Replace any invalid blocks with a text section
                blocks[i] = {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Invalid block structure detected and repaired."
                    }
                }
            elif block["type"] not in valid_block_types:
                # Convert any invalid block type to a section
                # Try to extract useful text content
                text_content = "Content converted from unsupported block type"
                
                # Try to get text from text field (common in many blocks)
                if isinstance(block.get('text'), dict) and 'text' in block['text']:
                    text_content = block['text']['text']
                # Try to get text from any elements
                elif isinstance(block.get('elements'), list):
                    texts = []
                    for element in block['elements']:
                        if isinstance(element, dict) and 'text' in element:
                            texts.append(element['text'])
                    if texts:
                        text_content = "\n• " + "\n• ".join(texts)
                
                blocks[i] = {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text_content
                    }
                }
        
        # Return both blocks and text fallback
        return {
            "blocks": blocks,
            "text": text_fallback
        }

    except Exception as e:
        # Handle any other exceptions
        error_message = f"An error occurred while generating Slack blocks: {str(e)}"
        return {
            "blocks": [{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": error_message
                }
            }],
            "text": content  # Return original content as fallback
        }

@weave.op(name="slack-send_ephemeral_message")
def send_ephemeral_message(*, channel: str, user: str, text: str) -> bool:
    """Send an ephemeral message that's only visible to a specific user."""
    try:
        client = SlackClient().client
        response = client.chat_postEphemeral(
            channel=channel,
            user=user,
            text=text
        )
        return response['ok']
    except Exception as e:
        print(f"Error sending ephemeral message: {str(e)}")
        return False

@weave.op(name="slack-reply_in_thread")
def reply_in_thread(*, channel: str, thread_ts: str, text: str, broadcast: Optional[bool] = False) -> bool:
    """Reply to a message in a thread."""
    try:
        client = SlackClient().client
        response = client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=text,
            reply_broadcast=broadcast
        )
        return response['ok']
    except Exception as e:
        print(f"Error replying in thread: {str(e)}")
        return False

@weave.op(name="slack-create_channel")
def create_channel(*, name: str, is_private: bool = False) -> Optional[str]:
    """
    Create a new Slack channel.

    Args:
        name (str): The name of the channel to create. Should only contain lowercase letters, numbers, and hyphens.
        is_private (bool, optional): Whether to create a private channel. Defaults to False.

    Returns:
        Optional[str]: The ID of the created channel if successful, None otherwise.
    """
    try:
        # Clean the channel name to match Slack's requirements
        clean_name = name.lower().replace(' ', '-')
        
        client = SlackClient().client
        if is_private:
            response = client.conversations_create(
                name=clean_name,
                is_private=True
            )
        else:
            response = client.conversations_create(
                name=clean_name
            )
        
        if response['ok']:
            return response['channel']['id']
        return None
    except Exception as e:
        print(f"Error creating Slack channel: {str(e)}")
        return None

@weave.op(name="slack-invite_to_channel")
def invite_to_channel(*, channel: str, user: str) -> bool:
    """
    Invite a user to a Slack channel.

    Args:
        channel (str): The channel ID or name to invite the user to. If name is provided, the '#' symbol will be added if not present.
        user (str): The user ID to invite to the channel.

    Returns:
        bool: True if the invitation was successful, False otherwise.
    """
    try:
        client = SlackClient().client
        
        # If channel name is provided instead of ID, try to get the ID
        if not channel.startswith('C'):  # Slack channel IDs start with 'C'
            if not channel.startswith('#'):
                channel = f'#{channel}'
            try:
                response = client.conversations_list()
                for ch in response['channels']:
                    if ch['name'] == channel[1:]:  # Remove # from channel name
                        channel = ch['id']
                        break
            except Exception as e:
                print(f"Error finding channel ID: {str(e)}")
                return False

        response = client.conversations_invite(
            channel=channel,
            users=[user]
        )
        return response['ok']
    except Exception as e:
        print(f"Error inviting user to channel: {str(e)}")
        return False
    
TOOLS = [
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "slack-post_to_slack",
                "description": "Posts a message to Slack. Important: understand the correct channel to post to from the user's message. Always ask the user for a channel if they haven't specified one. Do not post to very public channels like #general, unless specifically asked to.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "The Slack channel to post to"
                        },
                        "blocks": {
                            "type": "array",
                            "description": "The blocks to post to Slack",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "text": {"type": "object"}
                                }
                            }
                        },
                        "text": {
                            "type": "string",
                            "description": "Text to use as fallback content and for notifications"
                        }
                    },
                    "required": ["channel", "blocks"]
                }
            }
        },
        "implementation": post_to_slack
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "slack-generate_slack_blocks",
                "description": "Generates Slack blocks from content. Always use this when posting to slack to format complex messages to improve readability.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The content to be formatted for Slack"
                        }
                    },
                    "required": ["content"]
                }
            }
        },
        "implementation": generate_slack_blocks
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "slack-send_ephemeral_message",
                "description": "Sends an ephemeral message (only visible to a specific user) in a channel",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "The channel to send the message to"
                        },
                        "user": {
                            "type": "string",
                            "description": "The user ID who should see the message"
                        },
                        "text": {
                            "type": "string",
                            "description": "The message text"
                        }
                    },
                    "required": ["channel", "user", "text"]
                }
            }
        },
        "implementation": send_ephemeral_message
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "slack-reply_in_thread",
                "description": "Replies to a message in a thread",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "The channel containing the parent message"
                        },
                        "thread_ts": {
                            "type": "string",
                            "description": "The timestamp of the parent message"
                        },
                        "text": {
                            "type": "string",
                            "description": "The reply text"
                        },
                        "broadcast": {
                            "type": "boolean",
                            "description": "Whether to also broadcast the reply to the channel"
                        }
                    },
                    "required": ["channel", "thread_ts", "text"]
                }
            }
        },
        "implementation": reply_in_thread
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "slack-create_channel",
                "description": "Creates a new Slack channel",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the channel to create (will be automatically converted to lowercase and hyphens)"
                        },
                        "is_private": {
                            "type": "boolean",
                            "description": "Whether to create a private channel"
                        }
                    },
                    "required": ["name"]
                }
            }
        },
        "implementation": create_channel
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "slack-invite_to_channel",
                "description": "Invites a user to a Slack channel",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "The channel ID or name to invite the user to"
                        },
                        "user": {
                            "type": "string",
                            "description": "The user ID to invite to the channel"
                        }
                    },
                    "required": ["channel", "user"]
                }
            }
        },
        "implementation": invite_to_channel
    }
]