"""Tests for the registry utilities."""
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from tyler.utils.registry import (
    Registry, register, get, list,
    register_thread_store, get_thread_store,
    register_file_store, get_file_store,
    register_stores, create_stores
)

class MockComponent:
    """Mock component for testing."""
    def __init__(self, name):
        self.name = name

# Mock stores for testing
class MockThreadStore:
    def __init__(self, url=None):
        self.url = url

class MockFileStore:
    def __init__(self, path=None):
        self.path = path

@pytest.fixture
def reset_registry():
    """Reset the registry singleton between tests."""
    Registry._instance = None
    Registry._components = {}
    yield
    Registry._instance = None
    Registry._components = {}

def test_registry_singleton():
    """Test that Registry implements the singleton pattern correctly."""
    # Get two instances
    r1 = Registry.get_instance()
    r2 = Registry.get_instance()
    
    # They should be the same object
    assert r1 is r2
    
    # Register something in r1
    r1.register("test", "singleton", "value")
    
    # It should be accessible from r2
    assert r2.get("test", "singleton") == "value"

def test_register_and_get(reset_registry):
    """Test registering and retrieving components."""
    # Create a component
    component = MockComponent("test-component")
    
    # Register it
    result = register("mock", "test", component)
    
    # Register should return the same component
    assert result is component
    
    # Retrieve it
    retrieved = get("mock", "test")
    
    # Should be the same object
    assert retrieved is component
    assert retrieved.name == "test-component"

def test_get_nonexistent(reset_registry):
    """Test retrieving a nonexistent component."""
    # Get a component that doesn't exist
    component = get("missing", "nonexistent")
    
    # Should return None
    assert component is None

def test_list_all(reset_registry):
    """Test listing all components."""
    # Register a few components
    c1 = MockComponent("c1")
    c2 = MockComponent("c2")
    c3 = MockComponent("c3")
    
    register("type1", "c1", c1)
    register("type1", "c2", c2)
    register("type2", "c3", c3)
    
    # List all components
    components = list()
    
    # Should have 3 components
    assert len(components) == 3
    assert components[("type1", "c1")] is c1
    assert components[("type1", "c2")] is c2
    assert components[("type2", "c3")] is c3

def test_list_by_type(reset_registry):
    """Test listing components by type."""
    # Register a few components
    c1 = MockComponent("c1")
    c2 = MockComponent("c2")
    c3 = MockComponent("c3")
    
    register("type1", "c1", c1)
    register("type1", "c2", c2)
    register("type2", "c3", c3)
    
    # List components of type1
    components = list("type1")
    
    # Should have 2 components
    assert len(components) == 2
    assert components[("type1", "c1")] is c1
    assert components[("type1", "c2")] is c2
    assert ("type2", "c3") not in components

def test_replace_component(reset_registry):
    """Test replacing a component."""
    # Register a component
    c1 = MockComponent("original")
    register("test", "replace", c1)
    
    # Replace it
    c2 = MockComponent("replacement")
    register("test", "replace", c2)
    
    # Get the component
    retrieved = get("test", "replace")
    
    # Should be the replacement
    assert retrieved is c2
    assert retrieved.name == "replacement"

def test_thread_file_store_workflow(reset_registry):
    """Test a typical thread and file store registration workflow."""
    # Create stores
    thread_store = MockThreadStore("postgresql://localhost/test")
    file_store = MockFileStore("/path/to/files")
    
    # Register stores
    register("thread_store", "production", thread_store)
    register("file_store", "production", file_store)
    
    # Retrieve stores
    ts = get("thread_store", "production")
    fs = get("file_store", "production")
    
    # Verify stores
    assert ts is thread_store
    assert ts.url == "postgresql://localhost/test"
    assert fs is file_store
    assert fs.path == "/path/to/files"

def test_thread_store_convenience_functions(reset_registry):
    """Test the thread store convenience functions."""
    # Create a thread store
    thread_store = MockThreadStore("postgresql://localhost/test")
    
    # Register it using the convenience function
    registered = register_thread_store("test", thread_store)
    
    # Should return the registered store
    assert registered is thread_store
    
    # Get it using the convenience function
    retrieved = get_thread_store("test")
    
    # Should be the same store
    assert retrieved is thread_store
    assert retrieved.url == "postgresql://localhost/test"
    
    # Get a nonexistent store
    missing = get_thread_store("missing")
    assert missing is None

def test_file_store_convenience_functions(reset_registry):
    """Test the file store convenience functions."""
    # Create a file store
    file_store = MockFileStore("/path/to/files")
    
    # Register it using the convenience function
    registered = register_file_store("test", file_store)
    
    # Should return the registered store
    assert registered is file_store
    
    # Get it using the convenience function
    retrieved = get_file_store("test")
    
    # Should be the same store
    assert retrieved is file_store
    assert retrieved.path == "/path/to/files"
    
    # Get a nonexistent store
    missing = get_file_store("missing")
    assert missing is None

def test_register_stores(reset_registry):
    """Test registering both thread and file stores with the same name."""
    # Create stores
    thread_store = MockThreadStore("postgresql://localhost/test")
    file_store = MockFileStore("/path/to/files")
    
    # Register both with the same name
    ts, fs = register_stores("environment", thread_store, file_store)
    
    # Should return the registered stores
    assert ts is thread_store
    assert fs is file_store
    
    # Get them using the individual convenience functions
    retrieved_ts = get_thread_store("environment")
    retrieved_fs = get_file_store("environment")
    
    # Should be the same stores
    assert retrieved_ts is thread_store
    assert retrieved_fs is file_store
    
    # Should also be accessible using the generic get function
    assert get("thread_store", "environment") is thread_store
    assert get("file_store", "environment") is file_store

# New test for the async create_stores function
@pytest.mark.asyncio
async def test_create_stores(reset_registry):
    """Test creating and registering stores in one step."""
    # Mock the store creation functions
    thread_store = MockThreadStore("postgresql://localhost/test")
    file_store = MockFileStore("/path/to/files")
    
    # Use patch to replace the create methods with AsyncMocks
    with patch('tyler.database.thread_store.ThreadStore.create', new_callable=AsyncMock) as mock_thread_create, \
         patch('tyler.storage.file_store.FileStore.create', new_callable=AsyncMock) as mock_file_create:
        
        # Configure the mocks to return our test objects
        mock_thread_create.return_value = thread_store
        mock_file_create.return_value = file_store
        
        # Call the function
        ts, fs = await create_stores(
            "test_env", 
            thread_store_url="postgresql://localhost/test",
            file_store_path="/path/to/files"
        )
        
        # Verify the create methods were called with the right arguments
        mock_thread_create.assert_called_once_with("postgresql://localhost/test")
        mock_file_create.assert_called_once_with("/path/to/files")
        
        # Verify the stores were registered and returned
        assert ts is thread_store
        assert fs is file_store
        
        # Check they can be retrieved from the registry
        assert get_thread_store("test_env") is thread_store
        assert get_file_store("test_env") is file_store 