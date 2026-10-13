# Final teslimi ve karşılaştırmalı inceleme — 14 Ekim 2026

Bizim incelenen repo HEAD'i `8bc48fd4c09a3baa0e022c01e998b251e62c171a`, seçilen builder kaynağı `a8e8e06`. Karşılaştırılan [IremOztimur/agent-that-builds-agents](https://github.com/IremOztimur/agent-that-builds-agents) HEAD'i `89cfd6c`; `submission.json` builder commit'i `7a77291`. Bu ikisi arasında builder kodu değişmemiş; yalnız teslim/trace dosyaları ve submission açıklaması eklenmiş. Birincilik bilgisi kullanıcıdan; resmî sıralama/puan dökümü bu incelemede doğrulanmadı.

**Sonuç:** Sıfırın resmî nedeni henüz bilinmiyor. Kullanıcı dosyanın invalid sayılmış olabileceğini belirtti. Buna rağmen süreçteki en açık eksik kanıtlı: bizim final workflow'u hiç canlı müşteri görüşmesiyle denenmeden teslim edilmiş. Diğer ekibin seçilen koşusunda gerçek konuşma testi, hata teşhisi ve ölçülmüş sürüm seçimi var. Bizim teslim edilen workflow'da iki somut çalışma kusuru da yerelde yeniden üretildi.

## 1. Dosya invalid mıydı?

Şu kontroller geçti:

- `submission.json`, export, manifest ve trace satırları JSON olarak okunabiliyor.
- Export'un `workflow_id`, `agent_id`, `updated_at`, `workflow` sarmalayıcısı kitteki `freya.export_workflow` çıktısıyla ve referans teslimle aynı biçimde.
- `core-final-20261011` tag'i yerelde ve GitHub'da `8bc48fd` paket commit'ine çözülüyor; işaret edilen dosyalar o commit'te var.
- Selected manifest/trace, kendi workspace'imizde dry-run, publish, sürüm/readback ve export işlemlerinin tamamlandığını gösteriyor.

Bunlar organizatörün dosyayı kabul ettiğini veya kendi workspace'inde başarıyla çalıştırdığını kanıtlamaz. Bağlı Gmail'deki dar Freya aramasında final daveti bulundu; ret/puan gerekçesi bulunmadı. E-postanın Hamit tarafından gönderilip kabul edilmesi de bu checkout'taki paket dosyalarından doğrulanamaz. Resmî invalid hata mesajı olmadan ret nedenini belirli bir alana bağlamak doğru değil.

Teslimde ayrıca dikkat çeken iki nokta var:

- `submission.json.commit` tam SHA yerine tag. Tag gerçekten mevcut; bunu tek başına hata saymıyoruz. Değerlendiricinin yalnız SHA kabul edip etmediği bilinmiyor.
- Manifest'in **9.02 saniyesi yalnız resume/publish/export**. Trace daha eski generation, repair ve compilation koşularını içeriyor. Dört elapsed değerin toplamı **1881.88 saniye / 31 dakika 21.88 saniye**; ilk generation başlangıcından son export'a duvar süresi **70 dakika 12.74 saniye**. Bunlar ayrı koşular; toplamdan otomatik diskalifiye çıkarılamaz. Ancak sıfırdan tek bir 30 dakikalık otonom koşunun başarı kanıtı olarak 9.02 saniye gösterilemez. Teslim komutu da fiili resume komutundan farklı olarak yeni üretim komutu.

Kanıt: [manifest](../submission/selected/manifest.json), [trace](../submission/selected/trace.jsonl), [teslim alanları](../submission/selected/submission.json). Paket commit zamanı 11 Ekim 22:54:44 İstanbul; kapanışa yaklaşık beş dakika kalmıştı.

## 2. En büyük süreç farkı: gerçek görüşme

Bizim runner'da [case-folder modu testleri otomatik atlıyor](../scripts/build_agent.py#L486). Selected manifest `live_test.status=not_run`, neden `final_case` diyor. Son practice V10'un 8/10 konuşma ve 10/10 banka sonucu farklı, İngilizce tahsilat görevine ait; Türkçe finalin doğrulanması yerine geçmez. Mock'un 617 fixture yaprağına uyumu da telefon agentının konuştuğunu kanıtlamaz.

Referansın gerçek [final2 trace'i](https://github.com/IremOztimur/agent-that-builds-agents/blob/89cfd6ca1dcbe2c5a400fc00603ef27524a523fc/traces/final2.log#L56) önce 504 veren açılışı, küçük canlı probe'ları ve ardından çalışan açılışı gösteriyor. Sonra 12 kendi senaryosunda 11 geçiş ölçülen sürüm seçilmiş; toplam build 19.5 dakika. Bu gizli hakem puanı değil, kendi beklentileriyle ölçtükleri geliştirme sonucu.

Bu fark doğrudan önemli: schema-valid ve yayımlanmış bir workflow'un müşteriye doğru cevap verdiği ancak çalıştırılarak anlaşılır. Biz bunu finalde ölçmedik. Final API/hizmet tipine uygun yeni bir test koşucusu hazırlamak yerine practice scorer'ını atladık ve yerine uçtan uca kontrol koyamadık.

## 3. Seçilen workflow'da yeniden üretilen hatalar

### A. Başarılı API sonucunu hata sanma — güçlü genel başarısızlık adayı

`list_entry`, `list_cards_response.data` parent değerini boş string yapıyor. [`list_result`](../submission/selected/export.workflow.json#L2091), bu parent değeri bütün HTTP body sanıp JSON açmaya çalışıyor; mapping veya sonucu body olarak kaydeden hook yok.

Önceki gerçek Freya PUB-10 snapshot'ında HTTP 200 account/verify sonuçları `account_response.data.ok` ve `account_response.data.products.0.*` gibi **leaf alanlar** oluşturmuş; `account_response.data` parent anahtarı yok. Aynı veri şekli finalde de uygulanırsa parent boş kalır ve ilk kart sorgusu teknik hata yoluna düşer.

Seçilen final kodu ve gerçek public fixture ile offline karşılaştırma:

| Aynı başarılı HTTP 200 cevabının sunulması | Sonuç |
| --- | --- |
| Tarihsel engine snapshot'ındaki gibi yalnız leaf alanlar | `route=service_error`, kartlar okunmuyor |
| İlave olarak bütün body parent değişkenine konuyor | `list_ok=success`, `route=balance` |

Bu, geçmişte gerçekten görülen engine davranışıyla desteklenen güçlü bir entegrasyon kusuru. **Final değerlendirme call kaydı yok; bütün sıfırın kesin nedeni olarak sunulmuyor.** Engine'in finalde aynı şekilde davrandığı çalışma kaydıyla doğrulanmalı.

### B. Onay sırasında müşteri temsilcisi isteği siliniyor — doğrudan kod hatası

[`email_guard`](../submission/selected/export.workflow.json#L1691) ve [`week_guard`](../submission/selected/export.workflow.json#L1392), insan/ödeme/konu dışı niyeti `decision` düğümüne aktarmak için `reply_*` alanlarına geri yazıyor. Sonradan eklenen [compiler bölümü](../builder/compiler.py#L283) bu alanları koşulsuz tekrar boşaltıyor.

Seçilen guard ve gerçek graph geçişleriyle offline replay: “Temsilciye bağlar mısınız?” doğrudan decision'a verildiğinde `agent` rotası çıkıyor. Onay guard'ından geçirilince `interrupt → decision` oluyor fakat mesaj boş; sonuç tekrar `email_confirm` veya `week_confirm`. İstek kayboluyor. Bu, final görüşme kaydı olmasa da teslim edilen kodun somut hatası.

API prefix'inin yanlış olduğu ve `customerNumber/now` değişkenlerinin hiç sağlanmadığı ilk şüpheleri **elendi**. Önceki canlı kayıt node prefix'ini; selected trace içindeki BRIEF ise iki input'un sağlandığını doğruluyor. Sonucu açıklamak için elenen şüpheleri kullanmıyoruz.

## 4. Builder tasarımında ne farklıydı?

| Konu | Bizim builder | Referans builder |
| --- | --- | --- |
| Modelin çalışma araçları | Bütün kaynaklar prompt'ta; tool'lar kapalı, JSON üretimi | Tek session; dosya okuma/düzenleme ve komut çalıştırma |
| Kaynak okuma | Büyük müşteri fixture'ı dahil bütün içerik | Belge haritası/digest; büyük veri dosyaları gerektiğinde okunuyor |
| Aşamalar | Policy/workflow/checks birlikte üretim | Kural/beklenti çıkarımı, workflow, canlı test/repair için ayrı fazlar |
| Geri bildirim | Yerel/dry-run hataları modele döner; canlı sonuç generation döngüsünün dışında | Canlı konuşma ve araç sonuçları aynı session'a geri döner |
| Sürüm seçimi | Doğrulamadan geçen aday | Test edilmiş sürümler arasında en iyi ölçüm seçimi |
| Telefon konuşması | Sabit TTS + extraction + kod dalı | Modelin dar görev içinde konuşması ve araç kullanımı; hesap/limitler kodda |

Referans [SDK oturumu](https://github.com/IremOztimur/agent-that-builds-agents/blob/89cfd6ca1dcbe2c5a400fc00603ef27524a523fc/builder/lib/agent.py#L17) ve [girdi okuma](https://github.com/IremOztimur/agent-that-builds-agents/blob/89cfd6ca1dcbe2c5a400fc00603ef27524a523fc/builder/lib/intake.py#L9) kodu bu farkları gösteriyor. Bizim [tek prompt/kapalı araçlar](../scripts/build_agent.py#L563) ve [canlı testin sonradan gelmesi](../scripts/build_agent.py#L917) açık. Referansın README garantilerini mutlak saymıyoruz: ölçüm yoksa mevcut workflow'u yayımlayabilen fallback de var; seçilen gerçek trace'te ise ölçüm yapılmış.

Bizim final girdisinde 20.371 satırlık test müşteri JSON'u model bağlamına girdi. İlk final denemesi 1.175.636 karakterle CLI sınırında durdu; sonradan whitespace küçültmesi yapıldı. Kaynaklara gerektiğinde erişme fikrini builder girdisinde yeterince uygulayamadık. Referans 40 KB üzerindeki veri dosyalarını corpus'a gömmüyor; orijinal dosyaya gerektiğinde erişiyor. PDF akışında yalnız kutu metninin okları kaybedebileceğini de skill'inde açıkça dikkate alıyor.

Deterministik güvenlik kapıları, kaynak takibi ve doğrulama fikri yararlıydı. Sorun bu kontrollerin çoğunun modelin/sentetik testin hazırladığı ideal state'i ölçmesi, gerçek platformun değişken şekli ve doğal konuşma geçişlerinin finalde denenmemesiydi. Konuşmayı tamamen regex/extraction dallarına taşımak da kapsanması gereken davranış sayısını büyüttü. Daha fazla node veya daha fazla yerel test, daha yüksek uçtan uca başarı anlamına gelmedi.

## 5. Çıkarılacak ders

İlk hedef küçük bir final senaryosunu belgeler → API → gerçek konuşma → doğru işlem sonucuyla tamamlamak olmalıydı. Ardından güvenlik kapıları ve diğer dallar, aynı canlı ölçümü koruyarak eklenmeliydi. Yerel testlerde callback/consent/schema güvenliği ile gerçek platform uyumluluğu ayrı ölçülmeli; final runner'a birkaç dakikalık açılış kontrolü ve sınırlı senaryo turu ayrılmalıydı. Uzun coding-chat döngüsünü sınırlamak ile builder'ın zaman bütçeli test/repair yeteneğini kurmak ayrı işlerdir.

Bu inceleme yeni model veya canlı test başlatmadı, production/workflow/mock değiştirmedi. Read-only repo/trace incelemesi ve seçilen kodun offline replay'i yapıldı. Tekrar çalıştırılabilir yerel kanıt: ignored `build-the-builder/out/postmortem-20261014/reproduce.py/json`. Kesin invalid sebebi için organizatörün ret mesajı veya değerlendirme kaydı hâlâ gerekli.
