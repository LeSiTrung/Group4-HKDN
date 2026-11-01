import pytest

from scripts.evaluate_catalog import metrics


def test_catalog_metrics_measure_returned_precision_rank_and_missing_results():
    result=metrics({'a','b'},['wrong','b','a'])
    assert result['hit_at1']==0 and result['mrr_at5']==0.5
    assert result['returned_precision_at5']==pytest.approx(2/3)
    assert result['recall_at20']==1
    assert metrics({'a'},[])['recall_at20']==0


def test_empty_gold_measures_abstention_separately():
    assert metrics(set(),[])=={'empty_correct':True}
    assert metrics(set(),['wrong'])=={'empty_correct':False}
