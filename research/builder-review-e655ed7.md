# Konuşma düzeltmeleri ve reddedilen adayın bağımsız review'u

11 Ekim 2026. İncelenen HEAD `e655ed7`; uygulama/test kaynağı `cc09a5f`; model üretim kaynağı `8a95ace`; taban `fb91544`. `8a95ace`, `cc09a5f` ve `e655ed7` birlikte incelendi. Beklenen kullanım, ortak workspace'te tek builder/test çalışmasıdır.

Bu değişiklik, builder'ın konuşma üretim sözleşmesini ve bağımsız kontrollerini güçlendiriyor. Aynı brief/API'ye ait eski taslağı yalnız bir offline model onarımına başlangıç olarak kullanabiliyor; kaynak eşleşmesi, bütçe, kilit ve doğrulama kapıları korunuyor. **Runner değişikliği kabul edilebilir; son aday yayımlanmaya hazır değil.**

## Sonuç ve doğrulama

- Etkilenen beş test modülü bağımsız **57/57**, **91.754 saniye** geçti. Geliştirici raporundaki ilk 56 teste, `cc09a5f`'nin sonraki kapanış regresyonu eklenmiş; iki test sayısı çelişmiyor.
- Değişmemiş gerçek aday, güncel validator ile bağımsız **203/207** verdi. Aynı dört check ve aynı gerekçeler başarısız. Bunlar gerçek davranış hataları; bu review validator'ı gevşetmeyi önermiyor. **207, müşteri sayısı değil; yerel guard/check sayısıdır.**
- Provenance **47/47**. Güncel altı kaynak dosyası manifest'in yol/hash/satır sayılarıyla aynı. Aday SHA256 `5f2691d3699c456c2dac20ccd1e980c981697b9a0d165af73da860b36705e77b`; review sırasında değişmedi. Başlangıç taslağının hash'i de korunuyor.
- Manifest/trace: `8a95ace`, temiz kod, **451.70 saniye**, bir gerçek model merge-patch çağrısı, `offline=true`, `incomplete`, `live_test=not_run`. Olaylar yalnız begin → seed → model begin/end → local validation → end. Yeni Freya doğrulaması, publish veya test kanıtı yok.
- Bu review yalnız yerel kod/test/artefakt okudu ve snippet'leri offline çalıştırdı. Yeni model üretimi, Freya GET/yazma, banka oturumu, chat turn veya simülasyon başlatılmadı. Önceki bağımsız ölçüm **v7 4/10** olarak kalır; bu değişikliğe ait yeni canlı skor yok.

## Yerelde düzeldiği gösterilenler

Önceki v7 call'larının kaydedilmiş ham guard girdileri yeni, değiştirilmemiş aday kodunda tekrar yürütüldü. PUB-04'ün `the sixth of November` tarihi **23 Ekim deadline readback'ine**, PUB-07'nin `Monday the twenty-sixth` tarihi **27 Ekim iş günü readback'ine** ulaştı. Tarihler önceden rakama çevrilmedi; record yetkisi açılmadı. Bunlar tarih kök nedeninin yerel düzeltme kanıtıdır, canlı PASS değildir.

PUB-09'un gerçek düşük taksit isteği ve yanlış `offer` etiketi artık `restructuring` transferine ulaşıyor. PUB-06'nın gerçekten boş taşınmış soru metni, minimumu tekrar teklif etmek yerine güvenli bir soru açıklamasına dönüyor; ikna sayacı değişmiyor. Normal minimum sorusu `question` ve boş etiketle yeni kontrolleri geçiyor; yanlış `no` etiketi aşağıda hâlâ sorun.

İlk code-exec hiç çalışmadan yapılan boş-state graph kontrolü değişkensiz, toolsuz `Please repeat your answer.` listener'ına ulaşıyor. Önceki PUB-08 ham timeout'u helper'da tam bir `code_execution_failure` diagnostic üretiyor. Normal başarılı kayıt → SMS → müşterinin hayır cevabı → literal kapanış kontrolü geçti; `cc09a5f` bu gecikmiş kapanışı kapsıyor. İlerleyen her aşamadaki altyapı hatası veya canlı değişken çözümü ayrıca ölçülmedi.

## Önce düzeltilecekler

### 1. [P1] Güncel soru ve AI cevabı bazı event etiketlerinde hâlâ kayboluyor

- **Nedir:** Üretilmiş `decision`, ham soruyu yalnız belirli event'lerde toparlıyor; AI cevap prefix'ini yalnız normalize event tam `offer` olduğunda readback'e taşıyor. Compiler sözleşmesi `builder/prompt.md:394–410`; bağımsız kontroller `builder/validation.py:1466` ve `builder/validation.py:1515`. Gerçek aday snippet satırları 159–177, 242–259 ve 526–530.
- **Sorun:** `What is the minimum payment?` + yanlış `event=no`, bankadaki minimumu cevaplamak yerine bir ikna girişimi harcıyor ve yeniden ödeme teklifi yapıyor. Tam güncel ödeme teklifi + robot sorusu + `event=yes`, doğru readback'e ulaşıyor ama digital-assistant cevabını söylemiyor. Aynı girdinin `event=offer` kontrolü cevabı koruyor. Bağımsız `independent_minimum_answer_wrong` ve `independent_ai_with_current_offer_offer` reddi haklı; ikinci check'in `offer` etiketi güvenilir `validation_events.yes` değerini kullanıyor.
- **En küçük düzeltme:** Yalnız güncel metinden çıkarılan soru/AI/ödeme niyetini, event'e bağlı birkaç ayrı branch yerine aşamanın kararına tutarlı biçimde taşı. Minimum cevabı sayaç veya yeni teklif üretmesin. Cevap prefix'i aynı güncel teklifin readback'inde event yazımından bağımsız korunsun; onay/kayıt yetkisi yine mevcut guard'lardan gelsin.
- **Yapılmazsa:** Extraction'ın tek etiketi kaçırması, aynı müşteri cümlesini farklı banka/konuşma davranışına yönlendirir.

### 2. [P1] Transfer reddi ve düşük taksit reddinin kapsamı eksik

- **Nedir:** Support reddi regex'i `want a transfer` gibi dar yazımları tanıyor. Plan negation yalnız `plan` nesnesini kapsıyor; `lower instalments` phrase'i olumlu talep gibi kabul ediliyor. Gerçek aday `decision` satırları 148–155 ve 210–214. Validator girdileri `builder/validation.py:1482` ve `builder/validation.py:1499`.
- **Sorun:** Rapordaki `No, thanks. Is there a discount?` hem kontrol hem replay'de kapanmıyor. Ayrıca **gerçek PUB-05** cevabı `No, I do not want to be transferred. Can you just give me a discount?` yeni kodda `listen` / `I do not have that information.` oluyor; beklenen `no_promise/hardship` kapanışı yok. Yeni bağımsız negatif örnek `I do not want lower instalments.`; `plan`, `question` ve boş event'in üçünde de **yetkili restructuring transferi** açıyor. Bu son iki yazım mevcut yeni validator örneklerinde yok.
- **En küçük düzeltme:** Pending support'ta kısa/pasif transfer reddini de anla; soruya cevap verirken kaynak kapanışını koru. Plan/taksit isteğinin kendi nesnesine bağlı retleri olumlu talepten önce ayır. Genel tutar reddi + gerçek düşük taksit isteği ve hardship + gönüllü ödeme önceliği korunmalı. Sadece bu iki eksik yazım için küçük bağımsız regresyon ekle; yanlış/boş event kombinasyonlarını da kullan.
- **Yapılmazsa:** Mevcut PUB-05 kusuru sürer; bir planı açıkça istemeyen müşteri yanlış transfer edilir. Mevcut dört reddi kapatmak bu iki örneği tek başına kanıtlamaz.

### 3. [P2] Soru işareti, açılış selamını bilgi sorusu yapıyor

- **Nedir:** Güncel metin ve boş event geldiğinde genel `?` kontrolü `Hello?` ifadesini `question` yapıyor; sonra bilinmeyen bilgi cevabı ekleniyor. Gerçek aday `decision` satırları 161–177; kaynak konuşma normalizasyonu `builder/prompt.md:392`.
- **Sorun:** Değiştirilmemiş `unknown_opening_first_answer`, beklenen isim sorusundan önce `I do not have that information.` duyuyor. Ham generated check ile replay aynı davranışı verdi. Müşteri bir bilgi sormamış; bu bir greeting/unclear cevabı.
- **En küçük düzeltme:** Selam ve belirsiz açılış cevabını noktalama üzerinden bilgi sorusuna çevirmeden kaynak isim-sorma bütçesinde işle. Gerçek AI/scam/diğer soruları cevaplamayı koru; güvenlik cevabını veya first-party onayını uydurma.
- **Yapılmazsa:** Daha görüşmenin başında istenmeyen cevap verilir; açılış ask bütçesi yanlış niyetle harcanır.

## Karar ve sonraki görev

**Karar: 1, 2 ve 3 düzelmeden aday yayımlanmasın.** Repair runner, timeout diagnostics ve kapanış regresyonunda kritik yeni hata bulmadım. Sözleşme/gate yönü doğru; gerçek model çıktısı kısmen uyuyor. Test sayısını artırmak veya başarılı tarih düzeltmesini yeniden yazmak şu an ana iş değil.

[CURRENT_INTENT_REPAIR_PROMPT.md](../CURRENT_INTENT_REPAIR_PROMPT.md): yalnız güncel niyet ayrımını üretim mantığında tamamla; aynı kaynaklı son, yakın-tam adaydan en fazla tek offline model repair ile tam geçerli aday teslim et. Üretilmiş JSON'u elle yamalama, kontrol beklentilerini gevşetme, yeni canlı test/publish açma. Sonraki canlı ölçüm ancak bu teslim ve review sonrasında yapılabilir.

Bağımsız ignored kanıt `build-the-builder/out/review-e655ed7/`: `affected-tests.log`, `verify_candidate.py`, `verification.json`, `candidate-validation.json` ve okunabilir snippet kopyaları. Script aynı adayda dört ret + AI event kontrolü, beş eski call durumu, üç taksit-ret varyantı ve ilk timeout graph'ını doğruluyor. Ham girdiler/adaylar Git ile paylaşılmaz; üretim koduna veya v7'ye dokunulmadı. Self-check ve diff-check geçti.

Kontrol edilmedi: yeni üretim, yeni canlı test, A+B, üç tekrar, tam unit suite, gizli brief üretimi ve v8 taslağı. Yerel olumlu kanıtlar canlı skor artışı garantisi değildir.
