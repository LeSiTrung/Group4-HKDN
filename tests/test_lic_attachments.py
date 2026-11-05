import hashlib
import json
import sys
from types import SimpleNamespace
from pathlib import Path
from runpy import run_path

import httpx
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/collect_lic_attachments.py'
BASE = 'https://lic.ut.edu.vn'
PDF = BASE + '/wp-content/uploads/2024/guide.pdf'


def source(directory, links):
    module = run_path(str(SCRIPT))
    page = {'status': 'accepted', 'title': 'Thư viện', 'text': 'Hướng dẫn thư viện.', 'links': links}
    url = BASE + '/library/'
    row = {'source_url': url, 'final_url': url, 'fetched_at': '2026-11-01T00:00:00+00:00',
           'page': page, 'sha256': module['digest'](page)}
    directory.mkdir()
    (directory / 'one.json').write_text(json.dumps(row), encoding='utf-8')
    return module


def client(module, monkeypatch, handler):
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(module['time'], 'sleep', lambda seconds: None)


def test_inventory_requires_valid_library_source_and_safe_attachment(tmp_path):
    module = source(tmp_path / 'pages', [PDF, PDF, BASE + '/wp-content/uploads/2024/picture.png',
                    'https://evil.example/file.pdf', PDF + '?token=secret', BASE + '/login/file.pdf'])
    result = module['inventory'](tmp_path / 'pages')
    assert result == {PDF: [BASE + '/library/']}
    path = tmp_path / 'pages/one.json'
    row = json.loads(path.read_text())
    row['page']['links'].append(BASE + '/wp-content/uploads/evil.pdf')
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match='invalid_source_snapshot'):
        module['inventory'](tmp_path / 'pages')


def test_download_resume_and_corruption_repair(tmp_path, monkeypatch):
    module = source(tmp_path / 'pages', [PDF])
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        return httpx.Response(200, content=b'%PDF-1.7\nexample', headers={'content-type': 'application/pdf'})
    client(module, monkeypatch, handler)
    limit = module['network'].MAX_BYTES
    result = module['collect'](tmp_path / 'pages', tmp_path / 'output')
    assert result['complete'] and result['counts'] == {'downloaded': 1}
    assert module['network'].MAX_BYTES == limit
    row = result['urls'][PDF]
    binary = tmp_path / 'output' / row['file']
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == row['sha256']
    result = module['collect'](tmp_path / 'pages', tmp_path / 'output')
    assert result['reused'] == 1 and calls.count('/wp-content/uploads/2024/guide.pdf') == 1
    binary.write_bytes(b'corrupt')
    result = module['collect'](tmp_path / 'pages', tmp_path / 'output')
    assert result['reused'] == 0 and calls.count('/wp-content/uploads/2024/guide.pdf') == 2


@pytest.mark.parametrize('status', [401, 403, 429, 500, 503])
def test_denied_or_busy_source_stops_without_followup(tmp_path, monkeypatch, status):
    module = source(tmp_path / 'pages', [PDF, PDF.replace('guide', 'second')])
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        return httpx.Response(status)
    client(module, monkeypatch, handler)
    result = module['collect'](tmp_path / 'pages', tmp_path / 'output')
    assert not result['complete'] and result['blocked'] == 'source_http_' + str(status)
    assert len(calls) == 2 and result['pending'] == 2


def test_robots_and_redirect_scope_are_enforced(tmp_path, monkeypatch):
    module = source(tmp_path / 'pages', [PDF])
    calls = []
    deny = [False]
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow: /' if deny[0] else 'User-agent: *\nDisallow:')
        return httpx.Response(302, headers={'location': BASE + '/login/'})
    client(module, monkeypatch, handler)
    result = module['collect'](tmp_path / 'pages', tmp_path / 'output')
    assert not result['complete'] and result['blocked'] == 'robots_or_attachment_scope_denied'
    assert '/login/' not in calls
    deny[0] = True
    calls.clear()
    result = module['collect'](tmp_path / 'pages', tmp_path / 'output')
    assert result['blocked'] == 'robots_or_attachment_scope_denied' and calls == ['/robots.txt']


def test_html_mislabeled_as_pdf_is_not_saved(tmp_path, monkeypatch):
    module = source(tmp_path / 'pages', [PDF])
    def handler(request):
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        return httpx.Response(200, text='<html>Login</html>', headers={'content-type': 'application/pdf'})
    client(module, monkeypatch, handler)
    result = module['collect'](tmp_path / 'pages', tmp_path / 'output')
    assert result['complete'] and result['counts'] == {'quarantine_invalid_file': 1}
    assert not list((tmp_path / 'output/files').glob('*'))


def test_extract_checks_hash_and_withholds_login_examples(tmp_path, monkeypatch):
    module = source(tmp_path / 'pages', [PDF])
    directory = tmp_path / 'output'
    (directory / 'files').mkdir(parents=True)
    raw = b'%PDF-1.7\nexample'
    name = 'files/' + hashlib.sha256(PDF.encode()).hexdigest() + '.pdf'
    (directory / name).write_bytes(raw)
    row = {'status': 'downloaded', 'file': name, 'sha256': hashlib.sha256(raw).hexdigest(),
           'parents': [BASE + '/library/'], 'fetched_at': '2026-11-01T00:00:00+00:00'}
    (directory / 'manifest.json').write_text(json.dumps({'urls': {PDF: row}}))
    fake = SimpleNamespace(is_encrypted=False, pages=[
        SimpleNamespace(extract_text=lambda: 'Hướng dẫn tra cứu tài liệu. Contact someone@example.com'),
        SimpleNamespace(extract_text=lambda: 'Mật khẩu\nexample secret'),
        SimpleNamespace(extract_text=lambda: '')])
    monkeypatch.setitem(sys.modules, 'pypdf', SimpleNamespace(PdfReader=lambda path: fake, __version__='test'))
    result = module['extract'](directory)
    assert result['documents'] == 1 and result['pages'] == 3 and result['login_example_pages_withheld'] == 1
    text = json.loads(next((directory / 'text').glob('*.json')).read_text(encoding='utf-8'))
    assert text['pages'][0]['text'].endswith('[email omitted]')
    assert text['pages'][1]['text'] == '' and text['pages'][2]['status'] == 'needs_ocr'
    (directory / name).write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='attachment_hash_mismatch'):
        module['extract'](directory)


def test_missing_html_input_is_not_a_complete_empty_harvest(tmp_path):
    module = run_path(str(SCRIPT))
    with pytest.raises(ValueError, match='missing_source_snapshots'):
        module['inventory'](tmp_path / 'missing')


def test_redirect_requests_are_paced_and_large_download_bound_is_scoped(tmp_path, monkeypatch):
    module = source(tmp_path / 'pages', [PDF])
    clock, starts = [0.0], []
    original = module['network'].MAX_BYTES
    def handler(request):
        starts.append(clock[0])
        if request.url.path == '/robots.txt':
            assert module['network'].MAX_BYTES == original
            return httpx.Response(200, text='User-agent: *\nDisallow:\nCrawl-delay: 2')
        assert module['network'].MAX_BYTES == 16 * 1024 * 1024
        if request.url.path.endswith('/guide.pdf'):
            return httpx.Response(302, headers={'location': PDF.replace('guide', 'final')})
        return httpx.Response(200, content=b'%PDF-1.7\nexample', headers={'content-type': 'application/pdf'})
    client(module, monkeypatch, handler)
    monkeypatch.setattr(module['time'], 'monotonic', lambda: clock[0])
    monkeypatch.setattr(module['time'], 'sleep', lambda delay: clock.__setitem__(0, clock[0] + delay))
    result = module['collect'](tmp_path / 'pages', tmp_path / 'output')
    assert result['complete'] and len(starts) == 3
    assert all(b - a >= 2 for a, b in zip(starts, starts[1:]))
    assert module['network'].MAX_BYTES == original


@pytest.mark.parametrize('path', [
    '/wp-content/uploads/../../private.pdf',
    '/wp-content/uploads/%2e%2e/%2e%2e/private.pdf',
    '/wp-content/uploads/%2E%2E%2F%2E%2E%2Fprivate.pdf',
    '/wp-content/uploads/%252e%252e/private.pdf',
    '/wp-content/uploads/%25252e%25252e/private.pdf',
    '/wp-content/uploads/folder%5c..%5cprivate.pdf',
    '/wp-content/uploads/folder%255c..%255cprivate.pdf',
    '/wp-content/uploads/file%00.pdf',
    '/wp-content/uploads/file%0a.pdf',
])
def test_attachment_path_cannot_escape_uploads_even_after_redirect(tmp_path, monkeypatch, path):
    module = source(tmp_path / 'pages', [PDF])
    target = BASE + path
    assert module['attachment_url'](target) is None
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        return httpx.Response(302, headers={'location': target})
    client(module, monkeypatch, handler)
    result = module['collect'](tmp_path / 'pages', tmp_path / 'output')
    assert result['blocked'] == 'robots_or_attachment_scope_denied'
    assert calls == ['/robots.txt', '/wp-content/uploads/2024/guide.pdf']


def test_attachment_path_rejects_single_dot_segment():
    module = run_path(str(SCRIPT))
    assert module['attachment_url'](BASE + '/wp-content/uploads/./guide.pdf') is None
