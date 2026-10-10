# Starter kit v3 teknik incelemesi

10 Ekim 2026. Yerel kit kaynaklarından; canlı API çağrısı, hesap işlemi ve simülasyon yapılmadı. Orijinal kit değiştirilmedi. Buradaki mimari bir öneridir; gerçekleşmiş skor iddiası değildir.

## Yarışmanın gerçek ürünü

Ürün bir **builder**: bankanın kendisine verilen dosyalarını okuyup Freya üzerinde telefon agentı oluşturan program. Telefon agentı bu programın çıktısıdır. Final brieflerinin içerikleri önceden bilinmeyecek; sayılar, kimlik soruları, sonuç kodları, tatiller ve OpenAPI alanları değişebilecek. Finalde biri temiz spesifikasyon, diğeri mail + politika metni + değişiklik notu + kod listesi gibi dağınık malzeme olacak. İyi konuşan ama bugünkü bankayı ezberleyen agent yetmez.

Kaynak: `build-the-builder/README.md:69–92`.

- Finalde üç ürüne kadar destek şart. Brief B, A'nın üzerine uygulanır; B tek başına tam politika değildir.
- Başarı = doğru banka kayıtları + konuşma politikası + doğru bilgi verme. Bir case için kısmi puan yok.
- Gizli case farklı takvim günlerinde üç kez denenir; ancak üçünün de geçmesi sayılır. Her seferinde geçme olasılığı bağımsız biçimde %90 olsa üçlü geçiş yaklaşık %73 olur. Bu yalnızca güvenilirlik ihtiyacını açıklayan örnek hesap; gerçek koşular bağımsız olmayabilir.
- Telefon agentının modeli sabit (`freya.py:83–95`); builder modeli serbest.
- Builder çalışması testleri dahil en çok 30 dakika. Her final briefi için ayrı iz/trace ve platformdan dışa aktarılmış workflow gerekir.
- Final briefleri açıldıktan sonra genel hata düzeltilebilir, finalin hiçbir kuralı/sayısı/ismi builder kaynaklarına veya promptlarına elle eklenemez. Dosyalardan otomatik çıkarım esastır.

## En uygun geliştirme yaklaşımı

Acemi iki kişilik ekip için sıfırdan büyük bir framework yerine örnek builder'ın kısa skill'ini güçlendirmek ve küçük, deterministik yardımcıları eklemek mantıklı. Örnek builder'ın A'da 10/10 yaptığı README'deki bir organizatör beyanı; bu ekip için ölçülmüş sonuç değil. A başarısı temel eşik; B, konuşma çeşitleri ve değişmiş brieflerde genelleme fark yaratır.

Önerilen pipeline:

1. **Girdi paketi:** brief dosyaları + o briefin OpenAPI'si. API dosyasının yolu açık CLI argümanı olsun; sabit `tools/openapi.json` kullanımı finalde yanlış API'ye derleme riski yaratır.
2. **Politika çıkarımı:** güçlü builder modeli kaynak alıntısı/konumuyla `policy.json` oluştursun: kimlik adımları, takvim, tutar tabanları, deneme limitleri, öncelik/istisnalar, transfer koşulları, sonuç tablosu, çoklu ürün kuralları. Her zorunlu alanın kaynak desteği olsun. Çakışan memo ve politika için geçerlilik/öncelik çıkarımı yapılsın; belirsizliği uydurarak doldurmasın.
3. **Kapsam denetimi:** ikinci model geçişi her kuralın politikaya, politikadaki her kararın agent davranışına yansıdığını incelesin. Bu model finalin içine elle kural sokmaz; verilen kaynakları otomatik değerlendirir.
4. **Workflow derleme:** sabit Freya yapısını kodla üret; değişen iş değerlerini yalnızca çıkarılmış politikadan ve API şemasından doldur. JSON'ı baştan sona serbestçe yazdırmak schema hatalarını artırır.
5. **Yerel doğrulama:** JSON, Python snippet syntax, hedef düğümlerin varlığı, izin verilen alanlar, OpenAPI required/enum eşleşmesi, her action'ın hata yolu, her çağrının kapanış yolu. Gerçek bankayı aramadan yapılabilir.
6. **Freya dry-run → save/publish → read-back:** platformun sessizce attığı alanları yakala. Platformdaki kaydı dışa aktar ve test edilen yayımlanmış sürümle tutarlı olduğunu kontrol et.
7. **Bütçeli test/onarım:** tamamlanan testin transcript ve ledger nedenlerini oku, belirli hatayı düzelt. Kalan süreye göre ikinci tur; körlemesine üç tam koşu değil. Trace'e başlangıç, bitiş, model/amaç, workflow/sürüm, testler ve export bilgisi yaz.

Genel derleyici yazmak bir öneridir, kitte hazır böyle bir bileşen yok. Süre kısıtında önce mevcut agentic loop'u iyileştirmek, sonra en riskli hesapları hooks'a almak daha gerçekçi.

## Runtime'da neler kod olmalı?

LLM: insanın niyetini ve doğal ifadeyi anlamak, kısa ve doğru cevap vermek. Python state/hooks: policy kurallarını uygulamak ve bankaya gidecek veriyi hesaplamak.

- `now` call değişkeni tek tarih çıpası; gerçek sistem saatini kullanma.
- İş günü ekleme, tatil atlama, son tarih, bu/gelecek hafta anlamı, callback saat aralığı.
- Ürün sırasını ve `product_id` değerlerini `get_account`tan al; modelin id uydurmasına izin verme.
- Ürün bazında borç, floor, band, son tarih, deneme sayacı, teklif geçmişi, niyet/nota gerekçe.
- Kimliğin tamamlanma durumu; başarılı cevapları yeniden sormama; toplam yanlış cevap limiti ve özel hint istisnası.
- Onaylanan ürün/tutar/tarih üçlüsünü sabitle; müşteri düzeltirse önceki onayı geçersizleştirip tekrar oku.
- Promise kaydı başarılı olmadan kaydedildi deme; yalnızca tanımlı kadar retry; kayıtlı ürünü tekrar yazma.
- Notları çoklu ürün çağrısının sonucuna kadar tamponla. Brief B transferde hiçbir not istemiyor; erken `add_note` sonradan geri alınamayan hata olabilir.
- Kapanış sonucunu kayıtlı promise'lar, notlar ve transferden deterministik türet; `close_call` tam bir kez ve son araç olsun.

Örnek durum akışı: açılış/hatta kim var → kimlik → hesap ve tarih hazırlığı → ürün müzakeresi → toplu okuma/onay → kayıtlar/notlar → veda ve `close_call` → silent end_call. İnsan isteme, hardship, dispute gibi olayların öncelik sırası brief'ten alınmalı. Çok fazla küçük passthrough düğümü gecikmeyi artırır; related optional actions tek conversation düğümünde kalabilir.

## Puan kaybettiren kit/platform ayrıntıları

1. Banka API politika motoru değil. Tatilde/son tarihten sonra ödeme sözü kabul ediyor. `ok: true`, brief'e uygunluk kanıtı değil (`tools/openapi.json`, info.description).
2. Her user turunda extraction, routing ve dialogue ayrı çağrılar. Dialogue promptuna yazılan yönlendirme talimatı routing'i yönetmez (`docs/workflow-format.md:13–36`).
3. `tools` yalnızca conversation'da; `pre_actions` yalnızca code/api_request gibi action düğümlerinde. Yanlış yerdeki alan validation hatası vermeden silinebilir (`docs/tools-and-code.md:143–169`).
4. Backend değerleri `default` ile gönderilir; `const` çalışır değer atama mekanizması değil. Her API body alanı ayrı `body.properties` leaf olmalı (`docs/tools-and-code.md:78–109`).
5. Placeholder içeren default düğüme girişte sabitlenir. Aynı düğümde güncellenen değer beklentisi yanlış/stale argüman üretebilir. Değişken isimleri ve pre-hook kullanımı dikkatle tasarlanmalı.
6. Araç sonucu envelope içinde. Mapping `data.ok`, `data.products` gibi başlar. Tool mapping tool'da, pre_actions mapping düğümde olur (`docs/tools-and-code.md:223–287`).
7. Boolean `true`/`True` karşılaştırması sessizce bozulabilir; routing için `verified`, `failed`, `stay` gibi string durumlar daha sağlam.
8. Aynı isimli workflow değişkenleri çağrı boyunca kalır. Eski onay ve eski niyet yeni ürüne sızmasın. Ürün değişince state'i açıkça temizle. Tool `_args` ve `_response` alanları her kullanımda üzerine yazılır.
9. Ekstraksiyon confidence varsayılanı 0.95; değerler sessizce atılabilir. Özel extraction prompt built-in template'i tamamen değiştirir; gereken extractor input placeholder'ları eksikse mesaj hiç görülmez (`docs/workflow-format.md:528–609`).
10. Date type'ın built-in görece tarih yorumunu körlemesine kullanma: vague dönemleri somutlaştırabilir ve briefin özel `next Friday` anlamıyla/sentetik `now` ile çelişebilir. Bu kararları açık policy ve kodda sabitle.
11. `context_variables` API save sırasında sessizce kaybolduğu gözlenmiş. Gerekli state'i promptlarda açık `{{variable}}` olarak göster (`docs/workflow-format.md:244`).
12. Tool sonrası sessizlik ve negatif sonucu yok sayma organizatörlerce gözlenmiş. Defansif post-hook `result['data']['what_to_do_next']` gibi kısa talimat ekleyebilir. Prompt da her tool sonucundan sonra konuşma veya sonraki araç gerektiğini belirtmeli (`docs/tools-and-code.md:566–575`).
13. Yazma araçlarında otomatik retry aynı kaydı iki kez oluşturabilir. `maxRetries=0` ve politikadaki sayıda açık retry önerilir. API failure sayacı HTTP/transport başarısızlığı ile iş sonucu `ok:false` ayrımını otomatik olarak çözmez; business status'u doğrudan denetle.
14. Passthrough düğümünün son unconditional yolu eksikse deadlock. Global handler'lar yerel route'lar eşleşmeyince çalışır; yerel always/self-transition bir global interruptı gölgeleyebilir (`docs/workflow-format.md:393–412,486–526`).
15. Python snippet içinde `{{`/`}}` bulunmamalı; nested dict literal sonundaki `}}` bile sorun olabilir. `vars` kullan, try/except ve her output için fallback ata (`docs/tools-and-code.md:492–499`).
16. Sadece PUT yayımlamaz. `freya.save_workflow` günceller ve publish eder; aksi halde eski agentı test edersin (`freya.py:49–64`).
17. İlk create'de varsayılan model yanlışsa chat ilk denemede açılmayabilir. Client'ın AGENT_LLM düzeltmesi update yolunda; test override'ları simülasyonda modeli zaten sabitler. Modeli kurallara aykırı değiştirmek çözüm değil.
18. `freya.run_simulation` kuyruk ve polling için global zaman sınırı koymuyor. `agent_builder.py` max_turns koyuyor ama 30 dakikalık wall-clock guard koymuyor. Skill üç test turuna izin veriyor; üç adet 11 dakikalık koşu ve model zamanı limiti aşar. Builder için gerçek deadline şart.
19. SDK trace mesajları tutuluyor ama örnek açık bir end timestamp ve her çağrının kısa amaç kaydını ayrıca garanti etmiyor. Ek trace manifesti/final record uyumu güçlendirir.

## Mevcut testlerin gerçek kapsamı

13 public case: 10 A, 3 B. A'da happy path, third party, yanlış kimlik, son tarih, hardship, floor, vague/holiday, already paid, restructuring, transient create failure. B'de toplu ödeme, kısmi promise + refusal notları, farklı son tarihler.

`--brief B` **sadece üç B case'i** seçer. B regresyonunda A senaryolarını da kapsamak gerekir; ancak özgün A beklentileri doğrudan kullanılamaz: B bazı promisesiz ürünler için not ister, A hiç not istemez. Mevcut case id'leri korunarak A senaryolarının beklenen ledger/checks alanları B politikasına uyarlanmış ayrı bir dosya hazırlanmalı. Özgün 13 case'i filtresiz koşmak B için doğru bir başarı ölçümü değildir. `--reps 3` bir müşteriyi yalnız tüm üç koşuda geçtiyse sayar. `--style` tek seferde beş stilden birini tüm seçilmiş müşterilere uygular: pieces/corrects/talkative/asks_back/in_words. `--only PUB-...` hata odaklı kısa koşular sağlar. `--out` call id'leri ve failure'ları saklar. Kullanılacak örnekler (API key ve workspace hazır olduğunda):

```sh
python3 tools/run_cases.py A_AGENT_ID --brief A --out results/a.json
python3 tools/run_cases.py B_AGENT_ID --only PUB-12,PUB-13 --style corrects --out results/corrections.json
python3 tools/run_cases.py B_AGENT_ID --brief B --style pieces --out results/pieces.json
python3 tools/run_cases.py B_AGENT_ID --brief B --reps 3 --out results/reliability.json
```

Bu komutlar kit klasöründen çalıştırılır. Son komut 30 dakikalık final builder bütçesine sığmayabilir; final öncesi geliştirme testi olarak planlanmalı. İki kişi aynı workspace'te paralel simülasyon başlatmamalı.

Eksik public kapsam için sentetik ek testler: kimlikte açıklama sorusu/refusal/hint, yanlış numara/deceased/unclear, callback sınırları, doğrulama öncesi ve sonrası insan isteme, her iki create denemesinin başarısızlığı, onay sırasında değişiklik, kayıt sonrası değişiklik talebi, üç üründe farklı band/tarih, erken not adayından sonra transfer, ilk ürün paid diğer ürün dispute ve kapanış önceliği. Yeni takvim günleri için sadece `public-test-set.json` içindeki variables.now'u değiştirmek yetmez: run_cases canlı practice session değişkenlerini kullanır ve banka fixture'ını yalnız case id ile seçer. Banka PUB-01…PUB-13 dışında yeni practice müşteri açmaz. Yeni tarih/müşteri fixture'ları için yerel mock veya desteklenen chat kontrolleri gerekir; varsayımsal bir session endpoint'i kullanılamaz.

Genelleme testi: final öncesinde A/B'nin izinli sentetik varyantlarını hazırla; tatil ve limitleri, kimlik alanlarını, sonuç kodlarını değiştir ve temiz briefi mail/memo biçimine dönüştür. Builder'ın kaynak koduna dokunmadan değişen dosyaları okuyup farklı çıktı ürettiğini denetle. Örnek bugünkü değerleri kod içine gömmek bu testte yakalanır.

## İki kişilik iş bölümü

- Kişi 1: brief→policy→workflow, API şeması ve deterministic hesap/hooks.
- Kişi 2: public/custom test matrisi, transcript/ledger teşhisi, kurallara uygun trace/export, tek workspace simülasyon kuyruğu.

Öncelik: çalışan baseline → A+B doğru davranış → 3/3 güvenilirlik ve speech styles → değişmiş brief testleri → sade konuşma/tutum iyileştirmeleri. Şikâyet verilerinden ürün fikri çıkarmak olabilir; yarışma süresinde en yüksek doğrudan değer eksik policy ve yanlış kayıt risklerini azaltmakta.
