# İlk tamamlanan resmî test

10 Ekim 2026, 18:57–19:01 İstanbul. Starter kit v3'ün örnek agentı test edildi; henüz sizin builder'ınızın çıktısı değil.

**Test altyapısı çalıştı. PUB-01 sonucu 0/1: ödeme sözü doğru kaydedildi, zorunlu SMS cümlesi söylenmedi.**

| Alan | Değer |
|---|---|
| Agent | `3f592c60-c10e-4a5b-966c-6bc64825f658` |
| Workflow | `13c6ddbf-1c73-4ce0-914f-814045139dab` |
| Test edilen sürüm | 2; konuşma kaydındaki `entityVersionNumber` ile doğrulandı |
| Model | `experimental-5` |
| Vaka | PUB-01, Brief A, Happy path |
| Stil / tekrar | Varsayılan / 1 |
| Simülasyon | `052eab75-df9b-44ef-91d6-e33db13e8f5d` |
| Konuşma | `3c6fd25e-4598-448b-98e2-2eba76c9df5d` |
| Süre | Test 218 saniye; en yavaş agent turu 2,8 saniye |

## Başarılı çalışan işlemler

Yeni practice session açıldı. Agent sırasıyla doğum tarihi ve telefon son dört hanesini `verify_identity` ile doğruladı, ardından `get_account` çağırdı. Müşterinin açık onayından sonra `p1` için 420 tutarında, 2026-10-14 tarihli söz bir kez kaydedildi. `create_promise` yanıtı `ok: true`; `close_call` yanıtı da `ok: true` ve outcome `promise`.

Resmî scorer banka kayıtlarında uyumsuzluk bildirmedi. Konuşma değerlendiricisi SMS cümlesinin eksikliği nedeniyle vakayı başarısız saydı. API/simülasyon arızası nedeniyle yarıda kalan önceki denemelerden farklı olarak bu, tamamlanmış ve ölçülmüş bir agent sonucudur.

## Geliştiriciye ilk hata bildirimi

**Beklenen:** Brief A kural 38 uyarınca, `create_promise` başarılı olduktan sonra: “You will receive a text message confirming this promise.”

**Gerçek:** Agent son mesajında “Thank you. Your promise has been recorded. Have a good day.” dedi. SMS bildirimi yok.

**Değişiklik hedefi:** Builder'ın ürettiği kayıt sonrası başarı akışı, araç yanıtında `data.ok == true` olduğunda kayıt teyidi ve zorunlu SMS cümlesini söylemeli; ardından teşekkür/kapanış gelmeli. Kayıt başarısızlığında SMS veya başarı teyidi söylenmemeli. `Have a good day.` örnekte otomatik kapanışı tetiklediğinden zorunlu cümle bundan önce tamamlanmalı. Yeni sürüm yayımlanıp aynı vaka tekrar çalıştırılmalı.

Bu hata bir koşuda gözlendi; tekrarlanabilirliği henüz ölçülmedi. Final için elle workflow düzeltmek yerine düzeltmeyi builder'ın üretim mantığına uygulayın.

## Konuşmayı okuyunca ayrıca görülen eksikler

Bunlar bu koşunun resmî başarısızlık gerekçeleri değil; Brief A ile doğrudan karşılaştırmadan çıkan geliştirme maddeleridir:

- Kural 1: İlk cümle dijital asistanı ve bankayı söylüyor, görüşmenin kaydedildiğini söylemiyor.
- Kural 28: “Can you make this payment today?” yerine “When can you pay this amount?” diye soruyor.
- Kural 34: Onay cümlesinde tutar ve tarih var, ürün tekrar okunmuyor.

## Kayıtlar ve tekrar komutu

Ham kayıtlar yalnız testi çalıştıran bilgisayarda `build-the-builder/results/20261010T155757484043Z-3f592c60/` altında bulunur; Git dışında tutulur. `official-results.json` resmî sonuç, `summary.json` çalışma özeti ve `calls/3c6fd25e-4598-448b-98e2-2eba76c9df5d.json` konuşma/araç kaydıdır. Geliştirme için gereken somut bulgular bu raporda yer alır.

Proje kökünden, yayımlanan yeni agent ile:

```bash
bash scripts/test-agent.sh AGENT_ID --only PUB-01
```

Bu tek vaka düzeldikten sonra Brief A'nın 10 vakasını çalıştırıp kapsamı genişletin. Tek bir yeşil koşu, kararlılık kanıtı değildir.
