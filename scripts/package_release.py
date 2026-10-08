"""Build and validate a source-only deployable from an exact Git commit."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(rb'(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)')


def build(ref='HEAD', output=None):
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', ref+'^{commit}'], cwd=ROOT, text=True).strip()
    date = datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y-%m-%d')
    name = 'sector-pulse-'+date+'-'+commit[:12]
    folder = Path(output) if output else ROOT/'output/releases'
    folder.mkdir(parents=True, exist_ok=True)
    data = subprocess.check_output(['git', 'archive', '--format=tar', '--prefix='+name+'/', commit], cwd=ROOT)
    members = []
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            parts = PurePosixPath(member.name).parts[1:]
            if any(p in ('.private', '.git', '.venv', 'node_modules', 'output', 'outputs', 'tmp', 'release-private', '__pycache__', 'cache') for p in parts):
                raise ValueError('Private/generated archive path: '+member.name)
            if member.issym() or member.islnk():
                raise ValueError('Archive links require review: '+member.name)
            if member.isfile():
                path = PurePosixPath(*parts)
                if path.name in ('.env', '.env.local', '.fyers.env', 'token.json') or path.suffix in ('.log', '.db', '.sqlite', '.sqlite3'):
                    raise ValueError('Private file: '+str(path))
                payload = archive.extractfile(member).read()
                if SECRET.search(payload):
                    raise ValueError('Credential pattern in '+str(path))
                members.append(dict(path=str(path), size=len(payload), sha256=hashlib.sha256(payload).hexdigest()))
    target = folder/(name+'.tar.gz')
    # Compress the validated git archive; no working-tree or private overlay files.
    import gzip
    target.write_bytes(gzip.compress(data, mtime=0))
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(target.suffix+'.sha256').write_text(digest+'  '+target.name+'\n')
    target.with_suffix(target.suffix+'.manifest.json').write_text(json.dumps(dict(commit=commit, archive=target.name, sha256=digest, files=members), indent=2)+'\n')
    print(json.dumps(dict(archive=str(target.resolve()), commit=commit, sha256=digest, files=len(members)), indent=2))
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='HEAD')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    build(args.ref, args.output)
