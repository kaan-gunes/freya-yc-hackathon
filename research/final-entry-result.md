# Final giriş hattı ve gerçek vaka hazırlığı

11 Ekim 2026, 20:45 İstanbul. Çalışma sürüyor; final agentı/export/teslim henüz tamamlanmadı.

## Kaynak kodunda tamamlanan giriş hattı

- `builder/inputs.py`: PDF sayfaları, DOCX paragrafları/tabloları, XLSX sayfaları/hücreleri/tarihleri ve UTF-8 metin. JavaScript/TOML örnekleri yalnız metin olarak okunur. Makro/formül çalıştırmaz; kaynak ve çıkarılan metin SHA256 kaydeder. Okunamayan belge açık hata verir.
- `builder/language.py`, compiler ve prompt: Türkçe tam onay, ret/şart/soru güvenliği, Türkçe tarih ve tutar normalizasyonu. Tahsilat onayı bütün ödeme alanlarını gerektirir; hizmet onayı gerçek işlemin kapsamına bağlıdır. İş değerleri verilen kaynaklardan gelir.
- Runner: klasör girişi, JSON/YAML OpenAPI bulma, bütün HTTP tool'larını verilen mock base'e bağlama, testsiz publish/export ve boş teslim klasörüne güvenli paketleme. Doğrulama/readback/model/sürüm kapıları korundu.
- Şema bulunmazsa ayrı model çağrısı yalnız kaynakta açıkça bulunan HTTP sözleşmesini çıkarır. Her operasyon için endpoint/method/satır kanıtı gerekir; explicit body-success eşitliği kaynaklı extension ile taşınır. Eksik sözleşme, yeni alan veya yol uydurulması ve unresolved contract facts üretimi durdurur. Tam semantik şema doğruluğu ayrıca bağımsız review gerektirir.
- Trace gerçek redacted Codex JSON session olaylarını, başlangıç/bitişi, model amaçlarını, hash'leri, ID'leri, node/tool sayılarını ve testsiz durumu içerir. Yeni adaylar hash ile edit/resume sınırında doğrulanır.
- Bash çağırıcı aktif sanal ortamın Python'unu kullanır; requirements kurulumu komuta gerçekten ulaşır.

## Genel hizmet profili

Eski builder kimlik sorusu ve ödeme sözü koleksiyon profiline zorunlu bağlıydı. Kaynaktan seçilen genel hizmet profili bu zorunluluğu kaldırır; koleksiyon kapıları korunur. Gerçek API'nin nested request şekli, immutable call context, güncel işlem onayı, fresh readback ve güncel API sonucu kaynaklı metadata üzerinden doğrulanır. Finalin isimleri/alanları/rakamları generic builder koduna veya promptuna gömülmedi.

Bağımsız sentetik inceleme dört gerçek açık buldu: reset sonrası sahte raw response yazılması, business-success bağının kaldırılması, eksik/yanlış tipli required response, failure sonucundan koşulsuz success terminaline geçiş. Supplied date anchor için untrusted extraction kabulü de bulundu. Source-owned düzeltmeler ve negatif testler tamamlandı; son bağımsız yeniden inceleme bunları ve ek snapshot/forged-marker saldırılarını reddetti. Gerçek üretilmiş final politika ayrıca kaynak checklist'iyle incelenmelidir.

## Yerel kanıt

Son birleşik odaklı suite **81 test / OK**, **3.093 saniye**; runner, contract evidence, input reader, collections compiler/confirmation/language ve service guard kontrollerini içerir. Son service fixture suite ve bağımsız yeniden kontrol **12/12 PASS**. Self-check ve `git diff --check` geçti. Önceki 64/34 test koşuları bu testlerle örtüşür; ayrı benzersiz testler diye toplanmaz.

Önceki A adayının gerçek source-only CLI derlemesi **38.05 saniye**, **241/241**, provenance **47/47**, hatalar boş. Run `build-the-builder/out/20261011T172522976842Z`; dirty geliştirme kaynağıyla regression kanıtıdır, final seçimi değildir. Model/Freya çağrısı yok. Son yayımlı practice V10 resmî **8/10**, banka **10/10**; bu final skoru değildir.

## Final girişleri ve mock

Drive'daki **18** özgün dosya indirildi ve SHA256 envanteriyle donduruldu: `build-the-builder/out/final-case/original`. Güncel BRIEF/README, akış PDF'i, sözleşme, e-postalar, toplantı, eski FAQ/IVR, altı örnek, test müşterileri ve Cloudflare örnekleri mevcut. Tam klasör okuyucu kontrolü **22.771 çıkarılmış satır** ile geçti. İlk Downloads BRIEF kopyası eski envanter içerir; çalışmada güncel Drive kopyası kullanılır.

Cloudflare mock source'u `final-mock/` içinde ayrı tutulur. Yedi gerçek POST hizmeti, 34 sentetik müşteri, **617/617** fixture yaprağı yerelde ve yayımlı Worker üzerinde tam HTTP status/body karşılaştırmasıyla geçti. Bu sayı telefon görüşmesi skoru değildir. Canlı suite **20.18 saniye**, zorunlu 12 saniyelik gecikme dahil.

- Origin: `https://core-freya-final.hamitarsln09.workers.dev`
- Worker version: `5b33bf32-04e3-4181-8c8e-0d8bd016a731`
- Fixture SHA256: `d6ce155638f61ab17910d53ea993a2b0d68cf4e10d6b9db2fb8e4a7add0ef44d`

Bağımsız kaynak kontrol listesi 50+ kabul koşulu, çelişki çözümü ve gerçek açık noktaları kaydeder. İlk saatte eklenen belgeler 21:00 sonrasında ayrı snapshot'ta kontrol edilir; dondurulmuş girdiler sessizce değiştirilmez.

## Teslim ve açık iş

Kapanış **23:00 İstanbul / 20:00 UTC**. Alıcı **yavuz@freyavoice.ai**. Üç dosya: `submission.json`, `freya.export_workflow` çıktısı, builder session trace'i. Kullanıcı paket hazır olunca durum anlatılıp gönderim onayı sorulmasını istedi; e-posta gönderilmedi.

Final koşusu temiz code commit'iyle çalışmalı. Agentı builder üretir; workflow elle düzenlenmez. Genel bug düzeltmesi yapılırsa yeni builder koşusu ve trace gerekir. Kaynak review'u, publish/readback/export ve teslim alanları henüz bekleniyor. Yeni telefon simülasyonu başlatılmadı.

İlk gerçek final koşusu `20261011T175029017220Z`, temiz `51edba4` kaynağıyla **4.51 saniyede** model turn başlamadan durdu: Codex giriş sınırı 1.048.576 karakter, gönderilen 1.175.636 karakter. Workflow/publish oluşmadı. Genel düzeltme JSON'un yalnız satır dışı girintisini kaldırır; bütün değerler, string boşlukları, orijinal satır numaraları ve kaynak hashleri korunur. Bu vaka girdisinde 324.164 karakter kazandırır. 14 runner/contract testi geçti; yeni temiz koşu gereklidir.

Okuyucu limitleri: OCR yok; `.doc/.xls` dönüşümü gerekiyor; Excel formülleri cached değer ister; tamamen yazıyla söylenen DOB yılı yok. Final kaynağı IVR aktarım flag/kodunu ve yıllık değişim-hakkı alanını vermiyor; kaynakta bulunmayan endpoint/alan icat edilemez. Konuşma intent'i gerçek telephony transfer kanıtı değildir.
