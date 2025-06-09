"""Voice Interface for MCPHost
Provides Whisper speech-to-text input and text-to-speech output for mcphost
"""

from .voice_mcphost import VoiceMCPHost
from .version import __version__

__all__ = ['VoiceMCPHost', '__version__']