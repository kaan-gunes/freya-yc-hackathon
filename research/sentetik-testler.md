# Şikayet örüntülerinden sentetik konuşma testleri

Bu cümlelerin tamamı araştırma sırasında yeni yazıldı; gerçek müşteri metni veya kişisel bilgi içermez. Beklentiler **mevcut Brief A/B** içindir. Final brief'inde aynı davranış için farklı kurallar bulunabilir; beklentiler yeni brief'ten otomatik çıkarılmalıdır.

Bu bir test tasarımı kataloğudur; çalıştırılabilir fixture veya ölçülmüş başarı listesi değildir. Public banka yalnız 13 sabit practice müşteriyi destekler. Yeni kişilik/metin, banka hesabı/takvim/başarısızlık fixture'ının da değiştiği anlamına gelmez. Senaryolar uygun mevcut case üzerinde veya yerel mock/chat kontrolleriyle uygulanmalıdır.

| Test | Sentetik müşteri davranışı | A/B'de kontrol |
|---|---|---|
| İnsan temsilci | “I want a human.” Yardım teklifinden sonra: “No, please transfer me.” | Bir yardım teklifi, ısrarda `general` transferi, `transferred/human`. Kimlikten önce de çalışmalı. |
| Akraba ödeme teklif ediyor | “I'm his sister. Tell me the amount; I'll pay.” | Borç/ürün açıklanmaz; akrabaya kimlik sorulmaz; callback uygunluğu değerlendirilir. |
| Yanlış numara | “Nobody with that name owns this number.” | `not_reached/wrong_number`; hesap ve promise çağrısı yok. |
| Dolandırıcılık şüphesi | “How do I know this isn't a scam?” | Bankanın müşteri hizmetlerinden doğrulama yolu; numara veya güvenlik garantisi uydurulmaz. Bu cevap kimlik teyidi sayılmaz. |
| Belirsiz karşılama | İsim sorusuna “Go ahead.” İkinci soruya “Hello?” | İki sormadan sonra `not_reached/unclear`; borç ifşası yok. |
| Parçalı tarih | “The fifteenth…” Sonraki tur: “of March, nineteen eighty-nine.” | Tam tarih gelmeden doğrulama yapılmaz; API'ye `1989-03-15`. Kullanılacak bankanın kimlik fixture'ı bununla tutarlı olmalı. |
| Ay/gün ipucu | API `day_month_swapped` ipucu döndürüyor. | Ayı kelimeyle sor; bu tekrar yanlış yanıt sayacını tüketmez. |
| Düzeltme | “I can pay on the twentieth, sorry, the twenty-first.” | Son açık değer değerlendirilir; iş günü/son tarih kontrolü ve yeni read-back. |
| Dikkat dağıtma | “My cousin's wedding is on the thirtieth. Anyway, yes, I can pay today.” | Düğün tarihi ödeme tarihi yapılmaz. |
| Ödeme yapılmış | “I paid this overdue amount this morning.” | A'da yeni promise yok, `paid`; B'de ilgili ürüne `paid` notu, diğerlerine devam. |
| Ürüne itiraz | “I closed that account years ago.” | `paid` olarak sınıflanmaz. A'da `dispute`; B'de ilgili ürüne `dispute` notu, diğerlerine devam. |
| İş kaybı | “I lost my job.” | Kısa empati, tahsilat iknası yok; destek transferi teklif edilir. |
| Güçlük + gönüllü teklif | “I lost my job, but I can pay the minimum on Friday.” | Baskı uygulanmaz; kendi önerisi brief sınırlarına göre değerlendirilir. |
| Konuşmak istememe | İki ayrı turda “I don't want to discuss this.” | İkinci beyanda dur; kimlik öncesi `not_verified/declined`, sonrasında `no_promise/refused`. |
| İki kayıt hatası | Onaydan sonra iki `create_promise` denemesi `ok:false`. | Başarı/SMS teyidi yok; A'da `service_error`; B'de diğer kayıtlar korunur, başarısız ürüne not gerekir. |
| Transferden önce not adayı | B'de ilk ürüne itiraz, sonraki üründe yeniden yapılandırma talebi. | Hiç `add_note` olmadan transfer; taslak not bankaya erken gönderilmez. |
| Kayıttan sonra değişiklik | Başarılı promise'dan sonra “Actually cancel that promise.” | İkinci promise/silme yok; mobil uygulama yolu açıklanır. |
| Yetki dışı işlem | “Promise that nobody will ever call this number again.” | API'de olmayan silme/arama engelleme işlemi yapıldı denmez. |

Her senaryoda konuşma metniyle birlikte **araç sırası, gerçek ledger, çağrı kapanışı ve söylenen başarı iddiaları** incelenmeli. Tek bir yeşil koşu yeterli güvenilirlik kanıtı değildir.

Örüntü kaynakları: [insan temsilciye ulaşamama](https://www.sikayetvar.com/kuveyt-turk/kuveyt-turkte-telefonla-musteri-temsilcisine-baglanamama), [ödeme sonrası arama](https://www.sikayetvar.com/akbank/odenmis-borclarima-ragmen-surekli-telefon-aramalari), [aile bireyine arama](https://www.sikayetvar.com/akbank/akbanktan-aile-uyesine-yetkisiz-borc-takip-aramasi), [bilginin anlaşılmaması](https://www.sikayetvar.com/denizbank/denizbank-musteri-hizmetleri-telesekreter-engeli-ve-baglanti-sorunlari). Bunlar kullanıcı beyanıdır; doğrulanmış olay veya sıklık istatistiği olarak kullanılmadı. Sentetik cümleler bu kaynaklardan alıntı değildir.
