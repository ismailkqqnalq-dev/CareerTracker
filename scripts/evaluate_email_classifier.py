"""İşe alım e-postası sınıflandırıcısını, eğitimde görülmemiş test setinde ölçer.

Çalıştırma: python -m scripts.evaluate_email_classifier
Çıktı JSON'dur: doğruluk, tür bazında precision/recall, karışıklık matrisi,
yanlış öneri sayısı (eşiği geçip yanlış türe gidenler) ve hatalar.
"""

import json
import sys

from app.email_insights.classifier import (
    CONFIDENCE_THRESHOLD,
    EMAIL_TYPES,
    FALLBACK_TYPE,
    classify_text,
    load_examples,
    trained_model,
)


def evaluate() -> dict:
    model = trained_model()
    texts, expected = load_examples("emails_test.json")
    predicted = [classify_text(text, model).intent for text in texts]

    confusion = {actual: {guess: 0 for guess in EMAIL_TYPES} for actual in EMAIL_TYPES}
    for actual, guess in zip(expected, predicted):
        confusion[actual][guess] += 1

    per_type = {}
    for email_type in EMAIL_TYPES:
        true_positive = confusion[email_type][email_type]
        predicted_count = sum(confusion[actual][email_type] for actual in EMAIL_TYPES)
        actual_count = sum(confusion[email_type].values())
        per_type[email_type] = {
            "precision": round(true_positive / predicted_count, 4) if predicted_count else None,
            "recall": round(true_positive / actual_count, 4) if actual_count else None,
            "support": actual_count,
        }

    correct = sum(actual == guess for actual, guess in zip(expected, predicted))
    return {
        "model": "multinomial naive bayes (shared with the assistant), character 2-4 grams and words",
        "dataset": "synthetic only; hand-written Turkish and English recruiting emails",
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "train_size": len(load_examples("emails_train.json")[0]),
        "test_size": len(texts),
        "accuracy": round(correct / len(texts), 4),
        "wrong_suggestions": sum(
            actual != guess and guess != FALLBACK_TYPE for actual, guess in zip(expected, predicted)
        ),
        "per_type": per_type,
        "confusion": confusion,
        "errors": [
            {"text": text[:160], "expected": actual, "predicted": guess}
            for text, actual, guess in zip(texts, expected, predicted)
            if actual != guess
        ],
        "limitations": [
            "Synthetic emails are cleaner and more formulaic than real recruiting emails.",
            "Scores are regression signals, not estimates of accuracy on real inboxes.",
            "Suggestions are only produced for emails matched to one of the user's opportunities.",
        ],
    }


if __name__ == "__main__":
    json.dump(evaluate(), sys.stdout, ensure_ascii=True, indent=2)
    print()
