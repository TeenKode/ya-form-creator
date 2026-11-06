"""Fetch the pinned official Opera build for isolated Linux CI only."""
import hashlib
import os
from pathlib import Path
import subprocess
import urllib.request

if os.environ.get('GITHUB_ACTIONS') != 'true' or os.name == 'nt':
    raise SystemExit('This preparation runs only on a Linux GitHub Actions runner.')
version = '139.0.6053.38'
expected = '37e17fb2933557ec5c946066f64c70346241a94138e573c60f98be4f1f5f1e03'
url = f'https://deb.opera.com/opera-stable/pool/non-free/o/opera-stable/opera-stable_{version}_amd64.deb'
target = Path('browser-build/opera-ci').resolve()
target.mkdir(parents=True, exist_ok=True)
archive = target / 'opera.deb'
with urllib.request.urlopen(url, timeout=60) as response:
    data = response.read()
if hashlib.sha256(data).hexdigest() != expected:
    raise SystemExit('Opera package checksum mismatch')
archive.write_bytes(data)
subprocess.run(['dpkg-deb', '-x', str(archive), str(target / 'unpacked')], check=True)
binary = target / 'unpacked/usr/lib/x86_64-linux-gnu/opera-stable/opera'
with binary.open('rb') as handle:
    if handle.read(4) != b'\x7fELF':
        raise SystemExit('Opera binary is not ELF')
with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8') as env:
    env.write(f'YAFORM_OPERA_BINARY={binary}\n')
print(f'Prepared official Opera {version}; SHA-256 verified.')
