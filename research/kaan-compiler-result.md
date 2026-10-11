# Calls incelemesi ve kaynak kontrollü Kaan çekirdeği

11 Ekim 2026, Europe/Istanbul. Kullanıcı bu turda prompt yerine doğrudan geliştirme
istedi. Başlangıç `fa0d0fe`; uygulama kaynağı
[`020e4c3`](https://github.com/kaan-gunes/freya-yc-hackathon/commit/020e4c3973c003c87abf72a91af6327f970da947).
İki ayrı inceleme agentı gerçek adayı ve güvenlik yollarını kontrol etti.

**Sonuç: aynı Brief A girdilerinden, gerçek builder yolu ile yerelde geçerli bir
aday elde edildi. 232/232 kontrol, 47/47 kaynak kuralı, sıfır graf hatası.**
Yeni model çağrısı, Freya isteği, publish veya canlı test yapılmadı. Yeni canlı
skor yok; v7'nin son resmî 4/10 ve banka 7/10 sonucu tarihsel ölçüm olarak kalır.

## Claude'un teslimi ve asıl problem

[Claude sonucu](current-intent-repair-result.md) niyet ayrımını ilerletmişti:
minimum sorusu, pasif support reddi, düşük taksit reddi ve `Hello?` düzelmişti.
Yeni aday kendi ve bağımsız kontrollerin toplamında 214/214 geçti. Buna rağmen
model `decision → approval` yolu eklediği için üç yapısal güvenlik hatası vardı.
Validator bu adayı doğru biçimde durdurdu. Bu kapı gevşetilmedi.

Starter kit ve uzun prompt kuralları tanımlıyor. Ama modelin her üretimde güvenli
kontrol grafiğini yeniden yazması hataya açıktı. Model hem davranışı hem geçişi
üretiyordu; bazı gerçek konuşma biçimleri kontrollerde yoktu. Bir düzeltme başka
bir yolu bozabiliyordu. Sonraki model repair'ini tekrar istemek yerine kritik
onay dönüşünü artık kaynak kod derliyor.

Calls incelemesi, 214 kontrolün kaçırdığı ek hataları gösterdi:

- Gerçek PUB-04 girdisindeki `Am I talking to a robot?` sorusu dar AI kalıbına
  girmiyordu. Geçerli tarih readback'i üretilirken AI cevabı eksikti.
- AI sorusu belirsiz tarih veya minimum altı tutarla birlikte gelince offer guard
  önceki cevabı siliyordu. Cevap son konuşma yoluna kadar korunmalı.
- Approval aşamasında yanlış `yes` etiketi, soru, ret veya boş güncel metni onay
  sayabiliyordu. Plan reddi de bu aşamada transfer isteğiyle karışabiliyordu.
- Kontroller çok kısa onaylara dayanınca, bunları güvenli kılmak için fazla dar
  bir metin kalıbı kullanmak geçerli uzun/kibar onayları da reddedebiliyordu.
  Eski olumlu beklentiler değiştirilmeden bu regresyonlar kapatıldı.

## Arşivden ne öğrendik?

`calls.zip` içindeki 201 yararlı dosyanın envanteri ve 93 tam transcript'in olay
ve route tabloları işlendi. Sürüm dağılımı:

| Sürüm | Tam çağrı kaydı |
| --- | ---: |
| v7 | 11 |
| v6 | 59 |
| v5 | 14 |
| v4 | 2 |
| v3 | 1 |
| v2 | 2 |
| v1 | 4 |

V7'deki 11 kayıt, son tam A'nın 10 çağrısı ve önceki PUB-01 çağrısıdır; yeni bir
11 vakalık test veya puan değildir. A'da 10, B'de 3 farklı müşteri vardır.
Üç tekrar toplam 39 çağrı eder; 39 farklı vaka değildir.

V7'de iki açık `Snekbox did not respond in time` hatası, bir kapanış worker
hatası ve kontrollü bir `create_promise` 500 → başarılı retry var. İki çağrı
max duration'a ulaşıyor. Yedi çağrının konuşmasında çözülmemiş
`{{terminal_text}}` görülüyor. Bunlar eski yayımlı v7'ye aittir; yeni adayın
canlı davranışı değildir.

Tarih döngülerinde `speech_date` zaten doluydu. Agent aynı tarih cevabını tekrar
istiyordu; eksik veri tek başına açıklama değildi. Güncel Claude adayının kodu,
gerçek `the sixth of November` ve `Monday the twenty-sixth` alanlarını yerelde
kaynağın deadline/tatil kurallarıyla 23/27 Ekim readback'ine çeviriyor. Yeni
compiler bu iş kurallarını yeniden yazmıyor.

Gecikme ayrı bir sorundur. V7'de gözlenen 151 `code_exec` denemesinin medyanı
0,5 saniye; 91 kullanıcı → sonraki asistan konuşması aralığının medyanı
17,5 saniye. Bir örnekte event 6,5 saniyede, text/identity alanları 23,6 saniyede,
konuşma 24,7 saniyede geliyor. Extraction ve bekleme bu örneklerde önemli pay
tutuyor. Bu gözlem bütün gecikmenin kesin kök nedeni veya yeni compiler'ın hız
ölçümü değildir. V6'nın 2,6 saniyelik medyanı farklı çağrılar ve kısa hata
döngüleri içerdiğinden kontrollü karşılaştırma değildir.

Zip SHA256: `cc6c5b983f22c49dec1679e350ce141c3dbdaf3d67cb74ac18f185709b597c90`.
Ham transcript, ses, kişisel veri ve çalışma çıktıları Git'e eklenmedi.

## Kaynakta uygulanan mimari

`builder/compiler.py`, modelin tam adayını kopyalayıp kaynak kontrollü Kaan
kapılarını portable workflow'un içine yerleştiriyor. Girdi adayı değişmiyor.
Derlenmiş çıktı ikinci kez derlenirse aynı kalıyor.

1. **Onay dönüşü:** Confirmation sırasında bir soru cevaplandıktan sonra gelen
   yeni cevap approval'a doğrudan gidemez. Güncel teklif doğrulanır, yeniden
   okunur ve ancak bu readback'e verilen yeni açık onay kayıt yetkisi açar.
   Yeni tutar/tarih korunur; eski yetki, fingerprint ve kayıt sonucu temizlenir.
   Açık ret, kaynağın mevcut ret/sayaç yoluna gider.
2. **Güncel onay:** Modelin `yes` etiketi tek başına yeterli değildir. Boş metin,
   soru, ret, geçmiş onay, belirsizlik ve koşullu/kısmi ifadeler yetki açmaz.
   Açık uzun/kibar onaylar desteklenir. Tanınmayan biçim tekrar açıklama ister.
   Tutar/tarih eşitliğini ve gerçek request'i mevcut kapılar kontrol eder.
3. **Son konuşma:** AI/scam cevabı verilen policy'den alınır. Eski adaylar için
   generated decision içindeki tek açık kaynak cümlesi kullanılabilir.
   Cevap gerçek readback, açıklama veya kapanış metninde korunur. Agentla ilgili
   soru kalıbı, `robot vacuum` gibi başka nesnelerden ayrılır.
4. **Üretim:** Normal generation ve model repair sonucu publish öncesinde bu
   derleyiciden geçer. `--compile-build` aynı girdili eski adayı bir kez offline
   derler; model çağırmaz. Resume derlemez ve girdilerle birlikte kaydedilmiş
   compiler hash'ini de denetler. Açık recompile/repair değişen compiler'a izin
   verir; brief/API/platform eşleşmesi ve slot denetimi korunur.

Readback listener ve güvenli record-result retry dışında approval'a giren
korumasız yollar reddedilir. Derleyici yalnız bilinen exact-route handoff'u
yeniden bağlar; rastgele banka aksiyonu yolu icat etmez. Approval/offer/record
graf kapıları, validation ve kaynak provenance hâlâ son kabul sınırıdır.

Bu, özgün mimaride Kaan'ın kritik kontrol kısmının kaynak kodda uygulanmasıdır.
Bütün politika derleyicisi tamamlanmış değildir. Kimlik, takvim, tutar ve iş
istisnalarının önemli kısmı hâlâ girdiden üretilen kodda ve mevcut validator'da.
Yeni banka tutarı, tarih, tatil veya outcome hardcode edilmedi. Ayrı LLM şefi,
history kırpma ve yeni servis eklenmedi; çalışma anında yerel bilgisayar gerekmez.

## Gerçek builder çalıştırması

```bash
python3 scripts/build_agent.py build-the-builder/briefs/brief-a.md \
  --openapi build-the-builder/tools/openapi.json --slot kaan-brief-a \
  --offline --compile-build build-the-builder/out/20261011T145212543699Z \
  --budget-seconds 1800
```

- Run: `build-the-builder/out/20261011T154908350918Z/`, saat
  **18:49:08–18:49:32**, **24,44 saniye**.
- `status=completed_local`, `code_commit=020e4c3`, `code_dirty=false`.
- `generation_attempts=[]`; bir `compilation_attempts` kaydı: valid true,
  errors boş. `offline=true`, `live_test.status=not_run`.
- Trace: begin → candidate_seeded_for_compilation → workflow_compiled →
  local_validation → end. Model, Freya validation/publish veya simulation olayı yok.
- **232/232**, provenance **47/47**, `valid=true`, `ok=true`, errors boş.
- Claude'un tam seed SHA256'ı değişmedi:
  `7a6c1c6c8b0c4798dca74da71d9fb39263f35b40380e46998e6e062ad4f607a7`.
- Yeni tam aday SHA256:
  `ab8416a9254ca267c21673e670445e692d91901c7f98d05b54c2600d8a14a882`.
- Compiler SHA256:
  `fe8bb43a1b624b694c622b1b86870d63354316975ddf865ad6ebfcfc55f5ace8`
  (283 satır). Gerçek manifest kaynak/hash eşleşmesi ve `resume_candidate`
  aynı tam adayı model çağırmadan geri veriyor.
- Eski generated checks aynen korunuyor. Ek 18 bağımsız kontrol kaynak
  validator'dan geliyor. Daha önce bunlardan ikisi eski 214 kontrolü geçen
  adayda AI cevabının kaybolduğunu bağımsız olarak göstermişti.

## Kontroller ve sınırlar

- Runner, compiler-intent, confirmation-return ve compile-build testleri:
  **36/36**, **1,242 saniye**. Mock'lu testlerde yazan publish/test satırları
  gerçek platform işlemi değildir.
- Mevcut focused approval/retry testleri: **11/11**, **112,618 saniye**.
- Önceki v7 conversation testleri bu validator eklemesinden sonra **5/5**
  geçti; beklentileri değiştirilmedi. `self_check()` ve `git diff --check` geçti.
- İki ayrı inceleme gerçek güncel adayı **232/232** doğruladı. Idempotence,
  seed/check değişmezliği, yanlış onay ve güvenli 500 retry kontrol edildi.
- Gerçek PUB-04 state replay'i artık AI cevabını deadline readback'iyle birlikte
  söylüyor; kayıt yetkisi boş kalıyor. Gerçek arşiv replay'leri ve mutant
  kanıtları ignored `build-the-builder/out/kaan-compiler-review/` altında.

Yeni aday Freya dry-run/readback/export veya canlı çağrıyla doğrulanmadı. Eski
v7'nin 4/10'u bu kodu ölçmüyor. Platform template çözümü, extraction bekleme,
Snekbox timeout, canlı skor ve A+B/genel yeni brief güvenilirliği açık kalıyor.
Bu turda kullanıcıya yeni geliştirme promptu hazırlanmadı; kod geliştirildi.
