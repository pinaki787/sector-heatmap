#!/usr/bin/env python3
"""Idempotent local installation. Never starts or arms a trading runner."""
import argparse,os,platform,shutil,subprocess,sys,venv
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def run(args,**kwargs):
    subprocess.run([str(a) for a in args],check=True,cwd=kwargs.pop("cwd",ROOT),**kwargs)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-build',action='store_true',help='Use packaged prebuilt UI; requires client/dist/index.html')
    args=parser.parse_args()
    if platform.system() not in ('Darwin','Linux'):
        raise SystemExit('Renko requires POSIX file locks. Use macOS, Linux, or Windows through WSL2 Ubuntu.')
    if not (3,11)<=sys.version_info[:2]<=(3,12):
        raise SystemExit('Install Python 3.11 or 3.12 with venv, then run python3.11 setup.py. On Ubuntu: sudo apt install python3.11-venv; macOS: brew install python@3.11.')
    node=shutil.which('node');npx=shutil.which('npx')
    if not args.skip_build:
        if not node or not npx:raise SystemExit('Install Node.js 20.19+ (or 22.12+), including npm/npx, from nodejs.org, then rerun.')
        version=tuple(map(int,subprocess.check_output([node,'-p','process.versions.node'],text=True).strip().split('.')[:2]))
        if not ((version[0]==20 and version[1]>=19) or version>=(22,12)):raise SystemExit('Node.js 20.19+ or 22.12+ required.')
    elif not (ROOT/'client/dist/index.html').is_file():raise SystemExit('--skip-build requires the prebuilt UI included in the release tarball.')
    if not (ROOT/'.venv').exists():venv.EnvBuilder(with_pip=True).create(ROOT/'.venv')
    python=ROOT/'.venv/bin/python'
    run([python,'-m','pip','install','--disable-pip-version-check','-r','requirements.lock'])
    run([python,'-m','pip','check'])
    if not args.skip_build:
        build_env={**os.environ,'CI':'true','NPM_CONFIG_CACHE':str(ROOT/'.setup-cache/npm')}
        run([npx,'--yes','pnpm@10.17.1','install','--frozen-lockfile'],cwd=ROOT/'client',env=build_env)
        run([npx,'--yes','pnpm@10.17.1','run','build'],cwd=ROOT/'client',env=build_env)
    for target,example in [('.env','.env.example'),('.fyers.env','.fyers.env.example')]:
        file=ROOT/target
        if not file.exists():shutil.copyfile(ROOT/example,file);file.chmod(0o600)
    (ROOT/'.private').mkdir(mode=0o700,exist_ok=True)
    run([python,'-c','from sector_heatmap.web import run_server; from strategies.renko_supertrend.signals import settings; assert settings({})["rsi_slope_enabled"]'])
    print('Setup complete. No server or trading runner started.\nSet your broker credentials in .fyers.env, then authenticate with .venv/bin/python get_fyers_token.py.\nLaunch: .venv/bin/python heatmap_server.py\nOpen http://127.0.0.1:8080 . Live-order gates default OFF. See docs/installation.md.')

if __name__=='__main__':
    try:main()
    except subprocess.CalledProcessError as error:raise SystemExit(f'Setup failed (exit {error.returncode}); fix the reported prerequisite and rerun. Existing config is preserved.')
