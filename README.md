# 🗓️ İTF Ders Programı → iPhone Takvim Senkronizasyonu

Google Sheets'teki ders programını otomatik olarak iPhone Takvim uygulamasıyla senkronize eder.

## 📱 iPhone'da Takvime Abone Olma

1. iPhone'unuzda **Safari** tarayıcısını açın
2. Şu linke gidin:

```
webcal://aliefeakyol-lab.github.io/ders-takvim/ders-programi.ics
```

3. "Takvime Abone Ol" seçeneğine tıklayın
4. **Takvim Ekle** butonuna basın

> 💡 Takvim her 6 saatte bir otomatik güncellenir. iPhone'daki güncelleme sıklığını değiştirmek için:
> **Ayarlar → Takvim → Hesaplar → Abonelik → Getir** altından ayarlayabilirsiniz.

## 🔧 Nasıl Çalışır?

```
Google Sheets (Ders Programı)
        ↓ (CSV Export)
  GitHub Actions (Her 6 saatte)
        ↓ (Python Script)
   .ics Takvim Dosyası
        ↓ (GitHub Pages)
  iPhone Takvim Aboneliği
```

1. **GitHub Actions** her 6 saatte bir çalışır
2. Google Sheets'ten en güncel veriyi çeker
3. Python scripti ile `.ics` takvim dosyası üretir
4. Değişiklik varsa otomatik commit & push yapar
5. **GitHub Pages** üzerinden `.ics` dosyasını sunar
6. iPhone takvim aboneliği otomatik güncellenir

## 📋 Kaynak Tablo

[Google Sheets Ders Programı](https://docs.google.com/spreadsheets/d/1Xwqz2bXHvH2oQ_utv_WIVzPFvLZyJEXHvwey-bVDt7A/edit?usp=sharing)

## 🛠️ Manuel Güncelleme

Acil güncelleme gerekirse GitHub'da **Actions** sekmesine gidip **"Run workflow"** butonuna tıklayabilirsiniz.

## 📁 Proje Yapısı

```
ders-takvim/
├── sheets_to_ics.py          # Ana Python scripti
├── requirements.txt           # Python bağımlılıkları
├── README.md                  # Bu dosya
├── docs/
│   └── ders-programi.ics     # Üretilen takvim dosyası
└── .github/
    └── workflows/
        └── update-calendar.yml  # GitHub Actions workflow
```
