"""Record the frozen independent source-based set; content judgments stay separate."""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / 'tests/evaluation/independent-library-2026-11-07.json'
OUTPUT = ROOT / 'docs/validation/2026-11-07-independent-results.json'
EXPECTED_HASH = '535808732cad9d415ffdcafe82552a8e59690a07ea64e15caf5b904ce1bf25a7'
BASE_URL = 'http://127.0.0.1:8000'
OLLAMA_URL = 'http://127.0.0.1:11434'
MODEL = 'qwen3:1.7b'


def now():
    return datetime.now(timezone.utc).isoformat()


def load_dataset():
    raw = DATASET.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_HASH:
        raise ValueError('Frozen dataset hash changed; do not evaluate a different version silently.')
    return json.loads(raw), digest


def payload(case):
    request = {'message': case['question']}
    if case.get('prior_turns'):
        request['history'] = case['prior_turns']
    return request


def save(report):
    report['checkpoint_at_utc'] = now()
    temporary = OUTPUT.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(OUTPUT)


def pipeline(client, case, digest):
    request = payload(case)
    result = {'id': case['id'], 'dataset_sha256': digest, 'started_at_utc': now(),
              'request': request, 'history_kind': 'authored_scripted_public_context' if 'history' in request else 'none',
              'history_enrichment': 'none; exact frozen role/content, no invented assistant outputs or book IDs'}
    start = perf_counter()
    try:
        response = client.post('/api/chat', json=request)
        result['http_status'] = response.status_code
        result['raw_response_text'] = response.text
        try:
            result['response'] = response.json()
        except ValueError:
            result['response'] = None
    except httpx.HTTPError as exc:
        result['transport_error'] = f'{type(exc).__name__}: {exc}'
    result['elapsed_ms'] = round((perf_counter() - start) * 1000, 2)
    return result


def oracle(case, evidence, digest, generate_answer):
    rows = [evidence[ref] for ref in case['source_refs']]
    result = {'id': case['id'], 'dataset_sha256': digest, 'started_at_utc': now(),
              'question': case['question'], 'source_refs': case['source_refs'],
              'source_ids': {str(row['id']): ref for row, ref in zip(rows, case['source_refs'])},
              'evidence_kind': 'frozen published knowledge rows, including their source answer; oracle retrieval',
              'provider': 'ollama', 'model': MODEL, 'observed_model_http': []}
    original_send = httpx.Client.send

    def capture(client, request, *args, **kwargs):
        parsed = urlsplit(str(request.url))
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.port != 11434:
            raise RuntimeError('Oracle generation may call only loopback Ollama on port 11434.')
        body = json.loads(request.content) if request.content else {}
        if body.get('model') != MODEL:
            raise RuntimeError('Oracle generation attempted an unapproved model.')
        receipt = {'method': request.method, 'url': str(request.url),
                   'request_model': body.get('model'), 'request_options': body.get('options'),
                   'request_stream': body.get('stream'), 'request_think': body.get('think'),
                   'request_body_sha256': hashlib.sha256(request.content).hexdigest(),
                   'request_body_bytes': len(request.content)}
        result['observed_model_http'].append(receipt)
        response = original_send(client, request, *args, **kwargs)
        receipt['http_status'] = response.status_code
        receipt['raw_response_text'] = response.text
        try:
            receipt['response'] = response.json()
        except ValueError:
            pass
        return response

    start = perf_counter()
    try:
        with patch.object(httpx.Client, 'send', capture):
            result['validated_generation'] = generate_answer(case['question'], rows)
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    result['elapsed_ms'] = round((perf_counter() - start) * 1000, 2)
    result['model_http_observed'] = bool(result['observed_model_http'])
    return result


def main():
    dataset, digest = load_dataset()
    if OUTPUT.exists():
        raise SystemExit(f'{OUTPUT} already exists; preserve the original run before another evaluation.')
    report = {'schema_version': '1.0', 'started_at_utc': now(), 'dataset_id': dataset['dataset_id'],
              'dataset_sha256': digest, 'kind': 'separate AI-agent source-based evaluation; not human/library acceptance',
              'execution': {'api_base_url': BASE_URL, 'guest_only': True, 'timeout_seconds': 90,
                            'paid_providers_permitted': False, 'account_or_library_transactions': False,
                            'production_implementation_inspected_by_runner': False,
                            'oracle_generation': 'generate_answer imported as a callable; no prompt/source inspection'},
              'pipeline': [], 'oracle_generation': []}
    with httpx.Client(base_url=BASE_URL, headers={'X-Requested-With': 'LibraryAssistant'},
                      timeout=90, trust_env=False) as client:
        response = client.get('/health')
        response.raise_for_status()
        report['health_before'] = response.json()
        if response.json()['capabilities']['llm_provider'] not in ('none', 'ollama'):
            raise SystemExit('Only none/ollama providers are permitted.')
        save(report)
        for case in dataset['cases']:
            result = pipeline(client, case, digest)
            report['pipeline'].append(result)
            save(report)
            print(f"pipeline {case['id']}: HTTP {result.get('http_status')} {result['elapsed_ms']} ms", flush=True)
    os.environ.update(LLM_PROVIDER='ollama', LLM_MODEL=MODEL, LLM_TIMEOUT='90', OLLAMA_URL=OLLAMA_URL)
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.services.llm_service import generate_answer
    with httpx.Client(timeout=15, trust_env=False) as client:
        response = client.get(OLLAMA_URL + '/api/tags')
        response.raise_for_status()
        report['ollama_tags_before_oracle'] = response.json()
    if not any(row['name'] == MODEL for row in response.json()['models']):
        raise SystemExit('Approved local model is not installed.')
    selected = [case for case in dataset['cases'] if case['expected_status'] == 'answerable'
                and case['source_refs'] and all(ref.startswith('knowledge:') for ref in case['source_refs'])][:10]
    report['oracle_selection'] = {'rule': 'first up to ten answerable cases using knowledge-only evidence',
                                  'case_ids': [case['id'] for case in selected]}
    save(report)
    for case in selected:
        result = oracle(case, dataset['source_evidence'], digest, generate_answer)
        report['oracle_generation'].append(result)
        save(report)
        print(f"oracle {case['id']}: observed={result['model_http_observed']} returned={result.get('validated_generation') is not None} {result['elapsed_ms']} ms", flush=True)
    report['completed_at_utc'] = now()
    save(report)


if __name__ == '__main__':
    main()
