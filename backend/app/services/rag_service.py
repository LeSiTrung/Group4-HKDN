"""Vietnamese lexical baseline and an optional persistent semantic vector index."""
import hashlib
import json
import os
import re
import threading
import unicodedata
from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from time import monotonic
from uuid import NAMESPACE_URL, uuid5

STOP = set('toi minh ban cho hoi la co khong nao nhu the mot nhung va cua ve tai thu vien duoc muon can lam cach huong dan'.split())
NONSPACING_MARKS = dict.fromkeys(code for code in range(0x110000) if unicodedata.category(chr(code)) == 'Mn')
NON_SEARCH_CHARACTER = re.compile(r'[^a-z0-9 ]')


def normalize(text):
    text = unicodedata.normalize('NFD', text.lower().replace('đ','d'))
    if not text.isascii():
        text = text.translate(NONSPACING_MARKS)
    return ' '.join(NON_SEARCH_CHARACTER.sub(' ',text).split())


def tokens(text):
    return set(normalize(text).split()) - STOP


def keyword_search(question, rows):
    q, qt = normalize(question), tokens(question)
    results = []
    if not qt:
        return results
    for row in rows:
        variants = [row['question'], *row['aliases']]
        exact = any(q == normalize(x) for x in variants)
        phrases = [normalize(x) for x in row['keywords']]
        phrase_hits = [x for x in phrases if len(x)>=3 and re.search(r'(?<!\w)'+re.escape(x)+r'(?!\w)', q)]
        rt = tokens(' '.join(variants + row['keywords']))
        common = len(qt & rt)
        coverage = common/max(len(qt),1)
        if exact or (phrase_hits and coverage>=0.45) or (common>=2 and coverage>=0.65):
            score = 10 if exact else min(0.99, coverage*0.7 + min(len(phrase_hits),2)*0.15)
            results.append((row, score))
    return sorted(results, key=lambda x: (-x[1], x[0]['id']))


def chunk_text(text):
    """Keep raw UTF-8 excerpts under the embedding budget, with 48-byte overlap."""
    offsets = [0]
    for char in text:
        offsets.append(offsets[-1] + len(char.encode('utf-8')))
    chunks, start = [], 0
    while start < len(text):
        end = bisect_right(offsets, offsets[start] + 384) - 1
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(start + 1, bisect_left(offsets, offsets[end] - 48))
    return chunks


def knowledge_chunks(row):
    chunks = chunk_text(row['answer'])
    for text in [row['question'], *row['aliases']]:
        if text and text not in row['answer']:
            chunks.extend(chunk_text(text))
    return chunks


def row_fingerprint(row):
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


class VectorDocuments(Sequence):
    """Catalog documents projected once per SQLite revision and treated as read-only."""

    def __init__(self, rows):
        self._rows = tuple(rows)
        self.by_id = {row['id']: row for row in self._rows}
        self.row_hashes = {source_id: row_fingerprint(row) for source_id, row in self.by_id.items()}
        self.fingerprint = row_fingerprint(self.row_hashes)

    def __getitem__(self, index):
        return self._rows[index]

    def __len__(self):
        return len(self._rows)


class IndexBusy(RuntimeError):
    pass


class VectorIndex:
    def __init__(self, settings):
        self.settings, self.lock = settings, threading.RLock()
        self.reader_state = threading.Condition()
        self.active_readers = 0
        self.client = self.model = None
        self.fingerprint = None
        self.fingerprints = {}
        self.namespaces = {}
        self.book_lock = threading.Lock()
        self.book_pool = ThreadPoolExecutor(max_workers=1,thread_name_prefix='opac-index')
        self.book_job = None
        self.knowledge_job = None
        self.book_revision = 0
        self.book_ready_revision = -1
        self.book_retry_at = 0
        self.closing = threading.Event()
        self.error = None
        self.model_name = os.getenv('EMBEDDING_MODEL','sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        self.local_export = None
        if os.getenv('EMBEDDING_EXPORT','').strip():
            from .embedding_model import verified_export
            self.local_export=verified_export(os.environ['EMBEDDING_EXPORT'])
            self.model_name=self.local_export['name']
        self.collection = self._collection('knowledge')

    def _collection(self, namespace):
        if namespace not in ('knowledge', 'books'):
            raise ValueError('Unsupported vector namespace')
        return namespace + '_chunks_v1_' + hashlib.sha256(self.model_name.encode()).hexdigest()[:12]

    def _init(self, model=True):
        if self.client is None:
            from qdrant_client import QdrantClient
            url = os.getenv('QDRANT_URL')
            self.client = QdrantClient(url=url, api_key=os.getenv('QDRANT_API_KEY') or None) if url else QdrantClient(path=str(self.settings.data_dir/'vectors'))
        if model and self.model is None:
            if self.local_export:
                from .embedding_model import load_local_model
                self.model=load_local_model(self.local_export)
            else:
                from fastembed import TextEmbedding
                self.model = TextEmbedding(model_name=self.model_name, cache_dir=str(self.settings.data_dir/'models'), threads=2)

    @contextmanager
    def _read_access(self):
        if not self.lock.acquire(blocking=False):
            raise IndexBusy('Vector index is busy')
        try:
            limit = 4 if os.getenv('QDRANT_URL') else 1
            with self.reader_state:
                if self.closing.is_set() or self.active_readers >= limit:
                    raise IndexBusy('Vector index is busy')
                self.active_readers += 1
        finally:
            self.lock.release()
        try:
            yield
        finally:
            with self.reader_state:
                self.active_readers -= 1
                if self.active_readers == 0:
                    self.reader_state.notify_all()

    @contextmanager
    def _write_access(self, *, blocking=True):
        if not self.lock.acquire(blocking=blocking):
            raise IndexBusy('Vector index is busy')
        try:
            # Holding the writer lock stops new admissions while existing reads drain.
            with self.reader_state:
                if not blocking and self.active_readers:
                    raise IndexBusy('Vector index is busy')
                self.reader_state.wait_for(lambda: self.active_readers == 0)
            yield
        finally:
            self.lock.release()

    def invalidate(self):
        with self._write_access():
            self.fingerprints.clear()
            self.fingerprint=None
            for status in self.namespaces.values():
                status['ready'] = False

    def invalidate_books(self):
        with self.book_lock:
            self.book_revision+=1

    def prepare_knowledge(self, load_rows):
        with self.book_lock:
            if self.closing.is_set():
                return 'unavailable'
            if self.knowledge_job is not None and not self.knowledge_job.done():
                return 'preparing'
            if self.namespaces.get('knowledge',{}).get('ready') and self.model is not None:
                return 'ready'
            self.knowledge_job=self.book_pool.submit(self._prepare_knowledge,load_rows)
            return 'preparing'

    def _prepare_knowledge(self, load_rows):
        with self._write_access():
            try:
                if self.closing.is_set():
                    return
                rows=load_rows()
                self.rebuild(rows)
                if rows and not self.closing.is_set():
                    self._init()
            except Exception as exc:
                self.error=type(exc).__name__
                self.namespaces.setdefault('knowledge',{'sources':0,'chunks':0})['ready']=False

    def prepare_books(self, load_rows):
        with self.book_lock:
            if self.closing.is_set() or monotonic()<self.book_retry_at:
                return 'unavailable'
            if self.book_job is not None and not self.book_job.done():
                return 'preparing'
            if self.book_ready_revision==self.book_revision and self.namespaces.get('books',{}).get('ready'):
                return 'ready'
            self.book_job=self.book_pool.submit(self._prepare_books,load_rows,self.book_revision)
            return 'preparing'

    def _prepare_books(self, load_rows, revision):
        try:
            rows=load_rows()
            with self._write_access():
                self.rebuild(rows,'books')
                if rows and not self.closing.is_set():
                    self._init()
        except Exception as exc:
            with self.book_lock:
                self.book_retry_at=monotonic()+30
                self.namespaces.setdefault('books',{'sources':0,'chunks':0})['ready']=False
                self.error=type(exc).__name__
        else:
            with self.book_lock:
                self.book_ready_revision=revision
                self.book_retry_at=0

    def rebuild(self, rows, namespace='knowledge'):
        from qdrant_client.models import Distance, PayloadSchemaType, PointIdsList, PointStruct, VectorParams
        with self._write_access():
            try:
                collection = self._collection(namespace)
                self._init(model=False)
                corpus = rows if isinstance(rows, VectorDocuments) else VectorDocuments(rows)
                row_hashes, fingerprint = corpus.row_hashes, corpus.fingerprint
                exists = self.client.collection_exists(collection)
                if exists and fingerprint == self.fingerprints.get(collection):
                    self.error = None
                    self.namespaces[namespace]['ready']=True
                    return len(rows)
                documents = {}
                for row in rows:
                    row_hash = row_hashes[row['id']]
                    for number, text in enumerate(knowledge_chunks(row)):
                        chunk_id = str(uuid5(NAMESPACE_URL, f'{collection}:{row["id"]}:{row_hash}:{number}'))
                        documents[chunk_id] = {'source_id': row['id'], 'row_hash': row_hash,
                                               'chunk_index': number, 'text': text}
                existing, offset = {}, None
                if exists:
                    while True:
                        if self.closing.is_set():
                            raise RuntimeError('Index is shutting down')
                        # Local Qdrant sorts the full ID set for each scroll page.
                        page, offset = self.client.scroll(collection, offset=offset, limit=4096,
                                                          with_payload=True, with_vectors=False)
                        existing.update((str(point.id), point.payload) for point in page)
                        if offset is None:
                            break
                changed = [(chunk_id, payload) for chunk_id, payload in documents.items()
                           if existing.get(chunk_id) != payload]
                if changed:
                    self._init()
                    counts=Counter(payload['text'] for _,payload in changed)
                    shared={}
                    for start in range(0,len(changed),64):
                        if self.closing.is_set():
                            raise RuntimeError('Index is shutting down')
                        batch=changed[start:start+64]
                        texts=list(dict.fromkeys(payload['text'] for _,payload in batch if payload['text'] not in shared))
                        vectors=list(self.model.embed(texts)) if texts else []
                        if len(vectors) != len(texts):
                            raise ValueError('Incomplete embedding batch')
                        by_text=dict(zip(texts,vectors))
                        shared.update((text,vector) for text,vector in by_text.items() if counts[text]>1)
                        batch_vectors=[shared[text] if text in shared else by_text[text]
                                       for text in (payload['text'] for _,payload in batch)]
                        if not exists:
                            self.client.create_collection(collection, vectors_config=VectorParams(size=len(batch_vectors[0]), distance=Distance.COSINE))
                            if os.getenv('QDRANT_URL'):
                                self.client.create_payload_index(collection, field_name='source_id', field_schema=PayloadSchemaType.INTEGER)
                            exists=True
                        self.client.upsert(collection, points=[PointStruct(id=chunk_id, vector=vector.tolist(), payload=payload)
                                           for (chunk_id, payload), vector in zip(batch, batch_vectors)], wait=True)
                obsolete = list(existing.keys() - documents.keys())
                if obsolete:
                    self.client.delete(collection, points_selector=PointIdsList(points=obsolete), wait=True)
                self.fingerprints[collection]=fingerprint
                self.fingerprint, self.error = fingerprint, None
                self.namespaces[namespace] = {'sources': len(rows), 'chunks': len(documents), 'ready': True}
                return len(rows)
            except Exception as exc:
                self.error = type(exc).__name__
                self.fingerprints.pop(self._collection(namespace), None)
                self.namespaces.setdefault(namespace, {'sources': 0, 'chunks': 0})['ready'] = False
                raise

    def search_chunks(self, question, rows, namespace='knowledge', source_ids=None, *, ready_only=False):
        if len(question.encode('utf-8'))>384:
            raise ValueError('Embedding query exceeds 384 UTF-8 bytes')
        access = self._read_access() if ready_only else self._write_access(blocking=False)
        with access:
            try:
                from qdrant_client.models import FieldCondition, Filter, MatchAny
                if self.closing.is_set():
                    raise IndexBusy('Vector index is shutting down')
                corpus = rows if isinstance(rows, VectorDocuments) else VectorDocuments(rows)
                if ready_only:
                    if corpus.fingerprint!=self.fingerprints.get(self._collection(namespace)):
                        self.namespaces.setdefault(namespace,{'sources':0,'chunks':0})['ready']=False
                        raise IndexBusy('Book metadata changed since indexing')
                else:
                    self.rebuild(corpus,namespace)
                if not rows or (source_ids is not None and not source_ids):
                    return []
                if ready_only:
                    if self.client is None or self.model is None:
                        raise IndexBusy('Vector index is still preparing')
                else:
                    self._init()
                vector = next(self.model.query_embed(question)).tolist()
                query_filter = None if source_ids is None else Filter(must=[FieldCondition(key='source_id', match=MatchAny(any=list(source_ids)))])
                collection = self._collection(namespace)
                query_options = {'query': vector, 'query_filter': query_filter, 'limit': 6, 'score_threshold': 0.45}
                if namespace == 'books':
                    # A slightly larger chunk pool usually gives six sources in one query.
                    candidates = self.client.query_points(collection, **{**query_options, 'limit': 18}).points
                    by_source = {}
                    for point in candidates:
                        by_source.setdefault((point.payload or {}).get('source_id'), point)
                    if len(by_source) < 6 and len(candidates) == 18:
                        groups = self.client.query_points_groups(collection, group_by='source_id', group_size=1,
                                                                 **query_options).groups
                        hits = [group.hits[0] for group in groups if group.hits]
                    else:
                        hits = list(by_source.values())[:6]
                else:
                    hits = self.client.query_points(collection, **query_options).points
                matches = []
                for hit in hits:
                    payload = hit.payload or {}
                    source_id = payload.get('source_id')
                    if source_id in corpus.by_id and payload.get('row_hash') == corpus.row_hashes[source_id]:
                        matches.append({'row': corpus.by_id[source_id], 'text': payload['text'],
                                        'score': float(hit.score), 'chunk_id': str(hit.id)})
                if not ready_only:
                    self.error = None
                    self.namespaces[namespace]['ready'] = True
                return matches
            except IndexBusy:
                raise
            except Exception as exc:
                self.error = type(exc).__name__
                self.namespaces.setdefault(namespace, {'sources': 0, 'chunks': 0})['ready'] = False
                raise

    def search(self, question, rows, namespace='knowledge', source_ids=None, *, ready_only=False):
        results, seen = [], set()
        for match in self.search_chunks(question, rows, namespace, source_ids=source_ids,ready_only=ready_only):
            row = match['row']
            if row['id'] not in seen:
                results.append((row, match['score']))
                seen.add(row['id'])
        return results

    def close(self):
        with self.book_lock:
            self.closing.set()
        self.book_pool.shutdown(wait=True,cancel_futures=True)
        with self._write_access():
            if self.client:
                self.client.close()
                self.client = None

    def status(self):
        namespaces={name:dict(value) for name,value in self.namespaces.copy().items()}
        with self.book_lock:
            if self.book_job is not None:
                books=namespaces.setdefault('books',{'sources':0,'chunks':0,'ready':False})
                if not self.book_job.done() or self.book_ready_revision!=self.book_revision:
                    books['ready']=False
        return {'configured': os.getenv('ENABLE_VECTORS','true').lower()=='true',
                'ready': self.fingerprint is not None and self.error is None and all(value['ready'] for value in namespaces.values()),
                'model': self.model_name, 'error': self.error,
                'namespaces': namespaces}
