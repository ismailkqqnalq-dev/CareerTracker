# CareerTracker

[![Tests](https://github.com/ismailkqqnalq-dev/CareerTracker/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/ismailkqqnalq-dev/CareerTracker/actions/workflows/tests.yml)

İş, staj ve freelance başvurularını tek yerde takip etmek için geliştirilen kişisel bir kariyer CRM'inin REST API'si. FastAPI ve SQLAlchemy ile yazılmıştır; SQLite ile yerel, PostgreSQL ile Docker ortamında çalışabilir.

## Özellikler

- Fırsat/başvuru kayıtları için CRUD işlemleri
- Şirketlerde tanışılan kişiler için CRUD işlemleri
- Görüşme ve diğer aktiviteleri kaydetme
- Takip görevleri ve hatırlatmalar
- Başvuru istatistiklerini sunan dashboard
- Fırsatları CSV olarak dışa aktarma (Türkçe karakter desteği)
- Alembic veritabanı migration'ları
- GitHub Actions ile otomatik test çalıştırma

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
| Fırsatlar | \`/opportunities\` — GET, POST | Fırsatları listele veya ekle |
| Fırsat | \`/opportunities/{id}\` — GET, PATCH, DELETE | Detay, güncelleme, silme |
| Kişiler | \`/contacts\` — GET, POST | Kişileri listele veya ekle |
| Kişi | \`/contacts/{id}\` — GET, PATCH, DELETE | Detay, güncelleme, silme |
| Aktiviteler | \`/activities\` — GET, POST | Aktiviteleri listele veya ekle |
| Aktivite | \`/activities/{id}\` — GET, PATCH, DELETE | Detay, güncelleme, silme |
| Görevler | \`/tasks\` — GET, POST | Görevleri listele veya ekle |
| Görev | \`/tasks/{id}\` — GET, PATCH, DELETE | Detay, güncelleme, silme |
| Dashboard | \`/dashboard\` — GET | Başvuru istatistikleri |
| CSV | \`/opportunities/export\` — GET | Fırsatları CSV olarak indir |

## Yerel kurulum

Python 3.11 veya üzeri gerekir.

\`\`\`powershell
git clone https://github.com/ismailkqqnalq-dev/CareerTracker.git
cd CareerTracker

python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

Copy-Item .env.example .env
alembic upgrade head
python -m uvicorn app.main:app --reload
\`\`\`

PowerShell script çalıştırma ilkesi sanal ortamı etkinleştirmeyi engellerse, geçerli terminal oturumu için şu komutu kullanabilirsin:

\`\`\`powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\\.venv\\Scripts\\Activate.ps1
\`\`\`

API şu adreste çalışır: [http://127.0.0.1:8000](http://127.0.0.1:8000). Swagger arayüzü: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Varsayılan \`.env.example\`, yerel SQLite veritabanını kullanır. Tabloları oluşturmak veya güncellemek için \`alembic upgrade head\` komutu kullanılır.

## Docker ile PostgreSQL

Docker ve Docker Compose kurulu olmalı. Depoyu klonladıktan sonra:

\`\`\`powershell
Copy-Item .env.example .env
\`\`\`

Docker Compose içindeki PostgreSQL servisine bağlanmak için \`.env\` dosyasındaki \`DATABASE_URL\` değerini şu şekilde ayarla:

\`\`\`text
DATABASE_URL=postgresql://careertracker:careertracker@db:5432/careertracker
\`\`\`

Ardından uygulama ve veritabanını başlat, migration'ları uygula:

\`\`\`powershell
docker compose up --build -d
docker compose exec app alembic upgrade head
\`\`\`

API: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Servisleri durdurmak için \`docker compose down\` kullan. Veritabanı verileri \`postgres_data\` volume'unda saklanır.

## Testler

Geliştirme bağımlılıklarını kurup testleri çalıştır:

\`\`\`powershell
python -m pip install -e ".[dev]"
python -m pytest -q
\`\`\`

GitHub Actions, \`main\` branch'ine yapılan push ve Pull Request'lerde testleri otomatik çalıştırır.

## Migration oluşturma

Model değişikliğinden sonra yeni migration üretip gözden geçir:

\`\`\`powershell
alembic revision --autogenerate -m "migration açıklaması"
alembic upgrade head
\`\`\`

## Proje yapısı

\`\`\`text
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
\`\`\`

## Durum

Fırsatlar, kişiler, aktiviteler ve görevler için temel CRUD akışları; dashboard, CSV dışa aktarma, PostgreSQL/Docker ve migration altyapısı projede bulunmaktadır. Kimlik doğrulama ve kullanıcı arayüzü henüz kapsamda değildir.

## Lisans

Bu proje kişisel portföy ve öğrenme amacıyla geliştirilmektedir.