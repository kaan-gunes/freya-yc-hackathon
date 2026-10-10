# Builder incelemesi — 9046149

İncelenen değişiklikler: `a61056e..9046149`. İnceleme, yerel kod/testler ve Freya'dan salt okunur alınan yayımlanmış workflow/görüşme kayıtlarına dayanıyor. Üretim kodu veya Freya agentı değiştirilmedi; yeni simülasyon ve builder model çağrısı başlatılmadı.

**Sonuç:** Girdi dosyalarından üretim, süre bütçesi, publish/readback/export ve temel guard kontrolleri kurulmuş. Mevcut 20 repository testi geçiyor. Ancak ilk canlı görüşmede brief dışı güvenlik sorusu sorulmuş; ayrıca durum aktarımı ve doğrulama kontrollerinde tekrarlanabilen açıklar var. PUB-01'in üç tekrarda geçmesi hedefi henüz sağlanmadı.

## Kurtarılan canlı kayıt

Önceki [ilk builder raporu](first-builder-result.md), test okumalarının 503 ile kesildiği anı anlatıyor. İnceleme sırasında aynı simülasyonun son durumunu okuyabildik:

| Alan | Değer |
|---|---|
| Agent | `404df3cd-803d-4656-89ac-ac122f9d31d2` |
| Workflow | `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d` |
| Simülasyon | `c69cae64-1161-4984-9097-a07e907e44eb` |
| Iteration | `8b4bd945-e9f1-48c5-b0cf-7a032abd57a8` |
| Görüşme | `9d7195b6-72e3-4558-a703-e72e330b765a` |
| Simülasyon durumu | `completed` |
| Run değerlendirmesi | `inconclusive`; reason `null` |
| Test edilen sürüm | Run `agentVersionNumber: 1`; call `entityVersionNumber: 1` |
| Görüşme analizi | `successEvaluation.success: false` |

Bu okumalar tam resmî ledger skoru değildir. Banka ledger'ı yeniden puanlanmadı; **0/1 veya 1/1 gibi tamamlanmış bir skor iddia etmiyoruz**. Görüşmedeki politika hatası ise doğrudan görülebiliyor.

Kısa konuşma:

```text
Agent: I am a digital assistant calling from Freya Bank, and this call is recorded.
       Am I speaking with Mr Reyes?
Müşteri: Yes, this is Daniel Reyes.
Agent: Am I speaking with Mr Reyes?
Müşteri: Yes, that's me.
Agent: Thank you, Mr Reyes. Please provide the last four digits of your Social Security number.
Müşteri: I don't have that information.
Agent: Thank you. Goodbye.
```

Yerel tam kanıtlar `build-the-builder/out/review-9046149/` altında, Git dışında. Diğer bilgisayar bu dosyalara sahip olmayabilir; yukarıdaki kimliklerle aynı Freya kayıtları okunabilir. İncelemede kullanılan üretim mantığının kaynakları repoda bulunuyor. Ham trace ve tam export teslim için ayrıca korunmalı.

## Öncelikli bulgular

### 1. P1 — Yanıt işleme başarısız olduğunda konuşma modeli yeni bir güvenlik sorusu uyduruyor

**Gözlenen:** İlk açık isim teyidi extraction sonucunda `speech_event="none"` olmuş; bu değer opening enum'unda yok. İkinci açık teyitte extractor doğru `party_yes` üretmiş ama `0.679170276` güveni `0.7` eşiğinin altında kaldığı için atılmış. `talk` düğümündeki `matches_intent` de eşleşmeyince dialogue modeli SSN sorusuna geçmiş. Mevcut Brief A doğum tarihi, sonra telefonun son dört hanesini istiyor; SSN istemiyor.

**Etkisi:** Deterministik kontrollerin çevresinde serbest bir konuşma yolu kalmış. Doğru müşteri cevabı bile yanlış akışa düşebiliyor.

**Düzeltme yönü:** Her yeni cevabın güncel bir karar olarak işlenmesini ve extraction/router başarısızlığında güvenli bir cevap verilmesini sağla. Aşamanın izin verdiği sorular somut olarak bilinsin. Düşük güven veya enum dışı çıktı, yeni bir güvenlik alanı seçme yetkisi vermesin. Her aşama için kısa bir fallback ve mesaj güncelliği sözleşmesi kur. Confidence eşiğinin tek başına değiştirilmesi bu kaçış yolunu kapatmaz.

Kaynak: gerçek `opening`/`talk` düğümleri ve call logu; [builder promptu](../builder/prompt.md#L175), aynı prompttaki conversation fallback sınırlaması yaklaşık satır 229. `global_nodes` bu export'ta boş. Bir bütün olarak bütün conversation düğümlerine koşulsuz rota eklemek de doğru çözüm değildir; araç sonucu ve giriş davranışlarıyla birlikte test edilmeli.

### 2. P1 — Tarih alanlarını boş string ile temizlemek sunucuda reddediliyor

**Gözlenen:** Gerçek `code_exec` sonuçları `status: success` derken şu uyarıları da içeriyor:

```text
variable 'speech_date' rejected by schema validation
variable 'confirm_date' rejected by schema validation
```

Kod bu alanlara `''` yazıyor, alanlar ise date şemasına sahip. Yerel `_run_check` düz dictionary üzerinde çalıştığından Freya'nın bu tip denetimini taklit etmiyor.

**Somut replay:** Aynı `decision` kodunda, doğrulanmış müşterinin `speech_event="refuse"` cevabını iki kez denedik. `speech_date=""` iken `route=talk`, ikna sayısı 1. Önceki turdan `speech_date="2026-10-16"` kalınca `route=offer_guard`, eski tarih yeni öneri gibi işleniyor ve sayaç artmıyor. Eski `confirm_date` de yeni onayı yanlışlıkla correction yapabilir.

**Düzeltme yönü:** Alan temizleme yöntemini gerçek platformda doğrula. Her konuşma çıkarımının hangi mesajdan geldiğini veya tüketilip tüketilmediğini açıkça izle; eski değeri yeni cevap gibi kullanma. `code_exec` uyarıları ve güvenlik açısından kritik reddedilen yazılar rapora dahil olsun. `success` zarfı durum güncellemelerinin tamamının uygulandığı kanıtı sayılmasın.

### 3. P1 — Tamamlanmış kimlik doğrulaması, araya giren sorudan sonra hesap aşamasına ulaşamayabiliyor

Bu sorun önceki raporda zaten belirtilmiş; gerçek yayımlanmış `decision` koduyla bağımsız olarak tekrarlandı.

**Replay:** `stage=identity`, `bank_verified=verified`, `identity_status=verified`. Müşteri bir soru soruyor: `speech_event=question`. Kod soruyu yanıtlayıp eski telefon sorusunu tekrar ediyor, `stage=identity` kalıyor. Sonraki `answer` turunda doğrulanmamış kimlik dalı artık geçerli olmadığından kod ödeme dalına sarkıyor; boş ürün listesi nedeniyle `end/no_promise/service_error` çıkıyor.

**Düzeltme yönü:** Kimlik tamamlanması ve sonraki aşamaya geçiş tek bir tutarlı state değişimi olsun. Sorular ve diğer izinli araya girişler, doğrulanmış kimliği tekrar sormaya veya geçersiz bir ara durumda bırakmaya neden olmasın. Kritik istisnaları yine brief'in önceliğine göre işle.

### 4. P1 — Onayda tutar içeren bir transfer talebi normal düzeltmeye dönüşebiliyor

**Replay:** Geçerli 420 tutarlı teklif okunmuşken müşteri yeni bir ödeme planı ve 100 tutarından bahsediyor. `confirm_event=plan`, `confirm_correction=yes`, `confirm_amount=100`. Yayımlanmış `approval_guard`, önce correction dalına giriyor; `offer_guard → confirm` ile 100 tutarlı yeni söz öneriyor. `plan` olayı bu arada temizleniyor. Brief A41'e göre restructuring transferi gerekir.

**Düzeltme yönü:** Birleşik niyetlerde istisna önceliği ve parametre düzeltmesini birlikte işle. Özellikle human/plan/hardship/dispute gibi olaylar, yanlarında tarih veya tutar olduğu için kaybolmasın. Hardship + gönüllü teklif istisnasını da koru; bütün birleşik ifadeleri aynı transfer kuralına indirgeme.

Kaynak: gerçek `approval_guard` kodunun correction dalı exception dalından önce. [Prompttaki onay tanımı](../builder/prompt.md#L134) ile [istisna önceliği](../builder/prompt.md#L179) birlikte tutarlı bir davranış üretmeli.

### 5. P1 — Validator tek tek guard testlerini geçirip güvensiz bir zinciri kabul edebiliyor

[validation.py](../builder/validation.py#L504) üretilen testleri ayrı snippet üzerinde çalıştırıyor. Aynı model hem kodu hem test/expected değerlerini üretiyor; sabit test kategorileri mevcut ama zincir kontrolü eksik.

Mevcut [valid test fixture](../tests/test_builder_validation.py#L43) ile tekrarlandı:

```text
validate(candidate()).ok = true
Başlangıç: amount=1, date=2026-10-14, approval=yes
offer guard sonrası: record_authorization=''
approval guard sonrası: record_authorization='authorized'
```

Yani geçersiz tutar sonraki guard'da yeniden yetki kazanabiliyor. **Bu örnek yayımlanan v1'de geçersiz tutarın kaydedildiğini kanıtlamıyor:** v1 approval guard tutar/tarihi yeniden kontrol ediyor. Validator'ın kusurlu adayları eleme kabiliyetindeki boşluğu kanıtlıyor.

**Düzeltme yönü:** Builder kodundan bağımsız beklenen sonuçlarla aynı state üzerinde offer → readback → approval → record ve exception/retry yollarını test et. Geçerli teklifin kaydolabildiği pozitif kontrolü de bulunsun; her şeyi reddeden agent güvenli görünüp işe yaramaz. Guard'ın grafikte gerçekten zorunlu ve erişilebilir olduğunu denetle.

### 6. P2 — Servis hatasında, başlamış/tamamlanmış simülasyonun kimliği kaybolabiliyor

[test_agent.py:187](../scripts/test_agent.py#L187) önce `original_run_once` sonucunu bekliyor. Resmî runner, simülasyonu çalıştırdıktan sonra iteration ve ledger okuyor. Bu okumalardan biri hata verirse wrapper henüz hiçbir simülasyon kanıtını kaydetmemiş oluyor.

**Offline mock:** Tamamlanmış bir simülasyon sonrası ledger GET503 → exit 2, `blocked_by_bank`, `simulations=[]`, boş `calls`. Simülasyon/iteration kimliği özet kaydında yok. Polling sırasında hata olursa aynı kayıt eksikliği daha erken oluşabiliyor.

**Düzeltme yönü:** Session/simulation/iteration kimlikleri bilinir bilinmez kalıcılaştırılsın. Görüşmenin çalışması, banka kayıtlarının okunması ve puanlanması ayrı durumlar olsun. Servis düzeldiğinde mevcut koşu okunup tamamlanabilsin; belirsiz POST veya yazma işlemi otomatik tekrarlanmasın.

### 7. P2 — Sürüm kanıtı kısmi metadata hatasında atılıyor; call alanı da tanınmıyor

[test_agent.py:194](../scripts/test_agent.py#L194) simulation metadata ve iteration okumasını aynı try içinde yapıyor. İlkinde v7 elde edilip ikincisi hata verirse ilk kanıt da kullanılmıyor. Offline mock'ta tamamlanmış 1/1 sonuç, sürüm kanıtı boş diye builder tarafından reddediliyor.

Ayrıca iki [version_numbers](../scripts/test_agent.py#L62) uygulaması yalnız `agentVersionNumber` arıyor. Gerçek call dosyasındaki alan `entityVersionNumber`; v1 çağrısında bu alan 1. `version_numbers({"entityVersionNumber": 1})` boş liste üretiyor. Bu çağrının sürümü iteration'dan doğrulanabildi; bu nedenle mevcut kaydın sürümünü bilinmiyor saymıyoruz.

**Düzeltme yönü:** Her başarılı kaynaktan gelen kanıtı ayrı biriktir. Call alanını bağlamını kontrol ederek tanı; simulation/call/agent kimliğini ve sürümü eşleştir. Aynı numaralı ilgisiz nesne veya güncel dashboard sürümü test sürümünün kanıtı olmasın.

## Validator'da ek sınırlar

Şunlar canlı müşteri hatası olarak gözlenmedi; geçerli aday fixture'ına yapılan offline değişikliklerin validator tarafından kabul edilmesiyle gösterildi:

- API URL kontrolü statik default'a bakıyor. `verify_identity` pre-hook'unda `config['url']='https://example.invalid/not-bank'` hâlâ kabul ediliyor. [URL kontrolü](../builder/validation.py#L370), hook sonrası değişmezliği sağlamıyor. Hiçbir dış istek gönderilmedi.
- `vars` yazma sahipliği walrus alias'ı veya keyword argümanıyla aşılabiliyor. [AST kontrolü](../builder/validation.py#L90) bunu tek writer garantisi olarak sunmamalı.
- Callback/transfer için gerekli guard ve trusted alan bağları, promise kadar denetlenmiyor. Guard'sız, konuşmadan alınan tarih/saatle callback adayı kabul edildi. [Action manifest](../builder/validation.py#L467).
- Offer guard'ı erişilemez bırakmak veya unconditional passthrough döngüsü oluşturmak kabul edilebiliyor. Grafikte guard zorunluluğu ve terminale ulaşma denetlenmeli.
- `f=datetime.date.today; f()` gibi fonksiyon alias'ı gerçek saat yasağını aşabiliyor. [Çağrı kontrolü](../builder/validation.py#L82).

Bunlar için genel bir Python güvenlik motoru yazmak zorunlu değil. Küçük bir desteklenen kod alt kümesi, sabit yardımcılar veya gerçekten uygulanan alan/işlem yetkileri değerlendirilebilir. Kontrollerin garanti ettiği sınır ile yalnız uyardığı sınır açıkça ayrılmalı.

## Sonraki geliştirme sırası

1. Canlı SSN hatasını, tarih güncelliğini, kimlik dönüşünü ve onay istisnalarını kapat.
2. Bu hataları yakalayan bağımsız, ardışık state/graph kontrollerini ekle; geçerli happy path'i de koru.
3. Aynı sürüme ait tek PUB-01 sonucu, ardından ayrı geliştirme testinde üç tekrar al.
4. A'nın kalan vakalarına, özellikle hata/retry ve konuşma çeşitlerine genişle; sonra A+B kapsamını tamamla.
5. Kontrol mimarisini sade tut; ayrı LLM şefi ve agresif context kırpmayı ölçümden sonra ele al.

Ekip aynı banka takım anahtarını özel kanaldan kullanmalı; önceki rapor diğer bilgisayarda örnek anahtar bulunduğunu belirtiyor. Bu incelemede anahtar değeri paylaşılmadı veya değiştirilmedi. Yeni özellik eklemeden önce tek test koşusunun üretilen doğru sürümü gerçekten değerlendirdiğini ve hata durumunda kanıtını koruduğunu göstermeliyiz.
