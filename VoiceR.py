#!/usr/bin/env python3

import os
import json
import subprocess
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import time
import sys
import threading
import tkinter as tk
from tkinter import simpledialog, messagebox, ttk

# ---------------------------
# SETTINGS
# ---------------------------

APP_DIR = os.path.dirname(os.path.realpath(__file__))
COMMANDS_FILE = os.path.join(os.path.expanduser("~"), ".voicer_commands.json")


# Detect the directory of the running script
APP_DIR = os.path.dirname(os.path.realpath(__file__))

# Model folder inside the AppImage
MODEL_PATH = os.path.join(APP_DIR, "vosk-model-small-en-us-0.15")

WINDOW_NAME_SUBSTRING = "DARK SOULS II"

# Default commands
DEFAULT_COMMANDS = {
    "jump": {"key": "space", "hold": False},
    "attack": {"key": "ctrl", "hold": False},
    "reload": {"key": "r", "hold": False},
    "crouch": {"key": "c", "hold": False},
    "forward": {"key": "w", "hold": True},
    "left": {"key": "a", "hold": True},
    "right": {"key": "d", "hold": True},
    "back": {"key": "s", "hold": True},
    "hit": {"key": "h", "hold": False},
}

COOLDOWN = 0.15
last_time = 0
last_command = {}
holding_keys = {}
active_commands = set()
running = False

# ---------------------------
# LOAD / SAVE COMMANDS
# ---------------------------

def load_commands():
    try:
        if os.path.exists(COMMANDS_FILE):
            with open(COMMANDS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception as e:
        print("Failed to load commands:", e)

    return DEFAULT_COMMANDS.copy()


def save_commands(commands):
    with open(COMMANDS_FILE, "w") as f:
        json.dump(commands, f, indent=4)

COMMANDS = load_commands()

# ---------------------------
# VOSK SETUP
# ---------------------------

if not os.path.exists(MODEL_PATH):
    print("Model not found! Make sure path is correct.")
    sys.exit(1)

model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, 16000)
audio_queue = queue.Queue()

def audio_callback(indata, frames, time_, status):
    if status:
        print(status, file=sys.stderr)
    audio_queue.put(bytes(indata))

# ---------------------------
# KEY FUNCTIONS
# ---------------------------

def press_key(key):
    window_ids = subprocess.getoutput(f'xdotool search --name "{WINDOW_NAME_SUBSTRING}"').split()
    if not window_ids:
        log_message("Game window not found")
        return
    wid = window_ids[0]
    subprocess.run(['xdotool','windowactivate','--sync',wid])
    subprocess.run(['xdotool','windowraise',wid])
    subprocess.run(['xdotool','keydown',key])
    time.sleep(0.12)
    subprocess.run(['xdotool','keyup',key])

def hold_key(key):
    if holding_keys.get(key, False):
        return
    holding_keys[key] = True
    window_ids = subprocess.getoutput(f'xdotool search --name "{WINDOW_NAME_SUBSTRING}"').split()
    if not window_ids:
        log_message("Game window not found")
        return
    wid = window_ids[0]

    def _hold():
        subprocess.run(['xdotool','windowactivate','--sync',wid])
        subprocess.run(['xdotool','windowraise',wid])
        subprocess.run(['xdotool','keydown',key])
        while holding_keys.get(key, False):
            time.sleep(0.05)
        subprocess.run(['xdotool','keyup',key])

    threading.Thread(target=_hold, daemon=True).start()

def release_key(key):
    holding_keys[key] = False
    if key in active_commands:
        active_commands.remove(key)

# ---------------------------
# LOGGING
# ---------------------------

def log_message(msg):
    log_text.config(state="normal")
    log_text.insert(tk.END, msg + "\n")
    log_text.see(tk.END)
    log_text.config(state="disabled")

# ---------------------------
# VOICE LOOP
# ---------------------------

def voice_loop():
    global last_time, last_command, running, active_commands
    running = True
    with sd.RawInputStream(samplerate=16000, blocksize=512, dtype='int16', channels=1, callback=audio_callback):
        log_message("Listening...")
        while running:
            try:
                data = audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if recognizer.AcceptWaveform(data):
                text = json.loads(recognizer.Result()).get("text", "")
            else:
                text = json.loads(recognizer.PartialResult()).get("partial", "")

            current_time = time.time()

            # Handle commands
            for cmd, info in COMMANDS.items():
                key = info["key"]
                if cmd in text:
                    if info["hold"]:
                        if key not in active_commands:
                            log_message(f"Command recognized: {cmd}")
                            hold_key(key)
                            active_commands.add(key)
                    else:
                        if last_command.get(key,"") != cmd and (current_time - last_time > COOLDOWN):
                            log_message(f"Command recognized: {cmd}")
                            press_key(key)
                            last_time = current_time
                            last_command[key] = cmd

            # Stop command
            if "stop" in text:
                for key in list(active_commands):
                    release_key(key)
                log_message("Released all hold keys")

            # Reset last_command on silence
            if text.strip() == "":
                last_command = {}

# ---------------------------
# GUI FUNCTIONS
# ---------------------------

def start_listening():
    threading.Thread(target=voice_loop, daemon=True).start()

def stop_listening():
    global running
    running = False
    for key in list(active_commands):
        release_key(key)
    log_message("Stopped listening")

def refresh_command_list():
    for i in command_tree.get_children():
        command_tree.delete(i)
    for cmd, info in COMMANDS.items():
        hold_str = "Yes" if info["hold"] else "No"
        command_tree.insert("", "end", values=(cmd, info["key"], hold_str))

def add_command():
    cmd_word = simpledialog.askstring("Command Word", "Enter new command word:")
    if not cmd_word:
        return
    if cmd_word in COMMANDS:
        messagebox.showwarning("Exists", "This command already exists.")
        return
    key = simpledialog.askstring("Key", f"Enter key for '{cmd_word}':")
    if not key:
        return
    hold = messagebox.askyesno("Hold Key?", "Should this key be held until stopped?")
    COMMANDS[cmd_word] = {"key": key, "hold": hold}
    log_message(f"Added command '{cmd_word}' -> key '{key}' hold={hold}")
    refresh_command_list()
    save_commands(COMMANDS)

def edit_command_dialog():
    if not COMMANDS:
        messagebox.showinfo("No Commands", "No commands to edit.")
        return

    edit_win = tk.Toplevel(root)
    edit_win.title("Edit Command")

    tk.Label(edit_win, text="Select Command:").pack(pady=5)
    cmd_var = tk.StringVar()
    cmd_var.set(list(COMMANDS.keys())[0])
    cmd_dropdown = ttk.Combobox(edit_win, textvariable=cmd_var, values=list(COMMANDS.keys()), state="readonly")
    cmd_dropdown.pack(pady=5)

    tk.Label(edit_win, text="Key:").pack(pady=5)
    key_var = tk.StringVar()
    key_var.set(COMMANDS[cmd_var.get()]["key"])
    key_entry = tk.Entry(edit_win, textvariable=key_var)
    key_entry.pack(pady=5)

    hold_var = tk.BooleanVar()
    hold_var.set(COMMANDS[cmd_var.get()]["hold"])
    tk.Checkbutton(edit_win, text="Hold key until stop", variable=hold_var).pack(pady=5)

    def update_fields(event=None):
        sel = cmd_var.get()
        key_var.set(COMMANDS[sel]["key"])
        hold_var.set(COMMANDS[sel]["hold"])
    cmd_dropdown.bind("<<ComboboxSelected>>", update_fields)

    def save_changes():
        sel = cmd_var.get()
        COMMANDS[sel] = {"key": key_var.get(), "hold": hold_var.get()}
        log_message(f"Command '{sel}' updated to key '{key_var.get()}', hold={hold_var.get()}")
        refresh_command_list()
        save_commands(COMMANDS)
        edit_win.destroy()

    tk.Button(edit_win, text="Save", command=save_changes).pack(pady=5)

    def delete_command():
        sel = cmd_var.get()
        if messagebox.askyesno("Delete Command", f"Are you sure you want to delete '{sel}'?"):
            COMMANDS.pop(sel)
            log_message(f"Deleted command '{sel}'")
            refresh_command_list()
            save_commands(COMMANDS)
            edit_win.destroy()
    tk.Button(edit_win, text="Delete Command", command=delete_command).pack(pady=5)

def list_commands():
    if not COMMANDS:
        messagebox.showinfo("Commands", "No commands defined.")
        return
    msg = ""
    for cmd, info in COMMANDS.items():
        msg += f"{cmd} → key: {info['key']}, hold: {info['hold']}\n"
    messagebox.showinfo("Current Commands", msg)

def set_window_name():
    global WINDOW_NAME_SUBSTRING
    name = simpledialog.askstring("Window Name", "Enter The Name on The Top Bar of The Game:", initialvalue=WINDOW_NAME_SUBSTRING)
    if name:
        WINDOW_NAME_SUBSTRING = name
        log_message(f"Window name set to: {WINDOW_NAME_SUBSTRING}")

# ---------------------------
# GUI SETUP
# ---------------------------

root = tk.Tk()
root.title("VoiceR")
root.geometry("650x500")

frame_top = tk.Frame(root)
frame_top.pack(fill="x", padx=5, pady=5)

frame_bottom = tk.Frame(root)
frame_bottom.pack(fill="both", expand=True, padx=5, pady=5)

# Row 0: Start / Stop / Window
tk.Button(frame_top, text="Start Listening", command=start_listening).grid(row=0, column=0, padx=5, pady=5)
tk.Button(frame_top, text="Stop Listening", command=stop_listening).grid(row=0, column=1, padx=5, pady=5)
tk.Button(frame_top, text="Set Window Name", command=set_window_name).grid(row=0, column=2, padx=5, pady=5)

# Row 1: Add / Edit / List
tk.Button(frame_top, text="Add Command", command=add_command).grid(row=1, column=0, padx=5, pady=5)
tk.Button(frame_top, text="Edit Command", command=edit_command_dialog).grid(row=1, column=1, padx=5, pady=5)
tk.Button(frame_top, text="List Commands", command=list_commands).grid(row=1, column=2, padx=5, pady=5)

# Treeview in bottom frame
columns = ("Command", "Key", "Hold")
command_tree = ttk.Treeview(frame_bottom, columns=columns, show="headings", height=10)
for col in columns:
    command_tree.heading(col, text=col)
command_tree.pack(side="top", fill="both", expand=True, pady=5)
refresh_command_list()

# Log text in bottom frame
log_text = tk.Text(frame_bottom, height=10, state="disabled")
log_text.pack(side="bottom", fill="x", pady=5)

root.mainloop()
