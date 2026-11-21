"""Asistan niyet modelini, eğitimde görülmemiş test setinde ölçer.

Çalıştırma: python -m scripts.evaluate_assistant_intents
Çıktı JSON'dur: genel doğruluk, niyet bazında precision/recall, karışıklık
matrisi, yanlış cevap sayısı (eşiği geçip yanlış niyete gidenler) ve hatalar.
"""

import json
import sys

from app.assistant.intent_model import (
    CONFIDENCE_THRESHOLD,
    FALLBACK_INTENT,
    classify,
    load_examples,
    trained_model,
)


def evaluate() -> dict:
    model = trained_model()
    sentences, expected = load_examples("intents_test.json")
    predicted = [classify(sentence, model).intent for sentence in sentences]
    intents = model.intents

    confusion = {actual: {guess: 0 for guess in intents} for actual in intents}
    for actual, guess in zip(expected, predicted):
        confusion[actual][guess] += 1

    per_intent = {}
    for intent in intents:
        true_positive = confusion[intent][intent]
        predicted_count = sum(confusion[actual][intent] for actual in intents)
        actual_count = sum(confusion[intent].values())
        per_intent[intent] = {
            "precision": round(true_positive / predicted_count, 4) if predicted_count else None,
            "recall": round(true_positive / actual_count, 4) if actual_count else None,
            "support": actual_count,
        }

    correct = sum(actual == guess for actual, guess in zip(expected, predicted))
    return {
        "model": "multinomial naive bayes, character 2-4 grams and words",
        "dataset": "synthetic only; hand-written Turkish example questions",
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "train_size": len(load_examples("intents_train.json")[0]),
        "test_size": len(sentences),
        "accuracy": round(correct / len(sentences), 4),
        "wrong_answers": sum(
            actual != guess and guess != FALLBACK_INTENT
            for actual, guess in zip(expected, predicted)
        ),
        "per_intent": per_intent,
        "confusion": confusion,
        "errors": [
            {"text": sentence, "expected": actual, "predicted": guess}
            for sentence, actual, guess in zip(sentences, expected, predicted)
            if actual != guess
        ],
        "limitations": [
            "Small hand-written synthetic sample; real user questions will be more varied.",
            "Off-topic questions are open-ended; the threshold limits wrong answers but cannot catch all.",
        ],
    }


if __name__ == "__main__":
    # ensure_ascii keeps Windows legacy consoles from failing on Turkish text.
    json.dump(evaluate(), sys.stdout, ensure_ascii=True, indent=2)
    print()
