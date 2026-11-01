import hashlib
import json

import numpy as np
import pytest

from training.export_onnx import check_candidate, check_parity, file_hashes, verify_hashes


@pytest.fixture
def candidate(tmp_path):
    run=tmp_path/'run'; run.mkdir()
    dataset=tmp_path/'dataset'; dataset.mkdir()
    hashes={}
    for name in ('documents.json','pairs.json','groups.json','rejected.json'):
        (dataset/name).write_text('{}',encoding='utf-8')
        hashes[name]=hashlib.sha256((dataset/name).read_bytes()).hexdigest()
    (dataset/'manifest.json').write_text(json.dumps({'files_sha256':hashes}),encoding='utf-8')
    metrics={'smoke':False,'verdict':'WIN','delta':0.1,
        'dataset_manifest_sha256':hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest()}
    (run/'metrics.json').write_text(json.dumps(metrics),encoding='utf-8')
    return run,dataset,metrics


def test_valid_candidate_and_frozen_data_are_accepted(candidate):
    run,dataset,metrics=candidate
    assert check_candidate(run,dataset)==metrics


@pytest.mark.parametrize('delta',[float('nan'),float('inf'),-1,0.0049,True])
def test_invalid_or_nonfinite_win_is_rejected(candidate,delta):
    run,dataset,metrics=candidate
    metrics['delta']=delta
    (run/'metrics.json').write_text(json.dumps(metrics),encoding='utf-8')
    with pytest.raises(ValueError,match='Only a completed WIN'):
        check_candidate(run,dataset)


@pytest.mark.parametrize('name',['manifest.json','pairs.json'])
def test_changed_frozen_dataset_is_rejected(candidate,name):
    run,dataset,_=candidate
    (dataset/name).write_text('changed',encoding='utf-8')
    with pytest.raises(ValueError,match='manifest|Frozen dataset'):
        check_candidate(run,dataset)


def test_checkpoint_change_or_missing_file_is_rejected(tmp_path):
    (tmp_path/'weights').write_bytes(b'exact trained weights')
    hashes=file_hashes(tmp_path)
    verify_hashes(tmp_path,hashes)
    (tmp_path/'weights').write_bytes(b'other weights')
    with pytest.raises(ValueError,match='Artifact changed'):
        verify_hashes(tmp_path,hashes)
    (tmp_path/'weights').unlink()
    with pytest.raises(ValueError,match='Artifact changed'):
        verify_hashes(tmp_path,hashes)


def test_empty_checkpoint_cannot_pass_integrity_check(tmp_path):
    with pytest.raises(ValueError,match='Artifact changed'):
        verify_hashes(tmp_path,{})


def test_parity_requires_finite_fp32_normalized_matching_embeddings():
    reference=np.array([[1,0],[0,1]],dtype=np.float32)
    assert check_parity(reference,reference)['passed'] is True
    for changed in (reference[:1],reference.astype(np.float64),reference*2,
                    np.full_like(reference,np.nan),reference[:,::-1]):
        with pytest.raises(ValueError,match='parity'):
            check_parity(reference,changed)
