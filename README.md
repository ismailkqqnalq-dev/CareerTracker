# CareerTracker

[![Tests](https://github.com/ismailkqqnalq-dev/CareerTracker/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/ismailkqqnalq-dev/CareerTracker/actions/workflows/tests.yml)

İş, staj ve freelance başvurularını tek yerde takip etmek için geliştirilen kişisel bir kariyer CRM'inin REST API'si. FastAPI ve SQLAlchemy ile yazılmıştır; SQLite ile yerel, PostgreSQL ile Docker ortamında çalışabilir.
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
- Skill oluşturma, alias ekleme ve normalize edilmiş adla skill bulma
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

| Alan | Metot ve yol | Açıklama |
|---|---|---|
| Fırsatlar | `/opportunities` — GET, POST | Fırsatları listele veya ekle |
| Fırsat | `/opportunities/{id}` — GET, PATCH, DELETE | Detay, güncelleme, silme |
| Kişiler | `/contacts` — GET, POST | Kişileri listele veya ekle |
| Kişi | `/contacts/{id}` — GET, PATCH, DELETE | Detay, güncelleme, silme |
| Aktiviteler | `/activities` — GET, POST | Aktiviteleri listele veya ekle |
| Aktivite | `/activities/{id}` — GET, PATCH, DELETE | Detay, güncelleme, silme |
| Görevler | `/tasks` — GET, POST | Görevleri listele veya ekle |
| Görev | `/tasks/{id}` — GET, PATCH, DELETE | Detay, güncelleme, silme |
| Dashboard | `/dashboard` — GET | Başvuru istatistikleri |
| CSV | `/opportunities/export` — GET | Fırsatları CSV olarak indir |
| Skill | `/skills` — POST | Skill oluştur (201); tekrar eden ad için 409 |
| Skill çözümleme | `/skills/resolve?name=postgres` — GET | Ad veya alias ile bul; bulunamazsa 404 |
| Skill alias | `/skills/{skill_id}/aliases` — POST | Skill'e alternatif ad ekle |
| Fırsat skill'leri | `/opportunities/{opportunity_id}/skills` — POST, GET | Skill bağla veya bağlı skill'leri listele |

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
alembic upgrade head
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

### Kişisel katalog yazımları

`POST /skills` giriş yapan kullanıcıya özel bir beceri oluşturur.
`POST /skills/{skill_id}/aliases` yalnızca o kullanıcıya ait alternatif isim ekler;
ortak `SkillAliases` kayıtlarını değiştirmez. Hedef beceri ortak katalogdan veya
kullanıcının kendi becerilerinden olmalıdır; başka kullanıcıya ait ID için 404 döner.
`GET /skills` ve `/skills/resolve`, token ile ortak katalog + kendi kayıtlarını,
tokensız yalnızca ortak kataloğu kullanır. Aday sıralaması, profil ekleme ve
öneri eşleştirmesi de aynı görünürlük sınırını korur.

Kişisel öneri eşleştirmeleri (`SkillSuggestion.resolved_skill_id`) ayrı kalır.
Çözümlemede önce kabul edilmiş kişisel eşleştirme, sonra kişisel alias, sonra
ortak alias kullanılır. Ortak isimle çakışan kişisel alias yalnızca sahibini etkiler.
Kabul edilmiş kişisel eşleştirmeyle aynı isimde alias ekleme 409 döner.

Ortak katalog yalnızca sunucu tarafındaki seed işlemiyle yönetilir. Seed, kişisel
kayıtları sahiplenmez veya değiştirmez. Önceden oluşturulan kayıtların sahibi
saklanmadığı için `a91e73c208bf` migration'ı bunları ortak kayıt olarak korur;
geçmiş yazımları geriye dönük kişiselleştirmez. Yeni kişisel beceri/alias varken
downgrade durdurulur; kişisel veriyi silmez veya ortak veriye dönüştürmez.

API'yi çalışır durumda bıraktıktan sonra ikinci terminalde React arayüzünü başlat:

```powershell
cd frontend
npm install
npm run dev
```

Vite'ın gösterdiği yerel adresi aç. Arayüz, `/api` isteklerini `http://127.0.0.1:8000` adresindeki FastAPI uygulamasına proxy eder. Eşleştirme kullanıcı tarafından onaylanır ve yalnızca o kullanıcıya kaydedilir; genel skill kataloğuna otomatik alias eklenmez. Ayrıntılar için [`frontend/README.md`](frontend/README.md) dosyasına bak.

## Testler

Geliştirme bağımlılıklarını kurup testleri çalıştır:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

GitHub Actions, `main` branch'ine yapılan push ve Pull Request'lerde testleri otomatik çalıştırır.

## Migration oluşturma

Boş bir veritabanını kurmak için `alembic upgrade head` yeterlidir. İlk migration
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
alembic revision --autogenerate -m "migration açıklaması"
alembic upgrade head
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

- [x] **Faz 1 - Temel uygulama:** Fırsat, kişi, aktivite ve görev CRUD'ları, testler
- [x] **Faz 2 - Altyapı:** Dashboard, CSV dışa aktarma, PostgreSQL + Docker, Alembic, CI
- [x] **Faz 2.5 - Skill temeli:** Skill/alias modelleri, temel normalization, skill API'si, fırsat-skill bağlama ve listeleme, API testleri
- [ ] **Faz 3 - OCR:** İlan ekran görüntüsünden metin çıkarma (image preprocessing ile)
- [ ] **Faz 4 - NLP:** İlan metninden beceri, rol ve gereksinim çıkarımı (precision/recall/F1 ile ölçülecek)
- [ ] **Faz 5 - Skill normalization:** "Postgres" ve "PostgreSQL" gibi yazım farklarını birleştirme
- [ ] **Faz 6 - Kural tabanlı matching:** Kullanıcı skill profili, ilan ile profil karşılaştırması, skill gap analizi
- [ ] **Faz 7 - Veri analizi:** Market ve freelance analitiği (Pandas)
- [ ] **Faz 8 - Semantic similarity:** Embedding tabanlı eşleştirme
- [ ] **Faz 9 - Makine öğrenmesi:** Sınıflandırma ve model değerlendirme
- [ ] **Faz 10 - Deep learning / Computer Vision:** Belge anlama denemeleri
- [ ] **Faz 11 - Production:** Kimlik doğrulama, arayüz, deployment

> Eşleşme skorları gibi çıktılar bilimsel bir doğruluk ölçüsü değil, açıklanabilir bir hesaplamanın sonucudur.

## Durum

Faz 1–2 özellikleri ve Faz 2.5 skill temeli uygulandı. Skill ilişkisinden çıkarma
işlemi henüz uygulanmadı. Kullanıcı skill profili Faz 6'ya, kimlik doğrulama ve
arayüz Faz 11'e ayrıldı. Sıradaki hedef Faz 3 OCR baseline; geçiş öncesinde
migration bootstrap düzeltmesinin CI kontrolleri tamamlanmalıdır.
## Lisans

[MIT](LICENSE)
