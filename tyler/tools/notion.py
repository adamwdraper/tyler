import os
import requests
import weave
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class SearchParams:
    query: Optional[str] = None
    filter: Optional[Dict] = None
    start_cursor: Optional[str] = None
    page_size: Optional[int] = None

    def to_dict(self) -> Dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}

def create_notion_client():
    """Create a new NotionClient instance"""
    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise ValueError("Notion API token not found")
    return NotionClient(token)

class NotionClient:
    def __init__(self, token: str):
        """Initialize the Notion client"""
        self.token = token
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Makes a request to the Notion API"""
        url = f"{self.base_url}/{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=data)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            elif method == "PATCH":
                response = requests.patch(url, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Notion API request failed: {str(e)}")

    def search(self, query: Optional[str] = None, filter: Optional[Dict] = None,
              start_cursor: Optional[str] = None, page_size: Optional[int] = None) -> Dict:
        """Search Notion database"""
        data = {}
        if query:
            data["query"] = query
        if filter:
            data["filter"] = filter
        if start_cursor:
            data["start_cursor"] = start_cursor
        if page_size:
            data["page_size"] = page_size
        return self._make_request("POST", "search", data)

    def get_page(self, page_id: str) -> Dict:
        """Get a page by ID"""
        return self._make_request("GET", f"pages/{page_id}")

    def get_block_children(self, block_id: str, start_cursor: Optional[str] = None,
                         page_size: Optional[int] = None) -> Dict:
        """Get children blocks of a block"""
        data = {}
        if start_cursor:
            data["start_cursor"] = start_cursor
        if page_size:
            data["page_size"] = page_size
        return self._make_request("GET", f"blocks/{block_id}/children", data)

    def _fetch_all_children(self, block_id: str, start_cursor: Optional[str] = None,
                          page_size: Optional[int] = None) -> List[Dict]:
        """Fetch all children blocks recursively"""
        all_blocks = []
        current_cursor = start_cursor

        while True:
            response = self.get_block_children(block_id, start_cursor=current_cursor, page_size=page_size)
            blocks = response.get("results", [])
            all_blocks.extend(blocks)

            # Process each block's children if they have any
            for block in blocks:
                if block.get("has_children", False):
                    children = self._fetch_all_children(block["id"], page_size=page_size)
                    block["children"] = children

            next_cursor = response.get("next_cursor")
            if not next_cursor:
                break
            current_cursor = next_cursor

        return all_blocks

    def create_comment(self, rich_text: List[Dict], page_id: Optional[str] = None,
                      discussion_id: Optional[str] = None) -> Dict:
        """Create a comment on a page or discussion"""
        if not (bool(page_id) ^ bool(discussion_id)):
            raise ValueError("Either page_id or discussion_id must be provided, but not both")

        data = {"rich_text": rich_text}
        if page_id:
            data["parent"] = {"page_id": page_id}
        if discussion_id:
            data["discussion_id"] = discussion_id

        return self._make_request("POST", "comments", data)

    def get_comments(self, block_id: str, start_cursor: Optional[str] = None,
                    page_size: Optional[int] = None) -> Dict:
        """Get comments for a block"""
        data = {"block_id": block_id}
        if start_cursor:
            data["start_cursor"] = start_cursor
        if page_size:
            data["page_size"] = page_size
        return self._make_request("GET", "comments", data)

    def create_page(self, parent: Dict, properties: Dict, children: Optional[List[Dict]] = None,
                   icon: Optional[Dict] = None, cover: Optional[Dict] = None) -> Dict:
        """Create a new page"""
        data = {
            "parent": parent,
            "properties": properties
        }
        if children:
            data["children"] = children
        if icon:
            data["icon"] = icon
        if cover:
            data["cover"] = cover
        return self._make_request("POST", "pages", data)

    def update_block(self, block_id: str, block_type: str, content: Dict) -> Dict:
        """Update a block's content"""
        if not content:
            raise ValueError("Content parameter is required and cannot be empty")
        data = {block_type: content}
        return self._make_request("PATCH", f"blocks/{block_id}", data)

    def extract_clean_content(self, blocks: List[Dict]) -> Dict:
        """Extract clean content from blocks"""
        clean_text = []
        for block in blocks:
            if block["type"] == "paragraph":
                text = block["paragraph"].get("text", [])
                for t in text:
                    if "content" in t.get("text", {}):
                        clean_text.append(t["text"]["content"])
        return {"content": "\n".join(clean_text)}

@weave.op(name="notion-search")
def search(query: Optional[str] = None, filter: Optional[Dict] = None,
          start_cursor: Optional[str] = None, page_size: Optional[int] = None) -> Dict:
    """Search Notion database"""
    client = create_notion_client()
    return client.search(query=query, filter=filter, start_cursor=start_cursor, page_size=page_size)

@weave.op(name="notion-get_page")
def get_page(page_id: str) -> Dict:
    """Get a page by ID"""
    client = create_notion_client()
    return client.get_page(page_id=page_id)

@weave.op(name="notion-get_page_content")
def get_page_content(page_id: str, start_cursor: Optional[str] = None,
                    page_size: Optional[int] = None, clean_content: bool = False) -> Dict:
    """Get page content"""
    client = create_notion_client()
    blocks = client._fetch_all_children(page_id, start_cursor=start_cursor, page_size=page_size)
    if clean_content:
        return client.extract_clean_content(blocks)
    return {"object": "list", "results": blocks}

@weave.op(name="notion-create_comment")
def create_comment(rich_text: List[Dict], page_id: Optional[str] = None,
                  discussion_id: Optional[str] = None) -> Dict:
    """Create a comment on a page or discussion"""
    client = create_notion_client()
    return client.create_comment(rich_text=rich_text, page_id=page_id, discussion_id=discussion_id)

@weave.op(name="notion-get_comments")
def get_comments(block_id: str, start_cursor: Optional[str] = None,
                page_size: Optional[int] = None) -> Dict:
    """Get comments for a block"""
    client = create_notion_client()
    return client.get_comments(block_id=block_id, start_cursor=start_cursor, page_size=page_size)

@weave.op(name="notion-create_page")
def create_page(parent: Dict, properties: Dict, children: Optional[List[Dict]] = None,
               icon: Optional[Dict] = None, cover: Optional[Dict] = None) -> Dict:
    """Create a new page"""
    client = create_notion_client()
    return client.create_page(parent=parent, properties=properties, children=children,
                            icon=icon, cover=cover)

@weave.op(name="notion-update_block")
def update_block(block_id: str, block_type: str, content: Dict) -> Dict:
    """Update a block's content"""
    client = create_notion_client()
    return client.update_block(block_id=block_id, block_type=block_type, content=content)

TOOLS = [
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "notion-search",
                "description": "Searches all titles of pages and databases in Notion that have been shared with the integration. Can search by title or filter to only pages/databases. When constructing queries: • Include relevant keywords and filters (e.g., by title or tags) to precisely target the desired content. • Keep queries concise and leverage pagination to optimize performance. • Refine or expand filters and query terms over time for incremental improvements.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find in page/database titles. Query around subject matter such that it likely will be in the title. Optional - if not provided returns all pages/databases."
                        },
                        "filter": {
                            "type": "object",
                            "description": "Filter to only return pages or databases. Optional.",
                            "properties": {
                                "value": {
                                    "type": "string",
                                    "enum": ["page", "database"]
                                },
                                "property": {
                                    "type": "string",
                                    "enum": ["object"]
                                }
                            }
                        },
                        "start_cursor": {
                            "type": "string",
                            "description": "If there are more results, pass this cursor to fetch the next page. Optional."
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "Number of results to return. Default 5. Required.",
                            "minimum": 1,
                            "maximum": 100
                        }
                    }
                }
            }
        },
        "implementation": search
    },
    {
        "definition": {
            "type": "function", 
            "function": {
                "name": "notion-get_page",
                "description": "Retrieves a Notion page by its ID. Returns the page properties and metadata, not the content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "The ID of the page to retrieve"
                        }
                    },
                    "required": ["page_id"]
                }
            }
        },
        "implementation": get_page
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "notion-get_page_content",
                "description": "Retrieves the content (blocks) of a Notion page by its ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "The ID of the page whose content to retrieve"
                        },
                        "start_cursor": {
                            "type": "string",
                            "description": "If there are more blocks, pass this cursor to fetch the next page. Optional."
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "Number of blocks to return. Default 100. Optional.",
                            "minimum": 1,
                            "maximum": 100
                        },
                        "clean_content": {
                            "type": "boolean",
                            "description": "Use true if you are reading the content of a page without needing to edit it. If true, returns only essential text content without metadata, formatted in markdown-style. If false, returns full Notion API response. Optional, defaults to false."
                        }
                    },
                    "required": ["page_id"]
                }
            }
        },
        "implementation": get_page_content
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "notion-create_comment",
                "description": "Creates a comment in a Notion page or existing discussion thread.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "The ID of the page to add the comment to. Required if discussion_id is not provided."
                        },
                        "discussion_id": {
                            "type": "string",
                            "description": "The ID of the discussion thread to add the comment to. Required if page_id is not provided."
                        },
                        "rich_text": {
                            "type": "array",
                            "description": "The rich text content of the comment",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {
                                        "type": "object",
                                        "properties": {
                                            "content": {
                                                "type": "string",
                                                "description": "The text content"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "implementation": create_comment
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "notion-get_comments",
                "description": "Retrieves comments from a block ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "block_id": {
                            "type": "string",
                            "description": "The ID of the block to get comments from"
                        },
                        "start_cursor": {
                            "type": "string",
                            "description": "If there are more comments, pass this cursor to fetch the next page. Optional."
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "Number of comments to return. Default 100. Optional.",
                            "minimum": 1,
                            "maximum": 100
                        }
                    },
                    "required": ["block_id"]
                }
            }
        },
        "implementation": get_comments
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "notion-create_page",
                "description": "Creates a new page in Notion as a child of an existing page or database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "parent": {
                            "type": "object",
                            "description": "The parent page or database this page belongs to",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["page_id", "database_id"],
                                    "description": "Whether this is a page or database parent"
                                },
                                "id": {
                                    "type": "string",
                                    "description": "The ID of the parent page or database"
                                }
                            },
                            "required": ["type", "id"]
                        },
                        "properties": {
                            "type": "object",
                            "description": "Page properties. If parent is a page, only title is valid. If parent is a database, keys must match database properties."
                        },
                        "children": {
                            "type": "array",
                            "description": "Page content as an array of block objects. Optional.",
                            "items": {
                                "type": "object"
                            }
                        },
                        "icon": {
                            "type": "object",
                            "description": "Page icon. Optional.",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["emoji", "external"]
                                },
                                "emoji": {
                                    "type": "string"
                                },
                                "external": {
                                    "type": "object",
                                    "properties": {
                                        "url": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        },
                        "cover": {
                            "type": "object",
                            "description": "Page cover image. Optional.",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["external"]
                                },
                                "external": {
                                    "type": "object",
                                    "properties": {
                                        "url": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "required": ["parent", "properties"]
                }
            }
        },
        "implementation": create_page
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "notion-update_block",
                "description": "Updates the content of a specific block in Notion based on the block type.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "block_id": {
                            "type": "string",
                            "description": "The ID of the block to update"
                        },
                        "block_type": {
                            "type": "string",
                            "description": "The type of block being updated (e.g. paragraph, heading_1, to_do, etc)"
                        },
                        "content": {
                            "type": "object",
                            "description": "The new content for the block, structured according to the block type"
                        }
                    },
                    "required": ["block_id", "block_type", "content"]
                }
            }
        },
        "implementation": update_block
    }
]