# Voice-Controlled Note-Taking App

A simple Voice-Controlled Note-Taking desktop app built with Python (Tkinter GUI). It uses the SpeechRecognition library (Google Web Speech API) for speech-to-text, pyttsx3 for text-to-speech, and SQLite for storage.

## Features
- Record voice (background continuous recognition) and transcribe to the editor.
- Save notes with title and tags to a local SQLite database (`notes.db`).
- Search, export, play (TTS) and delete notes.
- Lightweight GUI (Tkinter) suitable for demo and resume projects.

## Files in this package
- `main.py` — The main application script (run this).
- `requirements.txt` — Python dependencies (see note on PyAudio below).
- `README.md` — This file.
- `notes.db` — (created on first run) SQLite database file.

## Prerequisites
- Python 3.8 or newer.
- pip (package manager).
- A working microphone device.
- Internet connection for Google Web Speech API (`recognize_google`) unless you swap to an offline engine.

## Install (recommended: virtual environment)
```bash
python -m venv venv
# Windows
venv\\Scripts\\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### PyAudio (microphone) installation notes
The `speech_recognition` library typically requires PyAudio for microphone input. Installing PyAudio can be OS-dependent:

- **Windows (easiest)**:
  ```bash
  pip install pipwin
  pipwin install pyaudio
  ```
  If `pipwin` is not available, you can download a prebuilt wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio and `pip install <wheel-file>`.

- **Ubuntu / Debian**:
  ```bash
  sudo apt update
  sudo apt install -y portaudio19-dev python3-dev
  pip install pyaudio
  ```

- **macOS** (with Homebrew):
  ```bash
  brew install portaudio
  pip install pyaudio
  ```

If you have trouble installing PyAudio, the app will still run but microphone recording may not be available.

## Run the app
```bash
python main.py
```

## Quick usage guide
1. Launch the app.
2. Click **Start Recording** — the app begins background recording and transcribing small phrases automatically.
3. Speak clearly near your microphone. Recognized phrases are appended to the editor.
4. Click **Stop Recording** (the same button toggles) to finish.
5. Edit the note, add a title/tags and click **Save Note**.
6. Use **Play (TTS)** to hear the note read aloud.
7. Select a saved note on the left to view/edit/export/delete it.

## Troubleshooting
- If speech is not being recognized, ensure your microphone is working and PyAudio is installed.
- If you see errors about `pyttsx3`, install it with `pip install pyttsx3`.
- The recognizer uses Google Web Speech API (online); for offline speech recognition consider Vosk (requires downloading an acoustic model).

## Extensions / Ideas
- Add autosave, multi-language support, timestamped transcripts, or sync with cloud storage (Firebase).
- Replace Google recognizer with an offline engine (Vosk) for privacy and offline use.
- Add tagging filters and export to markdown / PDF.

---
Made as a mini project for resume/interview demos.
