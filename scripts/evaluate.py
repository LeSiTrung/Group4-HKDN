"""Repeatable development checks; these cases are not library acceptance data."""
import argparse
import json
import os
import sys
import tempfile
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def failures(case, response):
    errors = []
    if response.get('status') != case['status']:
        errors.append(f"status: expected {case['status']}, got {response.get('status')}")
    if not response.get('answer', '').strip():
        errors.append('empty answer')
    if case.get('source') and not any(case['source'] in s.get('url', '') for s in response.get('sources', [])):
        errors.append('expected source missing')
    if case.get('book') and not any(case['book'] in b.get('title', '') for b in response.get('books', [])):
        errors.append('expected catalog record missing')
    if case.get('no_books') and response.get('books'):
        errors.append('unexpected catalog record')
    if case.get('contains') and case['contains'] not in response.get('answer', ''):
        errors.append('expected grounded fact missing')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', help='Optional running local API, e.g. http://127.0.0.1:8000; invokes its configured models')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', type=Path, default=ROOT / 'tests/evaluation/questions.json')
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding='utf-8'))
    with ExitStack() as stack:
        if args.base_url:
            parsed = urlsplit(args.base_url)
            if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1') or parsed.path not in ('', '/') or parsed.username or parsed.password:
                parser.error('Only an HTTP loopback API is allowed.')
            import httpx
            client = stack.enter_context(httpx.Client(base_url=args.base_url, headers={'X-Requested-With': 'LibraryAssistant'}, timeout=90, trust_env=False))
        else:
            os.environ['LLM_PROVIDER'] = 'none'
            os.environ['ENABLE_VECTORS'] = 'false'
            from fastapi.testclient import TestClient
            from app.main import create_app
            directory = stack.enter_context(tempfile.TemporaryDirectory())
            client = stack.enter_context(TestClient(create_app(Path(directory), testing=True), headers={'X-Requested-With': 'LibraryAssistant'}))
        health = client.get('/health')
        health.raise_for_status()
        capabilities = health.json()['capabilities']
        if args.base_url and capabilities['llm_provider'] not in ('none', 'ollama'):
            parser.error('Live evaluation permits only none/ollama, to avoid paid provider calls.')
        results = []
        for case in cases:
            start = perf_counter()
            response = client.post('/api/chat', json={k: case[k] for k in ('message', 'history') if k in case})
            elapsed = round((perf_counter() - start) * 1000, 2)
            data = response.json()
            errors = failures(case, data) if response.status_code == 200 else [f'HTTP {response.status_code}']
            results.append({'id': case['id'], 'passed': not errors, 'errors': errors, 'elapsed_ms': elapsed, 'response': data})
            print(f"{'PASS' if not errors else 'FAIL'} {case['id']}: {elapsed} ms" + ('; ' + '; '.join(errors) if errors else ''), flush=True)
        report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'kind': 'development regression; not held-out or library-validated',
                  'execution': args.base_url or 'isolated deterministic TestClient; vectors/LLM disabled',
                  'capabilities': capabilities, 'passed': sum(r['passed'] for r in results), 'total': len(results), 'results': results}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f"{report['passed']}/{len(results)} checks passed; report: {args.output}")
        return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
