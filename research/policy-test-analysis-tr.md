# Politika, test ve genelleme incelemesi

Kaynak: yerel `build-the-builder` v3 (10 Ekim 2026). Bu incelemede canlı Freya/banka API çağrısı yapılmadı, anahtar okunmadı ve özgün kit değiştirilmedi. Öneriler uygulama tasarımıdır; çalışan bir builder veya ölçülmüş skor değildir.

## Yarışmanın asıl hedefi

Telefon agentını elle mükemmelleştirmek yeterli değil. Teslim edilecek sistem, daha önce görmediği banka brieflerini ve onlarla gelen OpenAPI dosyasını okuyup insan müdahalesi olmadan Freya agentı üreten **builder**. Telefon agentının modeli sabit; builder herhangi bir model kullanabilir. Finalde politika sayıları, kimlik soruları, outcome kodları, takvim ve API alanları değişebiliyor. Kaynaklar: `README.md:9`, `README.md:71-85`.

Final açıldıktan sonra yeni briefin kuralını, değerini veya adını builder koduna/promptuna insan eliyle eklemek yasak. Yeni formatın tetiklediği gerçek bir parser hatasını genel biçimde düzeltmek serbest. Bu nedenle eğitici brief A'nın tatil listesini, iki güvenlik alanını veya outcome kodlarını genel builder şablonuna gömmek hatalı tasarım. Üretilen agentın briefteki değerleri içermesi ise işin kendisi: bunlar builder tarafından girdiden çıkarılmalı. Kaynak: `README.md:73-80`.

README'nin final bölümündeki bir çalıştırma ifadesi manuel adım olmamasını vurguluyor; genel kurallar ve güncel resmî teslim sayfası birden çok run arasından bir runın agentı ve o runın trace'inin gönderilebildiğini açıklıyor (`README.md:74`, `README.md:89`). Her run kendi içinde otonom ve 30 dakikadan kısa olmalı; teslim edilen export onu üreten runın trace'iyle eşleşmeli.

## Skorun anlamı

Bir müşteri ancak banka ledger'ı **ve** konuşma politikası **ve** doğruluk şartları birlikte sağlanırsa geçer. Kısmi puan yok. Ledger; outcome/reason, bütün promises, notes, callbacks ve transfers listelerini beklenenle karşılaştırıyor. Ekstra bir not veya fazla bir promise de başarısızlık yaratıyor (`README.md:57-67`, `tools/score.py`, `tools/run_cases.py:93-98`).

`close_call` son tool olmalı; brief tam bir tane istiyor. Ledger scorer son toolu kontrol ediyor, ancak her kuralı kendisi denetlemiyor. Örneğin konuşmanın başında sızıntı, confirmation ve zorlamanın sayısı transcript judge'a kalıyor. Sadece ledger yeşil olması yeterli değil.

Finalde her vaka üç kez çalışıyor ve üçü de geçmeli (`README.md:76`). Bağımsız hata varsayımında tek run başarı oranı %90 ise üçlü başarı yaklaşık %72,9; %95 ise %85,7. Bu bir ölçüm değil, neden rastlantısal prompt uyumundan ziyade kodla güvence aramak gerektiğinin matematiksel örneği.

Eşit skor önce geçen müşterilerdeki toplam söz verilen tutarla, sonra build süresiyle, sonra gönderim zamanı ile kırılıyor (`README.md:90`). Öncelik full amount istemek ve kurallara tam uyum; sırf fazla tutar için yasak baskı/teklif yapılamaz.

## Kritik kurallar ve zor birleşimler

| Alan | Beklenen davranış | Yaygın hata |
|---|---|---|
| İlk cümle | Dijital asistan + banka + kayıt bilgisi; kimlikten önce borç/tahsilat/ürün yok | Sıcak bir tanıtım içinde erken borç açıklamak |
| İsim doğrulama | Sadece açık evet, benim, speaking veya kendi adı; belirsiz yanıt için tek tekrar | `hello` veya `go ahead` yanıtını doğrulama saymak |
| Üçüncü kişi | Hesap/verifikasyon yok; sadece uygun callback/wrong number/deceased dalı | Eşin ödeme teklifini kabul etmek veya borcu açıklamak |
| Kimlik | Sorular sırayla; yalnız başarısız olan soru tekrar; toplam yanlış sayacı | Her retry'da ilk soruya dönmek veya toplamı soru başına sıfırlamak |
| Doğum tarihi | Sayısal giriş gün-ay-yıl; API'ye ISO tarih; swapped hint'te ayı kelimeyle sor | İngilizce parser'ın ay-gün varsayımı veya hint'i yanlış saymak |
| Bölük sayılar | Eksik giriş tamamlanmadan tool çağırma | `pieces` stilinde yarım telefon/dob göndermek |
| Zaman | Bütün hesaplar call variable `now` üzerinden | Bilgisayarın gerçek tarihini kullanmak |
| İş günü | Hafta içi eksi briefteki tatiller; deadline bugünden sonraki N'inci iş günü | Bugünü 1 saymak veya takvim günü eklemek |
| İkna | Tarih/tutar önerisi ret değildir; flat refusal/non-answer sayacı artırır | Müşterinin tarih teklifinde bir ikna hakkı yakmak |
| Tutar | Önce tam borç; alt sınırı agent teklif eder; kalan borç gecikmede bilgisi | `Ne kadar ödeyebilirsiniz?` diye sormak |
| Hardship | Kısa empati; baskı yok; destek aktarımı; kendi teklif verirse uygun promise mümkün | İş kaybından sonra standart ikna akışına devam etmek |
| Paid/dispute | Bu gecikmiş borç bugün ödendi = paid; geçmişte ürün kapandı/ödendi = dispute | Her `paid` kelimesini aynı dal saymak |
| Confirmation | Ürün+tutar+tarih read-back ve açık evet sonrası create | `Okay` benzeri muğlak tepkiyle erken kayıt veya değişiklik sonrası eski confirmation kullanmak |
| Tool hatası | Başarı yalnız `data.ok=true`; promise en fazla bir ek deneme | HTTP 200'ü bankanın işlemi yapması sanmak |
| Kayıt sonrası | Promise değiştirme/iptal yok; app'e yönlendir; text-message cümlesi | Aynı ürün için ikinci promise yaratmak |
| B çoklu ürün | Her ürün ilk sorudan önce açıklanır; sıra API sırası; ortak read-back, tek confirmation | Her üründe tekrar bugün ödeme sorusu veya ayrı ayrı confirmation |
| B deadline | Ürün başına hesap; ortak tarih teklifinde yalnız deadline'ı kısa ürün düzeltilir | En erken deadline'ı bütün ürünlere uygulamak |
| B final outcome | Herhangi recorded promise varsa promise; transfer bunun önüne geçer | Son ürün ret olduğu için bütün çağrıyı refused kapatmak |

Kaynaklar: `briefs/brief-a.md` bölümler 3–12; `briefs/brief-b.md:9-23`.

### En tehlikeli çoklu ürün yan etkisi

Brief B'de transfer olduğunda **öncesinde veya sonrasında hiçbir not olmamalı** (`brief-b.md:18`). Ancak promisesiz her ürün için not gerekiyor (`brief-b.md:16`). Bu yüzden görüşme sırasında reddedilen/paid/dispute ürünün notunu hemen bankaya yazmak riskli: müşteri sonraki üründe insan isterse önceki not geri alınamıyor.

Öneri: ürün kararlarını önce workflow state'inde taslak tut. Transfer gerçekleşirse bütün not taslağını at. Çağrı nihai kapanışa girdiğinde, transfer yolu artık kapanmışken notes listesini yaz ve kapat. Bu son pipeline'da konuşma devam etmesin. Transferden önce **gerçekten kaydedilmiş** promise kalır; yalnız anlaşılmış, confirmation bekleyen promise kaydedilmez (`brief-b.md:18`).

Promise commit sonucu ürün başına tutulmalı. Bir ürün iki kez hata verirken başka ürün başarıyla kaydedilmişse başarılı promise kalır; hatalı ürün service_error notu alır; final outcome promise olur (`brief-b.md:19-23`).

### Takvim sınırları için eksik tanımlanmış birleşimler

Brief A, deadline içindeki tatil/hafta sonunu sonraki iş gününe taşımayı söylüyor. Sonraki iş günü deadline dışına taşarsa genel promise deadline kuralı yine korunmalı. Ayrıca ilk ikna tarihi (`bu haftanın son iş günü`, bugün o günse gelecek hafta) olağandışı uzun tatil takviminde deadline dışına çıkabilir. Bunlar public sette yok. Kaynak üstünlüğünü açıkça çıkartan builder ve invariant testleri, böyle çakışmaları yakalamalı; yeni brief gelince insan eliyle özel tarih düzeltmesi eklenmemeli.

## 13 public case neyi kapsıyor, neyi kapsamıyor?

| Case | Kapsam |
|---|---|
| PUB-01 | Tam tutar, bugün, güvenlik sırası, tek promise, SMS cümlesi |
| PUB-02 | Eş cevaplıyor, gizlilik, ertesi iş gününe callback |
| PUB-03 | Üç yanlış doğum tarihi, kimlikte kapanış |
| PUB-04 | Deadline sonrası tarih, deadline teklifini kabul, AI sorusu |
| PUB-05 | İş kaybı, indirim isteği, destek reddi, hardship |
| PUB-06 | Tam tutar fazla, floor ve kalan gecikmiş bakiye açıklaması |
| PUB-07 | Belirsiz dönem → kesin tarih → tatil → sonraki iş günü |
| PUB-08 | Bu sabah app'te ödeme, paid |
| PUB-09 | Yeni plan / düşük taksit, restructuring aktarımı |
| PUB-10 | İlk create_promise hatası, doğru retry, tek ledger kaydı |
| PUB-11 | Üç ürün, ortak gün, tek read-back/confirmation |
| PUB-12 | Bir phone retry; bir promise, iki refused note; ayrı ikna bütçeleri |
| PUB-13 | İki ürün, ortak tarih isteği, farklı deadline |

Public set; yanlış numara, ölüm, isim belirsizliği, iki kimlik reddi, swapped-date hint, callback pencere sınırları, iki promise-service hatası, erken bantta ikna tükenmesi, confirmation sırasında değişiklik, recorded promise değişiklik isteği, transfer öncesi note temizliği ve çoklu ürün paid/dispute karışımlarını doğrudan kapsamıyor. `10/10` veya `13/13` bir kez görmek bu dallar için kanıt değil.

### Test runner ile ilgili önemli sınır

`run_cases.py --cases custom.json`, custom dosyadan persona scriptini, beklenen sonucu ve transcript checks'i okuyor. Ancak bankada session yaratırken **yalnız `case.id` gönderiyor** (`tools/run_cases.py:86`). JSON'da products/identity/now'ı değiştirmek banka fixture'ını değiştirmez. Yeni uydurulmuş case id'nin mock banka tarafından kabul edildiğine dair burada kanıt yok. Bu yüzden özel fixture kaydı destekleniyormuş gibi 50 yeni JSON case yazıp çalıştırmak doğru değil.

Desteklenen yol: aynı mevcut case id ile konuşma üslubunu değiştir; gerekli beklenen sonucu politika içinde tut. Yeni hesap/takvim/fault kombinasyonları için yerel mock ve yerel harness ya da organizatörün belgelenmiş fixture kayıt API'si gerekir. `--style pieces|corrects|talkative|asks_back|in_words` doğrudan belgelenmiş (`tools/run_cases.py:26-33`).

### Brief B regresyon tuzağı

`--brief B` sadece üç public vakayı koşar. A'nın kimlik/gizlilik/hata vakaları bu testte yoktur. B agentına bütün özgün public dosyayı vermek de doğrudan doğru değil: A'nın notes beklentileri A'ya göre. Örneğin B, doğrulanmış promisesiz PUB-05 ürününe `hardship`, PUB-08 ürününe `paid` note yazmalıdır; özgün A fixture expected listeleri notes=[] olduğundan haklı B davranışı yanlış puanlanır.

Çözüm: özgün kiti koruyarak B regresyon dosyası türet; banka fixture id'lerini aynı tut; sadece B politikasının değiştirdiği expected/checks'i gerekçeli güncelle. Kimlik aşamasında hiç hesap açılmayan vakalar için not üretmeye çalışma. Her transfer vakasında notlar boş kalmalı. B'nin A kurallarını koruyan davranışlarını bu dosyada test et.

## Önerilen doğrulama sırası

1. **Offline policy coverage:** A'nın 47 kuralı, B'nin 11 ek kuralı ve closing tablosu için her birine IR rule id + workflow aşaması + test id bağlantısı. Bu sayıların kendisi final parser'a sabitlenmez.
2. **Offline deterministik testler:** takvim, floor, ürün sırası, attempt sayacı, retry, outcome seçimi, schema allowed values. En değerli sınırlar: cuma, hafta sonu, ardışık tatil, yıl değişimi, deadline günü, callback 10:00/19:00 ve `now` eşitliği, days_late 7/8, amount floor−0.01/floor/full/full+0.01.
3. **Offline state testleri:** doğrulama olmadan hesap/borç yok; açık confirmation olmadan promise yok; aynı üründe duplicate promise yok; close tam bir tane ve son; transferte notes yok. Sadece happy-path örneklerini tekrar eden testler yerine bu invariant'ları test et.
4. **Kısa platform smoke:** export/import biçimi, ilk chat turn, API envelope, `data.ok`, string boolean ve tool sonrası konuşma. Platformda çalışan agentın gerçekten publish edildiğini kontrol et.
5. **Public baseline:** A için 10 vaka; B için 3 resmi vaka + politika uyarlanmış regresyon. Sonuçla birlikte ledger, transcript, call id, en yavaş turn ve artifact hash'i sakla.
6. **Üslup baskısı:** pieces / corrects / talkative / asks_back / in_words. Önce ilgili az sayıda vaka, sonra en iyi aday üzerinde kapsamlı seri. `talkative` stilindeki kuzen düğünü 30'unda cümlesi ödeme tarihi değildir.
7. **Kararlılık:** son aday için `--reps 3`. Her run geçmeli. Eski trace'in agentını sonradan sessizce değiştirme.

Bir workspace'te tek simulation var; takım arkadaşları birbirinden bağımsız simülasyon başlatmasın (`README.md:88`). 10 vakalık simülasyon 3–11 dakika. Final builder'ın kendi testi 30 dakika bütçesine dahil olduğundan her briefte tam 3 tekrar + 5 üslup paketi sığacağı varsayılmamalı. Kapsamlı test hazırlıkta, finalde bütçeli smoke ve gerekiyorsa seçici düzeltme yapılmalı. Yavaş model kaynaklı hataları mantık hatalarından ayırmak için transcript ve latency metriği birlikte incelenmeli (`README.md:100`, `run_cases.py:101-119`).

Ana araştırmada okunan resmi hackathon sayfası, final briefleri için practice case verilmeyeceğini ayrıca belirtiyor. Bu yüzden final builder'ın A/B public müşterileriyle kendi yeni brief agentını optimize etmesi uygun test stratejisi değil: outcome/kimlik/takvim/API şeması farklı olabilir. Final runında kaynak→IR coverage, yeni OpenAPI uyumu, deterministik hesap/state invariant'ları ve desteklenen chat smoke kontrolleri kullanılmalı; hazırlıktaki A/B başarıları finalde aynı müşterilerin geleceği varsayımına dönüştürülmemeli. Resmi kaynak: https://www.freyavoice.ai/hackathon (web araştırmasının ana kolunca doğrulandı).

## Genellenebilir builder için ara temsil (IR)

Önerilen yapı, bir hardcoded A/B sınıfı değil, bütün brieflerden kanıtlarıyla çıkarılmış bir Policy IR:

```text
policy_ir
  documents: {path, sha256, role, effective_date, supersedes}
  call_context: [{name, type, meaning, evidence}]
  identity: {ordered_questions, validation, failure_budget, hints, refusal_rule}
  privacy: {disclosure_gate, forbidden_before_gate, third_party_actions}
  calendar: {now_source, weekdays, holidays, relative_date_semantics}
  products: {ordering, amount_rules, bands, deadlines, attempts}
  interactions: [{trigger, priority, required_utterance, state_effect, evidence}]
  confirmation: {scope, fields, explicit_acceptance, correction_behavior}
  persistence: {actions, retries, duplicate_policy, irreversible_effects}
  finalization: {notes_policy, outcome_table, priority, terminal_tool}
  api_bindings: {seven_operation_names, input_schemas, enums, success_fields}
  unresolved: [{question, conflicting_evidence, severity}]
  coverage: [{source_rule, normalized_rule_id, workflow_node, test_ids}]
```

Her çıkarılmış değerin `evidence` alanı kaynak dosya + bölüm/satır + kısa alıntı içermeli. Final ham mail/policy/memo/code listesi olduğunda tarih ve `supersedes` ilişkisi çıkarılmalı; en son dosya adı otomatik kazansın diye varsayılmamalı. İkinci otomatik audit pass kaynaklarla IR'ı karşılaştırmalı: atlanan kural, çakışan memo, boş enum, kaynaksız sayı, eksik outcome, bilinmeyen API alanı.

İnsan yeni final kuralı eklemeyecek: builder kendi audit döngüsüyle hatalı extraction'ı düzeltecek. API binder required alanları ve enum'ları her çalışmada yeni OpenAPI'den türetecek. Kimlik sorularının iki tane/date_of_birth + phone olması veya queue kodlarının şu anki isimleri olması genel şablona gömülmeyecek.

Workflow katmanlarında:

- Konuşma modeli: niyet, tam/eksik bilgi, müşterinin son düzeltmesi ve açık kabulü anlar; kısa soruyu sorar.
- Deterministik kod: tarih, tatil, limit, miktar, counter, state ve final outcome hesaplar.
- API kapıları: doğru aşama ve doğru ürün id'si; input schema; action sonucu ve tekrar sınırı.
- Conversation prompt: kodun hazır tarih/tutar/sonraki eylem bilgisini açıklar; yeni politika icat etmez.

## Platform ayrıntıları: uyum için kritik

- `api_call` HTTP 200 envelope'ının içinde `data.ok=false` olabilir. İşlem başarısı ile transport başarısını ayır (`docs/tools-and-code.md:248-287`, `tools/openapi.json`).
- `response_mapping` `data.` ile başlar; booleans flattened variables içinde string olabilir. Kodu typed/normalized flag üretecek şekilde tut.
- Sabit config/vars için `default` kullanılır; `const` Freya'da değeri bake etmez (`tools-and-code.md:78-99`).
- Model dolduracak alanı, aynı isimli mevcut workflow variable nedeniyle node girişinde yanlışlıkla bake etme. Özellikle çoklu ürünlerde ilk ürünün amount/date/product id'si ikinci ürüne yapışmasın.
- Write tool'larında `maxRetries=0`; policy kontrollü retry ayrı yapılır. Belgeler otomatik write retry'nin duplicate yaratabileceğini söylüyor (`tools-and-code.md`, Retries and timeouts).
- Pre-hook config'i doğrular; post-hook success sonucunu işler. Envelope ve mapping davranışına göre yaz; unverified runtime özelliklerini varsayma.
- Code snippets hızlı olmalı, `vars` üzerinden okumalı, exception ve unset variable için fallback üretmeli. `{{` / `}}` snippet içinde kullanılmamalı; template işleminden etkilenebilir.
- Passthrough code/API node'larında son `always` transition gereklidir; yoksa deadlock. Agent sessiz kalırsa müşteri telefonu kapatabilir.
- `freya.save_workflow` publish eder; sadece PUT publish etmez (`README.md:98`). Yeni workflow her testte yaratılmamalı.

## Trace ve provenance planı

Her run ayrı bir klasör:

```text
runs/<utc-time>-<input-hash>/
  trace.jsonl
  input-manifest.json
  extracted-policy.json
  coverage.json
  workflow.generated.json
  workflow.exported.json
  validation.json
  tests/*.json
```

Zorunlu trace: start/end, her model çağrısının model adı ve tek satırlık amacı, Freya'da yaratılan/güncellenen workflow+agent, kendi testleri (`README.md:91`). Ek yararlı kanıt: builder sürümü/commit, brief/API hashleri, model call süreleri, repair sebepleri, workflow/export hashleri, publish durumu, toplam süre. API anahtarları/team key trace'e yazılmaz.

Ölçülen artifact ile teslim edilen export birebir eşleşmeli: export hash'i trace'te saklanmalı. Export kit API'si ile yapılmalı; yerel generated JSON'un platform kaydıyla eş olduğunu varsayma (`README.md:75`).

## Şikâyet analizi fikrinin buradaki doğru rolü

Şikâyetlerden yeni bankacılık kuralı türetmek yarışma hedefiyle çelişebilir. Örneğin genel UX için `müşteriyi derhal insana bağla` iyi görünürken mevcut brief önce bir kez yardım teklif etmeyi şart koşuyor; `ne kadar ödeyebilirsin?` doğal görünürken yasak.

Şikâyetlerden yalnız genel deneyim temalarını çıkarıp **sentetik konuşma stres testlerine** çevirmek faydalı: soruyu gereksiz tekrar, döngü, insan isteğini anlamama, bölük yanıtı kesme, müşterinin düzeltmesini kaçırma, empatisiz baskı, sessizlik, kayıt başarıyla tamamlanmadan yapılmış gibi konuşma. Bunlar policy'yi değiştirmez; policy uygulamasının dayanıklılığını ölçer.

Kit gerçek müşteri verisi getirmemeyi açıkça istiyor (`README.md:92`). Bu nedenle gerçek şikâyet metinlerini, isim/telefon/hesap/borç bilgilerini testlere veya agent promptuna taşımamak; anonim, toplu tema düzeyinde inceleyip tamamen uydurma senaryolar üretmek uygun yön. Bu notta şikâyet platformu araştırması yapılmadı; o çalışma diğer araştırma kolunun kapsamıdır.
