# Proje bağlamı ve chat devir notu

Updated: 11 October 2026. Latest independent review HEAD `4b637ea`; application source `d58cd36`. The deadline fix passes focused checks. The latest actual build used `9d376d0` and stopped at local validation; no new publish or live score. Final-source replay of its unchanged last candidate passes 126/176. Two local validator mismatches are independently confirmed: missing `re.I`, and privacy probes comparing different caller states. Temporary diagnostic adjustments pass 176/176; production files and candidates were not changed. Last known published agent is v6. A fresh GET for workflow versions timed out after 25 seconds, so current live metadata was not confirmed. This file preserves conversation context; it is not automatic evidence for later code or live state.

## Yeni chat önce ne okusun?

1. Bu dosya: hedef, ana fikir ve son doğrulanmış durum.
2. [İlk geliştirme promptu](DEVELOPMENT_PROMPT.md): konuştuğumuz tasarımın ayrıntılı açıklaması.
3. [Latest independent review](research/builder-review-4b637ea.md) and [latest development result](research/deadline-fix-live-result.md): deadline fix, blocked build, and two remaining validator mismatches. [Previous review](research/builder-review-7d7dc3e.md) explains the earlier deadline rejection. [V6 review](research/builder-review-6d324cd.md) and [second development result](research/second-builder-result.md) preserve live history.
4. [Güncel görev promptu](VALIDATOR_COMPAT_FIX_PROMPT.md): regex desteğini uyumlu hale getir, privacy testlerinde tutarlı arayan/konuşma durumunu karşılaştır, güvenlik kontrollerini koru; ardından tek build ve yayımlanırsa aynı sürümde PUB-01/tam A. [Tarih görevi](DEADLINE_FIX_PROMPT.md), [önceki validator görevi](NEXT_LIVE_VALIDATION_PROMPT.md), [focused görev](FOCUSED_FIX_PROMPT.md), [ikinci geliştirme promptu](NEXT_DEVELOPMENT_PROMPT.md) ve [sonraki kapsam](AFTER_CURRENT_TASK_PROMPT.md) tarihsel talimatlardır; canlı hedeflerinin tamamlandığını varsayma.
5. [Resmî kit README](build-the-builder/README.md), [örnek builder skill'i](build-the-builder/.claude/skills/build-phone-agent/SKILL.md), ilgili brief/OpenAPI ve ihtiyaç oldukça platform belgeleri. İş kurallarında verilen brief/API; platform davranışında belgeler ve doğrudan gözlem esas alınır. Araştırma notları bunların yerine geçmez.

Review yaparken Git durumunu, commit farkını ve test edilen agent sürümünü yeniden kontrol et. Eski rapordaki bulguyu yeni sürümde otomatik olarak var veya düzelmiş sayma.

## Ne yapıyoruz, nasıl birlikte çalışıyoruz?

Kaan ve arkadaşı Freya “Build the Builder” hackathonuna katılıyor; konuya yeniler. Arkadaşın kodlama agentı builder'ı geliştiriyor. Bu chat araştırma, review, test ve anlaşılır geliştirme promptları hazırlamak için kullanılıyor. Açıklamalar Türkçe, basit ve örnekli olsun. Promptlar hedefleri ve önemli sınırları taşısın; gereksiz dosya/sınıf/node zorunlulukları koymasın.

Kalıcı tercih: Her review sonunda, bulgulara göre arkadaşın kodlama chatine verilecek dar kapsamlı promptu da hazırla ve kullanıcıya ver. Prompt rutin kararları geliştiriciye bıraksın; gereksiz uzun geliştirme/test döngüsü başlatmasın.

Ürün, **verilen brief dosyaları ve ilgili OpenAPI'den otomatik telefon agentı üreten builder**. Yalnız elle hazırlanmış iyi bir telefon agentı teslim etmek yeterli değil. Banka soruları, tutarlar, tarihler ve sonuç kodları her çalışmanın girdisinden çıkmalı. Gizli brief'in değerlerini elle builder koduna/promptuna geçirmek yerine üretim mantığı düzeltilmeli.

Şikayet platformlarını inceleme fikri, genel telesekreter hata örüntülerinden sentetik testler üretmek içindi. Gerçek şikayet/müşteri verisi projeye taşınmıyor.

## Kaan, duvar ve şef: ana fikrimiz

- **Kaan:** Görüşmenin durumunu, aşama geçişlerini, araç yetkilerini, sayaçları ve banka sonuçlarını yöneten kontrol mantığı. İsim bir benzetme; `kaan.py` zorunluluğu yok.
- **Aşamalar:** Açılış, kimlik, hesap, ödeme, onay, kayıt ve kapanış gibi sınırlı görevler. Her aşama kendi işini bilir; bütün sistemin sırasını bilmesi gerekmez.
- **Duvar / Obsidian mantığı:** Küçük ana politika haritası ilgili alt kurallara yönlendirir. Her aşama gerekli talimatları, ortak istisnaları ve gerekli durumu alır. Builder girdinin tamamını okuyup kapsamı korur; parçalama bir kuralın kaybolmasına yol açmamalı.
- **Bilgi aktarımı:** Önceki aşamadan yapılandırılmış, gerekli bilgiler kalır. Müşterinin söylediği, modelin çıkardığı, bankanın doğruladığı, müşterinin onayladığı ve bankada kaydedilen bilgiler ayrı tutulur.
- **Şef:** Çıkarılan verinin tamamlığını, biçimini ve kaynakla tutarlılığını kontrol eden katman. İlk sürümde mümkün olduğunca kodla yapılır. Ayrı LLM şefi sonra ölçülerek değerlendirilebilir. Şef kimliğin gerçekliğine karar vermez; bu banka API'sinin görevidir.
- **Ucuz ön kontrol:** Biçim/tarih/tutar kontrolleri pahalı model kontrolünden önce yapılabilir. Eksik cevap ile bankanın yanlış bulduğu cevap ayrılır. TC'nin son hanesi ve baba adı konuşmadaki örneklerdi; mevcut brief istemediği için bu sorular eklenmez.
- **Gerçek erişim kısıtı:** Kimlik öncesinde hesap/borç bilgisi promptta bulunmaz ve hesap/ödeme araçları açılamaz. Sadece “söyleme” talimatı yeterli değil. Doğrulandı durumunu model değil, güvenilir banka sonucu belirler.
- **Aşamayı öldürmek:** Önceki görevi bitirmek; müşterinin görüşmesini kapatmak değil. Denetim için tam görüşme kaydı ayrıca korunur.

Başlangıç örneği: Müşteri kimlik cevabı verir → kod biçimi kontrol eder → gerekiyorsa şef kaliteyi değerlendirir → banka API'si doğrular → başarılıysa Kaan hesap aşamasına geçer. Başarısızsa brief'in izin verdiği kimlik akışında kalır. Ödeme aşamasına güvenlik cevaplarının tamamını taşımak gerekmez; güvenilir doğrulama durumu ve gerekli kimlikler taşınır.

**Platform sınırı:** Freya node değişimi geçmişi ve global değişkenleri otomatik silmez. History kırpma, dialogue/extraction/routing modellerine aynı şekilde uygulanmaz. Bu tasarım “sıfır halüsinasyon” garantisi değildir. Araç yetkileri kadar sözlü kaçışlar, eski değişkenler ve yanlış geçişler de test edilir.

Organizatörler export'u kendi workspace'lerinde çalıştırır. Görüşme sırasındaki Kaan mantığı workflow kodu/geçişleri içinde taşınmalı; bizim açık bilgisayarımıza, yerel MD dosyalarına veya harici şef servisine bağlı olmamalı.

## Builder şu anda nasıl çalışıyor?

Üç rolü karıştırma: Kodlama chat'indeki model builder kodunu yazıyor; builder'ın çağırdığı ayrı model brief'ten workflow üretiyor; Freya'nın sabit telefon modeli müşteriyle konuşuyor.

Mevcut giriş `scripts/build-agent.sh` → `scripts/build_agent.py`. Brief/OpenAPI, builder promptu ve platform belgeleri ayrı bir Codex CLI çağrısına gidiyor. Bu çağrının varsayılan modeli `gpt-6.1-sol`; reasoning seviyesi komutta açıkça ayarlanmıyor. Kodlama chat'inin “max” seçimi içteki çağrının da max olduğunu kanıtlamaz.

Model politika, workflow, kontroller, belirsizlikler ve özet üretir. Yerel validator ve Freya dry-run kontrolünden sonra publish/readback/export yapılır; test yardımcısı çalışır. Aynı 30 dakika içinde en fazla üç generation denemesi vardır; onarımlar sparse merge patch olabilir ve tam aday yeniden doğrulanır. Canlı konuşma testinin başarısızlığından sonra builder içinde otomatik geliştirme döngüsü henüz yoktur.

Kitteki `.claude/skills/build-phone-agent/SKILL.md` bu review'da okundu; ilgili brief/API ve güvenilir araç sonucu ilkeleri uygulandı. Dosya örnek Claude builder'ın skill'idir. Bizim custom builder bunu doğrudan yüklemiyor; `builder/prompt.md` ve platform belgelerini yüklüyor. Codex'in `.claude` içeriğini otomatik kullandığı varsayılmamalı.

## Son doğrulanmış sonuç ve açık iş

- Hazır baseline agent PUB-01'de ödeme sözünü kaydetti, zorunlu SMS cümlesini söylemedi; resmî sonuç **0/1**. Bu kendi builder'ımızın skoru değil. [Rapor](research/ilk-test-sonucu.md).
- Test history: earlier reviews recorded 87 tests, then 48 selected tests, then 17 independent tests. Latest developer delivery reports 84 distinct tests. Latest independent review ran focused approval/retry + inputs **21/21**, focused conversation **6/6**, builder `self_check()` and diff-check. Previous unchanged candidate passes **168/168** with final source; latest unchanged candidate passes **126/176**. The full unit suite was not repeated; there is no new live success claim.
- İlk v1'in SSN kaçışı tarihsel hatadır; v6 gate/pieces kayıtlarında bu kaçış, schema-write reddi veya unmatched route görülmedi. String resetleri, deterministik karar yolu, gerçek API kapıları ve evidence/resume için somut iyileştirmeler var.
- V6 raporu: PUB-01 ilk koşu 1/1 ve değişmeyen sürümde üç tekrar 3/3; tam A 3/10, seçilmiş corrects 1/5, tek pieces 1/1. Önceki `6d324cd` review'u GET ile v6 ve beş call'ı doğruladı; ledger tekrar puanlamadı. Pieces başarısı fragment assembly kanıtı değil.
- `0331b18` kelimeyle telefon rakamı/cardinal DOB günlerini; `f22ea8b` correction etiketi kaçan onay, hook atlanan hata, API/kimlik türleri, pre-auth konuşma ve yılsız ödeme tarihini yerel kontrol ediyor. Son `bd2bb29` kaynakla üretim denendi ancak validation'da durdu; canlı düzeltme kanıtı yok.
- Önceki kimlik override açığı açık kaynaklı, numaralı replacement referansı biçimi için kapandı. Sahte ilişkiler reddediliyor. Her prose biçimi desteklenmiyor; kimlik dışı ilişkiler de aynı kapıdan geçiyor. Gerçek B9/A39 metadata'sı açık numaralı referans taşımadığından reddediliyor; A+B genellemesi için takip notu, mevcut A blokajı değil.
- Önceki business-failure retry açığı kapandı. 25 → 999 mutantı artık reddediliyor; ürün/tutar/tarih mutasyonları ve ikinci denemede başarı denetleniyor.
- The earlier same-deadline false rejection is fixed locally in `9d376d0` and `d58cd36`. Two current P1 findings remain: the restricted regex module omits `re.I`, causing all 50 original last-candidate failures; after diagnostic alias support, three privacy probes wrongly reject a safe identity-to-callback transition because their comparison state lacks the relative's raw speech. Diagnostic alias + consistent fixture text passes **176/176**. Three unsafe pre-identity account-close variants are still rejected. No production fix was applied during review.
- Latest actual build: **1436.02 seconds**, one generation + two repairs, source `9d376d0`, last local result **124/176**. Independent final-source replay is **126/176**. Manifest and trace confirm no new dry-run/publish/PUB-01/full A. The build ended at local validation; this is not a live 0/1 or 0/10 score. A separate read-only version GET timed out during review.
- Helper'ın resume kilidi ve execution süresini koruma düzeltmeleri 19/19 yerel testle geçti. A+B, kelimeyle para ve cross-turn kimlik parçalarını birleştirme hâlâ açık kapsam.

Last known live agent `404df3cd-803d-4656-89ac-ac122f9d31d2`, workflow `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`, v6 ID `946ce959-11d7-4ab5-bfda-faeea22588ad`. Historical A batch simulation `667f1b35-8be6-422f-a1e9-db22f8324bf8`. Check the current published version before a live test. Actual build folders `build-the-builder/out/20261011T100012806452Z/` and `build-the-builder/out/20261011T105328711505Z/` are now available in this checkout. Independent offline evidence is under ignored `build-the-builder/out/review-4b637ea/`; these files are not shared through Git.

Order: fix the two local validator mismatches with small positive/negative tests → one builder run → PUB-01 and one full A run on a newly published version → next work from actual failures → A+B and styles. Avoid repeated long build/test loops; the user wants a quick result ready for review. A separate LLM checker and aggressive history trimming come after a working core. Final scoring rewards results and reproducibility, with no separate architecture originality score.

## Review ve test devamlılığı

Yeni push'ta önce son incelenen commit ile yeni kodun farkını incele. Kritik yolları bağımsız örneklerle doğrula; modelin hem ürettiği kodun hem kendi beklediği sonucun birbirini doğrulaması yeterli değil. Gerçek test, test edilen sürüm ve kaynak commit ile ilişkilendirilsin. Altyapı hatası agentın sıfır puanı değildir.

Aynı workspace'te tek simülasyon çalışır; test sırasında agent güncellenmesin. Ekip aynı Freya anahtarını ve aynı özel banka takım anahtarını kullanmalı. `env.sh`, ham sonuçlar ve trace'ler Git dışında; anahtarları raporlara koyma. Bazı ham kanıtlar yalnız ilgili bilgisayarda bulunur; diğer chat/checkout bunlara otomatik sahip olmaz. Okunabilir raporları repoda, teslim için tam trace/export'u ayrıca sakla.

Yeni review/test tamamlandığında bu notun tarihini, son incelenen commit'i ve doğrulanmış sonucunu güncelle; eski kanıtı sessizce yeni sürüme mal etme.
