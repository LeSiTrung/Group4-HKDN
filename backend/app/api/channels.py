"""Authenticated incoming text webhooks; no library transaction tools exposed."""

import hashlib
import hmac
import json
import os
import re
import time

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

router = APIRouter(tags=['channels'])
MAX_BODY = 262144


def _client():
    return httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False)


def _config(*names):
    values = [os.getenv(name, '') for name in names]
    if not all(values):
        raise HTTPException(503, 'Kênh nhắn tin chưa được cấu hình đầy đủ.')
    return values


async def _body(request):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY:
            raise HTTPException(413, 'Webhook vượt giới hạn dung lượng.')
    return bytes(body)


def _json(raw):
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise HTTPException(400, 'Webhook JSON không hợp lệ.') from None


def _fresh(timestamp):
    try:
        return abs(time.time() - int(timestamp) / 1000) <= 48 * 3600
    except (TypeError, ValueError, OverflowError):
        return False


def _claim(request, channel, recipient, message_id):
    event_key = hashlib.sha256(f'{channel}:{recipient}:{message_id}'.encode()).hexdigest()
    with request.app.state.db() as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS channel_events (event_key TEXT PRIMARY KEY, channel TEXT NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL)')
        cursor = connection.execute('INSERT OR IGNORE INTO channel_events(event_key,channel,status,created_at) VALUES (?,?,?,?)', (event_key, channel, 'processing', int(time.time())))
        claimed = cursor.rowcount == 1
    return event_key if claimed else None


def _status(request, event_key, state):
    with request.app.state.db() as connection:
        connection.execute('UPDATE channel_events SET status=? WHERE event_key=?', (state, event_key))


def _send(channel, recipient, answer):
    with _client() as client:
        if channel == 'messenger':
            token, page, version = _config('MESSENGER_PAGE_ACCESS_TOKEN', 'MESSENGER_PAGE_ID', 'MESSENGER_GRAPH_VERSION')
            if not re.fullmatch(r'v\d+\.\d+', version) or not re.fullmatch(r'[A-Za-z0-9_-]+', page):
                raise ValueError('Invalid channel configuration')
            response = client.post(f'https://graph.facebook.com/{version}/{page}/messages', headers={'Authorization': 'Bearer ' + token}, json={'recipient': {'id': recipient}, 'messaging_type': 'RESPONSE', 'message': {'text': answer[:2000]}})
            data = response.json()
            return response.status_code == 200 and isinstance(data, dict) and isinstance(data.get('message_id'), str) and bool(data['message_id'])
        token, = _config('ZALO_ACCESS_TOKEN')
        response = client.post('https://openapi.zalo.me/v3.0/oa/message/cs', headers={'access_token': token}, json={'recipient': {'user_id': recipient}, 'message': {'text': answer[:2000]}})
        data = response.json()
        return response.status_code == 200 and isinstance(data, dict) and data.get('error') == 0 and isinstance(data.get('data'), dict) and bool(data['data'].get('message_id'))


def _process(request, channel, events):
    processed = 0
    for recipient, message_id, text in events:
        if not all(isinstance(value, str) and value.strip() for value in (recipient, message_id, text)) or len(recipient) > 200 or len(message_id) > 300 or len(text) > 4000:
            continue
        event_key = _claim(request, channel, recipient, message_id)
        if event_key is None:
            continue
        try:
            result = request.app.state.answer(text.strip())
            answer = result.get('answer') if isinstance(result, dict) else None
            if not isinstance(answer, str) or not answer.strip():
                _status(request, event_key, 'failed')
                continue
        except Exception:
            _status(request, event_key, 'failed')
            continue
        # Mark before the network call: a crash/timeout must never trigger an automatic duplicate send.
        _status(request, event_key, 'uncertain')
        try:
            acknowledged = _send(channel, recipient, answer)
            _status(request, event_key, 'sent' if acknowledged else 'uncertain')
            processed += int(acknowledged)
        except (httpx.HTTPError, ValueError, HTTPException):
            continue
    return {'status': 'received', 'processed': processed}


@router.get('/webhooks/messenger', response_class=PlainTextResponse)
def messenger_verify(request: Request):
    expected, = _config('MESSENGER_VERIFY_TOKEN')
    query = request.query_params
    if query.get('hub.mode') != 'subscribe' or not hmac.compare_digest(query.get('hub.verify_token', '').encode(), expected.encode()):
        raise HTTPException(403, 'Xác minh webhook thất bại.')
    challenge = query.get('hub.challenge', '')
    if not challenge or len(challenge) > 200:
        raise HTTPException(400, 'Challenge không hợp lệ.')
    return challenge


@router.post('/webhooks/messenger')
async def messenger_webhook(request: Request):
    secret, page, _, _ = _config('MESSENGER_APP_SECRET', 'MESSENGER_PAGE_ID', 'MESSENGER_PAGE_ACCESS_TOKEN', 'MESSENGER_GRAPH_VERSION')
    raw = await _body(request)
    expected = 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get('x-hub-signature-256', '').encode(), expected.encode()):
        raise HTTPException(403, 'Chữ ký webhook không hợp lệ.')
    payload = _json(raw)
    if payload.get('object') != 'page' or not isinstance(payload.get('entry'), list):
        raise HTTPException(400, 'Sự kiện Messenger không hợp lệ.')
    events = []
    for entry in payload['entry'][:100]:
        if not isinstance(entry, dict) or str(entry.get('id')) != page or not isinstance(entry.get('messaging'), list):
            continue
        for event in entry['messaging'][:100]:
            if not isinstance(event, dict):
                continue
            message, sender, target = event.get('message'), event.get('sender'), event.get('recipient')
            if not isinstance(message, dict) or not isinstance(sender, dict) or not isinstance(target, dict) or message.get('is_echo') or str(target.get('id')) != page or not _fresh(event.get('timestamp')):
                continue
            events.append((sender.get('id'), message.get('mid'), message.get('text')))
    return await run_in_threadpool(_process, request, 'messenger', events[:100])


@router.post('/webhooks/zalo')
async def zalo_webhook(request: Request):
    app_id, secret, oa_id, _ = _config('ZALO_APP_ID', 'ZALO_OA_SECRET_KEY', 'ZALO_OA_ID', 'ZALO_ACCESS_TOKEN')
    raw = await _body(request)
    payload = _json(raw)
    stamp = payload.get('timestamp')
    if str(payload.get('app_id')) != app_id or not _fresh(stamp):
        raise HTTPException(403, 'Sự kiện Zalo không hợp lệ hoặc đã hết hạn.')
    expected = hashlib.sha256(app_id.encode() + raw + str(stamp).encode() + secret.encode()).hexdigest()
    signature = request.headers.get('x-zevent-signature', '').removeprefix('mac=')
    if not hmac.compare_digest(signature.encode(), expected.encode()):
        raise HTTPException(403, 'Chữ ký webhook không hợp lệ.')
    message, sender, target = payload.get('message'), payload.get('sender'), payload.get('recipient')
    events = []
    if payload.get('event_name') == 'user_send_text' and isinstance(message, dict) and isinstance(sender, dict) and isinstance(target, dict) and str(target.get('id')) == oa_id:
        events.append((sender.get('id'), message.get('msg_id'), message.get('text')))
    return await run_in_threadpool(_process, request, 'zalo', events)
