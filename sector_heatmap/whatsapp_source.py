"""Local native adapter; invoked only by explicit Start, never at startup."""
import os
import json
import subprocess
from pathlib import Path


class NativeWhatsAppSource:
    def __init__(self, executable):
        self.executable = Path(executable)

    def readiness(self):
        ready = self.executable.is_file() and os.access(self.executable, os.X_OK)
        return {"ready": ready, "blocker": None if ready else "Build the native WhatsApp reader using scripts/whatsapp/build.sh, then retry Start."}

    def read_latest(self, group):
        if not self.readiness()["ready"]:
            raise RuntimeError('Build the native WhatsApp reader using scripts/whatsapp/build.sh, then retry Start.')
        try:
            result = subprocess.run([str(self.executable), group], capture_output=True, text=True, timeout=20, check=True)
            payload = json.loads(result.stdout)
        except (subprocess.SubprocessError, ValueError):
            raise RuntimeError('Native WhatsApp reader failed or timed out. Check Accessibility/Screen Recording permissions.') from None
        if payload.get('error'):
            raise RuntimeError(str(payload['error'])[:600])
        if not isinstance(payload.get('messages'), list):
            raise RuntimeError('Native WhatsApp reader returned unverified data.')
        return payload['messages']
