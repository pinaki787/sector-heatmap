"""Cross-platform entrypoint for the local sector heat-map server."""
from sector_heatmap.web import run_server

if __name__ == "__main__":
    # Keep a private, on-demand thread dump available without privileged attach.
    import faulthandler
    import os
    from pathlib import Path
    import signal
    diagnostic_path = Path(__file__).resolve().parent / '.private' / 'backend-thread-stacks.txt'
    diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostic_fd = os.open(diagnostic_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    diagnostic_file = os.fdopen(diagnostic_fd, 'w')
    if hasattr(signal, 'SIGUSR2'):
        faulthandler.register(signal.SIGUSR2, file=diagnostic_file, all_threads=True)
    run_server()
