"""Tests for browser automation tool."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from tyler.tools.browser import browser_automate, browser_screenshot

# Mock classes and objects
class MockBrowserAgent:
    def __init__(self, **kwargs):
        self.task = kwargs.get('task')
        self.llm = kwargs.get('llm')
        self.browser = kwargs.get('browser')
        
    async def run(self):
        # Mock result with attributes that our functions expect
        result = MagicMock()
        result.all_results = ["Navigated to google.com", "Searched for 'test'"]
        result.output = "Completed search on Google"
        return result

class MockBrowser:
    def __init__(self, config=None):
        self.config = config
        
    async def close(self):
        pass

@pytest.mark.asyncio
async def test_browser_automate_success():
    """Test successful browser automation."""
    # Mock dependencies
    with patch('tyler.tools.browser.ChatOpenAI') as mock_chat_openai, \
         patch('tyler.tools.browser.Browser') as mock_browser_class, \
         patch('tyler.tools.browser.BrowserAgent', MockBrowserAgent):
        
        # Setup mocks
        mock_chat_openai.return_value = MagicMock()
        mock_browser_class.return_value = MockBrowser()
        
        # Call the function
        result = await browser_automate(
            task="Go to google.com and search for test",
            model="gpt-4o",
            headless=True
        )
        
        # Assertions
        assert result["success"] is True
        assert "Actions performed" in result["summary"]
        assert "Navigated to google.com" in result["summary"]
        assert "Searched for 'test'" in result["summary"]

@pytest.mark.asyncio
async def test_browser_automate_exception():
    """Test browser automation with exception."""
    # Mock dependencies
    with patch('tyler.tools.browser.ChatOpenAI') as mock_chat_openai, \
         patch('tyler.tools.browser.Browser') as mock_browser_class, \
         patch('tyler.tools.browser.BrowserAgent') as mock_agent_class:
        
        # Setup mocks
        mock_chat_openai.return_value = MagicMock()
        mock_browser_class.return_value = MockBrowser()
        mock_agent_class.side_effect = Exception("Browser automation failed")
        
        # Call the function
        result = await browser_automate(
            task="Go to google.com and search for test",
            model="gpt-4o",
            headless=True
        )
        
        # Assertions
        assert result["success"] is False
        assert result["error"] == "Browser automation failed"

@pytest.mark.asyncio
async def test_browser_screenshot_success():
    """Test successful browser screenshot."""
    # Mock dependencies
    with patch('tyler.tools.browser.ChatOpenAI') as mock_chat_openai, \
         patch('tyler.tools.browser.Browser') as mock_browser_class, \
         patch('tyler.tools.browser.BrowserAgent', MockBrowserAgent):
        
        # Setup mocks
        mock_chat_openai.return_value = MagicMock()
        mock_browser_class.return_value = MockBrowser()
        
        # Call the function
        result, files = await browser_screenshot(
            url="https://example.com",
            wait_time=2,
            full_page=True
        )
        
        # Assertions
        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["full_page"] is True
        assert len(files) == 1
        assert files[0]["filename"].startswith("screenshot_")
        assert files[0]["mime_type"] == "image/png"

@pytest.mark.asyncio
async def test_browser_screenshot_exception():
    """Test browser screenshot with exception."""
    # Mock dependencies
    with patch('tyler.tools.browser.ChatOpenAI') as mock_chat_openai, \
         patch('tyler.tools.browser.Browser') as mock_browser_class, \
         patch('tyler.tools.browser.BrowserAgent') as mock_agent_class:
        
        # Setup mocks
        mock_chat_openai.return_value = MagicMock()
        mock_browser_class.return_value = MockBrowser()
        mock_agent_class.side_effect = Exception("Screenshot failed")
        
        # Call the function
        result, files = await browser_screenshot(
            url="https://example.com",
            wait_time=2,
            full_page=True
        )
        
        # Assertions
        assert result["success"] is False
        assert result["error"] == "Screenshot failed"
        assert len(files) == 0

@pytest.mark.asyncio
async def test_browser_config_parameters():
    """Test that browser configuration parameters are set correctly."""
    # Mock dependencies
    with patch('tyler.tools.browser.ChatOpenAI') as mock_chat_openai, \
         patch('tyler.tools.browser.Browser') as mock_browser_class, \
         patch('tyler.tools.browser.BrowserAgent', MockBrowserAgent), \
         patch('tyler.tools.browser.BrowserConfig') as mock_browser_config, \
         patch('tyler.tools.browser.BrowserContextConfig') as mock_context_config:
        
        # Setup mocks
        mock_chat_openai.return_value = MagicMock()
        mock_browser_class.return_value = MockBrowser()
        mock_context_config.return_value = "mock_context_config"
        
        # Call the function
        await browser_automate(
            task="Go to google.com and search for test",
            headless=False
        )
        
        # Assertions for BrowserContextConfig
        mock_context_config.assert_called_once()
        context_config_kwargs = mock_context_config.call_args[1]
        assert context_config_kwargs["highlight_elements"] is True
        assert context_config_kwargs["wait_for_network_idle_page_load_time"] == 3.0
        assert context_config_kwargs["browser_window_size"] == {'width': 1280, 'height': 900}
        
        # Assertions for BrowserConfig
        mock_browser_config.assert_called_once()
        browser_config_kwargs = mock_browser_config.call_args[1]
        assert browser_config_kwargs["headless"] is False
        assert browser_config_kwargs["disable_security"] is True
        assert browser_config_kwargs["new_context_config"] == "mock_context_config"

# Integration test - this would be skipped by default as it requires actual browser installation
@pytest.mark.skip(reason="Integration test requiring actual browser installation")
@pytest.mark.asyncio
async def test_browser_integration():
    """Integration test for browser automation."""
    # This test actually runs the browser and performs a simple task
    result = await browser_automate(
        task="Go to example.com and get the title",
        headless=True  # Use headless mode for CI/CD environments
    )
    
    assert result["success"] is True
    assert "example" in result["summary"].lower() 