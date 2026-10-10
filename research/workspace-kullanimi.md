# Freya workspace'ini birlikte nasıl kullanacağız?

**GitHub kodları saklar. Freya workspace'i telefon agentını çalıştırır.** Bunlar iki ayrı yerdir. GitHub'a push yapmak, Freya'daki agentı otomatik güncellemez.

Bir benzetme: GitHub tasarım dosyalarının durduğu klasör, builder üretim yapan makine, Freya ise ortaya çıkan agentın çalıştığı atölye.

## Workspace'te neler var?

- **Workflow:** Agentın görüşmeyi nasıl yürüteceği. Ekranda kutular ve bağlantılar olarak görünür.
- **Node / düğüm:** Görüşmenin bir adımı. Hazır örnekte önce kimlik doğrulama, sonra ödeme görüşmesi var.
- **Agent:** Bu akışı kullanarak müşteriyle konuşan asistan. Test komutuna agent id verilir.
- **Variables / değişkenler:** Görüşmede kullanılacak bilgiler. Örneğin müşteri id'si, isim ve görüşmenin tarihi.
- **Version / sürüm:** Agentın belirli bir zamandaki hali. Yeni düzenlemeyi kaydetmek ve yayımlamak ayrı işlemlerdir.
- **Simulation / simülasyon:** Yapay müşterilerin agentla konuştuğu deneme.
- **Call / görüşme kaydı:** Agentın ve müşterinin söyledikleri ile kullanılan araçların kaydı.

Agent id ve workflow id ayrı kimliklerdir. Teste agent id verilir; workflow'u güncellerken veya dışa aktarırken workflow id kullanılır.

## İkiniz nasıl çalışacaksınız?

### Geliştiren kişi

Builder kodunu bilgisayarında geliştirir ve GitHub'a gönderir. Builder'ı çalıştırdığında Freya API'si üzerinden workflow oluşturulur veya mevcut workflow güncellenir. `freya.save_workflow` yeni sürümü yayımlar.

Test edecek kişiye **agent id + workflow id + yayımlanan sürüm numarası + Git commit'i** verir. Böylece hangi kodun ürettiği hangi agentı test ettiğimizi biliriz.

### Test eden kişi

GitHub'dan güncel kodu alır. Agent id ile test komutunu çalıştırır. Test sistemi müşteriyi oluşturur, agentla konuşturur, bankanın kayıtlarını ve konuşmayı değerlendirir.

Sonra "kötü konuşuyor" gibi genel yorum yerine somut hata yazar:

> Sürüm 2, PUB-01: Ödeme sözü başarıyla kaydedildi. Brief A kural 38'e göre SMS teyidi söylenmeliydi. Agent bunu söylemeden kapattı. Konuşma kaydı ve sonuç dosyası eklendi.

Geliştiren kişi builder'ı düzeltir, yeni agent sürümü üretir. Aynı test yeniden çalıştırılır.

## Dashboard'ı ne için açacağız?

1. Doğru workspace'te olduğumuzu ve üretilen workflow'un geldiğini görmek.
2. Kutulara bakarak agentın hangi adımlardan geçtiğini anlamak.
3. Güncel sürümün yayımlandığını kontrol etmek.
4. Test sonuçlarını ve görüşme kayıtlarını incelemek.
5. Gerekirse tek bir konuşmayı elle deneyerek davranışı anlamak.

Dashboard'daki kısa deneme ile resmî test puanı farklı şeylerdir. Agentın bir mesaj vermesi, bankaya doğru kayıt yaptığı veya kuralları geçtiği anlamına gelmez. Resmî test için `scripts/test-agent.sh` kullanıyoruz.

Hazır dashboard denemesinde `customer_id` dolu ve geçerli bir test müşterisine ait olmalı. Uydurulmuş bir id, bankada müşteri yaratmaz. Resmî test koşucusu ise yeni practice müşteri oluşturup gerekli değişkenleri görüşmeye kendisi verir.

## Ortak çalışırken dört alışkanlık

- Aynı workspace'te aynı anda bir simülasyon çalıştırın; testleri sıraya koyun.
- Test sürerken agentı değiştirmeyin. Sonuç hangi sürüme ait belli olsun.
- Aynı workflow'u güncelleyin; her denemede yeni workflow oluşturup listeyi doldurmayın.
- Final için düzeltmeleri builder'a uygulayın. Builder'ın ürettiği final agentını sonradan elle düzenlemeyin.

Yarışma kuralı gereği ekip başına tek Freya API anahtarı kullanılır. Aynı workspace'teki geliştirme ve test işlemleri ekibin bu anahtarıyla yapılır. Anahtar yalnız ekip içinde özel olarak paylaşılır. Arkadaşın dashboard'a erişimi yoksa, builder kodunu GitHub üzerinden geliştirip canlı testleri Kaan'ın bilgisayarından çalıştırabilirsiniz. GitHub reposuna erişmek, Freya workspace'ine erişim vermez.

Freya API anahtarı ve ortak banka takım anahtarı `env.sh` içindedir; bu dosya GitHub'a gönderilmez. Aynı workspace'te çalışırken banka takım anahtarı da aynı kalır.
