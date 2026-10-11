# Focused düzeltme incelemesi — 11 Ekim 2026

İncelenen HEAD `484e6b2`, uygulama commit'i `f22ea8b`; karşılaştırma tabanı `e747763`. Kaynak, validator ve test yardımcısı üç bağımsız inceleme koluyla kontrol edildi. Bu görevde production kodu değiştirilmedi; yeni model çağrısı, agent üretimi, publish, simülasyon veya banka yazması yapılmadı.

**Karar:** Önceki review'un önemli boşluklarına somut yerel kontroller eklenmiş. İki dar validator açığı kaldı. Bunlar kapatıldıktan sonra yeni agent üretip canlı sonucu ölçmek gerekiyor; kaynak testlerinin geçmesi yayımlanmış agentın düzeldiğini kanıtlamıyor.

## Bulgular

### 1. [P1] Yeni memo kimlik kuralını değiştirse de validator eski soruları zorunlu tutuyor

[`_identity_requirements`](../builder/validation.py#L382), her kaynak kuralından soru türü ve sayısı topluyor. [402–410. satırlardaki döngü](../builder/validation.py#L402) `replaces/replaced_by` ilişkisini dikkate almıyor. Oysa [compiler promptu](../builder/prompt.md#L43), geçersiz kılınan kuralların bu metadata ile korunmasını özellikle istiyor.

Offline karşılaştırmada, yalnız doğum yeri soran geçerli text-only aday kabul edildi. Aynı workflow korunup kaynak kanıtına şu iki kural eklendiğinde aday reddedildi:

- Eski kural: iki soru, doğum tarihi ve telefonun son dört hanesi; `replaced_by` yeni memoyu gösteriyor.
- Yeni memo: tek soru, doğum yeri; eski kuralı `replaces` ile değiştiriyor ve DOB sorulmasını yasaklıyor.

Her iki doğrulamada da orijinal brief satırları verildi. Validator eski `date` ve `numeric_code` türlerini, ayrıca eski iki soru ve yeni tek soru sayısını birlikte zorunlu saydı. Sonuç: `identity_questions omitted a required identity question type`.

Bu, **sentetik bir memo örneği**; mevcut Brief B kimlik sorularını değiştirmediğinden mevcut A+B için gözlenmiş bir arıza değil. Ancak final brief'te geçerli bir değişikliği builder'ın reddetmesine yol açabilir. Kaynak kanıtı korunurken yürürlükteki gereksinimler ayrı hesaplanmalı. Sahte bir override etiketiyle gerçek zorunluluğun silinmesini de engelleyen küçük karşı test gerekli.

### 2. [P2] `ok=false` sonrası retry, onaylı isteği değiştirirse validator yakalamıyor

[`retry_limit`](../builder/validation.py#L964), HTTP 200 ve `data.ok=false` sonrasında ikinci denemenin yetkisini ve sayısını kontrol ediyor; ilk ve ikinci banka isteğini karşılaştırmıyor. HTTP hata yolunda ise [aynı değişmezlik kontrolü mevcut](../builder/validation.py#L1010).

Offline fault injection, yalnız business-failure retry dalında tutarı değiştiren sentetik bozuk aday üretti. Hem kontrol adayı hem bozuk aday validator'dan geçti. Gerçek graph replay sonucu:

| Alan | Müşterinin onayladığı ilk istek | Yetkili ikinci deneme |
| --- | --- | --- |
| Ürün | `p1` | `p1` |
| Tutar | `25.0` | **`999.0`** |
| Tarih | `2026-10-14` | `2026-10-14` |
| Deneme sayısı | 1 | 2 |

Bu bulgu **validator'ın bozuk bir adayı kabul etmesi**; yayımlanmış agentın 999 kaydettiği iddiası değil. Tüm izinli retry yollarında bağlanmış istek ilk onaylı istekle aynı olmalı. Aynı kalan retry için olumlu kontrol; ürün, tutar ve tarih değişiklikleri için olumsuz kontroller yeterli. Deneme sınırı ve ikinci denemede başarı davranışı korunmalı.

## Doğrulama ve ilerleme

| Bu review'da bağımsız çalıştırılan kontrol | Sonuç |
| --- | --- |
| Önceden başarısız üç fixture testi + builder integration | 9/9, 2.572 saniye; integration mock kullanır |
| Yeni approval/retry, inputs, conversation modülleri | 20/20, 17.161 saniye |
| Test yardımcısı | 19/19 |
| Builder self-check ve `git diff --check` | Geçti |
| Yukarıdaki iki ayrı offline repro | İki bulgu da yeniden üretildi |

Toplam **48 seçilmiş test geçti**; bu review'da tam suite tekrarlanmadı. [Geliştirme raporu](focused-fix-result.md), tek tam koşunun 105/108 olduğunu ve sonrasında üç eski fixture'ın düzeltildiğini açıkça belirtiyor. Son kod için 108/108 ölçüldüğü iddia edilmemeli.

Marker boş/yanlışken onay düzeltmesi, post-hook atlanan API hatasının graph yolu, gerçek API alan eşlemesi, kimlik türüne göre kontroller, kimlik öncesi exception konuşması ve yılsız ödeme tarihi için yeni sözleşmeler ve sentetik regresyonlar var. Resume kilidi ve execution/recovery süre ayrımı da yerel testlerle doğrulandı. Bunlar compiler promptu ve validator değişiklikleri; henüz bu kaynakla yeni workflow üretilmedi.

Son bilinen canlı sürüm önceki review'daki v6'dır; bu görevde dashboard/API yeniden okunmadı. Eski v6'nın tam A sonucu 3/10, yeni kaynak için skor değildir. A+B, kelimeyle para ve cross-turn kimlik birleştirme hâlâ açık kapsam.

## Skill ve sonraki iş

Kullanıcının işaret ettiği [starter skill](../build-the-builder/.claude/skills/build-phone-agent/SKILL.md) bu review sırasında okundu. Brief/API'yi esas alma, araç sonucuna göre aşama değiştirme ve kayıt başarısızlığını dürüst bildirme ilkeleri incelemeye uygulandı. Bu skill kitteki örnek Claude builder içindir; bizim `scripts/build_agent.py` doğrudan `builder/prompt.md` ve platform belgelerini yüklüyor, bu skill dosyasını çağrı girdisine eklemiyor. `.claude` klasöründe bulunması Codex'te kendiliğinden kullanıldığını göstermez.

Önerilen sıra: yalnız iki bulguyu küçük karşı testlerle kapat → bir builder çalıştırmasıyla yeni sürüm üret → aynı sürümde PUB-01 ve bir tam A koşusunu ölç → gerçek hataya göre sonraki işi seç. Değişmeyen suite'i veya başarısız canlı vakayı körlemesine tekrar eden geliştirme döngüsü gerekmiyor.

## Yerel kanıtlar

Ignored `build-the-builder/out/review-484e6b2/` altında `identity-override-repro.py/json` ve `business-retry-repro.py/json` bulunur. Kaynak validator SHA256: `990d7d587b453eb69dc66fadae7968ef9e40f8c2eee5d14b5b324f42bb51c23d`. Repro'lar API/model/banka çağırmaz. Ham artefaktlar Git'e gitmez; ekip için paylaşılabilir sonuç bu rapordur.
