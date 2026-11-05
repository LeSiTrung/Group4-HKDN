"""Stage public LIC guide/policy attachments linked by validated library HTML snapshots."""
import argparse
import hashlib
import io
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.robotparser import RobotFileParser
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from collect_lic import BASE, HOST, digest, network, read_snapshot, write_json

MAX_BYTES = 16 * 1024 * 1024


def attachment_url(url):
    try:
        url = network._url(url, {HOST})
    except network.IntegrationError:
        return None
    parsed = urlsplit(url)
    path = unquote(parsed.path).lower()
    # Reject ambiguous paths before HTTP clients or servers normalize them.
    if '%' in path or '\\' in path or any(ord(c) < 32 or ord(c) == 127 for c in path) or any(part in ('.', '..') for part in path.split('/')):
        return None
    if parsed.query or not path.startswith('/wp-content/uploads/') or not path.endswith(('.pdf', '.docx')):
        return None
    return url


def inventory(pages):
    result = {}
    snapshots = sorted(Path(pages).glob('*.json'))
    if not snapshots:
        raise ValueError('missing_source_snapshots')
    for path in snapshots:
        try:
            row = json.loads(path.read_text(encoding='utf-8'))
            row = read_snapshot(path, row['source_url'])
            if row is None:
                raise ValueError
        except (ValueError, OSError, KeyError, TypeError):
            raise ValueError('invalid_source_snapshot: ' + path.name) from None
        if row['page']['status'] != 'accepted':
            continue
        for link in row['page']['links']:
            url = attachment_url(link)
            if url and row['source_url'] not in result.setdefault(url, []):
                result[url].append(row['source_url'])
    return result


def valid_file(raw, extension):
    if extension == '.pdf':
        return raw.startswith(b'%PDF-')
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            return {'[Content_Types].xml', 'word/document.xml'}.issubset(archive.namelist())
    except BadZipFile:
        return False


def collect(pages, directory):
    directory = Path(directory)
    files = directory / 'files'
    files.mkdir(parents=True, exist_ok=True)
    targets = inventory(pages)
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'source': BASE, 'complete': False,
              'scope': 'linked public institutional PDF/DOCX; staging only, no licensed book full text',
              'discovered': len(targets), 'reused': 0, 'blocked': None, 'urls': {}}
    try:
        prior = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))['urls']
    except (ValueError, OSError, KeyError, TypeError):
        prior = {}
    gap, next_request, robots = 1, 0.0, None

    def checkpoint():
        report['counts'] = dict(Counter(row['status'] for row in report['urls'].values()))
        report['pending'] = len(targets) - len(report['urls'])
        report['minimum_request_gap_seconds'] = gap
        write_json(directory / 'manifest.json', report)

    with network._client() as client:
        def pace(request):
            nonlocal next_request
            time.sleep(max(0, next_request - time.monotonic()))
            next_request = time.monotonic() + gap
        client.event_hooks['request'].append(pace)

        def request(url, attachment=False):
            def permitted(target):
                return (not attachment or attachment_url(target) is not None) and (robots is None or robots.can_fetch(network.USER_AGENT, target))
            # Standalone sequential tool only; keep the web app's 1 MiB bound unchanged.
            original_limit = network.MAX_BYTES
            try:
                if attachment:
                    network.MAX_BYTES = MAX_BYTES
                return network._fetch(client, url, {HOST}, permitted)
            finally:
                network.MAX_BYTES = original_limit

        try:
            _, status, raw, _ = request(BASE + '/robots.txt')
            robots = RobotFileParser()
            if status == 404:
                robots.parse(['User-agent: *', 'Disallow:'])
            elif status == 200:
                robots.parse(raw.decode('utf-8', errors='replace').splitlines())
            else:
                raise ValueError('robots_http_' + str(status))
            report['robots_sha256'] = hashlib.sha256(raw).hexdigest()
            rate = robots.request_rate(network.USER_AGENT) or robots.request_rate('*')
            if rate and rate.requests <= 0:
                raise ValueError('robots_or_attachment_scope_denied')
            gap = max(1, robots.crawl_delay(network.USER_AGENT) or robots.crawl_delay('*') or 0,
                      rate.seconds / rate.requests if rate else 0)
            if gap > 60:
                raise ValueError('robots_requires_later_resume')
            next_request = max(next_request, time.monotonic() + gap)
            for url, parents in targets.items():
                if not robots.can_fetch(network.USER_AGENT, url):
                    raise ValueError('robots_or_attachment_scope_denied')
                extension = Path(urlsplit(url).path).suffix.lower()
                name = 'files/' + hashlib.sha256(url.encode()).hexdigest() + extension
                path = directory / name
                cached = prior.get(url, {})
                try:
                    raw = path.read_bytes() if path.stat().st_size <= MAX_BYTES else b''
                    reusable = (cached.get('file') == name and cached.get('status') == 'downloaded'
                                and attachment_url(cached.get('final_url')) is not None
                                and robots.can_fetch(network.USER_AGENT, cached['final_url'])
                                and hashlib.sha256(raw).hexdigest() == cached.get('sha256') and valid_file(raw, extension))
                except (OSError, KeyError, TypeError):
                    reusable = False
                if reusable:
                    report['reused'] += 1
                    row = {**cached, 'parents': parents}
                else:
                    final, status, raw, kind = request(url, attachment=True)
                    if status in (401, 403, 429) or status >= 500:
                        raise ValueError('source_http_' + str(status))
                    row = {'status': 'missing_' + str(status), 'parents': parents, 'final_url': final,
                           'fetched_at': datetime.now(timezone.utc).isoformat(), 'content_type': kind}
                    if status == 200:
                        expected_type = 'application/pdf' if extension == '.pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                        if kind.split(';')[0].strip().lower() not in (expected_type, 'application/octet-stream') or not valid_file(raw, extension):
                            row['status'] = 'quarantine_invalid_file'
                        else:
                            temporary = path.with_suffix(extension + '.tmp')
                            temporary.write_bytes(raw)
                            temporary.replace(path)
                            row.update(status='downloaded', file=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                report['urls'][url] = row
                checkpoint()
            report['complete'] = True
        except network.IntegrationError as error:
            report['blocked'] = 'robots_or_attachment_scope_denied' if error.status_code in (400, 403) else 'network_or_size_limit'
        except ValueError as error:
            report['blocked'] = str(error)
        checkpoint()
    print(json.dumps({key: value for key, value in report.items() if key != 'urls'}), flush=True)
    return report


def extract(directory):
    """Offline PDF extraction; extracted text remains untrusted review material."""
    import pypdf
    directory = Path(directory)
    text_directory = directory / 'text'
    text_directory.mkdir(exist_ok=True)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    report = {'extracted_at': datetime.now(timezone.utc).isoformat(), 'extractor': 'pypdf ' + pypdf.__version__,
              'documents': 0, 'pages': 0, 'characters': 0, 'needs_ocr_pages': 0,
              'login_example_pages_withheld': 0, 'encrypted_documents': 0, 'unsupported_documents': 0,
              'scope': 'offline PDF text only; not OCR, reviewed facts, or proof of current policy'}
    for url, row in manifest['urls'].items():
        if row['status'] != 'downloaded':
            continue
        extension = Path(urlsplit(url).path).suffix.lower()
        if extension != '.pdf':
            report['unsupported_documents'] += 1
            continue
        expected = 'files/' + hashlib.sha256(url.encode()).hexdigest() + extension
        if row.get('file') != expected or attachment_url(url) is None:
            raise ValueError('invalid_attachment_identity')
        path = directory / expected
        if path.stat().st_size > MAX_BYTES or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('attachment_hash_mismatch')
        reader = pypdf.PdfReader(path)
        if reader.is_encrypted:
            report['encrypted_documents'] += 1
            continue
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ''
            normalized = ''.join(c for c in unicodedata.normalize('NFD', text) if not unicodedata.combining(c)).lower().replace('đ', 'd')
            status = 'text' if text.strip() else 'needs_ocr'
            if re.search(r'password|mat khau|username|user name|ten dang nhap|tai khoan dang nhap', normalized):
                status, text = 'withheld_login_example', ''
            text = re.sub(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', '[email omitted]', text)
            pages.append({'number': number, 'status': status, 'text': text})
            report['characters'] += len(text)
            report['needs_ocr_pages'] += status == 'needs_ocr'
            report['login_example_pages_withheld'] += status == 'withheld_login_example'
        document = {'source_url': url, 'source_sha256': row['sha256'], 'fetched_at': row['fetched_at'],
                    'parents': row['parents'], 'review_status': 'needs_review', 'pages': pages}
        document['sha256'] = digest(document)
        write_json(text_directory / (hashlib.sha256(url.encode()).hexdigest() + '.json'), document)
        report['documents'] += 1
        report['pages'] += len(pages)
    write_json(directory / 'extraction.json', report)
    print(json.dumps(report), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pages', type=Path, default=ROOT / 'backend/runtime/lic-public/pages')
    parser.add_argument('--output', type=Path, default=ROOT / 'backend/runtime/lic-attachments')
    parser.add_argument('--extract-only', action='store_true', help='Offline PDF extraction; requires pypdf in the tool environment')
    args = parser.parse_args()
    if args.extract_only:
        extract(args.output)
    else:
        raise SystemExit(0 if collect(args.pages, args.output)['complete'] else 1)
