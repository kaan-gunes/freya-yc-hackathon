# İlk geliştirme için prompt

Bu dosyanın tamamını repoyu açtığın kodlama agentına verebilirsin. Öneriler, bir başlangıç yönü gösteriyor; daha basit ve sağlam bir çözüm bulursan gerekçesini açıklayıp uygula. Dosya adları, sınıflar, node sayısı ve kullanacağın builder modeli sana ait kararlar.

## Ne geliştiriyoruz?

Bu repoda Freya “Build the Builder” hackathonu için ilk çalışan builder'ımızı geliştirmeni istiyorum. Ekibimiz iki kişi ve bu konuda yeniyiz. Bir kişi geliştirecek, diğer kişi üretilen agentı test edip somut hataları bildirecek.

Ürünümüz, müşterilerle konuşan tek bir agenttan ibaret değil. **Verilen banka brief'ini ve ona ait OpenAPI dosyasını okuyup Freya üzerinde telefon agentı üreten bir builder** geliştiriyoruz:

```text
Brief dosyaları + ilgili OpenAPI
    → kuralları çıkar
    → yapılandırılmış politika ve aşama bilgileri oluştur
    → Freya workflow'unu üret, doğrula ve yayımla
    → agentı test et, sonucu ve çalışma izini kaydet
```

Bugünkü Brief A/B ile başlayacağız. Finalde kimlik soruları, alan adları, tutarlar, takvim, sonuç kodları ve kurallar değişebilir. Bir brief temiz bir talimat metni, diğeri mail + politika + eski kuralı değiştiren memo + kod listesi gibi dağınık bir paket olabilir. Builder'ın bu girdileri okuyarak üretmesini istiyoruz. Bugünkü bankanın değerlerini kaynak koda veya kalıcı builder promptuna gömmek istemiyoruz.

## Önce repoyu tanı

Öncelikle `build-the-builder/README.md` dosyasını, verilen brief'leri, OpenAPI'yi ve ilgili platform belgelerini oku. Brief B, A'nın üzerine gelir: B üretiminde A+B birlikte girdi olmalı.

İşe yarayacak diğer dosyalar:

- `build-the-builder/docs/workflow-format.md`, `docs/tools-and-code.md`, `docs/api.md`: gerçek platform davranışı.
- `build-the-builder/examples/agent_builder.py` ve `.claude/skills/build-phone-agent/SKILL.md`: başlangıç builder'ı. Kullanmak veya farklı bir yaklaşım seçmek serbest.
- `build-the-builder/examples/base-agent.json`: geçerli JSON yapısının küçük örneği; bütün kuralları karşılamıyor.
- `research/kit-technical-audit.md`, `policy-test-analysis-tr.md`: önemli teknik riskler ve politika ayrıntıları.
- `research/ilk-test-sonucu.md`, `test-akisi.md`, `workspace-kullanimi.md`: gerçek ilk test, yardımcı komutlar ve ortak çalışma.
- `research/sentetik-testler.md`: ek senaryo fikirleri.

Araştırma notlarının bazıları testlerden önce yazıldı. Güncel kit ve doğrudan gözlenen sonuçları esas al; eski raporlardaki “henüz test yapılmadı” gibi ifadeleri bugünün durumu sanma. Brief/API iş kurallarının kaynağıdır, araştırma notları onların yerine geçmez. Eksik veya çelişen kritik bilgiyi sessizce uydurma; kaynakları ve çözemediğin noktayı görünür bırak.

## Konuştuğumuz mimariyi nasıl düşünüyoruz?

Ana kontrol mantığının takma adı **Kaan**. Bu isim bir tasarım benzetmesi; mutlaka `kaan.py` yazman gerekmiyor.

Kaan, görüşmenin hangi aşamada olduğunu, hangi araçların kullanılabileceğini, bankadan doğrulanmış bilgileri, deneme sayılarını ve kaydedilmiş işlemleri yönetiyor. LLM insanın ne söylediğini anlamaya ve uygun cevabı kurmaya yardımcı oluyor. Kritik hesaplar, izinler ve banka işlemlerinin koşulları mümkün olduğunca açık kod ve geçişlerle uygulanıyor.

Telefon agentı aşamalar halinde çalışıyor: açılış/hatta kim var, kimlik, hesap bilgisi, ödeme görüşmesi, açık onay, kayıt ve kapanış gibi. Her aşamanın kendi küçük talimatı ve gerekli araçları var. Aşama, kendisinin “ikinci agent” olduğunu bilmek zorunda değil; görevini ve elindeki bilgileri bilmesi yeterli.

Kaan'a bırakılan bilgi düz yazı bir özetten çok, yapılandırılmış durum olsun. Örneğin toplanan cevap, cevabın tamamlanıp tamamlanmadığı, bankanın doğrulama sonucu, ürün başına teklif ve onay durumu. Modelin çıkardığı bir iddia ile bankanın doğruladığı bir gerçek birbirine karışmasın.

**Duvar / Obsidian fikrimiz:** Her aşamaya bütün talimatları yığmak yerine, küçük bir ana harita ve onun yönlendirdiği ilgili alt politika parçaları olsun. Örneğin kimlik aşaması kimlik kurallarını; ödeme aşaması tarih ve tutar kurallarını kullansın. Her aşamaya gereken ortak kurallar ve istisnalar da taşınsın. İnsan isteme veya hardship gibi bir olay yalnız tek aşamada geçerli sanılmasın.

Bu MD yapısını öncelikle builder'ın bilgiyi düzenleme yöntemi olarak düşün. Builder girdinin tamamını okuyup kapsamı kontrol etmeli; parçalama yüzünden bir kural kaybolmamalı. Görüşme sırasında agentın bizim bilgisayardaki MD dosyalarını açabileceğini varsayma. Gerekli kurallar ve kod, dışa aktarılan workflow'a taşınmalı. Fiziksel dosya düzeninden çok doğru aşamaya doğru bilgi gitmesi önemli.

**Şef fikrimiz:** Agentın çıkardığı veriyi kontrol eden bir denetim katmanı. İlk sürümde bu rolün büyük bölümü deterministik kontrollerle karşılanabilir. Ayrı bir LLM şefi her turda çağırmak şimdilik öncelik değil. Sonradan, belirsiz yorumları veya builder'ın politika çıkarımını kontrol etmek için ölçerek ekleyebiliriz. Şefin banka gerçeğini bildiği varsayılmasın: biçimi düzgün bir cevap yanlış olabilir; kimliğin gerçekten doğru olduğuna banka API'si karar verir.

**Aşamayı “öldürmek”:** Müşterinin görüşmesini kapatmak değil, önceki aşamanın görevini bitirip sonraki aşamaya geçmek. Gereksiz talimatları taşımamak istiyoruz; gereken bilgileri kaybetmek istemiyoruz. Tam konuşma/test kaydı denetim için ayrıca saklanmalı.

## İlk geliştirme sırası

### 1. Önce taşınabilir, test edilebilir bir çekirdek

Brief ve OpenAPI yollarını girdi alan, kuralları yapılandıran, Freya workflow'u üreten ve çalışma kaydı bırakan küçük bir uçtan uca akış kur. Mevcut örnek builder'ı güçlendirmek veya küçük yardımcılarla ilerlemek uygundur. İlk günden büyük bir framework kurmak gerekmiyor.

`policy.json` gibi bir ara çıktı faydalı olabilir: kimlik adımları, takvim, ödeme sınırları, istisna öncelikleri, ürün davranışı, zorunlu cümleler ve kapanış tablosu; mümkünse her kuralın kaynak konumuyla birlikte. Bu, her çalışmada o çalışmanın girdilerinden üretilen bir çıktı olsun. Önceki brief'in politikası yeni çalışmaya sızmasın. Değişiklik memo'su varsa hangi eski kuralı değiştirdiği anlaşılmalı.

### 2. Kontrol ve araç erişimi

En önemli tasarım isteğimiz: **Kimlik doğrulanmadan hesap bilgisini söylememesi yalnızca bir prompt talimatına dayanmasın. O aşamada hesap bilgisine ve ödeme araçlarına erişimi olmasın.** Kimlik öncesi prompta/test değişkenlerine borç, ürün veya beklenen güvenlik cevaplarını koyma. `get_account` ve ödeme işlemlerini yalnız güvenilir banka doğrulamasından sonra aç.

Doğrulama tamamlandı bayrağını model kendi sözüyle veya extraction ile üretemesin. Bankanın yanıtını işleyen kod/geçiş bunu belirlesin. İnsan talebi, callback veya kapanış gibi kimlik öncesinde de izin verilen işlemler için brief'e uygun yollar kalsın.

İşlem alanlarını yalnız modele bırakmak yerine, müşteri/ürün kimliklerini güvenilir durumdan bağla; tutar, tarih ve enum değerlerini doğrula. Platformun gerçekten desteklediği mekanizmaları kullan. Bir hook'ta exception fırlatmanın isteği engellediğini belgesiz varsayma.

### 3. Kodla yapılabilecek kontroller

Tarih, iş günü/tatil, tutar sınırları, deneme sayıları, ürün sırası ve kapanış seçimi gibi kararları mümkün olduğunca kodla uygula. Tarih çıpası çağrının `now` değişkeni olsun; bilgisayarın gerçek saati değil.

Basit biçim kontrolleri, pahalı model incelemesinden önce yapılabilir. Fakat “cevap eksik/okunamıyor” ile “banka yanlış buldu” aynı şey değil. Müşteri sayıyı iki parçada söyleyebilir veya düzeltebilir. Yerel kontrol yüzünden brief'in izin vermediği bir ret ya da fazladan yanlış cevap sayacı üretme. Özel API hint'lerini ve sayaçlarını koru.

Konuşurken TC kimlik numarasının son hanesi örneğini verdik; bu yalnız bir ön kontrol benzetmesiydi. Mevcut A/B doğum tarihi ve telefon son dört hanesini soruyor. TC, baba adı gibi alanları veya gerçek dünya kurallarını verilen brief/API istemiyorsa ekleme.

### 4. Onay, kayıt ve zorunlu konuşma

Müşterinin önerdiği, açıkça onayladığı ve bankada başarıyla kaydedilen sözler ayrı durumlar olsun. Onay, belirli ürün+tutar+tarih bilgisine bağlı olsun. Müşteri düzeltirse eski onay geçersizleşsin; yeni değerler kontrol edilip yeniden okunsun.

HTTP 200 veya araç zarfındaki `status: success`, işlemin başarılı olduğu anlamına gelmeyebilir. İlgili API'nin iş sonucunu kontrol et; bugünkü örnekte bu `data.ok`. Başarısız ya da sonucu belirsiz bir kayıt için “kaydettim” deme. Retry politikasını brief'ten al; otomatik tekrar ve açık tekrar üst üste binip çift kayıt üretmesin. Önceki aracın başarı bayrağı yeni işlemde yanlışlıkla kullanılmasın.

Zorunlu açılış, onay, başarı/SMS ve kapanış cümlelerinin atlanmasını azaltacak sabit şablonlar veya desteklenen sabit mesaj mekanizmaları kullanmak iyi bir başlangıç. Bunları körlemesine her yolda söyleme; doğru duruma bağla. Cümle ve koşullar verilen brief'ten gelsin.

Somut ilk regresyon: Hazır örnek agent PUB-01'de doğru ödeme sözünü kaydetti, fakat Brief A'nın istediği **“You will receive a text message confirming this promise.”** cümlesini söylemedi ve resmî sonuç 0/1 oldu. Açılıştaki kayıt bildirimi, önce bugün ödeme sorusu ve onayda ürünün okunması da incelemede eksik bulundu. Ayrıntı `research/ilk-test-sonucu.md` içinde. Bu sonuç kendi builder'ımızın skoru değil.

### 5. Sonra bağlam yönetimini ölçerek iyileştir

İlk hedef aşamaya uygun kısa talimatlar ve açık durum aktarımı. Agresif history temizliğini çalışan çekirdeğin önüne koyma.

Freya'da node değiştirmek tam bir hafıza sıfırlaması değil: konuşma geçmişi ve çağrı değişkenleri kalıyor. `keep_recent` gibi kırpma ayarları dialogue modelini etkiliyor; extraction ve routing için aynı izolasyonu sağlamıyor. Değişkenlerin node başına özel kapsamı yok. `context_variables` alanının saklandığını da sunucudan okuyup doğrulamak gerekiyor.

Bu nedenle “tamamen bağımsız agentlar ve sıfır halüsinasyon” iddiasında bulunma. Gerçek erişim kısıtlarını kur, kritik durumu açık taşı, kalan platform sınırlarını belgeleyip test et. İleride bağlam kırpma veya LLM şefi eklersek aynı kuralları karşılayan bir sürümle başarı, gecikme ve hata türlerini karşılaştıralım.

## Tasarımda akılda tutulacak zor durumlar

- Müşteri kimlikteyken insan isteyebilir, ödeme görüşmesinde hardship bildirebilir. Yerel geçişler genel istisnaları gölgelemesin; öncelik brief'e göre olsun.
- “Evet, ama tarihi değiştirelim” eski teklif için kayıt onayı sayılmasın. Eski ürünün onayı, niyeti veya sayaçları yeni ürüne sızmasın.
- Finalde üç ürüne kadar destek gerekiyor. İlk küçük aşamayı A'da doğrulayabiliriz, fakat veri modeli en baştan ürün bazında durumu taşıyabilsin; B desteği sonraki tamamlanacak kapsam olarak görünür kalsın.
- Mevcut B'de herhangi bir transferde hiç not yazılmaması gerekiyor; önceki ürünün notunu erken yazmak sonraki transferde geri alınamayacak hata yaratır. Not adayları ile bankaya yazılmış notları ayır, yazma zamanını buna göre tasarla.
- Bazı sözler kaydolup diğeri başarısız olabilir. Kaydedilmiş işlemleri koru; bütünü başarılı veya bütünü başarısız gibi anlatma. Sözler, notlar, transfer ve sonuç önceliği verilen politikadan gelsin.
- `close_call` mevcut brief'te tam bir kez, son banka aracı olarak çağrılıyor; veda önce geliyor. Her çıkış yolunun tutarlı kapanışı olsun.
- Bir veri hiç yüklenmemiş olsa da LLM sözlü olarak sayı/başarı uydurabilir. Araç kısıtlarını, konuşma denetimi ve zorunlu mesaj kontrolleriyle birlikte test et.
- Fazla node ve her turda ek model denetimi gecikmeyi artırabilir. Bir kontrolün faydasını ölçmeden görüşmeye ekleme.

## Yarışma ve platform sınırları

Telefon agentının modeli `freya.py` içindeki `AGENT_LLM`; bunu değiştirme. Builder modeli serbest. Örnek builder Claude erişimi istiyor; Freya API anahtarı builder modeline erişim sağlamıyor. Mevcut erişime uygun çözüm seç; eksik erişimi gerçek test yapılmış gibi göstermeden bildir.

Telefon agentı yalnız verilen banka araç API'sini çağırabilir. Workflow içindeki code node ve Python hook'lar kullanılabilir. Bizim bilgisayardaki sürekli çalışan Python sürecine, yerel MD dosyalarına veya harici şef servisine bağımlı bir runtime tasarlama. Organizatörler export'u kendi workspace'lerinde çalıştıracak. “Kaan” kontrol mantığı, görüşme sırasında gereken kısmıyla taşınabilir workflow koduna ve geçişlerine dönüşmeli.

Final agentı insanın elle düzeltmesine ihtiyaç duymadan builder üretmeli. Düzeltmeyi üretim mantığına uygula ve yeniden üret. Gizli brief açılınca genel builder hatası düzeltilebilir; gizli brief'ten kural, değer veya isim kaynak koda/prompta elle eklenemez. Girdi dosyasından otomatik çıkarılması gerekir.

Her brief için builder çalışması, içindeki testler dahil en fazla 30 dakika. Gerçek bir süre bütçesi uygula; üç uzun test döngüsünün sığacağını varsayma. Final öncesindeki ayrı geliştirme/regresyon testleriyle builder'ın tek çalışmasının bütçesini ayır.

Puan, doğru banka kayıtları + politika + dürüstlük birlikte sağlanınca geliyor; mimariye ayrıca özgünlük puanı verilmiyor. Finalde bir vaka üç tekrarın tamamında geçmeli. Kod ve trace de inceleniyor; yeniden üretilebilirlik önemli. Hedefimiz bu tasarımın testlerde daha güvenilir sonuç vermesi.

## İlk sürümde ne teslim etmeni bekliyoruz?

İlk ara teslim: Brief A üzerinde gerçek uçtan uca çalışan, yukarıdaki güvenlik ve kayıt ayrımlarını taşıyan küçük bir builder. Tek başına çalışan bir JSON veya sadece mimari açıklaması yeterli değil; verilen dosyalardan üretim yapmalı. İlk ara teslim bütün final kapsamını tamamlamış sayılmayacak.

Şunları görmeyi bekliyoruz:

- Kurulum ve build komutu; brief/OpenAPI girdileri açık, kullanılan model erişimi anlaşılır.
- Üretilen politika/kurallar, workflow dosyası ve temel doğrulama sonucu.
- Freya'ya kaydetme/yayımlama, sunucudan geri okuma ve export. Kaybolmuş alan veya yanlış yayımlanmış sürüm varsa görünür hata.
- `agent_id`, `workflow_id`, test edilen yayımlanmış sürüm ve kod commit'i. Üretilen dosya, export ve trace'in yolları.
- Gerçek PUB-01 sonucu: önce tek koşu, düzeltildiyse üç tekrar. Sonra A'nın diğer vakalarına ve B'ye sıralı genişleme. Bir yeşil test bütün sistemin hazır olduğu anlamına gelmesin.
- Eksikler, başarısız vakalar ve platform sınırlamaları için kısa, somut rapor. Test çalışmadıysa bunu agent başarısızlığı veya başarı diye yazma.

PUB-01'in üç tekrarını geçmek ilk somut eşik; bütün final başarısı için bir iddia değil. Bundan sonra A'nın tamamı, A+B ile çoklu ürün davranışı, konuşma stilleri ve farklı sentetik brief'lere genelleme gelecek. Özellikle tarih/tutar düzeltmesi, doğrulanmadan hesap erişimi ve API başarısızlığı gibi riskler için anlamlı yerel kontroller ekle; sadece kodu tekrar eden testlerle kapsamı şişirme.

Root'tan mevcut test yardımcısını kullanabiliriz:

```bash
bash scripts/test-agent.sh AGENT_ID --only PUB-01
bash scripts/test-agent.sh AGENT_ID --only PUB-01 --reps 3
bash scripts/test-agent.sh AGENT_ID --brief A
# B kurallarıyla üretilmiş agent için:
bash scripts/test-agent.sh B_AGENT_ID --brief B
```

İleride `--style pieces`, `corrects`, `talkative`, `asks_back`, `in_words` ile çeşitlendirebiliriz. B testinin sadece üç B vakası olduğunu unutma. `--cases` dosyasına hayalî bir id yazmak bankada yeni müşteri oluşturmaz; ek fixture için desteklenen yol veya yerel mock gerekir. Resmî skor beklentilerini başarılı görünmek için değiştirme.

## Birlikte nasıl çalışacağız?

Aynı workspace'te aynı anda bir simülasyon çalışıyor. Test eden kişiye haber ver; test sürerken aynı agentı güncelleme. Her koşuda yeni workflow yaratmak yerine kendi sabit slotunu güncelle; mevcut hazır baseline'ı karşılaştırma için korumak yararlı olur.

Ekip başına tek Freya API anahtarı ve ortak banka takım anahtarı kullanıyoruz. `env.sh` yerel ve Git dışında. Anahtarları, yetkilendirme header'larını veya ham trace içine sızabilecek sırları Git'e/loglara koyma. Tam trace'i yerelde saklayıp teslim için koru; paylaşılacak raporları sır içermeyecek şekilde hazırla. Gerçek müşteri/şikayet verisi getirme; şikayet platformu fikrimiz yalnız genel hata örüntülerinden sentetik test üretmek içindi.

Trace; başlangıç/bitiş, model çağrılarının model ve kısa amacı, oluşturulan/güncellenen kimlikler, testler ve çıktıları içersin. Runtime logları da mümkünse aşama, kontrol sonucu, seçilen işlem ve kısa gerekçe göstersin. Modelin özel düşünce zincirini istemiyoruz; denetlenebilir karar özeti yeterli.

Test eden kişi örneğin “sürüm X, PUB-01: kayıt başarılı ama zorunlu SMS cümlesi yok” diye bildirecek. Sen üretim mantığını düzeltip yeni sürüm ve kimlik bilgisini paylaşacaksın. GitHub'a push kodu paylaşır; Freya'yı güncellemek için builder'ın ayrıca çalışması gerekir.

Önce mevcut dosyalardan kısa bir uygulama planı çıkar, sonra ilk küçük uçtan uca dilimi geliştir. Rutin teknik tercihler için sürekli onay bekleme. Platformun desteklemediği bir noktada tasarımı uyarlayıp gerekçesini söyle; ihtiyaç duyduğunda yalnız gerçekten eksik bilgiyi sor. Çalışan, ölçülebilen bir ilk sürüm istiyoruz; ayrıntılı tasarım uğruna ilk gerçek çıktıyı geciktirme.
