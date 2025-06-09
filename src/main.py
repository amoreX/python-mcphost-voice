#!/usr/bin/env python3
"""
Voice Interface for MCPHost - Main Script
Provides Whisper speech-to-text input and text-to-speech output for mcphost
"""

import sys
from voice_mcp import VoiceMCPHost


def main():
    """Main function"""
    # Default parameters
    model = "ollama:qwen3:8b"
    config_path = "/home/nihal/config.json"
    whisper_model = "small"
    response_timeout = 30

    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("Usage: python main.py [model] [config_path] [--whisper-model MODEL] [--timeout SECONDS]")
            print("Whisper models: tiny, base, small, medium, large")
            print("Example: python main.py 'ollama:qwen3:8b' '/home/nihal/config.json' --whisper-model base --timeout 45")
            return
        model = sys.argv[1]

    if len(sys.argv) > 2:
        config_path = sys.argv[2]

    # Check for whisper model argument
    for i, arg in enumerate(sys.argv):
        if arg == "--whisper-model" and i + 1 < len(sys.argv):
            whisper_model = sys.argv[i + 1]
            print(f"Using Whisper model: {whisper_model}")
        elif arg == "--timeout" and i + 1 < len(sys.argv):
            try:
                response_timeout = int(sys.argv[i + 1])
                print(f"Using timeout: {response_timeout} seconds")
            except ValueError:
                print("Warning: Invalid timeout value, using default 30 seconds")

    try:
        # Create and run voice interface
        voice_mcphost = VoiceMCPHost(
            model=model,
            config_path=config_path,
            whisper_model=whisper_model,
            response_timeout=response_timeout
        )
        voice_mcphost.run_interactive()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()