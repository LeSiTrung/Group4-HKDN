"""Bounded public reads and an explicitly configured library bridge."""

import ipaddress
import json
import os
import re
import socket
import time
from datetime import date
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

USER_AGENT = 'D7LibraryBot/1.0'
MAX_BYTES = 1_048_576
OPAC = 'https://opacthuvien.ut.edu.vn/opac/'


class IntegrationError(HTTPException):
    def __init__(self, detail, status_code=502, *, uncertain=False):
        super().__init__(status_code=status_code, detail=detail)
        self.uncertain = uncertain


def _client():
    return httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False)


def _url(url, allowed):
    try:
        if not isinstance(url, str) or len(url) > 4096 or '\\' in url or any(ord(c) < 33 for c in url):
            raise ValueError
        parsed = urlsplit(url)
        host = (parsed.hostname or '').encode('idna').decode('ascii').lower()
        if parsed.scheme != 'https' or parsed.username is not None or parsed.password is not None or parsed.port not in (None, 443) or host not in allowed:
            raise ValueError
        return urlunsplit(('https', host, parsed.path or '/', parsed.query, ''))
    except (ValueError, UnicodeError):
        raise IntegrationError('Địa chỉ HTTPS không nằm trong danh sách nguồn được phép.', 400) from None


def _public_ip(host):
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        ips = [ipaddress.ip_address(row[4][0]) for row in addresses]
        if not ips or any(not address.is_global or address.is_multicast or address.is_reserved or getattr(address, 'is_site_local', False) for address in ips):
            raise ValueError
        return str(ips[0])
    except (OSError, ValueError):
        raise IntegrationError('Không thể xác minh địa chỉ mạng công khai của nguồn.', 502) from None


def _fetch(client, url, allowed, permitted=None, *, method='GET', headers=None, payload=None):
    """Pin DNS for each hop; preserve certificate verification through original SNI."""
    deadline = time.monotonic() + 30
    for _ in range(4):
        url = _url(url, allowed)
        if permitted and not permitted(url):
            raise IntegrationError('Nguồn không cho phép thu thập đường dẫn này theo robots.txt.', 403)
        host = urlsplit(url).hostname
        ip = _public_ip(host)
        pinned = httpx.URL(url).copy_with(host=ip)
        request_headers = {'User-Agent': USER_AGENT, 'Host': host, 'Accept': 'text/html,application/json,text/plain', **(headers or {})}
        try:
            with client.stream(method, pinned, headers=request_headers, json=payload, extensions={'sni_hostname': host}) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    if method != 'GET':
                        raise IntegrationError('Dịch vụ giao dịch trả về chuyển hướng; cần đối soát.', 409, uncertain=True)
                    url = urljoin(url, response.headers.get('location', ''))
                    continue
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_BYTES or time.monotonic() > deadline:
                        raise IntegrationError('Phản hồi nguồn vượt giới hạn dung lượng.')
                return url, response.status_code, bytes(content), response.headers.get('content-type', '')
        except httpx.HTTPError:
            raise IntegrationError('Không thể kết nối dịch vụ nguồn. Vui lòng thử lại sau.') from None
    raise IntegrationError('Nguồn chuyển hướng quá nhiều lần.')


def _allowed_hosts():
    return {host.strip().lower() for host in os.getenv('CRAWL_ALLOWED_HOSTS', 'lic.ut.edu.vn,opacthuvien.ut.edu.vn').split(',') if host.strip()}


def crawl_pages(url, max_pages=3):
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 10:
        raise IntegrationError('Số trang cần nằm trong khoảng 1–10.', 400)
    seed = _url(url, _allowed_hosts())
    host = urlsplit(seed).hostname
    allowed = {host}
    with _client() as client:
        _, status, raw, _ = _fetch(client, f'https://{host}/robots.txt', allowed)
        robots = RobotFileParser()
        if status == 404:
            robots.parse(['User-agent: *', 'Allow: /'])
        elif status == 200:
            robots.parse(raw.decode('utf-8', errors='replace').splitlines())
        else:
            raise IntegrationError('Không đọc được robots.txt; tạm dừng thu thập.')
        delay = max(1, robots.crawl_delay(USER_AGENT) or robots.crawl_delay('*') or 1)
        rate = robots.request_rate(USER_AGENT) or robots.request_rate('*')
        if rate:
            if rate.requests == 0:
                raise IntegrationError('robots.txt không cho phép gửi yêu cầu.', 403)
            delay = max(delay, rate.seconds / rate.requests)
        if delay > 5:
            raise IntegrationError('Giới hạn robots.txt yêu cầu thu thập bằng lịch riêng.', 503)
        queue, seen, pages = [seed], set(), []
        while queue and len(seen) < max_pages:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            time.sleep(delay)
            final, status, raw, content_type = _fetch(client, current, allowed, lambda candidate: robots.can_fetch(USER_AGENT, candidate))
            if status != 200 or 'text/html' not in content_type.lower():
                raise IntegrationError('Nguồn không trả về trang HTML hợp lệ.')
            soup = BeautifulSoup(raw, 'html.parser')
            links = [link.get('href', '') for link in soup.select('a[href]')[:100]]
            title = soup.title.get_text(' ', strip=True)[:300] if soup.title else host
            for element in soup.select('script, style, nav, header, footer, noscript, form'):
                element.decompose()
            text = (soup.find('main') or soup.body or soup).get_text(' ', strip=True)[:40000]
            if text:
                pages.append({'title': title, 'url': final, 'text': text})
            for link in links:
                try:
                    candidate = _url(urljoin(final, link), allowed)
                    if candidate not in seen and candidate not in queue and len(queue) < 100 and robots.can_fetch(USER_AGENT, candidate):
                        queue.append(candidate)
                except (IntegrationError, ValueError):
                    continue
        if not pages:
            raise IntegrationError('Nguồn không chứa văn bản có thể nhập.')
        return pages


def search_catalog(query, kind='all'):
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200 or kind not in ('all', 'books', 'digital'):
        raise IntegrationError('Từ khóa hoặc loại tài liệu không hợp lệ.', 400)
    option = {'all': '0', 'books': '1', 'digital': '-4'}[kind]
    search_url = OPAC + 'Oshow.aspx?' + urlencode({'rdSearchOption': option, 'txtSearch': query.strip()})
    with _client() as client:
        _, status, raw, _ = _fetch(client, search_url, {'opacthuvien.ut.edu.vn'})
    if status != 200:
        raise IntegrationError('OPAC từ chối hoặc không thể xử lý truy vấn.')
    soup = BeautifulSoup(raw, 'html.parser')
    for element in soup.select('script, style'):
        element.decompose()
    items, seen = [], set()
    for node in soup.select('h2[onclick], a[onclick], a[href]'):
        match = re.search(r'(?:parent\.)?showPopupDetail\(\s*[\'"]?(\d+)', node.get('onclick', ''))
        item_id = match.group(1) if match else None
        if not item_id:
            try:
                target = urlsplit(urljoin(OPAC, node.get('href', '')))
            except ValueError:
                continue
            if target.hostname == 'opacthuvien.ut.edu.vn' and target.path.lower().endswith('/odetail.aspx'):
                item_id = next(iter(parse_qs(target.query).get('intItemId', [])), None)
        title = re.sub(r'^\d+\.\s+', '', node.get_text(' ', strip=True))[:500]
        if not item_id or not item_id.isdigit() or item_id in seen or not title:
            continue
        seen.add(item_id)
        card = node.find_parent(class_='item-box') or node.find_parent('li') or node.parent
        author, year = '', ''
        if len(card.select('h2')) <= 1:
            for paragraph in card.select('p'):
                label, separator, value = paragraph.get_text(' ', strip=True).partition(':')
                if separator and label.strip().lower() == 'tác giả':
                    author = value.strip()[:300]
                elif separator and label.strip().lower() in ('năm xuất bản', 'thông tin xuất bản', 'xuất bản'):
                    match = re.search(r'\b((?:19|20)\d{2})\b', value)
                    year = match.group(1) if match else ''
        items.append({'title': title, 'author': author, 'year': year, 'url': OPAC + 'ODetail.aspx?intItemId=' + item_id})
        if len(items) == 20:
            break
    if not items:
        plain = soup.get_text(' ', strip=True).lower()
        if not any(marker in plain for marker in ('không tìm thấy kết quả', 'không có kết quả', 'không tìm thấy tài liệu', 'không tìm thấy biểu ghi')):
            raise IntegrationError('Không nhận diện được kết quả OPAC; vui lòng mở trang tra cứu trực tiếp.')
    return {'items': items, 'search_url': search_url, 'warning': 'Kết quả trang đầu từ OPAC công khai; xem chi tiết để kiểm tra tình trạng bản sách.'}


def _bridge(token, env_name, payload=None, key=None):
    url = os.getenv(env_name, '')
    if not url:
        raise IntegrationError('Chưa cấu hình kết nối được thư viện cấp phép.', 503)
    if not isinstance(token, str) or not token.strip() or len(token) > 4096 or any(not 33 <= ord(char) <= 126 for char in token):
        raise IntegrationError('Mã truy cập thư viện không hợp lệ.', 400)
    host = urlsplit(url).hostname
    headers = {'Authorization': 'Bearer ' + token}
    if key:
        headers['Idempotency-Key'] = key
    try:
        with _client() as client:
            _, status, raw, _ = _fetch(client, url, {host}, method='POST' if payload is not None else 'GET', headers=headers, payload=payload)
        if status != 200:
            raise IntegrationError('Thư viện chưa xác nhận yêu cầu.', 502)
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (IntegrationError, ValueError, RecursionError) as error:
        if payload is not None:
            raise IntegrationError('Chưa xác định kết quả gia hạn. Cần đối soát với thư viện trước khi gửi lại.', 409, uncertain=True) from None
        if isinstance(error, IntegrationError):
            raise
        raise IntegrationError('Dịch vụ thư viện trả về dữ liệu không hợp lệ.') from None


def _library_texts(data):
    return {key: data[key].strip()[:limit] for key, limit in (('title', 500), ('book_title', 500), ('warning', 1000), ('message', 1000))
            if isinstance(data.get(key), str) and data[key].strip()}


def library_loans(token):
    data = _bridge(token, 'LIBRARY_LOANS_URL')
    if not isinstance(data.get('loans'), list) or len(data['loans']) > 500 or any(not isinstance(loan, dict) for loan in data['loans']):
        raise IntegrationError('Dịch vụ thư viện trả về danh sách mượn không hợp lệ.')
    loans = []
    for loan in data['loans']:
        normalized = _library_texts(loan)
        for key in ('id', 'loan_id'):
            if key in loan:
                value = loan[key]
                if type(value) not in (str, int) or not str(value).strip() or len(str(value)) > 200:
                    raise IntegrationError('Dịch vụ thư viện trả về mã lượt mượn không hợp lệ.')
                normalized[key] = str(value).strip()
        if not any(key in normalized for key in ('id', 'loan_id')):
            raise IntegrationError('Dịch vụ thư viện chưa cung cấp mã lượt mượn.')
        if loan.get('due_date') not in (None, ''):
            try:
                normalized['due_date'] = date.fromisoformat(loan['due_date']).isoformat()
            except (TypeError, ValueError):
                raise IntegrationError('Dịch vụ thư viện trả về ngày hạn trả không hợp lệ.') from None
        loans.append(normalized)
    return {'loans': loans, **{key: value for key, value in _library_texts(data).items() if key in ('message', 'warning')}}


def library_renew(token, loan_id, idempotency_key):
    if any(not isinstance(value, str) or not value.strip() or len(value) > 200 or any(ord(char) < 32 for char in value) for value in (loan_id, idempotency_key)):
        raise IntegrationError('Mã lượt mượn hoặc mã yêu cầu không hợp lệ.', 400)
    if not idempotency_key.isascii():
        raise IntegrationError('Mã yêu cầu cần dùng ký tự ASCII.', 400)
    data = _bridge(token, 'LIBRARY_RENEW_URL', {'loan_id': loan_id}, idempotency_key)
    if data.get('status') != 'renewed' or type(data.get('loan_id')) not in (str, int) or str(data.get('loan_id')) != loan_id or not isinstance(data.get('due_date'), str) or not data['due_date']:
        raise IntegrationError('Chưa có xác nhận gia hạn hợp lệ; cần đối soát với thư viện.', 409, uncertain=True)
    try:
        due_date = date.fromisoformat(data['due_date']).isoformat()
    except ValueError:
        raise IntegrationError('Ngày hạn trả không hợp lệ; cần đối soát với thư viện.', 409, uncertain=True) from None
    return {'status': 'renewed', 'loan_id': loan_id, 'due_date': due_date, **_library_texts(data)}
