---
name: verify
description: CareerTracker'da bir değişikliği bitti saymadan veya commit atmadan önce kullan. Değişen alana göre ilgili testleri, tüm test paketini, migration kontrolünü, frontend testlerini ve build'i çalıştırır, gerekirse API'yi başlatıp gerçekten çağırır.
---

# verify — CareerTracker doğrulama adımları

Amaç: Değişikliğin gerçekten çalıştığına dair kanıt toplamak. Ucuz kontrollerden pahalılara doğru ilerle,
bir adım kırılırsa sonrakilere geçmeden önce düzelt.

## 0. Neyin değiştiğine bak

```bash
git status --porcelain
git diff --stat
```

Değişen dosyalara göre hangi adımların gerektiğine karar ver:

| Değişen yer | Gereken adımlar |
| --- | --- |
| `app/`, `tests/`, `init_db.py` | 1, 2, 4 |
| `app/models/`, `migrations/` | 1, 2, 3, 4 |
| `frontend/` | 5, 6 |
| Yalnızca `README.md`, `docs/` | Doğrulama gerekmez; commit'e `Verified-by: none (yalnızca dokümantasyon)` yaz |

## 1. İlgili testler (ucuz)

Değişen modülün test dosyasını önce tek başına çalıştır. Örnek:

```bash
python -m pytest -q tests/test_skill_normalizer.py
```

## 2. Tüm backend test paketi

Kullanıcının yerel veritabanına dokunmamak için bellek içi SQLite ile çalıştır
(CI'daki `ocr-smoke` işi de böyle çalışır):

```bash
DATABASE_URL="sqlite:///:memory:" PYTHON_DOTENV_DISABLED=1 python -m pytest -q
```

Windows PowerShell'de:

```powershell
$env:DATABASE_URL="sqlite:///:memory:"; $env:PYTHON_DOTENV_DISABLED="1"; python -m pytest -q
```

## 3. Migration kontrolü (model veya migration değiştiyse)

Geçici bir SQLite dosyasıyla, kullanıcının veritabanından ayrı:

```bash
DATABASE_URL="sqlite:///verify_tmp.db" PYTHON_DOTENV_DISABLED=1 python -m alembic upgrade head
DATABASE_URL="sqlite:///verify_tmp.db" PYTHON_DOTENV_DISABLED=1 python -m alembic check
rm -f verify_tmp.db
```

`alembic check` yeni bir fark bulursa migration eksiktir.

## 4. Çalıştırarak doğrula (API değiştiyse)

Uygulamayı başlat, değişen endpoint'i gerçekten çağır, sonra kapat:

```bash
DATABASE_URL="sqlite:///verify_tmp.db" PYTHON_DOTENV_DISABLED=1 python -m alembic upgrade head
DATABASE_URL="sqlite:///verify_tmp.db" PYTHON_DOTENV_DISABLED=1 python -m uvicorn app.main:app --port 8765 &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/docs   # 200 beklenir
# değişen endpoint'i burada çağır (gerekirse önce /auth/register ve /auth/token ile token al)
kill %1; rm -f verify_tmp.db
```

Beklenen durum kodunu ve yanıtın şeklini kontrol et; sadece "sunucu açıldı" yeterli değildir.

## 5. Frontend testleri

```bash
cd frontend && npm test
```

`node_modules` yoksa önce `npm ci`.

## 6. Frontend build

```bash
cd frontend && npm run build
```

## Sonuç raporu

Bitirince kısa bir rapor ver:

- Çalıştırılan adımlar ve her birinin sonucu (geçti / kaldı / atlandı ve neden).
- Kırılan bir şey düzeltildiyse ne olduğu.
- Doğrulanamayan kısımlar (ör. PostgreSQL'e özel davranış, OCR bağımlılıkları kurulu değil).
- Commit'e eklenecek satır: `Verified-by: verify-skill`.

## Kurallar

- Aynı hata üç turda düzelmezse dur ve kullanıcıya sor.
- Testi geçirmek için testi değiştirme, atlama ya da `sleep` ekleme.
- Kullanıcının `.env` dosyasını ve `careertracker.db` veritabanını değiştirme; doğrulamada hep geçici veritabanı kullan.
