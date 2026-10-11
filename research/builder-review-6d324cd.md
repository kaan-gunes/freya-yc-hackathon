# İkinci builder incelemesi — 11 Ekim 2026

İncelenen HEAD `6d324cd`; son uygulama değişikliği `0331b18`, geliştirme raporu `867a097`. Önceki review uygulama commit'i `9046149` idi. Üç bağımsız inceleme koluyla kaynak, validator, test yardımcısı ve yayımlanmış workflow incelendi.

**Karar:** İlk çalışan çekirdek oluşmuş, ancak kapsamlı A başarısı ve final için hazır değil. Yeni düzeltmeler yalnız kaynakta; dashboard'daki agent hâlâ v6. Sonraki işi güncel somut açıklarla daraltmak gerekiyor.

## Doğrulanan durum

| Ölçüm | Sonuç | Kanıt sınırı |
| --- | --- | --- |
| Repository testleri | 87/87; bu review'da 185.807 saniye | Yerel test; canlı başarı anlamına gelmez |
| Builder `self_check()` | Geçti | Başlangıç kontrolleri |
| PUB-01, v6 | İlk koşu 1/1; aynı sürüm üç tekrar 3/3 | Geliştirme raporunda ayrı simülasyon kimlikleri var |
| Brief A'nın tamamı, v6 | 3/10 | Geliştirme raporundaki resmî skor; burada ledger tekrar puanlanmadı |
| Seçilmiş correction vakaları, v6 | 1/5 | Diğer dört vaka ödeme düzeltmesine gelmeden kimlikte takılmış |
| Tek pieces vakası, v6 | 1/1 | Parçaları birleştirme değil, eksik cevabı reddedip tam cevabı yeniden isteme |
| Son kaynak düzeltmesi `0331b18` | Yerel regresyonlar mevcut | Yeni üretim/publish/canlı skor yok |
| A+B | Henüz desteklenmiyor | Compiler promptu çoklu ürünü `unsupported` sayıyor |

Freya'dan **yalnız GET** ile workflow, sürüm listesi, 10 vakalık A iteration kaydı ve beş görüşme okundu. Yayımlanmış v6 ID'si `946ce959-11d7-4ab5-bfda-faeea22588ad`; agent `404df3cd-803d-4656-89ac-ac122f9d31d2`, workflow `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`. Beş call kaydının `assistantId` ve `entityVersionNumber=6` bilgisi eşleşiyor. Yeni simülasyon, model çağrısı, publish veya banka yazması yapılmadı.

Kaynak rapor: [second-builder-result.md](second-builder-result.md). Arkadaşın bilgisayarındaki tam build trace/policy/checks/export klasörleri burada yok; Git dışında tutuldukları için bu beklenen bir durum. Dashboard'dan indirilen workflow, orijinal builder trace'inin yerine geçmez.

## Öncelikli bulgular

### 1. [P1] Onayda yeni tutar/tarih, correction etiketi yoksa eski söz yetkilendiriliyor

**Yeni offline bulgu; canlı yanlış kayıt gözlendiği iddiası değil.** Yayımlanmış v6 `approval_guard` kodu, düzeltmeyi `approval_correction=yes` veya dar bir metin regex'iyle tanıyor. Güncel tutar/tarih alanları tek başına önceki teklifle karşılaştırılmıyor.

Gerçek guard koduyla sentetik, geçerli 420 / 2026-10-14 readback durumu replay edildi:

- `approval_event=yes`, correction boş, `approval_amount=300`, metin “Yes, three hundred dollars.” → kayıt yetkisi açılıyor, yazılacak tutar **420** kalıyor.
- Aynı durumda `approval_date=2026-10-15`, metin “Yes, tomorrow.” → yazılacak tarih **2026-10-14** kalıyor.
- Sıradan “Yes, I confirm.” kontrolü beklenen eski teklifi yetkilendiriyor.

Model bir alanı doğru çıkarıp correction etiketini kaçırabilir. Güncel alanlar readback ile çelişiyorsa eski söz yazılamamalı; yeni değerler denetlenip tekrar okunmalı. Etiketin boş/yanlış olduğu tutar ve tarih düzeltmelerini ayrı kapsayan regresyonlar gerekli. [Mevcut bağımsız correction testleri](../builder/validation.py#L723) her defasında etiketi `yes` yaptığı için bu kombinasyonu kaçırıyor. Runtime referansı: `approval_guard` code snippet satır 36–39 ve 84–87.

### 2. [P1] Gerçek API hatasında post-hook çalışmıyor; gerekli retry yapılmıyor

**Geliştirme raporunda kabul edilmiş; canlı kayıtla bu review'da tekrar doğrulandı.** PUB-10 call `bed89b3d-9c60-4de3-9cc5-dd32162b35c1` iki kimlik doğrulaması ve account sonrası yalnız bir `create_promise` çağırıyor. Platform `function_call_error` üretiyor; hata “nothing was recorded” diyor. Post-hook atlandığı için retry bayrakları oluşmuyor; `record` varsayılan geçişi `end` oluyor.

[Bağımsız hata kontrolleri](../builder/validation.py#L774) post-hook'u elle çağırıp approval koduna doğrudan geçiyor. Bu, gerçek platformun hook'u atladığı graph yolunu doğrulamıyor. Başarı ve hata sonrasında ulaşılabilen sonuç sınıflandırması, güncel status kanıtı ve gerçek graph regresyonu gerekli. Bu API'nin açıkça “hiçbir şey yazılmadı” garantisi verdiği hata ile sonucu belirsiz timeout ayrılmalı; belirsiz yazma körlemesine tekrarlanmamalı.

### 3. [P1] Validator API alanlarını sabit biliyor; doğru yeni API uyarlamasını engelliyor

**Yeni kaynak/fixture bulgusu.** [Kayıt kontrolleri](../builder/validation.py#L649) `body.get('amount')` ve `body.get('date')` kullanıyor. Kit, final OpenAPI alanlarının değişebileceğini açıkça söylüyor.

Offline karşılaştırma: geçerli test candidate'ı kabul edildi. OpenAPI ve workflow request alanları birlikte `payment_amount` / `payment_date` olarak yeniden adlandırıldı; guard mantığı ve değerler değişmedi. Statik API şema denetimi geçerken beş bağımsız kayıt kontrolü eski `amount` adını aradığı için aday reddedildi. Kaynaklı semantik alan eşlemesi validator'a da taşınmalı; sadece üreten modele “API'ye uy” demek yeterli değil.

Ayrıca [kimlik sözleşmesi](../builder/validation.py#L450) her girdide DOB ve başı sıfırlı sayısal kod sorusu zorunlu tutuyor. Bunlar A için anlamlı testler; başka sorulu brief'te var olmayan gereksinime dönüşmemeli. Tarih sorusu olmayan brief sınırı geliştirme raporunda da kabul edilmiş. Test seçimi çıkarılmış politikaya dayanmalı, eksik zorunlu kimlik sorusunu sessizce atlamamalı.

### 4. [P1] Kimlik öncesi `paid` olayı ödeme cümlesi söyletiyor

**Yeni offline politika bulgusu.** V6 `decision` koduna `stage=identity`, `bank_verified=unverified`, güncel `paid` olayı verildiğinde `paid` kapanışı ve “Payments can take one business day to appear.” cümlesi çıkıyor. `paid/dispute/plan` dalı kimlik durumundan bağımsız işleniyor. Brief A1, kimlik öncesi payment sözcüğünü de yasaklıyor.

Hesap API kapısı kapalı kalıyor; bu örnek veri erişim ihlali göstermiyor. Buna rağmen sabit konuşma metni brief'i ihlal ediyor. İstisna rotalarının sözlü çıktıları da kimlik durumuna göre denetlenmeli; pre-auth müşteri beyanı doğrulanmış ödeme/hesap bilgisi gibi kullanılmamalı. Runtime referansı: `decision` snippet satır 254–269. Genel [exception talimatı](../builder/prompt.md#L308), bu aşama ayrımının regresyonunu sağlamıyor.

### 5. [P2] DOB'nin yıl şartı ödeme tarihlerine de uygulanıyor

**Yeni offline parser bulgusu.** V6 tarih yordamı “6 November”, “the 23rd of October”, “October 23rd” için tarih üretmiyor; yıl eklendiğinde üretiyor. Ay adı dalı `dob` ayrımından önce hem gün hem yıl istiyor. Gerçek decision → offer guard zincirlerinde yılsız cevaplar tekrar soruya, yıllı eşleri readback'e ulaştı. “6 November 2026”, izinli son tarihe teklif olarak ayarlandı.

PUB-04'ün ödeme senaryosunda “6 November” var; mevcut canlı v6 bu noktaya gelmeden telefonda takıldığı için bu hatayı canlı skorun nedeni saymıyoruz. DOB için açık yıl şartı korunmalı. Ödeme tarihinin yılı brief'in `now` ve tarih kurallarına göre yalnız tek anlamlı çözüm varsa belirlenmeli; belirsizlik varsa soru sorulmalı. Runtime referansı: `decision` snippet satır 83–110.

### 6. [P2] Kilit reddedilen resume, geçerli sonuç dosyasını değiştiriyor

**Yeni, mock ile doğrulandı.** [Resume](../scripts/test_agent.py#L397) eski sonucu running yapıp puanı siliyor; [evidence.save](../scripts/test_agent.py#L433) bunu diske yazıyor; [kilit](../scripts/test_agent.py#L456) daha sonra alınıyor. Geçerli `completed`, 1/1 klasörü için kilit doluyken resume → API çağrısı sıfır, exit 2, eski özet `incomplete`, puansız hale geliyor. Mevcut klasöre ilk yazmadan önce uygun kilit alınmalı; eşzamanlı resume dosya yazmaları da korunmalı.

### 7. [P3] Resume, simülasyon süresini yeniden okuma süresiyle eziyor

**Yeni, mock ile doğrulandı.** [run_once](../scripts/test_agent.py#L270), resume sırasında resmî runner'ın GET süresini eski `seconds` üzerine yazıyor. Sentetik tamamlanmış koşu 128.45 saniyeden 0'a değişti; `official-results.json` da aynı değeri aldı. Asıl execution süresi korunup recovery/read süresi ayrı tutulmalı. Builder'ın 30 dakika manifest sayacı bundan etkilenmiyor.

## Önceki review'a göre ilerleme

SSN kaçışı, typed tarih reseti ve bozuk identity-return için somut karşılıklar var: dinleyiciler code'a deterministik gidiyor, string alanlar temizleniyor, model-visible bank araçları kaldırılmış, verified state uzlaştırılıyor. Okunan gate/pieces kayıtlarında schema-write reddi, extraction failure veya unmatched route bulunmadı. Bu beş call dışındaki her konuşmanın sorunsuz olduğunu iddia etmiyoruz.

Guard zincirleri, guard atlama kontrolleri, request binding, ikincil action kapıları, variable-table alias ve gerçek saat kontrolleri eklenmiş. Test ID'leri erken saklanıyor; sürüm kanıtı birikiyor ve read-only resume var. Geliştirme raporu başarısız vakaları saklamıyor; yeni kaynak değişikliğini eski canlı başarıyla karıştırmıyor.

Ancak A'nın beş vakası doğru rakamların kelimeyle söylenmesinde telefon sorusunu tekrar ediyor; PUB-03 cardinal günlerde bankaya hiç ulaşmıyor. `0331b18` bunları yakalayan yerel kontroller ekliyor; **yeni agent üretmeden canlı hata düzelmiş sayılmaz**. Parçalı kimlik cevabı birleştirme, kelimeyle para ve A+B açık kapsam.

Dokuz saat toplam geliştirme, tek builder çalışmasının dokuz saat olduğu anlamına gelmez. Raporda v6 build 1404.71 saniye; v2 build 1800 saniyede eksik bitmiş ve sonraki recovery ayrı tutulmuş. Bu ayrım doğru. Sonraki promptun neden başlatılmadığı başka chat'in son mesajı okunmadan kesin söylenemez.

## Önerilen kısa geliştirme sırası

1. Marker eksik düzeltmeyi ve hook atlanan API hata yolunu bağımsız regresyonlarla kapat. Kimlik öncesi exception konuşmasını ve yılsız ödeme tarihini aynı dar düzeltme işine ekle.
2. `0331b18` dahil builder'dan yeni sürüm üret. Yeni sürümde PUB-01 ve A'nın tamamını ölç; aynı kalan hata için yalnız kör tekrar yapma. Başarılı adayın tekrarları aynı sürümde olsun.
3. API alan eşlemesini ve kimlik türüne göre koşullu testleri genelle. Küçük sentetik değişiklikler doğru agentı yanlış reddetmesin; sahte/eksik binding de kabul edilmesin.
4. Sonra A+B: per-product state, ortak readback, kısmi kayıt ve transferde hiç note olmaması. Henüz bu desteğin var olduğunu varsayma.
5. Helper'ın kilit/süre düzeltmeleri sınırlı bir yan iş. Yeni framework, ayrı LLM şefi veya daha fazla MD katmanı şu an öncelik değil.

## Yerel kanıtlar

Ignored `build-the-builder/out/review-6d324cd/` altında API GET kayıtları, çıkarılmış runtime snippet'ları, `review-observations.json`, `approval-marker-repro.py/json`, `api-field-rename-repro.py/json`, `policy-repro.py`, `policy-repro-results.json`, `helper-repro.py/json` bulunur. Repro'lar banka/model çağırmaz. Bunlar bu checkout'a özgüdür; başka bilgisayara Git ile gitmez. Paylaşılan kanıt bu rapordur; tam teslim trace'leri ayrıca korunmalıdır.
