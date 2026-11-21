"""Niyet modeli: Türkçe katlama, öğrenme davranışı ve görülmemiş test setindeki kalite tabanı."""

import pytest

from app.assistant.intent_model import (
    CONFIDENCE_THRESHOLD,
    FALLBACK_INTENT,
    NaiveBayesIntentModel,
    classify,
    fold_text,
    load_examples,
    trained_model,
)
from scripts.evaluate_assistant_intents import evaluate


def test_fold_text_folds_turkish_letters_and_punctuation():
    assert fold_text("Trendyol'daki BAŞVURUM, İyi mi?") == "trendyol daki basvurum iyi mi"


def test_model_learns_from_examples_and_reports_a_probability():
    model = NaiveBayesIntentModel().fit(
        ["bugün görevim ne", "görevlerimi göster", "kaç başvurum var", "toplam başvuru sayım"],
        ["gorev", "gorev", "sayi", "sayi"],
    )

    prediction = model.predict("bugünkü görevler")

    assert prediction.intent == "gorev"
    assert 0.5 < prediction.confidence <= 1.0


def test_model_rejects_mismatched_training_data():
    with pytest.raises(ValueError):
        NaiveBayesIntentModel().fit(["tek cümle"], [])


def test_training_and_test_sets_do_not_share_sentences():
    train, _ = load_examples("intents_train.json")
    test, _ = load_examples("intents_test.json")

    assert not {fold_text(s) for s in train} & {fold_text(s) for s in test}


@pytest.mark.parametrize(
    ("message", "intent"),
    [
        ("Trendyol başvurum ne alemde", "basvuru_durumu"),
        ("bugun ne yapmaliyim", "bugun_ne_var"),
        ("Kimden ses çıkmadı", "takip_gereken"),
        ("Hangi becerileri geliştirmeliyim", "beceri_acigi"),
        ("Kaç başvurum var", "genel_durum"),
        ("Merhaba", "yardim"),
    ],
)
def test_classifies_core_questions(message, intent):
    assert classify(message).intent == intent


def test_low_confidence_predictions_fall_back_to_not_understood():
    prediction = classify("qwe zxc")

    assert prediction.intent == FALLBACK_INTENT


def test_held_out_test_set_quality_floor():
    report = evaluate()

    # Ölçülen değerler: doğruluk 0.886, 70 cümlede 6 yanlış cevap. Taban, gerilemeyi
    # yakalayacak ama veri setine küçük eklemelerde kırılmayacak kadar aşağıda.
    assert report["test_size"] == 70
    assert report["accuracy"] >= 0.85
    assert report["wrong_answers"] <= 8
    assert report["confidence_threshold"] == CONFIDENCE_THRESHOLD
    assert set(report["per_intent"]) == set(trained_model().intents)
