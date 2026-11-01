"""Hybrid retrieval over current library sources; excerpts remain source substrings."""
import hashlib

from .rag_service import chunk_text, keyword_search, tokens


def retrieve_knowledge(question, rows, vectors=None):
    ranked = keyword_search(question, rows)
    current = {row['id']:row for row in rows}
    query_tokens = tokens(question)
    excerpts = {}
    lexical = {row['id']:(row,score) for row,score in ranked}
    strong = bool(ranked and ranked[0][1]>=0.85)
    for row in rows:
        scored = []
        for text in chunk_text(row['answer']):
            overlap = len(query_tokens & tokens(text))
            coverage = overlap/max(len(query_tokens),1)
            score = coverage if overlap>=2 else 0
            scored.append((text,score))
            if not ranked and overlap>=2 and coverage>=0.5:
                lexical[row['id']] = (row,max(lexical.get(row['id'],(row,0))[1],0.45+coverage*0.35))
        excerpts[row['id']] = sorted(scored,key=lambda pair:-pair[1])
    ranked = sorted(lexical.values(),key=lambda pair:(-pair[1],pair[0]['id']))
    try:
        query_fits=len(question.encode('utf-8'))<=384
    except UnicodeEncodeError:
        query_fits=False
    semantic, degraded = [], bool(vectors is not None and not strong and not query_fits)
    if vectors is not None and not strong and query_fits:
        try:
            hits = vectors.search_chunks(question,rows)
            for hit in hits:
                row = current.get(hit['row']['id'])
                if row is not None and row==hit['row']:
                    semantic.append(hit)
        except Exception:
            degraded = True
    semantic_rows = {}
    for hit in semantic:
        row=hit['row']
        semantic_rows.setdefault(row['id'],(row,hit['score']))
    for hit in reversed(semantic):
        row=hit['row']
        # Metadata hits may rank a source, but only its actual answer is evidence.
        if hit['text'] in row['answer']:
            excerpts[row['id']].insert(0,(hit['text'],1))
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
        for text,_ in excerpts[row['id']]:
            if text in seen:
                continue
            seen.add(text)
            evidence.append({'source_id':row['id'],'text':text,
                             'chunk_id':hashlib.sha256(f"{row['id']}:{text}".encode()).hexdigest()})
            if len(seen)==2:
                break
    return {'ranked':ranked,'evidence':evidence,'method':method,'degraded':degraded}
