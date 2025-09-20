#!/usr/bin/env python3
"""
Voice-Controlled Note-Taking App (Tkinter + SpeechRecognition + pyttsx3 + SQLite)
Features:
- Record voice (background continuous recognition) and transcribe using Google Web Speech API.
- Save notes to local SQLite database with title, tags and timestamp.
- Search, export, play (TTS) and delete notes.
- Graceful fallback if SpeechRecognition or pyttsx3 are missing (instructs to install deps).
Notes:
- Requires internet for Google speech-to-text (recognize_google).
- Microphone support depends on PyAudio (install instructions in README.md).
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import threading, sqlite3, os, datetime, queue

# Try optional dependencies
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except Exception:
    SR_AVAILABLE = False

try:
    import pyttsx3
    TTS_AVAILABLE = True
except Exception:
    TTS_AVAILABLE = False

DB_PATH = os.path.join(os.path.dirname(__file__), "notes.db")

class NoteDB:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            tags TEXT,
            created_at TEXT
        );
        """
        self.conn.execute(sql)
        self.conn.commit()

    def add_note(self, title, content, tags):
        ts = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
        cur = self.conn.execute("INSERT INTO notes (title, content, tags, created_at) VALUES (?,?,?,?)",
                                (title, content, tags, ts))
        self.conn.commit()
        return cur.lastrowid

    def update_note(self, note_id, title, content, tags):
        self.conn.execute("UPDATE notes SET title=?, content=?, tags=? WHERE id=?",
                          (title, content, tags, note_id))
        self.conn.commit()

    def delete_note(self, note_id):
        self.conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.conn.commit()

    def get_all_notes(self):
        cur = self.conn.execute("SELECT * FROM notes ORDER BY created_at DESC")
        return cur.fetchall()

    def get_note_by_id(self, note_id):
        cur = self.conn.execute("SELECT * FROM notes WHERE id=?", (note_id,))
        return cur.fetchone()

    def search_notes(self, keyword):
        kw = f"%{keyword}%"
        cur = self.conn.execute("SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? OR tags LIKE ? ORDER BY created_at DESC",
                                (kw, kw, kw))
        return cur.fetchall()


class VoiceNoteApp:
    def __init__(self, root):
        self.root = root
        root.title("Voice-Controlled Note-Taking App")
        root.geometry("900x600")

        self.db = NoteDB()

        # Speech recognizer setup
        self.recognizer = sr.Recognizer() if SR_AVAILABLE else None
        self.microphone = None
        self.stop_listening = None
        self.listening = False

        if SR_AVAILABLE:
            try:
                self.microphone = sr.Microphone()
            except Exception:
                self.microphone = None

        # UI - left list, right editor
        self.left_frame = ttk.Frame(root, width=300)
        self.left_frame.pack(side="left", fill="y", padx=8, pady=8)
        self.right_frame = ttk.Frame(root)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=8, pady=8)

        # Left: notes list and controls
        ttk.Label(self.left_frame, text="Saved Notes").pack(anchor="w")
        self.notes_list = tk.Listbox(self.left_frame, width=40, height=30)
        self.notes_list.pack(side="left", fill="y")
        self.notes_list.bind("<<ListboxSelect>>", self.on_select_note)
        scrollbar = ttk.Scrollbar(self.left_frame, orient="vertical", command=self.notes_list.yview)
        scrollbar.pack(side="left", fill="y")
        self.notes_list.config(yscrollcommand=scrollbar.set)

        self.search_entry = ttk.Entry(self.left_frame)
        self.search_entry.pack(fill="x", pady=(6,2))
        self.search_entry.insert(0, "search... (press Enter)")
        self.search_entry.bind("<FocusIn>", lambda e: self.search_entry.delete(0, tk.END) if self.search_entry.get().startswith("search") else None)
        self.search_entry.bind("<Return>", lambda e: self.search_notes())

        ttk.Button(self.left_frame, text="New Note", command=self.new_note).pack(fill="x", pady=4)
        ttk.Button(self.left_frame, text="Delete Note", command=self.delete_note).pack(fill="x", pady=4)
        ttk.Button(self.left_frame, text="Export Note", command=self.export_note).pack(fill="x", pady=4)

        # Right: editor and controls
        title_frame = ttk.Frame(self.right_frame)
        title_frame.pack(fill="x")
        ttk.Label(title_frame, text="Title:").pack(side="left")
        self.title_entry = ttk.Entry(title_frame)
        self.title_entry.pack(side="left", fill="x", expand=True, padx=6)

        tags_frame = ttk.Frame(self.right_frame)
        tags_frame.pack(fill="x", pady=(6,0))
        ttk.Label(tags_frame, text="Tags:").pack(side="left")
        self.tags_entry = ttk.Entry(tags_frame)
        self.tags_entry.pack(side="left", fill="x", expand=True, padx=6)

        self.content_text = tk.Text(self.right_frame, wrap="word")
        self.content_text.pack(fill="both", expand=True, pady=(6,0))

        controls = ttk.Frame(self.right_frame)
        controls.pack(fill="x", pady=6)
        self.record_button = ttk.Button(controls, text="Start Recording", command=self.toggle_recording)
        self.record_button.pack(side="left", padx=4)
        ttk.Button(controls, text="Play (TTS)", command=self.play_note).pack(side="left", padx=4)
        ttk.Button(controls, text="Save Note", command=self.save_note).pack(side="left", padx=4)
        ttk.Button(controls, text="Refresh List", command=self.load_notes).pack(side="left", padx=4)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(root, textvariable=self.status_var).pack(side="bottom", fill="x")

        # internal state
        self.current_note_id = None
        self.load_notes()

    # ---------------- DB / UI helpers ----------------
    def load_notes(self, notes=None):
        if notes is None:
            notes = self.db.get_all_notes()
        self.notes_list.delete(0, tk.END)
        self.notes_map = []
        for row in notes:
            display = f"{row['title'] or '(no title)'} — {row['created_at'][:19]}"
            self.notes_list.insert(tk.END, display)
            self.notes_map.append(row['id'])

    def on_select_note(self, event=None):
        sel = self.notes_list.curselection()
        if not sel:
            return
        idx = sel[0]
        note_id = self.notes_map[idx]
        row = self.db.get_note_by_id(note_id)
        if row:
            self.current_note_id = row['id']
            self.title_entry.delete(0, tk.END); self.title_entry.insert(0, row['title'] or "")
            self.tags_entry.delete(0, tk.END); self.tags_entry.insert(0, row['tags'] or "")
            self.content_text.delete("1.0", tk.END); self.content_text.insert("1.0", row['content'] or "")
            self.status_var.set(f"Loaded note {row['id']}")

    def new_note(self):
        self.current_note_id = None
        self.title_entry.delete(0, tk.END)
        self.tags_entry.delete(0, tk.END)
        self.content_text.delete("1.0", tk.END)
        self.status_var.set("New blank note")

    def delete_note(self):
        sel = self.notes_list.curselection()
        if not sel:
            messagebox.showinfo("Delete", "Select a note to delete")
            return
        idx = sel[0]; note_id = self.notes_map[idx]
        if messagebox.askyesno("Confirm", "Delete selected note?"):
            self.db.delete_note(note_id)
            self.load_notes()
            self.new_note()
            self.status_var.set("Note deleted")

    def export_note(self):
        if self.current_note_id is None:
            messagebox.showinfo("Export", "Select or save a note first")
            return
        row = self.db.get_note_by_id(self.current_note_id)
        if not row:
            messagebox.showerror("Export", "Note not found")
            return
        default_name = (row['title'] or "note").replace(" ", "_")[:40] + ".txt"
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=default_name)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"Title: {row['title']}\nTags: {row['tags']}\nCreated: {row['created_at']}\n\n{row['content']}")
            messagebox.showinfo("Exported", f"Exported to {path}")

    def search_notes(self):
        q = self.search_entry.get().strip()
        if not q:
            self.load_notes()
        else:
            found = self.db.search_notes(q)
            self.load_notes(found)

    # ---------------- Recording / Recognition ----------------
    def toggle_recording(self):
        if not SR_AVAILABLE:
            messagebox.showerror("Missing Dependency", "SpeechRecognition is not installed. See README for setup.")
            return
        if not self.microphone:
            messagebox.showerror("Microphone", "No working microphone found or PyAudio not installed. See README.")
            return
        if not self.listening:
            # start background listening
            try:
                self.stop_listening = self.recognizer.listen_in_background(self.microphone, self._callback)
                self.listening = True
                self.record_button.config(text="Stop Recording")
                self.status_var.set("Recording... (background). Click Stop to finish.")
            except Exception as e:
                messagebox.showerror("Recording Error", str(e))
        else:
            # stop background listening
            try:
                if callable(self.stop_listening):
                    self.stop_listening(wait_for_stop=False)
                self.stop_listening = None
            except Exception:
                try:
                    self.stop_listening()
                except Exception:
                    pass
            self.listening = False
            self.record_button.config(text="Start Recording")
            self.status_var.set("Stopped recording")

    def _callback(self, recognizer, audio):
        # Called from background thread when a phrase is detected.
        try:
            text = recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            text = ""  # nothing recognized
        except Exception as e:
            text = f"[error: {e}]"
        if text:
            # append to text widget safely in main thread
            self.root.after(0, lambda: self._append_text(text))

    def _append_text(self, text):
        cur = self.content_text
        if cur.get("1.0", tk.END).strip():
            cur.insert(tk.END, " " + text)
        else:
            cur.insert(tk.END, text)
        self.status_var.set("Transcribed a phrase")

    # ---------------- Text-to-speech ----------------
    def play_note(self):
        content = self.content_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Play", "Nothing to read")
            return
        if not TTS_AVAILABLE:
            messagebox.showerror("Missing Dependency", "pyttsx3 is not installed. See README.")
            return
        def _play():
            engine = pyttsx3.init()
            engine.say(content)
            engine.runAndWait()
        threading.Thread(target=_play, daemon=True).start()

    # ---------------- Save ----------------
    def save_note(self):
        title = self.title_entry.get().strip()
        tags = self.tags_entry.get().strip()
        content = self.content_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Save", "Note content is empty")
            return
        if not title:
            title = content.strip().splitlines()[0][:60] if content.strip() else "(no title)"
        if self.current_note_id is None:
            nid = self.db.add_note(title, content, tags)
            self.current_note_id = nid
            self.status_var.set("Saved new note")
        else:
            self.db.update_note(self.current_note_id, title, content, tags)
            self.status_var.set("Updated note")
        self.load_notes()

def main():
    root = tk.Tk()
    app = VoiceNoteApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
