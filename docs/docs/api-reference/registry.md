---
sidebar_position: 7
---

# Registry API

The `tyler.utils.registry` module provides a centralized mechanism for managing shared instances of core components, primarily `ThreadStore` and `FileStore`. This allows different parts of an application, or multiple agent instances, to access the same store instances by a registered name, ensuring consistency and a single source of truth for storage operations.

While the registry includes a generic `Registry` class, most users will interact with the specific helper functions provided for `ThreadStore` and `FileStore`.

## Overview

The registry helps in scenarios where you might have multiple store configurations (e.g., a default in-memory store for quick tasks and a persistent database store for long-term storage) or when you want to explicitly manage the lifecycle and accessibility of your store instances.

Key benefits:
-   **Named Instances**: Register stores with a unique name (e.g., "default", "persistent_db", "archive_files").
-   **Global Access**: Retrieve registered stores from anywhere in your application using their name.
-   **Agent Integration**: Agents can be configured to use stores from the registry by passing store instances directly to the Agent constructor, or by using the registry's `get_thread_store()` and `get_file_store()` functions to retrieve stores by name.

## Core Functions

These are the primary functions you'll use to interact with the registry for thread and file stores.

### `register_thread_store`

Registers a `ThreadStore` instance with a given name.

```python
def register_thread_store(name: str, thread_store: ThreadStore) -> ThreadStore
```

**Parameters:**

| Parameter      | Type        | Description                         |
| -------------- | ----------- | ----------------------------------- |
| `name`         | `str`       | The name to register the store with. |
| `thread_store` | `ThreadStore` | The `ThreadStore` instance to register. |

**Returns:**

The registered `ThreadStore` instance.

**Example:**

```python
from tyler import ThreadStore
from tyler.utils.registry import register_thread_store

# Create a database-backed thread store
db_thread_store = await ThreadStore.create("sqlite+aiosqlite:///./tyler_threads.db")

# Register it with the name "persistent"
register_thread_store("persistent", db_thread_store)

# Create an in-memory thread store
mem_thread_store = await ThreadStore.create()
register_thread_store("default_memory", mem_thread_store)
```

### `get_thread_store`

Retrieves a registered `ThreadStore` instance by its name.

```python
def get_thread_store(name: str) -> Optional[ThreadStore]
```

**Parameters:**

| Parameter | Type  | Description                                  |
| --------- | ----- | -------------------------------------------- |
| `name`    | `str` | The name of the `ThreadStore` to retrieve. |

**Returns:**

The `ThreadStore` instance if found, otherwise `None`.

**Example:**

```python
from tyler.utils.registry import get_thread_store

persistent_store = get_thread_store("persistent")
if persistent_store:
    # Use the store
    print(f"Retrieved persistent store: {type(persistent_store)}")

default_store = get_thread_store("default_memory")
if default_store:
    print(f"Retrieved default memory store: {type(default_store)}")
```

### `register_file_store`

Registers a `FileStore` instance with a given name.

```python
def register_file_store(name: str, file_store: FileStore) -> FileStore
```

**Parameters:**

| Parameter    | Type      | Description                       |
| ------------ | --------- | --------------------------------- |
| `name`       | `str`     | The name to register the store with. |
| `file_store` | `FileStore` | The `FileStore` instance to register. |

**Returns:**

The registered `FileStore` instance.

**Example:**

```python
from tyler import FileStore
from tyler.utils.registry import register_file_store

# Create a file store with a custom path
custom_file_store = await FileStore.create(base_path="/mnt/tyler_data/files")
register_file_store("custom_data", custom_file_store)

# Create a default in-memory file store (though less common for FileStore)
# For FileStore, usually a path-based store is preferred even for defaults.
default_fs = await FileStore.create() # Uses default path or in-memory if path not settable
register_file_store("default_files", default_fs)
```

### `get_file_store`

Retrieves a registered `FileStore` instance by its name.

```python
def get_file_store(name: str) -> Optional[FileStore]
```

**Parameters:**

| Parameter | Type  | Description                                |
| --------- | ----- | ------------------------------------------ |
| `name`    | `str` | The name of the `FileStore` to retrieve. |

**Returns:**

The `FileStore` instance if found, otherwise `None`.

**Example:**

```python
from tyler.utils.registry import get_file_store

custom_fs = get_file_store("custom_data")
if custom_fs:
    print(f"Retrieved custom file store: {type(custom_fs)}")

default_fs = get_file_store("default_files")
if default_fs:
    print(f"Retrieved default file store: {type(default_fs)}")
```

## Agent Integration

Once stores are registered, an `Agent` can be configured to use them by name:

```python
from tyler import Agent, ThreadStore, FileStore
from tyler.utils.registry import register_thread_store, register_file_store

# Setup and register stores
db_store = await ThreadStore.create("sqlite+aiosqlite:///main_threads.db")
fs_store = await FileStore.create(base_path="./tyler_files")
register_thread_store("main_db", db_store)
register_file_store("main_files", fs_store)

# Initialize agent
agent = Agent(
    name="ConfiguredAgent",
    purpose="To demonstrate using registered stores.",
    model_name="gpt-4.1"
)

# Option 1: Configure agent with store instances directly
agent = Agent(
    name="ConfiguredAgent",
    purpose="To demonstrate using registered stores.",
    model_name="gpt-4.1",
    thread_store=db_store,  # Pass store instance directly
    file_store=fs_store     # Pass store instance directly
)

# Option 2: Retrieve stores from registry and pass to agent
from tyler.utils.registry import get_thread_store, get_file_store
retrieved_db_store = get_thread_store("main_db")
retrieved_fs_store = get_file_store("main_files")

agent = Agent(
    name="ConfiguredAgent",
    purpose="To demonstrate using registered stores.",
    model_name="gpt-4.1",
    thread_store=retrieved_db_store,
    file_store=retrieved_fs_store
)

# Now, when agent performs operations requiring storage,
# it will use the configured ThreadStore and FileStore.
# For example, agent.go(thread) will save the thread using the configured stores.
```

## Generic Registry Functions (Advanced)

The registry also provides generic functions for registering and retrieving any type of component. These are less commonly used directly for thread/file stores, as the specific helpers above are preferred.

### `register`

```python
def register(component_type: str, name: str, instance: Any) -> Any
```
Registers any component instance with a given type and name.

### `get`

```python
def get(component_type: str, name: str) -> Optional[Any]
```
Retrieves any registered component by its type and name.

### `list_components` (Conceptual, actual name `list` in code)
The registry has a `list` method (e.g., `Registry.get_instance().list()`) to view registered components, which can be useful for debugging.

```python
from tyler.utils.registry import list as list_registered_components

all_stores = list_registered_components()
print("All registered components:", all_stores)

thread_stores_only = list_registered_components(component_type="thread_store")
print("Thread stores:", thread_stores_only)
```

## See Also
- [Core Concepts: Storage](../core-concepts.md#storage)
- [Configuration Guide](../configuration.md#storage-configuration)
- [Agent API](./agent.md)
- [ThreadStore API](./thread-store.md)
- [FileStore API](./file-store.md) 