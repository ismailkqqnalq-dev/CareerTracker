# CareerTracker

[![Tests](https://github.com/ismailkqqnalq-dev/CareerTracker/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/ismailkqqnalq-dev/CareerTracker/actions/workflows/tests.yml)

İş, staj ve freelance fırsatlarını takip etmek için geliştirilen bir kariyer CRM'idir. FastAPI ve SQLAlchemy REST API'si, SQLite ile yerel ve PostgreSQL ile Docker ortamında çalışabilir. `frontend/` dizininde başvuru, kişi, görev ve aktivite yönetimi için CRM ekranları; beceri profili/eşleşmesi, beceri önerileri, OCR, ilan analizi ve başvuru analitiği akışları bulunur. Arayüz temel CRM iş akışlarını kapsar; mobil istemci ve üretim dağıtımı bu kapsamın dışındadır.
## Vizyon

CareerTracker, başvuru takibinden öteye geçmeyi hedefliyor: **Career Tracker AI**. Farklı platformlardan (LinkedIn, Indeed, Upwork, Fiverr) gelen iş ve freelance fırsatlarını tek yerde toplayıp ilanlardan yapılandırılmış veri çıkaran, kullanıcının becerileriyle karşılaştıran ve zamanla piyasa trendlerini analiz eden bir kariyer istihbarat platformu.

Proje aşamalı geliştirilir: önce sağlam bir backend, sonra her yapay zekâ bileşeni için önce basit bir baseline, ardından gelişmiş yöntem ve ölçülebilir karşılaştırma.
## Özellikler

- Fırsat/başvuru kayıtları için CRUD işlemleri
- Şirketlerde tanışılan kişiler için CRUD işlemleri
- Görüşme ve diğer aktiviteleri kaydetme
- Takip görevleri ve hatırlatmalar
- Başvuru istatistiklerini sunan dashboard
- Kullanıcıya özel, seçilen dönem için aylık başvuru hacmi analizi
- Fırsatları CSV olarak dışa aktarma (Türkçe karakter desteği)
- Başvurular, kişiler, görevler ve aktiviteler için React arayüzünden listeleme, ekleme, güncelleme ve silme
- Genel bakış ekranında kullanıcıya özel başvuru durumları, görüşme/teklif sayıları ve son kayıtlar
- Alembic veritabanı migration'ları
- GitHub Actions ile otomatik test çalıştırma
- 247 becerilik ortak teknik seed kataloğu, kullanıcıya özel skill/alias yönetimi ve normalize edilmiş adla skill bulma
- Fırsatlara skill bağlama ve bağlı skill'leri listeleme
- Profil becerilerini yönetme, fırsat gereksinimlerine katalog becerisi ekleme ve profil/fırsat eşleşmesini görme (`frontend/` MVP arayüzü)
- Kullanıcıya özel bekleyen beceri önerilerini gözden geçirip mevcut katalogla eşleştirme (`frontend/` MVP arayüzü)
- Kullanıcının aylık başvuru adetlerini seçilen dönemde görselleştirme (`frontend/` MVP arayüzü)

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
| Hesap | `DELETE /auth/me` | Evet | Mevcut parolayı yeniden doğrular, hesabı ve kişisel kayıtlarını siler |
| Skill kataloğu | `GET /skills` | Opsiyonel | Ortak katalogu; oturum varsa kullanıcının kendi skill'lerini de listeler |
| Skill kataloğu | `POST /skills` | Evet | Yalnızca giriş yapan kullanıcıya özel skill oluşturur |
| Skill çözümleme | `GET /skills/resolve?name=...` | Opsiyonel | Görünür skill'i ad veya alias ile bulur |
| Skill alias | `POST /skills/{skill_id}/aliases` | Evet | Kişisel alias ekler; ortak alias kaydını değiştirmez |
| Beceri önerileri | `POST /skills/suggestions` | Evet | Tanınmayan skill adı için öneri oluşturur veya mevcut öneriyi döndürür |
| Beceri önerileri | `GET /skills/suggestions` | Evet | Kullanıcının önerilerini listeler; `status` ile süzülebilir |
| Beceri önerisi | `PATCH /skills/suggestions/{suggestion_id}` | Evet | Öneriyi görünür bir skill ile kişisel olarak eşleştirir |
| Adaylar | `GET /skills/suggestions/{suggestion_id}/candidates` | Evet | Bekleyen öneri için `strategy=lexical` (varsayılan) veya isteğe bağlı `strategy=semantic` ile adayları sıralar |
| Profil skill'leri | `GET, POST /users/me/skills` | Evet | Profil skill'lerini listeler veya ekler |
| Profil skill'i | `PATCH, DELETE /users/me/skills/{user_skill_id}` | Evet | Profil kaydını günceller veya siler |
| Fırsat skill'leri | `POST, GET /opportunities/{opportunity_id}/skills` | Evet | Fırsata skill bağlar veya bağlı skill'leri listeler |
| Fırsat skill eşleşmesi | `GET /opportunities/{opportunity_id}/skill-match` | Evet | Profilde bulunan ve eksik skill'leri karşılaştırır |
| OCR | `POST /ocr/extract` | Evet | PNG/JPEG ham ikili gövdesini bellekte işler, metin ve görsel ölçülerini döndürür; sonuç saklanmaz |
| İlan analizi | `POST /job-analysis` | Evet | En fazla 100 KB metinden etiketli ilan alanlarını, rol etiketini veya baştaki kısa unvan satırını ve görünür katalog becerilerini çıkarır; becerileri profilinle karşılaştırır; sonucu saklamaz |
| Fırsatlar | `GET, POST /opportunities`; `GET, PATCH, DELETE /opportunities/{id}` | Evet | Kullanıcının fırsatlarını yönetir |
| Kişiler | `GET, POST /contacts`; `GET, PATCH, DELETE /contacts/{id}` | Evet | Kullanıcının kişilerini yönetir |
| Aktiviteler | `GET, POST /activities`; `GET, PATCH, DELETE /activities/{id}` | Evet | Kullanıcının aktivitelerini yönetir |
| Görevler | `GET, POST /tasks`; `GET, PATCH, DELETE /tasks/{id}` | Evet | Kullanıcının görevlerini yönetir |
| Dashboard | `GET /dashboard` | Evet | Kullanıcının fırsat istatistiklerini döndürür |
| Analitik | `GET /analytics/applications?months=12` | Evet | Sunucunun geçerli takvim ayı dahil son 1–60 aydaki başvuru sayılarını döndürür; boş aylar sıfırdır |
| CSV | `GET /opportunities/export` | Evet | Kullanıcının fırsatlarını CSV olarak indirir |

Koleksiyon liste uç noktaları `limit` (varsayılan `50`, en fazla `200`) ve
`offset` (varsayılan `0`) parametrelerini kabul eder. Yanıt biçimi JSON listesi
olarak kalır; filtre uygulanmış toplam kayıt sayısı `X-Total-Count` başlığında
döner. `GET /skills/suggestions/{id}/candidates` kendi `limit` sınırını kullanır.

CSV dışa aktarma kayıtları akışlı üretir. Elektronik tablo formülü olarak
yorumlanabilecek metin hücrelerinin başına tek tırnak eklenir; güvenlik için bu,
dışa aktarılan hücre içeriğini değiştirir. Türkçe UTF-8 BOM korunur.

CRM yazma şemaları alan uzunluklarını sınırlar. Fırsat `job_link` ve kişi
`linkedin` alanları boş olabilir; doluysa yalnızca HTTP/HTTPS URL kabul edilir.
Maaş 0 ile PostgreSQL `INTEGER` üst sınırı arasında olmalıdır. `type` ve `status`
serbest metin olarak kalır; yanıt şemaları eski verilerle uyum için uzunluk kısıtı
uygulamaz.

Her hesap varsayılan olarak en fazla 5000 fırsat oluşturabilir. Sınır
`MAX_OPPORTUNITIES_PER_USER` ile değiştirilebilir; kotaya ulaşınca yeni fırsat
isteği `409 quota_exceeded` döndürür. Sayaç yalnızca isteği yapan kullanıcının
fırsatlarını kapsar.

### İstek sınırları

Kimlik doğrulama ve kaynak tüketen işlemler için süreç içi, bellek tabanlı
sınırlar uygulanır. Varsayılanlar: girişte IP başına 30/dakika ve IP+e-posta
çifti başına 8/dakika; kayıtta IP başına 5/saat; OCR ve ilan analizinde kullanıcı
başına 10/dakika ve her işlem türü için aynı kullanıcının aynı anda en fazla bir
isteği. Semantik skill adayı araması yalnızca `strategy=semantic` seçildiğinde
kullanıcı başına varsayılan 10/dakikadır; lexical sıralama bu sınırdan etkilenmez.
Aşımda `429`, `{"detail","error_code":"rate_limited"}` ve
`Retry-After` döner. OCR'ın mevcut süreç-geneli eşzamanlılık sınırı doluysa
`503 ocr_busy` davranışı korunur.

Sınırlar ve bellek anahtarı üst sınırı `.env` içindeki
`RATE_LIMIT_LOGIN_IP_PER_MINUTE`, `RATE_LIMIT_LOGIN_IP_EMAIL_PER_MINUTE`,
`RATE_LIMIT_REGISTER_IP_PER_HOUR`, `RATE_LIMIT_OCR_PER_USER_PER_MINUTE`,
`RATE_LIMIT_JOB_ANALYSIS_PER_USER_PER_MINUTE`,
`RATE_LIMIT_SEMANTIC_CANDIDATES_PER_USER_PER_MINUTE` ve
`RATE_LIMIT_MAX_TRACKED_KEYS` ile ayarlanabilir. Limiter e-posta adreslerini
saklamaz; IP ve e-posta bileşimlerini tek yönlü özetlerle anahtarlar. Süresi
dolmuş anahtarlar yeni isteklerde temizlenir. Bellek anahtar sınırına ulaşıldığında
yeni anahtarlar, en yakın pencere süresi dolana kadar 429 alır.

`/ocr/extract` ve `/job-analysis` dışındaki istek gövdeleri en fazla 1 MiB
olabilir. `Content-Length` büyükse gövde okunmadan `413 request_too_large` döner;
başlık yoksa veya gerçek akış bildirilen boyutu aşarsa alınan baytlar ayrıca
sayılır. OCR'ın 10 MiB ve ilan analizinin 100 KB sınırları kendi uç noktalarında
uygulanır.

`X-Forwarded-For` varsayılan olarak yok sayılır. Yalnızca doğrudan istemci
`TRUSTED_PROXY_IPS` içindeki IP/CIDR ağlarından biriyse zincir güvenilir proxy
sınırına kadar sağdan sola değerlendirilir. Bu ayarı yalnızca uygulamanın önündeki
gerçek proxy ağları için doldur.

Sayaçlar süreç içinde tutulur; birden fazla Uvicorn worker veya uygulama örneği
arasında paylaşılmaz. Bu nedenle çoklu worker dağıtımında sınırlar her worker için
ayrı uygulanır. Paylaşımlı sayaç gereken yayında Redis gibi ortak depolama
kullanılmalı; bu proje içi bellek deposu geliştirme ve tek-worker kullanım içindir.

### Beceri API hata kodları

JSON hata gövdesindeki sabit kodlar:

| `error_code` | Endpoint | Anlamı |
|---|---|---|
| `skill_not_found` | `GET /skills/resolve` | Görünür katalogda bu adla skill bulunamadı (404) |
| `skill_already_recognized` | `POST /skills/suggestions` | Skill zaten tanınıyor; öneri yerine katalogdaki skill kullanılmalı (409) |
| `semantic_engine_unavailable` | `GET /skills/suggestions/{suggestion_id}/candidates?strategy=semantic` | İsteğe bağlı FastEmbed kurulmamış veya model yerel önbellekte yok (503) |
| `semantic_engine_failed` | `GET /skills/suggestions/{suggestion_id}/candidates?strategy=semantic` | Yerel embedding motoru çıkarım yapamadı (502) |
| `opportunity_not_found` | `POST, GET /opportunities/{opportunity_id}/skills`; `GET /opportunities/{opportunity_id}/skill-match` | Fırsat bulunamadı veya kullanıcıya ait değil (404) |
| `unknown_skill` | `POST /opportunities/{opportunity_id}/skills` | Skill tanınmadı (404); öneri kaydedildiyse gövdede `suggestion_id` de bulunur |

### İlan analizi hata kodları

`POST /job-analysis`, `Cache-Control: no-store` ile çalışır; metin veritabanına
yazılmaz. İstek gövdesi UTF-8 JSON'dur ve en fazla 100.000 bayt kabul edilir.
Başarılı yanıt rolü, açık etiketle bulunmuş şirket/konum/çalışma türü/ücret/
deneyim/eğitim/başvuru bağlantısını kaynak satır numarasıyla, katalogda
eşleşen becerileri özgün satırlarıyla ve her becerinin mevcut kullanıcının
profilinde kayıtlı olup olmadığını döndürür. `profile_match`, her benzersiz
beceri için zorunlu/tercih edilen/bölümü belirtilmeyen gruplarda profilinde
kayıtlı olma oranını verir; bu bir işe uygunluk veya başarı olasılığı değildir.

| `error_code` | HTTP | Anlamı |
|---|---:|---|
| `invalid_content_length` | 400 | Geçersiz `Content-Length` başlığı |
| `job_text_too_large` | 413 | İstek gövdesi 100 KB sınırını aşıyor |
| `invalid_job_text` | 422 | JSON veya `text` alanı geçersiz |
| `empty_job_text` | 422 | Metin boş veya yalnızca boşluk içeriyor |

### OCR API hata kodları

`POST /ocr/extract` hataları aynı `{detail, error_code}` zarfını kullanır. İstek gövdesi
`image/png` veya `image/jpeg` ham baytlarıdır; multipart kullanılmaz. `Content-Length`
yalnızca erken ret için okunur, boyut sınırı akış sırasında da uygulanır. Endpoint
görseli uygulama dosya sistemine veya veritabanına yazmaz; proxy ya da ASGI sunucusunun
gövdeyi uygulamaya iletmeden önce tamponlayıp tamponlamadığı dağıtım ayarlarına bağlıdır.

| `error_code` | HTTP | Anlamı |
|---|---:|---|
| `invalid_content_length` | 400 | Geçersiz uzunluk başlığı |
| `request_body_timeout` | 408 | Görsel gövdesi 20 saniyelik okuma süresinde tamamlanmadı |
| `image_too_large` | 413 | Gövde 10 MiB sınırını aşıyor |
| `image_pixel_limit_exceeded` | 413 | Görsel piksel sınırını aşıyor |
| `unsupported_image_type` | 415 | İçerik PNG/JPEG değil |
| `animated_image_unsupported` | 415 | Animasyonlu görsel desteklenmiyor |
| `invalid_image_input`, `empty_image`, `invalid_image` | 422 | Gövde boş, bozuk veya çözümlenemiyor |
| `empty_ocr_result` | 200 | Görsel geçerli, okunabilir metin yok; `text` boş, ölçüler yine döner |
| `invalid_ocr_result`, `ocr_engine_failed` | 502 | Motor geçersiz sonuç verdi veya çıkarım başarısız oldu |
| `ocr_engine_unavailable`, `ocr_engine_initialization_failed`, `ocr_busy` | 503 | OCR bağımlılığı/motor yok, başlatılamadı, dört yükleme yuvası dolu veya OCR yuvası dolu |
| `ocr_timeout` | 504 | OCR çıkarımı bekleme sınırını aştı; çalışan CPU çıkarımı durdurulamaz ve bitene kadar yuva tutulur |

Süreç başına en fazla 4 gövde okuması eşzamanlı yürür; her biri 10 MiB ile
sınırlandırıldığı için birikmiş istek gövdeleri için nominal üst sınır 40 MiB'dir.
ASGI sunucusunun teslim ettiği tek bir büyük parça ve bayta dönüştürme sırasındaki
geçici kopya ek bellek kullanabilir. Gövde okuması 20 saniyeyi aşarsa 408 döner ve
okuma yuvası bırakılır. Yükleme tamamlanınca bu yuva OCR için serbest kalır.

OCR eşzamanlılık sınırı süreç başına 1'dir. Gövde yuvaları veya OCR yuvası doluysa
istek bekletilmeden `ocr_busy` / 503 döner. Birden fazla Uvicorn worker varsa her
işçi kendi limitlerine sahiptir; host genelindeki limit worker sayısıyla çarpılır.
OCR çıkarım beklemesi 30 saniyedir; zaman aşımı çalışan OCR işini durdurmaz ve yuva
iş bitene kadar tutulur. OCR gövdesi ve çıkarılan metin uygulama loglarına yazılmaz. Swagger `/docs` sayfasında
`POST /ocr/extract` için şemada PNG/JPEG ikili gövde tanımlıdır. Swagger UI'da
**Try it out** ile dosya seçip **Execute**'a basarak tokenli isteği deneyebilirsin;
canlı tarayıcıda bu kontrol bu değişiklikte tamamlanmadı.

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
python -m app.seed_skill_catalog
python -m uvicorn app.main:app --reload
```

## Güvenlik yapılandırması

Uygulama başlarken `JWT_SECRET_KEY` değerinin en az 32 bayt ve örnek/placeholder
olmayan bir değer olduğunu doğrular. `.env.example` içindeki anahtar yalnızca
placeholder'dır; yerel `.env` dosyanda yeni bir anahtar üret:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Üretilen değeri yalnızca yerel `.env` dosyasındaki `JWT_SECRET_KEY` alanına koy;
gerçek anahtarı depoya veya `.env.example` dosyasına ekleme.

Yalnızca `APP_ENV=development` açıkça belirtilmişse (büyük/küçük harf duyarsız)
kayıt varsayılan olarak açıktır. `APP_ENV` tanımsız, boş veya bilinmeyen bir değerse
kayıt kapalıdır. `REGISTRATION_ENABLED=true|false` ile varsayılan açıkça
geçersiz kılınabilir. Kapalı kayıt isteği `403 registration_disabled` döndürür.

Hesap sahibi `DELETE /auth/me` isteğiyle mevcut parolasını yeniden doğrulayıp
hesabını silebilir. Kullanıcının CRM kayıtları, profil becerileri, önerileri ve
kişisel becerileri veritabanı `CASCADE` kurallarıyla silinir; ortak beceri
kataloğu ve diğer kullanıcıların kayıtları korunur. Silinen hesabın JWT'si,
hesap bulunamadığı için sonraki istekte geçersiz olur. Yanlış parola
`403 password_confirmation_failed` döndürür. İşlem geri alınamaz; bu MVP'de
hesap silme yalnızca API üzerinden yapılabilir.

Kabul edilmiş risk: kayıtlı e-posta için `POST /auth/register` mevcut davranış
gereği `409` döndürür ve bu, e-posta adresinin sistemde olup olmadığını ortaya
çıkarabilir. Şimdilik açık hata mesajı kayıt deneyimi için korunuyor. Bu yanıtı
genelleştirmek, e-posta doğrulama ve parola kurtarma akışıyla birlikte ele
alınmalıdır.

## Docker ile PostgreSQL

Docker ve Docker Compose kurulu olmalı. Depoyu klonladıktan sonra:

```powershell
Copy-Item .env.example .env
```

`.env` içinde PostgreSQL parolası için güçlü, URL'de güvenle kullanılabilecek
rastgele bir değer belirle ve aynı değeri iki yerde kullan:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```text
POSTGRES_PASSWORD=<rastgele-güçlü-değer>
DATABASE_URL=postgresql://careertracker:<aynı-değer>@db:5432/careertracker
```

`POSTGRES_PASSWORD` eksikse Compose başlamaz. Bu değerleri `.env.example` veya
depodaki başka bir dosyaya yazma.

Sentetik ilan metni analizi ölçümünü bellekteki SQLite kataloğunda çalıştır:

```powershell
python -m scripts.evaluate_job_text_analysis
```

Betik precision/recall/F1, tanınmayan sentetik terimleri ve OCR benzeri yazım
bozulmalarındaki sonuçları JSON olarak terminale yazar; veritabanına veya dosyaya
çıktı kaydetmez.

Ardından uygulama ve veritabanını başlat, migration'ları uygula:

```powershell
docker compose up --build -d
docker compose exec app alembic upgrade head
docker compose exec app python -m app.seed_skill_catalog
```

API: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Servisleri durdurmak için `docker compose down` kullan. Veritabanı verileri `postgres_data` volume'unda saklanır.

## Frontend arayüzü

Giriş yaptıktan sonra genel bakışta başvuru durumlarını ve son kayıtları görebilir;
başvuru, kişi, görev ve aktivite kayıtlarını yönetebilirsin. Koleksiyon ekranları
50 kayıtlık sayfalarla çalışır. Başvurulara bağlı kişiler, görevler ve aktiviteler
başvurunun silinmesinde backend'in mevcut cascade davranışına tabidir; arayüz silme
onayında bunu bildirir.

Beceri önerisi ekranı yeni beceri gönderme ve benzer adayları kullanıcı onayıyla
eşleştirme akışını sunar. Profil/eşleşme ve aylık analitik ekranları da yer alır.
İlan analizi kural tabanlıdır; katalogda bulunmayan becerileri veya serbest metin
anlamını her durumda çıkaracağı garanti edilmez.

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
- Seed kataloğu yazılım, veri bilimi/ML, web, veritabanı, bulut ve DevOps
  alanlarından seçilmiş teknik beceriler içerir. `Skill.category` serbest metin
  alanıdır; sabit enum veya yeni migration gerektirmez. Seed'in çalışması ortak
  kataloğa beceri ve global alias ekler; komut tekrar çalıştırılabilir ve kişisel
  skill/alias kayıtlarını değiştirmez.

### Aday sıralaması ve eşleştirme

Aday sıralamasında varsayılan `lexical` stratejisi `difflib.SequenceMatcher` metin
benzerliği ve token örtüşmesi kullanan bir heuristiktir. `semantic` stratejisi,
isteğe bağlı yerel FastEmbed/ONNX çok dilli embedding modelini kullanır. İki skor
da benzerliktir; doğruluk olasılığı veya becerilerin aynı olduğuna dair güven ölçüsü
değildir. Model CareerTracker verisiyle eğitilmemiştir. `C#` ve `C++` gibi sembollü
adlar için yazım eşlemeleri yalnızca varsayılan lexical stratejide kullanılır.
Semantik model kurulumu ve küçük sentetik değerlendirme için
[semantik aday sıralama notlarına](docs/semantic-candidates.md) bak.
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

İlan görseli için PNG/JPEG dosyası seçip **Görselden metin çıkar**'a bas. Çıkan
metni gözden geçir; **Analiz alanına aktar** metni ilan analiz kutusuna kopyalar,
ardından analizi ayrıca başlatırsın. Görsel ve OCR sonucu veritabanına veya
tarayıcı depolamasına yazılmaz; OCR isteği kimlik doğrulamalı API'ye gönderilir.
OCR motoru isteğe bağlıdır; kurulumu ve yerel kullanım adımları için
[`docs/ocr-baseline.md`](docs/ocr-baseline.md) belgesine bak.

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

Boş bir veritabanında tabloları kurmak için `python -m alembic upgrade head`, ortak beceri
kataloğunu eklemek için `python -m app.seed_skill_catalog` çalıştır. İlk migration
fırsat, kişi, aktivite ve görev tablolarını; sonraki migration skill tablolarını
oluşturur. `init_db.py`, Alembic geçmişini kaydetmediği için normal kurulum adımı değildir.

İlk migration önceden boştu ve bu bootstrap düzeltmesiyle tamamlandı. Mevcut
tabloları doğru olan ve `d0fe616da34f` veya `b3b24fd6d532` revision'ında kayıtlı
veritabanlarında ilk migration tekrar çalışmaz. Bu durumdaki veriler korunur.
Eski boş migration ile kurulmuş, temel tabloları eksik bir veritabanı bu değişiklikle
otomatik onarılmaz. `init_db.py` ile kurulmuş fakat Alembic revision'ı olmayan
veritabanlarında da önce yedek alınmalı ve şema/revision eşleşmesi incelenmelidir;
körlemesine `stamp head` uygulanmamalıdır.

### Eski CRM kayıtlarına sahip atama

`opportunities`, `contacts`, `tasks` veya `activities` tablolarında `user_id`
değeri `NULL` olan eski kayıtlar varsa, son sahiplik migration'ı `user_id` alanlarını
`NOT NULL` yapmadan önce bu kayıtların hangi mevcut kullanıcıya ait olduğunu açıkça
belirlemek gerekir. Migration kayıtları silmez veya otomatik olarak bir kullanıcıya
atamaz. Önce uygulamayı durdurup yedek alın; ardından betiği varsayılan salt okunur
dry-run ile çalıştırıp sayıları ve bağlantı tutarsızlıklarını inceleyin:

```powershell
python scripts/claim_orphan_records.py --user-id 1 --database-url "sqlite:///C:/path/to/careertracker.db"
```

SQLite'ta `--apply`, değişikliklerden hemen önce veritabanının tutarlı bir kopyasını
aynı dizine `careertracker.db.bak-claim-YYYYMMDD-HHMMSS` adıyla alır ve yedek yolunu
çıktıda gösterir. Yolu not edip yedeğin oluşturulduğunu doğruladıktan sonra sahipliği
atanabilir:

```powershell
python scripts/claim_orphan_records.py --user-id 1 --database-url "sqlite:///C:/path/to/careertracker.db" --apply
```

PostgreSQL için önce `pg_dump` ile elle yedek alın ve yedeği doğrulayın; betik
PostgreSQL yedeği oluşturmaz. Uygulamadan önce bu onayı ayrıca verin:

```powershell
python scripts/claim_orphan_records.py --user-id 1 --database-url "postgresql://..." --apply --i-have-a-backup
```

Betiğin bağlantı tutarsızlığı raporladığı durumda otomatik düzeltme yapmayın; ilgili
kayıtların sahipliğini inceleyin. Betik başarıyla tamamlandıktan ve sahipsiz satır
kalmadığı doğrulandıktan **sonra** migration'ı çalıştırın:

```powershell
python -m alembic upgrade head
```

Yeni kurulan veritabanlarında bu sahiplik devri adımı gerekmez. CRM kayıtları artık
her zaman bir kullanıcıya bağlı olmalıdır; downgrade bu kısıtı kaldırır.

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
scripts/            # Tekrar çalıştırılabilir değerlendirme ve yardımcı betikler
migrations/        # Alembic migration dosyaları
tests/             # pytest testleri
```

## Yol Haritası

- **Tamamlandı — Faz 1:** Fırsat, kişi, aktivite ve görev backend CRUD'ları.
- **Tamamlandı — Faz 2:** Dashboard, CSV dışa aktarma, PostgreSQL/Docker, Alembic ve CI.
- **Tamamlandı — Faz 2.5:** Skill modelleri ve API'si, seed katalogu, kişisel skill/alias ve öneri eşleştirme temeli.
- **Kısmi — Faz 3:** Görsel doğrulama/OCR servis baseline'ı, kimlik doğrulamalı ham metin çıkarma API'si ve sonucu kullanıcı onayıyla Faz 4 analiz alanına aktaran arayüz var; sonuç saklanmaz ve gerçek ilanlarda OCR kalitesi kapsamlı ölçülmedi.
- **Kısmi — Faz 4:** Yapıştırılan/OCR'dan aktarılan ilan metninden açık etiketli alanları, görünür katalog becerilerini ve tanınan gereksinim bölümlerini çıkaran; becerileri kullanıcı profilindeki kayıt, seviye ve deneyimle karşılaştıran kural tabanlı servis, API ve MVP arayüzü var. Yedi kısa gerçek ilan kırpıntısı üzerinde dar kapsamlı bir regresyon değerlendirmesi bulunur; bu, kapsamlı veya üretim doğruluğu ölçümü değildir. Sonuç saklanmaz; serbest metinden anlamsal alan çıkarımı ve kapsamlı değerlendirme tamamlanmadı.
- **Kısmi — Faz 5:** Normalizasyon, seed alias'ları, kişisel alias'lar ve metin benzerliğine dayalı aday sıralaması var; kapsamlı beceri normalizasyonu tamamlanmadı.
- **Kısmi — Faz 6:** Profil becerilerini yönetme, fırsat becerisi ekleme ve eşleşen/eksik becerileri gösteren MVP arayüzü ile backend endpoint'leri var; tam eşleştirme ürünü tamamlanmadı.
- **Kısmi — Faz 7:** Kullanıcıya özel, son 1–60 takvim ayı için aylık başvuru sayısı API'si ve aylık dağılımı gösteren React ekranı var; bu betimleyici sayım tahmin veya piyasa analizi değildir. İleri metrikler, dönüşüm analizi ve piyasa analizi tamamlanmadı.
- **Kısmi — Faz 8:** Beceri önerileri için isteğe bağlı, yerel embedding tabanlı semantik aday stratejisi var; varsayılan lexical davranış korunur. Değerlendirme küçük sentetik kümeyle sınırlıdır.
- **Planlandı — Faz 9–10:** Makine öğrenmesi ve deep learning/computer vision çalışmaları.
- **Kısmi — Faz 11:** JWT kimlik doğrulaması ve başvuru, kişi, görev, aktivite, beceri ve analiz akışlarını kapsayan React web arayüzü var; mobil istemci ve deployment tamamlanmadı.

Fazlar doğrusal ilerlemez. Faz 5, 6 ve 11'in bazı altyapı parçaları OCR/NLP başlamadan önce geliştirildi; bu fazlar tamamlandı anlamına gelmez.

## Durum

Faz 1, 2 ve 2.5 tamamlandı. Faz 3 OCR baseline aşamasında; görsel yükleme için
kimlik doğrulamalı API ve sonucu ilan analiz alanına aktaran arayüz eklendi. Faz
4'te etiketli ilan alanı/rol çıkarımı, katalog becerisi eşleşmesi ve profil
becerileriyle karşılaştırma yapan kural tabanlı API ve arayüz eklendi. Faz 5, 6
ve 11'den bazı parçalar erken teslim edildi ancak bu fazların bütünü tamamlanmış
değildir. Arayüz başvuru, kişi, görev ve aktivite CRUD ekranlarını, kullanıcıya
özel genel bakışı, OCR/ilan analizini, beceri önerilerini, profil eşleşmesini ve
aylık başvuru analizini sunar. Mobil istemci ve üretim dağıtımı yapılmamıştır.

## Bilinen sınırlar

- Beceri önerisini reddetmek için endpoint veya arayüz akışı yoktur.
- `PATCH /skills/suggestions/{suggestion_id}` kabul edilmiş öneriyi yeniden
  eşleştirebilir.
- Kabul edilmiş önerinin hedef skill'i silinirse foreign key `resolved_skill_id`'yi
  boş bırakır; önerinin durumu `accepted` kalır. Bu davranış testle belgelenmiştir.
- Aday sıralamasının varsayılanı yazım/metin benzerliği heuristiğidir. İsteğe bağlı
  semantik model küçük sentetik kümede denenmiştir; gerçek kullanıcı/ilan verisinde
  başarı ölçümü değildir. Her iki stratejinin skoru doğruluk olasılığı değildir.
- Bir fırsata bağlanan skill'i kaldırmak için endpoint yoktur; yalnızca profil skill'i silinebilir.
- Fırsat silinince ona bağlı kişiler, görevler, aktiviteler ve fırsat-skill
  bağlantıları veritabanı `CASCADE` kurallarıyla silinir. Kişi silinince aktivite
  kaydı korunur ve `contact_id` boşaltılır (`SET NULL`).
- İlan analizi yalnızca ortak katalogu, kullanıcının kendi skill'lerini ve kişisel eşleştirmelerini görür. Katalog dışında kalan terimleri otomatik olarak öneri veya alias yapmaz.
- İlan analizi ML değildir: becerileri ad/alias sözlüğü ve sözcük sınırlarıyla arar; yalnızca katalogda karşılığı olan becerileri algılayabilir. Uygulama bu sınırlamayı analiz sonucunda kullanıcıya gösterir. Şirket, konum ve ücret gibi bilgileri yalnızca açık etiketlerden alır. Rolü açık etiketten alır; etiket yoksa ilk beş satırdaki kısa, iş unvanı biçimine benzeyen satırı daha düşük güvenli başlık adayı olarak gösterebilir. Gereksinim türünü yalnızca tanınan bölüm başlıklarından belirler.
- Profil karşılaştırması, bölüm başına katalogda eşleşen benzersiz becerilerden kaçının mevcut kullanıcının profilinde kayıtlı olduğunu gösterir. Profilde kayıtlı olmamak kişinin beceriyi bilmediğini kanıtlamaz. Profil seviyesi ve deneyim yılı gösterilir, ilandaki serbest deneyim ifadesiyle otomatik kıyaslanmaz.
- Ortak katalog küratörlü ve sınırlıdır; beceri dışarıda kalabilir. Yeni global alias eklemeden önce hem `normalize_text` hem ilan analizindeki Türkçe/OCR katlama sonrası çakışmalar denetlenmelidir. `Spark`, `Iceberg`, `Airflow`, `Redshift` ve `Modal` katalogda bağlam kontrollü alias'lardır; örneğin lakehouse/veri işleme, orkestrasyon, veri ambarı veya ML/model çalıştırma bağlamı olmadan eşleşmez. `BERT`, `BART`, `JAX`, `embeddings`, `Braintrust`, `reranking` ve `spelling correction` gibi adlar da yakındaki NLP/ML, değerlendirme veya arama bağlamını gerektirir. `Argo` tek başına katalog alias'ı değildir. `Spring`, `Excel`, `Word` ve `Dash` gibi genel sözcükler de tek başına alias yapılmaz; kısa `C`, `R`, `Go` adları yalnızca programlama bağlamı filtresini geçen satırlarda eşleşir.
- İlan analizi eşleştirme sırasında Unicode NFC/NFD eşdeğerlerini kanonikleştirir ve `matched_text` alanında kaynak metindeki özgün yazımı korur. OCR harf hatalarını ve Türkçe ekleri anlamsal olarak düzeltmez; bu nedenle gerçek ilanlarda beceri kaçırabilir veya metne göre istenmeyen eşleşmeler olabilir.
- `scripts.evaluate_job_text_analysis` sentetik ilan/OCR varyantlarını, `scripts.evaluate_public_job_postings` yedi kısa ve elle etiketlenmiş gerçek ilan kırpıntısını ölçer. Gerçek ilan kümesi veri mühendisliği, yazılım, makine öğrenmesi ve DevOps rollerinden seçilmiştir; küçük ve temsil gücü olmayan bir regresyon kümesidir. Katalogda bilerek yer almayan belirsiz yalın adlar (ör. Rust ve Scala) kapsama notu olarak raporlanır, precision/recall/F1 hesabına girmez. Hiçbir sonuç gerçek ilanlardaki genel başarıyı kanıtlamaz.


- Rate-limit sayaçları süreç içi bellektedir; birden fazla worker veya replika
  arasında paylaşılmaz. Dağıtık kullanımda ortak bir depo, örneğin Redis gerekir.
- Giriş sınırları IP ve IP+e-posta bileşimi bazındadır. Çok sayıda farklı IP'den
  tek hesaba yapılan dağıtık parola denemeleri bu sınırları aşabilir; hesap başına
  sert kilit, hizmet engelleme riski nedeniyle uygulanmıyor.
- `RATE_LIMIT_MAX_TRACKED_KEYS` üst sınırı dolduğunda yeni limiter anahtarları
  pencere süresi dolana kadar `429` alır. Çok sayıda farklı IP'li saldırı bu
  nedenle yeni kullanıcıları geçici olarak etkileyebilir.
- Sabit pencere algoritması, pencere sınırının iki yanında kısa sürede yaklaşık
  iki kat istek geçmesine izin verebilir.

## Lisans

[MIT](LICENSE)
