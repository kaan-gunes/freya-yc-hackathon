# İkinci geliştirme için prompt

Bu repodaki ilk builder'ı bir sonraki çalışan sürüme taşımanı istiyorum. Önce `research/builder-review-9046149.md` incelemesini ve mevcut kodu oku. İlk tasarımımızın açıklaması `DEVELOPMENT_PROMPT.md` içinde; aşağıdaki iş, o hedeflerin devamı.

Mimari ve dosya düzeninde karar alanın var. Amaç, gerçek konuşmada gözlenen hataları kapatıp ölçülmüş bir ilk başarı almak. Daha küçük ve sağlam bir çözüm bulursan gerekçesini açıklayıp uygula. Her madde için yeni node, yeni model veya ayrı framework eklemen gerekmiyor.

## Hedefimiz ve mevcut durum

Ürünümüz, verilen brief dosyaları ve o brief'e ait OpenAPI'den otomatik Freya telefon agentı üreten builder. Bankanın kimlik soruları, takvimi, limitleri ve sonuç kodları her çalışmanın girdilerinden gelmeli. Finalde farklı kurallar ve üç ürüne kadar destek gerekecek; şimdiki ara teslimde Brief A'nın çalışan çekirdeğini kararlı hale getiriyoruz.

“Kaan” dediğimiz kontrol katmanı aşamaları, güvenilir durumu, hesapları ve araç erişimini yönetiyor. LLM insanın ifadesini anlıyor ve kısa cevap kuruyor. Kimlik öncesinde hesap bilgisi/ödeme aracı erişimi kapalı; banka doğrulaması gerçeğin kaynağı. Obsidian/duvar fikrimiz, doğru aşamaya ilgili kuralları ve gerekli durumu vermek. İlk sürümün şefi büyük ölçüde kod kontrolleri; ayrı bir LLM şefi sonraki ölçülebilir bir seçenek.

Kurulan temel iyi bir başlangıç: brief/OpenAPI girdileri, kaynaklı politika, workflow üretimi, yerel kontroller, 30 dakika bütçesi, publish/readback/export ve trace var. 20 repository testi geçiyor. Ancak bu testler gerçek konuşmayı ve guard zincirini yeterince kapsamıyor.

Yayımlanmış ilk çıktı:

- Agent: `404df3cd-803d-4656-89ac-ac122f9d31d2`
- Workflow: `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`
- İncelenen sürüm: 1
- İlk simülasyon: `c69cae64-1161-4984-9097-a07e907e44eb`
- Iteration: `8b4bd945-e9f1-48c5-b0cf-7a032abd57a8`
- Call: `9d7195b6-72e3-4558-a703-e72e330b765a`

Önceki raporda 503 nedeniyle okunamayan simülasyon artık `completed`. Run verdict `inconclusive`, call analizi başarısız. Tam ledger skoru yeniden hesaplanmadığı için bu kayda 0/1 veya 1/1 demiyoruz. İnceleme klasöründeki ignored dosyalar diğer bilgisayarda bulunmayabilir; rapordaki kimliklerle Freya'dan okunabilir. Gerçek agentı elle düzeltmek yerine üretim mantığını düzeltip yeni sürüm üret.

## Önce kapatılacak konuşma ve state hataları

**Yanıtın güvenli karar yolunda kalması.** Gerçek çağrıda müşteri “Yes, this is Daniel Reyes.” ve “Yes, that's me.” diyor. İlkinde enum dışı `none` çıkmış; ikincisinde doğru `party_yes`, düşük confidence nedeniyle reddedilmiş. Sonra `talk.matches_intent` eşleşmeyince dialogue modeli brief'te olmayan Social Security Number sorusunu sormuş. A/B doğum tarihi ve telefon son dört hanesini istiyor.

Her yeni mesaj için güncel çıkarım/karar akışını ve başarısız çıkarım için güvenli fallback'i kur. Konuşma modeli o aşamada hangi somut soruların izinli olduğunu bilsin. Bilinmeyen, düşük güvenli veya router'ın eşleştiremediği bir yanıt; yeni güvenlik alanı, yeni aşama veya doğrulanmış bilgi üretmesin. Confidence ve yönlendirme ayarlarını birlikte değerlendir; asıl kabul ölçütü bu kaçışın kapanması. Genel conversation yasaklarını mevcut workflow'un ihtiyaçlarına göre sadeleştirebilirsin; araç sonuçları, node girişleri ve global istisnalarla uyumunu test et.

**Tarihlerin güncelliği.** Canlı logda `speech_date=''` ve `confirm_date=''` yazıları şema tarafından reddediliyor; araç zarfı yine `success` diyor. Eski tarih kalırsa yeni bir “hayır” cevabı teklif sayılabiliyor. Yerel düz dictionary testleri bu platform davranışını yakalamıyor.

Tarih ve diğer konuşma alanları için platformun kabul ettiği temizleme/tüketme yöntemini doğrula. Her yeni mesajın verisini önceki mesajın değerinden ayır; alan yazılamadığında bunu görünür yap. Bir önceki tutar/tarih, yeni ret veya yeni onayı sessizce değiştirmesin. İstersen ham ifade ve normalize edilmiş değerleri ayır, mesaj kimliği/güncellik bayrağı kullan veya daha uygun bir alan yapısı seç. Seçtiğin yöntemin Freya'da gerçekten çalıştığını göster.

**Kimlikten sonraki geçiş.** Yayımlanmış karar kodunda `stage=identity` ama banka zaten `verified` iken gelen bir soru, kimlikte bırakıyor. Sonraki cevap boş ürün listesiyle ödeme dalına düşüp `service_error` kapatabiliyor. Kimlik soruları tamamlandığında stage, bank state ve dönüş rotası tutarlı olsun. Araya giren soru/insan talebi gibi olaylardan sonra gerekli aşamaya güvenli dönülsün; tamamlanmış soruyu gereksiz tekrar sorma.

**Onayda birleşik niyetler.** `confirm_event=plan`, `confirm_correction=yes`, `confirm_amount=100` durumunda mevcut approval guard düzeltmeyi önce işleyip transfer talebini siliyor. Brief A41'e göre restructuring gerekir. Human/plan/hardship/dispute gibi olayların tutar veya tarih içermesi niyetlerini kaybettirmesin. Önceliği verilen brief'ten al. Hardship ile müşterinin kendi gönüllü ödeme teklifinin birlikte geldiği izinli durumları da koru.

## Kontrolleri gerçek akışa yaklaştır

Mevcut validator'ın kabul ettiği test fixture'ında `amount=1` offer guard'dan geçemiyor, fakat sonraki approval guard yalnız “yes” ile yeniden `authorized` yapabiliyor. Tek tek snippet kontrolleri geçiyor. Bu, yayımlanmış agentın aynı geçersiz tutarı kaydettiği iddiası değil; validator'da bir doğrulama boşluğu.

Modelin ürettiği örneklerin yanına, beklenen sonucu builder tarafından belirlenen bağımsız zincir kontrolleri ekle. Aynı state üzerinde offer → readback → approval → record; düzeltme; transfer; başarısız kayıt/retry; tamamlanmış kimlikten dönüş yollarını denetle. Geçerli bir teklifin açık onayla kaydolabildiği pozitif kontrol de olsun. Temel sorular: geçersiz teklifi sonraki adım yeniden yetkilendirebiliyor mu, onay doğru teklif sürümüne mi ait, aynı kayıt iki kez yapılabiliyor mu?

Graph üzerinde zorunlu guard'ın atlanmadığını ve action düğümlerinin kullanıcı girişi olmadan sonsuz döngüye girmediğini denetle. Callback/transfer ve ileride add_note için de koşulların ve veri kaynaklarının geçerliliğini ele al; yalnız create_promise'a odaklanma.

Raporda validator için ek karşı örnekler var: pre-hook ile URL/müşteri binding'inin değişmesi, alias üzerinden trusted state yazılması ve gerçek saat fonksiyonu alias'ı. Bunları canlı saldırı yaşanmış gibi sunma. Küçük bir desteklenen kod alt kümesi, yeniden kullanılan güvenilir yardımcılar veya gerçek yazma izinleriyle çözebilirsin. Genel bir Python sandbox projesi kurmak zorunda değilsin. Denetimin garanti ettiği sınırları açık yaz.

## Test kanıtlarını koru

`test_agent.py`, simülasyon çalışıp iteration/ledger okuması hata verdiğinde kimlikleri kaybedebiliyor. Session, simulation ve iteration kimliklerini bilinir bilinmez kaydet; çalıştırma, sonuç okuma ve puanlama durumlarını ayır. Servis düzeldiğinde mevcut koşuyu okumaya devam edebilelim. Belirsiz POST/yazma işlemini yeniden göndermekten kaçın.

Sürüm kanıtını her başarılı metadata okumasından ayrı biriktir. İkinci okuma hata verince ilkini atma. Gerçek call kaydı `entityVersionNumber` kullanıyor; mevcut yardımcı yalnız `agentVersionNumber` tanıyor. Kaynağın doğru call/agent'a ait olduğunu doğrulayarak iki alanın uygun bağlamını işle. Güncel dashboard sürümü, test edilen sürümün yerine geçmesin.

Typed state yazma hataları, extraction başarısızlıkları ve konuşmanın beklenmeyen fallback'e düşmesi test raporunda görülebilsin. Banka arızası, tamamlanmış başarısız vaka ve eksik değerlendirme ayrı kalsın. Resmî scorer beklentilerini değiştirme; kurtarılan çağrıya eksik ledger bilgisiyle skor uydurma.

## Geliştirme ve teslim sırası

Kısa bir plan çıkarıp konuşma/state hatalarını ve bunları yakalayan anlamlı regresyonları düzelt. Mevcut model promptu uzamış; güvenilir kontrolleri kodda tutup aşama talimatlarını sadeleştirmek uygun. Her düzeltmeyi kalıcı prompta yeni bir yasak ekleyerek yapman gerekmiyor. Mimariyi değiştireceksen bu hataları nasıl kapattığını göster.

Builder'dan yeni sürüm üret, dry-run/publish/readback/export ve trace zincirini koru. İlk canlı eşik PUB-01 bir kez; geçerse aynı yayımlanmış sürümle ayrı geliştirme koşusunda üç tekrar. Sonra A'nın diğer vakalarını, özellikle başarısız kayıt, kimlik, hardship, tarih ve correction/pieces stillerini genişlet. A+B çoklu ürün desteği sonraki tamamlanacak kapsam olarak görünür kalsın. Bu aşamada ayrı LLM şefi veya agresif history kırpma öncelikli değil.

```bash
# Mevcut root test yardımcısı:
bash scripts/test-agent.sh AGENT_ID --only PUB-01
bash scripts/test-agent.sh AGENT_ID --only PUB-01 --reps 3
bash scripts/test-agent.sh AGENT_ID --brief A
```

Builder'ın tek çalışması kendi testleri dahil 30 dakikayı aşmasın; ayrı geliştirme testlerini bu çalışma izine yanlışlıkla katma. Üç tekrar koşusu sırasında agentı güncelleme. Aynı workspace'te tek simülasyon çalışır; ekip içinde sıraya koy. Tek Freya anahtarı ve aynı özel banka takım anahtarı kullanılsın; önceki rapordaki örnek takım anahtarını özel kanaldan düzeltin. Sırları repoya veya trace'e yazma.

Telefon modeli `freya.AGENT_LLM` olarak kalmalı. Runtime yalnız verilen banka API'sine ve export içindeki code/hooks/geçişlere dayanmalı. Gerekli kurallar ve kod yerel dosya/sürekli çalışan servis gerektirmeden taşınabilmeli. Final brief kuralları elle kaynak koda/prompta eklenmemeli; girdilerden otomatik çıkarılmalı.

Sonunda şu bilgileri paylaş:

- Değişen davranışlar ve hangi regresyonla doğrulandıkları.
- Kod commit'i, agent/workflow kimliği ve test edilen yayımlanmış sürüm.
- Build komutu, trace/export yolları ve gerçek test sonuçları.
- Kalan başarısız vakalar ve açık kapsam; servis engeli varsa eldeki simülasyon kimlikleri.

Rutin teknik tercihlerde onay beklemeden ilerle. Gerçekten eksik erişim/bilgi varsa net söyle; bağımsız yapılabilecek işleri sürdür. Hedefimiz, aynı müşteriyi üç kez kurallara uygun yürüten ve hata olduğunda nedenini gösterebilen bir sonraki sürüm.
