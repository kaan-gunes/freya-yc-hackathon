# Final teslim hazırlığı — 11 Ekim 2026

Resmî canlı sayfa incelendi. **38 dakika, teslimin kapanmasına değil final belgelerinin açılmasına yakın süreydi.** İnceleme sırasında saat 19:25 İstanbul'du. Bu rapor teslim veya deploy yapıldığı anlamına gelmez.

**20:45 güncellemesi:** Güncel Drive BRIEF'i, README ve diğer 16 kaynak dosya okundu. Downloads'taki ilk brief yerine güncel dondurulmuş Drive kopyası kullanılır. Teslim alıcısı **yavuz@freyavoice.ai**; üç ek: submission.json, resmî workflow export'u ve builder'ın gerçek agent session logu. Gönderimden önce kullanıcıya durum anlatılıp onay sorulacak. Genel giriş hattı ve mock tamam: Worker yayımlı, 617/617 gerçek HTTP fixture karşılaştırması geçti. Yeni inbound hizmet profilinin bağımsız güvenlik kontrolleri sürüyor; final agent henüz üretilmedi. Aşağıdaki eksik tablosu **19:25 tarihsel incelemesidir**. İlk saat yeni belgeleri 21:00'den sonra ayrıca kontrol edilecek. [Güncel final çalışma kaydı](final-entry-result.md).

**21:03 güncellemesi:** İlk saat Drive recheck tamamlandı: yeni Oct10 toplantı kaydıyla **19 dosyalık** ayrı snapshot son üretim girdisidir; eski 18 dosyanın hash'i aynı. Genel profile güvenlik/allOf review'u ve 83 birleşik test geçti. İki ilk koşu agent/publish öncesi durdu; yeni temiz koşu yapılacak. Paket hazır olmadan gönderim onayı istenmez; e-posta henüz gönderilmedi.

## Kesin takvim ve teslim

| Aşama | 11 Ekim Pazar, İstanbul | UTC |
|---|---|---|
| Final belgeleri açılır | **20:00** | 17:00 |
| Teslim kapanır | **23:00** | 20:00 |

Final, **tek Türkçe kredi kartı ekstre-borç vakasıdır**. A/B practice koşuları final teslim yerine geçmez. Belgeler Markdown, Word, PDF ve Excel içerebilir. Gizli müşteriler ve final başarı ölçütleri yayımlanmıyor; zip'te altı örnek konuşma bulunacağı belirtiliyor. [Resmî final ve FAQ](https://www.freyavoice.ai/hackathon#submit)

Gerekli çıktılar:

- Belgeleri girdi alarak builder'ın ürettiği tek phone agent; model Freya LLM olmalı.
- Final hizmet sözleşmesi ve test müşterilerine göre kurulmuş, **Cloudflare Workers üzerinde çalışan mock**. Agent finalde yalnız bu mock'u çağırmalı. Mock sonuçlar açıklanana kadar açık kalmalı.
- `freya.export_workflow` ile alınmış workflow JSON ve aynı üretim koşusunun trace'i; ikisi de repoda commit edilmiş olmalı. Workflow üretimden sonra elle düzenlenmemeli.
- `submission.json`: `team`, `members` (her üye için ad/e-posta; toplam bir veya iki kişi), `repo`, `commit`, `run_command`, `workflow`, `trace`, `mock_url`.
- `submission.json`, **kit e-postasında belirtilen adrese 23:00 İstanbul'dan önce gönderilmeli**. Sayfada teslim formu veya alıcı adresi yok. Verilen komut ve dosya yolları örnek; ekip kendi yollarını kullanabilir. [Resmî teslim adımları ve alanlar](https://www.freyavoice.ai/hackathon#submit)

Trace başlangıç/bitiş zamanını, her model çağrısının modelini ve kısa amacını, workflow/agent ID'lerini, adım/tool sayılarını ve yapılan testlerin sonuçlarını göstermeli. API anahtarları temizlenmeli. **Final e-postası, builder Claude Code/Codex kullanırsa o üretimin gerçek agent session logunu özellikle istiyor**; runner bu olayları trace.jsonl içinde saklıyor. Video şartı belirtilmiyor. Birden fazla builder koşusu yapılabilir, seçilen tek koşunun agentı ve trace'i teslim edilir. Kapanış sonrası güncelleme hakkı açıklanmıyor. [Trace ve sınırlar](https://www.freyavoice.ai/hackathon#submit)

**Canlı resmî sayfa, kit v3 README'nin eski final varsayımlarından günceldir.** Kit iki brief ve değişmeyen yedi tool adı anlatıyor; canlı sayfa tek Türkçe vaka ve ekibin Workers mock'unu istiyor. Final API şemasını kitin eski final açıklamasından kesin varsaymamalıyız.

## Repoda mevcut olanlar

- `scripts/build_agent.py`: kaynak hash'leri, üretim manifest'i, başlangıç/bitiş ve model amaçlarıyla redacted `trace.jsonl`.
- Aynı runner: Freya doğrulama, publish, sürüm/readback kontrolü ve `export.workflow.json` üretimi.
- `build-the-builder/freya.py`: resmî `export_workflow` yardımcısı.

Bunları yeniden yazmaya gerek yok. Final koşusunun seçilen temiz çıktıları tracked bir `submission/` klasörüne alınabilir; raw çağrı kayıtları veya yerel anahtarlar pakete topluca eklenmemeli.

## 19:25'te doğrulanan eksikler — tarihsel

| Eksik | Yer ve etkisi |
|---|---|
| Klasör ve karma belge girişi | `scripts/build_agent.py:251–252` yalnız brief dosyaları ve zorunlu `--openapi` alıyor. `source()` UTF-8 decode yapıyor. `{case_folder}` ile Markdown/Word/PDF/Excel okutma yolu yok. |
| Mock URL girişi | Runner'da `{mock_url}` parametresi yok. Final hizmet sözleşmesinden API bağları çıkarılmalı ve çalışma anında mock adresine bağlanmalı. |
| Finalde testsiz publish/export | Runner online modda export'tan sonra practice scorer'ı zorunlu çalıştırıyor. Finalde PUB-01 veya A/B scorer bulunmuyor; publish/export bu practice koşusuna bağlı kalmamalı. |
| Türkçe onay desteği | `builder/compiler.py` içindeki `_kaan_clear_confirmation` İngilizce grammar kullanıyor; Türkçe `Evet` kabul edilmez. Güvenlik kapısını kaldırmadan genel dil desteği gerekir. |
| Girdi diline uygun tarih işleme | `builder/prompt.md` İngilizce ay/tarih grammar'ını şart koşuyor. Final dili için genel dil uyumu hazırlanmalı; finalden iş kuralı kopyalanmamalı. |
| Trace adım/tool sayıları | Mevcut trace ID'leri yazıyor; adım/tool sayıları event'lerde yok. Üretilen workflow'dan sayılıp mevcut event'e eklenebilir. |
| Workers mock ve teslim dosyası | İnceleme sırasında repoda Workers/wrangler/mock veya `submission.json` şablonu yoktu. |
| Commit edilebilir final çıktısı | `.gitignore`, `build-the-builder/out/` ve `build-the-builder/traces/` klasörlerini dışlıyor. Seçilen temiz export/trace/manifest tracked teslim yoluna alınmalı. |

Satır numaraları bu incelemenin anlık durumudur; eşzamanlı kaynak düzeltmeleri sırasında kayabilir. Bu rapor için test veya deploy çalıştırılmadı.

## En küçük eylem sırası

1. Final açılmadan genel dosya girişi, girdi diline uyum, mock URL girişi, finalde practice testini atlama ve temiz export/trace paketleme eksiklerini tamamla. PUB-06 genel extraction düzeltmesini ve kullanıcının istediği practice testlerini yürüt.
2. 20:00 İstanbul'da Submit sekmesi veya kit e-postasından final zip'i indir. Önce `BRIEF.md` ve `README.md` oku.
3. Hizmet sözleşmesi ve test müşterileriyle Workers mock'u kur, deploy et ve erişimini doğrula.
4. Final belge klasörü ve mock URL ile builder'ı çalıştır. Aynı koşunun bütün üretim trace'ini sakla; agentı elle düzeltme.
5. Export, trace ve manifest'i temiz teslim klasörüne al; `submission.json` alanlarını doldur; repo commit'ini doğrula.
6. 23:00 İstanbul'dan önce kit e-postasındaki adrese gönder. Mock'u sonuçlar açıklanana kadar çalışır tut.

Genel bug düzeltmesi izinlidir. Resmî kural “You may fix a bug in your builder.” ve “Nothing from the final case may be written into it.” diyor. PUB-06'daki genel extraction hatasını düzeltmek bu sınıra uygundur; finalin isimlerini, alan adlarını, değerlerini veya iş kurallarını kaynak/prompta taşımak uygun değildir. [Resmî kurallar](https://www.freyavoice.ai/hackathon#rules)

## Açık bilgiler ve sınır

- Ekip bilgisi kullanıcıdan alındı: Core, Hamit Tuğrul Arslan ve Kaan Güneş. Üye e-postaları yerel teslim taslağına alındı. **Final e-postası alıcıyı yavuz@freyavoice.ai olarak doğruladı.** Yerel taslak `build-the-builder/out/submission-prep/submission.draft.json`; final alanları henüz doldurulmadı ve gönderilmedi.
- İnceleme anında final zip bağlantısı henüz açılmamıştı. Hizmet sözleşmesi, API alanları, örnek müşteriler ve içeriklerin yapısı henüz doğrulanmadı.
- Kapanış sonrası resubmit/update hakkı ve GitHub repo erişim yöntemi sayfada açıklanmıyor.
- Practice A skoru final skor tahmini değildir. Dosya/dil/API adaptasyonu ve erişilebilir mock tamamlanmadan final hazırlığı bitmiş sayılmaz.
