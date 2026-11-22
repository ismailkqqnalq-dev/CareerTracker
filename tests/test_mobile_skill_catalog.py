"""Android/mobil ilanlarında geçen beceriler: Türkçe yazımlar ve bağlam isteyen belirsiz kelimeler."""

from app.services.job_text_analysis_service import analyze_job_text
from app.services.skill_catalog_service import seed_skill_catalog
from app.services.skill_normalizer import find_skill


ANDROID_POSTING = """Aranan Nitelikler
- Nesne tabanlı geliştirme, design patterns ve mobil cihazlar için sistem mimarileri konularını çok iyi bilen,
- Thread ve bellek yönetimi, IPC ve servisler gibi Android detayları konusunda uzman,
- Junit ve Espresso gibi Unit testing framework'leri ile çalışmış,
- SQL ve Java bilgisine sahip"""


def skill_names(db_session, text):
    seed_skill_catalog(db_session)
    return {skill["name"] for skill in analyze_job_text(db_session, user_id=1, text=text)["skills"]}


def test_android_posting_skills_are_extracted_as_required(db_session):
    seed_skill_catalog(db_session)
    result = analyze_job_text(db_session, user_id=1, text=ANDROID_POSTING)

    found = {skill["name"]: skill["occurrences"][0]["section"] for skill in result["skills"]}
    assert set(found) == {
        "Android", "Object-Oriented Programming", "Design Patterns", "Multithreading",
        "Memory Management", "Inter-Process Communication", "JUnit", "Espresso",
        "Unit Testing", "SQL", "Java",
    }
    assert set(found.values()) == {"required"}


def test_turkish_and_english_spellings_resolve_to_the_same_skill(db_session):
    seed_skill_catalog(db_session)
    expected = {
        "oop": "Object-Oriented Programming",
        "nesne yönelimli programlama": "Object-Oriented Programming",
        "tasarım desenleri": "Design Patterns",
        "eşzamanlı programlama": "Multithreading",
        "hafıza yönetimi": "Memory Management",
        "süreçler arası iletişim": "Inter-Process Communication",
        "birim testi": "Unit Testing",
        "mobil uygulama mimarisi": "Mobile Architecture",
        "android sdk": "Android",
    }

    resolved = {alias: getattr(find_skill(db_session, alias), "name", None) for alias in expected}

    assert resolved == expected


def test_espresso_as_coffee_is_not_a_skill(db_session):
    assert "Espresso" not in skill_names(db_session, "Ofisimizde her sabah taze espresso ve kahvaltı ikram ediyoruz.")


def test_espresso_next_to_android_testing_is_a_skill(db_session):
    assert "Espresso" in skill_names(db_session, "Android UI testleri için Espresso deneyimi")


def test_a_social_media_thread_is_not_multithreading(db_session):
    assert "Multithreading" not in skill_names(db_session, "Kampanya duyurusunu sosyal medyada bir thread olarak paylaşacak")


def test_mobile_architecture_is_extracted_from_its_common_phrases(db_session):
    names = skill_names(db_session, "Kotlin ile mobil uygulama mimarisi ve Clean Code prensipleri")

    assert "Mobile Architecture" in names
