# Mevcut iş tamamlandıktan sonraki geliştirme

Bu, devam eden görevin **ardından** yapılacak iş. Önce mevcut görevi ve sonuç raporunu tamamla; sonra bu metne geç. Önceki görevin testlerinin geçtiğini varsayma. Amaç, çalışan çekirdeği Brief A'nın kapsamına, ardından A+B çoklu ürün akışına taşımak. Teknik tercihleri sana bırakıyoruz; küçük ve güvenilir çözümleri tercih et.

## Önce geldiğin noktayı belirle

Kendi son değişikliklerini, test çıktılarını ve varsa servis hatalarını oku. Repo bağlamı `PROJECT_CONTEXT.md`, tasarım `DEVELOPMENT_PROMPT.md`, önceki iş `NEXT_DEVELOPMENT_PROMPT.md` içinde. Eski review bulgularını yeni sürümün durumu gibi sunma. Son kodun, yayımlanan agentın ve test edilen sürümün eşleşmesini kontrol et.

PUB-01 aynı yayımlanmış sürümde üç kez gerçekten geçmediyse önce bunu tamamla. Hata varsa önceki işin kalan düzeltmesini yap. Tamamlanmış başarılı tekrarları gereksiz yere baştan çalıştırma. Yalnız local testlerin veya ledger'ın geçmesi, konuşma politikasının da geçtiğini kanıtlamaz. Altyapı engeli varsa bunu agent hatasından ayır; yeni kapsama çalışırmış gibi geçme.

## 1. Brief A'nın kalan davranışları

İlk eşik sağlandıysa A'nın bütün resmî vakalarını bir kez çalıştır. Başarısız vakada konuşmayı, banka kayıtlarını ve state/geçişleri birlikte incele; üretim mantığını düzeltip builder'dan yeniden üret. Hatalı sonucu yakalayan anlamlı bir regresyon ekle. Resmî kit/scorer beklentilerini başarı elde etmek için değiştirme; son agentı elle düzeltme.

Özellikle üçüncü kişi/gizlilik, kimlik hataları, tarih ve tatil hesabı, alt tutar, hardship, paid/dispute, restructuring ve başarısız kayıt/retry yollarını değerlendir. A'da ciddi açık kalırsa önce onu kapat. İlgili az sayıda vakada `pieces`, `corrects` veya `asks_back` gibi stilleri dene; bütün vaka × bütün stil × üç tekrar kombinasyonunu körlemesine çalıştırmak gerekmiyor. Kod değişmediğinde ve test yeni bilgi üretmediğinde aynı koşuyu tekrar tekrar başlatma.

## 2. A+B ile çoklu ürün

A çekirdeği güvenilir hale gelince Brief B'yi **A+B birlikte** girdi vererek destekle. A için çalışan adayı koru; B için ayrı slot/sürüm kaydı kullan. Önce kitteki gerçek B kurallarını oku. Bu metindeki hatırlatmaların yerine girdileri esas al; B'ye özgü değerleri kalıcı builder koduna/promptuna elle gömme.

Önemli davranışlar:

- Ürünleri banka API'sinin sırasıyla yönet. Her ürünün tutarı, deadline'ı, deneme sayısı, teklif/onay/kayıt durumu ayrı olsun. Önceki ürünün alanları veya onayı sonraki ürüne sızmasın.
- Bütün ürünleri tanıt, hepsini bugün ödeme sorusunu bir kez sor. Ortak tarih önerisinde deadline'ları ürün başına uygula ve değişikliği açıkla.
- Önerilen sözleri birlikte geri oku, tek açık onay al, sonra ürün başına kayıt yap. Düzeltme ilgili onayı geçersizleştirsin. Başarılı kayıt ile yalnız anlaşılmış teklif ayrı kalsın.
- Başarılı kayıtları koru; diğer üründeki hatayı bütün görüşme başarısız olmuş gibi anlatma. Promise başarısı, retry ve nihai outcome girdideki kurallara dayansın.
- Promisesiz ürünün note adayını, bankaya yazılmış note'tan ayır. Herhangi bir transferde öncesinde veya sonrasında hiç note olmaması kuralı, yazma zamanını etkiliyor. Sonradan gelen transfer geri alınamayan erken note hatası yaratmasın.
- Ürün bazındaki paid/dispute akışı diğer ürünleri gereksiz yere sonlandırmasın. Transfer, kısmi başarı ve kapanış önceliklerini doğru uygula; `close_call` doğru son işlem olsun.

Önce çoklu ürün state/işlem zincirlerini yerel kontrollerle doğrula; sonra B'nin üç resmî vakasını dene. Düzeltmelerden sonra son adayın bu vakalardaki kararlılığını aynı sürümde üçer başarılı koşuyla ölç. Tekrarların sırasını süreye göre seç; eksik doğrulamayı raporla. B testi yalnız üç vaka içeriyor; A davranışlarının da korunduğunu anlamlı regresyonlarla göster.

B agentını özgün A expected sonuçlarıyla körlemesine puanlama: B'nin note kuralları bazı A beklentilerini değiştiriyor. Gerekirse özgün kiti koruyarak, değişikliklerinin politika gerekçesini açık yazdığın ayrı B regresyonları kullan. Bir JSON'a yeni case ID yazmak bankada müşteri oluşturmaz; özel hesap/hata birleşimleri için yerel mock veya belgelenmiş fixture yolu gerekir.

## 3. Girdilere gerçekten uyduğunu küçük bir deneyle göster

Çekirdek çalıştıktan sonra, sentetik girdi varyasyonlarıyla builder'ın eski brief'i ezberlemediğini kontrol et. Örneğin takvim/limit değişikliği veya eski kuralı açıkça değiştiren bir memo. API alanı/enum değişimini de yeni OpenAPI ile birlikte değerlendirebilirsin. Küçük, anlamlı örnekler seç; her biri için pahalı bir canlı agent üretmek zorunda değilsin.

Beklenen sonucu bağımsız belirle; kaynak → çıkarılmış politika → üretilen davranış ilişkisini göster. Sonuçlara uygun sahte public müşteri uydurma. Farklı brief için A/B test müşterilerinin geçerli olduğunu varsayma. Finalde elle kural eklemeden girdiden üretme ve kendi run'ını bütçesinde bitirme hedefini koru.

## Çalışma ve sonuç

Kaan kontrolcü, aşamaya gerekli bağlam, güvenilir yapılandırılmış state ve gerçek araç yetkileri ana tasarımımız. Ayrı LLM şefi veya agresif history kırpma bu aşamanın ön şartı değil. Yeni bir framework kurmak yerine ölçülen hata ve kapsam eksiklerini çöz. Telefon modeli sabit kalsın; runtime export içinde taşınsın.

Her builder run'ı kendi testleri dahil 30 dakika sınırını korusun; ayrı geliştirme testlerini o run'ın süresiyle karıştırma. Aynı workspace'te bir simülasyon çalışır; test edilen agentı koşu sırasında güncelleme. Servis okumaları bozulursa bilinen simülasyon kimliğinden devam et; belirsiz POST/yazmayı yeniden gönderme. Altyapı sorunu sürerse canlı çağrıları sınırsız tekrarlamak yerine bağımsız yerel işleri tamamlayıp somut engeli raporla.

Anahtarlar, ham sonuçlar ve trace'ler Git dışında kalsın; teslim için tam trace/export'u koru. Sonunda `research/third-development-result.md` içine kısa bir sonuç yaz: değişen davranış, commit, A/B agent/workflow ve test edilen sürümler, vaka bazında gerçek sonuçlar, trace/export yolları ve kalan işler. Başarılı eski aday ile yeni adayın durumunu karıştırma. Paylaşılabilir kod/raporları commit/push et; paralel ekip değişikliklerini ezme. `PROJECT_CONTEXT.md` içindeki son incelenen commit'i reviewer doğrulamadan değiştirme; yeni geliştirme sonucuna bağlantı ekleyebilirsin.

Rutin tercihler için onay beklemeden ilerle. Kritik erişim eksikse veya sonraki adım için gerçekten insan kararı gerekiyorsa açıkça bildir. Hedef: sabah bakıldığında hangi kapsamın çalıştığı, hangi sürümde ölçüldüğü ve neyin kaldığı anlaşılır olsun.
