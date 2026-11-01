import math
import pytest

from scripts.evaluate_vector_index import retrieval_metrics


def test_vector_metrics_use_rank_and_all_relevant_documents():
    score=retrieval_metrics({'a'},['wrong','a'])
    assert score['hit_at1']==0 and score['hit_at5']==1
    assert score['mrr_at5']==0.5
    assert score['ndcg_at5']==pytest.approx(1/math.log2(3))
    assert retrieval_metrics({'a','b'},['a','b'])['ndcg_at5']==1
    assert retrieval_metrics({'a','b'},['a'])['recall_at5']==0.5
    assert all(value==0 for value in retrieval_metrics({'a'},[]).values())
