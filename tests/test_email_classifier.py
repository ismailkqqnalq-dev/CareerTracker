"""E-posta sınıflandırıcısı: ön işleme, veri sızıntısı koruması ve görülmemiş test setinde kalite tabanı."""

import pytest

from app.assistant.intent_model import fold_text
from app.email_insights.classifier import (
    CONFIDENCE_THRESHOLD,
    EMAIL_TYPES,
    classify_email,
    clean_email,
    load_examples,
)
from scripts.evaluate_email_classifier import evaluate


def test_clean_email_drops_quoted_replies_and_signatures():
    body = "\n".join([
        "Merhaba, sizi teknik mülakata davet etmek isteriz.",
        "",
        "Saygılarımızla,",
        "Ayşe Yılmaz - İK",
        "On Mon, 3 Nov 2026 at 10:00, Aday <aday@example.com> wrote:",
        "> Başvurumu ilettim, teşekkürler.",
    ])

    assert clean_email("Mülakat", body) == "Mülakat\nMerhaba, sizi teknik mülakata davet etmek isteriz."


def test_clean_email_skips_pasted_headers_before_the_message():
    body = "Kimden: ik@example.com\nKonu: Başvurunuz\nTarih: 3 Kasım\n\nBaşvurunuz bize ulaştı."

    assert clean_email("", body) == "Başvurunuz bize ulaştı."


def test_clean_email_keeps_a_long_line_that_starts_like_a_closing():
    body = "Teşekkürler, başvurunuzu aldık ve İK ekibimiz önümüzdeki günlerde inceleyecek."

    assert "başvurunuzu aldık" in clean_email("", body)


def test_training_and_test_sets_do_not_share_emails():
    train, _ = load_examples("emails_train.json")
    test, _ = load_examples("emails_test.json")

    assert not {fold_text(text) for text in train} & {fold_text(text) for text in test}


@pytest.mark.parametrize(
    ("subject", "body", "expected"),
    [
        ("Başvurunuz alındı", "Backend Developer başvurunuz bize ulaştı, inceleyip dönüş yapacağız.", "basvuru_alindi"),
        ("Görüşme daveti", "Sizinle bir ön görüşme yapmak istiyoruz, uygun olduğunuz saatleri paylaşır mısınız?", "mulakat_daveti"),
        ("Kodlama testi", "Süreç kapsamında online kodlama testini 3 gün içinde tamamlamanızı rica ederiz.", "degerlendirme"),
        ("İş teklifi", "Size pozisyon için iş teklifimizi sunmaktan memnuniyet duyarız, detaylar ektedir.", "teklif"),
        ("Başvurunuz hakkında", "Maalesef başka bir adayla ilerleme kararı aldık, başarılar dileriz.", "ret"),
        ("Yeni ilanlar", "Profiline uygun 10 yeni iş ilanı yayınlandı, hemen incele.", "diger"),
    ],
)
def test_classifies_typical_emails(subject, body, expected):
    assert classify_email(subject, body).intent == expected


def test_held_out_test_set_quality_floor():
    report = evaluate()

    # Ölçülen: doğruluk 0.95, 60 e-postada 2 yanlış öneri. Taban gerilemeyi yakalar,
    # veri setine küçük eklemelerde kırılmaz.
    assert report["test_size"] == 60
    assert report["accuracy"] >= 0.88
    assert report["wrong_suggestions"] <= 5
    assert report["confidence_threshold"] == CONFIDENCE_THRESHOLD
    assert set(report["per_type"]) == set(EMAIL_TYPES)
