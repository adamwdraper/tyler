# Audio processing

The audio module provides tools for text-to-speech synthesis and speech-to-text transcription using advanced AI models.

## Available tools

### Text-to-speech

Convert text to natural-sounding speech using AI voices.

#### Parameters

- `input` (string, required)
  - Text to convert to speech
  - Maximum 4096 characters

- `voice` (string, optional)
  - Voice to use for speech generation
  - Options:
    - `alloy` (default)
    - `echo`
    - `fable`
    - `onyx`
    - `nova`
    - `shimmer`

- `model` (string, optional)
  - Model to use for generation
  - Options:
    - `tts-1` (default)
    - `tts-1-hd`

- `response_format` (string, optional)
  - Audio file format
  - Options:
    - `mp3` (default)
    - `opus`
    - `aac`
    - `flac`

- `speed` (float, optional)
  - Speed of generated audio
  - Range: 0.25 to 4.0
  - Default: 1.0

#### Returns

A tuple containing:

1. Status dictionary:
   - `success`: Boolean indicating success
   - `description`: Description of generated audio
   - `details`: Dictionary containing:
     - `filename`: Generated audio filename
     - `voice`: Voice used
     - `model`: Model used
     - `format`: Audio format
     - `speed`: Speed setting
     - `text_length`: Length of input text
   - `error`: Error message if failed

2. Files array containing:
   - `content`: Audio file content (bytes)
   - `filename`: Audio filename
   - `mime_type`: Audio MIME type
   - `description`: Audio description

### Speech-to-text

Transcribe speech from audio files to text.

#### Parameters

- `file_url` (string, required)
  - Path to the audio file
  - Must be a valid local file path

- `language` (string, optional)
  - Language code in ISO-639-1 format
  - If not specified, auto-detects language

- `prompt` (string, optional)
  - Text to guide transcription style
  - Useful for continuing previous segments

#### Returns

A dictionary containing:
- `success`: Boolean indicating success
- `text`: Transcribed text
- `details`: Dictionary containing:
  - `model`: Model used
  - `language`: Language detected/used
  - `file_url`: Original file path
- `error`: Error message if failed

## Example usage

```python
from tyler.models import Agent, Thread, Message

# Create an agent with audio tools
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with audio processing",
    tools=["audio"]
)

# Create a thread for text-to-speech
thread = Thread()
message = Message(
    role="user",
    content='Convert this text to speech: "Hello, how are you today?"'
)
thread.add_message(message)

# Process the thread - agent will use text-to-speech tool
processed_thread, new_messages = await agent.go(thread)

# Example of speech-to-text
transcribe_thread = Thread()
message = Message(
    role="user",
    content="Transcribe the audio from recording.mp3"
)
transcribe_thread.add_message(message)

# Process the thread - agent will use speech-to-text tool
processed_transcription, new_messages = await agent.go(transcribe_thread)
```

## Best practices

1. **Text-to-Speech**
   - Keep text within length limits
   - Choose appropriate voice for content
   - Consider audio quality needs
   - Use natural language input

2. **Speech-to-Text**
   - Use high-quality audio input
   - Specify language when known
   - Provide context with prompts
   - Consider audio format support

3. **Audio Quality**
   - Select appropriate formats
   - Use HD models when needed
   - Adjust speed carefully
   - Monitor file sizes

4. **Resource Management**
   - Handle large files properly
   - Monitor API usage
   - Manage storage space
   - Consider bandwidth usage

## Common use cases

1. **Content Creation**
   - Audiobook generation
   - Voice-over production
   - Podcast content
   - Educational materials

2. **Accessibility**
   - Text-to-speech for visually impaired
   - Transcription for hearing impaired
   - Multi-language support
   - Audio documentation

3. **Audio Processing**
   - Meeting transcription
   - Voice note conversion
   - Audio content analysis
   - Language learning tools

## Limitations

1. **Text-to-Speech**
   - 4096 character limit per request
   - Limited voice options
   - Language constraints
   - Pronunciation accuracy

2. **Speech-to-Text**
   - Background noise sensitivity
   - Accent recognition
   - Speaker separation
   - Technical terminology

3. **General Constraints**
   - API rate limits
   - File size limits
   - Processing time
   - Cost considerations

## Error handling

Common errors and solutions:

1. **Input Validation**
   - Check text length
   - Verify file formats
   - Validate parameters
   - Handle special characters

2. **Processing Issues**
   - Handle API errors
   - Manage timeouts
   - Process format errors
   - Handle quality issues

3. **Resource Errors**
   - Monitor API quotas
   - Handle storage limits
   - Manage bandwidth
   - Control concurrency 