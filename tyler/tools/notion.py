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
        """Extract clean content from blocks with preserved markdown formatting and links"""
        clean_text = []
        for block in blocks:
            # Skip blocks without a type or with unsupported types
            if "type" not in block or block["type"] == "unsupported":
                continue
                
            block_type = block["type"]
            type_data = block.get(block_type, {})
            
            # Handle most common block types
            if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", 
                             "bulleted_list_item", "numbered_list_item", "toggle", 
                             "quote", "callout", "to_do"]:
                # Rich text is in rich_text field per Notion API docs
                rich_text = type_data.get("rich_text", [])
                if rich_text:
                    # Build formatted text with preserved links
                    formatted_segments = []
                    for rt in rich_text:
                        text = rt.get("plain_text", "")
                        if not text:
                            continue
                            
                        # Apply text formatting
                        if rt.get("annotations", {}).get("bold", False):
                            text = f"**{text}**"
                        if rt.get("annotations", {}).get("italic", False):
                            text = f"*{text}*"
                        if rt.get("annotations", {}).get("strikethrough", False):
                            text = f"~~{text}~~"
                        if rt.get("annotations", {}).get("code", False):
                            text = f"`{text}`"
                            
                        # Preserve hyperlinks as markdown
                        if rt.get("href"):
                            text = f"[{text}]({rt.get('href')})"
                            
                        formatted_segments.append(text)
                        
                    text_content = "".join(formatted_segments)
                    
                    if text_content:
                        # Add appropriate prefix based on block type
                        if block_type.startswith("heading_"):
                            level = block_type[-1]
                            clean_text.append(f"{'#' * int(level)} {text_content}")
                        elif block_type == "bulleted_list_item":
                            clean_text.append(f"* {text_content}")
                        elif block_type == "numbered_list_item":
                            clean_text.append(f"1. {text_content}")
                        elif block_type == "to_do":
                            checkbox = "- [x]" if type_data.get("checked", False) else "- [ ]"
                            clean_text.append(f"{checkbox} {text_content}")
                        elif block_type == "quote":
                            clean_text.append(f"> {text_content}")
                        elif block_type == "toggle":
                            # Mark toggle headers with a special prefix for visibility
                            clean_text.append(f"▶ {text_content}")
                        else:
                            clean_text.append(text_content)
            
            # Handle tables
            elif block_type == "table":
                has_column_header = type_data.get("has_column_header", False)
                has_row_header = type_data.get("has_row_header", False)
                
                # Process table rows if they exist
                if "children" in block:
                    table_rows = []
                    max_col_widths = []
                    
                    # First pass: collect all rows and determine column widths
                    for row_block in block["children"]:
                        if row_block.get("type") == "table_row":
                            row_data = row_block.get("table_row", {})
                            cells = row_data.get("cells", [])
                            row_content = []
                            
                            # Process each cell
                            for cell_idx, cell in enumerate(cells):
                                # Each cell is an array of rich text objects
                                cell_text = ""
                                for rt in cell:
                                    text = rt.get("plain_text", "")
                                    if rt.get("annotations", {}).get("bold", False):
                                        text = f"**{text}**"
                                    if rt.get("annotations", {}).get("italic", False):
                                        text = f"*{text}*"
                                    if rt.get("href"):
                                        text = f"[{text}]({rt.get('href')})"
                                    cell_text += text
                                
                                row_content.append(cell_text)
                                
                                # Update max column width
                                if len(max_col_widths) <= cell_idx:
                                    max_col_widths.append(len(cell_text))
                                else:
                                    max_col_widths[cell_idx] = max(max_col_widths[cell_idx], len(cell_text))
                            
                            table_rows.append(row_content)
                    
                    # Second pass: format as a nice text table
                    if table_rows:
                        # Add header separator if needed
                        formatted_table = []
                        
                        # Format each row
                        for row_idx, row in enumerate(table_rows):
                            row_str = "| "
                            for col_idx, cell in enumerate(row):
                                # Pad cell content to match column width
                                if col_idx < len(max_col_widths):
                                    row_str += cell.ljust(max_col_widths[col_idx]) + " | "
                                else:
                                    row_str += cell + " | "
                            
                            formatted_table.append(row_str)
                            
                            # Add header separator after first row if it's a header
                            if row_idx == 0 and has_column_header:
                                separator = "| "
                                for col_idx, width in enumerate(max_col_widths):
                                    separator += "-" * width + " | "
                                formatted_table.append(separator)
                        
                        # Add the formatted table to output
                        clean_text.append("\n".join(formatted_table))
            
            # Handle child page references
            elif block_type == "child_page":
                title = type_data.get("title", "")
                if title:
                    clean_text.append(f"## Page: {title}")
                    
            # Handle URL links
            elif block_type == "link_to_page":
                if "page_id" in type_data:
                    page_id = type_data["page_id"]
                    clean_text.append(f"[Linked Page]({page_id})")
                    
            # Handle bookmarks
            elif block_type == "bookmark":
                url = type_data.get("url", "")
                caption = ""
                caption_texts = type_data.get("caption", [])
                if caption_texts:
                    caption = " ".join([t.get("plain_text", "") for t in caption_texts])
                
                if url:
                    if caption:
                        clean_text.append(f"[{caption}]({url})")
                    else:
                        clean_text.append(f"[Bookmark]({url})")
            
            # Always check for children, whether or not has_children is true
            # This is important for toggle blocks which might have children in the API response
            if "children" in block and block_type != "table":  # Skip for tables as we process children differently
                child_content = self.extract_clean_content(block["children"])
                child_text = child_content.get("content", "")
                if child_text:
                    # Indent child content but use a more visible indentation for toggle content
                    if block_type == "toggle":
                        # Use a different indentation marker for toggle content
                        indented_text = "\n".join([f"  ▷ {line}" for line in child_text.split("\n")])
                    else:
                        indented_text = "\n".join([f"    {line}" for line in child_text.split("\n")])
                    clean_text.append(indented_text)
        
        return {"content": "\n\n".join(clean_text)}

def _simplify_notion_item(item: Dict) -> Dict:
    """Helper function to simplify a Notion page or database object."""
    simplified_item = {
        "object": item.get("object"),
        "id": item.get("id"),
        "created_time": item.get("created_time"),
        "last_edited_time": item.get("last_edited_time"),
        "archived": item.get("archived", False),
        "in_trash": item.get("in_trash", False),
        "parent": item.get("parent"),
        "title": ""
    }

    item_object_type = item.get("object")

    if item_object_type == "page":
        simplified_item["url"] = item.get("url")
        simplified_item["public_url"] = item.get("public_url")
        
        # Extract the page title from properties
        if "properties" in item:
            properties = item["properties"]
            if "title" in properties and isinstance(properties["title"], dict) and "title" in properties["title"]:
                title_property = properties["title"]["title"]
                if isinstance(title_property, list):
                    simplified_item["title"] = "".join([t.get("plain_text", "") for t in title_property])
            elif "Page" in properties and isinstance(properties["Page"], dict) and "title" in properties["Page"]: # Check for "Page" property
                page_property = properties["Page"]["title"]
                if isinstance(page_property, list):
                    simplified_item["title"] = "".join([t.get("plain_text", "") for t in page_property])

    elif item_object_type == "database":
        simplified_item["url"] = item.get("url") # Databases also have URLs
        # Database titles are directly in a 'title' array of rich text objects
        title_array = item.get("title", [])
        if isinstance(title_array, list):
            simplified_item["title"] = "".join([t.get("plain_text", "") for t in title_array])
            
    return simplified_item

@weave.op(name="notion-search")
def search(query: Optional[str] = None, filter: Optional[Dict] = None,
          start_cursor: Optional[str] = None, page_size: Optional[int] = None) -> Dict:
    """Search Notion database"""
    client = create_notion_client()
    raw_results = client.search(query=query, filter=filter, start_cursor=start_cursor, page_size=page_size)

    simplified_items = [_simplify_notion_item(item) for item in raw_results.get("results", [])]

    return {
        "object": raw_results.get("object"),
        "results": simplified_items,
        "next_cursor": raw_results.get("next_cursor"),
        "has_more": raw_results.get("has_more"),
        "type": raw_results.get("type"),
        "page_or_database": raw_results.get("page_or_database", {}),
        "request_id": raw_results.get("request_id")
    }

@weave.op(name="notion-list_pages")
def list_pages() -> Dict:
    """Get a simplified list of all available pages in Notion.
    Returns only essential metadata for each page."""
    # Use empty search to get all pages with hardcoded page_size=25
    result = search(query="", filter={"value": "page", "property": "object"}, page_size=50)
    
    # The search function now returns simplified items, so no need to simplify again here.
    # However, list_pages specifically deals with 'page' objects.
    # The search might return 'database' objects if filter is not strictly 'page'.
    # We'll rely on the search function's simplification which is now more generic.
    # If we strictly want only page fields as before, we might need to adjust _simplify_notion_item
    # or re-process here. For now, let's assume the generic simplification is fine.

    # If the intention of list_pages is to *only* list pages and *only* have page-specific simplified fields,
    # we might need a dedicated simplification or filter step.
    # For now, we assume that the `search` will provide adequately simplified items.
    # The `filter={"value": "page", "property": "object"}` should ensure only pages are returned by search.
    
    return result # search already returns the desired structure with simplified results

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
    
    # First get the page metadata to get the URL
    page_info = client.get_page(page_id)
    page_url = page_info.get("url", "")
    page_title = ""
    
    # Extract page title from properties
    if "properties" in page_info and "title" in page_info["properties"]:
        title_prop = page_info["properties"]["title"]
        if "title" in title_prop and title_prop["title"]:
            page_title = "".join([t.get("plain_text", "") for t in title_prop["title"]])
    
    # Also try to get title from Page property if it exists
    if not page_title and "properties" in page_info and "Page" in page_info["properties"]:
        page_prop = page_info["properties"]["Page"]
        if "title" in page_prop and page_prop["title"]:
            page_title = "".join([t.get("plain_text", "") for t in page_prop["title"]])
    
    # Get the page content
    blocks = client._fetch_all_children(page_id, start_cursor=start_cursor, page_size=page_size)
    
    if clean_content:
        content_result = client.extract_clean_content(blocks)
        # Add page metadata to the result
        content_result["page_url"] = page_url
        content_result["page_title"] = page_title
        return content_result
    
    return {
        "object": "list", 
        "results": blocks,
        "page_url": page_url,
        "page_title": page_title
    }

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
                "description": "Searches all titles of pages and databases in Notion that have been shared with the integration. Can search by title or filter to only pages/databases. When constructing queries: • Query around general subject matter. Use keywords that would likely be in the title of a page or database that contains relevant information. • Refine or expand query terms over time for incremental improvements.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find in page/database titles. Query around subject matter such that it likely will be in the title of a page or database."
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
                "name": "notion-list_pages",
                "description": "Retrieves a list of all accessible Notion pages with minimal metadata. Useful for discovering available pages without extra details. Returns only essential information: id, title, creation/edit times, archived status, and URLs.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        "implementation": list_pages
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