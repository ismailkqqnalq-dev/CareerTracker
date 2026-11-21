"""Asistan için niyet sınıflandırıcısı: harf n-gram'lı Multinomial Naive Bayes.

Model, `intents_train.json` içindeki örnek cümlelerden her niyet için özellik
(harf parçası ve kelime) sıklıklarını öğrenir. Tahmin, her niyetin log
olasılığını hesaplayıp en yükseğini seçer; güven, bu olasılıkların softmax'ıdır.
Bağımlılık yoktur ve eğitim veri setinin küçüklüğü sayesinde milisaniyeler sürer.
"""

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
NGRAM_SIZES = (2, 3, 4)
SMOOTHING = 0.5
FALLBACK_INTENT = "anlasilamadi"
# Naive Bayes güvenleri 1'e yığılır. Eşik yalnızca eğitim setinde leave-one-out ile
# seçildi: 0.98'de doğruluk korunurken yanlış niyete verilen cevaplar yarıya iner.
# Test seti seçime karışmadı; `scripts/evaluate_assistant_intents.py` raporlar.
CONFIDENCE_THRESHOLD = 0.98

_TURKISH_FOLD = str.maketrans({
    "İ": "i", "I": "i", "ı": "i",
    "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c",
    "Â": "a", "â": "a", "Î": "i", "î": "i", "Û": "u", "û": "u",
})
_NON_WORD = re.compile(r"[^a-z0-9]+")


def fold_text(text: str) -> str:
    """Türkçe harfleri ASCII'ye katlar, küçük harfe çevirir, noktalamayı boşluğa indirir."""
    folded = text.translate(_TURKISH_FOLD).lower()
    return _NON_WORD.sub(" ", folded).strip()


def features(text: str) -> Counter:
    """Kelimeler ve kelime sınırlarıyla doldurulmuş harf n-gram'ları."""
    counts: Counter = Counter()
    for word in fold_text(text).split():
        counts[f"w:{word}"] += 1
        padded = f" {word} "
        for size in NGRAM_SIZES:
            for start in range(len(padded) - size + 1):
                counts[f"c:{padded[start:start + size]}"] += 1
    return counts


@dataclass(frozen=True)
class Prediction:
    intent: str
    confidence: float


class NaiveBayesIntentModel:
    def fit(self, sentences: list[str], labels: list[str]) -> "NaiveBayesIntentModel":
        if not sentences or len(sentences) != len(labels):
            raise ValueError("sentences and labels must be non-empty and the same length")
        self.intents = sorted(set(labels))
        feature_counts = {intent: Counter() for intent in self.intents}
        label_counts = Counter(labels)
        for sentence, label in zip(sentences, labels):
            feature_counts[label].update(features(sentence))

        self.vocabulary = set().union(*feature_counts.values())
        vocabulary_size = len(self.vocabulary)
        self.log_priors = {
            intent: math.log(label_counts[intent] / len(labels)) for intent in self.intents
        }
        self.log_likelihoods = {}
        self.log_unseen = {}
        for intent in self.intents:
            total = sum(feature_counts[intent].values()) + SMOOTHING * vocabulary_size
            self.log_likelihoods[intent] = {
                feature: math.log((count + SMOOTHING) / total)
                for feature, count in feature_counts[intent].items()
            }
            self.log_unseen[intent] = math.log(SMOOTHING / total)
        return self

    def predict(self, text: str) -> Prediction:
        # Eğitimde hiç görülmemiş özellikler her niyete aynı payı eklerdi; atlanır.
        observed = {
            feature: count for feature, count in features(text).items() if feature in self.vocabulary
        }
        scores = {}
        for intent in self.intents:
            likelihoods = self.log_likelihoods[intent]
            unseen = self.log_unseen[intent]
            scores[intent] = self.log_priors[intent] + sum(
                count * likelihoods.get(feature, unseen) for feature, count in observed.items()
            )
        best = max(scores, key=scores.get)
        # Softmax'ı en yüksek skora göre kaydırarak taşmayı önler.
        exponentials = {intent: math.exp(score - scores[best]) for intent, score in scores.items()}
        return Prediction(intent=best, confidence=1 / sum(exponentials.values()))


def load_examples(file_name: str) -> tuple[list[str], list[str]]:
    data = json.loads((DATA_DIR / file_name).read_text(encoding="utf-8"))
    sentences, labels = [], []
    for intent, examples in data.items():
        sentences.extend(examples)
        labels.extend([intent] * len(examples))
    return sentences, labels


@lru_cache(maxsize=1)
def trained_model() -> NaiveBayesIntentModel:
    """Eğitim setinden bir kez eğitilir ve süreç boyunca yeniden kullanılır."""
    return NaiveBayesIntentModel().fit(*load_examples("intents_train.json"))


def classify(text: str, model: NaiveBayesIntentModel | None = None) -> Prediction:
    """Eşiğin altındaki tahminleri, yanlış cevap vermek yerine anlaşılamadı sayar."""
    prediction = (model or trained_model()).predict(text)
    if prediction.confidence < CONFIDENCE_THRESHOLD:
        return Prediction(intent=FALLBACK_INTENT, confidence=prediction.confidence)
    return prediction
