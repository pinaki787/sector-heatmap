"""Presentable, immutable journal export; spreadsheet generation has no order route."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def export_xlsx(data, root):
    from sector_heatmap.portable_journal import export_journal
    return export_journal(data, kind="renko")
