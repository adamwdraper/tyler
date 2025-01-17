import pytest
from unittest.mock import patch, MagicMock
from flask import Flask, jsonify
import json
import os
from models.router_agent import RouterAgent
from models.thread import Thread
from models.message import Message

# Mock weave.init and litellm before importing api
with patch('weave.init') as mock_weave_init, \
     patch('litellm.completion') as mock_completion:
    mock_completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test response"))]
    )
    from api import app, slack_client, router_agent, thread_store

@pytest.fixture
def client():
    """Test client fixture"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_slack_signature():
    """Mock valid Slack signature verification"""
    with patch('slack_sdk.signature.SignatureVerifier.is_valid_request') as mock:
        mock.return_value = True
        yield mock

@pytest.fixture
def mock_slack_client():
    """Mock Slack client"""
    with patch('api.slack_client.client') as mock:
        mock.chat_postMessage.return_value = {"ok": True, "ts": "123.456"}
        mock.files_info.return_value = {
            "ok": True,
            "file": {
                "url_private": "https://test.com/file.txt"
            }
        }
        yield mock

@pytest.fixture
def mock_thread_store():
    """Mock thread store"""
    with patch('api.thread_store') as mock:
        yield mock

@pytest.fixture
def mock_router_agent():
    """Mock router agent"""
    with patch('api.router_agent') as mock:
        yield mock

@pytest.fixture
def mock_requests():
    """Mock requests for file downloads"""
    with patch('requests.get') as mock:
        mock.return_value = MagicMock(
            ok=True,
            content=b"test file content"
        )
        yield mock

@pytest.fixture
def mock_agent_registry():
    """Mock agent registry"""
    with patch('api.agent_registry') as mock:
        mock_agent = MagicMock()
        mock_thread = MagicMock(spec=Thread)
        mock_thread.id = "test-thread-id"
        mock_thread.to_dict.return_value = {"id": "test-thread-id"}
        mock_message = MagicMock(spec=Message)
        mock_message.model_dump.return_value = {"role": "assistant", "content": "Test response"}
        mock_agent.go.return_value = (mock_thread, [mock_message])
        mock.get_agent.return_value = mock_agent
        yield mock

@pytest.fixture
def mock_go():
    """Mock go function"""
    with patch('api.go') as mock:
        with app.app_context():
            mock.return_value = jsonify({
                "thread": {"id": "test-thread-id"},
                "new_messages": [{"role": "assistant", "content": "Test response"}]
            })
        yield mock

def test_slack_events_url_verification(client, mock_slack_signature):
    """Test URL verification challenge"""
    challenge = "test_challenge"
    response = client.post('/slack/events',
                          json={"type": "url_verification", "challenge": challenge},
                          headers={"X-Slack-Signature": "valid", "X-Slack-Request-Timestamp": "123"})
    
    assert response.status_code == 200
    assert response.json == {"challenge": challenge}
    assert response.content_type == "application/json"

def test_slack_events_invalid_signature(client):
    """Test request with invalid Slack signature"""
    with patch('slack_sdk.signature.SignatureVerifier.is_valid_request') as mock:
        mock.return_value = False
        response = client.post('/slack/events',
                             json={"type": "event_callback"},
                             headers={"X-Slack-Signature": "invalid", "X-Slack-Request-Timestamp": "123"})
        
        assert response.status_code == 403
        assert response.data.decode() == "Invalid request signature"

def test_slack_events_app_mention(client, mock_slack_signature, mock_router_agent, mock_slack_client, mock_agent_registry, mock_thread_store):
    """Test handling app mention events"""
    event_data = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "user": "U123",
            "text": "Hello <@bot>",
            "ts": "123.456",
            "channel": "C123"
        }
    }
    
    # First call to thread_store.get returns None (new thread)
    mock_thread_store.get.side_effect = [
        None,  # First call when checking for existing thread
        MagicMock(  # Second call in go
            spec=Thread,
            id="123.456",
            messages=[
                MagicMock(
                    role="user",
                    content="Hello <@bot>",
                    source={"name": "slack"}
                )
            ],
            to_dict=lambda: {"id": "123.456"}
        )
    ]
    
    # Mock router agent response
    mock_router_agent.route.return_value = "test_agent"
    
    # Mock agent response
    mock_agent = MagicMock()
    mock_thread = MagicMock(spec=Thread)
    mock_thread.id = "123.456"
    mock_thread.to_dict.return_value = {"id": "123.456"}
    mock_agent.go.return_value = (mock_thread, [
        MagicMock(
            role="assistant",
            content="Test response",
            model_dump=lambda: {"role": "assistant", "content": "Test response"}
        )
    ])
    mock_agent_registry.get_agent.return_value = mock_agent
    
    response = client.post('/slack/events',
                          json=event_data,
                          headers={"X-Slack-Signature": "valid", "X-Slack-Request-Timestamp": "123"})
    
    assert response.status_code == 200
    
    # Verify the flow
    assert mock_thread_store.get.call_count >= 1
    mock_router_agent.route.assert_called_once_with("123.456")
    mock_agent_registry.get_agent.assert_called_once_with("test_agent")
    mock_slack_client.chat_postMessage.assert_called_with(
        channel="C123",
        text="Test response",
        thread_ts="123.456"
    )

def test_slack_events_with_file_attachment(client, mock_slack_signature, mock_slack_client, mock_requests, mock_router_agent, mock_go):
    """Test handling Slack events with file attachments"""
    event_data = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "user": "U123",
            "text": "Here's a file",
            "ts": "123.456",
            "channel": "C123",
            "files": [{
                "id": "F123",
                "name": "test.txt",
                "mimetype": "text/plain"
            }]
        }
    }
    
    # Mock router_agent.route to return an agent name
    mock_router_agent.route.return_value = "test_agent"
    
    response = client.post('/slack/events',
                          json=event_data,
                          headers={"X-Slack-Signature": "valid", "X-Slack-Request-Timestamp": "123"})
    
    assert response.status_code == 200
    mock_slack_client.files_info.assert_called_once_with(file="F123")
    mock_requests.assert_called_once()
    mock_slack_client.chat_postMessage.assert_called_with(
        channel="C123",
        text="Test response",
        thread_ts="123.456"
    )

def test_go_duplicate_detection(client, mock_thread_store):
    """Test duplicate message detection in go"""
    # Create a mock thread with an existing message
    mock_thread = MagicMock(spec=Thread)
    mock_thread.messages = [
        MagicMock(
            role="user",
            content="test message",
            source={"name": "test_source"}
        )
    ]
    mock_thread.to_dict.return_value = {"id": "test-thread-id"}
    mock_thread_store.get.return_value = mock_thread
    
    # Send the same message again
    response = client.post("/process/message", json={
        "message": "test message",
        "source": {
            "name": "test_source",
            "thread_id": "test-thread-id"
        }
    })
    
    assert response.status_code == 200
    assert response.json["new_messages"] == []
    mock_thread_store.get.assert_called_once_with("test-thread-id")

def test_go_new_thread(client, mock_thread_store, mock_router_agent, mock_agent_registry):
    """Test creating a new thread in go"""
    # Mock thread store to return None (no existing thread)
    mock_thread_store.get.return_value = None
    
    # Mock router agent response
    mock_router_agent.route.return_value = "test_agent"
    
    # Mock agent response
    mock_agent = MagicMock()
    mock_thread = MagicMock(spec=Thread)
    mock_thread.id = "new-thread-id"
    mock_thread.to_dict.return_value = {"id": "new-thread-id"}
    mock_agent.go.return_value = (mock_thread, [])
    mock_agent_registry.get_agent.return_value = mock_agent
    
    response = client.post("/process/message", json={
        "message": "test message",
        "source": {
            "name": "test_source",
            "thread_id": "new-thread-id"
        }
    })
    
    assert response.status_code == 200
    mock_thread_store.get.assert_called_once_with("new-thread-id")
    mock_agent_registry.get_agent.assert_called_once_with("test_agent")

def test_go_with_attachments(client, mock_thread_store, mock_router_agent, mock_agent_registry):
    """Test processing a message with attachments"""
    # Mock thread store to return None (no existing thread)
    mock_thread_store.get.return_value = None
    
    # Mock router agent response
    mock_router_agent.route.return_value = "test_agent"
    
    # Mock agent response
    mock_agent = MagicMock()
    mock_thread = MagicMock(spec=Thread)
    mock_thread.id = "new-thread-id"
    mock_thread.to_dict.return_value = {"id": "new-thread-id"}
    mock_agent.go.return_value = (mock_thread, [])
    mock_agent_registry.get_agent.return_value = mock_agent
    
    response = client.post("/process/message", json={
        "message": "test message with attachment",
        "source": {
            "name": "test_source",
            "thread_id": "new-thread-id"
        },
        "attachments": [{
            "filename": "test.txt",
            "content": "dGVzdCBmaWxlIGNvbnRlbnQ=",  # base64 encoded "test file content"
            "mime_type": "text/plain"
        }]
    })
    
    assert response.status_code == 200
    mock_thread_store.get.assert_called_once_with("new-thread-id")
    mock_agent_registry.get_agent.assert_called_once_with("test_agent")

def test_go_invalid_request(client):
    """Test processing a message with invalid request format"""
    response = client.post("/process/message", json={
        "invalid": "format"
    })
    
    assert response.status_code == 400
    assert "Source must be an object with 'name' and 'thread_id' properties" in response.data.decode()

def test_go_missing_fields(client):
    """Test processing a message with missing required fields"""
    response = client.post("/process/message", json={
        "message": "test",
        "source": {
            "name": "test"
            # missing thread_id
        }
    })
    
    assert response.status_code == 400
    assert "Source must be an object with 'name' and 'thread_id' properties" in response.data.decode()

def test_go_error(client, mock_router_agent, mock_thread_store):
    """Test processing a message where an error occurs"""
    mock_router_agent.route.side_effect = Exception("Processing error")
    mock_thread_store.get.return_value = None
    
    response = client.post("/process/message", json={
        "message": "test message",
        "source": {
            "name": "test_source",
            "thread_id": "test-thread-id"
        }
    })
    
    assert response.status_code == 500
    assert "Error: Processing error" in response.data.decode()

def test_slack_events_missing_required_data(client, mock_slack_signature):
    """Test handling Slack events with missing required data"""
    event_data = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "user": "U123",
            # Missing text
            "ts": "123.456",
            "channel": "C123"
        }
    }
    
    response = client.post('/slack/events',
                          json=event_data,
                          headers={"X-Slack-Signature": "valid", "X-Slack-Request-Timestamp": "123"})
    
    assert response.status_code == 200  # Slack always expects 200
    # No further processing should occur due to missing data

def test_slack_events_file_download_error(client, mock_slack_signature, mock_slack_client, mock_requests):
    """Test handling file download errors in Slack events"""
    event_data = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "user": "U123",
            "text": "Here's a file",
            "ts": "123.456",
            "channel": "C123",
            "files": [{
                "id": "F123",
                "name": "test.txt",
                "mimetype": "text/plain"
            }]
        }
    }
    
    # Mock file download failure
    mock_requests.return_value = MagicMock(ok=False, status_code=404)
    
    response = client.post('/slack/events',
                          json=event_data,
                          headers={"X-Slack-Signature": "valid", "X-Slack-Request-Timestamp": "123"})
    
    assert response.status_code == 200  # Should still return 200 to Slack
    mock_slack_client.files_info.assert_called_once_with(file="F123")
    mock_requests.assert_called_once() 