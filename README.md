# CareerTracker

[![Tests](https://github.com/ismailkqqnalq-dev/CareerTracker/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/ismailkqqnalq-dev/CareerTracker/actions/workflows/tests.yml)

İş, staj ve freelance fırsatlarını takip etmek için geliştirilen bir kariyer CRM'idir. FastAPI ve SQLAlchemy REST API'si, SQLite ile yerel ve PostgreSQL ile Docker ortamında çalışabilir. `frontend/` dizininde beceri önerileri için sınırlı bir React MVP'si bulunur; tam CRM arayüzü değildir.
## Vizyon

CareerTracker, başvuru takibinden öteye geçmeyi hedefliyor: **Career Tracker AI**. Farklı platformlardan (LinkedIn, Indeed, Upwork, Fiverr) gelen iş ve freelance fırsatlarını tek yerde toplayıp ilanlardan yapılandırılmış veri çıkaran, kullanıcının becerileriyle karşılaştıran ve zamanla piyasa trendlerini analiz eden bir kariyer istihbarat platformu.

Proje aşamalı geliştirilir: önce sağlam bir backend, sonra her yapay zekâ bileşeni için önce basit bir baseline, ardından gelişmiş yöntem ve ölçülebilir karşılaştırma.
## Özellikler

- Fırsat/başvuru kayıtları için CRUD işlemleri
- Şirketlerde tanışılan kişiler için CRUD işlemleri
- Görüşme ve diğer aktiviteleri kaydetme
- Takip görevleri ve hatırlatmalar
- Başvuru istatistiklerini sunan dashboard
- Fırsatları CSV olarak dışa aktarma (Türkçe karakter desteği)
- Alembic veritabanı migration'ları
- GitHub Actions ile otomatik test çalıştırma
- Ortak seed skill kataloğu, kullanıcıya özel skill/alias yönetimi ve normalize edilmiş adla skill bulma
- Fırsatlara skill bağlama ve bağlı skill'leri listeleme
- Kullanıcıya özel bekleyen beceri önerilerini gözden geçirip mevcut katalogla eşleştirme (`frontend/` MVP arayüzü)

## Teknoloji

- Python 3.11+
- FastAPI, Pydantic
- SQLAlchemy
- SQLite / PostgreSQL
- Alembic
- pytest, HTTPX
- Docker Compose

## API

Uygulama çalışırken interaktif dokümantasyon: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Kimlik doğrulaması gereken endpoint'lerde `Authorization: Bearer <token>` gönder. “Opsiyonel” endpoint'ler tokensız ortak katalogla sınırlıdır.

| Alan | Metot ve yol | Giriş | Açıklama |
|---|---|---|---|
| Hesap | `POST /auth/register` | Hayır | Hesap oluşturur |
| Oturum | `POST /auth/token` | Hayır | E-posta (`username` alanında) ve parola ile JWT alır |
| Oturum | `GET /auth/me` | Evet | Oturum açmış kullanıcıyı döndürür |
| Skill kataloğu | `GET /skills` | Opsiyonel | Ortak katalogu; oturum varsa kullanıcının kendi skill'lerini de listeler |
| Skill kataloğu | `POST /skills` | Evet | Yalnızca giriş yapan kullanıcıya özel skill oluşturur |
| Skill çözümleme | `GET /skills/resolve?name=...` | Opsiyonel | Görünür skill'i ad veya alias ile bulur |
| Skill alias | `POST /skills/{skill_id}/aliases` | Evet | Kişisel alias ekler; ortak alias kaydını değiştirmez |
| Beceri önerileri | `POST /skills/suggestions` | Evet | Tanınmayan skill adı için öneri oluşturur veya mevcut öneriyi döndürür |
| Beceri önerileri | `GET /skills/suggestions` | Evet | Kullanıcının önerilerini listeler; `status` ile süzülebilir |
| Beceri önerisi | `PATCH /skills/suggestions/{suggestion_id}` | Evet | Öneriyi görünür bir skill ile kişisel olarak eşleştirir |
| Adaylar | `GET /skills/suggestions/{suggestion_id}/candidates` | Evet | Bekleyen öneri için benzer adları sıralar |
| Profil skill'leri | `GET, POST /users/me/skills` | Evet | Profil skill'lerini listeler veya ekler |
| Profil skill'i | `PATCH, DELETE /users/me/skills/{user_skill_id}` | Evet | Profil kaydını günceller veya siler |
| Fırsat skill'leri | `POST, GET /opportunities/{opportunity_id}/skills` | Evet | Fırsata skill bağlar veya bağlı skill'leri listeler |
| Fırsat skill eşleşmesi | `GET /opportunities/{opportunity_id}/skill-match` | Evet | Profilde bulunan ve eksik skill'leri karşılaştırır |
| Fırsatlar | `GET, POST /opportunities`; `GET, PATCH, DELETE /opportunities/{id}` | Evet | Kullanıcının fırsatlarını yönetir |
| Kişiler | `GET, POST /contacts`; `GET, PATCH, DELETE /contacts/{id}` | Evet | Kullanıcının kişilerini yönetir |
| Aktiviteler | `GET, POST /activities`; `GET, PATCH, DELETE /activities/{id}` | Evet | Kullanıcının aktivitelerini yönetir |
| Görevler | `GET, POST /tasks`; `GET, PATCH, DELETE /tasks/{id}` | Evet | Kullanıcının görevlerini yönetir |
| Dashboard | `GET /dashboard` | Evet | Kullanıcının fırsat istatistiklerini döndürür |
| CSV | `GET /opportunities/export` | Evet | Kullanıcının fırsatlarını CSV olarak indirir |

### Beceri API hata kodları

JSON hata gövdesindeki sabit kodlar:

| `error_code` | Endpoint | Anlamı |
|---|---|---|
| `skill_not_found` | `GET /skills/resolve` | Görünür katalogda bu adla skill bulunamadı (404) |
| `skill_already_recognized` | `POST /skills/suggestions` | Skill zaten tanınıyor; öneri yerine katalogdaki skill kullanılmalı (409) |
| `opportunity_not_found` | `POST, GET /opportunities/{opportunity_id}/skills`; `GET /opportunities/{opportunity_id}/skill-match` | Fırsat bulunamadı veya kullanıcıya ait değil (404) |
| `unknown_skill` | `POST /opportunities/{opportunity_id}/skills` | Skill tanınmadı (404); öneri kaydedildiyse gövdede `suggestion_id` de bulunur |

## Yerel kurulum

Python 3.11 veya üzeri gerekir.

```bash
git clone https://github.com/ismailkqqnalq-dev/CareerTracker.git
cd CareerTracker
python -m venv .venv
```

Sanal ortamı etkinleştir:

- **Windows (PowerShell):** `.\.venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source .venv/bin/activate`

Bağımlılıkları kur ve çalıştır:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

`.env.example` dosyasını `.env` olarak kopyala (Windows: `Copy-Item .env.example .env`, macOS/Linux: `cp .env.example .env`), sonra:

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

## Docker ile PostgreSQL

Docker ve Docker Compose kurulu olmalı. Depoyu klonladıktan sonra:

```powershell
Copy-Item .env.example .env
```

Docker Compose içindeki PostgreSQL servisine bağlanmak için `.env` dosyasındaki `DATABASE_URL` değerini şu şekilde ayarla:

```text
DATABASE_URL=postgresql://careertracker:careertracker@db:5432/careertracker
```

Ardından uygulama ve veritabanını başlat, migration'ları uygula:

```powershell
docker compose up --build -d
docker compose exec app alembic upgrade head
```

API: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Servisleri durdurmak için `docker compose down` kullan. Veritabanı verileri `postgres_data` volume'unda saklanır.

## Beceri öneri arayüzü (MVP)

Arayüz beceri önerisi akışının MVP'sidir: kayıt ve giriş, tanınmayan beceri önerisi
gönderme, benzer adayları görüntüleme ve kullanıcı onayıyla eşleştirme. Fırsat,
kişi, aktivite ve görevleri yönetmek için tam CRM arayüzü içermez.

### Katalog ve kişisel eşleştirme

- Ortak katalog seed ile yönetilir ve uygulamanın kullanıcıya açık API'sinde salt
  okunurdur. `POST /skills` ortak katalogu değiştirmez; giriş yapan kişiye özel bir
  skill oluşturur.
- `POST /skills/{skill_id}/aliases`, ayrı `PersonalSkillAlias` kaydı ekleyerek
  yalnızca o kullanıcının çözümlemesini etkiler; ortak `SkillAliases` kayıtlarını
  değiştirmez.
- Tanınmayan beceri `POST /skills/suggestions` ile kullanıcıya özel öneri olur.
  `PATCH /skills/suggestions/{suggestion_id}` ile verilen karar
  `SkillSuggestion.resolved_skill_id` üzerinde kişisel olarak saklanır; genel
  kataloğa alias eklenmez.
- Giriş yapan kullanıcı ortak katalogu ve kendi skill/alias kayıtlarını görür.
  Tokensız `GET /skills` ve `GET /skills/resolve` yalnızca ortak kayıtları gösterir.
  Başka kullanıcının özel kayıtları çözümleme ve aday listelerinde görünmez.

### Aday sıralaması ve eşleştirme

Aday sıralaması `difflib.SequenceMatcher` metin benzerliği ve token örtüşmesi kullanan
kural tabanlı bir heuristiktir. Skor yazım/metin benzerliğini gösterir; ML sonucu,
doğruluk olasılığı veya aynı beceri olduğuna dair güven ölçüsü değildir. `C#` ve
`C++` gibi sembollü adlar için yazım eşlemeleri bulunsa da skor yine benzerliktir.
`skill-match` endpoint'i de ML kullanmaz: fırsat becerilerini kullanıcının profil
beceri ID'leriyle karşılaştırır ve eşleşen/eksik becerileri döndürür.

### Yerel frontend

Önce API'yi depo kökünden başlat:

```powershell
python -m uvicorn app.main:app --reload
```

Ardından ayrı terminalde frontend komutlarını çalıştır:

```powershell
cd frontend
npm ci
npm test
npm run build
npm run dev
```

Vite'ın verdiği yerel adresi aç. Geliştirme proxy'si `/api` isteklerini varsayılan
olarak `http://127.0.0.1:8000` adresine yönlendirir. Başka API adresi için Vite'ı
başlatmadan önce `CAREERTRACKER_API_URL` ortam değişkenini ayarla.

## Testler

Backend testleri ve migration kontrolleri için:

```powershell
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m alembic check
python -m pytest -q
```

Frontend testleri Vitest ile çalışır. `cd frontend` sonrasında `npm ci`, `npm test`
ve `npm run build` komutlarını çalıştır. GitHub Actions, Pull Request'lerde ve `main` push'larında
backend testlerini, migration kontrollerini, frontend testlerini ve frontend build'ini
çalıştırır.

## Migration oluşturma

Boş bir veritabanını kurmak için `python -m alembic upgrade head` yeterlidir. İlk migration
fırsat, kişi, aktivite ve görev tablolarını; sonraki migration skill tablolarını
oluşturur. `init_db.py`, Alembic geçmişini kaydetmediği için normal kurulum adımı değildir.

İlk migration önceden boştu ve bu bootstrap düzeltmesiyle tamamlandı. Mevcut
tabloları doğru olan ve `d0fe616da34f` veya `b3b24fd6d532` revision'ında kayıtlı
veritabanlarında ilk migration tekrar çalışmaz. Bu durumdaki veriler korunur.
Eski boş migration ile kurulmuş, temel tabloları eksik bir veritabanı bu değişiklikle
otomatik onarılmaz. `init_db.py` ile kurulmuş fakat Alembic revision'ı olmayan
veritabanlarında da önce yedek alınmalı ve şema/revision eşleşmesi incelenmelidir;
körlemesine `stamp head` uygulanmamalıdır.

`alembic downgrade base` artık temel tabloları da siler; yalnızca atılabilir test
veritabanlarında kullanılmalıdır. CI, SQLite ve PostgreSQL'de temiz kurulumu ve
model/şema uyumunu; ayrıca PostgreSQL'de geri alma ve tekrar kurulumu kontrol eder.

Model değişikliğinden sonra yeni migration üretip gözden geçir:

```powershell
python -m alembic revision --autogenerate -m "migration açıklaması"
python -m alembic upgrade head
```

## Proje yapısı

```text
app/
├── core/          # Ortak yapılandırmalar
├── database/      # SQLAlchemy engine ve oturum
├── models/        # Veritabanı modelleri
├── repositories/  # Veritabanı sorguları
├── routes/        # FastAPI endpoint'leri
├── schemas/       # Pydantic istek/yanıt şemaları
├── services/      # Uygulama iş mantığı
└── main.py        # FastAPI uygulaması
migrations/        # Alembic migration dosyaları
tests/             # pytest testleri
```

## Yol Haritası

- **Tamamlandı — Faz 1:** Fırsat, kişi, aktivite ve görev backend CRUD'ları.
- **Tamamlandı — Faz 2:** Dashboard, CSV dışa aktarma, PostgreSQL/Docker, Alembic ve CI.
- **Tamamlandı — Faz 2.5:** Skill modelleri ve API'si, seed katalogu, kişisel skill/alias ve öneri eşleştirme temeli.
- **Başlamadı — Faz 3:** OCR ile ilan görüntülerinden metin çıkarma.
- **Planlandı — Faz 4:** İlan metninden yapılandırılmış bilgi çıkarımı ve ölçüm.
- **Kısmi — Faz 5:** Normalizasyon, seed alias'ları, kişisel alias'lar ve metin benzerliğine dayalı aday sıralaması var; kapsamlı beceri normalizasyonu tamamlanmadı.
- **Kısmi — Faz 6:** Kullanıcı skill profili ve fırsat skill-match/gap endpoint'i var; tam eşleştirme ürünü ve arayüzü tamamlanmadı.
- **Planlandı — Faz 7–10:** Analitik, semantic similarity, makine öğrenmesi ve deep learning/computer vision çalışmaları.
- **Kısmi — Faz 11:** JWT kimlik doğrulaması ve beceri önerileri için React MVP'si var; deployment ve tam CRM arayüzü tamamlanmadı.

Fazlar doğrusal ilerlemez. Faz 5, 6 ve 11'in bazı altyapı parçaları OCR/NLP başlamadan önce geliştirildi; bu fazlar tamamlandı anlamına gelmez.

## Durum

Faz 1, 2 ve 2.5 tamamlandı. Faz 3 OCR henüz başlamadı. Faz 5, 6 ve 11'den bazı
parçalar erken teslim edildi ancak bu fazların bütünü tamamlanmış değildir. Bugünkü
arayüz beceri önerilerinin gözden geçirilmesi ve eşleştirilmesiyle sınırlıdır.

## Bilinen sınırlar

- Beceri önerisini reddetmek için endpoint veya arayüz akışı yoktur.
- `PATCH /skills/suggestions/{suggestion_id}` kabul edilmiş öneriyi yeniden
  eşleştirebilir.
- Kabul edilmiş önerinin hedef skill'i silinirse foreign key `resolved_skill_id`'yi
  boş bırakır; önerinin durumu `accepted` kalır. Bu davranış testle belgelenmiştir.
- Aday sıralaması yazım/metin benzerliği heuristiğidir. Kısa veya sembollü adlarda
  skorlar anlamsal doğruluk anlamına gelmez.
## Lisans

[MIT](LICENSE)
