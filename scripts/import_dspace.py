"""Stage public UTH DSpace metadata; write catalog rows only with --apply."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))

from app.config import Settings
from app.database.connection import Store
from app.services.dspace_catalog import import_books, stage_snapshots


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('records',type=Path)
    parser.add_argument('--apply',action='store_true',help='Import validated records; back up SQLite first.')
    parser.add_argument('--publish',action='store_true',help='Publish new validated metadata; existing rows are always preserved.')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if not args.records.is_dir():
        parser.error('Records directory does not exist.')
    target=args.report or args.records.parent/'dspace-import-report.json'
    if target.resolve().parent==args.records.resolve():
        parser.error('Report must be outside the raw records directory.')
    books,report=stage_snapshots(args.records,published=args.publish)
    report.update(applied=args.apply,publish_new=args.publish,imported=0,skipped_existing=0)
    if args.apply and books:
        store=Store(Settings.load().data_dir/'library.sqlite3')
        report.update(import_books(store.connect,books))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({**{key:value for key,value in report.items() if key!='rejected'},'rejected':len(report['rejected']),'report':str(target)},ensure_ascii=False))
    return 1 if report['rejected'] else 0


if __name__=='__main__':
    raise SystemExit(main())
