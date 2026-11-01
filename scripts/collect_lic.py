"""Stage public LIC HTML for review; never imports crawled text into the chatbot."""
import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.services import integrations as network

BASE = 'https://lic.ut.edu.vn'
HOST = 'lic.ut.edu.vn'


def write_json(path, value):
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def url_scope(url):
    try:
        url = network._url(url, {HOST})
    except network.IntegrationError:
        return None, 'unsafe_host'
    parsed = urlsplit(url)
    clean = url.split('?')[0]
    path = unquote(parsed.path).lower()
    if parsed.query:
        return clean + '?query_omitted', 'query'
    if re.search(r'\.(?:pdf|docx?|xlsx?|pptx?|zip|rar|exe|jpe?g|png|gif|webp|svg|mp[34]|avi|xml|css|js|txt|woff2?)$', path):
        return clean, 'media'
    if any(word in path for word in ('casino', 'betwinner', 'playregal', 'joka-', 'machance')):
        return clean, 'spam'
    if path.startswith(('/nhan-su', '/author/', '/cong-tac-vien')):
        return clean, 'personnel'
    if path.startswith(('/blocks/', '/featured_item', '/wp-', '/feed/', '/download/')) or path.endswith('/feed/'):
        return clean, 'template'
    if path.startswith('/dich-vu-cong-nghe-thong-tin/') or path.strip('/') in {
        'dieu-khoan-su-dung-uth-app', 'quan-ly-he-thong-hoc-thi-va-ho-tro-truc-tuyen',
        'lap-trinh-phan-mem', 'bao-tri-may-tinh', 'quan-tri-he-thong-thong-tin',
        'pham-mem-quan-ly-dao-tao', 'phan-mem-quan-ly-dao-tao', 'quan-ly-phong-lab-phong-hoc-phong-hop-truc-tuyen',
        'quan-tri-mang-du-lieu-website-csdl', 'he-thong-mang-may-tinh', 'elearning'}:
        return clean, 'non_library_it'
    return clean, None


def sitemap_locations(raw):
    try:
        tree = ET.fromstring(raw)
    except ET.ParseError:
        raise ValueError('malformed_sitemap') from None
    kind = tree.tag.rsplit('}', 1)[-1]
    if kind not in ('sitemapindex', 'urlset'):
        raise ValueError('unexpected_sitemap')
    child = 'sitemap' if kind == 'sitemapindex' else 'url'
    return kind, [node.text.strip() for node in tree.findall('{*}' + child + '/{*}loc') if node.text]


def parse_page(raw, url):
    soup = BeautifulSoup(raw, 'html.parser')
    links = [urljoin(url, node['href']) for node in soup.select('a[href]')]
    title = soup.title.get_text(' ', strip=True)[:300] if soup.title else ''
    for node in soup.select('script,style,nav,header,footer,noscript,form,aside'):
        node.decompose()
    content = soup.select_one('.entry-content') or soup.find('main') or soup.body or soup
    text = content.get_text('\n', strip=True)
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', '[email omitted]', text)
    # Old public examples may contain credentials; they are never evidence for login.
    text = '\n'.join(line for line in text.splitlines() if not re.search(r'password|mật khẩu|mat khau', line, re.I))
    return {'title': title, 'text': text, 'links': links, 'status': classify(title, text)}


def classify(title, text):
    title = re.split(r'\s[-|–]\sTrung tâm Thông tin', title, flags=re.I)[0]
    normalized = unicodedata.normalize('NFD', title + ' ' + text)
    normalized = ''.join(c for c in normalized if not unicodedata.combining(c)).lower().replace('đ', 'd')
    status = 'accepted' if any(word in normalized for word in ('thu vien', 'ban doc', 'tai lieu', 'library')) else 'quarantine_unrelated'
    if len(text) < 30:
        status = 'quarantine_empty'
    if re.search(r'casino|betwinner|playregal|machance', normalized):
        status = 'quarantine_spam'
    return status


def read_snapshot(path, url):
    try:
        if path.stat().st_size > 3_000_000:
            return None
        row = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(row, dict) or not isinstance(row.get('page'), dict):
            return None
        page = row['page']
        if row['source_url'] != url or url_scope(row['final_url'])[1] is not None or row['sha256'] != digest(page):
            return None
        if not isinstance(row['fetched_at'], str) or datetime.fromisoformat(row['fetched_at']).tzinfo is None:
            return None
        if not isinstance(page.get('links'), list) or any(not isinstance(link, str) for link in page['links']):
            return None
        if page.get('status') in ('missing_404', 'missing_410', 'quarantine_non_html'):
            return row
        if page.get('status') in ('accepted', 'quarantine_unrelated', 'quarantine_empty', 'quarantine_spam') and isinstance(page.get('text'), str) and isinstance(page.get('title'), str):
            return row
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        pass
    return None


def collect(directory, max_pages=1000):
    directory = Path(directory)
    pages = directory / 'pages'
    pages.mkdir(parents=True, exist_ok=True)
    statuses, queue, seen, hashes = {}, [], set(), {}
    report = {'source': BASE, 'checked_at': datetime.now(timezone.utc).isoformat(), 'complete': False,
              'blocked': None, 'reused': 0, 'sitemaps': [], 'sitemap_locations': 0, 'sitemap_all_loc_elements': 0,
              'minimum_request_gap_seconds': 1, 'scope': 'public HTML only; staged review candidates, not published facts'}
    robots = None
    next_request = 0.0
    retry_after = [None]

    def checkpoint():
        report['counts'] = dict(Counter(row['status'] for row in statuses.values()))
        report['discovered_unique'] = len(statuses) + len(queue)
        report['pending'] = len(queue)
        report['urls'] = statuses
        write_json(directory / 'manifest.json', report)

    def add(url, origin):
        canonical, reason = url_scope(url)
        if canonical is None or canonical in seen:
            return
        seen.add(canonical)
        if reason:
            statuses[canonical] = {'status': 'quarantine_spam' if reason == 'spam' else 'skipped_' + reason, 'discovered_from': origin}
        else:
            queue.append(canonical)

    with network._client() as client:
        def pace(request):
            nonlocal next_request
            time.sleep(max(0, next_request - time.monotonic()))
            next_request = time.monotonic() + report['minimum_request_gap_seconds']
        client.event_hooks['request'].append(pace)
        client.event_hooks['response'].append(lambda response: retry_after.__setitem__(0, response.headers.get('retry-after')))
        def request(url, check=True, page=False):
            nonlocal next_request
            excluded = [None]
            def permitted(target):
                if check and robots and not robots.can_fetch(network.USER_AGENT, target):
                    return False
                if page:
                    excluded[0] = url_scope(target)[1]
                    if excluded[0]:
                        return False
                return True
            for attempt in range(3):
                retry_after[0] = None
                try:
                    result = network._fetch(client, url, {HOST}, permitted)
                except network.IntegrationError as error:
                    if excluded[0]:
                        raise ValueError('redirect_scope_excluded_' + excluded[0]) from None
                    if error.status_code in (400, 403):
                        raise ValueError('robots_or_safe_host_denied') from None
                    if attempt == 2:
                        raise ValueError('network_or_size_limit') from None
                    next_request = max(next_request, time.monotonic() + 2 ** attempt)
                    continue
                if result[1] in (401, 403):
                    raise ValueError('source_denied_' + str(result[1]))
                if result[1] in (429, 500, 502, 503, 504):
                    if attempt == 2:
                        raise ValueError('source_busy_' + str(result[1]))
                    try:
                        delay = float(retry_after[0]) if retry_after[0] else 2 ** (attempt + 1)
                    except ValueError:
                        raise ValueError('retry_after_requires_later_resume') from None
                    if not 0 <= delay <= 60:
                        raise ValueError('retry_after_requires_later_resume')
                    next_request = max(next_request, time.monotonic() + delay)
                    continue
                return result

        try:
            _, status, raw, _ = request(BASE + '/robots.txt', check=False)
            robots = RobotFileParser()
            if status == 404:
                robots.parse(['User-agent: *', 'Allow: /'])
            elif status == 200:
                robots.parse(raw.decode('utf-8', errors='replace').splitlines())
            else:
                raise ValueError('robots_unavailable')
            report['robots_sha256'] = hashlib.sha256(raw).hexdigest()
            if not robots.can_fetch(network.USER_AGENT, BASE + '/'):
                raise ValueError('robots_denied')
            rate = robots.request_rate(network.USER_AGENT) or robots.request_rate('*')
            if rate and rate.requests <= 0:
                raise ValueError('robots_denied')
            gap = max(1, robots.crawl_delay(network.USER_AGENT) or robots.crawl_delay('*') or 0, rate.seconds / rate.requests if rate else 0)
            if gap > 60:
                raise ValueError('robots_requires_later_resume')
            report['minimum_request_gap_seconds'] = gap
            next_request = max(next_request, time.monotonic() + gap)
            maps = [BASE + '/sitemap_index.xml']
            done = set()
            while maps:
                url = maps.pop(0)
                if url in done:
                    continue
                if len(done) >= 20 or network._url(url, {HOST}) != url or not urlsplit(url).path.endswith('.xml') or urlsplit(url).query:
                    raise ValueError('untrusted_sitemap_location')
                done.add(url)
                _, status, raw, _ = request(url)
                if status != 200:
                    raise ValueError('sitemap_http_' + str(status))
                kind, locations = sitemap_locations(raw)
                report['sitemaps'].append({'url': url, 'kind': kind, 'locations': len(locations), 'sha256': hashlib.sha256(raw).hexdigest()})
                if kind == 'sitemapindex':
                    maps.extend(locations)
                else:
                    report['sitemap_locations'] += len(locations)
                    report['sitemap_all_loc_elements'] += sum(node.tag.rsplit('}', 1)[-1] == 'loc' for node in ET.fromstring(raw).iter())
                    for location in locations:
                        add(location, 'sitemap')
            add(BASE + '/', 'seed')
            fetched, processed = 0, 0
            while queue:
                url = queue.pop(0)
                if not robots.can_fetch(network.USER_AGENT, url):
                    statuses[url] = {'status': 'blocked_robots'}
                    continue
                path = pages / (hashlib.sha256(url.encode()).hexdigest() + '.json')
                row = read_snapshot(path, url)
                if row is not None:
                    if 'text' in row['page']:
                        prior_hash = row['sha256']
                        row['page']['status'] = classify(row['page']['title'], row['page']['text'])
                        row['sha256'] = digest(row['page'])
                        if row['sha256'] != prior_hash:
                            write_json(path, row)
                    report['reused'] += 1
                if row is None:
                    if fetched >= max_pages:
                        queue.insert(0, url)
                        break
                    fetched += 1
                    try:
                        final, status, raw, content_type = request(url, page=True)
                        if status in (404, 410):
                            page = {'status': 'missing_' + str(status), 'links': []}
                        elif status != 200:
                            raise ValueError('page_http_' + str(status))
                        elif 'text/html' not in content_type.lower():
                            page = {'status': 'quarantine_non_html', 'links': []}
                        else:
                            page = parse_page(raw, final)
                        row = {'source_url': url, 'final_url': final, 'fetched_at': datetime.now(timezone.utc).isoformat(), 'page': page, 'sha256': digest(page)}
                        write_json(path, row)
                    except ValueError as error:
                        if str(error).startswith('redirect_scope_excluded_'):
                            statuses[url] = {'status': 'skipped_redirect_' + str(error).removeprefix('redirect_scope_excluded_')}
                            checkpoint()
                            continue
                        statuses[url] = {'status': 'error', 'reason': str(error)}
                        if 'denied' in str(error) or 'busy' in str(error) or 'retry_after' in str(error):
                            raise
                        checkpoint()
                        continue
                page = row['page']
                status = page['status']
                content_hash = hashlib.sha256(page.get('text', '').encode()).hexdigest()
                details = {'status': status, 'sha256': row['sha256'], 'fetched_at': row['fetched_at']}
                if status == 'accepted':
                    if content_hash in hashes:
                        details.update(status='duplicate', duplicate_of=hashes[content_hash])
                    else:
                        hashes[content_hash] = url
                statuses[url] = details
                for link in page['links']:
                    add(link, 'navigation')
                checkpoint()
                processed += 1
                if processed % 10 == 0:
                    print(json.dumps({'processed_pages': processed, 'pending': len(queue), 'counts': report['counts']}), flush=True)
            if queue:
                report['blocked'] = 'page_budget_exhausted'
            elif any(row['status'] in ('error', 'blocked_robots') for row in statuses.values()):
                report['blocked'] = 'inaccessible_pages'
            else:
                report['complete'] = True
        except (ValueError, network.IntegrationError) as error:
            report['blocked'] = str(error) if isinstance(error, ValueError) else 'safe_network_denied'
        checkpoint()
    print(json.dumps({k: v for k, v in report.items() if k not in ('urls', 'sitemaps')}), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'backend/runtime/lic-public')
    parser.add_argument('--max-pages', type=int, default=1000)
    args = parser.parse_args()
    if args.max_pages < 1:
        parser.error('max-pages must be positive')
    raise SystemExit(0 if collect(args.output, args.max_pages)['complete'] else 1)
