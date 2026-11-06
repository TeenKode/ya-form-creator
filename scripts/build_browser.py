"""Build static Pages site and a self-contained unpacked MV3 extension, offline."""
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'web-dist'
EXTENSION = ROOT / 'browser-build' / 'extension'


def build():
    for output in (SITE, EXTENSION):
        # Only generated directories inside this checkout can be cleared.
        resolved = output.resolve()
        if not resolved.is_relative_to(ROOT) or resolved == ROOT:
            raise RuntimeError('Unsafe build directory')
        if resolved.exists():
            shutil.rmtree(resolved)
        resolved.mkdir(parents=True)
    for source in (ROOT / 'web').iterdir():
        if source.is_file():
            shutil.copy2(source, SITE / source.name)
    for name in ('manifest.json', 'service-worker.mjs', 'api.mjs', 'bridge.js',
                 'options.html', 'options.mjs', 'review.html', 'review.mjs', 'ui.css'):
        shutil.copy2(ROOT / 'extension' / name, EXTENSION / name)
    shutil.copytree(ROOT / 'extension' / 'icons', EXTENSION / 'icons')
    for output in (SITE, EXTENSION):
        shutil.copy2(ROOT / 'browser' / 'core.mjs', output / 'core.mjs')
    shutil.copy2(ROOT / 'assets' / 'app-icon.png', SITE / 'icon.png')
    (SITE / '.nojekyll').touch()
    with zipfile.ZipFile(SITE / 'yaform-extension.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(EXTENSION.rglob('*')):
            if source.is_file():
                archive.write(source, source.relative_to(EXTENSION).as_posix())
    print('Built web-dist/ and browser-build/extension/ (no credentials or user files).')


if __name__ == '__main__':
    build()
