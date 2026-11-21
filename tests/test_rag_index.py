from types import SimpleNamespace

import numpy as np
from threading import Event
import pytest
from qdrant_client import QdrantClient

from app.services import rag_service as rag


class Embedding:
    def __init__(self):
        self.documents = []

    def embed(self, documents):
        self.documents.extend(documents)
        return iter(self.vector(text) for text in documents)

    def query_embed(self, text):
        return iter([self.vector(text)])

    @staticmethod
    def vector(text):
        return np.array([1., 0.] if 'TAILMARKER' in text else [0., 1.])


def test_large_rebuild_bounds_each_embedding_and_upsert_batch(tmp_path,monkeypatch):
    index=index_at(tmp_path)
    embed=index.model.embed
    upsert=index.client.upsert
    def bounded_embed(documents):
        assert len(documents)<=64
        return embed(documents)
    def bounded_upsert(*args,**kwargs):
        assert len(kwargs['points'])<=64
        return upsert(*args,**kwargs)
    monkeypatch.setattr(index.model,'embed',bounded_embed)
    monkeypatch.setattr(index.client,'upsert',bounded_upsert)
    try:
        sources=[row(i,answer=f'New source {i}') for i in range(100)]
        index.rebuild(sources)
        assert len(points(index))==sum(len(rag.knowledge_chunks(source)) for source in sources)
    finally:
        index.close()


def test_rebuild_embeds_shared_text_once_but_keeps_distinct_source_points(tmp_path):
    index=index_at(tmp_path)
    sources=[row(i,question='TAILMARKER',answer=f'Nội dung riêng {i}') for i in range(100)]
    try:
        index.rebuild(sources,'books')
        assert index.model.documents.count('TAILMARKER')==1
        shared=[point for point in points(index,'books') if point.payload['text']=='TAILMARKER']
        assert {point.payload['source_id'] for point in shared}=={source['id'] for source in sources}
    finally:
        index.close()


def test_late_embedding_failure_preserves_old_points_and_resumes_completed_batches(tmp_path,monkeypatch):
    index=index_at(tmp_path)
    old=row(999,answer='Old source')
    index.rebuild([old])
    original_ids={p.id for p in points(index)}
    embed=index.model.embed
    calls=[]
    def fail_second_batch(documents):
        calls.append(len(documents))
        if len(calls)==2:
            raise RuntimeError('second batch failed')
        return embed(documents)
    monkeypatch.setattr(index.model,'embed',fail_second_batch)
    sources=[row(i,question=f'Replacement source {i}',answer=f'Replacement source {i}') for i in range(100)]
    try:
        with pytest.raises(RuntimeError,match='second batch'):
            index.rebuild(sources)
        assert original_ids<={p.id for p in points(index)}
        assert index.status()['ready'] is False
    finally:
        index.close()
    restarted=index_at(tmp_path)
    try:
        restarted.rebuild(sources)
        total=sum(len(rag.knowledge_chunks(source)) for source in sources)
        assert len(restarted.model.documents)==total-64
        assert not original_ids&{p.id for p in points(restarted)}
        assert restarted.status()['ready'] is True
    finally:
        restarted.close()


def row(source_id=1, **changes):
    return {'id': source_id, 'question': 'Tra cứu thư viện', 'aliases': [],
            'answer': 'Thông tin nguồn thử nghiệm. ' * 30, **changes}


def index_at(path):
    index = rag.VectorIndex(SimpleNamespace(data_dir=path))
    index.client = QdrantClient(path=str(path / 'vectors'))
    index.model = Embedding()
    return index


def test_book_index_preparation_is_single_flight_and_search_never_waits(tmp_path,monkeypatch):
    index=index_at(tmp_path)
    started,release=Event(),Event()
    source=row(1,answer='TAILMARKER')
    rebuild=index.rebuild
    calls=[]

    def slow_rebuild(rows,namespace):
        with index.lock:
            calls.append(namespace)
            started.set()
            assert release.wait(5)
            return rebuild(rows,namespace)

    monkeypatch.setattr(index,'rebuild',slow_rebuild)
    try:
        assert index.prepare_books(lambda:[source])=='preparing'
        assert started.wait(5)
        assert index.prepare_books(lambda:[source])=='preparing'
        with pytest.raises(rag.IndexBusy):
            index.search_chunks('TAILMARKER',[source])
        index.invalidate_books()
        release.set()
        index.book_job.result(timeout=5)
        assert calls==['books']
        assert index.prepare_books(lambda:[source])=='preparing'
        index.book_job.result(timeout=5)
        assert index.prepare_books(lambda:[source])=='ready'
        assert index.search('TAILMARKER',[source],namespace='books',ready_only=True)[0][0]==source
        assert calls==['books','books']
    finally:
        release.set()
        index.close()


def test_book_warmup_and_invalidated_revision_are_visible_in_status(tmp_path,monkeypatch):
    index=index_at(tmp_path)
    source=row(answer='TAILMARKER')
    index.rebuild([source])
    started,release=Event(),Event()
    def load():
        started.set()
        assert release.wait(5)
        return [source]
    try:
        assert index.prepare_books(load)=='preparing'
        assert started.wait(5)
        status=index.status()
        assert not status['ready'] and not status['namespaces']['books']['ready']
        assert status['namespaces']['knowledge']['ready']
        release.set()
        index.book_job.result(timeout=5)
        assert index.status()['ready']
        index.invalidate_books()
        assert not index.status()['namespaces']['books']['ready']
    finally:
        release.set()
        index.close()


@pytest.mark.parametrize('query',['x'*385,'ạ'*129])
def test_oversized_query_is_rejected_before_embedding_or_index_work(tmp_path,query):
    index=index_at(tmp_path)
    try:
        with pytest.raises(ValueError,match='query'):
            index.search_chunks(query,[row()])
        assert index.model.documents==[]
        assert not points(index)
    finally:
        index.close()


def points(index, namespace='knowledge'):
    collection = index.collection if namespace == 'knowledge' else index._collection(namespace)
    if not index.client.collection_exists(collection):
        return []
    return index.client.scroll(collection, limit=1000, with_payload=True, with_vectors=False)[0]


@pytest.mark.parametrize('text', ['', 'short', 'a' * 900, 'Tiếng Việt 😀 漢字\n' * 100])
def test_chunks_preserve_complete_raw_text_with_utf8_overlap(text):
    chunks = rag.chunk_text(text)
    assert chunks == rag.chunk_text(text)
    if not text:
        assert chunks == []
        return
    assert all(0 < len(chunk.encode('utf-8')) <= 384 for chunk in chunks)
    cursor = 0
    for number, chunk in enumerate(chunks):
        assert text[cursor:cursor + len(chunk)] == chunk
        end = cursor + len(chunk)
        if number < len(chunks) - 1:
            suffix = ''
            for char in reversed(chunk):
                if len((char + suffix).encode('utf-8')) > 48:
                    break
                suffix = char + suffix
            assert suffix and chunks[number + 1].startswith(suffix)
            cursor = end - len(suffix)
        else:
            assert end == len(text)


def test_knowledge_chunks_include_tail_and_bounded_metadata():
    source = row(answer='long text ' * 200 + 'TAILMARKER', aliases=['Alias ' * 100])
    chunks = rag.knowledge_chunks(source)
    assert all(len(text.encode('utf-8')) <= 384 for text in chunks)
    assert any('TAILMARKER' in text for text in chunks)
    assert source['question'] in chunks
    assert any('Alias ' in text for text in chunks)
    assert rag.row_fingerprint(source) == rag.row_fingerprint(dict(reversed(list(source.items()))))
    assert rag.row_fingerprint(source) != rag.row_fingerprint({**source, 'published': False})


def test_incremental_restart_and_single_source_edit(tmp_path):
    index = index_at(tmp_path)
    first, second = row(), row(2, answer='Other source')
    assert index.rebuild([first, second]) == 2
    count = len(index.model.documents)
    assert count > 2
    index.rebuild([first, second])
    assert len(index.model.documents) == count
    index.close()
    restarted = index_at(tmp_path)
    try:
        restarted.rebuild([first, second])
        assert restarted.model.documents == []
        edited = {**second, 'answer': 'Changed source'}
        restarted.rebuild([first, edited])
        assert restarted.model.documents == rag.knowledge_chunks(edited)
        assert restarted.status()['namespaces']['knowledge']['sources'] == 2
        assert restarted.status()['namespaces']['knowledge']['chunks'] == len(points(restarted))
    finally:
        restarted.close()


def test_search_tail_returns_original_rows_and_dedupes(tmp_path):
    index = index_at(tmp_path)
    source = row(answer='background ' * 200 + 'TAILMARKER ' * 20)
    try:
        matches = index.search_chunks('TAILMARKER', [source])
        assert matches and len(matches) <= 6
        assert all(match['row'] is source for match in matches)
        assert 'TAILMARKER' in matches[0]['text']
        assert isinstance(matches[0]['chunk_id'], str)
        assert index.search('TAILMARKER', [source])[0][0] is source
        assert len(index.search('TAILMARKER', [source])) == 1
    finally:
        index.close()


def test_withdrawal_empty_inventory_and_namespaces_do_not_drop_collections(tmp_path, monkeypatch):
    index = index_at(tmp_path)
    monkeypatch.setattr(index.client, 'delete_collection', lambda *a, **k: pytest.fail('must preserve collections'))
    try:
        index.rebuild([row()])
        index.rebuild([row(2)], namespace='books')
        index.rebuild([])
        assert points(index) == []
        assert points(index, 'books')
        assert index.search_chunks('question', []) == []
        assert index.status()['namespaces']['knowledge']['sources'] == 0
    finally:
        index.close()


def test_failed_update_keeps_old_points_and_never_reports_ready(tmp_path, monkeypatch):
    index = index_at(tmp_path)
    original, edited = row(), row(answer='Edited source')
    index.rebuild([original])
    old_ids = {point.id for point in points(index)}
    upsert = index.client.upsert

    def fail_after_partial_upsert(*args, **kwargs):
        assert kwargs['wait'] is True
        kwargs['points'] = kwargs['points'][:1]
        upsert(*args, **kwargs)
        raise RuntimeError('sensitive internal failure details')

    monkeypatch.setattr(index.client, 'upsert', fail_after_partial_upsert)
    try:
        with pytest.raises(RuntimeError):
            index.rebuild([edited])
        assert old_ids <= {point.id for point in points(index)}
        assert index.status()['ready'] is False
        assert 'sensitive' not in str(index.status())
        monkeypatch.setattr(index.client, 'upsert', upsert)
        index.rebuild([edited])
        assert index.status()['ready'] is True
        assert not old_ids & {point.id for point in points(index)}
    finally:
        index.close()


def test_stale_payload_never_becomes_evidence(tmp_path, monkeypatch):
    index = index_at(tmp_path)
    old, current = row(), row(answer='Updated facts')
    index.rebuild([old])
    monkeypatch.setattr(index, 'rebuild', lambda *a, **k: 1)
    try:
        assert index.search_chunks('question', [current]) == []
        assert index.search_chunks('question', [row(2)]) == []
    finally:
        index.close()


def test_query_outage_recovery_restores_readiness(tmp_path, monkeypatch):
    index = index_at(tmp_path)
    source = row()
    index.rebuild([source])
    query_embed = index.model.query_embed

    def fail_query(text):
        raise RuntimeError('private endpoint information')

    monkeypatch.setattr(index.model, 'query_embed', fail_query)
    try:
        with pytest.raises(RuntimeError):
            index.search_chunks('question', [source])
        assert index.status()['ready'] is False
        monkeypatch.setattr(index.model, 'query_embed', query_embed)
        assert index.search_chunks('question', [source])
        assert index.status()['ready'] is True
        assert index.status()['namespaces']['knowledge']['ready'] is True
    finally:
        index.close()


def test_persisted_scan_covers_more_than_one_page_and_preserves_legacy_collection(tmp_path):
    from qdrant_client.models import Distance, VectorParams

    index = index_at(tmp_path)
    legacy = 'knowledge_legacy_fixture'
    index.client.create_collection(legacy, vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    sources = [row(number, answer=f'Source {number}') for number in range(260)]
    try:
        index.rebuild(sources)
        assert len(points(index)) > 256
        index.invalidate()
        index.model.documents.clear()
        index.rebuild(sources)
        assert index.model.documents == []
        assert index.client.collection_exists(legacy)
    finally:
        index.close()


def test_failed_obsolete_delete_is_not_ready_and_retry_removes_withdrawn_chunks(tmp_path, monkeypatch):
    index = index_at(tmp_path)
    first, second = row(), row(2)
    index.rebuild([first, second])
    delete = index.client.delete

    def fail_delete(*args, **kwargs):
        assert kwargs['wait'] is True
        raise RuntimeError('delete unavailable')

    monkeypatch.setattr(index.client, 'delete', fail_delete)
    try:
        with pytest.raises(RuntimeError):
            index.rebuild([first])
        assert index.status()['ready'] is False
        monkeypatch.setattr(index.client, 'delete', delete)
        index.rebuild([first])
        assert {point.payload['source_id'] for point in points(index)} == {first['id']}
        assert index.status()['ready'] is True
    finally:
        index.close()


def test_success_in_other_namespace_does_not_hide_index_failure(tmp_path, monkeypatch):
    index = index_at(tmp_path)
    embed = index.model.embed

    def fail_embed(documents):
        raise RuntimeError('books unavailable')

    monkeypatch.setattr(index.model, 'embed', fail_embed)
    try:
        with pytest.raises(RuntimeError):
            index.rebuild([row()], namespace='books')
        monkeypatch.setattr(index.model, 'embed', embed)
        index.rebuild([row()])
        assert index.status()['namespaces']['books']['ready'] is False
        assert index.status()['ready'] is False
    finally:
        index.close()


def test_source_filter_applies_before_limit_and_preserves_full_inventory(tmp_path, monkeypatch):
    index = index_at(tmp_path)
    sources = [row(number, answer='TAILMARKER source ' + str(number)) for number in range(1, 10)]
    try:
        matches = index.search_chunks('TAILMARKER', sources, namespace='books', source_ids={9})
        assert matches and {match['row']['id'] for match in matches} == {9}
        assert index.search('TAILMARKER', sources, namespace='books', source_ids={8})[0][0] is sources[7]
        assert {point.payload['source_id'] for point in points(index, 'books')} == set(range(1, 10))
        monkeypatch.setattr(index.model, 'query_embed', lambda text: pytest.fail('empty filter must not embed query'))
        assert index.search_chunks('TAILMARKER', sources, namespace='books', source_ids=[]) == []
    finally:
        index.close()


def test_knowledge_warmup_is_single_flight_and_requests_do_not_wait(tmp_path,monkeypatch):
    index=index_at(tmp_path)
    started,release=Event(),Event()
    rebuild=index.rebuild
    source=row(answer='TAILMARKER')
    calls=[]
    def slow_rebuild(rows,namespace='knowledge'):
        with index.lock:
            calls.append(namespace)
            started.set()
            assert release.wait(5)
            return rebuild(rows,namespace)
    monkeypatch.setattr(index,'rebuild',slow_rebuild)
    try:
        assert index.prepare_knowledge(lambda:[source])=='preparing'
        assert started.wait(5)
        assert index.prepare_knowledge(lambda:[source])=='preparing'
        with pytest.raises(rag.IndexBusy):
            index.search_chunks('TAILMARKER',[source])
        release.set()
        index.knowledge_job.result(timeout=5)
        assert calls==['knowledge']
        assert index.prepare_knowledge(lambda:[source])=='ready'
        assert index.search('TAILMARKER',[source])[0][0]==source
    finally:
        release.set()
        index.close()


def test_retrieval_filters_before_top_k_without_rewriting_knowledge(tmp_path):
    from app.services.retrieval import retrieve_knowledge

    index=index_at(tmp_path)
    allowed=row(7,answer='TAILMARKER',keywords=[])
    rows=[row(number,answer='TAILMARKER',keywords=[]) for number in range(1,7)]+[allowed]
    try:
        index.rebuild(rows)
        index.model.documents.clear()
        found=retrieve_knowledge('TAILMARKER',[allowed],index,index_rows=rows)
        assert [source['id'] for source,_ in found['ranked']]==[7]
        assert index.status()['namespaces']['knowledge']['sources']==7
        assert index.model.documents==[]
        assert len(points(index))==sum(len(rag.knowledge_chunks(source)) for source in rows)
    finally:
        index.close()


def test_failed_warmup_is_visible_and_does_not_prevent_later_recovery(tmp_path,monkeypatch):
    index=index_at(tmp_path)
    def unavailable():
        raise RuntimeError('private-detail-not-for-status')
    try:
        assert index.prepare_knowledge(unavailable)=='preparing'
        index.knowledge_job.result(timeout=5)
        assert index.status()['ready'] is False
        assert index.status()['error']=='RuntimeError'
        assert 'private-detail' not in str(index.status())
        assert index.prepare_knowledge(lambda:[row()])=='preparing'
        index.knowledge_job.result(timeout=5)
        assert index.status()['ready'] is True
    finally:
        index.close()
    assert index.prepare_knowledge(lambda:[row()])=='unavailable'


def test_busy_query_does_not_wait_for_vector_module_import(tmp_path,monkeypatch):
    import builtins
    from threading import Thread
    index=index_at(tmp_path)
    started,release=Event(),Event()
    def hold_lock():
        with index.lock:
            started.set()
            release.wait(5)
    worker=Thread(target=hold_lock)
    worker.start()
    assert started.wait(5)
    original_import=builtins.__import__
    def loading_module(name,*args,**kwargs):
        if name=='qdrant_client.models':
            pytest.fail('A busy query must not wait on the cold vector import')
        return original_import(name,*args,**kwargs)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(builtins,'__import__',loading_module)
            with pytest.raises(rag.IndexBusy):
                index.search_chunks('TAILMARKER',[row()])
    finally:
        release.set()
        worker.join(timeout=5)
        index.close()


def test_remote_qdrant_creates_source_id_payload_index(tmp_path, monkeypatch):
    index = index_at(tmp_path)
    monkeypatch.setenv('QDRANT_URL', 'http://qdrant:6333')
    created = []
    monkeypatch.setattr(index.client, 'create_payload_index', lambda collection, **kwargs: created.append((collection, kwargs)))
    try:
        index.rebuild([row(1, answer='TAILMARKER')], 'books')
        assert len(created) == 1
        assert created[0][0] == index._collection('books')
        assert created[0][1]['field_name'] == 'source_id'
    finally:
        index.close()
