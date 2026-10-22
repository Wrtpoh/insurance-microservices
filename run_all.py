"""Запуск всех сервисов и шлюза одной командой: python run_all.py (остановка — Ctrl+C)."""
import subprocess
import sys
import time

SERVICES = [
    ("client_service.main:create_app", 8001),
    ("product_service.main:create_app", 8002),
    ("policy_service.main:create_app", 8003),
    ("claim_service.main:create_app", 8004),
    ("gateway.main:create_app", 8000),
]


def main() -> None:
    processes = [subprocess.Popen([sys.executable, "-m", "uvicorn", target, "--factory",
                                   "--port", str(port), "--log-level", "warning"])
                 for target, port in SERVICES]
    print("Запущено: gateway http://127.0.0.1:8000 (документация каждого сервиса: /docs на портах 8001-8004)")
    try:
        while all(p.poll() is None for p in processes):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in processes:
            p.terminate()


if __name__ == "__main__":
    main()
