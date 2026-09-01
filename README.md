# CareerTracker

İş, staj ve freelance fırsatlarını tek yerden yönetmeni sağlayan kişisel kariyer CRM'i.

FastAPI, SQLAlchemy ve PostgreSQL kullanılarak geliştirilen bir backend projesidir.

## Özellikler

- **Fırsatlar** — İş, staj ve freelance başvurularını takip et (şirket, pozisyon, maaş, durum, notlar vb.)
- **Kişiler** — Şirketlerde iletişim kurduğun kişileri kaydet
- **Görüşmeler ve Aktiviteler** — Telefon görüşmesi, e-posta, mülakat gibi etkileşimleri logla
- **Görevler ve Hatırlatmalar** — Takip etmen gereken işleri kaydet
- **Dashboard** — Toplam başvuru, aktif süreç, mülakat ve teklif istatistikleri
- **CSV Dışa Aktarma** — Tüm verilerini dışa aktar

## Başvuru Durum Akışı

```
Yeni fırsat → Başvuruldu → Ön görüşme → Teknik mülakat → Son mülakat → Teklif → Kabul / Reddedildi / Geri çekildi
```

## Proje Yapısı

```
careertracker/
├── app/
│   ├── main.py           # FastAPI uygulama girişi
│   ├── models/            # SQLAlchemy modelleri
│   ├── schemas/            # Pydantic şemaları
│   ├── routes/            # API endpoint'leri
│   ├── services/            # İş mantığı
│   ├── repositories/        # Veritabanı erişim katmanı
│   ├── database/            # Veritabanı bağlantısı ve oturum yönetimi
│   └── core/               # Ayarlar ve ortak yapılandırmalar
├── tests/                  # Testler (pytest)
├── migrations/              # Alembic migration dosyaları
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Kurulum

### Gereksinimler

- Python 3.11+
- Docker (isteğe bağlı, PostgreSQL ile çalıştırmak için)

### Yerel Kurulum

```bash
# Sanal ortam oluştur
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Bağımlılıkları kur
pip install -e .

# Uygulamayı çalıştır
uvicorn app.main:app --reload
```

Uygulama varsayılan olarak `http://127.0.0.1:8000` adresinde çalışır.
İnteraktif API dokümantasyonuna `http://127.0.0.1:8000/docs` adresinden erişebilirsin.

### Docker ile Çalıştırma

```bash
docker-compose up --build
```

## Ortam Değişkenleri

`.env.example` dosyasını `.env` olarak kopyala ve kendi değerlerinle doldur:

```bash
cp .env.example .env
```

## Testleri Çalıştırma

```bash
pytest
```

## Geliştirme Yol Haritası

- [ ] Fırsatlar modülü (CRUD)
- [ ] Kişiler modülü
- [ ] Görüşmeler ve aktiviteler modülü
- [ ] Görevler ve hatırlatmalar modülü
- [ ] Dashboard istatistikleri
- [ ] CSV dışa aktarma
- [ ] PostgreSQL + Alembic migration
- [ ] GitHub Actions ile CI
- [ ] Kimlik doğrulama (opsiyonel)

Detaylı görev listesi için [Issues](../../issues) sekmesine bakabilirsin.

## Lisans

Bu proje kişisel bir portföy/öğrenme projesidir.