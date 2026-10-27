from scripts.evaluate_ocr import character_metrics, synthetic_cases, evaluate_cases


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


def test_dataset_is_deterministic_and_in_memory():
    first, second = synthetic_cases(), synthetic_cases()
    assert len(first) >= 10
    assert first == second
    assert all(isinstance(case["image"], bytes) for case in first)


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
