"""Tyler - A development kit for AI agents with a complete lack of conventional limitations"""

__version__ = "1.1.0"

from tyler.utils.logging import get_logger
from tyler.models.agent import Agent, StreamUpdate
from tyler.models.thread import Thread
from tyler.models.message import Message
from tyler.database.thread_store import ThreadStore
from tyler.storage.file_store import FileStore
from tyler.utils.registry import Registry
from tyler.models.attachment import Attachment

# Configure logging when package is imported
logger = get_logger(__name__) 