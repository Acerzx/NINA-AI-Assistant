"""
NINA AI Assistant Web - Main Entry Point (v10 FINAL)
"""
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from backend import app, manager, backend


def open_browser():
    """Открывает веб-интерфейс в браузере после небольшой задержки"""
    import time
    time.sleep(2.5)
    try:
        webbrowser.open(f"http://localhost:8000")
    except Exception:
        pass


def print_banner():
    print("=" * 70)
    print("  NINA AI Assistant Web - Полная версия (v10)")
    print("  + Prometheus Metrics + Session Metadata + Advanced Sequence Parser")
    print("=" * 70)
    print()
    print(f"  NINA API:         http://{backend.nina_host}:{backend.nina_port}/v2/api")
    print(f"  Ollama:           {backend.ollama_url}")
    print(f"  AI Модель:        {backend.model}")
    print(f"  Веб-интерфейс:    http://localhost:8000")
    print(f"  Prometheus:       http://localhost:8000/api/metrics")
    print(f"  Сеть:             http://<ваш-ip>:8000")
    print()
    print("  Модули:")
    for mod, enabled in backend.settings.get("modules", {}).items():
        if enabled:
            print(f"    ✓ {mod}")
    print()
    if backend.nina_profile.get("name"):
        print(f"  Профиль: {backend.nina_profile['name']}")
    if backend.nina_profile.get("observatory", {}).get("name"):
        print(f"  Обсерватория: {backend.nina_profile['observatory']['name']}")
    if backend.nina_profile.get("telescope", {}).get("name"):
        print(f"  Телескоп: {backend.nina_profile['telescope']['name']}")
    mount_name = backend.nina_profile.get("telescope", {}).get("mount_name")
    if mount_name:
        print(f"  Монтировка: {mount_name}")
    if backend.nina_profile.get("camera", {}).get("device_name"):
        print(f"  Камера: {backend.nina_profile['camera']['device_name']}")
    print()
    print("  Для остановки: Ctrl+C")
    print("=" * 70)
    print()


if __name__ == "__main__":
    print_banner()
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="warning",
        access_log=False,
        ws_ping_interval=30,
        ws_ping_timeout=30
    )