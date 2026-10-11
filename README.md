# Freya YC Hackathon

Freya “Build the Builder” hackathonu için ortak çalışma klasörü. Starter kit v3, araştırma notları, test araçları ve [ilk builder](builder/README.md) bulunur.

**Amaç:** Banka talimatlarını ve araç API dosyasını okuyup, Freya üzerinde kurallara uygun bir telefon agentı oluşturan builder geliştirmek.

```text
Banka talimatları + OpenAPI → Builder → Freya'da telefon agentı → Test → Hata raporu
```

## Önce bunları okuyun

**Yeni chat veya review için:** [Proje bağlamı ve devir notu](PROJECT_CONTEXT.md), ana fikri, alınan kararları ve son incelenen durumu bir araya getirir.

1. [Starter kit README](build-the-builder/README.md): resmî başlangıç ve yarışma kuralları.
2. [Freya workspace'ini kullanma](research/workspace-kullanimi.md): ortak çalışmayı basitçe anlatır.
3. [Araştırma özeti](research/hackathon-arastirmasi.md): görev, puanlama ve geliştirme önerileri.
4. [İlk test sonucu](research/ilk-test-sonucu.md): altyapı çalıştı; hazır agent PUB-01'i SMS cümlesi eksikliği nedeniyle geçemedi.
5. [Test akışı](research/test-akisi.md): test komutları ve hata bildirim biçimi.
6. [İlk geliştirme promptu](DEVELOPMENT_PROMPT.md): kodlama agentına verilecek mimari, geliştirme sırası ve ilk sürüm beklentileri.
7. [İlk builder incelemesi](research/builder-review-9046149.md) ve [ikinci geliştirme promptu](NEXT_DEVELOPMENT_PROMPT.md): canlı konuşma bulguları, doğrulama açıkları ve sıradaki düzeltmeler.
8. [Mevcut işten sonraki prompt](AFTER_CURRENT_TASK_PROMPT.md): önce son sonucu kontrol ederek A kapsamı, A+B çoklu ürün ve küçük genelleme kontrollerine ilerler.
9. [İkinci builder incelemesi](research/builder-review-6d324cd.md): v6'nın ölçülen sınırları, yeni onay/API/genelleme hataları ve güncel geliştirme önceliği.
10. [Review sonrası tek tur düzeltme promptu](FOCUSED_FIX_PROMPT.md): kodu düzelt, gerekli yerel kontrollerden sonra hemen review'a teslim et; üretim ve canlı test sonraki ayrı aşama.
11. [Focused düzeltme incelemesi](research/builder-review-484e6b2.md): 48 seçilmiş yerel test geçti; memo önceliği ve business-failure retry için kalan iki validator açığı. Henüz yeni canlı agent üretilmedi.
12. [Sıradaki düzeltme ve canlı doğrulama promptu](NEXT_LIVE_VALIDATION_PROMPT.md): iki validator açığını kapat, bir builder çalıştırması ve aynı sürümde tek tam A testiyle teslim et.

## Klasörler

| Klasör | İçerik |
|---|---|
| `build-the-builder/` | Resmî starter kit v3; briefler, örnek agent/builder, API istemcisi ve test koşucusu |
| `scripts/` | Resmî testleri çalıştırıp hata, skor ve konuşma kayıtlarını saklayan yardımcı komutlar |
| `builder/` | Girdi dosyalarından politika ve workflow üreten ilk builder; yerel kontroller ve çalıştırma rehberi |
| `research/` | Teknik incelemeler, sentetik test fikirleri ve hata raporları |

## Kurulum

Python 3.10 veya yenisi gerekir. Test yardımcısı yalnız standart kütüphaneyi kullanır. Örnek Claude builder'ın ek kurulumunu starter kit README'si açıklar.

```bash
git clone https://github.com/kaan-gunes/freya-yc-hackathon.git
cd freya-yc-hackathon
cp build-the-builder/env.example build-the-builder/env.sh
```

`build-the-builder/env.sh` dosyasına ekibin Freya API anahtarını ve ortak banka test anahtarını yazın. **Yarışma kuralı ekip başına tek Freya anahtarıdır. Banka takım anahtarını da herkes aynı kullanmalı; en az 16 karakter gerekir.** Anahtarlar Git'te bulunmaz; ekip içinde özel olarak paylaşılır. Her bilgisayar kendi yerel `env.sh` dosyasını oluşturur.

Freya anahtarı test edeceğiniz agentın bulunduğu workspace'e erişmeli. Başka workspace'teki agent id bu kurulumun yerine geçmez.

## İlk test

Agent id, Freya'nın agentı tanımak için verdiği kimliktir. Şu anda Kaan'ın workspace'inde test edilen hazır örnek:

```bash
bash scripts/test-agent.sh 3f592c60-c10e-4a5b-966c-6bc64825f658 --only PUB-01
```

Bu id yalnız ilgili workspace'e erişiminiz varsa kullanılabilir. Kendi agentınızı test ederken onun id'sini yazın:

```bash
# Brief A'nın 10 müşterisi
bash scripts/test-agent.sh AGENT_ID --brief A

# Brief B'nin 3 müşterisi
bash scripts/test-agent.sh AGENT_ID --brief B

# Bir müşteriyi üç kez test et
bash scripts/test-agent.sh AGENT_ID --only PUB-01 --reps 3
```

Her koşu `build-the-builder/results/` altında ayrı klasör üretir. `summary.json` genel durumu, `official-results.json` resmî puanı, `calls/` konuşma ve araç kayıtlarını tutar. `0` tüm seçilen vakalar geçti, `1` tamamlanmış testte başarısız vaka var, `2` çalışma tamamlanamadı demektir. Altyapı arızası sıfır puan sayılmaz.

**Aynı workspace'te aynı anda bir simülasyon çalışır.** Testten önce ekip içinde haberleşin; test sırasında agentı güncellemeyin. Değişikliklerin kullanılması için sürüm yayımlanmalı; `freya.save_workflow` bu işlemi yapar.

API anahtarları, çalışma sonuçları ve yerel agent/persona önbellekleri Git dışında tutulur. Paylaşmak istediğiniz test bulgularını `research/` içine okunabilir bir hata raporu olarak ekleyin. Builder'ın her çalışmasının trace kaydını ayrıca saklayın; final tesliminde gerekir.
