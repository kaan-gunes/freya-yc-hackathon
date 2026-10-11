# Kaan V9: PUB-01 ve tam A canlı sonucu

11 Ekim 2026, Europe/Istanbul. Kullanıcının açık talimatıyla hazır aday yayımlandı,
PUB-01 bir kez çalıştırıldı; geçince aynı sürümde tam A bir kez çalıştırıldı.

**Gerçek sonuç: PUB-01 1/1; tam A resmî 9/10, banka 10/10.**
Önceki v7'nin resmî 4/10 sonucu tarihsel olarak korunuyor. Yeni sonuç V9'a ait.
PUB-06 resmî FAIL kaldı; banka sonucunu 10/10 resmî skor olarak sunmuyoruz.

## Aday, yayın ve sürüm kanıtı

- Kaynak commit `15c69c2bb704431b9c7d7850011e99e74bd7238e`, temiz worktree.
  Compiler uygulaması `d472fc2`; Claude'un iş kuralları seed'i `58eed9a`.
- Hazır aday: `build-the-builder/out/20261011T155956791672Z/`.
  SHA256 `1710420e88b6ab6a124a6adc21c2c10ff5f589dc90980ea22d50acec95ecee85`.
- Gerçek online builder run: `build-the-builder/out/20261011T160936816815Z/`.
  Aynı kaynak/hash/slot denetimiyle `--resume-build`; yeni generation/repair yok.
  Yerel 232/232 ve provenance 47/47 tekrar geçti; Freya dry-run kabul etti.
- Agent `404df3cd-803d-4656-89ac-ac122f9d31d2`;
  workflow `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`.
- **Yayımlı V9 ID `9e19551f-6382-4aac-9568-ae7ad60363d6`.**
  Önceki V8 yayımlanmamış taslaktı; test V8'de çalışmadı.
- Publish sonrası readback ve export gönderilen workflow alanlarını koruyor.
  Full A öncesinde yayımlı ID tekrar kontrol edildi. Aynı yerel kilit full A
  boyunca tutuldu; workflow'a test sırasında hiçbir güncelleme yapılmadı.
- PUB-01 ve full A'nın 11 ham call'ı V9 numarasını ve aynı version ID'yi
  doğruluyor. Full A'nın 10 iteration run'ı da aynı sürümü doğruluyor.
- Test sonrası GET: hâlâ V9 yayımlı, gönderilen workflow alanlarında fark yok,
  aktif simülasyon yok; workspace simülasyon toplamı 19'dan 21'e çıktı.

## Çalıştırılan testler

| Test | Resmî | Banka | Simülasyon süresi |
| --- | ---: | ---: | ---: |
| PUB-01, tek koşu | 1/1 | 1/1 | 42,66 saniye |
| Tam A, tek koşu | 9/10 | 10/10 | 106,47 saniye |

Online builder toplamı **63,66 saniye**. Tam A yardımcısının sonuçları okuma ve
puanlamayla birlikte duvar saati yaklaşık **134,91 saniye**. Bunlar farklı süreler.

- PUB-01: `build-the-builder/results/20261011T160954631854Z-404df3cd/`;
  simulation `85c54bb6-1266-4be8-865c-f5e458070706`,
  iteration `37fad9f7-eb60-4ffa-8cd5-23f54c3afa41`.
- Tam A: `build-the-builder/results/20261011T161152987319Z-404df3cd/`;
  simulation `e1413613-545f-4aea-ae67-d916f2702f34`,
  iteration `c953b529-3a63-4cd8-b997-83f6e05fa93d`.

| Vaka | Resmî | Banka sonucu |
| --- | --- | --- |
| PUB-01 | PASS | 420 / 14 Ekim; tek vaat |
| PUB-02 | PASS | Callback; kimlik/hesap erişimi yok |
| PUB-03 | PASS | Kimlik doğrulanmadı; doğru kapanış |
| PUB-04 | PASS | 1.250 / 23 Ekim; AI cevabı da söylendi |
| PUB-05 | PASS | Hardship; support reddinden sonra doğru kapanış |
| PUB-06 | **FAIL** | 637,50 / 16 Ekim doğru; konuşmada minimum iki kez teklif |
| PUB-07 | PASS | 540 / 27 Ekim; tarih/tatil akışı doğru |
| PUB-08 | PASS | Already-paid kapanışı; vaat yok |
| PUB-09 | PASS | Tek restructuring transferi; vaat yok |
| PUB-10 | PASS | 500 → güvenli retry → tek 365 / 16 Ekim vaat |

Değiştirilmemiş resmî scorer kullanıldı. Root, bilinen tamamlanmış iteration ve
ledger'ları yalnız GET ile tekrar aldı. Ayrı inceleme agentı on ledger'ı
`score_ledger` ile yeniden puanladı; banka AND konuşma hakemi sonucu bütün
resmî satırlarla birebir aynı. Kaydedilmiş vakalar resmî public A setiyle aynı.
Hakem veya zorunlu açılış değiştirilmedi.

PUB-01 smoke call'ında gerçek readback → güncel açık onay → tek başarılı kayıt
→ kayıt/SMS cümlesi → literal kapanış zinciri bağımsız doğrulandı. PUB-10'da ilk
500'den sonra hiçbir şeyin kaydedilmediği söylendi; başarı/SMS cümlesi yalnız
ikinci kayıt başarılı olduktan sonra geldi. Eski v7'nin PUB-10 hakem FAIL'i bu
koşuda tekrarlanmadı; bundan hakemin her gelecekteki koşuda geçeceği çıkarılmaz.

On full A çağrısında çözülmemiş `{{...}}` **0**, diagnostics **0**, okunamayan
transcript **0**. Hepsi asistanın kapanışıyla bitti. Her çağrının en yavaş asistan
turunun medyanı **3,8 saniye**, en kötü değer **5,6 saniye**. Bu metrik eski
arşivdeki bütün kullanıcı → sonraki konuşma aralıklarının medyanıyla aynı ölçü
değildir; kontrolsüz bir hız karşılaştırması yapılmadı.

## Kalan PUB-06: kayıp güncel metin ve tekrar teklif

Call `9e0d8e69-eda1-4a48-b720-682dd15087a6` gerçek bir tekrar gösteriyor.
Hakem yalnız bilgi cevabını teklif sanmıyor:

1. **12,05 s:** “Can you pay 637.5? The rest stays overdue.”
2. **14,04 s:** müşteri “You tell me.”
3. Extraction yalnız `speech_event=non_answer` döndürdü; `speech_text` gelmedi.
4. **15,77 s:** “Can you pay 637.5 on 2026-10-16? The rest stays overdue.”

Decision girdisi `stage=payment`, `floor_offered=yes`, `full_too_much=yes`,
`persuasion_attempts=0`, `speech_event=non_answer`, `speech_text=''`.
Kod boş güncel metne rağmen non-answer etiketini ret sayıyor; attempt 1'e
geçip Friday ve floor seçiyor. Sonraki gerçek TTS minimumu tekrar teklif ediyor.
Listen alanı en son metnin aynen taşınmasını istiyor; bu canlı turda extraction
sınırı bu sözleşmeyi sağlamadı. Mevcut missing-question testinin non-answer
eşleniği yok. Minimum soru testleri bu gerçek girdi biçimini kapsamıyordu.

`speech_text` ve `speech_event` alanlarında bunu açıklayan extraction condition
yok; her ikisi `min_confidence=0.0`, `max_retries=1`. Event açıklaması da gerçek
kasıtlı non-answer'ı eksik extraction'dan ayırmayı istiyor. Bu açıklama tek başına
runtime'da alanın eksiksiz yazılmasını garanti etmiyor; karar kapısı doğrulamalı.

Kaynak kuralı da korunmalı: Brief A kural 26 floor'u bir kez teklif etmeyi,
kural 30 gerçek flat refusal/non-answer'da attempt 1'i ve full-too-much ise
floor tutarını kullanmayı söylüyor; attempt 2 için ayrıca floor istisnası var.
Public hakemin “exactly once” kriteri bu bağlamı aynı biçimde değerlendirmiyor.
Bu yüzden sonucu kesin banka kuralı ihlali veya kesin hakem hatası diye
etiketlemiyoruz; resmî FAIL aynen kalıyor.

**Sıradaki dar düzeltme:** floor-sonrası `non_answer` etiketi var ama güncel
metin boşsa bunu kanıtlanmış müşteri reddi sayma. Eksik extraction olarak
literal açıklama iste; mevcut teklif, floor ve persuasion sayacını koru.
Metni taşınmış gerçek non-answer'da kural 30 akışını koru. “You tell me” için
özel hardcode, sayacı sıfırlama, tutarı konuşmadan gizleme veya scorer değişikliği
önerilmiyor. Bu turda kaynak kod veya yayımlı aday değiştirilmedi.

## Çalışma ve açık sınırlar

Görüşme, müşteri simülasyonu ve konuşma hakemi Freya'da çalışır. Yerel komut
durumu izler, sonuçları indirir ve banka scorer'ını çalıştırır. Görüşme sırasında
yerel bir Kaan servisi yok; kontrol kodu yayımlı workflow içinde taşınır.
Chat'in sürekli düşünmesi görüşmeyi çalıştırmaz. Yerel izleme durursa sonuç
toplama eksik kalabilir; bilinen simulation ID üzerinden yalnız GET resume
yapılabilir, yeni bir simülasyon oluşturmak gerekmez.

İstenen sıra tamamlandı: toplam **iki simülasyon, 11 çağrı**, bir publish edilen
sürüm; yeni model çağrısı veya üçüncü test yok. A+B, üç tekrar, ek stiller ve
yeni/gizli brief güvenilirliği test edilmedi. 9/10 tek tam A ölçümüdür.

Ham transcript, ledger, iteration, export, trace ve anahtarlar Git dışında.
Bağımsız kanıtlar her result klasörünün `independent-review/` altında;
pre/postflight `build-the-builder/out/kaan-live-preflight/` altında.
