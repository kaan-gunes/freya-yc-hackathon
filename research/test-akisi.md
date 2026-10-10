# Geliştiren arkadaş ve test ekibi için çalışma akışı

Test komutları proje kökünden çalıştırılır. `env.sh` otomatik yüklenir; anahtarlar çıktılarda gösterilmez. Starter kit ve resmî skor kuralları değiştirilmedi; ek wrapper yalnız hata raporlama, log ve konuşma kayıtlarını tamamlıyor.

```bash
# İlk tek müşteri testi; kayıtlı hazır agentı kullanır:
bash scripts/test-agent.sh --only PUB-01

# Arkadaşının verdiği agent id ile A'nın 10 vakası:
bash scripts/test-agent.sh AGENT_ID --brief A

# B'nin üç resmî vakası:
bash scripts/test-agent.sh AGENT_ID --brief B

# Belirli bir hataya odaklanma:
bash scripts/test-agent.sh AGENT_ID --brief A --only PUB-04,PUB-07 --style corrects

# Son adayın üç tekrar boyunca kararlılığı:
bash scripts/test-agent.sh AGENT_ID --brief A --reps 3
```

Her çalışma `build-the-builder/results/<zaman>-<agent>/` altında ayrı klasöre yazılır:

- `summary.json`: tamamlandı mı, altyapıda mı engellendi, varsa skor.
- `console.log`: bütün test çıktısı.
- `official-results.json`: resmî koşucunun vaka sonuçları; ancak koşu tamamlanırsa oluşur.
- `calls/`: tamamlanan koşunun konuşma ve araç kayıtları. Konuşma indirme sorunu ayrıca summary'de belirtilir.

Çıkış kodları: `0` bütün seçilen vakalar geçti; `1` test tamamlandı ama en az bir vaka başarısız; `2` altyapı veya çalışma hatası nedeniyle tam skor üretilemedi. Skor üretilemeyen çalışma 0/10 olarak raporlanmaz.

Arkadaşın her sürüm için agent id, workflow id ve yayımlanan sürümü iletmeli. Aynı workflow güncellenebilir. Test sırasında aynı agent değiştirilmemeli; test ettiğimiz sürüm ile hata bildiriminin sürümü eşleşmeli. Güncelleme yayımlanmadan eski agent test edilmiş olur. `freya.save_workflow` yayımı yapar.

Hata bildirimi şu biçimde hazırlanır:

```text
Sürüm / agent:
Vaka / konuşma stili:
Beklenen:
Gerçek sonuç:
İlgili konuşma ve araç çağrısı:
Sonuç dosyası:
Tekrar sayısı ve kaçında gerçekleşti:
```

B agentında A senaryoları da test edilmeli, ancak not beklentileri B'ye uyarlanmış ayrı bir `--cases` dosyası gerekir. Özgün A/B dosyasını filtresiz koşmak B için doğru bir regresyon puanı üretmez. Yeni case dosyası bankada yeni müşteri fixture'ı yaratmaz.

## İlk engelin teşhisi

10 Ekim 2026'da güncel v3 kit ile yerel `freya.py`, `tools/score.py`, `tools/run_cases.py` ve OpenAPI dosyaları karşılaştırıldı; aynılar. Takım anahtarı gereken en az 16 karakter koşulunu sağlıyor. Freya yönetim API'sinde workflow kayıt/yayım çalışıyor. İlk kısa chat denemesi yanıt verdi; sonraki bir deneme HTTP 503 döndürdü. Dolayısıyla chat erişimi de her denemede başarılı olmadı.

Bankanın `POST /v1/practice/sessions` endpoint'i `{"case":"PUB-01"}` için HTTP 500, `text/plain` gövdesinde `error code: 1101` döndürdü. Browser User-Agent ile de aynı sonuç alındı. Cloudflare belgelerinde 1101, Worker'ın JavaScript istisnası üretmesi olarak açıklanıyor. Hatanın sunucudaki tam nedeni, organizatörün Worker logları olmadan bilinemez. Anahtar veya istek ile tetiklenen bir sunucu hatası olasılığı da yalnız bu yanıtla kesin dışlanamaz. [Cloudflare açıklaması](https://developers.cloudflare.com/workers/observability/errors/)

Starter koşucu, düz metni JSON olarak çözmeye çalıştığı için ayrıca `JSONDecodeError` gösteriyor. Bu ikinci hata asıl sunucu arızasını gizliyor; test wrapper'ı gerçek HTTP yanıtını görünür kılıyor.

### Dashboard kontrolünde ayrılan sorunlar

- Organizatörün hazır workflow'unda geçerli sentetik müşteri vardı. Bizim kopyamızın dashboard `test_variables.customer_id` alanı boştu. Hazır örneğin yalnız müşteri/görüşme girdileri kopyalanarak baseline sürüm 2 yayımlandı; agent politikası değiştirilmedi, doğru güvenlik yanıtları agent bağlamına eklenmedi. Sonradan API'den dolu müşteri alanı, yayımlanan sürüm 2 ve `experimental-5` modeli doğrulandı.
- Bu eksik alan dashboard denemesini etkiler. Resmî `run_cases.py`, müşteri değişkenlerini yeni practice session'dan aldığı için önceki session oluşturma HTTP 500 hatasını açıklamaz.
- Hazır dashboard müşterisiyle bankanın doğum tarihi doğrulaması, telefon son dört hanesi doğrulaması ve `get_account` çağrısı HTTP 200 ile başarılı oldu. **Bankanın tamamı çalışmıyor sonucu doğru değildi; kanıtlanan arıza practice session oluşturma endpoint'indeydi.** Bunlar doğrudan araç kontrolleridir; agent başarısı veya resmî puan değildir.
- Brave'deki test ayrıca `network path negotiation (ICE) could not complete` gösterdi. Bu, tarayıcı görüşme bağlantısının ayrı bir hatasıdır; kesin ağ/sunucu nedeni belirlenmedi. Resmî metin simülasyonunu tarayıcı mikrofonuna bağlamadan CLI üzerinden test ediyoruz.

Kanıtlar: `results/dashboard-baseline-setup.json`, `results/dashboard-original-bank-test.json`, `results/dashboard-original-bank-account.json`.

Kullanıcının paylaştığı Freya ekip duyurusunda API ve kod çalıştırma hatalarının düzeltildiği bildirildi. Bunun üzerine 10 Ekim 15:57 UTC'de PUB-01 resmî test akışı yeniden başlatıldı ve 218 saniyede tamamlandı. Yeni müşteri oluşturma, simülasyon, bankacılık araçları, puanlama ve konuşma kaydını indirme bu koşuda çalıştı. Agent sürüm 2 için sonuç **0/1**: banka kayıtları beklentiyi karşıladı, konuşma değerlendiricisi ödeme sözü sonrasında SMS cümlesinin eksik olduğunu bildirdi. Bu sonuç yalnız bir müşteri ve bir tekrara aittir; A'nın 10 müşterisi veya üç tekrar sonucu değildir. Tarayıcı ICE hatasının düzeldiği ayrıca doğrulanmadı.

Sonuç klasörü: `results/20261010T155757484043Z-3f592c60/`. Arkadaşın için okunabilir hata raporu: `research/ilk-test-sonucu.md`.
