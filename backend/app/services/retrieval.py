"""Hybrid retrieval over current library sources; excerpts remain source substrings."""
import hashlib
import math
from collections import Counter

from .rag_service import chunk_text, keyword_search, tokens


def retrieve_knowledge(question, rows, vectors=None, *, index_rows=None):
    ranked = keyword_search(question, rows)
    current = {row['id']:row for row in rows}
    query_tokens = tokens(question)
    lexical = {row['id']:(row,score) for row,score in ranked}
    strong = bool(ranked and ranked[0][1]>=0.85)
    # Supplement missing intent without making incidental body text compete with a complete FAQ match.
    if not strong:
        metadata = {row['id']:tokens(' '.join([row['question'],*row['aliases'],*row['keywords']])) for row in rows}
        answers = {row['id']:tokens(row['answer']) for row in rows}
        content = {row_id:terms | answers[row_id] for row_id,terms in metadata.items()}
        frequency = Counter(token for terms in content.values() for token in terms)
        missing = query_tokens-content[ranked[0][0]['id']] if ranked else query_tokens
        terms = missing & frequency.keys()
        weights = {token:1+math.log((len(rows)+1)/(frequency[token]+1)) for token in terms}
        total = sum(weights.values()) or 1
        for row in rows:
            row_id = row['id']
            if row_id not in lexical and len(terms & content[row_id])>=2:
                intent = sum(weights[token] for token in terms & metadata[row_id])/total
                body = sum(weights[token] for token in terms & answers[row_id])/total
                score = min(0.84,0.2+intent*0.5+body*0.4)
                if score>=0.45:
                    lexical[row_id] = (row,score)
        ranked = sorted(lexical.values(),key=lambda pair:(-pair[1],pair[0]['id']))
    try:
        query_fits=len(question.encode('utf-8'))<=384
    except UnicodeEncodeError:
        query_fits=False
    semantic, degraded = [], bool(vectors is not None and not strong and not query_fits)
    if vectors is not None and not strong and query_fits:
        try:
            hits = (vectors.search_chunks(question,rows) if index_rows is None else
                    vectors.search_chunks(question,index_rows,source_ids=set(current)))
            for hit in hits:
                row = current.get(hit['row']['id'])
                if row is not None and row==hit['row']:
                    semantic.append(hit)
        except Exception:
            degraded = True
    semantic_rows = {}
    semantic_excerpts = {}
    for hit in semantic:
        row=hit['row']
        semantic_rows.setdefault(row['id'],(row,hit['score']))
        # Metadata hits may rank a source, but only its actual answer is evidence.
        if hit['text'] in row['answer']:
            semantic_excerpts.setdefault(row['id'],[]).append(hit['text'])
    method='hybrid' if ranked and semantic_rows else 'semantic' if semantic_rows else 'keyword' if ranked else 'none'
    if semantic_rows:
        fused, scores = {}, {}
        for channel in (ranked,list(semantic_rows.values())):
            for rank,(row,score) in enumerate(channel,1):
                fused[row['id']]=fused.get(row['id'],0)+1/(60+rank)
                scores[row['id']]=max(scores.get(row['id'],0),score)
        ranked=[(current[row_id],scores[row_id]) for row_id in sorted(fused,key=lambda row_id:(-fused[row_id],row_id))]
    evidence=[]
    for row,_ in ranked[:3]:
        seen=set()
        if len(row['answer'].encode('utf-8'))<=1400:
            available=[row['answer']]
        else:
            scored=[]
            for text in chunk_text(row['answer']):
                overlap=len(query_tokens & tokens(text))
                scored.append((text,overlap if overlap>=2 else 0))
            available=semantic_excerpts.get(row['id'],[])+[text for text,_ in sorted(scored,key=lambda pair:-pair[1])]
        for text in available:
            if text in seen:
                continue
            seen.add(text)
            evidence.append({'source_id':row['id'],'text':text,
                             'chunk_id':hashlib.sha256(f"{row['id']}:{text}".encode()).hexdigest()})
            if len(seen)==2:
                break
    return {'ranked':ranked,'evidence':evidence,'method':method,'degraded':degraded}
