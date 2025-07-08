"""Tyler - A development kit for AI agents with a complete lack of conventional limitations"""

__version__ = "1.1.0"

from tyler.utils.logging import get_logger
from tyler.models.agent import Agent, StreamUpdate
from narrator import Thread, Message, ThreadStore, FileStore, Attachment

# Configure logging when package is imported
logger = get_logger(__name__) 