"""Component registry for managing shared resources."""
from typing import Any, Dict, Tuple, Optional, TYPE_CHECKING
import logging

# Type hints with conditional imports to avoid circular dependencies
if TYPE_CHECKING:
    from tyler import ThreadStore, FileStore
    
logger = logging.getLogger(__name__)

class Registry:
    """Registry for managing shared components like thread stores and file stores.
    
    This registry ensures components have stable identity across multiple
    agent initializations.
    """
    
    # Singleton instance of the registry
    _instance = None
    
    # Dictionary to store registered components
    _components: Dict[Tuple[str, str], Any] = {}
    
    @classmethod
    def get_instance(cls) -> 'Registry':
        """Get the singleton instance of the registry."""
        if cls._instance is None:
            cls._instance = Registry()
        return cls._instance
    
    def register(self, component_type: str, name: str, instance: Any) -> Any:
        """Register a component in the registry.
        
        Args:
            component_type: Type of component (e.g., "thread_store", "file_store")
            name: Name identifier for the component
            instance: The component instance to register
            
        Returns:
            The registered instance
        """
        key = (component_type, name)
        self._components[key] = instance
        logger.debug(f"Registered {component_type} with name '{name}'")
        return instance
    
    def get(self, component_type: str, name: str) -> Optional[Any]:
        """Get a component from the registry.
        
        Args:
            component_type: Type of component to retrieve
            name: Name identifier of the component
            
        Returns:
            The component instance or None if not found
        """
        key = (component_type, name)
        component = self._components.get(key)
        if component is None:
            logger.debug(f"Component {component_type} with name '{name}' not found")
        return component
    
    def list(self, component_type: Optional[str] = None) -> Dict[Tuple[str, str], Any]:
        """List all registered components, optionally filtered by type.
        
        Args:
            component_type: Optional type to filter components by
            
        Returns:
            Dictionary of components
        """
        if component_type is None:
            return self._components.copy()
        
        return {k: v for k, v in self._components.items() if k[0] == component_type}

# Basic registry functions
def register(component_type: str, name: str, instance: Any) -> Any:
    """Register a component in the global registry."""
    return Registry.get_instance().register(component_type, name, instance)

def get(component_type: str, name: str) -> Optional[Any]:
    """Get a component from the global registry."""
    return Registry.get_instance().get(component_type, name)

def list(component_type: Optional[str] = None) -> Dict[Tuple[str, str], Any]:
    """List components in the global registry."""
    return Registry.get_instance().list(component_type)

# Thread store specific functions
def register_thread_store(name: str, thread_store: "ThreadStore") -> "ThreadStore":
    """Register a thread store with the given name.
    
    Args:
        name: Name identifier for the thread store
        thread_store: The thread store instance
        
    Returns:
        The registered thread store
    """
    return register("thread_store", name, thread_store)

def get_thread_store(name: str) -> Optional["ThreadStore"]:
    """Get a thread store by name.
    
    Args:
        name: Name of the thread store
        
    Returns:
        The thread store instance or None if not found
    """
    return get("thread_store", name)

# File store specific functions
def register_file_store(name: str, file_store: "FileStore") -> "FileStore":
    """Register a file store with the given name.
    
    Args:
        name: Name identifier for the file store
        file_store: The file store instance
        
    Returns:
        The registered file store
    """
    return register("file_store", name, file_store)

def get_file_store(name: str) -> Optional["FileStore"]:
    """Get a file store by name.
    
    Args:
        name: Name of the file store
        
    Returns:
        The file store instance or None if not found
    """
    return get("file_store", name) 