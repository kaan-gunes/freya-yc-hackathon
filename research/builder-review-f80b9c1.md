# Validator uyumluluğu ve üretim blokajı review'u

11 Ekim 2026. İncelenen HEAD `f80b9c1`; uygulama kaynağı `5a70c9b`; karşılaştırma tabanı `0382f6e`.

Değişiklik, kısıtlı regex modülüne `re.I` eş adını ekliyor. Kimlik öncesi hesap iddialarını müşteri ve yakını için ayrı, tutarlı durumlarla kontrol ediyor. Beklenen kullanım: ortak workspace'te tek builder/test çalışması.

**Karar: validator düzeltmelerini kabul et; çalışan agent teslimi hâlâ blokeli.** Bu diff'te yeni bir kritik validator hatası bulmadım. Son build'i durduran 17 hata gerçekten eksik workflow'dan geliyor; kontrolleri gevşetmek çözüm değil.

## Sonucu engelleyen bulgu

### 1. [P1] Üretim tam workflow yerine güvenli kapanış döndürüyor; onarımlar çalışan akışı değiştirmiyor

- **Nedir:** Builder, model çıktısını tam aday olarak doğruluyor; başarısızlıkta iki JSON merge-patch onarımı istiyor. İlgili yol: `scripts/build_agent.py:315` ve `scripts/build_agent.py:377`.
- **Sorun:** Gerçek son run'ın üç adayı da yalnızca `opening`, `safe_stop`, `end` düğümlerini içeriyor. Kimlik/banka kapısı, hesap, teklif/onay, kayıt ve zorunlu yedi guard testi yok. İki repair yalnız politika açıklaması, belirsizlik ve özeti değiştiriyor. Workflow, checks ve 17 hata üç denemede birebir aynı. Parse edilebilir JSON ve model exit 0, işin tamamlandığı anlamına gelmiyor.
- **En kısa uygulanabilir adım:** Aynı girdilerden daha önce üretilmiş tam aday artık mevcut validator ile geçiyor. Builder'a kaynak eşleşmesini doğrulayan küçük bir devam etme yolu ekleyip bu adayı değiştirmeden mevcut validation → Freya dry-run → publish/readback/export → test hattına ver. Sıfırdan bir üretim daha yapmak şu anda aynı başarısızlığın tekrarı riskini taşıyor. Devam yolu genel üretim sorununu çözmüş sayılmamalı.
- **Yapılmazsa:** Yerel validator düzelmiş olsa bile canlıda eski v6 kalır; yeni davranışlar ve skor hakkında kanıt üretilemez.

Bu, üretilmiş workflow'a elle müdahale önerisi değildir. Aynı kaynakların kontrol edilen çıktısını builder üzerinden yeniden kullanma önerisidir. Girdi, prompt veya platform belgesi değişmişse eski aday otomatik kabul edilmemeli.

## Bağımsız kontroller

| Kontrol | Sonuç |
| --- | --- |
| `tests.test_validator_compat` | 3/3; 4.004 s |
| `tests.test_focused_conversation` + `tests.test_focused_inputs` | 16/16; 12.527 s |
| Builder `self_check()` ve `git diff --check` | Geçti |
| Önceki değişmemiş aday, `20261011T100012806452Z` | 171/171; kaynak provenance geçti |
| Tam değişmemiş aday, `20261011T105328711505Z/candidate-attempt-3.json` | **179/179**; kaynak provenance geçti |
| Son run'ın değişmemiş adayı, `20261011T123005259560Z` | 2/3; aynı 17 gerçek hata |
| İki run'ın altı girdi kaynağı | Brief, OpenAPI, builder promptu ve üç platform belgesinin SHA256 değerleri birebir aynı; güncel dosyalar da eşleşiyor |
| Üç son adayın workflow/checks/hataları | Assert ile birebir aynı olduğu doğrulandı |

Yeni testler güvenli yakın/callback yolunu kabul ediyor; hem müşteri hem yakın için kimlik öncesi `paid`, `no_promise/dispute`, `transferred/restructuring` sonuçlarını reddediyor. `re.I` hem modül hem doğrudan import ile çalışıyor; `purge` ve `os` sınırları korunuyor. Tarih dışı kimlik soruları, API alanı değişiklikleri, kaynakla değiştirme, gerekli sorunun silinmesi ve kimlik öncesi konuşma/kapanış negatif kontrolleri de bağımsız geçti.

Aday dosyalarının hashleri doğrulamadan önce/sonra aynı. Tam adayın SHA256 değeri `e7f55259dd18f20518e67886267c2e4aaefeb533dcc50081008b7b3aaa4af6fd`. Bu yerel başarı, canlı müşteri skoru değildir.

## Gerçek build ve canlı durum

Manifest ve trace bağımsız okundu: kaynak `5a70c9b`, temiz kod, **1008.34 s**, bir üretim ve iki repair, sonuç `incomplete`. Yeni Freya validation/save/publish/export veya müşteri testi yok. Model çıktısı açıkça eksik olduğunu belirtiyor; kaynaklar normal tek ürün akışı için yeterli. Neden tam implementasyon üretmediğini bu çıktı tek başına açıklamıyor; model kapasitesi, çıktı sınırı veya prompt büyüklüğünü kanıtlanmış kök neden saymıyorum.

Bağımsız, kimlik doğrulanmış GET okumaları workspace'i, simülasyonları ve workflow sürümlerini doğruladı. Aktif simülasyon yok; toplam 17. Aynı agent `404df3cd-803d-4656-89ac-ac122f9d31d2`, workflow `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`, yayımlanmış v6 ID `946ce959-11d7-4ab5-bfda-faeea22588ad`. GET'ler platform veya banka verisini değiştirmedi. Eski v6 3/10 skoru bu kaynak için yeni skor değildir.

## Teslim ve sonraki prompt

[VALIDATED_CANDIDATE_RESUME_PROMPT.md](../VALIDATED_CANDIDATE_RESUME_PROMPT.md): yalnız aynı kaynaklı tam adaydan devam etme, aynı güvenlik kapıları ve yeni sürümde tek PUB-01/tam A doğrulaması. Ham dosyalar ignored olduğu için başka checkout'ta bulunmaları varsayılmamalı.

Bağımsız yerel raporlar `build-the-builder/out/review-f80b9c1/`; platform okuması `build-the-builder/out/validator-compat-checks/independent-review-f80b9c1.json`. Bu dosyalar Git dışında. Üretim kodu ve workflow değiştirilmedi; yeni build veya canlı test başlatılmadı.

Kontrol edilmedi: bütün unit suite, tam adayın Freya dry-run/canlı davranışı, yeni veya değiştirilmiş girdilerden güvenilir üretim, A+B ve cross-turn parçalı kimlik. Devam yolu yalnız mevcut A için canlı kanıtı hızlandırır; final kapsamının tamamlandığını kanıtlamaz.
