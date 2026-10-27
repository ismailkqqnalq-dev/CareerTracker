from scripts.evaluate_ocr import character_metrics, synthetic_cases


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
