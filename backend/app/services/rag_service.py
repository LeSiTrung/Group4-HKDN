"""Vietnamese lexical baseline and an optional persistent semantic vector index."""
import hashlib
import json
import os
import re
import threading
import unicodedata

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


class VectorIndex:
    def __init__(self, settings):
        self.settings, self.lock = settings, threading.RLock()
        self.client = self.model = None
        self.fingerprint = None
        self.fingerprints = {}
        self.error = None
        self.model_name = os.getenv('EMBEDDING_MODEL','sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        self.collection = 'knowledge_'+hashlib.sha256(self.model_name.encode()).hexdigest()[:12]

    def _init(self):
        if self.client is None:
            from qdrant_client import QdrantClient
            url = os.getenv('QDRANT_URL')
            self.client = QdrantClient(url=url, api_key=os.getenv('QDRANT_API_KEY') or None) if url else QdrantClient(path=str(self.settings.data_dir/'vectors'))
        if self.model is None:
            from fastembed import TextEmbedding
            self.model = TextEmbedding(model_name=self.model_name, cache_dir=str(self.settings.data_dir/'models'), threads=2)

    def invalidate(self):
        with self.lock:
            self.fingerprints.clear()
            self.fingerprint=None

    def rebuild(self, rows, namespace='knowledge'):
        from qdrant_client.models import Distance, PointStruct, VectorParams
        with self.lock:
            try:
                self._init()
                collection=self.collection if namespace=='knowledge' else 'books_'+hashlib.sha256(self.model_name.encode()).hexdigest()[:12]
                fingerprint = hashlib.sha256(json.dumps(rows, ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                if fingerprint == self.fingerprints.get(collection):
                    return len(rows)
                documents = [x['question']+'\n'+' '.join(x['aliases'])+'\n'+x['answer'] for x in rows]
                if documents:
                    vectors = list(self.model.embed(documents))
                    if self.client.collection_exists(collection):
                        self.client.delete_collection(collection)
                    self.client.create_collection(collection, vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE))
                    self.client.upsert(collection, points=[PointStruct(id=x['id'],vector=v.tolist(),payload={'knowledge_id':x['id']}) for x,v in zip(rows,vectors)])
                elif self.client.collection_exists(collection):
                    self.client.delete_collection(collection)
                self.fingerprints[collection]=fingerprint
                self.fingerprint, self.error = fingerprint, None
                return len(rows)
            except Exception as exc:
                self.error = type(exc).__name__
                raise

    def search(self, question, rows, namespace='knowledge'):
        with self.lock:
            self.rebuild(rows,namespace)
            if not rows:
                return []
            vector = next(self.model.query_embed(question)).tolist()
            collection=self.collection if namespace=='knowledge' else 'books_'+hashlib.sha256(self.model_name.encode()).hexdigest()[:12]
            hits = self.client.query_points(collection,query=vector,limit=3,score_threshold=0.45).points
            # Always join current published rows: deleted/expired sources cannot survive in vectors.
            current = {x['id']:x for x in rows}
            return [(current[x.id],x.score) for x in hits if x.id in current]

    def close(self):
        with self.lock:
            if self.client:
                self.client.close()

    def status(self):
        return {'configured': os.getenv('ENABLE_VECTORS','true').lower()=='true', 'ready': self.fingerprint is not None and self.error is None,
                'model': self.model_name, 'error': self.error}
