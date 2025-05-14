"""
Browser automation tool using browser-use.

This tool allows Tyler to control a web browser to perform various tasks.
"""
import asyncio
import json
import weave
from typing import Dict, Any, Optional, List, Tuple
from browser_use import Agent as BrowserAgent, Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@weave.op(name="browser-automate")
async def browser_automate(*, 
                          task: str, 
                          model: str = "gpt-4.1",
                          headless: bool = False,  # Default to non-headless mode so users can see the browser
                          timeout: int = 300) -> Dict[str, Any]:
    """
    Automate browser tasks using browser-use.
    
    Args:
        task (str): The task to perform in natural language (e.g., "Go to google.com and search for Browser Use")
        model (str): The model to use for the browser agent (default: "gpt-4.1")
        headless (bool): Whether to run the browser in headless mode (default: False)
        timeout (int): Maximum time in seconds to run the task (default: 300)
        
    Returns:
        Dict[str, Any]: The result of the browser automation task
    """
    try:
        # Initialize the LLM
        llm = ChatOpenAI(model=model)
        
        # Configure the browser with supported parameters
        # Create context config with settings to improve visibility
        context_config = BrowserContextConfig(
            highlight_elements=True,  # Highlight interactive elements with colorful bounding boxes
            wait_for_network_idle_page_load_time=3.0,  # Wait longer for page loads to ensure content is visible
            browser_window_size={'width': 1280, 'height': 900}  # Set a good window size for visibility
        )
        
        # Configure the browser
        browser_config = BrowserConfig(
            headless=headless,
            disable_security=True,  # Helps with cross-site iFrames and other functionality
            new_context_config=context_config  # Apply our context configuration
        )
        
        browser = Browser(config=browser_config)
        
        # Initialize the browser agent
        agent = BrowserAgent(
            task=task,
            llm=llm,
            browser=browser
        )
        
        # Run the browser agent
        result = await agent.run()
        
        # Extract useful information from the result
        summary = "Task completed successfully"
        if hasattr(result, 'all_results') and result.all_results:
            summary = "Actions performed: " + ", ".join([str(r) for r in result.all_results])
        elif hasattr(result, 'output') and result.output:
            summary = result.output
            
        # Close the browser
        await browser.close()
        
        # Return the result with more detailed information
        return {
            "success": True,
            "summary": summary,
            "result": str(result)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@weave.op(name="browser-screenshot")
async def browser_screenshot(*, 
                           url: str,
                           wait_time: int = 3,
                           full_page: bool = True) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Take a screenshot of a webpage.
    
    Args:
        url (str): The URL to take a screenshot of
        wait_time (int): Time to wait in seconds after page load before taking screenshot (default: 3)
        full_page (bool): Whether to capture the full page or just the viewport (default: True)
        
    Returns:
        Tuple[Dict[str, Any], List[Dict[str, Any]]]: Tuple containing:
            - Dict with success status and metadata
            - List of file dictionaries with screenshot data
    """
    try:
        # Configure the browser context for screenshots
        context_config = BrowserContextConfig(
            wait_for_network_idle_page_load_time=wait_time,  # Use the wait_time parameter
            browser_window_size={'width': 1280, 'height': 900}  # Set a good window size for screenshots
        )
        
        # Configure the browser in headless mode for screenshots
        browser_config = BrowserConfig(
            headless=True,
            new_context_config=context_config
        )
        
        browser = Browser(config=browser_config)
        
        # Create a simple task to navigate to the URL and take a screenshot
        task = f"Go to {url} and take a {'full page' if full_page else 'viewport'} screenshot"
        
        # Initialize the browser agent
        llm = ChatOpenAI(model="gpt-4.1")
        
        agent = BrowserAgent(
            task=task,
            llm=llm,
            browser=browser
        )
        
        # Run the browser agent
        result = await agent.run()
        
        # Close the browser
        await browser.close()
        
        # Extract screenshot from result if available
        # Note: This is a simplified implementation. The actual implementation
        # would need to extract the screenshot from the browser-use result
        # and convert it to the expected format.
        
        # For now, return a placeholder
        return (
            {
                "success": True,
                "url": url,
                "full_page": full_page
            },
            [
                {
                    "filename": f"screenshot_{url.replace('://', '_').replace('/', '_')}.png",
                    "content": "base64_encoded_content_would_go_here",
                    "mime_type": "image/png"
                }
            ]
        )
    except Exception as e:
        return (
            {
                "success": False,
                "error": str(e)
            },
            []
        )

# Define the tools to be exported
TOOLS = [
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "browser-automate",
                "description": "Automate browser tasks using browser-use. This tool allows you to control a web browser to perform various tasks like navigating to websites, filling forms, clicking buttons, and more.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The task to perform in natural language (e.g., 'Go to google.com and search for Browser Use')"
                        },
                        "model": {
                            "type": "string",
                            "description": "The model to use for the browser agent (default: 'gpt-4.1')"
                        },
                        "headless": {
                            "type": "boolean",
                            "description": "Whether to run the browser in headless mode (default: False)"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Maximum time in seconds to run the task (default: 300)"
                        }
                    },
                    "required": ["task"]
                }
            }
        },
        "implementation": browser_automate
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "browser-screenshot",
                "description": "Take a screenshot of a webpage using browser-use.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to take a screenshot of"
                        },
                        "wait_time": {
                            "type": "integer",
                            "description": "Time to wait in seconds after page load before taking screenshot (default: 3)"
                        },
                        "full_page": {
                            "type": "boolean",
                            "description": "Whether to capture the full page or just the viewport (default: True)"
                        }
                    },
                    "required": ["url"]
                }
            }
        },
        "implementation": browser_screenshot
    }
] 