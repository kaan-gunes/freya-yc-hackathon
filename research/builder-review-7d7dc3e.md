# Validator düzeltmeleri ve üretim blokajı incelemesi — 11 Ekim 2026

İncelenen HEAD `7d7dc3e`, uygulama commit'i `bd2bb29`; karşılaştırma tabanı `e9352ae`. Üç bağımsız inceleme koluyla kaynak, regresyonlar ve teslim raporu kontrol edildi. Production kodu değiştirilmedi; model/Freya/banka çağrısı veya canlı test başlatılmadı.

**Karar:** Önceki iki açık, desteklenen kaynak biçimi içinde kapanmış. Yeni teslim henüz çalışan yeni agent vermiyor: raporlanan tek builder çalışması yerel validation'da durmuş. Tarih düzeltmesi testindeki yanlış ret bağımsız bir sentetik örnekle doğrulandı; sıradaki dar iş bu kontrolü düzeltmek.

## 1. [P1] Yeniden okunan teklif aynı tarihe dönüyorsa validator güvenli akışı reddediyor

[`unmarked_correction`](../builder/validation.py#L910), fixture tarihine bir gün ekleyerek yeni müşteri talebi üretir. [934. satır](../builder/validation.py#L934), tekrar okunan teklifin fingerprint'i eskisiyle aynıysa adayı reddeder. Fingerprint ürün/tutar/tarihi temsil eder; yeniden okuma gerçekleştiğini tek başına temsil etmez.

Brief A [kural 23](../build-the-builder/briefs/brief-a.md#L66), müşteri son tarihten sonraki bir gün isterse son tarihi yeniden teklif etmeyi gerektirir. İlk teklif zaten son tarihteyse şu güvenli akış mümkündür:

1. Müşteri daha geç tarih ister; eski kayıt yetkisi ve iki fingerprint temizlenir.
2. Offer guard geç tarihi kabul etmez, izin verilen son tarihi yeniden teklif eder.
3. Gerçek confirmation node'una girilir; henüz kayıt yetkisi yoktur.
4. Yalnız yeni müşteri onayı kayıt yetkisini açar.

Tutar ve kabul edilen tarih aynı kaldığı için yeni fingerprint'in eskisiyle aynı olması normaldir. Validator bunu eski onayın taşınmasıyla karıştırıyor.

**Bağımsız offline kanıt:** Test adayına kural 23'ün son tarihe geri dönme davranışı eklendi. İç tarihteki kontrol adayı geçti. Aynı kodda ilk teklif son tarihe taşınınca yalnız `independent_approval_date_missing_correction_marker` ve `independent_approval_date_wrong_correction_marker` başarısız oldu. Her iki marker durumu için gerçek guard ve graph geçişleri replay edildi: temizleme, yeniden confirmation, yeni onay öncesi yetkisizlik ve yeni onay sonrası kayıt yolu doğrulandı. API çağrısı yapılmadı.

Bu sentetik örnek validator kusurunu doğrular. Arkadaşın bilgisayarındaki son generated workflow burada bulunmadığından onu bağımsız incelemiş saymıyoruz. [Teslim raporunun](validator-fix-live-result.md#L58) 23 → 24 → 23 Ekim açıklaması aynı mekanizmayla tutarlı.

**Beklenen düzeltme:** Değişen kabul edilmiş tarih için geçerli bir test girdisi kullan; son tarih sınırını ayrıca kapsa. Eski yetkinin temizlenmesi, offer doğrulaması, gerçek yeniden okuma ve yeni onay gereksinimini koru. Yalnız `fingerprint != original` koşulunu kaldırıp bayat onay testlerini gevşetmek yeterli değil. Aynı tutar/tarih yeniden okunabilir; yeniden okunmadan veya yeni onay olmadan kayıt açılamamalı.

## Önceki bulguların durumu

- **Kimlik override:** Orijinal kaynak, daha yüksek input önceliği ve açık numaralı kural referansı taşıyan memo kabul ediliyor. `replaces`, `replaced_by` ve iki ilişkinin birlikte kullanımı geçti; temelsiz kaynak/yanlış kural/yanlış brief/öncelik/ID örnekleri reddedildi. Eski repro'daki açık replacement referansı olmayan memo artık desteklenen pozitif sözleşme değildir; genellemenin her prose biçimini kapsadığı iddia edilmiyor.
- **Business-failure retry:** Önceki 25 → 999 mutantı artık reddediliyor. Normal aday geçiyor; hem ikinci başarısızlık hem ikinci denemede başarı kontrolleri değişmiş isteği yakalıyor. Yeni regresyon ürün/tutar/tarih mutasyonlarını kapsıyor. Timeout, sınırlı retry ve post-hook atlanan HTTP-error yolları kontrol adayında geçiyor.

Ek kapsam notu: Replacement denetimi `_identity_requirements` içinde bütün kaynak kurallarına uygulanıyor. Gerçek B9/A39 ilişkisi açık numaralı referans içermediğinden metadata ile bağlanınca reddediliyor; metadata olmadan aynı sentetik aday geçiyor. Yeni compiler promptu bu tür linkleri zaten kısıtlıyor. Bu mevcut A üretim blokajı değildir ve gerçek A+B başarısı/başarısızlığı ölçülmedi. Diğer memo biçimleri ve kimlik dışı provenance, genelleme aşamasında ele alınmalı; bu dar tarih düzeltmesini genişletmek gerekmiyor.

## Test ve üretim kanıtı

| Kontrol | Sonuç ve sınır |
| --- | --- |
| Bu review: focused inputs + approval/retry | **17/17**, 22.325 saniye |
| Bu review: builder self-check ve diff-check | Geçti |
| Bağımsız retry, identity override ve deadline repro'ları | Yukarıdaki sonuçlar doğrulandı; offline |
| Geliştiricinin raporladığı yerel testler | 92 farklı test geçti; üç tekrar dahil 95 execution. Sayım kaynakla doğrulandı; bütün pass logları burada yok |
| Geliştiricinin tek builder çalışması | Rapora göre 996.41 saniye, bir generation + iki bounded repair; final local validation 166/168 |
| Yeni publish/PUB-01/tam A | **Yapılmadı; yeni skor yok** |

`scripts/build_agent.py` bu teslimde değişmedi. Kaynak akışında local validation geçmeden dry-run ve publish'e erişilmiyor; üçüncü başarısız adaydan sonra duruluyor. Raporun yeni workflow/agent/version/simulation ID üretilemediği beyanı bu akışla tutarlı.

Ham build klasörü `/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/out/20261011T100012806452Z/` ve preflight logları bu checkout'ta bulunmuyor. 996.41 saniye, attempt sonuçları ve son adayın ayrıntıları geliştiricinin raporuna dayanıyor. Rapordaki Freya preflight bağlantı sorunu ayrıca var; build'i durduran neden yerel doğrulama. Bu sonuç **0/1 veya 0/10 değildir**. Son bilinen canlı v6'nın eski 3/10 skoru yeni kaynakla karıştırılmamalı.

## Sıradaki iş ve yerel artefaktlar

Tarih kontrolünü küçük olumlu/olumsuz regresyonlarla düzelt → ardından bir yeni builder çalışması ve yayımlanabilirse aynı sürümde bir tam A testi → sonuçları teslim et. Canlı başarısızlık sonrası otomatik üretim/test döngüsü veya A+B geliştirmesi başlatılmamalı. Production workflow'u elle değiştirmek gerekmiyor.

Ignored `build-the-builder/out/review-7d7dc3e/` altında `deadline-readback-repro.py/json`, `business-retry-repro.py/json` ve `identity-override-review.py/json` bulunur. Validator SHA256: `5ce6439a0e90e078faa9d2b27bd5e0a6699634883c068f391544f35f83031241`. Bu artefaktlar yerel; Git ile paylaşılabilir sonuç bu rapordur.
