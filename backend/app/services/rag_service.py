"""Vietnamese lexical baseline and an optional persistent semantic vector index."""
import hashlib
import json
import os
import re
import threading
import unicodedata
from bisect import bisect_left, bisect_right
from uuid import NAMESPACE_URL, uuid5

STOP = set('toi minh ban cho hoi la co khong nao nhu the mot nhung va cua ve tai thu vien duoc muon can lam cach huong dan'.split())


def normalize(text):
    text = unicodedata.normalize('NFD', text.lower().replace('đ','d'))
    return ' '.join(re.sub(r'[^a-z0-9 ]',' ', ''.join(x for x in text if unicodedata.category(x)!='Mn')).split())


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


class VectorIndex:
    def __init__(self, settings):
        self.settings, self.lock = settings, threading.RLock()
        self.client = self.model = None
        self.fingerprint = None
        self.fingerprints = {}
        self.namespaces = {}
        self.error = None
        self.model_name = os.getenv('EMBEDDING_MODEL','sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
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
            from fastembed import TextEmbedding
            self.model = TextEmbedding(model_name=self.model_name, cache_dir=str(self.settings.data_dir/'models'), threads=2)

    def invalidate(self):
        with self.lock:
            self.fingerprints.clear()
            self.fingerprint=None
            for status in self.namespaces.values():
                status['ready'] = False

    def rebuild(self, rows, namespace='knowledge'):
        from qdrant_client.models import Distance, PointIdsList, PointStruct, VectorParams
        with self.lock:
            try:
                collection = self._collection(namespace)
                self._init(model=False)
                row_hashes = {row['id']: row_fingerprint(row) for row in rows}
                fingerprint = row_fingerprint(row_hashes)
                exists = self.client.collection_exists(collection)
                if exists and fingerprint == self.fingerprints.get(collection):
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
                        page, offset = self.client.scroll(collection, offset=offset, limit=256,
                                                          with_payload=True, with_vectors=False)
                        existing.update((str(point.id), point.payload) for point in page)
                        if offset is None:
                            break
                changed = [(chunk_id, payload) for chunk_id, payload in documents.items()
                           if existing.get(chunk_id) != payload]
                if changed:
                    self._init()
                    vectors = list(self.model.embed([payload['text'] for _, payload in changed]))
                    if len(vectors) != len(changed):
                        raise ValueError('Incomplete embedding batch')
                    if not exists:
                        self.client.create_collection(collection, vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE))
                    self.client.upsert(collection, points=[PointStruct(id=chunk_id, vector=vector.tolist(), payload=payload)
                                       for (chunk_id, payload), vector in zip(changed, vectors)], wait=True)
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

    def search_chunks(self, question, rows, namespace='knowledge', source_ids=None):
        from qdrant_client.models import FieldCondition, Filter, MatchAny
        if len(question.encode('utf-8'))>384:
            raise ValueError('Embedding query exceeds 384 UTF-8 bytes')
        with self.lock:
            try:
                self.rebuild(rows,namespace)
                if not rows or (source_ids is not None and not source_ids):
                    return []
                self._init()
                vector = next(self.model.query_embed(question)).tolist()
                query_filter = None if source_ids is None else Filter(must=[FieldCondition(key='source_id', match=MatchAny(any=list(source_ids)))])
                hits = self.client.query_points(self._collection(namespace), query=vector, query_filter=query_filter,
                                                limit=6, score_threshold=0.45).points
                current = {row['id']: row for row in rows}
                hashes = {row['id']: row_fingerprint(row) for row in rows}
                matches = []
                for hit in hits:
                    payload = hit.payload or {}
                    source_id = payload.get('source_id')
                    if source_id in current and payload.get('row_hash') == hashes[source_id]:
                        matches.append({'row': current[source_id], 'text': payload['text'],
                                        'score': float(hit.score), 'chunk_id': str(hit.id)})
                self.error = None
                self.namespaces[namespace]['ready'] = True
                return matches
            except Exception as exc:
                self.error = type(exc).__name__
                self.namespaces.setdefault(namespace, {'sources': 0, 'chunks': 0})['ready'] = False
                raise

    def search(self, question, rows, namespace='knowledge', source_ids=None):
        results, seen = [], set()
        for match in self.search_chunks(question, rows, namespace, source_ids=source_ids):
            row = match['row']
            if row['id'] not in seen:
                results.append((row, match['score']))
                seen.add(row['id'])
        return results

    def close(self):
        with self.lock:
            if self.client:
                self.client.close()
                self.client = None

    def status(self):
        return {'configured': os.getenv('ENABLE_VECTORS','true').lower()=='true',
                'ready': self.fingerprint is not None and self.error is None and all(value['ready'] for value in self.namespaces.values()),
                'model': self.model_name, 'error': self.error,
                'namespaces': {name: dict(value) for name, value in self.namespaces.items()}}
