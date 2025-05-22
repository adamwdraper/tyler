# Image generation and analysis

The image module provides tools for generating and analyzing images using advanced AI models. These tools allow you to create high-quality images from text descriptions and analyze existing images.

## Configuration

Before using image tools, you need to set up your OpenAI API key:

```bash
OPENAI_API_KEY=your-openai-key
```

You can get an API key from the [OpenAI platform](https://platform.openai.com/api-keys).

## Available tools

### Image-generate

Generates images based on text descriptions using DALL-E 3.

#### Parameters

- `prompt` (string, required)
  - Text description of the desired image
  - Maximum 4000 characters

- `size` (string, optional)
  - Size of the generated image
  - Options:
    - `1024x1024` (default)
    - `1792x1024`
    - `1024x1792`

- `quality` (string, optional)
  - Quality level of the generated image
  - Options:
    - `standard` (default)
    - `hd`

- `style` (string, optional)
  - Visual style of the generated image
  - Options:
    - `vivid` (default)
    - `natural`

#### Returns

A dictionary containing:
- `success`: Boolean indicating success
- `description`: Revised prompt used for generation
- `details`: Dictionary containing:
  - `filename`: Generated image filename
  - `size`: Image dimensions used
  - `quality`: Quality setting used
  - `style`: Style setting used
  - `created`: Timestamp
- `error`: Error message if failed

Files array containing:
- `content`: Base64 encoded image data
- `filename`: Image filename
- `mime_type`: Image format (e.g., "image/png")
- `description`: Image description

### Analyze-image

Analyzes and describes the contents of an image using GPT-4V.

#### Parameters

- `file_url` (string, required)
  - Path to the image file
  - Must be a valid local file path or URL

- `prompt` (string, optional)
  - Custom prompt to guide the analysis
  - Use to focus on specific aspects of the image

#### Returns

A dictionary containing:
- `success`: Boolean indicating success
- `analysis`: Detailed analysis of the image
- `file_url`: Original image path
- `error`: Error message if failed

## Example usage

```python
from tyler.models import Agent, Thread, Message

# Create an agent with image tools
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with image generation and analysis",
    tools=["image"]
)

# Create a thread for image generation
thread = Thread()
message = Message(
    role="user",
    content="Generate an image of a serene Japanese garden"
)
thread.add_message(message)

# Process the thread - agent will use image-generate tool
processed_thread, new_messages = await agent.go(thread)

# Example of image analysis
analysis_thread = Thread()
message = Message(
    role="user",
    content="Analyze the artistic style of the image at /path/to/image.jpg"
)
analysis_thread.add_message(message)

# Process the thread - agent will use analyze-image tool
processed_analysis, new_messages = await agent.go(analysis_thread)
```

## Best practices

1. **Effective Prompting**
   - Be specific and detailed in descriptions
   - Include style preferences when relevant
   - Consider composition and layout
   - Use clear, unambiguous language

2. **Image Generation Settings**
   - Choose appropriate size for the use case:
     - `1024x1024` for balanced compositions
     - `1792x1024` for landscapes
     - `1024x1792` for portraits
   - Select quality based on needs:
     - `hd` for professional/detailed work
     - `standard` for prototypes/drafts
   - Pick style to match content:
     - `vivid` for dramatic/digital art
     - `natural` for photorealistic results

3. **Image Analysis**
   - Provide clear analysis prompts
   - Focus on specific aspects
   - Use domain-specific terminology
   - Consider context and purpose

4. **Error Handling**
   - Validate input parameters
   - Check file paths and URLs
   - Handle API rate limits
   - Process responses appropriately

## Common use cases

1. **Content Creation**
   - Marketing materials
   - Website illustrations
   - Social media content
   - Educational resources

2. **Visual Analysis**
   - Art critique
   - Design feedback
   - Content moderation
   - Technical inspection

3. **Creative Assistance**
   - Concept visualization
   - Storyboarding
   - Mood boards
   - Style exploration

## Limitations

1. **Generation Constraints**
   - 4000 character prompt limit
   - Fixed size options
   - Content safety filters
   - No real person generation

2. **Analysis Constraints**
   - Text recognition accuracy varies
   - Complex scene understanding
   - Cultural context awareness
   - Technical detail precision

## Error handling

Common errors and solutions:

1. **API Errors**
   - Check API key validity
   - Monitor rate limits
   - Handle timeouts
   - Validate responses

2. **Content Filters**
   - Review content guidelines
   - Adjust descriptions
   - Check restricted content

3. **File Operations**
   - Verify file paths
   - Check permissions
   - Validate formats
   - Handle large files 