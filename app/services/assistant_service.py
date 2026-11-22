"""Kural tabanlı asistan cevapları: niyeti eğitilmiş model bulur, cevabı bu modül kayıtlardan üretir.

Hiçbir cevap uydurulmaz; her cümle kullanıcının kendi kayıtlarından ya da
mevcut servislerin hesapladığı sayılardan gelir. Mesajlar saklanmaz.
"""

from collections import Counter
from datetime import date, datetime

from sqlalchemy import or_

from app.assistant.intent_model import classify, fold_text
from app.models.email_insights import EmailSuggestion
from app.models.opportunity import Opportunity
from app.models.opportunity_skills import OpportunitySkill
from app.models.skills import Skill, UserSkill
from app.models.tasks import Task
from app.services import agenda_service, opportunity_service
from app.services.agenda_service import ACTIVE_STATUSES, _status_key

MAX_ITEMS = 5
MIN_COMPANY_TOKEN_LENGTH = 3
SMALL_SAMPLE = 5
DEFAULT_SUGGESTIONS = [
    "Bugün ne yapmalıyım?",
    "Kimden ses çıkmadı?",
    "Hangi becerileri geliştirmeliyim?",
    "Kaç başvurum var?",
]
# Şirket adlarında ayırt edici olmayan ekler; eşleşmede kullanılmaz.
_GENERIC_COMPANY_WORDS = {
    "as", "a", "s", "ltd", "sti", "anonim", "sirketi", "holding", "inc", "llc", "gmbh",
    "teknoloji", "teknolojileri", "yazilim", "bilisim", "sistemleri", "group", "grup",
}
_ACTIVE_KEYS = {_status_key(status) for status in ACTIVE_STATUSES}
# E-posta sınıflandırıcısının bulduğu türler, asistan cevabında kısa adlarıyla.
_EMAIL_TYPE_LABELS = {
    "basvuru_alindi": "başvuru alındı bildirimi",
    "mulakat_daveti": "mülakat daveti",
    "degerlendirme": "test/ödev daveti",
    "teklif": "iş teklifi",
    "ret": "olumsuz dönüş",
}


def _as_date(value):
    return value.date() if isinstance(value, datetime) else value


def _display(value) -> str:
    value = _as_date(value)
    return value.strftime("%d.%m.%Y") if value else "tarih yok"


def _days_ago(value, today: date) -> str:
    value = _as_date(value)
    if not value:
        return "Son temas tarihi yok"
    days = (today - value).days
    return "Son temas: bugün" if days <= 0 else f"Son temas: {days} gün önce"


def _company_key(company: str | None) -> str | None:
    """Şirket adının ilk ayırt edici kelimesi; eşleşmenin dayandığı anahtar."""
    for token in fold_text(company or "").split():
        if len(token) >= MIN_COMPANY_TOKEN_LENGTH and token not in _GENERIC_COMPANY_WORDS:
            return token
    return None


def _mentioned_opportunities(db, user_id: int, message: str) -> list[Opportunity]:
    # Türkçe ekler kelimenin sonuna gelir: "trendyoldan" kelimesi "trendyol" ile başlar.
    words = fold_text(message).split()
    matches = []
    for opportunity in db.query(Opportunity).filter(Opportunity.user_id == user_id).all():
        key = _company_key(opportunity.company)
        if key and any(word.startswith(key) for word in words):
            matches.append(opportunity)
    return sorted(matches, key=lambda item: item.id, reverse=True)


def _reply(text, items=(), suggestions=()) -> dict:
    return {"reply": text, "items": list(items), "suggestions": list(suggestions)}


def _opportunity_status(db, user_id: int, message: str, today: date) -> dict:
    matches = _mentioned_opportunities(db, user_id, message)
    if not matches:
        recent = (
            db.query(Opportunity)
            .filter(Opportunity.user_id == user_id)
            .order_by(Opportunity.id.desc())
            .limit(3)
            .all()
        )
        if not recent:
            return _reply("Henüz kayıtlı bir başvurun yok. Başvurular ekranından ilk başvurunu ekleyebilirsin.")
        return _reply(
            "Mesajındaki şirketle eşleşen bir başvurun bulamadım. Son başvurularından birini sorabilirsin:",
            suggestions=[f"{item.company} başvurum ne alemde?" for item in recent if item.company],
        )

    shown = matches[:MAX_ITEMS]
    open_tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
            Task.opportunity_id.in_([item.id for item in shown]),
            or_(Task.is_completed.is_(False), Task.is_completed.is_(None)),
        )
        .order_by(Task.due_date.is_(None), Task.due_date, Task.id)
        .all()
    )
    first_task = {}
    for task in open_tasks:
        first_task.setdefault(task.opportunity_id, task)

    items = []
    for opportunity in shown:
        details = [
            f"Durum: {opportunity.status or 'belirtilmemiş'}",
            f"Başvuru tarihi: {_display(opportunity.application_date)}",
            _days_ago(opportunity.last_contact_date, today),
        ]
        if opportunity.next_action:
            details.append(f"Sıradaki adım: {opportunity.next_action}")
        task = first_task.get(opportunity.id)
        if task:
            due = f" (son tarih {_display(task.due_date)})" if task.due_date else ""
            details.append(f"Açık görev: {task.description}{due}")
        # İki model birlikte: e-posta sınıflandırıcısının bu başvuru için bulduğu son olay.
        email = (
            db.query(EmailSuggestion)
            .filter(EmailSuggestion.user_id == user_id, EmailSuggestion.opportunity_id == opportunity.id)
            .order_by(EmailSuggestion.received_at.desc(), EmailSuggestion.id.desc())
            .first()
        )
        if email and email.email_type in _EMAIL_TYPE_LABELS:
            details.append(f"Son e-posta ({_display(email.received_at)}): {_EMAIL_TYPE_LABELS[email.email_type]}")
        items.append({"title": f"{opportunity.company} · {opportunity.position}", "details": details})

    count = len(matches)
    text = "Başvurunun son durumu:" if count == 1 else f"Bu şirketle eşleşen {count} başvurun var:"
    if count > MAX_ITEMS:
        text += f" En yeni {MAX_ITEMS} tanesini gösteriyorum."
    return _reply(text, items)


def _today_tasks(db, user_id: int, message: str, today: date) -> dict:
    tasks = agenda_service.get_agenda(db, user_id=user_id, today=today)["tasks"]
    if not tasks:
        return _reply("Gecikmiş ya da önümüzdeki 7 gün içinde son tarihi olan açık görevin yok.")

    overdue = sum(task["due_date"] < today for task in tasks)
    due_today = sum(task["due_date"] == today for task in tasks)
    items = []
    for task in tasks[:MAX_ITEMS]:
        if task["due_date"] < today:
            when = f"Gecikti ({_display(task['due_date'])})"
        elif task["due_date"] == today:
            when = "Bugün"
        else:
            when = _display(task["due_date"])
        items.append({"title": task["description"], "details": [when, f"{task['company']} · {task['position']}"]})

    text = f"{len(tasks)} açık görevin var: {overdue} gecikmiş, {due_today} bugün, {len(tasks) - overdue - due_today} bu hafta."
    if len(tasks) > MAX_ITEMS:
        text += f" İlk {MAX_ITEMS} tanesi:"
    return _reply(text, items)


def _follow_ups(db, user_id: int, message: str, today: date) -> dict:
    follow_ups = agenda_service.get_agenda(db, user_id=user_id, today=today)["follow_ups"]
    if not follow_ups:
        return _reply("Takip zamanı gelen başvurun yok; süreçteki başvurularının hepsiyle son 7 gün içinde temas kurmuşsun.")

    items = []
    for item in follow_ups[:MAX_ITEMS]:
        contact = (
            f"{item['days_since_contact']} gündür temas yok"
            if item["days_since_contact"] is not None
            else "İletişim tarihi yok"
        )
        details = [f"Durum: {item['status']}", contact]
        if item["next_action"]:
            details.append(f"Sıradaki adım: {item['next_action']}")
        items.append({"title": f"{item['company']} · {item['position']}", "details": details})

    text = f"Süreçte olup 7 günden uzun süredir temas kurmadığın {len(follow_ups)} başvuru var:"
    return _reply(text, items)


def _skill_gaps(db, user_id: int, message: str, today: date) -> dict:
    rows = (
        db.query(OpportunitySkill.opportunity_id, Skill.id, Skill.name)
        .join(Opportunity, Opportunity.id == OpportunitySkill.opportunity_id)
        .join(Skill, Skill.id == OpportunitySkill.skill_id)
        .filter(Opportunity.user_id == user_id)
        .all()
    )
    if not rows:
        return _reply(
            "Başvurularında henüz kayıtlı beceri yok, bu yüzden bir açık hesaplayamıyorum. "
            "İlan analizinden başvuru kaydettiğinde ilanın becerileri de eklenir."
        )

    opportunity_count = len({opportunity_id for opportunity_id, _, _ in rows})
    demand = Counter((skill_id, name) for _, skill_id, name in rows)
    profile = {skill_id for (skill_id,) in db.query(UserSkill.skill_id).filter(UserSkill.user_id == user_id)}
    missing = sorted(
        ((count, name) for (skill_id, name), count in demand.items() if skill_id not in profile),
        key=lambda item: (-item[0], item[1].casefold()),
    )
    if not missing:
        return _reply(f"Beceri bilgisi olan {opportunity_count} başvurunda istenen becerilerin hepsi profilinde kayıtlı.")

    items = [
        {"title": name, "details": [f"{count} / {opportunity_count} başvuruda isteniyor"]}
        for count, name in missing[:MAX_ITEMS]
    ]
    text = f"Beceri bilgisi olan {opportunity_count} başvurunda en çok istenen ama profilinde olmayan beceriler:"
    if opportunity_count < SMALL_SAMPLE:
        text += " (Henüz az başvuru var; bunu kesin sonuç değil, bir eğilim olarak düşün.)"
    return _reply(text, items)


def _overview(db, user_id: int, message: str, today: date) -> dict:
    stats = opportunity_service.get_dashboard_stats(db, user_id=user_id)
    total = stats["total_opportunities"]
    if not total:
        return _reply("Henüz kayıtlı bir başvurun yok.")

    by_status = {status or "Belirtilmemiş": count for status, count in stats["by_status"].items()}
    active = sum(count for status, count in by_status.items() if _status_key(status) in _ACTIVE_KEYS)
    items = [
        {"title": status, "details": [f"{count} başvuru"]}
        for status, count in sorted(by_status.items(), key=lambda item: (-item[1], item[0]))
    ]
    text = (
        f"Toplam {total} başvurun var: {active} tanesi hâlâ süreçte, "
        f"{stats['offer_count']} teklif, {stats['interview_count']} görüşme aşamasında."
    )
    return _reply(text, items)


def _help(db, user_id: int, message: str, today: date) -> dict:
    return _reply(
        "Ben CareerTracker asistanıyım. Kayıtlarına bakarak şunları cevaplayabilirim:",
        [
            {"title": "Başvuru durumu", "details": ["Örnek: \"Trendyol başvurum ne alemde?\""]},
            {"title": "Bugünün işleri", "details": ["Geciken ve bu haftaki görevlerin"]},
            {"title": "Takip edilmesi gerekenler", "details": ["Uzun süredir ses çıkmayan başvurular"]},
            {"title": "Beceri açığı", "details": ["İlanlarda istenip profilinde olmayan beceriler"]},
            {"title": "Genel durum", "details": ["Başvuru sayıların ve aşamaları"]},
        ],
        DEFAULT_SUGGESTIONS,
    )


def _not_understood(db, user_id: int, message: str, today: date) -> dict:
    return _reply(
        "Bunu anlayamadım. Başvuruların, görevlerin ve becerilerinle ilgili sorular sorabilirsin.",
        suggestions=DEFAULT_SUGGESTIONS,
    )


HANDLERS = {
    "basvuru_durumu": _opportunity_status,
    "bugun_ne_var": _today_tasks,
    "takip_gereken": _follow_ups,
    "beceri_acigi": _skill_gaps,
    "genel_durum": _overview,
    "yardim": _help,
    "anlasilamadi": _not_understood,
}


def answer(db, user_id: int, message: str, today: date) -> dict:
    prediction = classify(message)
    reply = HANDLERS[prediction.intent](db, user_id, message, today)
    return {"intent": prediction.intent, "confidence": round(prediction.confidence, 4), **reply}
