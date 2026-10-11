# Review sonrası tek tur düzeltme ve teslim

Hackathon için yaklaşık beş saatimiz kaldı. Bu görevde mevcut builder'ın aşağıdaki somut açıklarını düzeltmeni, sınırlı doğrulama yapıp sonucu bize teslim etmeni istiyoruz. Sonraki kararı biz review'dan sonra vereceğiz. Önceki `AFTER_CURRENT_TASK_PROMPT.md` kapsamına ve A+B işine bu turda otomatik geçme.

Doğrudan işe başla; rutin teknik kararlar için onay isteme. Dosya/sınıf/node düzenini sana bırakıyoruz. Küçük, anlaşılır çözümler yeterli. Bu görevi yaklaşık **60 dakikada teslim etmeyi hedefle**. **75 dakika sonunda** elindeki çalışan değişiklikleri, testleri ve kalan engeli raporlayıp teslim et; yeni uzun üretim/test turu açma. Başlangıç saatini kaydet ve süreyi takip et. Amaç her şeyi kusursuzlaştırmak değil, somut bir sonraki sürümü review'a vermek.

Önce güncel Git durumunu, `PROJECT_CONTEXT.md`, `research/builder-review-6d324cd.md` ve mevcut kodu oku. İhtiyaç duyduğun brief/API/platform bölümlerine bak. Önceki kodlama chat'inin bütün geçmişini yeniden araştırman gerekmiyor. Review'un incelediği uygulama `0331b18`; yayımlanmış agent v6, bu son kaynak düzeltmesini henüz içermiyor. Daha yeni değişiklik varsa farkı kontrol et; düzelmiş işi baştan yapma.

## Bu turda çözülecekler

1. **Onayda değişen tutar/tarihi correction etiketine bağımlı bırakma.** V6'da 420 / 14 Ekim geri okunmuşken güncel extraction `yes`, yeni tutar `300`, correction boş olduğunda hâlâ 420 için kayıt yetkisi çıkıyor. Yeni tarih için de aynı sorun var. Güncel tutar/tarih önceki readback ile çelişiyorsa eski söz yetkilendirilemesin; yeni değer denetlensin ve yeniden okunsun. Etiketin eksik olduğu tutar/tarih örneklerini ve sıradan geçerli onayı bağımsız regresyonlarla kapsa. Bunlar test örnekleri; üretim kuralları ve değerleri brief/API'den çıkmaya devam etsin.

2. **API hatasında post-hook atlandığında gerçek akış toparlansın.** PUB-10'da `create_promise` hata veriyor, platform post-hook'u çalıştırmıyor; agent gerekli ikinci denemeyi yapmadan kapanıyor. Başarı ve hata yollarından gerçekten ulaşılan bir sonuç işleme yolu kur. Güncel, kaynağı belli hata kanıtını kullan; eski status'u yeni işlem sanma. API'nin açıkça hiçbir kayıt yapılmadığını garanti ettiği ve tekrarına izin verdiği hata, sonucu belirsiz timeout'tan ayrı olsun. Regresyon post-hook'u çalışmış varsaymasın; gerçek graph üzerinden izinli retry ve belirsiz sonuçta yazmama sınırını denetlesin.

3. **Validator'ın API/kimlik varsayımlarını girdiye bağla.** OpenAPI ile workflow birlikte `amount/date` yerine başka alan adlarına doğru uyarlansa bile validator eski adları arayıp reddediyor. Semantik alan eşlemesini gerçek request ve OpenAPI ile doğrula; sabit adları kaldırırken kontrolleri gevşetme. DOB/numeric-code kontrolleri de yalnız girdinin gerektirdiği kimlik türlerine uygulansın. Zorunlu soruyu yok sayarak veya bütün testleri atlayarak geçme. Yeniden adlandırılmış doğru API için pozitif, hatalı binding için negatif örnek yeterli; kapsamlı bir varyasyon motoru kurma.

4. **Kimlik öncesindeki istisna konuşmasını düzelt.** V6, kimlik doğrulanmadan `paid` olayında “Payments can take…” diyebiliyor. Hesap erişim kapısına ek olarak sözlü çıktı ve kapanış da o aşamanın brief kurallarına uysun. İnsan talebi gibi kimlik öncesinde izin verilen yolları koru.

5. **Doğum tarihi ile ödeme tarihi gereksinimini ayır.** DOB için gerekli açık yıl şartını koru. Ödeme aşamasında “6 November”, “October 23rd” gibi gün/ay ifadelerini `now` ve brief kurallarına göre çöz; belirsizlik varsa netleştir. Telefon rakamlarının kelimeyle söylenmesi ve cardinal DOB günleri için son kaynak düzeltmelerini de koru.

Resume'ın kilit almadan eski sonucu değiştirmesi ve süreyi ezmesi review'da ayrıca var. Ana düzeltmeleri geciktirmeden küçük bir değişiklikle kapanıyorsa yap; yetişmiyorsa açıkça sonraya bırak. A+B, yeni framework, ayrı LLM şefi ve agresif history kırpma bu görevin kapsamı değil.

## Doğrulama ve durma noktası

Yerel kod yazma/debugging sırasında hatayı çözüp ilgili testi yeniden çalıştırman normal. Ancak **canlı başarısızlık → yeni agent üret → tekrar test et** döngüsüne girme.

- İlgili anlamlı regresyonları çalıştır. Kod düzeltmeleri bittikten sonra repository testlerini bir kez topluca ve builder self-check'i çalıştır. Sonradan yerel hata düzeltirsen etkilenen kontrolleri yeniden çalıştır; değişmeyen bütün suite'i durmadan tekrarlama.
- Yerel kontroller uygunsa **en fazla bir builder çalışması** başlat. Mevcut, aynı 30 dakika bütçesini paylaşan en fazla üç generation denemesi kalabilir; bu, ikinci/üçüncü ayrı builder çalışmasına dönüşmesin. Generated workflow'u elle düzeltme. Mevcut v6 export'unu/kimliğini koru; review adayı için ayrı sabit slot kullanabilirsin.
- O çalışma publish/readback/export ve içindeki tek PUB-01 testini yapsın. Üretim ve sürüm doğrulaması başarılıysa, süre elverdiğinde **aynı sürümde tam A'yı yalnız bir kez** çalıştır. PUB-01'in başarısız olması tek başına ikinci bir build başlatma nedeni değil; tam A sonuçları da bu teslimin hata raporu olabilir.
- Bu turda üç tekrar, bütün stiller, B testi veya geniş sentetik canlı test matrisi yok. Bunlara review'dan sonra karar vereceğiz.
- Üretim başarısızsa mevcut hata/trace ile teslim et. Servis engelinde bilinen ID'leri koru; belirsiz POST'u tekrarlama ve süresiz poll/resume yapma. Yeni uzun adıma başlamadan kalan süreyi kontrol et; 75 dakikalık teslim sınırına sığmayan işi başlatma.

Bir builder run'ı kendi testleri dahil 30 dakikayı geçmesin. Aynı workspace'te tek simülasyon çalışır; test sırasında o agentı güncelleme. Sabit Freya telefon modelini ve export'un kendi başına çalışmasını koru. Sırlar ve ham trace/sonuçlar Git dışında kalsın; mevcut ekip anahtarlarını değiştirme. Resmî scorer ve beklentileri değiştirme.

## Teslim

`research/focused-fix-result.md` içine kısa bir rapor yaz: hangi davranış düzeldi, hangi test doğruladı, kaynak commit, aday agent/workflow/sürüm, gerçek vaka sonuçları, trace/export yolları ve kalan açıklar. Kodda düzeltilen ile yayımlanıp canlıda doğrulananı ayır. Bir koşu eksikse skor uydurma.

Paylaşılabilir kod ve raporu commit/push et; ekip değişikliklerini ezme. Reviewer doğrulamadan `PROJECT_CONTEXT.md` içindeki son incelenen commit'i ilerletme. Son cevabında rapor ve commit'i verip **bu görevi bitir**. Başarısızlıkları saklama, yeni işe geçmek için “başlayayım mı?” diye sorma; teslimden sonra biz review yapacağız.
