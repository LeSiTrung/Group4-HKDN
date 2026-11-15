import math
import sys
import pytest

from app.database.connection import Store
from app.services import rag_service
from scripts import evaluate_vector_index
from scripts.evaluate_vector_index import retrieval_metrics
from training import prepare_data


def test_vector_metrics_use_rank_and_all_relevant_documents():
    score=retrieval_metrics({'a'},['wrong','a'])
    assert score['hit_at1']==0 and score['hit_at5']==1
    assert score['mrr_at5']==0.5
    assert score['ndcg_at5']==pytest.approx(1/math.log2(3))
    assert retrieval_metrics({'a','b'},['a','b'])['ndcg_at5']==1
    assert retrieval_metrics({'a','b'},['a'])['recall_at5']==0.5
    assert all(value==0 for value in retrieval_metrics({'a'},[]).values())


def test_vector_evaluation_rebuild_keeps_published_marc(tmp_path, monkeypatch):
    store = Store(tmp_path / 'library.sqlite3')
    with store.connect() as db:
        url = 'https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=1'
        book_id = db.execute('INSERT INTO books(title,source_url,checked_at,published) VALUES (?,?,?,1)',
                             ('Giáo trình thử', url, '2026-11-13')).lastrowid
        db.execute('INSERT INTO book_marc VALUES (?,?,?,?,?,?,?)',
                   (book_id, url, '2026-11-13', 'hash', 'Kỹ thuật tàu', 'Tóm tắt MARC', ''))

    class Index:
        def __init__(self, settings):
            self.client = self

        def _init(self, model):
            pass

        def _collection(self, namespace):
            return namespace

        def collection_exists(self, name):
            return name == 'books'

        def rebuild(self, documents, namespace):
            assert namespace == 'books'
            assert len(documents) == 1
            assert 'Kỹ thuật tàu' in documents[0]['aliases']
            assert documents[0]['answer'] == 'Tóm tắt MARC'

        def status(self):
            return {}

        def close(self):
            pass

    (tmp_path / 'manifest.json').write_text('{}', encoding='utf-8')
    monkeypatch.delenv('QDRANT_URL', raising=False)
    monkeypatch.setattr(rag_service, 'VectorIndex', Index)
    monkeypatch.setattr(prepare_data, 'load_frozen_dataset', lambda _: ({}, [], {'test': []}))
    monkeypatch.setattr(sys, 'argv', ['evaluate_vector_index.py', '--data-dir', str(tmp_path),
                                    '--dataset', str(tmp_path), '--output', str(tmp_path / 'report.json')])
    evaluate_vector_index.main()
