# İki validator düzeltmesi ve tek canlı doğrulama

Freya hackathon projemizde son review tamamlandı. Şimdi kalan iki validator açığını kapatıp aynı görev içinde yeni agent üretmeni ve canlı sonucu ölçmeni istiyoruz. Doğrudan başla; rutin kararları kendin ver. En kısa sürede çalışır, review edilebilir teslim yap. Dosya/sınıf düzenini ve çözüm ayrıntılarını sana bırakıyoruz.

Önce güncel Git durumunu, `PROJECT_CONTEXT.md`, `research/builder-review-484e6b2.md` ve ilgili kodu oku. İncelenen uygulama `f22ea8b`; review raporu `a4fb52f` ile pushlandı. Daha yeni düzeltme varsa farkını kontrol et, işi yeniden yapma. `build-the-builder/.claude/skills/build-phone-agent/SKILL.md` dosyasını da oku; brief/API'yi esas alma ve araç sonucuna göre ilerleme ilkelerini kullan. Bu görevde aşağıdaki tek üretim/test sınırı geçerli. Önceki kaynak-only görev tamamlandı; **bu mesaj yeni üretim, publish ve canlı testi de kapsıyor.**

İki düzeltme:

1. **Geçersiz kılınan kimlik kurallarını hâlâ zorunlu sayma.** `builder/validation.py` içindeki `_identity_requirements`, `replaces/replaced_by` ilişkisini dikkate almıyor. Eski brief DOB + telefon son dört hane isterken yeni memo bunları tek doğum yeri sorusuyla değiştirdiğinde, doğru text-only aday eski sorular eksik diye reddediliyor. Eski kaynakları denetim için koru, yürürlükteki gereksinimleri doğru hesapla. Sadece modele ait bir override etiketiyle gerçek gereksinimin silinmesine izin verme; kaynak ve öncelik desteğini denetle. Yeni memo için pozitif, temelsiz override için negatif küçük regresyon ekle. Genel bir prose parser veya yeni framework gerekmiyor.

2. **Business-failure retry'da onaylı banka isteği değişmesin.** `retry_limit()` HTTP 200 / `data.ok=false` sonrasında ikinci denemenin sayısını ve yetkisini kontrol ediyor, isteğin ilk onaylı istekle aynı kaldığını kontrol etmiyor. Sentetik bozuk adayda onaylanan 25 ikinci denemede 999 oluyor ve validator kabul ediyor. HTTP-error yolundaki mevcut değişmezlik kontrolünü bütün izinli retry yollarına tutarlı uygula. Aynı isteğin izinli retry'ı geçsin; ürün/tutar/tarih değişen örnekler reddedilsin. Deneme sınırı, timeout güvenliği ve ikinci denemede başarı davranışı korunsun. Bu rakamlar yalnız test örneği; üretim değerleri brief/API'den gelsin.

İlgili anlamlı yerel regresyonları ve builder self-check'i çalıştır. Etkisine göre gerekli diğer kontrolleri seç; değişmeyen tüm suite'i tekrar tekrar çalıştırma. Yerel hata düzeltip etkilenen testi yeniden çalıştırman normal. Kontroller geçince düzeltilmiş kaynak commit'ini kaydet ve **onay beklemeden canlı aşamaya geç**:

- Mevcut Brief A ve kendi OpenAPI'siyle **bir builder çalıştırması** yap. Mevcut sınırlı otomatik repair mekanizmasını kullanabilirsin; bu çalışma kendi testleri dahil en fazla 30 dakika sürsün. Yeni bir builder/yeniden üretim döngüsü başlatma.
- Yeni agentın workflow/agent/version kimliklerini, kaynak commit'ini, trace ve export yolunu kaydet. Builder'ın yaptığı tek PUB-01 testi yeterli; ayrıca aynı testi tekrarlama.
- Yeni sürüm yayımlandıysa **o sürümde tam Brief A'yı bir kez** çalıştır. Test boyunca agentı değiştirme. Başarısız vaka varsa konuşma ve araç kaydından somut nedeni çıkar; bu görevde tekrar üretip yeniden canlı test etme. Çözüm önerisini rapora bırak.
- Build veya platform tamamlanmayı engellerse mevcut kanıtı ve engeli raporlayıp teslim et. Bilinen simülasyonun sonuç okuması yarıda kaldıysa mevcut read-only resume yolunu kullan; aynı görüşmeleri yeniden başlatma. Altyapı hatasına sıfır puan yazma.

Generated workflow'u elle düzeltme; davranış builder'dan üretilsin. Aynı workspace'te tek simülasyon çalışır; çalışan başka test varsa çakıştırma. Mevcut ekip anahtarlarını, sabit Freya telefon modelini ve resmî scorer'ı koru. Sırlar, ham sonuçlar ve trace Git dışında kalsın; teslim için trace/export saklansın.

A+B, ayrı LLM şefi, geniş history değişiklikleri, yeni araştırma veya eski sonraki-görev promptlarına bu turda geçme. Son bilinen canlı v6'nın 3/10 sonucu yeni kaynak için kanıt değil; ölçtüğün yeni sürümle karıştırma.

`research/validator-fix-live-result.md` içine kısa rapor yaz: düzeltmeler, çalıştırılan testler ve gerçek sonuçları, kaynak commit, yeni sürüm kimlikleri, PUB-01 ve tam A sonucu, başarısız vakaların somut nedenleri, trace/export yolları ve kalan açıklar. Test edilmediyse açıkça belirt; başarı uydurma. Paylaşılabilir kod ve raporu commit/push et, ekip değişikliklerini ezme. `PROJECT_CONTEXT.md` içindeki son bağımsız review commit'ini kendi tesliminle ilerletme.

Son cevabında commit, rapor ve ölçülen sonucu verip görevi bitir. “Başlayayım mı?” diye sorma veya yeni bir geliştirme turu açma; sonraki review'u biz yapacağız.
