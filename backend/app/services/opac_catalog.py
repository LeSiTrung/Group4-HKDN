"""Validate consolidated public OPAC listings before any catalog write."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from .catalog import BookInput, save_book
from .knowledge import today

BASE = 'https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId='
CATEGORIES = {'1', '3', '9', '10', '23', '32', '36', '11-7'}


def normalize_listing(row, *, published=False):
    if not isinstance(row, dict):
        raise ValueError('invalid_listing')
    identifier = row.get('id')
    if not isinstance(identifier, str) or not re.fullmatch(r'[1-9][0-9]*', identifier) or row.get('source_url') != BASE + identifier:
        raise ValueError('source_identity')
    categories = row.get('categories')
    if not isinstance(categories, list) or not categories or any(not isinstance(value, str) or value not in CATEGORIES for value in categories):
        raise ValueError('invalid_categories')
    fields = row.get('fields')
    if not isinstance(fields, dict) or any(not isinstance(key, str) or not isinstance(values, list) or any(not isinstance(value, str) for value in values) for key, values in fields.items()):
        raise ValueError('invalid_fields')
    title = row.get('title')
    if not isinstance(title, str) or not title.strip():
        raise ValueError('missing_title')
    try:
        fetched = datetime.fromisoformat(row['fetched_at'])
        if fetched.tzinfo is None:
            raise ValueError
        checked_at = fetched.astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
        if checked_at > today():
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise ValueError('timestamp') from None
    def values(key):
        return '; '.join(dict.fromkeys(value.strip() for value in fields.get(key, []) if value.strip()))
    publication = values('Thông tin xuất bản')
    years = set(re.findall(r'\b\d{4}\b', publication))
    description = '\n'.join(key + ': ' + values(key) for key in
                            ('Thông tin xuất bản', 'Dạng tài liệu', 'Chỉ số Phân loại thập phân Dewey') if values(key))
    try:
        return BookInput(title=title, author=values('Tác giả'), year=next(iter(years)) if len(years) == 1 else '',
                         subjects=values('Từ khóa'), description=description,
                         kind='digital' if {'32', '11-7'}.intersection(categories) else 'books',
                         source_url=row['source_url'], checked_at=checked_at, published=published)
    except ValidationError as error:
        names = ','.join(sorted({str(item['loc'][0]) for item in error.errors()}))
        raise ValueError('field_limits:' + names) from None


def stage_pack(path, manifest_path, *, published=False):
    path, manifest_path = Path(path), Path(manifest_path)
    if path.stat().st_size > 64 * 1024 * 1024 or manifest_path.stat().st_size > 16384:
        raise ValueError('pack_size_limit')
    with manifest_path.open('rb') as source:
        manifest_raw = source.read(16385)
    with path.open('rb') as source:
        raw = source.read(64 * 1024 * 1024 + 1)
    if len(manifest_raw) > 16384 or len(raw) > 64 * 1024 * 1024:
        raise ValueError('pack_size_limit')
    manifest = json.loads(manifest_raw)
    if not isinstance(manifest, dict) or manifest.get('bytes') != len(raw) or manifest.get('sha256') != hashlib.sha256(raw).hexdigest():
        raise ValueError('pack_integrity')
    count = manifest.get('records')
    if type(count) is not int or not 1 <= count <= 100000:
        raise ValueError('pack_count')
    lines = raw.splitlines()
    if len(lines) != count:
        raise ValueError('pack_count')
    books, seen = [], set()
    report = {'discovered': count, 'accepted': 0, 'rejected': [], 'pack_sha256': manifest['sha256']}
    for line in lines:
        if len(line) > 65536:
            raise ValueError('listing_size_limit')
        row = json.loads(line)
        try:
            book = normalize_listing(row, published=published)
        except ValueError as error:
            if not str(error).startswith('field_limits:'):
                raise
            book = None
            report['rejected'].append({'id': row['id'], 'reason': str(error)})
        if row['id'] in seen:
            raise ValueError('duplicate_source_id')
        seen.add(row['id'])
        if book is not None:
            books.append(book)
    report['accepted'] = len(books)
    return books, report


def import_books(db_factory, books):
    imported = 0
    with db_factory() as db:
        db.execute('BEGIN IMMEDIATE')
        for book in books:
            if db.execute('SELECT 1 FROM books WHERE source_url=?', (book.source_url,)).fetchone():
                continue
            save_book(db, book)
            imported += 1
        db.execute("INSERT INTO audit(action,target) VALUES ('book.opac_import',?)", (str(imported),))
    return {'imported': imported, 'skipped_existing': len(books) - imported}
