# Freya YC Hackathon

Freya “Build the Builder” hackathonu için ortak çalışma klasörü. Starter kit v3, araştırma notları ve test araçları bulunur. Kendi builder'ımız henüz geliştirilmedi.

**Amaç:** Banka talimatlarını ve araç API dosyasını okuyup, Freya üzerinde kurallara uygun bir telefon agentı oluşturan builder geliştirmek.

```text
Banka talimatları + OpenAPI → Builder → Freya'da telefon agentı → Test → Hata raporu
```

## Önce bunları okuyun

1. [Starter kit README](build-the-builder/README.md): resmî başlangıç ve yarışma kuralları.
2. [Freya workspace'ini kullanma](research/workspace-kullanimi.md): ortak çalışmayı basitçe anlatır.
3. [Araştırma özeti](research/hackathon-arastirmasi.md): görev, puanlama ve geliştirme önerileri.
4. [İlk test sonucu](research/ilk-test-sonucu.md): altyapı çalıştı; hazır agent PUB-01'i SMS cümlesi eksikliği nedeniyle geçemedi.
5. [Test akışı](research/test-akisi.md): test komutları ve hata bildirim biçimi.

## Klasörler

| Klasör | İçerik |
|---|---|
| `build-the-builder/` | Resmî starter kit v3; briefler, örnek agent/builder, API istemcisi ve test koşucusu |
| `scripts/` | Resmî testleri çalıştırıp hata, skor ve konuşma kayıtlarını saklayan yardımcı komutlar |
| `research/` | Teknik incelemeler, sentetik test fikirleri ve hata raporları |

## Kurulum

Python 3.10 veya yenisi gerekir. Test yardımcısı yalnız standart kütüphaneyi kullanır. Örnek Claude builder'ın ek kurulumunu starter kit README'si açıklar.

```bash
git clone https://github.com/kaan-gunes/freya-yc-hackathon.git
cd freya-yc-hackathon
cp build-the-builder/env.example build-the-builder/env.sh
```

`build-the-builder/env.sh` dosyasına kendi Freya API anahtarınızı ve ekibin ortak banka test anahtarını yazın. **Banka takım anahtarını herkes aynı kullanmalı; en az 16 karakter gerekir.** Kaan'ın mevcut takım anahtarı Git'te bulunmaz; ekip içinde özel olarak paylaşılır. Her bilgisayar kendi `env.sh` dosyasını oluşturur.

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
