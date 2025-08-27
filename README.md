# AutoStop for Spotify

**AutoStop** is a Python script for **Windows** that automatically pauses Spotify whenever it detects audio from other applications (e.g., YouTube, games) and resumes playback once that audio stops.  
Background processes like **Discord** or **NVIDIA Container** are ignored so they don’t accidentally pause Spotify.

---

## Features

- Detects external audio using **PyCAW** (per-process audio peaks).
- Controls Spotify via Windows **SMTC API** (no OAuth keys needed).
- Debounce logic: avoids triggering on short clicks or system sounds.
- Robust: runs a **supervisor process** that restarts the worker if it crashes.
- Logs activity to a file (`autoduck.log`) for debugging.
- Supports excluding specific processes (e.g., `discord.exe`, `nvidiacontainer.exe`).

---
