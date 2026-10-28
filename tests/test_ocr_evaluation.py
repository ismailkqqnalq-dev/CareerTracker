from app.skill_catalog import SKILL_CATALOG
from scripts.evaluate_ocr import character_metrics, synthetic_cases, evaluate_cases, term_recall


def test_alignment_records_substitution_deletion_insertion_and_all_letters():
    metrics = character_metrics("ğüç", "gü")
    assert metrics["edit_distance"] == 2
    assert metrics["turkish_correct"] == 1
    assert metrics["turkish_total"] == 3
    assert metrics["confusions"]["ğ"] == {"g": 1}
    assert metrics["confusions"]["ç"] == {"<deleted>": 1}
    assert "İ" in metrics["confusions"]
    assert character_metrics("a", "ab")["insertions"] == {"b": 1}


def test_folded_metric_uses_existing_normalize_text():
    metrics = character_metrics("İ ı I", "i i i")
    assert metrics["cer"] > 0
    assert metrics["folded_cer"] == 0
    assert character_metrics("ş", "s")["folded_cer"] == 1


def test_metrics_empty_input_and_identity():
    assert character_metrics("", "")["cer"] == 0
    assert character_metrics("abc", "abc")["cer"] == 0


def test_term_recall_normalizes_output_and_catalog_terms():
    metrics = term_recall("PYTHON, FastAPI and C#", ("Python", "FastAPI", "PostgreSQL", "C#"))
    assert metrics == {
        "expected": 4,
        "found": 3,
        "recall": 0.75,
        "matched": ["Python", "FastAPI", "C#"],
        "missing": ["PostgreSQL"],
    }


def test_dataset_is_deterministic_and_in_memory():
    first, second = synthetic_cases(), synthetic_cases()
    assert len(first) >= 10
    assert first == second
    assert all(isinstance(case["image"], bytes) for case in first)
    catalog_case = next(case for case in first if case["id"] == "tr-catalog-terms")
    assert catalog_case["skill_terms"] == tuple(item["name"] for item in SKILL_CATALOG)
    assert catalog_case["reference"].count("\n") == 4
    assert catalog_case["width"] < 1200


def test_evaluation_with_fake_motor_reports_errors_timings_and_confusions():
    class EmptyMotor:
        def recognize(self, image):
            return ""
    report = evaluate_cases(EmptyMotor(), synthetic_cases()[:2], repeats=2)
    assert len(report["images"]) == 2
    assert report["summary"]["cer"] == 1
    assert "ğ" in report["summary"]["confusions"]
    for row in report["images"]:
        assert row["error_code"] == "empty_ocr_result"
        assert len(row["warm_runs"]) == 2
        assert row["first_pass"]["wall_s"] >= 0


def test_evaluation_summarizes_term_recall_and_top_confusions():
    class PartialMotor:
        def recognize(self, image):
            return "Python FastAPI C#"

    case = next(case for case in synthetic_cases() if case["id"] == "tr-catalog-terms")
    report = evaluate_cases(PartialMotor(), [case], repeats=1)
    summary = report["summary"]
    assert summary["term_recall"]["expected"] == len(SKILL_CATALOG)
    assert summary["term_recall"]["found"] == 3
    assert summary["term_recall"]["recall"] == 3 / len(SKILL_CATALOG)
    assert 0 < len(summary["top_confusions"]) <= 10
    assert summary["top_confusions"] == sorted(
        summary["top_confusions"], key=lambda item: (-item["count"], item["expected"], item["observed"])
    )
