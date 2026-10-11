# Proje bağlamı ve chat devir notu

Son geliştirme ve iki ayrı yerel inceleme, 11 Ekim 2026: uygulama kaynağı **`d472fc2`**. Kullanıcı bu chat'e prompt yerine doğrudan geliştirme görevi verdi. [Calls incelemesi ve Kaan compiler sonucu](research/kaan-compiler-result.md): 93 tam çağrı kaydı incelendi; kritik onay dönüşü, güncel metinden onay kapısı ve AI cevabının son konuşmaya taşınması kaynak koda alındı. Son gerçek builder komutu aynı Claude adayını model çağırmadan **25,12 saniyede** derledi: **232/232**, provenance **47/47**, sıfır graf hatası, `completed_local`, clean source. Seçilmiş testler **48/48**, self-check/diff-check geçti. Yeni canlı skor yok; v7'nin son ölçümü hâlâ resmî **4/10**, banka **7/10**.

Claude'un [son model repair'i](research/current-intent-repair-result.md), kaynak `58eed9a`, niyet düzeltmelerini yaptı ve **214/214** verdi; ancak `decision → approval` yolu üç yapısal kapı hatası yarattı. Kapılar gevşetilmedi. Yeni `builder/compiler.py` handoff'u offer guard → yeni readback yoluna bağladı. Eski generated checks değişmedi. Gerçek `Am I talking to a robot?`, yanlış yes etiketli soru/ret/boş metin ve belirsiz teklifte kaybolan AI cevabı için ek bağımsız kontroller var. Bütün politika derleyicisi tamamlanmış değildir; A+B/yeni brief ve runtime gecikme güvenilirliği açık.

Önceki bağımsız review, HEAD `e655ed7`, uygulama/test kaynağı `cc09a5f`, model üretimi `8a95ace`: etkilenen 57 test, self-check/diff-check geçti. Aynı eski offline aday **203/207**, provenance **47/47** idi; dört ret ve iki ek niyet hatası vardı. Bu tarihsel sonuç güncel adayın sonucu değildir.

Önceki geliştirici teslimi [konuşma düzeltmeleri sonucu](research/v7-conversation-fix-result.md), [bağımsız incelendi](research/builder-review-e655ed7.md). Tek offline model repair **451.70 saniyede** validation'da durmuştu; dry-run/publish/test yoktu. Ardından Claude'un niyet repair'i ve yukarıdaki kaynak compiler uygulaması geldi.

Önceki bağımsız review HEAD `650dcbe`, uygulama `eb7fc1e`: v7'nin mevcut 10 A çağrısı + ledger yalnız GET ile yeniden okundu; resmî **4/10**, banka **7/10** doğrulandı. PUB-10 retry doğru; hakem çağrı kaydı ile vaat kaydını karıştırmış, resmî FAIL korunuyor. Bu skor son offline kod düzeltmelerini ölçmüyor.

Önceki canlı geliştirici teslimi [tam adaydan devam sonucu](research/validated-candidate-live-result.md), [bağımsız incelendi](research/builder-review-650dcbe.md). Tek builder PUB-01 1/1 raporlandı; tam A'nın 4/10'u bağımsız yeniden puanlandı. On ham call ve canlı iteration run'ı aynı v7/version ID'yi doğruluyor. O review'daki GET v7 yayımlı, aktif simülasyon yok, toplam 19 gösterdi; ayrıca **yayımlanmamış v8 taslağı vardı**. Workflow GET'i bu taslağı döndürdüğünden v7 için arşivlenen export ve sürümü bağlı call'lar esas alındı. V8 son review'da okunmadı veya değiştirilmedi. Genel yeni-brief üretimi/A+B tamamlanmış sayılmıyor.

Önceki geliştirici teslimi [validator uyumluluğu sonucu](research/validator-compat-live-result.md), artık [bağımsız incelendi](research/builder-review-f80b9c1.md). Tam aday `build-the-builder/out/20261011T105328711505Z/candidate-attempt-3.json` 179/179 geçiyor; bu run ile son eksik üretim run'ının altı girdi kaynağı birebir aynı ve güncel dosyalar da hashlerle eşleşiyor. Yukarıdaki yeni teslim, bu adayı değiştirmeden kaynak eşleşmesi kontrollü builder devam yoluyla doğruladı/yayımladı/test etti. Bu, yeni/gizli girdilerden güvenilir üretimin veya A+B'nin tamamlandığı anlamına gelmez.

## Yeni chat önce ne okusun?

1. Bu dosya: hedef, ana fikir ve son doğrulanmış durum.
2. [İlk geliştirme promptu](DEVELOPMENT_PROMPT.md): konuştuğumuz tasarımın ayrıntılı açıklaması.
3. [Güncel kaynak compiler sonucu](research/kaan-compiler-result.md) ve [Claude'un önceki repair sonucu](research/current-intent-repair-result.md): yeni aday 232/232 ve graf geçerli; henüz yayımlanmadı. [Önceki bağımsız review](research/builder-review-e655ed7.md), [V7 canlı review'u](research/builder-review-650dcbe.md) ve diğer review'lar tarihsel kanıtı korur.
4. [Niyet repair promptu](CURRENT_INTENT_REPAIR_PROMPT.md), [konuşma düzeltme görevi](V7_CONVERSATION_FIX_PROMPT.md), [tam adaydan devam görevi](VALIDATED_CANDIDATE_RESUME_PROMPT.md) ve önceki promptlar tarihsel talimatlardır. Güncel kullanıcı talimatı kod geliştirmekti; yeni prompt istenmedi. Eski canlı hedeflerin tamamlandığını varsayma.
5. [Resmî kit README](build-the-builder/README.md), [örnek builder skill'i](build-the-builder/.claude/skills/build-phone-agent/SKILL.md), ilgili brief/OpenAPI ve ihtiyaç oldukça platform belgeleri. İş kurallarında verilen brief/API; platform davranışında belgeler ve doğrudan gözlem esas alınır. Araştırma notları bunların yerine geçmez.

Review yaparken Git durumunu, commit farkını ve test edilen agent sürümünü yeniden kontrol et. Eski rapordaki bulguyu yeni sürümde otomatik olarak var veya düzelmiş sayma.

## Ne yapıyoruz, nasıl birlikte çalışıyoruz?

Kaan ve arkadaşı Freya “Build the Builder” hackathonuna katılıyor; konuya yeniler. Bu chat başlangıçta araştırma, review, test ve prompt hazırlıyordu. **Son kullanıcı talimatı bu chat'in doğrudan kod geliştirmesi ve yeni prompt hazırlamamasıydı; bu turda uygulandı.** Açıklamalar Türkçe, basit ve örnekli olsun. Sonraki görevi kullanıcının güncel talimatından al.

Önceki tercih: Her review sonunda dar kapsamlı prompt ver. Kullanıcının bu turdaki **“prompt hazırlama geliştir”** talimatı bu tercihinin önüne geçti. Tekrar prompt istenmedikçe bu geliştirme teslimine prompt ekleme.

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

Model politika, workflow, kontroller, belirsizlikler ve özet üretir. Normal generation/model repair sonucu şimdi kaynak `builder/compiler.py` ile derlenir; sonra yerel validator ve online ise Freya dry-run/publish/readback/export/test kapıları çalışır. `--offline --compile-build RUN` aynı girdili eski tam adayı model/Freya çağrısı olmadan bir kez derler; kaynak ve slot eşleşmesini korur. `--resume-build` derlemez; girdiler ve kaydedilmiş compiler hash'i aynı olmalı. Aynı 30 dakika içinde en fazla üç normal generation denemesi vardır; onarımlar sparse merge patch olabilir. Canlı konuşma başarısızlığından sonra otomatik geliştirme döngüsü henüz yoktur.

Kitteki `.claude/skills/build-phone-agent/SKILL.md` bu review'da okundu; ilgili brief/API ve güvenilir araç sonucu ilkeleri uygulandı. Dosya örnek Claude builder'ın skill'idir. Bizim custom builder bunu doğrudan yüklemiyor; `builder/prompt.md` ve platform belgelerini yüklüyor. Codex'in `.claude` içeriğini otomatik kullandığı varsayılmamalı.

## Son doğrulanmış sonuç ve açık iş

- Hazır baseline agent PUB-01'de ödeme sözünü kaydetti, zorunlu SMS cümlesini söylemedi; resmî sonuç **0/1**. Bu kendi builder'ımızın skoru değil. [Rapor](research/ilk-test-sonucu.md).
- Güncel kaynak compiler: gerçek builder ile **232/232**, provenance **47/47**, graf hatası yok. Seçilmiş testler **48/48**; ayrıca v7 conversation testleri validator eklemesinden sonra **5/5** geçti. İki ayrı inceleme ilk derlenmiş adayı yerelde doğruladı; son kaynakla gerçek CLI aynı 232 kontrolü tekrar geçti. Yeni canlı test yok. **232/232 müşteri skoru değil**, yerel kontrol sonucudur. Önceki 203/207 ve 214/214 sonuçları ilgili raporlarda korunuyor.
- İlk v1'in SSN kaçışı tarihsel hatadır; v6 gate/pieces kayıtlarında bu kaçış, schema-write reddi veya unmatched route görülmedi. String resetleri, deterministik karar yolu, gerçek API kapıları ve evidence/resume için somut iyileştirmeler var.
- V6 raporu: PUB-01 ilk koşu 1/1 ve değişmeyen sürümde üç tekrar 3/3; tam A 3/10, seçilmiş corrects 1/5, tek pieces 1/1. Önceki `6d324cd` review'u GET ile v6 ve beş call'ı doğruladı; ledger tekrar puanlamadı. Pieces başarısı fragment assembly kanıtı değil.
- `0331b18` kelimeyle telefon rakamı/cardinal DOB günlerini; `f22ea8b` correction etiketi kaçan onay, hook atlanan hata, API/kimlik türleri, pre-auth konuşma ve yılsız ödeme tarihini yerel kontrol ediyor. Son `bd2bb29` kaynakla üretim denendi ancak validation'da durdu; canlı düzeltme kanıtı yok.
- Önceki kimlik override açığı açık kaynaklı, numaralı replacement referansı biçimi için kapandı. Sahte ilişkiler reddediliyor. Her prose biçimi desteklenmiyor; kimlik dışı ilişkiler de aynı kapıdan geçiyor. Gerçek B9/A39 metadata'sı açık numaralı referans taşımadığından reddediliyor; A+B genellemesi için takip notu, mevcut A blokajı değil.
- Önceki business-failure retry açığı kapandı. 25 → 999 mutantı artık reddediliyor; ürün/tutar/tarih mutasyonları ve ikinci denemede başarı denetleniyor.
- Önceki same-deadline yanlış reddi `9d376d0`/`d58cd36` ile kapandı. Regex eş adı ve farklı arayan durumu karşılaştırması `5a70c9b` ile bağımsız doğrulandı. `--resume-build` aynı girdili adayı taşıyor; normal yeni-brief üretiminin eksik akış/no-op repair sorunu çözülmüş sayılmaz.
- Son gerçek builder çağrısı: **25,12 saniye**, kaynak `d472fc2`, offline source compilation; **232/232** ile `completed_local`, model/dry-run/publish/test yok. Üç local compilation ve ara portable Python reddi raporda kayıtlı. Son model generation Claude'un **251,09 saniyelik** `58eed9a` repair'iydi. Önceki **176,53 saniyelik** `eb7fc1e` reuse run'ı v7'yi yayımladı; son bağımsız canlı A ölçümü **4/10**, banka **7/10**. Yayımlanmamış v8 taslağı v7 kanıtı değildir.
- Helper'ın resume kilidi ve execution süresini koruma düzeltmeleri 19/19 yerel testle geçti. A+B, kelimeyle para ve cross-turn kimlik parçalarını birleştirme hâlâ açık kapsam.

Son doğrulanmış yayımlı agent `404df3cd-803d-4656-89ac-ac122f9d31d2`, workflow `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`, **v7 ID `c8c90f97-a11c-480b-bafe-b7125680f419`**. Tam A simulation `6b91beeb-e7c2-4d6b-8bfd-ae18ac6117b9`, iteration `9958e79c-ad44-4238-8298-6c70a98948f0`. Önceki GET'te V8 ID `58790ad1-6f15-4876-bc95-1539894097c2` yayımlanmamış taslaktı. Yeni testten önce güncel yayımlı sürümü kontrol et. V7 build/export `build-the-builder/out/20261011T130940222950Z/`, tam A `build-the-builder/results/20261011T131304090587Z-404df3cd/`. **Son geçerli offline aday `build-the-builder/out/20261011T155956791672Z/`**; değişmemiş Claude seed'i `build-the-builder/out/20261011T145212543699Z/`. Calls inceleme ve bağımsız kanıt `build-the-builder/out/kaan-compiler-review/`. Ham dosyalar bu checkout'ta; Git ile paylaşılmaz.

Son teslimde geçerli offline aday var; niyet ve confirmation dönüşü için tekrar model repair gerekmedi. Sonraki ayrı canlı doğrulama görevinde güncel yayımlı sürüm ve ekip durumunu kontrol ederek platform kapılarından geçilebilir; bu turda canlı test/publish yapılmadı. Kaynak eşleşmesi gevşetilmemeli. A'nın public seti 10, B'nin 3 müşteridir; hepsini üç kez koşmak 39 çağrı, 13 farklı müşteridir. A+B/üç tekrar, stiller, canlı gecikme ve yeni girdiden üretim güvenilirliği açık kapsam. Kaan'ın aşama/araç kapıları korunmalı; ayrı LLM şefi/history kırpma sonraki kapsam.

## Review ve test devamlılığı

Yeni push'ta önce son incelenen commit ile yeni kodun farkını incele. Kritik yolları bağımsız örneklerle doğrula; modelin hem ürettiği kodun hem kendi beklediği sonucun birbirini doğrulaması yeterli değil. Gerçek test, test edilen sürüm ve kaynak commit ile ilişkilendirilsin. Altyapı hatası agentın sıfır puanı değildir.

Aynı workspace'te tek simülasyon çalışır; test sırasında agent güncellenmesin. Ekip aynı Freya anahtarını ve aynı özel banka takım anahtarını kullanmalı. `env.sh`, ham sonuçlar ve trace'ler Git dışında; anahtarları raporlara koyma. Bazı ham kanıtlar yalnız ilgili bilgisayarda bulunur; diğer chat/checkout bunlara otomatik sahip olmaz. Okunabilir raporları repoda, teslim için tam trace/export'u ayrıca sakla.

Yeni review/test tamamlandığında bu notun tarihini, son incelenen commit'i ve doğrulanmış sonucunu güncelle; eski kanıtı sessizce yeni sürüme mal etme.
