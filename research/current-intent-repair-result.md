# Güncel niyet ayrımı ve tek offline repair sonucu

11 Ekim 2026, Europe/Istanbul. Bu bir geliştirici raporu, bağımsız review değil.

Başlangıç HEAD `efcd0e9`, `origin/main` ile aynıydı. Üretim kaynağı:
[`58eed9a`](https://github.com/kaan-gunes/freya-yc-hackathon/commit/58eed9a4e23cc31d87843a9b6eb144f5ed36c46b).
Son bağımsız review işaretçisi (`e655ed7`) ve `PROJECT_CONTEXT.md` değiştirilmedi.

**Durum: hazır aday yok.** Niyet düzeltmeleri yeni adayda çalışıyor. Ama model
grafiğe yeni bir yol ekledi ve onay/kayıt kapısının yapısal kontrolü bu yüzden
adayı reddetti. Aday yayımlanmamalı. İkinci repair veya publish yapılmadı.

## Kaynakta ne değişti

| Dosya | Değişiklik |
| --- | --- |
| `builder/prompt.md` | Event tek başına karar vermiyor; yalnız bir ipucu. Kod, yalnız kopyalanmış güncel metinden ayrı bilgiler çıkarıyor: selam, soru (AI / scam / minimum / diğer), support reddi, plan reddi, plan isteği ve açık ödeme önerisi. Bu bilgiler birbirini silmiyor. `?` tek başına soru sayılmıyor; `Hello?` kaynağın isim-sorma akışında kalıyor. Pending support'ta baştaki "No/No, thanks" ve pasif "I do not want to be transferred" reddi, sorudan ve yes/question/boş event'ten önce geliyor. Ret plan/taksit nesnesine bağlıysa, hiçbir etiketle restructuring sayılmıyor. Tutar reddi + taksit isteği hâlâ plan isteği. Cevap prefix'i event'e göre değil, son rotaya göre (listen/readback/close) ekleniyor. Cevap kayıt yetkisi değil. |
| `builder/validation.py` | Yalnız iki eksik girdi eklendi. Gerçek PUB-05 cümlesi `No, I do not want to be transferred. Can you just give me a discount?` `question`, yanlış `yes` ve boş event ile deneniyor. `I do not want lower instalments.` `plan`, `question`, boş ve `no` ile deneniyor. Eski dört beklenti aynı kaldı; toplam check sayısı 207'den 214'e çıktı. |
| `tests/test_v7_conversation.py` | Doğru küçük aday iki yeni girdiyi de kabul ediyor. Eski gerçek hatanın iki mutantı (pasif reddi gölgelemek, reddedilen taksiti transfer etmek) reddediliyor. |

Tutar, tarih, tatil, zorunlu açılış ve resmî scorer değişmedi; bunlar hardcode edilmedi.

## Yerel kontroller

- `python3 -m unittest tests.test_v7_conversation tests.test_build_agent tests.test_test_agent tests.test_focused_conversation tests.test_focused_approval_retry -q`: **57/57**, **98.698 saniye**. Ekrandaki "transport read failed" satırları mock'lu testlerden geliyor; review log'unda da aynı satırlar var.
- `tests.test_v7_conversation` tek başına: **5/5**, **22.118 saniye**.
- Builder `self_check()` ve `git diff --check`: geçti.
- Değişmemiş eski aday, yeni validator ile **203/214** verdi: eski 4 hata ve 7 yeni girdinin hepsi başarısız. Yani yeni kontroller eski davranışı reddediyor. Ayrıca eski kod, yanlış `yes` etiketli iki reddi support'a transfer ediyordu.

## Tek offline repair

```bash
python3 scripts/build_agent.py build-the-builder/briefs/brief-a.md \
  --openapi build-the-builder/tools/openapi.json --slot kaan-brief-a \
  --offline --repair-build build-the-builder/out/20261011T140530260392Z \
  --budget-seconds 1800
```

- Run `build-the-builder/out/20261011T145212543699Z/`. Saat **17:52:12–17:56:23**, süre **251.09 saniye** (bütçe 1800).
- Model `gpt-6.1-sol`. Tek merge-patch çağrısı yapıldı. Değerler: `code_commit=58eed9a`, `code_dirty=false`, `offline=true`, `live_test.status=not_run`, status `incomplete`.
- Trace sırası: begin → seed → model begin/end → local validation → end. Reuse, Freya doğrulaması, kayıt veya publish olayı yok.
- Başlangıç adayı değişmedi. SHA256 `5f2691d3699c456c2dac20ccd1e980c981697b9a0d165af73da860b36705e77b`; bu, manifest'teki seed hash'i ile aynı.
- Kaynak eşleşmesi: brief/API/platform dosyaları eskisiyle birebir aynı. Yalnız izinli compiler prompt'u değişti; yeni SHA256 `4fbd2188f5fd2c83a5771adb48fc58c4a852c797fee170eac3fc07a7f351f7a0`. Manifest'teki altı kaynak güncel dosyalarla aynı.
- Yeni tam aday `candidate-attempt-1.json`, SHA256 `7a6c1c6c8b0c4798dca74da71d9fb39263f35b40380e46998e6e062ad4f607a7`.
- **Check'ler 214/214, provenance 47/47** (doğrulama 5.13 saniye). Seed'deki hiçbir üretilmiş check silinmedi veya değiştirilmedi.
- Aday yine de **geçersiz**. Üç graf hatası var:
  - `record: offer guard does not dominate readback/record`
  - `approval: confirmation readback does not dominate approval/record`
  - `record: confirmation readback does not dominate approval/record`

### Gerçek blokaj

Model yeni bir `decision → approval` geçişi ekledi (`route == "approval"`). Kendi
özetinde bunu "connected resumed confirmation to its approval guard" diye anlatıyor.
Eski adayda decision kodu readback sırasında sorulan bir sorudan sonra
`route='approval'` yazıyordu, ama grafikte bu rotaya giden bir yol yoktu. Sonraki
cevap literal tekrar listener'ına düşüyordu; bu, eski adayda gizli bir çıkmaz
yoldu. Model bu çıkmazı doğrudan approval'a bağlayarak kapattı.

Sorun şu: `decision` görüşmenin başından itibaren erişilebilir. Bu yüzden
approval ve kayıt artık offer guard ve readback'ten geçmeden de grafikte
erişilebilir oluyor. Kapı haklı olarak reddetti; bu kontrol gevşetilmedi.

Doğru en küçük düzeltme şöyle: confirmation'da bir soru cevaplandıktan sonra gelen
yeni cevap doğrudan approval'a gitmesin. Aynı teklif offer guard üzerinden tekrar
okunsun (readback), ve approval'a yalnız readback listener'ından gidilsin. Bu bir
sonraki üretim sözleşmesi maddesi olur. Bunu denemek ikinci bir model çağrısı
demek; o yüzden bu görevde yapılmadı.

## Yeni adayda niyet replay'leri (offline)

Ignored `build-the-builder/out/current-intent-repair/verify_candidate.py` adayın
kodunu değiştirmeden çalıştırıyor. **32/32** senaryo geçti:

- `Hello?`, `Hi there?`, `Good morning?` → yalnız isim sorusu; "bilgim yok" cevabı yok. Açılıştaki gerçek AI sorusu cevaplanıyor ve ardından isim sorusu geliyor.
- Minimum sorusu `question`, boş ve yanlış `no` ile → "The minimum amount is 100." Teklif yok, persuasion sayacı değişmiyor. Metin yoksa "What would you like to know?".
- Pending support: kibar ve pasif PUB-05 retleri `question`, yanlış `yes` ve boş event ile → `no_promise/hardship` kapanışı. Support tekrar teklif edilmiyor. `Yes, please connect me.` → support transferi. Hardship + gönüllü teklif → readback.
- Kaydedilmiş gerçek PUB-05 support state'i → `no_promise/hardship`.
- `I do not want lower instalments.` dört etiketle → transfer yok, sayaç değişmiyor. `I cannot pay that amount. I would like lower instalments instead.` → restructuring transferi. Kimlik öncesinde ikisi de banka aksiyonu açmıyor. `I plan to pay on Friday.` transfer etmiyor.
- AI sorusu + güncel tutar/tarih `yes`, `offer`, `question` ve boş event ile → readback'te digital-assistant cevabı var, kayıt yetkisi yok. Yalnız artık (residual) alanlar readback açmıyor.

Bunlar niyet düzeltmesinin yerel kanıtı. Adayın geçerli olduğu anlamına gelmez.

## Sınırlar

Freya dry-run, publish, chat turn, banka oturumu, simülasyon veya tekrar çalıştırma
yapılmadı. V8 taslağına dokunulmadı. **Yeni canlı skor yok**; v7'nin 4/10'u bu
değişikliği ölçmüyor. Ham aday, model çıktısı, trace ve doğrulama JSON'u ignored
`build-the-builder/out/` altında kalıyor. Anahtar veya ham konuşma commit edilmedi.

Sonraki karar review'a ait: yukarıdaki confirmation-dönüşü maddesiyle aynı son
adaydan bir offline repair daha yapılabilir. Canlı ölçüm, ancak geçerli bir aday
ve review'dan sonra gelmeli.
