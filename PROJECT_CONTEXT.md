# Proje bağlamı ve chat devir notu

Güncelleme: 11 Ekim 2026. Son review HEAD `484e6b2`; son incelenen uygulama commit'i `f22ea8b`, geliştirme raporu `484e6b2`. Son bilinen yayımlanmış agent v6, `9fb2dce` girdili builder çalışmasından; yeni kaynak henüz agent olarak üretilmedi. Bu review'da canlı API/dashboard yeniden okunmadı. Bu dosya konuşma devamlılığı içindir; sonraki kodun veya canlı Freya agentının otomatik güncel durum kanıtı değildir.

## Yeni chat önce ne okusun?

1. Bu dosya: hedef, ana fikir ve son doğrulanmış durum.
2. [İlk geliştirme promptu](DEVELOPMENT_PROMPT.md): konuştuğumuz tasarımın ayrıntılı açıklaması.
3. [Güncel inceleme](research/builder-review-484e6b2.md) ve [focused geliştirme sonucu](research/focused-fix-result.md): yeni kaynak kontrolleri ve kalan iki validator açığı. [Önceki review](research/builder-review-6d324cd.md) ile [ikinci geliştirme sonucu](research/second-builder-result.md) canlı v6 geçmişi içindir.
4. [Son düzeltme promptu](FOCUSED_FIX_PROMPT.md): hızlı kaynak teslimi istendi, bu görevde üretim/canlı test yapılmadı. [İkinci geliştirme promptu](NEXT_DEVELOPMENT_PROMPT.md) ve [sonraki kapsam](AFTER_CURRENT_TASK_PROMPT.md) önceki planlardır; tamamlandıkları varsayılmamalı.
5. [Resmî kit README](build-the-builder/README.md), [örnek builder skill'i](build-the-builder/.claude/skills/build-phone-agent/SKILL.md), ilgili brief/OpenAPI ve ihtiyaç oldukça platform belgeleri. İş kurallarında verilen brief/API; platform davranışında belgeler ve doğrudan gözlem esas alınır. Araştırma notları bunların yerine geçmez.

Review yaparken Git durumunu, commit farkını ve test edilen agent sürümünü yeniden kontrol et. Eski rapordaki bulguyu yeni sürümde otomatik olarak var veya düzelmiş sayma.

## Ne yapıyoruz, nasıl birlikte çalışıyoruz?

Kaan ve arkadaşı Freya “Build the Builder” hackathonuna katılıyor; konuya yeniler. Arkadaşın kodlama agentı builder'ı geliştiriyor. Bu chat araştırma, review, test ve anlaşılır geliştirme promptları hazırlamak için kullanılıyor. Açıklamalar Türkçe, basit ve örnekli olsun. Promptlar hedefleri ve önemli sınırları taşısın; gereksiz dosya/sınıf/node zorunlulukları koymasın.

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
- Önceki review'da 87 repository testi geçmişti. Güncel teslimin raporladığı tek tam koşu 105/108; ardından üç eski fixture düzeltildi. Yeni review'da bu üçü dahil 48 seçilmiş test, builder self-check ve diff-check geçti; tam suite tekrar edilmedi. Son kod için 108/108 veya canlı başarı iddia edilmiyor.
- İlk v1'in SSN kaçışı tarihsel hatadır; v6 gate/pieces kayıtlarında bu kaçış, schema-write reddi veya unmatched route görülmedi. String resetleri, deterministik karar yolu, gerçek API kapıları ve evidence/resume için somut iyileştirmeler var.
- V6 raporu: PUB-01 ilk koşu 1/1 ve değişmeyen sürümde üç tekrar 3/3; tam A 3/10, seçilmiş corrects 1/5, tek pieces 1/1. Önceki `6d324cd` review'u GET ile v6 ve beş call'ı doğruladı; ledger tekrar puanlamadı. Pieces başarısı fragment assembly kanıtı değil.
- `0331b18` kelimeyle telefon rakamı/cardinal DOB günlerini yerel kontrol ediyor. `f22ea8b` correction etiketi kaçan onay, hook atlanan API hata yolu, alan eşlemesi/kimlik türleri, pre-auth exception konuşması ve yılsız ödeme tarihi için compiler sözleşmeleri ve sentetik kontroller ekledi. Bu kaynakla henüz yeni agent üretilmedi; canlı düzeltme kanıtı yok.
- Güncel P1: Kimlik sorularını değiştiren sentetik memo, eski kuralları `replaces/replaced_by` ile koruyunca validator eski soru türlerini ve sayılarını da zorunlu tutup geçerli adayı reddediyor. Mevcut B kimliği değiştirmiyor; final genellemesini etkileyen bir açık.
- Güncel P2: HTTP 200 / `ok=false` sonrası retry'ın onaylı isteği koruduğu kontrol edilmiyor. Sentetik fault injection'da onaylı tutar 25 iken ikinci yetkili istek 999 oluyor ve validator kabul ediyor. Bu canlı yanlış kayıt iddiası değil; HTTP-error yolunda mevcut olan değişmezlik denetimi bu yola da uygulanmalı.
- Helper'ın resume kilidi ve execution süresini koruma düzeltmeleri 19/19 yerel testle geçti. A+B, kelimeyle para ve cross-turn kimlik parçalarını birleştirme hâlâ açık kapsam.

Son bilinen canlı agent `404df3cd-803d-4656-89ac-ac122f9d31d2`, workflow `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`, v6 ID `946ce959-11d7-4ab5-bfda-faeea22588ad`. A batch simülasyonu `667f1b35-8be6-422f-a1e9-db22f8324bf8`. Canlı testten önce bu sürümün hâlâ en yeni olduğu yeniden kontrol edilmeli. Tam build artefaktları arkadaşın bilgisayarında; root checkout'ta önceki GET kanıtları ve ignored `out/review-484e6b2/` altında iki yeni offline repro bulunuyor.

Sıra: iki güncel validator açığını küçük karşı testlerle kapat → son kaynakla bir builder üretimi → yeni sürümde PUB-01 ve bir tam A koşusu → gerçek hataya göre sonraki iş → A+B ve stiller. Gereksiz tekrar ve uzun geliştirme/test döngüsü kurma; kullanıcı hızlı, review'a hazır teslim istiyor. Ayrı LLM şefi/agresif bağlam kırpma, çalışan çekirdekten sonra ölçülecek. Final puanında ayrıca mimari özgünlük puanı yok; sonuç ve yeniden üretilebilirlik önemli.

## Review ve test devamlılığı

Yeni push'ta önce son incelenen commit ile yeni kodun farkını incele. Kritik yolları bağımsız örneklerle doğrula; modelin hem ürettiği kodun hem kendi beklediği sonucun birbirini doğrulaması yeterli değil. Gerçek test, test edilen sürüm ve kaynak commit ile ilişkilendirilsin. Altyapı hatası agentın sıfır puanı değildir.

Aynı workspace'te tek simülasyon çalışır; test sırasında agent güncellenmesin. Ekip aynı Freya anahtarını ve aynı özel banka takım anahtarını kullanmalı. `env.sh`, ham sonuçlar ve trace'ler Git dışında; anahtarları raporlara koyma. Bazı ham kanıtlar yalnız ilgili bilgisayarda bulunur; diğer chat/checkout bunlara otomatik sahip olmaz. Okunabilir raporları repoda, teslim için tam trace/export'u ayrıca sakla.

Yeni review/test tamamlandığında bu notun tarihini, son incelenen commit'i ve doğrulanmış sonucunu güncelle; eski kanıtı sessizce yeni sürüme mal etme.
