# V10 kaynak düzeltmesi ve canlı sonuç — 11 Ekim 2026

**Son gerçek sonuç: V10 tam A resmî 8/10, banka 10/10.** Önce tek PUB-06 resmî/banka 1/1 geçti; ardından sürümü değiştirmeden tek tam A çalıştırıldı. Bu sonuç V9'un önceki 9/10 ölçümünün yerini alan güncel ölçümdür. PUB-06 tamamen kapanmadı; PUB-10 ayrıca hakem uyuşmazlığı nedeniyle FAIL oldu. Üçüncü simülasyon başlatılmadı.

## Kaynak değişikliği

`builder/compiler.py`, doğrulanmış ödeme aşamasında `non_answer` etiketiyle güncel metin/tutar/tarih bulunmadığında literal tekrar ister. Öneri tutarı/tarihi, minimum teklif durumu ve ikna sayacı korunur; kayıt yetkisi açılmaz. Gerçek metni bulunan `non_answer` kaynak A30 ikna akışını korur. Müşteri cümlesi özel durum olarak kodlanmadı; scorer ve zorunlu açılış değiştirilmedi.

Derleyici ödeme aşamasını fixture'dan, dinleme rotasını gerçek graf geçişinden alır. Teklif dönüşü ve güncel onay güven kapıları korunur. Eski generated checks ve brief/API girdileri değişmedi.

İlk yeni derleme, dinamik `vars[name]` yazımını taşınabilir Python sınırında reddetti; aday yayımlanmadı. Derleyici sabit alan yazımları üretecek şekilde düzeltildi. Test artık derlenmiş karar kodunu `_parse` + `_writes` sınırından geçiriyor.

| Doğrulama | Sonuç |
|---|---|
| Odaklı compiler/onay testleri | 17/17 PASS |
| Gerçek V9 PUB-06 girdisi replay | Boş/whitespace metinde teklif 637,50 / 14 Ekim ve sayaç 0 korunuyor; literal tekrar; yetki yok |
| Metni dolu gerçek non-answer replay | A30 ikna dalı korunuyor; sayaç artıyor ve cuma teklifi yapılabiliyor |
| Gerçek builder kaynak derlemesi | 234/234, provenance 47/47, graf geçerli; 27,92 saniye |
| Freya dry-run/readback/export | PASS |
| Tek PUB-06 | Resmî 1/1, banka 1/1 |
| Aynı V10 tek tam A | Resmî 8/10, banka 10/10 |

Kaynak commit `890e8d90fbe1842329d6f14f48404cf0b029ace1`, clean worktree. Derleme ve publish/resume yeni model çağrısı yapmadı. Aynı girdili mevcut aday kaynak koda göre otomatik derlendi; workflow elle düzenlenmedi. PUB-06 publish/resume koşusu 99,79 saniye sürdü.

## PUB-06 tek testin kapsamı

Call `58d459ed-201b-4721-b5f8-d4566456131f`: 11,287 saniyede minimum yalnız bir kez teklif edildi; kalan borcun gecikmede kaldığı söylendi. 17,248 saniyede minimum müşterinin sorusuna cevap olarak belirtildi. 19,427 saniyede 637,50 / 16 Ekim readback; 21,571 saniyede güncel onay; tek başarılı kayıt ve ardından SMS cümlesi.

**Yeni boş `non_answer` dalı bu çağrıda çalışmadı.** Boş extraction `question` olarak geldi; mevcut güvenli question açıklaması soruyu tekrar istedi. İki `decision_fallback` diagnostics kaydı bu açıklama yoluna ait. Yeni dalın kanıtı kayıtlı V9 girdisiyle yerel replay'dir; tek canlı PASS yeni dalın canlı kanıtı gibi sunulamaz.

## Tam A'da kalan iki FAIL

**PUB-06 gerçek tekrar:** Call `09b7d767-3f87-4b83-9a5b-96b5cef6c69c`.

- 10,196 saniye: ilk minimum teklif.
- 12,519 saniye: müşteri “You tell me.”
- 12,815 saniye: extraction `non_answer` ve **dolu güncel metin** taşıyor.
- Yeni boş metin koruması bu girdiye uygulanmıyor.
- 13,098 saniye: mevcut kaynak ikna dalı sayacı 0 → 1, tarihi bugün → 16 Ekim yapıyor.
- 13,109 saniye: minimum yeniden teklif ediliyor. Banka tek doğru 637,50 / 16 Ekim kaydı tutuyor, fakat konuşma kriteri FAIL.

Eksik metin hatası kaynakta düzeltildi; dolu metinli non-answer/geri soru ayrımı ve ilk minimum tekliften sonraki A26/A30 davranışı hâlâ açık. A30'un meşru iknasını sessizce silmek veya cümleye özel hardcode eklemek çözüm diye sunulmamalı.

**PUB-10 hakem uyuşmazlığı:** Call `130edfa5-7166-4d1a-ae5d-45c802b52ead`. Ham hakem gerekçesi, zorunlu “this call is recorded” açılışını başarılı `create_promise` öncesinde vaat kaydı iddiası sayıyor. Gerçek araç kayıtları 500 → güvenli retry → 200; tek doğru 365 / 16 Ekim vaadi var. 20,256 saniyedeki ödeme kaydı/SMS cümlesi başarılı API çağrısından sonra. Bu kanıt skor gerekçesiyle uyuşmuyor; **resmî FAIL ve toplam 8/10 değiştirilmedi**. Zorunlu açılış kaldırılmadı.

Diğer sekiz vaka PASS. Tam A'da tüm ledger'lar doğru, placeholder ve diagnostics sıfır, eksik transcript veya müşteri kapanışı yok. Her çağrının en yavaş turunun medyanı 5 saniye, en kötü 7 saniye. Bu tek ölçüm tekrarlarda garanti değildir.

## Sürüm ve bağımsız kanıt

- Agent: `404df3cd-803d-4656-89ac-ac122f9d31d2`
- Workflow: `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`
- V10 ID: `2cde6d00-bc31-4d26-8d05-e53b4d89f72b`
- PUB-06 simulation: `2ab26fc3-99e5-408e-a309-3d8c67ce1734`; iteration: `df6874aa-ce99-46f1-aa1c-1bcac559ce2d`
- Tam A simulation: `3075685b-1c4e-4cbd-a92f-732d1d3477af`; iteration: `3e7ae8c6-e5fc-4b78-ba1c-30173e64107b`

Tam A boyunca yerel ortak builder kilidi tutuldu; yayınlanan sürüm test öncesi ve sonrası aynı ID ile doğrulandı. Her call/iteration aynı V10'u taşıyor. Bağımsız doğrulama tamamlanmış iteration ve banka ledger'larını GET ile aldı; resmî scorer'ı aynı verilere tekrar uyguladı; resmî satırlarla birebir eşleşti ve resmî sonuç dosyasını değiştirmedi. İkinci okuyucu ham konuşmaları ve iki FAIL'i ayrıca inceledi.

Yerel ham kanıt yolları, Git dışında:

- Derleme: `build-the-builder/out/20261011T163212402703Z/`
- Publish, export ve trace: `build-the-builder/out/20261011T163314424796Z/`
- Kaydedilmiş V9 girdisi replay: `build-the-builder/out/kaan-pub06-source-replay/actual-v9-input-replay.json`
- PUB-06: `build-the-builder/results/20261011T163339422212Z-404df3cd/`
- Tam A: `build-the-builder/results/20261011T163524105863Z-404df3cd/`
- İki sonuç klasörünün `independent-review/`: ham iteration/ledger ve `score-verification.json`.

## Final teslimine etkisi

Bu practice A sonucu final teslim değildir. Canlı resmî sayfaya göre final Türkçe vaka 20:00 İstanbul'da açılır, teslim 23:00'te kapanır. Klasör/karma belge girişi, Türkçe onay/tarih uyumu, Workers mock ve final export/trace paketi henüz tamamlanmadı. Ayrıntılar [final teslim hazırlığı](final-submission-readiness.md).

Core ekip bilgileriyle yerel `build-the-builder/out/submission-prep/submission.draft.json` hazırlandı; final commit/run_command/workflow/trace/mock_url alanları boş, alıcı adresi eksik. E-posta veya final submission gönderilmedi. A+B, üç tekrar, stiller ve yeni final girdisinden üretim bu turda çalıştırılmadı.
