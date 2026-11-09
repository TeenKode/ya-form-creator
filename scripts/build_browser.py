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
    for name in ('manifest.json', 'service-worker.mjs', 'api.mjs', 'oauth.mjs', 'identity-reader.js', 'bridge.js',
                 'options.html', 'options.mjs', 'review.html', 'review.mjs', 'ui.css'):
        shutil.copy2(ROOT / 'extension' / name, EXTENSION / name)
    shutil.copytree(ROOT / 'extension' / 'icons', EXTENSION / 'icons')
    for output in (SITE, EXTENSION):
        shutil.copy2(ROOT / 'browser' / 'core.mjs', output / 'core.mjs')
    for name in ('editor-model.mjs', 'logic-analyzer.mjs'):
        shutil.copy2(ROOT / 'browser' / name, SITE / name)
    shutil.copy2(ROOT / 'assets' / 'app-icon.png', SITE / 'icon.png')
    header = (ROOT / 'docs' / 'AI_PROMPT_HEADER_RU.md').read_text(encoding='utf-8')
    rules = (ROOT / 'AI_JSON_RULES.md').read_text(encoding='utf-8')
    # The standalone handoff must not tell a tool-less chat to fetch more files.
    rules = '\n'.join(line for line in rules.splitlines() if not line.startswith('**Входная точка:**'))
    guide = (ROOT / 'docs' / 'FIELD_GUIDE_RU.md').read_text(encoding='utf-8')
    schema = (ROOT / 'schema' / 'form.schema.json').read_text(encoding='utf-8')
    pack = (header + '\n\n--- ПОЛНЫЕ ПРАВИЛА ФОРМАТА ---\n\n' + rules
            + '\n\n--- СПРАВОЧНИК ПОЛЕЙ ---\n\n' + guide
            + '\n\n--- JSON SCHEMA ---\n\n' + schema
            + '\n\n--- КОНЕЦ ПРАВИЛ ---\nОжидай описание анкеты от пользователя.\n')
    (SITE / 'ai-reference.txt').write_text(pack, encoding='utf-8', newline='\n')
    short = (ROOT / 'AI_SHORT_RU.md').read_text(encoding='utf-8')
    (SITE / 'ai-instructions.txt').write_text(short, encoding='utf-8', newline='\n')
    (SITE / '.nojekyll').touch()
    with zipfile.ZipFile(SITE / 'yaform-extension.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(EXTENSION.rglob('*')):
            if source.is_file():
                archive.write(source, source.relative_to(EXTENSION).as_posix())
    print('Built web-dist/ and browser-build/extension/ (no credentials or user files).')


if __name__ == '__main__':
    build()
