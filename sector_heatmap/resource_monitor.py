"""Read-only Linux telemetry. No broker requests, credentials, or process arguments."""
import datetime as dt
import glob
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

_lock = threading.Lock()
_cache = {}
_history = None
_history_at = 0


def command(args):
    return subprocess.check_output(args, text=True, timeout=12, env={**os.environ, 'LC_ALL': 'C', 'TZ': 'UTC'})


def parse_sar(text, kind):
    """Use column names rather than assuming a sysstat version's column order."""
    columns = None
    rows = []
    date = None
    for line in text.splitlines():
        parts = line.split()
        if line.startswith('Linux'):
            for token in parts:
                try:
                    date = dt.datetime.strptime(token, '%m/%d/%y').date()
                except ValueError:
                    pass
        if not parts:
            continue
        if (kind == 'cpu' and '%idle' in parts) or (kind == 'memory' and '%memused' in parts):
            columns = parts[1:]
            continue
        if not columns or not date or len(parts) != len(columns) + 1:
            continue
        try:
            stamp = dt.datetime.combine(date, dt.time.fromisoformat(parts[0]), dt.timezone.utc).isoformat()
            values = dict(zip(columns, parts[1:]))
            if kind == 'cpu':
                if values.get('CPU') != 'all':
                    continue
                row = dict(time=stamp, cpu=round(sum(float(values.get(k, 0)) for k in ('%user','%nice','%system')), 2), non_idle=round(100-float(values['%idle']), 2), iowait=float(values['%iowait']), steal=float(values['%steal']))
            else:
                row = dict(time=stamp, memory=float(values['%memused']))
            rows.append(row)
        except (ValueError, KeyError):
            continue
    return rows


def history():
    global _history, _history_at
    if _history is not None and time.monotonic()-_history_at < 300:
        return _history
    points = {}
    errors = []
    files = sorted(glob.glob('/var/log/sysstat/sa[0-9][0-9]'), key=os.path.getmtime)[-31:]
    if not shutil.which('sar') or not files:
        errors.append('Historical sysstat records are unavailable on this host.')
    else:
        for file in files:
            for flag, kind in [('-u', 'cpu'), ('-r', 'memory')]:
                try:
                    for row in parse_sar(command(['sar', flag, '-f', file]), kind):
                        points.setdefault(row['time'], {}).update(row)
                except (OSError, subprocess.SubprocessError):
                    errors.append(f'{Path(file).name}: {kind} history unavailable')
    rows = [points[k] for k in sorted(points)]
    peaks = {}
    for key in ('cpu','non_idle','memory','iowait','steal'):
        candidates = [r for r in rows if key in r]
        if candidates:
            peak = max(candidates, key=lambda r:r[key])
            peaks[key] = dict(value=peak[key], time=peak['time'])
    _history = dict(rows=rows, peaks=peaks, errors=errors, source='sysstat', interval_note='CPU points average the recording interval (normally 10 minutes); memory points are snapshots. Brief spikes may be higher. Disk history is not recorded here.')
    _history_at = time.monotonic()
    return _history


def cpu_sample():
    return list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))


def cpu_delta(first, last):
    delta = [b-a for a,b in zip(first,last)]
    total = sum(delta)
    if total <= 0 or min(delta) < 0:
        raise ValueError('CPU counters could not be sampled')
    pct = lambda value:round(value/total*100,2)
    return dict(cpu=pct(sum(delta[:3])+sum(delta[5:7])), iowait=pct(delta[4]), steal=pct(delta[7]), idle=pct(delta[3]), non_idle=pct(total-delta[3]))


def snapshot():
    global _cache
    with _lock:
        if _cache and time.monotonic()-_cache['_at'] < 15:
            return {k:v for k,v in _cache.items() if k!='_at'}
        if not Path('/proc/meminfo').exists():
            raise RuntimeError('Resource monitoring requires the Linux server.')
        a = cpu_sample()
        time.sleep(.25)
        cpu = cpu_delta(a, cpu_sample())
        mem = {line.split(':')[0]: int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
        total, available = mem['MemTotal'], mem['MemAvailable']
        disk = shutil.disk_usage('/')
        try:
            # comm intentionally excludes command arguments and environment secrets.
            processes = []
            for line in command(['ps','-eo','comm=,rss=,pcpu=','--sort=-rss']).splitlines()[:8]:
                name, rss, pcpu = line.rsplit(None,2)
                processes.append(dict(name=name, rss_bytes=int(rss)*1024, cpu_lifetime_pct=float(pcpu)))
        except (OSError, subprocess.SubprocessError, ValueError):
            processes = []
        warnings = []
        if cpu['cpu'] >= 80: warnings.append('CPU work is above 80% in this short sample. Check the trend for sustained pressure.')
        if cpu['steal'] >= 5: warnings.append('Hypervisor steal is above 5%: the virtual machine is waiting for CPU time from the host.')
        if cpu['iowait'] >= 5: warnings.append('I/O wait is above 5%: investigate storage latency alongside workload activity.')
        if available/total < .15: warnings.append('Less than 15% of memory is available. Check growing processes and memory pressure.')
        if disk.used/disk.total > .85: warnings.append('Root disk is over 85% full. Review storage growth.')
        result = dict(as_of=dt.datetime.now(dt.timezone.utc).isoformat(), hostname=os.uname().nodename, cores=os.cpu_count(), cpu=cpu,
          memory=dict(total=total, available=available, used=total-available, used_pct=round((total-available)/total*100,2), cache=mem.get('Cached',0), swap_total=mem.get('SwapTotal',0), swap_used=mem.get('SwapTotal',0)-mem.get('SwapFree',0)),
          disk=dict(total=disk.total, used=disk.used, free=disk.free, used_pct=round(disk.used/disk.total*100,2)),
          load=list(os.getloadavg()), uptime_seconds=float(Path('/proc/uptime').read_text().split()[0]), processes=processes, warnings=warnings, history=history())
        _cache = dict(result, _at=time.monotonic())
        return result

if __name__ == '__main__':
    print(json.dumps(snapshot()))
