import subprocess
import whisper
import os
import time

AUDIO_FILE = "voice.wav"
WHISPER_MODEL = "small"

def record_audio():
    print("🎤 Recording... Press ENTER to stop.")
    proc = subprocess.Popen([
        "arecord", "-f", "cd", "-t", "wav", "-r", "16000", AUDIO_FILE
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        input()
    except KeyboardInterrupt:
        proc.terminate()
        raise
    proc.terminate()
    proc.wait()
    return os.path.exists(AUDIO_FILE) and os.path.getsize(AUDIO_FILE) > 0

def transcribe():
    print("🧠 Transcribing...")
    model = whisper.load_model(WHISPER_MODEL)
    result = model.transcribe(AUDIO_FILE)
    return result["text"].strip()

def switch_to_mcphost_window():
    print("🔀 Switching window with Alt+Tab...")
    subprocess.run(["xdotool", "key", "Alt_L+Tab"])
    time.sleep(1.5)  # Give it time to switch and load

def type_into_terminal(text):
    switch_to_mcphost_window()
    print(f"⌨️ Typing: {text}")
    subprocess.run(["xdotool", "type", "--delay", "50", text])
    subprocess.run(["xdotool", "key", "Return"])

def main():
    print("🎙️ Voice to MCPHost ready. Press ENTER to record.")
    while True:
        try:
            input("🔴 Press ENTER to start recording...")
            if not record_audio():
                print("❌ No audio recorded.")
                continue
            prompt = transcribe()
            if not prompt:
                print("❓ Nothing transcribed.")
                continue
            print(f"🗣️ You said: {prompt}")
            if prompt.lower() in ["exit", "quit", "bye", "stop"]:
                print("👋 Exiting.")
                break
            type_into_terminal(prompt)
        except KeyboardInterrupt:
            print("\n👋 Stopped by user.")
            break
        finally:
            if os.path.exists(AUDIO_FILE):
                os.remove(AUDIO_FILE)

if __name__ == "__main__":
    main()
