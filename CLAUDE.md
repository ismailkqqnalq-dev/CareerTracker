# CareerTracker — Claude Code kuralları

İş, staj ve freelance fırsatlarını takip eden kariyer CRM'i.
Backend: FastAPI + SQLAlchemy + Alembic (yerelde SQLite, Docker'da PostgreSQL).
Frontend: React + Vite (`frontend/`). Testler: pytest (`tests/`), Vitest (`frontend/src/*.test.jsx`).

## Komutlar

| İş | Komut |
| --- | --- |
| Bağımlılıklar | `pip install -e ".[dev]"` ve `cd frontend && npm ci` |
| Backend testleri | `python -m pytest -q` |
| Migration kontrolü | `python -m alembic upgrade head` ve `python -m alembic check` |
| Frontend testleri | `cd frontend && npm test` |
| Frontend build | `cd frontend && npm run build` |
| API'yi çalıştır | `python -m uvicorn app.main:app --reload` |
| Arayüzü çalıştır | `cd frontend && npm run dev` |

## Bitti demeden önce doğrula

- Bir değişikliği "bitti" saymadan ve commit atmadan önce `/verify` skill'ini çalıştır.
  Önce ucuz kontroller (ilgili testler), sonra pahalılar (tüm test paketi, build, migration kontrolü).
- Değişikliği çalıştırarak doğrula: API'de değişiklik yaptıysan uygulamayı başlatıp ilgili
  endpoint'i gerçekten çağır; arayüzde değişiklik yaptıysan build al.
- **Üç denemede dur:** Aynı hatayı üç turda düzeltemezsen dur. Ne denediğini, hatanın çıktısını
  ve şüphelendiğin kök nedeni özetle ve kullanıcıya sor. Dördüncü kez aynı yaklaşımı deneme.
- **Testi geçirmek için testi değiştirme.** Bir test kırılırsa önce kodu düzelt. Testin kendisinin
  yanlış olduğunu düşünüyorsan değiştirmeden önce gerekçesiyle kullanıcıya sor.
- **Kararsız (flaky) testlere tolerans yok:** Testi atlama (`skip`), `sleep` ekleme, tekrar deneme
  döngüsü kurma. Kök nedeni bul; bulunamıyorsa testi sil ve nedenini commit mesajında açıkla.
- Doğrulama yapamadığın bir şey varsa (ör. PostgreSQL'e özel davranış, OCR bağımlılıkları kurulu değil)
  bunu açıkça söyle; doğrulanmamış şeyi doğrulanmış gibi sunma.

## Commit kuralları

- Her özellik ayrı branch'te (`feature/...`, `fix/...`, `chore/...`), merge PR ile ve kullanıcı tarafından yapılır.
- Commit mesajları Conventional Commits biçiminde: `feat: ...`, `fix: ...`, `docs: ...`, `chore: ...`.
- Her commit mesajının sonuna nasıl doğrulandığını yaz:
  `Verified-by: verify-skill` | `Verified-by: pytest` | `Verified-by: manual` | `Verified-by: none (<neden>)`.

## Proje kuralları

- Kullanıcıya ait kayıtlar her zaman `user_id` ile süzülür; başka kullanıcının verisine erişim testlerle korunur.
- Veritabanı şemasını değiştiren her değişiklik bir Alembic migration'ı ile gelir; `alembic check` temiz kalmalı.
- `.env`, `careertracker.db` ve gizli anahtarlar asla commit edilmez.
- Kullanıcı bu projeyi öğrenmek için geliştiriyor: büyük bir değişiklik yapmadan önce planı kısaca açıkla,
  bitirince neyi neden yaptığını özetle.
