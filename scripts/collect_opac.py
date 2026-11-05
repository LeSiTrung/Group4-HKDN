"""Checkpoint public OPAC bibliographic metadata, without login or document downloads."""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from contextlib import ExitStack,contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.services import integrations as network
from app.services.opac_catalog import stage_pack

BASE = network.OPAC
HOST = 'opacthuvien.ut.edu.vn'
CATEGORIES = {'10': 'Video', '36': 'Khóa luận', '11-7': 'Báo / Tạp chí điện tử', '23': 'CD-ROM', '9': 'Báo / Tạp chí', '3': 'Luận văn', '32': 'Tài liệu số', '1': 'Sách truyền thống'}


@contextmanager
def collection_lock(directory):
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'collector.lock').open('a+b') as handle:
        if not handle.tell():
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('OPAC collector already running for this output directory') from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name=='nt':
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def category_url(category):
    dictionary, browse = category.split('-', 1) if '-' in category else ('10', category)
    return BASE + 'OShow.aspx?DicID=' + dictionary + '&BrowseId=' + browse


def write_json(path, value):
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for attempt in range(8):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            # Windows readers can briefly deny an otherwise atomic replacement.
            time.sleep(0.05 * 2 ** attempt)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def validate_listing(value, page):
    if not isinstance(value, dict) or any(type(value.get(key)) is not int for key in ('page', 'first', 'last', 'total')):
        raise ValueError('listing_schema')
    if value['page'] != page or not 1 <= value['first'] <= value['last'] <= value['total']:
        raise ValueError('listing_range')
    rows = value.get('records')
    if not isinstance(rows, list) or len(rows) != value['last'] - value['first'] + 1:
        raise ValueError('listing_record_count')
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].isdigit() or row['id'] in ids:
            raise ValueError('listing_record_identity')
        ids.add(row['id'])
        if not isinstance(row.get('title'), str) or not row['title'].strip() or row.get('source_url') != BASE + 'ODetail.aspx?intItemId=' + row['id']:
            raise ValueError('listing_record_source')
        if not isinstance(row.get('fields'), dict) or any(not isinstance(key, str) or not isinstance(items, list) or any(not isinstance(text, str) for text in items) for key, items in row['fields'].items()):
            raise ValueError('listing_record_fields')


def parse_listing(raw, expected_page):
    soup = BeautifulSoup(raw, 'html.parser')
    current = soup.select_one('#hidCurrentPage')
    if not current or current.get('value') != str(expected_page):
        raise ValueError('listing_page_identity')
    summary = soup.select_one('.divPage')
    match = re.search(r'Mục\s+([\d.]+)\s+đến\s+([\d.]+)\s+của\s+([\d.]+)', summary.get_text(' ', strip=True) if summary else '')
    if not match:
        raise ValueError('listing_summary_missing')
    first, last, total = (int(x.replace('.', '')) for x in match.groups())
    records = []
    for card in soup.select('.item-box'):
        title = card.select_one('h2 [onclick]')
        identifier = re.fullmatch(r'(?:parent\.)?showPopupDetail\((\d+)\)', title.get('onclick', '').strip()) if title else None
        ordinal = re.match(r'^(\d{1,3}(?:\.\d{3})+|\d+)\.\s*(.+)$', title.get_text(' ', strip=True)) if title else None
        if not identifier or not ordinal or int(ordinal[1].replace('.', '')) != first + len(records):
            raise ValueError('listing_record_identity')
        fields = {}
        for paragraph in card.select('.item-intro p'):
            label, separator, text = paragraph.get_text(' ', strip=True).partition(':')
            if separator:
                fields.setdefault(label.strip(), []).append(text.strip())
        records.append({'id': identifier[1], 'title': ordinal[2], 'fields': fields,
                        'source_url': BASE + 'ODetail.aspx?intItemId=' + identifier[1]})
    if not 1 <= first <= last <= total or len(records) != last - first + 1 or len({x['id'] for x in records}) != len(records):
        raise ValueError('listing_range_or_duplicate')
    form = {node['name']: node.get('value', '') for node in soup.select('input[type="hidden"][name]')}
    # Viewstate and cookies live only in memory; never save anonymous session tokens.
    form['UHeader1:hidMyListIds'] = ''
    form['UHeader1:hidUser'] = ''
    value = {'page': expected_page, 'first': first, 'last': last, 'total': total, 'records': records}
    validate_listing(value, expected_page)
    return value, form


def parse_detail(raw, identifier):
    soup = BeautifulSoup(raw, 'html.parser')
    identity = soup.select_one('#hidItemID')
    if not identity or identity.get('value') != identifier:
        raise ValueError('detail_record_identity')
    fields = []
    for block in soup.select('.popup-modul > .ClearFix'):
        lines = block.get_text('\n', strip=True).splitlines()
        if not any(re.match(r'^Ldr\s', line) for line in lines):
            continue
        for line in lines:
            match = re.match(r'^(Ldr|\d{3})\s+(.+)$', line)
            if match and (match[1] == 'Ldr' or int(match[1]) < 900):
                fields.append({'tag': match[1], 'value': match[2].strip()})
        break
    if not any(row['tag'] == '245' for row in fields):
        raise ValueError('detail_marc_missing')
    return {'id': identifier, 'marc': fields}


def read_snapshot(path, url, page=None):
    try:
        if path.stat().st_size > 2_097_152:
            return None
        row = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(row, dict) or not isinstance(row.get('record'), dict):
            return None
        if page is not None:
            validate_listing(row['record'], page)
        else:
            fields = row['record'].get('marc')
            identifier = row['record'].get('id')
            if not isinstance(identifier, str) or not identifier.isdigit() or url != BASE + 'ODetail.aspx?intItemId=' + identifier:
                return None
            if not isinstance(fields, list) or any(not isinstance(field, dict) or not isinstance(field.get('tag'), str) or not re.fullmatch(r'Ldr|[0-8]\d\d', field['tag']) or not isinstance(field.get('value'), str) for field in fields) or not any(field['tag'] == '245' for field in fields):
                return None
        if row['source_url'] == url and row['sha256'] == digest(row['record']) and datetime.fromisoformat(row['fetched_at']).tzinfo:
            return row
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        pass
    return None


def collect(directory, categories=None, max_pages=None, details=True, acknowledge_robots=False, details_from_pack=None):
    with collection_lock(Path(directory)):
        return _collect(directory,categories,max_pages,details,acknowledge_robots,details_from_pack)


def _collect(directory, categories=None, max_pages=None, details=True, acknowledge_robots=False, details_from_pack=None):
    directory = Path(directory)
    pages, records = directory / 'pages', directory / 'records'
    pages.mkdir(parents=True, exist_ok=True)
    records.mkdir(exist_ok=True)
    categories = [] if details_from_pack is not None else list(categories or CATEGORIES)
    report = {'source': BASE, 'recorded_at': datetime.now(timezone.utc).isoformat(), 'complete': False,
              'blocked': None, 'categories': {}, 'listing_records': 0, 'detail_records': 0,
              'phase': 'listing', 'details_requested': details,
              'session_refreshes': 0, 'transport_retries': 0,
              'minimum_request_gap_seconds': 10, 'robots_disallow_acknowledged': False,
              'scope': 'public bibliographic metadata; no login, full text, reader data or current availability claim'}
    found, fetched_pages, robots = {}, 0, None
    if details_from_pack is not None:
        if not details:
            raise ValueError('details_from_pack_requires_details')
        pack_path=Path(details_from_pack)
        books,inventory=stage_pack(pack_path,pack_path.with_name('catalog-listings-manifest.json'))
        found.update((book.source_url.rsplit('=',1)[-1],book.source_url) for book in books)
        # Field limits quarantine catalog metadata, never validated source identities.
        found.update((row['id'],BASE+'ODetail.aspx?intItemId='+row['id']) for row in inventory['rejected'])
        report.update(phase='details',frozen_inventory={'pack':str(pack_path.resolve()),
            'pack_sha256':inventory['pack_sha256'],'records':inventory['discovered']})
        report['scope']='MARC details for frozen inventory only, not current full-site inventory; '+report['scope']

    def checkpoint():
        report['listing_records'] = len(found)
        report['recorded_at'] = datetime.now(timezone.utc).isoformat()
        write_json(directory / 'manifest.json', report)

    if details_from_pack is not None:
        checkpoint()
    with ExitStack() as stack:
        client = stack.enter_context(network._client())
        def request(url, form=None):
            report['last_request_url']=url
            if robots and not robots.can_fetch(network.USER_AGENT, url):
                if not acknowledge_robots:
                    raise ValueError('robots_disallowed_requires_explicit_operator_acknowledgement')
                report['robots_disallow_acknowledged'] = True
            for attempt in range(3):
                try:
                    final, status, raw, kind = network._fetch(client, url, {HOST}, lambda target: target == url,
                        method='POST' if form is not None else 'GET', form=form,
                        minimum_gap=report['minimum_request_gap_seconds'],max_pacing_wait=None)
                    break
                except network.IntegrationError as error:
                    if not error.retryable or attempt==2:
                        raise
                    report['transport_retries']+=1
                    checkpoint()
                    time.sleep(30*2**attempt)
            if status != 200:
                raise ValueError('source_http_' + str(status))
            if url != 'https://' + HOST + '/robots.txt' and ('text/html' not in kind.lower() or final != url):
                raise ValueError('unexpected_source_type_or_redirect')
            return raw

        def save(path, url, value):
            row = {'source_url': url, 'fetched_at': datetime.now(timezone.utc).isoformat(), 'record': value, 'sha256': digest(value)}
            write_json(path, row)
            return row

        try:
            raw = request('https://' + HOST + '/robots.txt')
            robots = RobotFileParser()
            robots.parse(raw.decode('utf-8', errors='replace').splitlines())
            report['robots_sha256'] = hashlib.sha256(raw).hexdigest()
            if not robots.can_fetch(network.USER_AGENT, BASE):
                if not acknowledge_robots:
                    raise ValueError('robots_disallowed_requires_explicit_operator_acknowledgement')
                report['robots_disallow_acknowledged'] = True
            rate = robots.request_rate(network.USER_AGENT) or robots.request_rate('*')
            if rate and rate.requests <= 0:
                raise ValueError('robots_zero_request_rate')
            report['minimum_request_gap_seconds'] = max(10, robots.crawl_delay(network.USER_AGENT) or robots.crawl_delay('*') or 0,
                                                        rate.seconds / rate.requests if rate else 0)
            if report['minimum_request_gap_seconds'] > 60:
                raise ValueError('source_requires_later_resume')
            # Separate anonymous sessions preserve each category's server-side result set.
            sessions = {}
            for category in categories:
                url = category_url(category)
                category_client = stack.enter_context(network._client())
                client = category_client
                value, form = parse_listing(request(url), 1)
                path = pages / (category + '-00001.json')
                old = read_snapshot(path, url, 1)
                if old and old['record'] != value:
                    raise ValueError('inventory_changed_use_new_output_directory')
                if not old:
                    save(path, url, value)
                    fetched_pages += 1
                sessions[category] = (client, form, value)
                report['categories'][category] = {'name': CATEGORIES[category], 'total': value['total'], 'pages': 1, 'unique_records': len(value['records']), 'complete': value['last'] == value['total']}
                found.update((row['id'], row['source_url']) for row in value['records'])
                checkpoint()
            # Round robin keeps all six document types progressing during a long harvest.
            active = dict.fromkeys(categories, 1)
            seen = {category: set() for category in categories}
            while active:
                for category in list(active):
                    page = active[category]
                    client, form, seed = sessions[category]
                    url = category_url(category)
                    path = pages / f'{category}-{page:05}.json'
                    row = read_snapshot(path, url, page)
                    if row:
                        value = row['record']
                    else:
                        if max_pages is not None and fetched_pages >= max_pages:
                            raise ValueError('page_budget_exhausted')
                        form.update(hidCurrentPage=str(page), raiseShowRecord='raiseShowRecord')
                        raw = request(url, form)
                        try:
                            value, form = parse_listing(raw, page)
                        except ValueError as error:
                            if str(error) != 'listing_summary_missing':
                                raise
                            report['session_refreshes'] += 1
                            report['last_recovery'] = {'category': category, 'page': page, 'response_sha256': hashlib.sha256(raw).hexdigest()}
                            refreshed, form = parse_listing(request(url), 1)
                            if refreshed != seed:
                                raise ValueError('inventory_changed_during_session_refresh')
                            form.update(hidCurrentPage=str(page), raiseShowRecord='raiseShowRecord')
                            value, form = parse_listing(request(url, form), page)
                        save(path, url, value)
                        fetched_pages += 1
                        sessions[category] = (client, form, seed)
                    if value['page'] != page or value['total'] != seed['total'] or value['first'] != len(seen[category]) + 1:
                        raise ValueError('inventory_range_changed')
                    for book in value['records']:
                        if book['id'] in seen[category]:
                            raise ValueError('repeated_record_within_category')
                        seen[category].add(book['id'])
                        found[book['id']] = book['source_url']
                    completed = value['last'] == value['total']
                    if completed and len(seen[category]) != value['total']:
                        raise ValueError('inventory_count_mismatch')
                    report['categories'][category].update(pages=page, unique_records=len(seen[category]), complete=completed)
                    if completed:
                        del active[category]
                    else:
                        active[category] += 1
                    checkpoint()
                    print(json.dumps({'category': category, 'page': page, 'unique_records': len(found), 'category_complete': completed}), flush=True)
            if details:
                report['phase'] = 'details'
                checkpoint()
                for identifier, url in found.items():
                    path = records / (identifier + '.json')
                    if not read_snapshot(path, url):
                        save(path, url, parse_detail(request(url), identifier))
                    report['detail_records'] += 1
                    checkpoint()
                    if report['detail_records'] % 20 == 0:
                        print(json.dumps({'detail_records': report['detail_records'], 'total': len(found)}), flush=True)
            report['complete'] = True
            report['phase'] = 'complete'
        except (ValueError, network.IntegrationError) as error:
            report['blocked'] = str(error) if isinstance(error, ValueError) else 'safe_network_error'
            if isinstance(error,network.IntegrationError):
                report['failure']={'status_code':error.status_code,'detail':str(error.detail),'url':report.get('last_request_url')}
        checkpoint()
    print(json.dumps({key: value for key, value in report.items() if key != 'categories'}), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'backend/runtime/opac-public')
    parser.add_argument('--categories', nargs='+', choices=CATEGORIES, default=list(CATEGORIES))
    parser.add_argument('--max-pages', type=int)
    parser.add_argument('--listings-only', action='store_true')
    parser.add_argument('--details-from-pack', type=Path, help='Collect missing MARC for a validated frozen catalog-listings.jsonl pack; do not refresh listings.')
    parser.add_argument('--acknowledge-robots-disallow', action='store_true', help='Explicit operator direction to read public metadata despite REP; never bypasses authentication or HTTP denials.')
    args = parser.parse_args()
    if args.details_from_pack is not None and args.listings_only:
        parser.error('details-from-pack cannot be combined with listings-only')
    if args.details_from_pack is None and args.max_pages is not None and args.max_pages < len(args.categories):
        parser.error('max-pages must allow at least one seed per category')
    try:
        result = collect(args.output, args.categories, args.max_pages, not args.listings_only, args.acknowledge_robots_disallow, args.details_from_pack)
    except (OSError,ValueError) as error:
        parser.exit(1,'Collection rejected: '+str(error)+'\n')
    raise SystemExit(0 if result['complete'] else 1)
