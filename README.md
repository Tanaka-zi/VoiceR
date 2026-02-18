# VoiceR
VoiceR is a Linux voice control app that lets you control games using speech commands.

## Setup (Fedora)

Install dependencies:

Install Python 3
```
sudo dnf install -y python3 python3-pip
```
Install Vosk Sounddevice
```
pip install vosk sounddevice
```

Install xdotool:

```
sudo dnf install xdotool
```

## Features
- Voice commands → keyboard input
- Hold / tap keys
- GUI command editor
- Offline speech recognition (Vosk)

## Requirements
- Python 3
- xdotool
- X11 session or wayland
- vosk sounddevice

## Usage

- run app
```
python3 VoiceR.py
```
- press "set window name"

- Type the Game's window name (make sure the game is running in window mode)

- press "Start listening" and boom you're golden
