from scripts.evaluate_job_text_analysis import evaluate


REQUIRED_SYNTHETIC_CASES = {
    "tr-clean",
    "en-clean",
    "symbols-and-short-name",
    "ocr-like-noise",
    "turkish-ascii-ocr-folding",
    "turkish-concept-aliases",
    "folded-headings-and-sections",
    "ambiguous-short-terms",
    "phrase-overlap",
    "unknown-terms",
}


def test_evaluator_covers_core_synthetic_scenarios():
    report = evaluate()
    cases = report["cases"]
    case_ids = [case["id"] for case in cases]

    assert len(case_ids) == len(set(case_ids))
    assert REQUIRED_SYNTHETIC_CASES <= set(case_ids)
    assert "synthetic only" in report["dataset"]
    assert set(report["aggregate_micro"]) >= {
        "true_positive",
        "false_positive",
        "false_negative",
        "precision",
        "recall",
        "f1",
    }


def test_evaluator_exposes_false_positives_and_unresolved_terms():
    report = evaluate()
    cases = {case["id"]: case for case in report["cases"]}

    assert report["aggregate_micro"]["false_positive"] == 0

    ambiguous = cases["ambiguous-short-terms"]
    assert ambiguous["predicted"] == ["C", "Go", "R"]
    assert ambiguous["scores"]["false_positive"] == 0
    assert "DefinitelyUncataloguedTerm" in cases["unknown-terms"]["catalog_unresolved_terms"]


def test_evaluator_uses_only_an_in_memory_database(monkeypatch):
    import scripts.evaluate_job_text_analysis as evaluator

    create_engine = evaluator.create_database_engine
    database_urls = []

    def capture_database_url(database_url):
        database_urls.append(database_url)
        return create_engine(database_url)

    monkeypatch.setattr(evaluator, "create_database_engine", capture_database_url)

    evaluator.evaluate()

    assert database_urls == ["sqlite:///:memory:"]
