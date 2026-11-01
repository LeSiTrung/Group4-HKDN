import hashlib
import json
from types import SimpleNamespace

import pytest

from app.services.rag_service import VectorIndex


@pytest.fixture
def export(tmp_path):
    directory=tmp_path/'onnx'/'model'; directory.mkdir(parents=True)
    files={'model.onnx':b'measured weights','config.json':json.dumps({'hidden_size':384}).encode(),
        'tokenizer_config.json':json.dumps({'model_max_length':128,'max_length':128}).encode(),
        'tokenizer.json':json.dumps({'truncation':{'max_length':128}}).encode()}
    for name,value in files.items():
        (directory/name).write_bytes(value)
    parity={'passed':True,'sample_texts':50,'embedding_shape':[50,384],'max_abs_error':0.000001,
        'min_cosine':0.999999,'dtype':'float32'}
    report={'passed':True,'max_seq_length':128,'pooling':'attention-mask mean','normalized':True,
        'fastembed':parity,'onnx_batches':[{**parity,'batch_size':n} for n in (1,3,8)],
        'artifact_sha256':{name:hashlib.sha256(value).hexdigest() for name,value in files.items()}}
    path=tmp_path/'onnx-parity.json'
    path.write_text(json.dumps(report),encoding='utf-8')
    return path,directory,report


def test_default_model_identity_and_collection_are_preserved(tmp_path,monkeypatch):
    monkeypatch.delenv('EMBEDDING_EXPORT',raising=False)
    monkeypatch.delenv('EMBEDDING_MODEL',raising=False)
    index=VectorIndex(SimpleNamespace(data_dir=tmp_path))
    assert index.model_name=='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    assert index.collection=='knowledge_chunks_v1_39897b1e723b'


@pytest.mark.parametrize('asset',['model.onnx','tokenizer.json'])
def test_local_export_identity_is_content_bound_and_does_not_expose_paths(export,tmp_path,monkeypatch,asset):
    path,directory,report=export
    monkeypatch.setenv('EMBEDDING_EXPORT',str(path))
    first=VectorIndex(SimpleNamespace(data_dir=tmp_path/'runtime'))
    assert first.model_name.startswith('local/uth-minilm-')
    assert str(tmp_path) not in json.dumps(first.status())
    (directory/asset).write_bytes((directory/asset).read_bytes()+b'\n')
    report['artifact_sha256'][asset]=hashlib.sha256((directory/asset).read_bytes()).hexdigest()
    path.write_text(json.dumps(report),encoding='utf-8')
    second=VectorIndex(SimpleNamespace(data_dir=tmp_path/'runtime'))
    assert first.collection!=second.collection


@pytest.mark.parametrize('change',['weights','tokenizer','unverified','bad_parity','bad_settings','missing','extra_tokens'])
def test_invalid_export_is_rejected_before_index_is_opened(export,tmp_path,monkeypatch,change):
    path,directory,report=export
    if change=='weights': (directory/'model.onnx').write_bytes(b'tampered')
    elif change=='tokenizer': (directory/'tokenizer.json').write_bytes(b'tampered')
    elif change=='missing': (directory/'model.onnx').unlink()
    elif change=='extra_tokens': (directory/'special_tokens_map.json').write_text('{"additional_special_tokens":["python"]}',encoding='utf-8')
    elif change=='unverified': report['fastembed']['passed']=False
    elif change=='bad_parity': report['fastembed']['max_abs_error']=float('nan')
    elif change=='bad_settings': report['max_seq_length']=512
    path.write_text(json.dumps(report),encoding='utf-8')
    monkeypatch.setenv('EMBEDDING_EXPORT',str(path))
    with pytest.raises(ValueError,match='embedding export'):
        VectorIndex(SimpleNamespace(data_dir=tmp_path/'runtime'))
    assert not (tmp_path/'runtime'/'vectors').exists()


@pytest.mark.parametrize('tamper',['tokenizer','extra_tokens'])
def test_export_is_revalidated_and_loaded_offline_with_no_registry_fallback(export,tmp_path,monkeypatch,tamper):
    import fastembed
    path,directory,_=export
    calls=[]
    class FakeEmbedding:
        @classmethod
        def list_supported_models(cls): return []
        @classmethod
        def add_custom_model(cls,**kwargs): calls.append(('register',kwargs))
        def __init__(self,**kwargs): calls.append(('load',kwargs))
    monkeypatch.setattr(fastembed,'TextEmbedding',FakeEmbedding)
    monkeypatch.setenv('EMBEDDING_EXPORT',str(path))
    index=VectorIndex(SimpleNamespace(data_dir=tmp_path/'runtime'))
    index.client=SimpleNamespace(close=lambda:None)
    try:
        index._init()
        options=calls[-1][1]
        assert options['specific_model_path']==str(directory.resolve())
        assert options['local_files_only'] is True and options['cuda'] is False
        assert options['providers']==['CPUExecutionProvider']
        index.model=None
        if tamper=='tokenizer':
            (directory/'tokenizer.json').write_bytes(b'changed after constructor')
        else:
            (directory/'special_tokens_map.json').write_text('{"additional_special_tokens":["python"]}',encoding='utf-8')
        with pytest.raises(ValueError,match='embedding export'):
            index._init()
        assert len(calls)==2
    finally:
        index.close()
