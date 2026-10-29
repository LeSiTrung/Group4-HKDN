"""Bound request size before parsing; reject cross-site mutations and bursts."""
import time
from collections import defaultdict, deque
from threading import Lock
from starlette.datastructures import Headers
from starlette.responses import JSONResponse


class RequestGate:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.hits, self.lock = defaultdict(deque), Lock()
        self.next_gc = 0

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        path, method = scope['path'], scope['method']
        unsafe = method not in ('GET', 'HEAD', 'OPTIONS')
        if unsafe and path.startswith('/api/') and not path.startswith('/api/webhooks/'):
            origin = headers.get('origin', '').rstrip('/')
            if headers.get('x-requested-with') != 'D7' or (origin and origin not in self.settings.origins):
                return await JSONResponse({'detail': 'Nguồn yêu cầu không hợp lệ.'}, 403)(scope, receive, send)
        if not self.settings.testing and path.startswith('/api/'):
            now = time.monotonic()
            group = 'auth' if path.startswith('/api/auth/') and unsafe else 'api'
            key = (scope.get('client', ('unknown',))[0], group)
            with self.lock:
                # Bound memory even when public callers rotate addresses.
                if len(self.hits) >= 10000 and now>=self.next_gc:
                    self.hits = defaultdict(deque, {k: v for k, v in self.hits.items() if v and v[-1] > now-60})
                    self.next_gc = now+60
                blocked = key not in self.hits and len(self.hits)>=10000
                if not blocked:
                    bucket = self.hits[key]
                    while bucket and bucket[0] <= now-60:
                        bucket.popleft()
                    blocked = len(bucket) >= (10 if group == 'auth' else 120)
                    if not blocked:
                        bucket.append(now)
            if blocked:
                return await JSONResponse({'detail': 'Bạn gửi quá nhanh. Vui lòng thử lại sau một phút.'}, 429, headers={'Retry-After': '60'})(scope, receive, send)
        if unsafe:
            chunks, size = [], 0
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                chunk = message.get('body', b'')
                size += len(chunk)
                if size > 65536:
                    return await JSONResponse({'detail': 'Yêu cầu vượt quá 64 KiB.'}, 413)(scope, receive, send)
                chunks.append(chunk)
                if not message.get('more_body', False):
                    break
            delivered = False

            async def bounded_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
                return await receive()
        else:
            bounded_receive = receive

        async def secure_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + [
                    (b'x-content-type-options', b'nosniff'), (b'x-frame-options', b'DENY'),
                    (b'referrer-policy', b'strict-origin-when-cross-origin'),
                    (b'cache-control', b'no-store')]
                if self.settings.secure_cookies:
                    message['headers'].append((b'strict-transport-security', b'max-age=31536000'))
            await send(message)
        await self.app(scope, bounded_receive, secure_send)
