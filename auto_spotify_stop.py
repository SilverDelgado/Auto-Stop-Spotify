import asyncio
import time
import logging
import os
from typing import Optional, Tuple, List
from multiprocessing import Process

SPOTIFY_PROC = "spotify.exe"
PEAK_THRESHOLD = 0.01
ACTIVE_DEBOUNCE_SEC = 0.2
INACTIVE_DEBOUNCE_SEC = 1.0
POLL_SEC = 0.25
HEARTBEAT_SEC = 5.0
RESTART_DELAY_SEC = 0.1

# 🚀 Lista de procesos que NO deben pausar Spotify
IGNORE_PROCS = {"nvcontainer.exe", "discord.exe"}

def setup_logging(to_console: bool = True):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    if to_console:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger().addHandler(console)

def worker_main():
    setup_logging(to_console=False)
    logging.info("[Worker] start")

    try:
        from comtypes import CoInitialize, CoUninitialize
        from ctypes import POINTER, cast
        from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as SMTCManager,
        )
    except Exception as e:
        logging.error(f"[Worker] Import error: {repr(e)}")
        return 2

    com_initialized = False
    try:
        CoInitialize()
        com_initialized = True
    except Exception as e:
        logging.error(f"[Worker] CoInitialize error: {repr(e)}")

    def get_endpoint_peak() -> float:
        try:
            speakers = AudioUtilities.GetSpeakers()
            iface = speakers.Activate(IAudioMeterInformation._iid_, 23, None)
            meter = cast(iface, POINTER(IAudioMeterInformation))
            return float(meter.GetPeakValue())
        except Exception:
            return 0.0

    def list_session_peaks() -> Tuple[float, List[Tuple[str, float]], float]:
        spotify_peak = 0.0
        externals: List[Tuple[str, float]] = []
        try:
            sessions = AudioUtilities.GetAllSessions()
            for ses in sessions:
                proc_name = "unknown"
                try:
                    p = ses.Process
                    if p:
                        proc_name = p.name()
                except Exception:
                    pass
                try:
                    meter = ses._ctl.QueryInterface(IAudioMeterInformation)
                    peak = float(meter.GetPeakValue())
                except Exception:
                    peak = 0.0

                if proc_name.lower() == SPOTIFY_PROC:
                    spotify_peak = max(spotify_peak, peak)
                else:
                    # ⚡️ ignoramos procesos específicos
                    if proc_name.lower() in IGNORE_PROCS:
                        continue
                    if peak > 0.0:
                        externals.append((proc_name, peak))
        except Exception as e:
            logging.error(f"[Diag] list_session_peaks error: {repr(e)}")
        externals_sorted = sorted(externals, key=lambda x: x[1], reverse=True)[:5]
        if externals_sorted:
            logging.info("[Diag] top externos: " + ", ".join(f"{n}:{p:.3f}" for n,p in externals_sorted))
        endpoint_peak = get_endpoint_peak()
        logging.info(f"[Diag] peaks → endpoint:{endpoint_peak:.3f} spotify:{spotify_peak:.3f}")
        return spotify_peak, externals_sorted, endpoint_peak

    async def get_spotify_session():
        try:
            mgr = await SMTCManager.request_async()
            sessions = mgr.get_sessions()
            logging.info(f"[Diag] SMTC sesiones: {len(sessions)}")
            chosen = None
            for s in sessions:
                try:
                    appid = s.source_app_user_model_id
                except Exception:
                    appid = None
                if appid:
                    logging.info(f"[Diag] SMTC sesión: {appid}")
                    if "spotify" in appid.lower():
                        chosen = s
            return chosen
        except Exception as e:
            logging.error(f"[Diag] SMTC request_async() falló: {repr(e)}")
            return None

    async def spotify_pause(session):
        try:
            await session.try_pause_async()
            logging.info("[AutoDuck] → try_pause_async() enviado")
        except Exception as e:
            logging.error(f"[Diag] try_pause_async() error: {repr(e)}")

    async def spotify_play(session):
        try:
            await session.try_play_async()
            logging.info("[AutoDuck] → try_play_async() enviado")
        except Exception as e:
            logging.error(f"[Diag] try_play_async() error: {repr(e)}")

    def external_audio_active() -> bool:
        spotify_peak, externals, endpoint_peak = list_session_peaks()
        any_ext = any(p >= PEAK_THRESHOLD for _, p in externals)
        if any_ext:
            return True
        extra = max(0.0, endpoint_peak - spotify_peak)
        if extra >= PEAK_THRESHOLD * 0.8:
            logging.info(f"[Diag] fallback endpoint extra:{extra:.3f} ≥ umbral:{PEAK_THRESHOLD*0.8:.3f}")
            return True
        return False

    async def main_loop():
        logging.info("[AutoDuck] Iniciando vigilancia. Ctrl+C para salir.")
        active_since = None
        inactive_since = time.time()
        paused_by_us = False
        last_heartbeat = 0.0
        while True:
            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_SEC:
                logging.info("[HB] vivo")
                last_heartbeat = now
            session = await get_spotify_session()
            if session is None:
                logging.info("[Diag] Spotify SMTC no encontrado")
            ext_active = external_audio_active()
            logging.info(f"[Diag] audio_externo={'SÍ' if ext_active else 'no'}")
            if ext_active:
                inactive_since = None
                if active_since is None:
                    active_since = now
                if (now - active_since) >= ACTIVE_DEBOUNCE_SEC and session is not None and not paused_by_us:
                    logging.info("[AutoDuck] Audio externo → Pausando Spotify")
                    await spotify_pause(session)
                    paused_by_us = True
            else:
                active_since = None
                if inactive_since is None:
                    inactive_since = now
                if (now - inactive_since) >= INACTIVE_DEBOUNCE_SEC and session is not None and paused_by_us:
                    logging.info("[AutoDuck] Silencio externo → Reanudando Spotify")
                    await spotify_play(session)
                    paused_by_us = False
            await asyncio.sleep(POLL_SEC)

    exit_code = 0
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logging.info("[Worker] Ctrl+C recibido; saliendo limpio.")
        exit_code = 0
    except Exception as e:
        logging.error(f"[Worker] Excepción no controlada en worker: {repr(e)}")
        exit_code = 1
    finally:
        if com_initialized:
            try:
                CoUninitialize()
            except Exception:
                pass
    return exit_code

def worker_entry():
    code = worker_main()
    os._exit(code)

def supervise():
    setup_logging(to_console=True)
    logging.info("[Supervisor] Lanzando worker con autorestart")
    while True:
        p = Process(target=worker_entry)
        p.start()
        p.join()
        code = p.exitcode
        if code == 0:
            logging.info("[Supervisor] Worker terminó limpio. Saliendo.")
            break
        logging.warning(f"[Supervisor] Worker cayó (code={code}). Reiniciando en {RESTART_DELAY_SEC}s...")
        time.sleep(RESTART_DELAY_SEC)

# if __name__ == "__main__":
#     supervise()

if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support()                
    supervise()
