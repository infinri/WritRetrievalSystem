"""Hand-scored examples keep experiment reporting honest."""
import math
import pytest
from writ_retrieval.evaluation.full_corpus import scores, metrics
from writ_retrieval.evaluation.compare import paired


def test_hand_scored_primary_secondary_and_cutoff():
    result = scores(["secondary", "unjudged", "primary"], ["primary", "secondary"])
    assert result["hit5"] == 1 and result["rr5"] == 1/3
    assert result["ndcg10"] == pytest.approx(2.5 / (3 + 1/math.log2(3)))
    assert scores(["a", "b", "c", "d", "e", "primary"], ["primary"])["rr5"] == 0
    assert scores(["a", "b", "c", "d", "e", "primary"], ["primary"])["rr10"] == 1/6


def test_abstentions_count_as_zero_not_removed_from_denominator():
    miss = {**scores([], ["primary"]), "mode": "abstained"}
    hit = {**scores(["primary"], ["primary"]), "mode": "standard"}
    assert metrics([miss, hit])["rr5"] == .5
    assert metrics([miss, hit])["abstentions"] == 1


def test_paired_report_includes_losses_and_ignores_only_timings():
    left = [{"id": "1", "cohort": "coding", "rr5": 1, "uncached_ms": 2}, {"id":"2", "cohort":"coding", "rr5":0, "uncached_ms":2}]
    right = [{"id":"1", "cohort":"coding", "rr5":0, "uncached_ms":9}, {"id":"2", "cohort":"coding", "rr5":0, "uncached_ms":9}]
    result = paired(left, right)
    assert result["regressed_rr5"][0]["id"] == "1"
    assert [r["id"] for r in result["unchanged_rr5"]] == ["2"]
    assert result["changed_outputs"] == ["1"]
