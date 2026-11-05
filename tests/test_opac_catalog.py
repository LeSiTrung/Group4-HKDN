import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.database.connection import Store
from app.services.opac_catalog import import_books, normalize_listing, stage_pack


def listing(identifier='5712'):
    return {'id': identifier, 'title': 'Sách Python', 'fields': {'Tác giả': ['Nguyễn Văn A'],
            'Thông tin xuất bản': ['H.: Giáo dục, 2020'], 'Từ khóa': ['Tin học; Python'],
            'Dạng tài liệu': ['Sách truyền thống'], 'Ký hiệu': ['KS123']},
            'source_url': 'https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=' + identifier,
            'fetched_at': '2026-11-01T18:00:00+00:00', 'categories': ['1']}


def pack(tmp_path, rows):
    path = tmp_path / 'catalog-listings.jsonl'
    raw = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows).encode()
    path.write_bytes(raw)
    manifest = tmp_path / 'catalog-listings-manifest.json'
    manifest.write_text(json.dumps({'records': len(rows), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}))
    return path, manifest


def test_mapping_preserves_source_and_leaves_live_holdings_out():
    book = normalize_listing(listing(), published=True)
    assert book.author == 'Nguyễn Văn A' and book.year == '2020'
    assert str(book.checked_at) == '2026-11-02' and book.published
    assert book.subjects == 'Tin học; Python' and book.kind == 'books'
    assert 'KS123' not in book.description and '2020' in book.description
    row = listing(); row['categories'] = ['32']; row['fields']['Thông tin xuất bản'] = ['2020–2021']
    book = normalize_listing(row)
    assert book.kind == 'digital' and book.year == '' and not book.published
    row['categories'] = ['11-7']; row['fields']['Thông tin xuất bản'] = ['Paris, 1890']
    book = normalize_listing(row)
    assert book.kind == 'digital' and book.year == '1890'


@pytest.mark.parametrize('change', [
    {'source_url': 'https://evil.example/book'}, {'id': '../5712'}, {'id': '٠١'},
    {'fetched_at': '2026-11-01'}, {'fetched_at': '2099-01-01T00:00:00Z'},
    {'fields': {'Tác giả': 'wrong'}}, {'categories': ['unknown']}, {'title': ''}])
def test_untrusted_metadata_is_rejected(change):
    with pytest.raises(ValueError):
        normalize_listing({**listing(), **change})


def test_integrity_count_duplicates_and_field_quarantine(tmp_path):
    row = listing('2'); row['title'] = 'x' * 501
    path, manifest = pack(tmp_path, [listing(), row])
    books, report = stage_pack(path, manifest)
    assert len(books) == 1 and report['rejected'] == [{'id': '2', 'reason': 'field_limits:title'}]
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError, match='integrity'):
        stage_pack(path, manifest)
    path, manifest = pack(tmp_path, [listing(), listing()])
    with pytest.raises(ValueError, match='duplicate'):
        stage_pack(path, manifest)
    path, manifest = pack(tmp_path, [listing()])
    value = json.loads(manifest.read_text()); value['records'] = 2
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='count'):
        stage_pack(path, manifest)


def test_import_is_idempotent_preserves_operator_edits_and_rolls_back(tmp_path):
    store = Store(tmp_path / 'db.sqlite3')
    book = normalize_listing(listing(), published=True)
    assert import_books(store.connect, [book]) == {'imported': 1, 'skipped_existing': 0}
    with store.connect() as db:
        db.execute("UPDATE books SET title='Operator title', published=0")
    assert import_books(store.connect, [book]) == {'imported': 0, 'skipped_existing': 1}
    with store.connect() as db:
        assert dict(db.execute('SELECT title,published FROM books').fetchone()) == {'title': 'Operator title', 'published': 0}
        assert db.execute('SELECT action FROM audit LIMIT 1').fetchone()[0] == 'book.opac_import'
    with pytest.raises(AttributeError):
        import_books(store.connect, [normalize_listing(listing('2')), None])
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM books').fetchone()[0] == 1


def test_cli_dry_run_and_bad_pack_apply_never_create_database(tmp_path, monkeypatch, capsys):
    from runpy import run_path
    path, manifest = pack(tmp_path, [listing()])
    runtime = tmp_path / 'not-created'
    monkeypatch.setenv('DATA_DIR', str(runtime))
    monkeypatch.setattr(sys, 'argv', ['import_opac.py', str(path), '--publish'])
    main = run_path(str(Path(__file__).resolve().parents[1] / 'scripts/import_opac.py'))['main']
    assert main() == 0
    assert json.loads(capsys.readouterr().out)['applied'] is False
    assert not runtime.exists()
    path.write_text('tampered')
    monkeypatch.setattr(sys, 'argv', ['import_opac.py', str(path), '--apply'])
    with pytest.raises(SystemExit):
        main()
    assert not runtime.exists()


def test_pack_with_foreign_late_row_cannot_return_partial_import(tmp_path):
    row = listing('2'); row['source_url'] = 'https://evil.example/book'
    path, manifest = pack(tmp_path, [listing(), row])
    with pytest.raises(ValueError, match='source_identity'):
        stage_pack(path, manifest)


@pytest.mark.parametrize('suffix', ['', '-wal', '-shm', '-journal'])
def test_cli_report_cannot_overwrite_sqlite_or_companions(tmp_path, monkeypatch, suffix):
    from runpy import run_path
    path, _ = pack(tmp_path, [listing()])
    runtime = tmp_path / 'runtime'; runtime.mkdir()
    target = runtime / ('library.sqlite3' + suffix)
    target.write_bytes(b'preserved SQLite data')
    monkeypatch.setenv('DATA_DIR', str(runtime))
    monkeypatch.setattr(sys, 'argv', ['import_opac.py', str(path), '--report', str(target)])
    main = run_path(str(Path(__file__).resolve().parents[1] / 'scripts/import_opac.py'))['main']
    with pytest.raises(SystemExit):
        main()
    assert target.read_bytes() == b'preserved SQLite data'
