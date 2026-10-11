# Aynı kaynaklı tam adaydan builder ile devam

11 Ekim 2026, Europe/Istanbul. Uygulama kaynağı: `eb7fc1efe4b146d195bbb376d3ce7ac1f289a20f`.
Repo `f19207c` üzerinde temizdi; `git pull --ff-only` yeni ekip değişikliği bulmadı.
Son bağımsız review işaretçisi HEAD `f80b9c1`, uygulama kaynağı `5a70c9b` olarak korunuyor.
Bu rapor geliştirici teslimidir; yeni bağımsız review değildir.

## Küçük devam yolu

`scripts/build_agent.py --resume-build <run-directory>`, eski manifestin son üretim
denemesine ait tam aday dosyasını okur. Brief sırası, OpenAPI, builder promptu ve üç
platform belgesi; dosya yolu, SHA256 ve satır sayısıyla birebir eşleşmek zorundadır.
Aynı workflow slotu ve eski üretim commit'i de zorunludur. Eksik/değişmiş kaynak,
bozuk aday, güncel validator veya provenance hatası platform erişiminden önce durur.
OpenAPI doğrulaması hash'i alınan aynı içerikle yapılır.

Devam yolu model çağırmaz ve repair yapmaz. Güncel validation/provenance, Freya
dry-run, mevcut save/publish, readback, export ve sürümü doğrulayan test hattını kullanır.
1800 saniyelik gerçek bütçe ve mevcut yerel kilit korunur. Yeni manifest/trace eski
run'ı, üretim commit'ini, aday hash'ini ve yeniden kullanım zamanını kaydeder;
`generation_attempts` boştur. Aday ve workflow elle değiştirilmedi.

## Kaynak ve aday kanıtı

Eski üretim run'ı: `build-the-builder/out/20261011T105328711505Z/`.
Üretim kaynağı: `9d376d0d7e9f89aa09e4c4cc8ca542c57bf25ec8`; temiz kod.
Başlangıç/bitiş: 13:53:28–14:17:24; **1436.02 s**. O tarihteki validator adayı
reddetmişti. Güncel validator aynı değişmemiş adayı **179/179**, provenance **47/47**
ile kabul ediyor. Bu eski üretim süresi yeni çağrının bütçesine eklenmedi.

Kullanılan dosya: `candidate-attempt-3.json`.
SHA256: `e7f55259dd18f20518e67886267c2e4aaefeb533dcc50081008b7b3aaa4af6fd`.
Yerel doğrulamadan önce/sonra aynı hash doğrulandı.

| Kaynak | SHA256 |
| --- | --- |
| `build-the-builder/briefs/brief-a.md` | `d57c049c89aec4615f5b939c5a96ee9bd194142d17045bc4036615cfbdf0f1c7` |
| `build-the-builder/tools/openapi.json` | `9a8410b12e5c82b6c6a30e9ed7030574d6f919cafdb1e035cef7bd876b0badb8` |
| `builder/prompt.md` | `99ba844c80e2d1042f5ba7cfb5249c7ed5e3cd1c6076fecf75b5b6e8424ca2a1` |
| `build-the-builder/docs/workflow-format.md` | `4ff70b5a37b647122e6a6f3ca1a523b207dbcdf6afb32058de8451a8c7d1dcfc` |
| `build-the-builder/docs/tools-and-code.md` | `56be9c87fbfddf5855c25fe83d4633bafd885d7cba5677133c15d211eb21b711` |
| `build-the-builder/docs/api.md` | `6003c0ba733f33b5981822d3418c20e042d29107fbb1045213b35dad6bf95157` |

Bu altı kaynak eski manifestle ve yeni çağrının kaynaklarıyla aynı. Önceki eksik
üretim `20261011T123005259560Z`, kaynak `5a70c9b`, 1008.34 s tarihsel blokajdır;
onun eksik adayı kullanılmadı.

## Yerel kontroller

| Kontrol | Sonuç | Süre |
| --- | --- | --- |
| Etkilenen `tests.test_build_agent` | 13/13 | 0.185 s |
| Seçilmiş helper kilit, read-only resume ve ledger kurtarma kontrolleri | 3/3 | 0.021 s |
| Değişmemiş gerçek aday ve kaynak provenance | 179/179; 47/47 | 3.445 s |
| Builder `self_check()` ve `git diff --check` | Geçti | Ayrı ölçülmedi |

Mock kontrolleri altı kaynak değişikliğini ayrı ayrı, kaynak sırasını, eksik
manifest/kaynak/adayı, bozuk JSON/aday biçimini, güncel validator ve provenance
reddini kapsar. Dry-run reddinde üretim/repair/save yoktur. Kilit, gerçek bütçe
hatası, readback değişikliği ve yayımlanmamış sürüm de testi engeller. Eşleşen
kaynaklı olumlu kontrol aynı dry-run/publish/readback/export/test hattından geçer,
aday değişmez ve model çağrısı yapılmaz. Eski üretim/repair runner kontrolleri de geçti.

## Tek canlı devam çağrısı

```bash
bash scripts/build-agent.sh build-the-builder/briefs/brief-a.md \
  --openapi build-the-builder/tools/openapi.json --slot kaan-brief-a \
  --resume-build build-the-builder/out/20261011T105328711505Z \
  --budget-seconds 1800 --only PUB-01 --reps 1
```

16:09:30 preflight: aktif simülasyon yok; toplam 17; aynı slotta v6 yayımlanmıştı.
Telefon modeli `experimental-5` olarak korundu. Yeni run:
`build-the-builder/out/20261011T130940222950Z/`, başlangıç **16:09:40**.
Builder içindeki güncel 179 kontrol ve provenance, ardından Freya dry-run geçti.
Readback gönderilen alanları ve sabit telefon modelini doğruladı; export alındı.
Bitiş **16:12:36**; toplam **176.53 s**, bütçe içinde. Manifest `completed`,
`code_dirty=false`, `generation_attempts=[]` ve test sürümü doğrulanmış olarak kapandı.
Eski aday ile yeni run'ın tam aday JSON'u birebir aynı; export da bütün gönderilen
workflow alanlarını koruyor. Yeni model üretimi veya onarım yok.

| Kimlik | Değer |
| --- | --- |
| Slot | `kaan-brief-a` |
| Agent | `404df3cd-803d-4656-89ac-ac122f9d31d2` |
| Workflow | `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d` |
| Yeni yayımlanmış sürüm | **v7** |
| Sürüm ID | `c8c90f97-a11c-480b-bafe-b7125680f419` |
| Export | `build-the-builder/out/20261011T130940222950Z/export.workflow.json` |
| Export SHA256 | `aa5ca4332929a87d591580d61ded077fba4b853ae9a7da2f09ac324c1f3bf0cf` |

### Builder içindeki tek PUB-01

**1/1 geçti**, banka kayıtları ve konuşma kontrolleriyle. Test kanıtı yalnız **v7**
bildiriyor; sürüm doğrulama hatası yok. Simulation:
`6d9cb581-b46f-4507-8d18-989b0c3b2a27`; iteration:
`94a48a95-a370-4352-8eae-2d8b3678d66d`. Test çalışma süresi yaklaşık **167 s**.
Akış: `verify_identity → verify_identity → get_account → create_promise → close_call`.
En yavaş agent cevabı **29 s**; bu tek ölçüm yavaşlığın nedenini kanıtlamaz.
Sonuç klasörü: `build-the-builder/results/20261011T130947967547Z-404df3cd/`.
Call: `66f9a313-2550-4114-9119-f426d81fbabe`; call ve iteration kanıtları v7'yi doğruluyor.

### Aynı v7 üzerinde tek tam Brief A

```bash
bash scripts/test-agent.sh 404df3cd-803d-4656-89ac-ac122f9d31d2 --brief A --reps 1
```

Tam A öncesinde aynı yayımlanmış v7 ID'si ve boş aktif simülasyon listesi yeniden
doğrulandı. Ayrı geliştirme testi **16:13:04–16:22:27** arasında tamamlandı;
helper toplam süresi yaklaşık **563.02 s**, simülasyon çalışma süresi **541.17 s**.
Sonuç **4/10**: PUB-01, PUB-02, PUB-03 ve PUB-08 geçti. Resmî banka/konuşma
puanlaması değiştirilmedi. Tam A içindeki PUB-01, bu grubun normal parçasıdır;
ayrı bir PUB-01 tekrar testi başlatılmadı.

Simulation: `6b91beeb-e7c2-4d6b-8bfd-ae18ac6117b9`; iteration:
`9958e79c-ad44-4238-8298-6c70a98948f0`. Sonuç klasörü:
`build-the-builder/results/20261011T131304090587Z-404df3cd/`.
Helper `completed`, komut çıkışı `1` (puanlanmış müşteri başarısızlıkları).
Sürüm kanıtı yalnız **7**; okuma hatası ve kayıtlı schema/extraction/router
diagnostic hatası yok. Bütün 10 call'ın agent/workflow/v7 sürüm ID'si ayrı kontrol edildi.
Bu, her cevabın doğru sınıflandığı anlamına gelmez: semantik yanlış sınıflamalar
aşağıdaki raw olaylarda görünür, diagnostic hata sayılmaz.

| Vaka | Sonuç | Call ID |
| --- | --- | --- |
| PUB-01 | Geçti | `e08ecfc2-e7a8-4fb1-913f-8e9ffa047758` |
| PUB-02 | Geçti | `f9150d50-68b4-4190-85e3-db9869ce21cc` |
| PUB-03 | Geçti | `870e56a3-bf24-4263-8c4d-19ad1e6a0d41` |
| PUB-04 | Kaldı | `321fc40e-fa70-4128-825c-9e28d923976e` |
| PUB-05 | Kaldı | `8e604ea0-5f28-41c3-a990-7d5daf00c72e` |
| PUB-06 | Kaldı | `716fd65e-41c8-458f-9fcc-063907fa6996` |
| PUB-07 | Kaldı | `3f9ca412-9c20-4a7b-a165-3ab35599ff1b` |
| PUB-08 | Geçti | `baa082e7-6517-4236-ba7f-5b15e9f07f99` |
| PUB-09 | Kaldı | `0aea9cd3-89b4-43f1-a1da-8085d62e2677` |
| PUB-10 | Kaldı | `62b3e83e-2658-4863-9742-7d7aeedc9cfa` |

### Başarısız müşterilerde ilk takılma noktası

| Vaka | İlk somut sorun | Devamındaki sonuç |
| --- | --- | --- |
| PUB-04 | Kimlik/banka doğrulaması geçti. Extraction ilk ödeme cevabını `offer`, tarihi kelimeyle `the sixth of November` olarak taşıdı. `offer_guard.date_value` sayıyla gün beklediği için tarihi çözemedi; `offer_guard → listen` aynı kesin gün sorusuna döndü. Müşteri aynı tarihi açıkça tekrarladı; sorun eksik cevap değildi. | 23 Ekim son tarih teklifine ulaşmadı; robot sorusu da cevaplanmadı. Tekrarlanan sorular ve `exceeded-max-duration`; banka kaydı `no_promise/refused`, vaat yok. |
| PUB-05 | İlk destek reddi indirim sorusuyla birlikte geldi. Extraction bunu `question` yaptı; `support` durumundaki açık reddi uygulamak yerine karar yolu mevcut destek sorusunu tekrar sundu. | Destek üç kez teklif edildi. Banka kapanışı doğru `no_promise/hardship`; konuşma kontrolü kaldı. |
| PUB-06 | Minimum teklifinden sonraki minimumun ne olduğu sorusu `question` olarak geldi. `floor_offered=yes` olmasına rağmen karar yolu cevaba mevcut ödeme teklifini ekledi. | Minimum teklif tekrarlandı. Doğru tutar/tarih ve tek vaat bankaya kaydedildi; konuşma kontrolü kaldı. |
| PUB-07 | İlk belirsiz tarihten sonra bir kesin gün sorusu uygundu. Sonraki `Monday the twenty-sixth` extraction'da `offer` ve aynı tarih metni olarak vardı; ödeme tarih ayrıştırıcısı kelimeyle günü çözemedi. | Aynı soru 16 kez tekrarlandı; 26 Ekim tatili/27 Ekim teklifi işlenmedi. Vaat ve `close_call` yok; `exceeded-max-duration`. |
| PUB-09 | Düşük taksit isteği ilk ödeme cevabında `offer` olarak sınıflandı. Karar kodunun restructuring kapısı `speech_event=plan` bekliyor; mevcut metindeki plan isteği bu kapıya taşınmadı. | Yanlış tarih/tutar ve ikna akışına girdi; restructuring transferi yok, kapanış `no_promise/refused`. Daha önce bir kimlik sorusu tekrarlandı ama banka doğrulaması sonradan tamamlandı; sonucu bozan kalıcı ayrım ödeme aşamasındaydı. |
| PUB-10 | İlk `create_promise` kontrollü `service unavailable` döndü; izinli tek retry başarılı oldu. İlk puanlama reddi, konuşma hakeminin zorunlu açılıştaki çağrının kaydedildiği bilgisini erken vaat kaydı iddiası saymasıdır. | Tek doğru vaat ve doğru kapanış bankada var; vaat kaydedildi cümlesi gerçek başarıdan sonra söylendi. Raw judge nedeni ve konuşma bu ayrımı açıkça gösteriyor; yanlış hakem yorumu olarak değerlendiriyorum. Resmî FAIL değiştirilmedi. |

PUB-05, PUB-06 ve PUB-10'un ledger tarafı geçti, konuşma tarafı kaldı.
PUB-04/PUB-07 tarih sorunları kimlik tarih ayrıştırıcısında değil, ödeme
`offer_guard` ayrıştırıcısındadır. PUB-05/PUB-06/PUB-09'da kod istisnası veya
unmatched route yok; yanlış olay türü/önceliği veya soru tekrarı vardır.
PUB-10'un ilk servis hatası testin beklenen banka hatasıdır; genel altyapı blokajı değildir.

Ek somut kusur: PUB-05/PUB-06/PUB-09/PUB-10 kapanışında `{{terminal_text}}`
literal olarak konuşmaya çıkmış. Bu, tüm gönderilen alanları koruyan readback'in
şablonun canlıda doğru çözüldüğünü kanıtlamadığını gösterir. Sonucun kapsamını
aşan düzeltme veya elle workflow değişikliği yapılmadı.

Tam A'da en yavaş cevapların medyanı yaklaşık **28 s**, en yavaş cevap **47 s**;
müşteri tarafından kapatılmış başarısız çağrı yok. PUB-04/PUB-07 süre sınırına
takıldı ve tekrar döngüsü de doğrudan görünür; bütün hataları model yavaşlığına
bağlamak için kanıt yok. Yeni build, repair veya test tekrarı başlatılmadı.
Read-only resume gerekmedi; iki simülasyonun bütün okumaları tamamlandı.

16:24:20 son GET kontrolü: aktif simülasyon yok; toplam **19** (başlangıçtaki
17'ye yalnız bu iki simülasyon eklendi). Aynı **v7** ve sürüm ID'si yayımlanmış;
workflow alanları ve telefon modeli hâlâ gönderilen değerlerle eşleşiyor.
Aday ve export hashleri aynı kaldı. Kanıt:
`build-the-builder/out/validated-candidate-checks/post-test-readback.json`.

## Kapsam ve yerel kanıtlar

Kontrol edilmedi: tüm değişmemiş unit suite, yeni/gizli girdilerden güvenilir üretim,
A+B ve ek konuşma stilleri. Bu yol yalnız aynı girdili mevcut A adayını yeniden
kullanır; farklı girdilere otomatik taşımaz ve genel üretim sorununu çözmüş sayılmaz.
Yeni dependency, cache framework, mimari veya validator genişletmesi eklenmedi.

Ham kanıtlar `build-the-builder/out/validated-candidate-checks/`, yeni run dizini
ve `build-the-builder/results/` altında ignored olarak tutulur. Anahtarlar ve ham
trace/export Git'e eklenmez. Bu dosyalar bu checkout'ta vardır; Git ile paylaşılmaz.
