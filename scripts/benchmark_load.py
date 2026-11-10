"""Bounded read-only load probes against a local library assistant."""
import argparse
import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit

import httpx


def loopback_url(url):
    parsed=urlsplit(url)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1') or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise ValueError('Only an HTTP loopback API root without credentials is allowed.')
    parsed.port
    return url.rstrip('/')


def summarize(rows, elapsed):
    times=sorted(row['elapsed_ms'] for row in rows)
    def percentile(fraction):
        position=(len(times)-1)*fraction
        lower=int(position)
        return round(times[lower]+(times[min(lower+1,len(times)-1)]-times[lower])*(position-lower),2)
    successful=sum(row['ok'] for row in rows)
    return {'requests':len(rows),'successful':successful,'failed':len(rows)-successful,
            'p50_ms':percentile(.5),'p95_ms':percentile(.95),'max_ms':max(times),
            'requests_per_second':round(len(rows)/elapsed,3),
            'http_statuses':dict(Counter(str(row['http_status']) for row in rows)),
            'modes':dict(Counter(row['mode'] for row in rows if row['mode']))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',type=loopback_url,default='http://127.0.0.1:8000')
    parser.add_argument('--concurrency',type=int,nargs='+',default=[1,5,10,20])
    parser.add_argument('--requests',type=int,default=20,help='Requests per phase; total at most100')
    parser.add_argument('--profile',choices=['retrieval','llm'],default='retrieval')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.concurrency or any(value<1 or value>32 or value>args.requests for value in args.concurrency) or not 1<=args.requests<=50 or args.requests*len(args.concurrency)>100:
        parser.error('Use1–32 workers, at least one request per worker and at most100 total probes.')
    cases=[('guide','/api/chat',{'message':'Làm thế nào để tra cứu sách tại thư viện?'}),
           ('catalog','/api/catalog?q=Python&source=local&field=all&page_size=5',None),
           ('metadata','/api/chat',{'message':'Sách “A Guide to Advanced Java JAV0081” xuất bản năm nào?'})]
    if args.profile=='llm':
        if max(args.concurrency)>4:
            parser.error('LLM probes are limited to4 concurrent requests on the local model.')
        cases=[('llm','/api/chat',{'message':'Thư viện tổ chức lớp hướng dẫn sử dụng và khai thác cơ sở dữ liệu cho bạn đọc như thế nào?'})]
    limits=httpx.Limits(max_connections=max(args.concurrency),max_keepalive_connections=max(args.concurrency))
    with httpx.Client(base_url=args.base_url,headers={'X-Requested-With':'LibraryAssistant'},
                      limits=limits,timeout=httpx.Timeout(90,connect=3,pool=5),trust_env=False) as client:
        health_response=client.get('/health')
        health_response.raise_for_status()
        health=health_response.json()
        provider=health['capabilities']['llm_provider']
        if provider not in ('none','ollama') or (args.profile=='llm' and provider!='ollama'):
            parser.error('Only local Ollama/none is permitted; LLM profile requires Ollama.')
        def probe(index):
            name,path,body=cases[index%len(cases)]
            started=perf_counter()
            row={'case':name,'http_status':None,'mode':None,'ok':False}
            try:
                response=client.get(path) if body is None else client.post(path,json=body)
                row['http_status']=response.status_code
                data=response.json()
                row['mode']=data.get('mode')
                row['ok']=response.status_code==200 and (bool(data.get('items')) if name=='catalog' else
                    data.get('status')=='answered' and bool(data.get('sources')) and bool(data.get('answer','').strip()))
                if name=='metadata':
                    row['ok']=row['ok'] and '2010' in data.get('answer','') and len(data.get('books',[]))==1
                if not row['ok']:
                    row['error']=f"HTTP{response.status_code}; status={data.get('status')}"
            except (httpx.HTTPError,ValueError) as exc:
                row['error']=type(exc).__name__
            row['elapsed_ms']=round((perf_counter()-started)*1000,2)
            return row
        warmup=[probe(index) for index in range(len(cases))]
        if not all(row['ok'] for row in warmup):
            parser.error('Public probe fixtures unavailable: '+json.dumps(warmup))
        report={'recorded_at':datetime.now(timezone.utc).isoformat(),'base_url':args.base_url,
                'profile':args.profile,'client_cpu_count':os.cpu_count(),'capabilities':health['capabilities'],
                'scope':'closed-loop synthetic guest clients on one local host; shared IP; no OPAC reads, account writes or transactions',
                'limits':'Small samples; not a production capacity guarantee. LLM warm-up is reported separately; inspect modes/fallbacks.',
                'warmup':warmup,'phases':[]}
        for workers in args.concurrency:
            started=perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                rows=list(pool.map(probe,range(args.requests)))
            elapsed=perf_counter()-started
            phase={'concurrency':workers,'elapsed_seconds':round(elapsed,3),**summarize(rows,elapsed),'results':rows}
            report['phases'].append(phase)
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({key:value for key,value in phase.items() if key!='results'}),flush=True)
    return 0 if all(phase['failed']==0 for phase in report['phases']) else 1


if __name__=='__main__':
    raise SystemExit(main())
