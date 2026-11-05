"""Stage verified OPAC listing metadata; writes only with --apply."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.config import Settings
from app.database.connection import Store
from app.services.opac_catalog import import_books, stage_pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--apply', action='store_true', help='Import accepted metadata; back up SQLite first.')
    parser.add_argument('--publish', action='store_true', help='Publish newly inserted rows; existing rows remain unchanged.')
    args = parser.parse_args()
    manifest = args.manifest or args.pack.with_name('catalog-listings-manifest.json')
    target = args.report or args.pack.with_name('opac-import-report.json')
    database = Settings.load().data_dir / 'library.sqlite3'
    protected = {args.pack.resolve(), manifest.resolve(), *(Path(str(database) + suffix).resolve() for suffix in ('', '-wal', '-shm', '-journal'))}
    if target.resolve() in protected:
        parser.error('Report must not overwrite the pack, manifest, or SQLite database/companion files.')
    try:
        books, report = stage_pack(args.pack, manifest, published=args.publish)
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(1, 'Pack rejected before database writes: ' + str(error) + '\n')
    report.update(applied=args.apply, publish_new=args.publish, imported=0, skipped_existing=0)
    if args.apply and books:
        report.update(import_books(Store(database).connect, books))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({**{k: v for k, v in report.items() if k != 'rejected'}, 'rejected': len(report['rejected']), 'report': str(target)}))
    return 1 if report['rejected'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
