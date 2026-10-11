# Zaman kritik: doğrulanmış tam adaydan builder üzerinden devam et

Önce `PROJECT_CONTEXT.md`, `research/builder-review-f80b9c1.md` ve `research/validator-compat-live-result.md` oku. Son kaynak `5a70c9b`; review HEAD `f80b9c1`. Ekip değişikliklerini koruyarak repoyu güncelle.

İki validator hatası düzeldi. Review'da 19 bağımsız test geçti. Son yeni build 16 dakika 48 saniye harcadı ama model yalnız açılış/güvenli kapanış üretti; iki repair workflow/checks'i değiştirmedi. Şimdi aynı işi sıfırdan tekrar üretmeye çalışma.

**Hedef: mevcut tam adayın canlı sonucunu, builder'ın güvenlik ve kayıt hattını koruyarak en kısa sürede almak.**

Tam aday: `build-the-builder/out/20261011T105328711505Z/candidate-attempt-3.json`. Yeni validator ile bağımsız **179/179** ve provenance geçti. Bu run ile son run'ın brief, OpenAPI, builder promptu ve üç platform belgesinin hashleri aynı. Adayı veya içindeki workflow'u elle değiştirme. Ham dosya ignored; kendi checkout'unda varlığını kontrol et. Yoksa boş/eksik son adayı veya eski v6'yı yerine koyma; açık blokaj bildir.

1. `scripts/build_agent.py` içine küçük bir `--resume-build <run-directory>` yolu ekle. Verilen brief/API ve kullanılan prompt/platform belgelerinin tamamını eski manifest ile eşleştir; eksik kaynak, değişmiş hash veya bozuk aday varsa publish etmeden dur. Bu yol, kaydedilmiş tam adayı okuyup güncel validator ve kaynak provenance ile yeniden doğrulasın. İş kurallarını veya run yolunu kaynak koda gömme.
2. Mevcut validation → Freya dry-run → save/publish → readback/export → test hattını kullan. Güvenlik kapılarını, gerçek süre bütçesini, kilidi, aynı slotu ve sürüm doğrulamasını koru. Eski adayı doğrudan ayrı bir publish script'iyle yükleme. Yeni trace/manifest'te yeniden kullanım olduğunu, önceki üretim run'ını/kod commit'ini, aday hashini ve bu çağrının zamanını açık kaydet. Yeni model üretimi yapılmış gibi yazma.
3. Küçük mock regresyonlarla eşleşen kaynaktan devamın bütün kapılardan geçtiğini; değişmiş brief/API/prompt/belge veya invalid adayın platform yazısından önce reddedildiğini doğrula. Yalnız etkilenen runner kontrollerini çalıştır; tüm suite'i tekrar etme. Yeni dependency/cache framework ekleme.
4. Kod kontrolleri geçince commit et ve onay beklemeden bu devam yolunu **bir kez** çalıştır. Aynı `kaan-brief-a` slotu, mevcut Brief A/OpenAPI, en fazla 1800 saniye, builder içinde PUB-01 **bir kez**. Önce ortak workspace'te başka simülasyon olmadığını kontrol et; test boyunca sürümü değiştirme.
5. Yeni sürüm yayımlanıp PUB-01 testi tamamlanırsa, aynı sürümde tam Brief A'yı **bir kez** ayrı geliştirme testi olarak çalıştır. Yeni build/repair döngüsü başlatma. Platform blokajında somut rapor ver; simülasyon oluşturulduktan sonra okuma kesilirse mevcut read-only resume yolunu kullan.

`research/validated-candidate-live-result.md` dosyasına kaynak commit'ini, eski/yeni run ve sürelerini, yeniden kullanım yöntemini, kaynak/aday hashlerini, yerel kontrolleri, yeni agent/workflow/version/export ve simülasyon kimliklerini, gerçek PUB-01/A sonucunu yaz. Başarısız müşterilerde ilk takılma noktasını belirt. Altyapı/üretim blokajını sıfır müşteri skoru diye yazma. Ham trace/export ve anahtarlar Git dışında kalsın; kaynak ve okunabilir raporu commit/push ile teslim et.

Bu, **aynı girdili mevcut A adayından devam** görevidir. Yeni/gizli brief üretiminin düzeldiğini, finalin hazır olduğunu veya A+B desteğini iddia etme. Aday farklı girdilere otomatik taşınamaz. Model/telefon modeli değişikliği, yeni mimari, ek validator genişletmesi veya A+B işi başlatma. Son bağımsız-review işaretçisini geliştirici raporuyla ilerletme.
