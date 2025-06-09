"""Text processing utilities for voice MCPHost."""

import re


def clean_text_for_speech(text):
    """Clean text to make it more suitable for TTS.
    
    Args:
        text (str): Input text to clean
        
    Returns:
        str: Cleaned text optimized for speech
    """
    # Remove common formatting that doesn't sound good
    text = text.replace("**", "")
    text = text.replace("*", "")
    text = text.replace("#", "")
    text = text.replace("`", "")
    text = text.replace("```", "")

    # Remove markdown links
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Replace some technical terms with more speakable versions
    replacements = {
        "CLI": "command line",
        "API": "A P I",
        "JSON": "J SON",
        "HTTP": "H T T P",
        "URL": "U R L", 
        "SSH": "S S H",
        "CPU": "C P U",
        "GPU": "G P U",
        "RAM": "R A M"
    }
    
    for term, replacement in replacements.items():
        text = text.replace(term, replacement)

    # Limit length for TTS (very long responses can be overwhelming)
    if len(text) > 500:
        text = text[:500] + "... The response was truncated for speech."

    return text


def clean_mcphost_response(response):
    """Clean up MCPHost response by removing debug info and formatting.
    
    Args:
        response (str): Raw response from MCPHost
        
    Returns:
        str: Cleaned response text
    """
    if not response:
        return ""

    lines = response.split('\n')
    cleaned_lines = []

    skip_patterns = [
        'DEBUG', 'INFO', '2025/', 'creating message', 'sending messages',
        '\x1b', 'ESC', 'command:', 'args:', 'buffer', 'before', 'after'
    ]

    for line in lines:
        # Skip debug lines, timestamps, escape sequences, and empty lines
        if any(skip in line for skip in skip_patterns):
            continue
        if line.strip() == "":
            continue
        # Skip lines that are mostly control characters
        if len(line.strip()) > 0 and len([c for c in line if ord(c) < 32]) > len(line) // 2:
            continue

        cleaned_lines.append(line.strip())

    # Join and clean up
    result = ' '.join(cleaned_lines)

    # Remove any remaining technical artifacts and control characters
    result = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', result)  # Remove control characters
    result = re.sub(r'<[^>]+>', '', result)  # Remove XML-like tags
    result = re.sub(r'\s+', ' ', result)  # Normalize whitespace

    return result.strip()