import pytest
from unittest.mock import patch, MagicMock
import asyncio
from tyler.tools.slack import (
    SlackClient,
    post_to_slack,
    generate_slack_blocks,
    send_ephemeral_message,
    reply_in_thread
)

@pytest.fixture
def mock_env_token(monkeypatch):
    """Fixture to mock SLACK_BOT_TOKEN environment variable"""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "mock-token")

@pytest.fixture
def mock_slack_client():
    """Fixture to create a mock Slack client"""
    with patch('slack_sdk.WebClient') as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.chat_postMessage.return_value = {"ok": True}
        mock_instance.chat_postEphemeral.return_value = {"ok": True}
        yield mock_instance

def test_slack_client_init_missing_token(monkeypatch):
    """Test SlackClient initialization with missing token"""
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="SLACK_BOT_TOKEN environment variable is required"):
        SlackClient()

def test_slack_client_init(mock_env_token):
    """Test SlackClient initialization with token"""
    client = SlackClient()
    assert client.token == "mock-token"

@patch('tyler.tools.slack.SlackClient')
def test_post_to_slack(mock_slack_client):
    """Test posting messages to Slack"""
    mock_instance = MagicMock()
    mock_instance.client.chat_postMessage.return_value = {"ok": True}
    mock_slack_client.return_value = mock_instance

    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test message"}}]

    # Test with channel name without #
    result = post_to_slack(channel="general", blocks=blocks)
    assert result is True
    mock_instance.client.chat_postMessage.assert_called_with(
        channel="#general",
        blocks=blocks,
        text="Test message"
    )

    # Test with channel name with #
    result = post_to_slack(channel="#random", blocks=blocks)
    assert result is True
    mock_instance.client.chat_postMessage.assert_called_with(
        channel="#random",
        blocks=blocks,
        text="Test message"
    )

    # Test with channel ID and explicit text
    result = post_to_slack(channel="C1234567890", blocks=blocks, text="Custom text")
    assert result is True
    mock_instance.client.chat_postMessage.assert_called_with(
        channel="C1234567890",
        blocks=blocks,
        text="Custom text"
    )

@patch('litellm.acompletion')
@pytest.mark.asyncio
async def test_generate_slack_blocks(mock_acompletion):
    """Test generating Slack blocks from content"""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "Test content"}}], "text": "Test content plain text"}'
            )
        )
    ]
    mock_acompletion.return_value = mock_response

    result = await generate_slack_blocks(content="Test content")
    assert isinstance(result, dict)
    assert "blocks" in result
    assert "text" in result
    assert result["blocks"][0]["type"] == "section"
    assert result["blocks"][0]["text"]["text"] == "Test content"
    assert result["text"] == "Test content plain text"

    # Test error handling with invalid JSON response
    mock_response.choices[0].message.content = "Invalid JSON"
    result = await generate_slack_blocks(content="Test content")
    assert isinstance(result, dict)
    assert "blocks" in result
    assert "text" in result
    assert isinstance(result["blocks"], list)
    assert len(result["blocks"]) > 0
    assert "type" in result["blocks"][0]
    assert "text" in result["blocks"][0]
    assert "Error" in result["blocks"][0]["text"]["text"]

@patch('tyler.tools.slack.SlackClient')
def test_send_ephemeral_message(mock_slack_client):
    """Test sending ephemeral messages"""
    mock_instance = MagicMock()
    mock_instance.client.chat_postEphemeral.return_value = {"ok": True}
    mock_slack_client.return_value = mock_instance

    result = send_ephemeral_message(
        channel="general",
        user="U123",
        text="Test message"
    )
    
    assert result is True
    mock_instance.client.chat_postEphemeral.assert_called_with(
        channel="general",
        user="U123",
        text="Test message"
    )

@patch('tyler.tools.slack.SlackClient')
def test_reply_in_thread(mock_slack_client):
    """Test replying in threads"""
    mock_instance = MagicMock()
    mock_instance.client.chat_postMessage.return_value = {"ok": True}
    mock_slack_client.return_value = mock_instance

    result = reply_in_thread(
        channel="general",
        thread_ts="1234567890.123",
        text="Test reply",
        broadcast=True
    )
    
    assert result is True
    mock_instance.client.chat_postMessage.assert_called_with(
        channel="general",
        thread_ts="1234567890.123",
        text="Test reply",
        reply_broadcast=True
    )

def test_error_handling_in_functions(mock_env_token, mock_slack_client):
    """Test error handling in Slack functions"""
    # Set up error behavior for all Slack API calls
    mock_slack_client.chat_postMessage.side_effect = Exception("API Error")
    mock_slack_client.chat_postEphemeral.side_effect = Exception("API Error")
    
    # Test error handling in post_to_slack
    result = post_to_slack(channel="general", blocks=[])
    assert result is False

    # Test error handling in send_ephemeral_message
    result = send_ephemeral_message(channel="general", user="U123", text="test")
    assert result is False

    # Test error handling in reply_in_thread
    result = reply_in_thread(channel="general", thread_ts="123", text="test")
    assert result is False 