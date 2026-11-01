"""Freeze weakly supervised query/document pairs from public DSpace metadata."""
import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from uuid import UUID

SEED=31


def plain(text):
    return ' '.join(re.sub(r'<[^>]+>',' ',str(text)).split())


def normalize(text):
    text=unicodedata.normalize('NFD',text.lower().replace('đ','d'))
    text=''.join(c for c in text if unicodedata.category(c)!='Mn')
    return ' '.join(re.findall(r'[a-z0-9]+',text))


def work_title(title):
    title=normalize(title)
    title=re.sub(r'\b(thuyet minh|ban ve|phu luc)\b',' ',title)
    return ' '.join(title.split())


def values(metadata,key):
    rows=metadata.get(key,[])
    if not isinstance(rows,list) or any(not isinstance(row,dict) or not isinstance(row.get('value'),str) for row in rows):
        raise ValueError('invalid metadata values')
    return [plain(row['value']) for row in rows if row['value'].strip()]


def prepare_records(snapshots):
    documents={}; rejected=[]
    for snapshot in snapshots:
        identifier=''
        try:
            row=snapshot.get('record',{})
            identifier=row.get('uuid','')
            if str(UUID(identifier))!=identifier or snapshot.get('source_url')!=f'https://thuvienso.ut.edu.vn/items/{identifier}':
                raise ValueError('invalid source identity')
            digest=hashlib.sha256(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
            if snapshot.get('sha256')!=digest:
                raise ValueError('snapshot integrity')
            if row.get('type')!='item' or row.get('inArchive') is not True or row.get('withdrawn') is not False or row.get('discoverable') is not True:
                raise ValueError('not a public archived record')
            if not isinstance(row.get('name'),str):
                raise ValueError('missing title')
            title=plain(row['name'])
            if not title or len(title)>500:
                raise ValueError('missing or oversized title')
            metadata=row.get('metadata',{})
            if not isinstance(metadata,dict):
                raise ValueError('invalid metadata')
            authors=[name for name in values(metadata,'dc.contributor.author') if not re.match(r'^(gvhd|huong dan|nguoi huong dan)\b',normalize(name))]
            subjects=values(metadata,'creativework.keywords')+values(metadata,'dc.subject')
            abstracts=values(metadata,'dc.description.abstract')
            text=title
            if subjects:
                text+='\nChủ đề: '+'; '.join(dict.fromkeys(subjects))
            if abstracts:
                text+='\nTóm tắt: '+' '.join(abstracts)
            documents[identifier]={'title':title,'text':text,'source_url':snapshot['source_url'],'authors':authors,
                'title_key':work_title(title)}
        except (ValueError,TypeError,AttributeError) as error:
            reason=str(error) if type(error) is ValueError and str(error) in {
                'invalid source identity','snapshot integrity','not a public archived record',
                'missing title','missing or oversized title','invalid metadata','invalid metadata values'} else 'invalid snapshot'
            rejected.append({'id':identifier if isinstance(identifier,str) else '', 'reason':reason})
    # Conservative title-family grouping prevents duplicated editions/parts crossing splits.
    groups={}
    for identifier,row in sorted(documents.items()):
        group=hashlib.sha256(row['title_key'].encode()).hexdigest()[:16]
        groups.setdefault(group,[]).append(identifier)
        row['group_id']=group
        del row['title_key']
    parents={group:group for group in groups}
    def component(group):
        while parents[group]!=group:
            parents[group]=parents[parents[group]]
            group=parents[group]
        return group
    owners={}
    for identifier,row in sorted(documents.items()):
        for author in row['authors']:
            author=normalize(author)
            if author in owners:
                left,right=component(row['group_id']),component(owners[author])
                parents[max(left,right)]=min(left,right)
            owners[author]=row['group_id']
    for row in documents.values():
        split_group=component(row['group_id'])
        bucket=int(hashlib.sha256(f'{SEED}:{split_group}'.encode()).hexdigest()[:8],16)%10
        row.update(split_group=split_group,split='test' if bucket==0 else 'dev' if bucket==1 else 'train')
    pairs=[]
    for group,identifiers in sorted(groups.items()):
        identifier=identifiers[0]; row=documents[identifier]
        words=row['title'].split()
        # Synthetic partial-title queries exercise abbreviation/no-accent lookup; not human qrels.
        selected=[word for index,word in enumerate(words) if index%4!=3] if len(words)>7 else words
        topic=' '.join(selected)
        if int(group[0],16)%2:
            topic=normalize(topic)
        query=('Tìm tài liệu về ' if row['split']=='train' else 'Tôi cần tài liệu liên quan đến ')+topic
        pairs.append({'query':query,'positive':row['text'],'document_id':identifier,'group_id':group,
            'split':row['split'],'relevant_ids':identifiers})
    return {'documents':dict(sorted(documents.items())),'groups':dict(sorted(groups.items())),
        'pairs':pairs,'rejected':sorted(rejected,key=lambda row:row['id'])}


def build_dataset(source,output):
    if (output/'manifest.json').exists():
        raise FileExistsError('Dataset already frozen; use a new output directory instead of replacing test data.')
    files=sorted(source.glob('*.json'))
    if not files:
        raise ValueError('No source snapshots found')
    snapshots=[json.loads(path.read_text(encoding='utf-8')) for path in files]
    data=prepare_records(snapshots)
    output.mkdir(parents=True,exist_ok=True)
    hashes={}
    for name in ('documents','pairs','groups','rejected'):
        raw=(json.dumps(data[name],ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        (output/f'{name}.json').write_bytes(raw)
        hashes[f'{name}.json']=hashlib.sha256(raw).hexdigest()
    source_hash=hashlib.sha256()
    for path in files:
        source_hash.update(path.name.encode()); source_hash.update(hashlib.sha256(path.read_bytes()).digest())
    report={'kind':'weak supervision from public metadata; synthetic development evaluation, not library acceptance',
        'seed':SEED,'source_files':len(files),'source_sha256':source_hash.hexdigest(),'documents':len(data['documents']),
        'work_groups':len(data['groups']),'rejected':len(data['rejected']),
        'pairs_by_split':dict(Counter(row['split'] for row in data['pairs'])),'files_sha256':hashes,
        'group_policy':'Accent/case-normalized title families plus shared-author components stay in one split; one canonical training pair per title family; relevance does not merge unrelated works by the same author',
        'limitations':['Synthetic partial-title queries; false-negative topic overlap remains possible',
            'Title-family grouping is conservative and not a bibliographic authority resolver',
            'All corpus documents may be retrieved at eval, but dev/test queries and positives are excluded from training pairs',
            'Encoder max_seq_length=128 is explicit; full raw metadata remains preserved separately']}
    (output/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def load_frozen_dataset(path):
    manifest=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    if set(manifest['files_sha256'])!={'documents.json','pairs.json','groups.json','rejected.json'}:
        raise ValueError('Unexpected frozen dataset files')
    for file,expected in manifest['files_sha256'].items():
        if hashlib.sha256((path/file).read_bytes()).hexdigest()!=expected:
            raise ValueError('Frozen dataset changed: '+file)
    documents=json.loads((path/'documents.json').read_text(encoding='utf-8'))
    pairs=json.loads((path/'pairs.json').read_text(encoding='utf-8'))
    splits={name:[row for row in pairs if row['split']==name] for name in ('train','dev','test')}
    for name,rows in splits.items():
        if len(rows)<2:
            raise ValueError('Need at least two work groups in '+name)
    components={name:{documents[row['document_id']]['split_group'] for row in rows} for name,rows in splits.items()}
    if components['train']&components['dev'] or components['train']&components['test'] or components['dev']&components['test']:
        raise ValueError('Split leakage found')
    return manifest,documents,splits


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build_dataset(args.source,args.output),ensure_ascii=False,indent=2))
