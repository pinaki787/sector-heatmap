"""Local XLSX export using the installed Codex spreadsheet runtime."""
import json, os, shutil, subprocess, tempfile
from pathlib import Path


def export_xlsx(data, root):
    from sector_heatmap.portable_journal import export_journal
    return export_journal(data, kind="delta")
