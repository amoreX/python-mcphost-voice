#!/usr/bin/env python3
"""
Voice Interface for MCPHost
Provides Whisper speech-to-text input and text-to-speech output for mcphost
"""

import subprocess
import whisper
import pyttsx3
import sys
import threading
import queue
import time
import os
import re
import select
from pathlib import Path

class VoiceMCPHost:
    def __init__(self, model="ollama:qwen3:8b", config_path="/home/nihal/config.json",
                 whisper_model="small", response_timeout=30):
        self.model = model
        self.config_path = config_path
        self.audio_file = "voice.wav"
        self.response_timeout = response_timeout

        # Initialize Whisper
        print(f"🧠 Loading Whisper model '{whisper_model}'...")
        self.whisper_model = whisper.load_model(whisper_model)
        print("✅ Whisper model loaded!")

        # Initialize text-to-speech
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)  # Speed of speech
        self.tts_engine.setProperty('volume', 0.9)  # Volume level

        # Queue for TTS to avoid blocking
        self.tts_queue = queue.Queue()
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.tts_thread.start()

        print("🎤 Voice MCPHost initialized!")
        print("Press ENTER to start/stop recordings")
        print("Press Ctrl+C to interrupt")

    def _tts_worker(self):
        """Background worker for text-to-speech"""
        while True:
            try:
                text = self.tts_queue.get(timeout=1)
                if text is None:
                    break
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
                self.tts_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"TTS Error: {e}")

    def record_and_transcribe(self):
        """
        Records audio from the microphone and transcribes it using Whisper.

        Returns:
            str: The transcribed text.
        """
        print("🎤 Recording... Press ENTER to stop.")

        # Start arecord as a background process
        process = subprocess.Popen([
            "arecord", "-f", "cd", "-t", "wav", "-r", "16000", self.audio_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        try:
            input()  # Wait for user to press Enter
        except KeyboardInterrupt:
            process.terminate()
            process.wait()
            raise

        process.terminate()  # Stop recording
        process.wait()

        # Check if audio file was created and has content
        if not os.path.exists(self.audio_file) or os.path.getsize(self.audio_file) == 0:
            print("❌ No audio recorded or file is empty")
            return None

        print("🧠 Transcribing...")
        try:
            result = self.whisper_model.transcribe(self.audio_file)
            transcribed_text = result["text"].strip()

            if not transcribed_text:
                print("❓ No speech detected in audio")
                return None

            return transcribed_text
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            return None
        finally:
            # Clean up audio file
            try:
                os.remove(self.audio_file)
            except:
                pass

    def speak_text(self, text):
        """Add text to TTS queue"""
        # Clean up text for better speech
        clean_text = self._clean_text_for_speech(text)
        self.tts_queue.put(clean_text)

    def _clean_text_for_speech(self, text):
        """Clean text to make it more suitable for TTS"""
        # Remove common formatting that doesn't sound good
        text = text.replace("**", "")
        text = text.replace("*", "")
        text = text.replace("#", "")
        text = text.replace("`", "")
        text = text.replace("```", "")

        # Remove markdown links
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Replace some technical terms with more speakable versions
        text = text.replace("CLI", "command line")
        text = text.replace("API", "A P I")
        text = text.replace("JSON", "J SON")
        text = text.replace("HTTP", "H T T P")
        text = text.replace("URL", "U R L")
        text = text.replace("SSH", "S S H")
        text = text.replace("CPU", "C P U")
        text = text.replace("GPU", "G P U")
        text = text.replace("RAM", "R A M")

        # Limit length for TTS (very long responses can be overwhelming)
        if len(text) > 500:
            text = text[:500] + "... The response was truncated for speech."

        return text

    def _read_line_with_timeout(self, pipe, timeout):
        """Read a line from pipe with timeout"""
        if sys.platform == "win32":
            # Windows doesn't support select on pipes
            try:
                return pipe.readline()
            except:
                return None
        else:
            # Unix/Linux
            ready, _, _ = select.select([pipe], [], [], timeout)
            if ready:
                try:
                    return pipe.readline()
                except:
                    return None
            return None

    def _clean_mcphost_response(self, response):
        """Clean up MCPHost response by removing debug info and formatting"""
        if not response:
            return ""

        lines = response.split('\n')
        cleaned_lines = []

        for line in lines:
            # Skip debug lines, timestamps, escape sequences, and empty lines
            if any(skip in line for skip in [
                'DEBUG', 'INFO', '2025/', 'creating message', 'sending messages',
                '\x1b', 'ESC', 'command:', 'args:', 'buffer', 'before', 'after'
            ]):
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

    def run_mcphost(self, prompt):
        """Run mcphost with the given prompt and return output"""
        # Try basic approach first (more reliable in this case)
        try:
            return self.run_mcphost_basic(prompt)
        except Exception as e:
            print(f"⚠️ Basic approach failed: {e}, trying pexpect")
            try:
                return self.run_mcphost_with_pexpect(prompt)
            except ImportError:
                return "Both approaches failed and pexpect not available"
            except Exception as e2:
                return f"Both approaches failed. Basic: {e}, Pexpect: {e2}"

    def run_mcphost_with_pexpect(self, prompt):
        """Run mcphost using pexpect for better interactive handling"""
        try:
            import pexpect

            print(f"🤖 Sending to MCPHost (pexpect): {prompt}")

            # Spawn mcphost with proper environment
            cmd = f"mcphost -m {self.model} --config {self.config_path}"
            child = pexpect.spawn(cmd, env={'TERM': 'dumb'})  # Use dumb terminal to avoid escape sequences
            child.timeout = 10  # Shorter timeout for initial setup
            child.logfile_read = sys.stdout.buffer  # Enable logging for debugging

            # Read initial output and look for any prompt-like text
            try:
                # Look for various possible prompt patterns
                index = child.expect([
                    r"Enter your prompt.*",
                    r"prompt.*",
                    r"You:.*",
                    r"User:.*",
                    r">>.*",
                    r">.*",
                    pexpect.TIMEOUT
                ], timeout=15)

                if index == 6:  # TIMEOUT
                    print("⚠️ Timeout waiting for initial prompt, trying to send anyway...")
                else:
                    print(f"✅ Found prompt pattern {index}")

            except pexpect.TIMEOUT:
                print("⚠️ No clear prompt found, continuing anyway...")

            # Send our prompt regardless
            child.sendline(prompt)

            # Look for assistant response with more flexible patterns
            assistant_found = False
            response_text = ""

            try:
                # Wait for assistant response with multiple possible patterns
                index = child.expect([
                    r"Assistant:.*",
                    r"Response:.*",
                    r"AI:.*",
                    pexpect.TIMEOUT
                ], timeout=self.response_timeout)

                if index < 3:  # Found assistant response
                    assistant_found = True
                    print(f"✅ Found assistant response pattern {index}")

                    # Read until we see another prompt or timeout
                    child.timeout = 5  # Shorter timeout for reading response
                    response_parts = []

                    while True:
                        try:
                            index = child.expect([
                                r"Enter your prompt.*",
                                r"prompt.*",
                                r"You:.*",
                                r">>.*",
                                pexpect.TIMEOUT,
                                pexpect.EOF
                            ], timeout=5)

                            if index < 4:  # Found next prompt
                                response_text = child.before.decode('utf-8', errors='ignore')
                                break
                            elif index == 4:  # TIMEOUT - might be end of response
                                response_text += child.before.decode('utf-8', errors='ignore')
                                break
                            else:  # EOF
                                response_text += child.before.decode('utf-8', errors='ignore')
                                break

                        except pexpect.TIMEOUT:
                            # Collect what we have so far
                            response_text += child.before.decode('utf-8', errors='ignore')
                            break

                else:
                    print("⚠️ No assistant response pattern found")

            except pexpect.TIMEOUT:
                print("⚠️ Timeout waiting for assistant response")
                # Try to get whatever output we have
                response_text = child.before.decode('utf-8', errors='ignore')

            child.close()

            if response_text:
                cleaned_response = self._clean_mcphost_response(response_text)
                return cleaned_response if cleaned_response else "Empty response after cleaning"
            else:
                return "No response text captured"

        except Exception as e:
            return f"Error with pexpect approach: {str(e)}"

    def run_mcphost_basic(self, prompt):
        """Basic approach for running mcphost (fallback) - RAW OUTPUT"""
        try:
            # Prepare the command
            cmd = [
                "mcphost",
                "-m", self.model,
                "--config", self.config_path
            ]

            print(f"🤖 Sending to MCPHost (basic): {prompt}")

            # Use Popen for interactive communication
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,  # Unbuffered
                universal_newlines=True
            )

            # Send the prompt
            process.stdin.write(prompt + "\n")
            process.stdin.flush()

            # Collect ALL output - no filtering
            all_output = ""
            stderr_output = ""

            # Read output line by line with timeout
            start_time = time.time()

            while time.time() - start_time < self.response_timeout:
                try:
                    # Check if process is still running
                    if process.poll() is not None:
                        break

                    # Try to read a line with a short timeout
                    line = self._read_line_with_timeout(process.stdout, 1.0)
                    if line is not None:
                        all_output += line
                        print(f"STDOUT: {repr(line)}")  # Show exactly what we get

                    # Also try to read stderr
                    stderr_line = self._read_line_with_timeout(process.stderr, 0.1)
                    if stderr_line is not None:
                        stderr_output += stderr_line
                        print(f"STDERR: {repr(stderr_line)}")  # Show exactly what we get

                except Exception as e:
                    print(f"Error reading output: {e}")
                    break

            # Clean up the process
            try:
                process.stdin.write("quit\n")
                process.stdin.flush()
                time.sleep(0.5)
            except:
                pass

            try:
                process.terminate()
                process.wait(timeout=2)
            except:
                process.kill()

            # Return RAW output - no cleaning
            print("\n" + "="*50)
            print("RAW STDOUT OUTPUT:")
            print(repr(all_output))
            print("\n" + "="*50)
            print("RAW STDERR OUTPUT:")
            print(repr(stderr_output))
            print("="*50)

            return f"STDOUT:\n{all_output}\n\nSTDERR:\n{stderr_output}"

        except Exception as e:
            error_msg = f"Error running MCPHost: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg

    def run_interactive(self):
        """Main interactive loop"""
        print("\n🎙️  Voice MCPHost is ready!")
        print("Press ENTER to start recording, then ENTER again to stop and process...")

        # Give a welcome message
        welcome_msg = "Voice MCPHost with Whisper is ready. Press enter to start recording."
        self.speak_text(welcome_msg)

        try:
            while True:
                # Record and transcribe speech
                user_input = self.record_and_transcribe()

                if not user_input:
                    print("🔄 No input detected, try again...")
                    continue

                print(f"🗣️ You said: {user_input}")

                # Check for exit commands
                if user_input.lower() in ['exit', 'quit', 'goodbye', 'stop', 'bye']:
                    goodbye_msg = "Goodbye! Thanks for using Voice MCPHost!"
                    print(f"👋 {goodbye_msg}")
                    self.speak_text(goodbye_msg)
                    time.sleep(3)  # Give TTS time to finish
                    break

                # Send to MCPHost
                response = self.run_mcphost(user_input)

                if response:
                    print(f"🤖 MCPHost response:\n{response}")

                    # Speak the response
                    self.speak_text(response)

                print("\n" + "="*50)
                print("🎤 Press ENTER to record again or say 'exit' to quit...")

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user. Goodbye!")
            self.speak_text("Goodbye!")
            time.sleep(2)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            error_msg = "An error occurred. Please check the console for details."
            self.speak_text(error_msg)
        finally:
            # Cleanup
            self.tts_queue.put(None)  # Signal TTS thread to stop
            # Clean up any remaining audio file
            try:
                os.remove(self.audio_file)
            except:
                pass

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
            print("Usage: python voice_mcphost.py [model] [config_path] [--whisper-model MODEL] [--timeout SECONDS]")
            print("Whisper models: tiny, base, small, medium, large")
            print("Example: python voice_mcphost.py 'ollama:qwen3:8b' '/home/nihal/config.json' --whisper-model base --timeout 45")
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
