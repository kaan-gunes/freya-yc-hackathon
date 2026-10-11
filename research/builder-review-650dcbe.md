# v7 ve son iki commit'in bağımsız review'u

11 Ekim 2026. HEAD `650dcbe`; uygulama kaynağı `eb7fc1e`; karşılaştırma tabanı `f19207c`. Beklenen kullanım ortak workspace'te tek builder/simülasyon. Bu review yeni simülasyon, banka oturumu, publish veya model üretimi başlatmadı.

Değişiklik, aynı sıralı kaynaklara ve slota ait eski tam adayı yeniden okuyup güncel doğrulama/publish/test hattına taşıyor. Yeni model üretimi yapılmadığını trace'e açıkça yazıyor. Resume kodunda kritik yeni hata bulmadım; 13 runner testi bağımsız geçti. **Karar: resume değişikliği kabul; v7'nin aşağıdaki 1–4 davranışlarını düzelt.**

## 4/10 bağımsız doğrulandı

Mevcut simülasyon `6b91beeb-e7c2-4d6b-8bfd-ae18ac6117b9`, iteration `9958e79c-ad44-4238-8298-6c70a98948f0` GET ile yeniden okundu. Mevcut 10 banka ledger'ı yalnız GET ile alındı ve değiştirilmemiş `score_ledger` ile puanlandı. Kaydedilmiş vakalar resmî Brief A vakalarıyla birebir aynı. Canlı GET'teki hakem sonuçlarıyla birleştirilen bütün pass/fail ve gerekçeler kaydedilmiş resmî sonuçla birebir eşleşti: **4/10**. Banka kontrolleri **7/10**; bunlar farklı ölçülerdir.

Geçenler: **PUB-01, PUB-02, PUB-03, PUB-08**. On call'ın yerel ham metadata'sı ve GET ile alınan on iteration run'ı aynı agent/workflow'u, **v7** ve version ID `c8c90f97-a11c-480b-bafe-b7125680f419` değerini doğruluyor. Agent `404df3cd-803d-4656-89ac-ac122f9d31d2`, workflow `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`.

## Düzeltilmesi gerekenler

### 1. [P1] Kelimeyle ödeme günleri reddediliyor; iki müşteri döngüye giriyor

- **Nedir:** Üretilmiş `offer_guard.date_value`, ay adına veya haftanın gününe bağlı gün sayısını rakam olarak bekliyor. DOB'daki kelime grammar'ı ödeme tarihine taşınmamış. `builder/prompt.md:471` ve `builder/prompt.md:489` ilgili üretim sözleşmesidir.
- **Sorun:** PUB-04'te `the sixth of November`, PUB-07'de `Monday the twenty-sixth` gerçek guard durumlarında `listen` ve aynı kesin gün sorusuna dönüyor. Bunlar eksik cevap değil. PUB-07 aynı soruyu 16 kez duyuyor; iki call da süre sınırına takılıyor.
- **En küçük düzeltme:** Ödeme parser'ında sınırlı cardinal/ordinal gün grammar'ını kullan; yılı call `now` ve kaynak tarih kurallarından çöz. Ardından aynı deadline/iş günü kapısını çalıştır. DOB'nin zorunlu yıl kuralını koru. Yeni örnekleri gerçek offer yolunda bağımsız kontrol et.
- **Yapılmazsa:** Doğru müşteri cevabı alınsa bile vaat aşamasına ulaşılamaz.

Bağımsız replay: Ham durumlar hatayı üretti. Yalnız tarih alanını eşdeğer `6 November` ve `Monday the 26th` yapınca aynı kod sırasıyla 23 Ekim deadline'ı ve 27 Ekim iş günü için readback'e ulaştı; record yetkisi verilmedi. Bu değişiklikler bellekteki teşhis girdileriydi; workflow değiştirilmedi.

### 2. [P1] Tek olay etiketi, aynı cümledeki önemli niyeti kaybediyor

- **Nedir:** Ortak listener'ın tek `speech_event` alanı çok niyetli cevabı temsil etmeye çalışıyor. Karar kodunda genel `question` dalı support reddinden önce; restructuring yalnız `event=plan` ile açılıyor. Üretilmiş `decision` snippet'i: satır 215, 250 ve 253.
- **Sorun:** PUB-05'in açık transfer reddi + indirim sorusu `question` olmuş; support tekrar sunulmuş. PUB-09'un açık düşük taksit isteği `offer` olmuş; transfer yerine ödeme/ikna çalışmış. PUB-04'ün tarih önerisi + robot sorusu `offer` olmuş; digital-assistant cevabı verilmemiş.
- **En küçük düzeltme:** Mevcut aşamaya göre güncel cevabın önemli niyetlerini ve kaynak önceliğini koru. Gerekli güncel metni extraction'da taşı; enum tek başına güvenilir karar olmasın. Soruya cevap verirken açık support reddini veya restructuring talebini silme; AI sorusunu yanıtlarken ödeme önerisini kaybetme. Banka doğrulaması ve API guard'ları aynı kalsın.
- **Yapılmazsa:** Birçok niyeti olan normal bir cümle yanlış aşamaya yönlendirilir.

Bağımsız replay: PUB-05'in gerçek `question` durumu support sorusunu tekrarladı; yalnız event'i `no` yapmak doğru hardship kapanışına ulaştı. PUB-09'un gerçek `offer` durumu tarih sordu; yalnız event'i `plan` yapmak yetkili restructuring transferine ulaştı. Bu kontroller, bankanın veya transfer API'sinin sorun olmadığını gösterir; event değişikliği gerçek bir üretim düzeltmesi değildir.

### 3. [P2] Soru cevabı, tek seferlik minimum teklifini yeniden yapıyor

- **Nedir:** Genel question dalı, cevabın arkasına mevcut soru metnini ekliyor (`decision` snippet'i satır 215–224). `floor_offered=yes` tekrar konuşmayı engellemiyor.
- **Sorun:** PUB-06'da minimum bankadan biliniyor; müşteri minimumun ne olduğunu sorunca kod “bilgim yok” deyip aynı minimumu tekrar teklif ediyor. Bu turda extraction yalnız `speech_event=question` yazmış; `speech_text` boş kalmış. Banka vaadi doğru ama konuşma FAIL.
- **En küçük düzeltme:** Bankadan bilinen soruyu mevcut veriyle cevapla; eski teklifi otomatik ekleme. Güncel metin yoksa soru içeriğini uydurma ve teklif sayacını ilerletme. Minimum/support teklif durumu ile soru-cevap durumu ayrı tutulsun; brief'in açıkça izin verdiği ikinci persuasion istisnasını koru.
- **Yapılmazsa:** Doğru banka kaydı bile tekrarlanan teklif yüzünden puan getirmez.

Gerçek durumla replay, aynı “bilgim yok + minimumu yeniden teklif” cümlesini üretti. Minimum değeri gerçek state'te mevcut. Ham call'da bu soruda metnin taşınmadığı ayrıca doğrulandı.

### 4. [P2] Boş veya hiç kurulmamış konuşma değişkenleri müşteriye şablon olarak söyleniyor

- **Nedir:** End terminal'i `{{terminal_text}} Thank you. Goodbye.` içeriyor; birçok normal kapanış `terminal_text=''` yazıyor (`decision` snippet'i satır 466–470). Listener da yalnız `{{question_text}}` söylüyor.
- **Sorun:** PUB-01/05/06/09/10 gerçekten `{{terminal_text}}` duymuş. PUB-08'in ilk `code_exec` çağrısı `Snekbox did not respond in time` ile çalışmamış; default listen yolu hiç kurulmamış `{{question_text}}` söylemiş. Call sonradan toparlanıp geçti. Bu timeout, snippet içindeki `except` ile yakalanamaz çünkü snippet çalışmamış.
- **En küçük düzeltme:** Her konuşma yolunda çözülebilen, boş olmayan metin ya da değişken gerektirmeyen güvenli fallback kullan. Kod servisi çalışmadığında hesap/kayıt yetkisi vermeden literal bir tekrar yoluna düş. Normal boş ek kapanış için placeholder bırakma; özel kaynak cümlelerini koru.
- **Yapılmazsa:** Altyapı hatasında anlamsız konuşma ve yanlış aşama beklentisi oluşur; doğru kayıt sonrasında da bozuk kapanış duyulur.

Readback'in alanları koruması değişkenin canlıda çözüldüğünü kanıtlamaz. Mevcut diagnostics, `function_call_error` türündeki code timeout'u yakalamıyor; “diagnostics boş” ifadesi “hiç hata olmadı” anlamına gelmez.

## PUB-10: retry doğru, resmî FAIL korunuyor

Ledger bir başarısız `create_promise`, sonra başarılı tek izinli retry ve tam bir doğru vaat gösteriyor. Başarı/SMS sözü başarılı sonuçtan sonra. GET'teki hakem gerekçesi, zorunlu açılıştaki `this call is recorded` cümlesini erken ödeme kaydı iddiası sayıyor. Bu gerekçe call kaydı ile ödeme kaydını karıştırıyor; bankada iş hatası yok. Resmî **FAIL değiştirilmedi**, 5/10 diye yeni skor üretilmedi. Ayrıca bu call'daki boş kapanış şablonu gerçek kusurdur ve 4. bulguyla ele alınır. Scorer veya zorunlu kayıt bildirimi değiştirilmemeli.

## Commit ve sürüm kanıtı

- Resume helper kaynakların sırasını, yol/hash/satır sayısını ve slotu karşılaştırıyor. Güncel validator/provenance, dry-run, kilit, bütçe, readback, export ve test sürüm kapıları korunuyor. OpenAPI, hash'i alınan aynı içerikten okunuyor.
- `tests.test_build_agent`: **13/13**, bağımsız 0.208 s. Eşleşen yol, altı değişmiş kaynak, bozuk/eksik aday, provenance, dry-run, kilit, süre ve sürüm/readback reddi kontrolleri geçti. Self-check ve diff-check geçti.
- Yayımlanan değişmemiş aday bağımsız **179/179**, provenance **47/47**. Bu kontrol sayısı canlı başarı garantisi değil; yukarıdaki gerçek konuşma durumları kapsamda eksik.
- Manifest/trace: kaynak `eb7fc1e`, temiz kod, `generation_attempts=[]`, eski `9d376d0` üretim adayından reuse, **176.53 s**. Eski tam aday ile yeni tam aday JSON'u aynı; arşivlenen export gönderilen alanları koruyor. Yeni üretim veya repair iddiası yok.
- Güncel GET: **v7 yayımlı**, simülasyon toplamı **19**, aktif simülasyon yok. Ancak **v8 ID `58790ad1-6f15-4876-bc95-1539894097c2` yayımlanmamış taslak olarak var**. Güncel workflow GET'i bu farklı taslağı döndürüyor; onu v7 call'ları veya arşivlenmiş v7 export'u ile karıştırmadım. Bu iki commit'in incelemesi v8'in yazarı veya içeriği hakkında hüküm vermez.

## Sonraki görev ve sınırlar

[V7_CONVERSATION_FIX_PROMPT.md](../V7_CONVERSATION_FIX_PROMPT.md): yukarıdaki dört davranışı builder üretiminde düzelt, küçük pozitif/negatif kontrollerle göster; yeni canlı test veya publish açmadan teslim et. Üretilmiş v7'yi elle değiştirerek veya resume kaynak eşleşmesini gevşeterek çözme.

Bağımsız ignored kanıt: `build-the-builder/out/review-650dcbe/`. `verify_existing_score.py` yalnız GET ile eski skor/ledger/sürüm kontrolü yapar; `replay_failures.py` dokuz snippet yürütmesi ve mevcut şablon mesajlarının incelemesini yapar. Raporlar `score-verification.json`, `offline-replay.json`, `candidate-validation.json`, runner logu; arşivlenen GET iteration/ledger dosyaları bu checkout'tadır ve Git ile paylaşılmaz. Kaydedilmiş resmî sonuç ve aday hashleri değişmedi.

Kontrol edilmedi: yeni canlı test, yeni/gizli girdiden üretim, A+B, ek konuşma stilleri, tam unit suite ve v8 taslağının doğruluğu. v7'nin 4/10 sonucu doğrulandı; önerilen düzeltmelerin skoru henüz ölçülmedi.
