"""Collect public UTH DSpace item metadata; never downloads document files."""
import argparse
import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config import Settings
from app.services import integrations as network

HOST='thuvienso.ut.edu.vn'
BASE='https://'+HOST
INTERVAL=0.25


def item_id(url):
    parsed=urlsplit(url)
    match=re.fullmatch(r'/items/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})',parsed.path)
    if parsed.scheme!='https' or parsed.netloc!=HOST or parsed.query or parsed.fragment or not match:
        raise ValueError('noncanonical_item_url')
    return match[1]


def digest(record):
    return hashlib.sha256(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def snapshot(identifier,record):
    if not isinstance(record,dict) or record.get('uuid')!=identifier or record.get('type')!='item' or not isinstance(record.get('metadata'),dict):
        raise ValueError('invalid_item_identity_or_metadata')
    return {'source_url':BASE+'/items/'+identifier,'fetched_at':datetime.now(timezone.utc).isoformat(),
        'sha256':digest(record),'record':record}


def cached(path,identifier):
    try:
        if path.stat().st_size>2_000_000:
            return False
        row=json.loads(path.read_text(encoding='utf-8'))
        return item_id(row['source_url'])==identifier and row['sha256']==digest(row['record']) and row['record']['uuid']==identifier
    except (OSError,ValueError,KeyError,TypeError,RecursionError):
        return False


def write_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)


def retry_seconds(value):
    try:
        seconds=float(value)
    except (TypeError,ValueError):
        try:
            seconds=max(0,(parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds())
        except (TypeError,ValueError,OverflowError):
            seconds=2
    if not 0<=seconds<=60:
        raise ValueError('retry_after_requires_later_resume')
    return seconds


def collect(directory,limit=None):
    directory=Path(directory)
    records=directory/'records'
    records.mkdir(parents=True,exist_ok=True)
    unavailable=directory/'unavailable'
    unavailable.mkdir(exist_ok=True)
    stop=threading.Event()
    pace=threading.Lock()
    clients_lock=threading.Lock()
    local=threading.local()
    clients=[]
    next_request=[0.0]
    gap=[INTERVAL]
    robots=None

    def request(url):
        if not hasattr(local,'client'):
            local.client=network._client()
            local.client.event_hooks['response'].append(lambda response:setattr(local,'retry_after',response.headers.get('retry-after')))
            with clients_lock:
                clients.append(local.client)
        for attempt in range(3):
            if stop.is_set():
                raise ValueError('collection_stopped')
            with pace:
                wait=next_request[0]-time.monotonic()
                if wait>0:
                    time.sleep(wait)
                next_request[0]=time.monotonic()+gap[0]
            local.retry_after=None
            try:
                fetched=network._fetch(local.client,url,{HOST},
                    (lambda target:robots.can_fetch(network.USER_AGENT,target)) if robots else None)
            except network.IntegrationError as error:
                if error.status_code in (400,403):
                    stop.set()
                    raise ValueError('source_or_robots_denied') from None
                if attempt==2:
                    raise ValueError('source_unreachable_or_oversized') from None
                time.sleep(2**attempt)
                continue
            status=fetched[1]
            if status==403:
                stop.set()
                raise ValueError('source_denied_'+str(status))
            if status in (429,500,502,503,504):
                if attempt==2:
                    stop.set()
                    raise ValueError('source_busy_'+str(status))
                try:
                    delay=retry_seconds(local.retry_after) if local.retry_after else 2**(attempt+1)
                except ValueError:
                    stop.set()
                    raise
                # Shared pause prevents another worker ignoring Retry-After.
                with pace:
                    next_request[0]=max(next_request[0],time.monotonic()+delay)
                continue
            if status!=200:
                raise ValueError('source_http_'+str(status))
            return fetched[2]

    try:
        robots=RobotFileParser()
        # robots must be fetched before enabling the per-path permission check.
        parsed=robots
        robots=None
        parsed.parse(request(BASE+'/robots.txt').decode('utf-8').splitlines())
        robots=parsed
        delay=robots.crawl_delay(network.USER_AGENT) or robots.crawl_delay('*') or 0
        rate=robots.request_rate(network.USER_AGENT) or robots.request_rate('*')
        if delay>60 or (rate and (rate.requests<=0 or rate.seconds/rate.requests>60)):
            raise ValueError('robots_requires_later_resume')
        interval=max(INTERVAL,delay,rate.seconds/rate.requests if rate else 0)
        gap[0]=interval
        # A single lock enforces the advertised gap across both workers.
        next_request[0]=time.monotonic()+interval
        index=ET.fromstring(request(BASE+'/sitemap_index.xml'))
        maps=[n.text for n in index.iter() if n.tag.endswith('}loc') and n.text]
        if not maps or len(maps)>20:
            raise ValueError('unexpected_sitemap_count')
        urls=set()
        for url in maps:
            parsed_url=urlsplit(url)
            if parsed_url.scheme!='https' or parsed_url.netloc!=HOST or not re.fullmatch(r'/sitemap\d+\.xml',parsed_url.path) or parsed_url.query:
                raise ValueError('untrusted_sitemap_location')
            tree=ET.fromstring(request(url))
            for node in tree.iter():
                if node.tag.endswith('}loc') and node.text and urlsplit(node.text).path.startswith('/items/'):
                    item_id(node.text)
                    urls.add(node.text)
        if not urls:
            raise ValueError('empty_public_item_inventory')
        urls=sorted(urls)
        write_json(directory/'inventory.json',{'source':BASE+'/sitemap_index.xml','checked_at':datetime.now(timezone.utc).isoformat(),'items':urls})
        selected=urls[:limit] if limit else urls
        statuses={}

        def fetch_item(url):
            identifier=item_id(url)
            path=records/(identifier+'.json')
            terminal=unavailable/(identifier+'.json')
            if cached(path,identifier):
                return identifier,'reused'
            if terminal.is_file():
                try:
                    prior=json.loads(terminal.read_text(encoding='utf-8'))
                    if prior.get('source_url')==url and prior.get('status') in ('restricted_401','missing_404','missing_410'):
                        return identifier,prior['status']
                except (ValueError,OSError,AttributeError):
                    pass
            try:
                if not robots.can_fetch(network.USER_AGENT,url):
                    stop.set()
                    raise ValueError('public_item_path_disallowed')
                data=json.loads(request(BASE+'/server/api/core/items/'+identifier))
                write_json(path,snapshot(identifier,data))
                return identifier,'fetched'
            except (ValueError,OSError,RecursionError) as error:
                status={'source_http_401':'restricted_401','source_http_404':'missing_404','source_http_410':'missing_410'}.get(str(error))
                if status:
                    write_json(terminal,{'source_url':url,'status':status,'checked_at':datetime.now(timezone.utc).isoformat()})
                    return identifier,status
                return identifier,str(error) if isinstance(error,ValueError) else 'snapshot_write_failed'

        def report():
            success=sum(value in ('fetched','reused') for value in statuses.values())
            inaccessible={key:value for key,value in statuses.items() if value in ('restricted_401','missing_404','missing_410')}
            pending=sum(value=='collection_stopped' for value in statuses.values())
            return {'recorded_at':datetime.now(timezone.utc).isoformat(),'source':BASE,'inventory_total':len(urls),'target':len(selected),
                'processed':len(statuses)-pending,'collected':success,'fetched':sum(value=='fetched' for value in statuses.values()),
                'reused':sum(value=='reused' for value in statuses.values()),'failed':len(statuses)-success-len(inaccessible)-pending,
                'restricted':sum(value=='restricted_401' for value in inaccessible.values()),'inaccessible':inaccessible,
                'remaining':len(urls)-success-len(inaccessible),'complete':success+len(inaccessible)==len(urls),'stopped':stop.is_set(),
                'failures':{key:value for key,value in statuses.items() if value not in ('fetched','reused','restricted_401','missing_404','missing_410','collection_stopped')},
                'max_workers':2,'minimum_request_gap_seconds':interval,'scope':'public metadata only; no full text or reader data'}

        print(f'Inventory: {len(urls)} public item URLs; target {len(selected)}; workers2',flush=True)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures=[executor.submit(fetch_item,url) for url in selected]
            for future in as_completed(futures):
                identifier,status=future.result()
                statuses[identifier]=status
                if len(statuses)%25==0:
                    current=report()
                    write_json(directory/'manifest.json',current)
                    print(f"Collected {current['collected']}/{len(urls)}; failed {current['failed']}; reused {current['reused']}",flush=True)
        final=report()
        write_json(directory/'manifest.json',final)
        print(json.dumps({k:v for k,v in final.items() if k not in ('failures','inaccessible')}),flush=True)
        return final
    finally:
        for client in clients:
            client.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Settings.load().data_dir/'uth-dspace')
    parser.add_argument('--limit',type=int,help='Explicit partial smoke collection; omit for complete exposed inventory')
    args=parser.parse_args()
    if args.limit is not None and args.limit<1:
        parser.error('limit must be positive')
    try:
        result=collect(args.output,args.limit)
    except (ValueError,ET.ParseError,network.IntegrationError) as error:
        parser.exit(1,'Collection stopped: '+(error.detail if isinstance(error,network.IntegrationError) else str(error))+'\n')
    return 0 if result['failed']==0 else 1


if __name__=='__main__':
    raise SystemExit(main())
