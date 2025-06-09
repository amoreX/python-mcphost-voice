"""Main VoiceMCPHost implementation."""

import os
import sys
import time
import threading
import queue
import whisper
import pyttsx3
import subprocess

from .text_utils import clean_text_for_speech, clean_mcphost_response
from .mcphost_runner import MCPHostRunner


class VoiceMCPHost:
    """Voice interface for MCPHost with speech-to-text and text-to-speech capabilities."""

    def __init__(self, model="ollama:qwen3:8b", config_path="/home/nihal/config.json",
                 whisper_model="small", response_timeout=30):
        """Initialize VoiceMCPHost.
        
        Args:
            model (str): Model identifier to use with MCPHost
            config_path (str): Path to MCPHost config file
            whisper_model (str): Whisper model to use for speech recognition
            response_timeout (int): Timeout in seconds for waiting for responses
        """
        self.model = model
        self.config_path = config_path
        self.audio_file = "voice.wav"
        self.response_timeout = response_timeout

        # Initialize MCPHost runner
        self.mcphost = MCPHostRunner(model, config_path, response_timeout)

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
        """Background worker for text-to-speech."""
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
        """Records audio from the microphone and transcribes it using Whisper.

        Returns:
            str or None: The transcribed text, or None if no speech detected
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
        """Add text to TTS queue.
        
        Args:
            text (str): Text to speak
        """
        clean_text = clean_text_for_speech(text)
        self.tts_queue.put(clean_text)

    def run_interactive(self):
        """Main interactive loop."""
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
                response = self.mcphost.run_mcphost(user_input)
                if response:
                    clean_response = clean_mcphost_response(response)
                    print(f"🤖 MCPHost response:\n{clean_response}")
                    self.speak_text(clean_response)

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