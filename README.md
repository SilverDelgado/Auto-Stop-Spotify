# AutoStop for Spotify

**AutoStop** is a Python script for **Windows** that automatically pauses Spotify whenever it detects audio from other applications like youtube and resumes playback once that audio stops.  
Background processes like **Discord** or **NVIDIA Container** are ignored so they don’t accidentally pause Spotify.

---

## Features

- Detects external audio using **PyCAW** (per-process audio peaks).
- Controls Spotify via Windows **SMTC API** (no OAuth keys needed).
- Debounce logic: avoids triggering on short clicks or system sounds.
- Robust: runs a **supervisor process** that restarts the worker if it crashes.
- Supports excluding specific processes (e.g., `discord.exe`, `nvidiacontainer.exe`).

---

## Requirements

- Windows 10/11 with the **Spotify app** (not the web player).
- Python 3.9+.
- Dependencies:
  ```powershell
  pip install pycaw comtypes winsdk
  ```

---

## Usage

1. Clone/download this repository and locate `auto_spotify_stop.py`.
2. Open a terminal (PowerShell or VS Code) in that folder.
3. Run:
   ```powershell
   python -u auto_spotify_stop.py
   ```
   - Run `--noconsole`  so u only see activity in the log file.
4. Keep it running in the background:
   - When external audio is detected (e.g., YouTube in Brave/Chrome), Spotify is paused.
   - When external audio stops, Spotify resumes after a short delay.

---

## Configuration

Inside the script, you can tune the following:

- **Sensitivity**:
  ```python
  PEAK_THRESHOLD = 0.01
  ```
  Increase to `0.02–0.05` if Spotify pauses too easily. Decrease if external audio isn’t detected.

- **Debounce timing**:
  ```python
  ACTIVE_DEBOUNCE_SEC = 0.4     # external audio must last this long to trigger pause
  INACTIVE_DEBOUNCE_SEC = 1.5   # silence duration before Spotify resumes
  ```

- **Ignored processes**:  
  Add process names (`.exe`) that should *not* trigger Spotify pause:
  ```python
  EXCLUDE_PROCS = {"nvidiacontainer.exe", "discord.exe"}
  ```
  You can extend this list with any other executables you want to ignore (e.g., `teams.exe`, `zoom.exe`).

---

## Limitations

- Works only with the **Spotify desktop app** (not the web player).
- If different apps output to **different audio devices**, PyCAW may not detect them as “external”.

---
