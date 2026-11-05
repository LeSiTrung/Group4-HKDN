"""Read only the public aggregate availability of one printed OPAC record."""

import re
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from . import integrations as network

_SOURCE = re.compile(re.escape(network.OPAC) + r'ODetail\.aspx\?intItemId=([1-9][0-9]*)')
_cache = OrderedDict()
_lock = threading.Lock()


def _counts(raw, identifier):
    soup = BeautifulSoup(raw, 'html.parser')
    identities = soup.select('#hidItemID')
    scope = soup.select_one('.TabbedPanelsContent')
    if len(identities) != 1 or identities[0].get('value') != identifier or scope is None:
        return None
    kinds = [node.parent.get_text(' ', strip=True) for node in scope.select('li > span')
             if node.get_text(' ', strip=True) == 'Dạng tài liệu:']
    if kinds != ['Dạng tài liệu: Sách truyền thống']:
        return None
    labels = [node for node in scope.select('p') if node.get_text(' ', strip=True) == 'Số bản tài liệu rỗi:']
    if len(labels) != 1:
        return None
    value = labels[0].find_next_sibling()
    match = re.fullmatch(r'([0-9]+)\s*/\s*([0-9]+)', value.get_text(' ', strip=True)) if value and value.name == 'span' else None
    if not match:
        return None
    try:
        available, total = map(int, match.groups())
        if available > total:
            return None
        reserved_labels = [node for node in scope.select('p') if node.get_text(' ', strip=True) == 'Số bản được giữ chỗ:']
        if len(reserved_labels) > 1:
            return None
        if reserved_labels:
            value = reserved_labels[0].find_next_sibling()
            reserved = value.get_text(' ', strip=True) if value and value.name == 'span' else ''
            if not re.fullmatch('[0-9]+', reserved) or int(reserved) > total:
                return None
    except ValueError:
        return None
    return available, total


def _fetch(source_url):
    permitted_calls = 0

    def single_hop(url):
        nonlocal permitted_calls
        permitted_calls += 1
        # Reject every redirect before the shared fetcher can issue another request.
        return permitted_calls == 1 and url == source_url

    with network._client() as client:
        return network._fetch(client, source_url, {'opacthuvien.ut.edu.vn'}, permitted=single_hop)


def get_availability(source_url):
    """Return unknown on source failure; a missing count never means zero copies."""
    identifier = _SOURCE.fullmatch(source_url) if isinstance(source_url, str) and len(source_url) <= 4096 else None
    if not identifier:
        raise network.IntegrationError('Đường dẫn bản ghi OPAC không hợp lệ.', 400)
    with _lock:
        now = time.monotonic()
        for url, (expires, _) in list(_cache.items()):
            if expires <= now:
                del _cache[url]
        if source_url in _cache:
            return dict(_cache[source_url][1])
        counts = None
        try:
            final_url, status, raw, content_type = _fetch(source_url)
            if final_url == source_url and status == 200 and content_type.split(';', 1)[0].strip().lower() in {'text/html', 'application/xhtml+xml'}:
                counts = _counts(raw, identifier[1])
        except network.IntegrationError:
            pass
        result = {'status': ('available' if counts[0] > 0 else 'unavailable') if counts else 'unknown',
                  'available': counts[0] if counts else None, 'total': counts[1] if counts else None,
                  'checked_at': datetime.now(timezone.utc).isoformat(), 'source_url': source_url}
        _cache[source_url] = (time.monotonic() + 60, result)
        while len(_cache) > 128:
            _cache.popitem(last=False)
        return dict(result)
