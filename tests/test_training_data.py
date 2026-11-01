import json
import hashlib
from pathlib import Path

import pytest

from training.prepare_data import build_dataset, load_frozen_dataset, prepare_records


def snapshot(identifier, title, author='Nguyễn A', **changes):
    record={'uuid':identifier,'name':title,'type':'item','inArchive':True,'withdrawn':False,'discoverable':True,
        'metadata':{'dc.contributor.author':[{'value':author}],
                    'creativework.keywords':[{'value':'Cầu đường'}]}}
    record.update(changes)
    digest=hashlib.sha256(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    return {'source_url':f'https://thuvienso.ut.edu.vn/items/{identifier}', 'record':record,'sha256':digest}


def test_duplicate_works_share_split_and_relevance_without_duplicate_training_positives():
    rows=[snapshot('00000000-0000-0000-0000-000000000001','Thiết kế cầu bê tông (Thuyết minh)'),
          snapshot('00000000-0000-0000-0000-000000000002','Thiet ke cau be tong (Ban ve)')]
    result=prepare_records(rows)
    assert len(result['groups'])==1
    group=next(iter(result['groups'].values()))
    assert len(group)==2
    assignments={row['split'] for row in result['documents'].values()}
    assert len(assignments)==1
    assert len(result['pairs'])==1


def test_withdrawn_or_foreign_source_is_not_training_content():
    rows=[snapshot('00000000-0000-0000-0000-000000000001','Public title'),
          snapshot('00000000-0000-0000-0000-000000000002','Withdrawn secret',withdrawn=True),
          {**snapshot('00000000-0000-0000-0000-000000000003','Foreign source'),'source_url':'https://evil.example/item'}]
    result=prepare_records(rows)
    assert len(result['documents'])==1 and len(result['rejected'])==2
    assert 'Withdrawn secret' not in json.dumps(result['documents'])


def test_missing_title_or_malformed_record_is_not_fabricated_as_training_text():
    rows=[snapshot('00000000-0000-0000-0000-000000000001',None),{'record':[]},
        {'record':{'uuid':None}}]
    result=prepare_records(rows)
    assert not result['documents'] and len(result['rejected'])==3


@pytest.mark.parametrize('change',[{'discoverable':None},{'type':'collection'},{'metadata':[]},
    {'metadata':{'dc.contributor.author':'not an array'}}])
def test_nonpublic_or_malformed_metadata_is_rejected_even_with_matching_hash(change):
    row=snapshot('00000000-0000-0000-0000-000000000001','Valid title',**change)
    result=prepare_records([row])
    assert not result['documents'] and len(result['rejected'])==1


def test_snapshot_integrity_is_verified_before_training_text_is_built():
    row=snapshot('00000000-0000-0000-0000-000000000001','Original title')
    row['record']['name']='Tampered title'
    result=prepare_records([row])
    assert not result['documents'] and len(result['rejected'])==1


def test_source_order_does_not_change_group_splits_or_queries():
    rows=[snapshot(f'00000000-0000-0000-0000-{n:012d}',f'Chủ đề nghiên cứu độc lập {n}',f'Tác giả {n}') for n in range(40)]
    first=prepare_records(rows)
    second=prepare_records(list(reversed(rows)))
    assert first==second
    groups_by_split={name:set() for name in ('train','dev','test')}
    for row in first['documents'].values():
        groups_by_split[row['split']].add(row['group_id'])
    assert groups_by_split['train'] and groups_by_split['dev'] and groups_by_split['test']
    assert not groups_by_split['train']&groups_by_split['test']
    assert not groups_by_split['train']&groups_by_split['dev']


def test_shared_author_is_kept_in_one_split_without_making_unrelated_works_relevant():
    rows=[snapshot('00000000-0000-0000-0000-000000000001','Bridge Design'),
          snapshot('00000000-0000-0000-0000-000000000002','Library Systems')]
    result=prepare_records(rows)
    assert len(result['groups'])==2
    assert len({row['split'] for row in result['documents'].values()})==1
    assert all(len(pair['relevant_ids'])==1 for pair in result['pairs'])


def test_build_freezes_manifest_and_refuses_accidental_overwrite(tmp_path):
    source=tmp_path/'records'; source.mkdir()
    for n in range(3):
        (source/f'{n}.json').write_text(json.dumps(snapshot(f'00000000-0000-0000-0000-{n:012d}',f'Tài liệu {n}')),encoding='utf-8')
    output=tmp_path/'dataset'
    report=build_dataset(source,output)
    assert report['documents']==3 and report['kind'].startswith('weak supervision')
    before=(output/'manifest.json').read_bytes()
    with pytest.raises(FileExistsError):
        build_dataset(source,output)
    assert (output/'manifest.json').read_bytes()==before


def test_changed_evaluation_pairs_are_rejected_before_training(tmp_path):
    source=tmp_path/'records'; source.mkdir()
    for n in range(100):
        (source/f'{n}.json').write_text(json.dumps(snapshot(f'00000000-0000-0000-0000-{n:012d}',f'Independent document {n}',f'Author {n}')),encoding='utf-8')
    output=tmp_path/'dataset'
    build_dataset(source,output)
    load_frozen_dataset(output)
    (output/'pairs.json').write_text('[]',encoding='utf-8')
    with pytest.raises(ValueError,match='Frozen dataset changed'):
        load_frozen_dataset(output)
