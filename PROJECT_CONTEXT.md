# Proje bağlamı ve chat devir notu

Güncelleme: 11 Ekim 2026. Son review HEAD `7d7dc3e`; son incelenen uygulama commit'i `bd2bb29`, geliştirme raporu `7d7dc3e`. Yeni kaynakla bir builder çalışması yapıldı, yerel validation'da durdu; yeni publish veya canlı skor yok. Son bilinen yayımlanmış agent v6, `9fb2dce` girdili builder çalışmasından. Bu review'da canlı API/dashboard yeniden okunmadı. Bu dosya konuşma devamlılığı içindir; sonraki kodun veya canlı Freya agentının otomatik güncel durum kanıtı değildir.

## Yeni chat önce ne okusun?

1. Bu dosya: hedef, ana fikir ve son doğrulanmış durum.
2. [İlk geliştirme promptu](DEVELOPMENT_PROMPT.md): konuştuğumuz tasarımın ayrıntılı açıklaması.
3. [Güncel inceleme](research/builder-review-7d7dc3e.md) ve [son geliştirme sonucu](research/validator-fix-live-result.md): iki düzeltmenin durumu, yerel tarih testi yüzünden bloke olan üretim. [Önceki review](research/builder-review-484e6b2.md) ve [focused sonuç](research/focused-fix-result.md) geçmiş kaynak kontrolleridir. [V6 review](research/builder-review-6d324cd.md) ile [ikinci geliştirme sonucu](research/second-builder-result.md) canlı geçmişi içindir.
4. [Son görev promptu](NEXT_LIVE_VALIDATION_PROMPT.md): iki validator düzeltmesi yapıldı, tek üretim yerel validation'da durdu, canlı aşamaya ulaşılamadı. Önce güncel review'un tarih kontrolü düzeltmesini ele al. [Önceki düzeltme promptu](FOCUSED_FIX_PROMPT.md) yalnız kaynak teslimiydi. [İkinci geliştirme promptu](NEXT_DEVELOPMENT_PROMPT.md) ve [sonraki kapsam](AFTER_CURRENT_TASK_PROMPT.md) eski planlardır; tamamlandıkları varsayılmamalı.
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
- Test geçmişi: `6d324cd` review'unda 87 test; `484e6b2` review'unda 48 seçilmiş test geçti. Son `bd2bb29` teslimi 92 farklı testin geçtiğini raporluyor; yöntem sayımı kaynakla doğrulandı. Güncel bağımsız review'da focused inputs + approval/retry 17/17, self-check ve diff-check geçti. Tam suite tekrar edilmedi; yeni canlı başarı iddia edilmiyor.
- İlk v1'in SSN kaçışı tarihsel hatadır; v6 gate/pieces kayıtlarında bu kaçış, schema-write reddi veya unmatched route görülmedi. String resetleri, deterministik karar yolu, gerçek API kapıları ve evidence/resume için somut iyileştirmeler var.
- V6 raporu: PUB-01 ilk koşu 1/1 ve değişmeyen sürümde üç tekrar 3/3; tam A 3/10, seçilmiş corrects 1/5, tek pieces 1/1. Önceki `6d324cd` review'u GET ile v6 ve beş call'ı doğruladı; ledger tekrar puanlamadı. Pieces başarısı fragment assembly kanıtı değil.
- `0331b18` kelimeyle telefon rakamı/cardinal DOB günlerini; `f22ea8b` correction etiketi kaçan onay, hook atlanan hata, API/kimlik türleri, pre-auth konuşma ve yılsız ödeme tarihini yerel kontrol ediyor. Son `bd2bb29` kaynakla üretim denendi ancak validation'da durdu; canlı düzeltme kanıtı yok.
- Önceki kimlik override açığı açık kaynaklı, numaralı replacement referansı biçimi için kapandı. Sahte ilişkiler reddediliyor. Her prose biçimi desteklenmiyor; kimlik dışı ilişkiler de aynı kapıdan geçiyor. Gerçek B9/A39 metadata'sı açık numaralı referans taşımadığından reddediliyor; A+B genellemesi için takip notu, mevcut A blokajı değil.
- Önceki business-failure retry açığı kapandı. 25 → 999 mutantı artık reddediliyor; ürün/tutar/tarih mutasyonları ve ikinci denemede başarı denetleniyor.
- Güncel P1: `unmarked_correction` fixture gününe bir gün ekleyip yeni readback fingerprint'inin eskisinden farklı olmasını istiyor. İlk teklif zaten deadline'daysa kural 23 gereği son tarih yeniden teklif edilir; eski yetki temizlenip yeni onay beklense de aynı değerler yanlış ret alıyor. Bağımsız sentetik guard/graph replay iki marker durumunda bunu doğruladı. Arkadaşın son generated workflow'u burada yok; o adayın ayrıntıları teslim raporuna dayanıyor.
- Son builder raporu: 996.41 saniye, bir generation + iki repair, final local validation 166/168; yeni dry-run/publish/PUB-01/tam A yok. Freya preflight ayrıca bağlantı hatası vermiş; üretimi durduran neden yerel kontrol. Bu bir canlı 0/1 veya 0/10 skoru değil.
- Helper'ın resume kilidi ve execution süresini koruma düzeltmeleri 19/19 yerel testle geçti. A+B, kelimeyle para ve cross-turn kimlik parçalarını birleştirme hâlâ açık kapsam.

Son bilinen canlı agent `404df3cd-803d-4656-89ac-ac122f9d31d2`, workflow `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`, v6 ID `946ce959-11d7-4ab5-bfda-faeea22588ad`. A batch simülasyonu `667f1b35-8be6-422f-a1e9-db22f8324bf8`. Canlı testten önce bu sürümün hâlâ en yeni olduğu yeniden kontrol edilmeli. Son build artefaktları arkadaşın bilgisayarında: `out/20261011T100012806452Z/`. Root checkout'ta önceki GET kanıtları ve ignored `out/review-7d7dc3e/` altında üç yeni offline repro bulunuyor.

Sıra: tarih kontrolündeki yanlış reddi küçük karşı testlerle düzelt → bir builder üretimi → yayımlanabilirse yeni sürümde PUB-01 ve bir tam A koşusu → gerçek hataya göre sonraki iş → A+B ve stiller. Gereksiz tekrar ve uzun geliştirme/test döngüsü kurma; kullanıcı hızlı, review'a hazır teslim istiyor. Ayrı LLM şefi/agresif bağlam kırpma, çalışan çekirdekten sonra ölçülecek. Final puanında ayrıca mimari özgünlük puanı yok; sonuç ve yeniden üretilebilirlik önemli.

## Review ve test devamlılığı

Yeni push'ta önce son incelenen commit ile yeni kodun farkını incele. Kritik yolları bağımsız örneklerle doğrula; modelin hem ürettiği kodun hem kendi beklediği sonucun birbirini doğrulaması yeterli değil. Gerçek test, test edilen sürüm ve kaynak commit ile ilişkilendirilsin. Altyapı hatası agentın sıfır puanı değildir.

Aynı workspace'te tek simülasyon çalışır; test sırasında agent güncellenmesin. Ekip aynı Freya anahtarını ve aynı özel banka takım anahtarını kullanmalı. `env.sh`, ham sonuçlar ve trace'ler Git dışında; anahtarları raporlara koyma. Bazı ham kanıtlar yalnız ilgili bilgisayarda bulunur; diğer chat/checkout bunlara otomatik sahip olmaz. Okunabilir raporları repoda, teslim için tam trace/export'u ayrıca sakla.

Yeni review/test tamamlandığında bu notun tarihini, son incelenen commit'i ve doğrulanmış sonucunu güncelle; eski kanıtı sessizce yeni sürüme mal etme.
