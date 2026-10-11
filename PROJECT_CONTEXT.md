# Proje bağlamı ve chat devir notu

Bağımsız review, 11 Ekim 2026: HEAD `650dcbe`, uygulama kaynağı `eb7fc1e`. Resume değişikliği kabul edildi; 13 runner testi, self-check/diff-check ve değişmemiş adayın 179/179 kontrolü geçti. Mevcut tam A simülasyonu ve 10 ledger yalnız GET ile yeniden okundu; resmî scorer/hakem birleşimi **v7 4/10** sonucunu birebir doğruladı, banka tarafı **7/10**. Yeni test/publish/model üretimi yok. Dört kusur: kelimeyle ödeme günleri, karışık niyet önceliği, soru sırasında tekrar edilen minimum/support teklifi, boş/kurulmamış konuşma değişkenleri. PUB-10 retry doğru; hakem çağrı kaydı ile vaat kaydını karıştırmış, resmî FAIL korunuyor. Bu not sonraki kod/canlı durum için otomatik kanıt değildir.

Son geliştirici teslimi [tam adaydan devam sonucu](research/validated-candidate-live-result.md), artık [bağımsız incelendi](research/builder-review-650dcbe.md). Tek builder PUB-01 1/1 raporlandı; tam A'nın 4/10'u bağımsız yeniden puanlandı. On ham call ve canlı iteration run'ı aynı v7/version ID'yi doğruluyor. Güncel GET v7 yayımlı, aktif simülasyon yok, toplam 19 gösteriyor; ayrıca **yayımlanmamış v8 taslağı var**. Güncel workflow GET'i bu taslağı döndürdüğünden v7 için arşivlenen export ve sürümü bağlı call'lar esas alındı. V8'in yazarı/içeriği bu iki commit review'unun dışında. Genel yeni-brief üretimi/A+B tamamlanmış sayılmıyor.

Önceki geliştirici teslimi [validator uyumluluğu sonucu](research/validator-compat-live-result.md), artık [bağımsız incelendi](research/builder-review-f80b9c1.md). Tam aday `build-the-builder/out/20261011T105328711505Z/candidate-attempt-3.json` 179/179 geçiyor; bu run ile son eksik üretim run'ının altı girdi kaynağı birebir aynı ve güncel dosyalar da hashlerle eşleşiyor. Yukarıdaki yeni teslim, bu adayı değiştirmeden kaynak eşleşmesi kontrollü builder devam yoluyla doğruladı/yayımladı/test etti. Bu, yeni/gizli girdilerden güvenilir üretimin veya A+B'nin tamamlandığı anlamına gelmez.

## Yeni chat önce ne okusun?

1. Bu dosya: hedef, ana fikir ve son doğrulanmış durum.
2. [İlk geliştirme promptu](DEVELOPMENT_PROMPT.md): konuştuğumuz tasarımın ayrıntılı açıklaması.
3. [Son bağımsız review](research/builder-review-650dcbe.md) ve [son geliştirici sonucu](research/validated-candidate-live-result.md): resume kodu ve v7 4/10 doğrulandı; dört davranış kusuru. [Önceki review](research/builder-review-f80b9c1.md), [validator review](research/builder-review-4b637ea.md), [deadline review](research/builder-review-7d7dc3e.md), [v6 review](research/builder-review-6d324cd.md) ve [ikinci geliştirici sonucu](research/second-builder-result.md) tarihsel kanıtı korur.
4. [Güncel görev promptu](V7_CONVERSATION_FIX_PROMPT.md): dört konuşma kusurunu üretim mantığında ve yerel kontrollerde düzelt; yeni canlı test/publish açmadan teslim et. [Tam adaydan devam görevi](VALIDATED_CANDIDATE_RESUME_PROMPT.md), [validator uyumluluğu görevi](VALIDATOR_COMPAT_FIX_PROMPT.md), [tarih görevi](DEADLINE_FIX_PROMPT.md) ve önceki geliştirme promptları tarihsel talimatlardır; canlı hedeflerinin tamamlandığını varsayma.
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
- Test geçmişi önceki raporlarda korunuyor. Son bağımsız review: runner **13/13**, self-check/diff-check, aynı aday **179/179** ve provenance **47/47**. Mevcut 10 ledger + iteration hakemi resmî **4/10** ile eşleşti; dokuz offline snippet replay'i tarih/niyet/tekrar nedenlerini doğruladı. Yeni canlı test ve tam suite yok.
- İlk v1'in SSN kaçışı tarihsel hatadır; v6 gate/pieces kayıtlarında bu kaçış, schema-write reddi veya unmatched route görülmedi. String resetleri, deterministik karar yolu, gerçek API kapıları ve evidence/resume için somut iyileştirmeler var.
- V6 raporu: PUB-01 ilk koşu 1/1 ve değişmeyen sürümde üç tekrar 3/3; tam A 3/10, seçilmiş corrects 1/5, tek pieces 1/1. Önceki `6d324cd` review'u GET ile v6 ve beş call'ı doğruladı; ledger tekrar puanlamadı. Pieces başarısı fragment assembly kanıtı değil.
- `0331b18` kelimeyle telefon rakamı/cardinal DOB günlerini; `f22ea8b` correction etiketi kaçan onay, hook atlanan hata, API/kimlik türleri, pre-auth konuşma ve yılsız ödeme tarihini yerel kontrol ediyor. Son `bd2bb29` kaynakla üretim denendi ancak validation'da durdu; canlı düzeltme kanıtı yok.
- Önceki kimlik override açığı açık kaynaklı, numaralı replacement referansı biçimi için kapandı. Sahte ilişkiler reddediliyor. Her prose biçimi desteklenmiyor; kimlik dışı ilişkiler de aynı kapıdan geçiyor. Gerçek B9/A39 metadata'sı açık numaralı referans taşımadığından reddediliyor; A+B genellemesi için takip notu, mevcut A blokajı değil.
- Önceki business-failure retry açığı kapandı. 25 → 999 mutantı artık reddediliyor; ürün/tutar/tarih mutasyonları ve ikinci denemede başarı denetleniyor.
- Önceki same-deadline yanlış reddi `9d376d0`/`d58cd36` ile kapandı. Regex eş adı ve farklı arayan durumu karşılaştırması `5a70c9b` ile bağımsız doğrulandı. `--resume-build` aynı girdili adayı taşıyor; normal yeni-brief üretiminin eksik akış/no-op repair sorunu çözülmüş sayılmaz.
- Son gerçek builder çağrısı: **176.53 saniye**, kaynak `eb7fc1e`, model çağrısı olmadan eski `9d376d0` tam adayından reuse; dry-run/publish/readback/export ve builder PUB-01 raporu var. Aynı v7'nin tam A sonucu **4/10**, banka **7/10**. Güncel yayımlanmamış v8 taslağı v7 kanıtı değildir.
- Helper'ın resume kilidi ve execution süresini koruma düzeltmeleri 19/19 yerel testle geçti. A+B, kelimeyle para ve cross-turn kimlik parçalarını birleştirme hâlâ açık kapsam.

Son doğrulanmış yayımlı agent `404df3cd-803d-4656-89ac-ac122f9d31d2`, workflow `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`, **v7 ID `c8c90f97-a11c-480b-bafe-b7125680f419`**. Tam A simulation `6b91beeb-e7c2-4d6b-8bfd-ae18ac6117b9`, iteration `9958e79c-ad44-4238-8298-6c70a98948f0`. V8 ID `58790ad1-6f15-4876-bc95-1539894097c2` yayımlanmamış taslak. Yeni testten önce güncel yayımlı sürümü kontrol et. V7 build/export `build-the-builder/out/20261011T130940222950Z/`, tam A `build-the-builder/results/20261011T131304090587Z-404df3cd/`, bağımsız kanıt `build-the-builder/out/review-650dcbe/`. Ham dosyalar bu checkout'ta; Git ile paylaşılmaz.

Sıra: v7'nin dört konuşma kusurunu üretimde düzelt → küçük yerel pozitif/negatif kontroller ve gerekirse tek offline aday → review → sonraki ayrı canlı doğrulama kararı. Bu görevde yeni canlı test/publish yok. Aynı adayı değişmemiş resume etmek bu kusurları çözmez; kaynak eşleşmesi gevşetilmemeli. A+B, stiller ve yeni girdiden üretim güvenilirliği açık kapsam. Kaan'ın aşama/araç kapıları korunmalı; ayrı LLM şefi/history kırpma sonraki kapsam.

## Review ve test devamlılığı

Yeni push'ta önce son incelenen commit ile yeni kodun farkını incele. Kritik yolları bağımsız örneklerle doğrula; modelin hem ürettiği kodun hem kendi beklediği sonucun birbirini doğrulaması yeterli değil. Gerçek test, test edilen sürüm ve kaynak commit ile ilişkilendirilsin. Altyapı hatası agentın sıfır puanı değildir.

Aynı workspace'te tek simülasyon çalışır; test sırasında agent güncellenmesin. Ekip aynı Freya anahtarını ve aynı özel banka takım anahtarını kullanmalı. `env.sh`, ham sonuçlar ve trace'ler Git dışında; anahtarları raporlara koyma. Bazı ham kanıtlar yalnız ilgili bilgisayarda bulunur; diğer chat/checkout bunlara otomatik sahip olmaz. Okunabilir raporları repoda, teslim için tam trace/export'u ayrıca sakla.

Yeni review/test tamamlandığında bu notun tarihini, son incelenen commit'i ve doğrulanmış sonucunu güncelle; eski kanıtı sessizce yeni sürüme mal etme.
