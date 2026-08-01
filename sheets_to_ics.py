#!/usr/bin/env python3
"""
Google Sheets Ders Programı → iCalendar (.ics) Dönüştürücü

Bu script, Google Sheets'teki ders programını okuyup iPhone Takvim
uygulamasıyla uyumlu .ics dosyası üretir.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar, Event

# ─── Yapılandırma ───────────────────────────────────────────────────────────

SPREADSHEET_ID = "1Xwqz2bXHvH2oQ_utv_WIVzPFvLZyJEXHvwey-bVDt7A"
CSV_EXPORT_URL = (
    f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
)
OUTPUT_DIR = Path(__file__).parent / "docs"
OUTPUT_FILE = OUTPUT_DIR / "ders-programi.ics"
TIMEZONE = ZoneInfo("Europe/Istanbul")
CALENDAR_NAME = "İTF Ders Programı"

# Filtrelenecek konu anahtar kelimeleri (büyük/küçük harf duyarsız)
EXCLUDED_KEYWORDS = [
    "SERBEST ÇALIŞMA",
]

# Türkçe ay isimleri → ay numarası
TURKISH_MONTHS = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4,
    "mayıs": 5, "haziran": 6, "temmuz": 7, "ağustos": 8,
    "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
}

# Türkçe gün isimleri → Python weekday (0=Pazartesi, 6=Pazar)
TURKISH_DAYS = {
    "pazartesi": 0, "salı": 1, "çarşamba": 2,
    "perşembe": 3, "cuma": 4, "cumartesi": 5, "pazar": 6,
}

# iCalendar RRULE gün kodları
ICAL_DAY_CODES = {
    0: "MO", 1: "TU", 2: "WE", 3: "TH", 4: "FR", 5: "SA", 6: "SU",
}


# ─── Yardımcı Fonksiyonlar ──────────────────────────────────────────────────

def fetch_csv_data() -> str:
    """Google Sheets'ten CSV verisini indirir."""
    print(f"📥 Google Sheets'ten veri indiriliyor...")
    response = requests.get(CSV_EXPORT_URL, timeout=30)
    response.raise_for_status()
    # Google Sheets UTF-8 BOM ile dönebilir
    return response.content.decode("utf-8-sig")


def parse_turkish_date(date_str: str) -> datetime | None:
    """
    Türkçe tarih stringini datetime objesine çevirir.
    Örnek: '1 Ekim 2025 Çarşamba' → datetime(2025, 10, 1)
    """
    date_str = date_str.strip()
    if not date_str:
        return None

    # "HER HAFTA" ile başlıyorsa bu bir tarih değil
    if date_str.upper().startswith("HER HAFTA"):
        return None

    # Gün adını çıkar (opsiyonel olabilir)
    # Format: "1 Ekim 2025 Çarşamba" veya "1 Ekim 2025"
    parts = date_str.split()
    if len(parts) < 3:
        return None

    try:
        day = int(parts[0])
        month_name = parts[1].lower()
        year = int(parts[2])

        month = TURKISH_MONTHS.get(month_name)
        if month is None:
            print(f"  ⚠️ Bilinmeyen ay: '{month_name}' → '{date_str}'")
            return None

        return datetime(year, month, day)
    except (ValueError, IndexError):
        print(f"  ⚠️ Tarih parse edilemedi: '{date_str}'")
        return None


def parse_time(time_str: str) -> tuple[int, int] | None:
    """
    Saat stringini (saat, dakika) tuple'ına çevirir.
    '08:30' → (8, 30)
    '16.40' → (16, 40)  (bazı satırlarda nokta kullanılmış)
    """
    time_str = time_str.strip()
    if not time_str:
        return None

    # Hem ':' hem '.' ayracını destekle
    time_str = time_str.replace(".", ":")
    parts = time_str.split(":")
    if len(parts) != 2:
        return None

    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return None


def parse_recurring_day(date_str: str) -> int | None:
    """
    'HER HAFTA PAZARTESİ' → 0 (Python weekday)
    """
    date_str = date_str.strip().upper()
    if not date_str.startswith("HER HAFTA"):
        return None

    day_name = date_str.replace("HER HAFTA", "").strip().lower()
    return TURKISH_DAYS.get(day_name)


def should_exclude(konu: str) -> bool:
    """Konu filtreleme: belirli anahtar kelimeler varsa etkinliği atla."""
    konu_upper = konu.strip().upper()
    if not konu_upper:
        return True
    return any(keyword in konu_upper for keyword in EXCLUDED_KEYWORDS)


def generate_uid(row_data: dict, index: int) -> str:
    """Her etkinlik için benzersiz UID üretir."""
    raw = f"{row_data.get('TARİH', '')}-{row_data.get('Başlama Saati', '')}-{row_data.get('KONU', '')}-{index}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest() + "@itf-ders-programi"


def find_semester_date_range(rows: list[dict]) -> tuple[datetime | None, datetime | None]:
    """Veri satırlarından dönemin başlangıç ve bitiş tarihini bulur."""
    dates = []
    for row in rows:
        dt = parse_turkish_date(row.get("TARİH", ""))
        if dt:
            dates.append(dt)

    if not dates:
        return None, None

    return min(dates), max(dates)


def find_first_weekday_in_range(
    weekday: int, start_date: datetime, end_date: datetime
) -> datetime | None:
    """Belirli bir tarih aralığında ilk belirtilen haftanın gününü bulur."""
    current = start_date
    while current <= end_date:
        if current.weekday() == weekday:
            return current
        current += timedelta(days=1)
    return None


def clean_subject(konu: str) -> tuple[str, str]:
    """
    Konu stringinden ders adı ve hoca bilgisini ayırır.
    Örnek: '1-Psikolojinin Tanımı / Doç. Dr. Ayşe ALÇALAR (Dr. Irmak Polat)'
    → ('Psikolojinin Tanımı', 'Doç. Dr. Ayşe ALÇALAR')
    """
    konu = konu.strip()
    if not konu:
        return ("", "")

    # Numaralı ders prefix'ini temizle: "1-...", "12-..."
    cleaned = re.sub(r"^\d+\s*[-–]\s*", "", konu)

    # ' / ' ile ayrılmışsa hoca bilgisini ayır
    parts = cleaned.split(" / ", 1)
    title = parts[0].strip()
    lecturer = parts[1].strip() if len(parts) > 1 else ""

    return (title, lecturer)


# ─── Ana İşlev ──────────────────────────────────────────────────────────────

def create_calendar(csv_data: str) -> Calendar:
    """CSV verisini parse edip iCalendar objesi oluşturur."""

    cal = Calendar()
    cal.add("prodid", "-//ITF Ders Programı//TR")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", CALENDAR_NAME)
    cal.add("x-wr-timezone", "Europe/Istanbul")

    reader = csv.DictReader(io.StringIO(csv_data))
    rows = list(reader)

    print(f"📊 Toplam {len(rows)} satır okundu.")

    # Dönem tarih aralığını bul (tekrarlayan etkinlikler için)
    semester_start, semester_end = find_semester_date_range(rows)
    if semester_start and semester_end:
        print(
            f"📅 Dönem aralığı: {semester_start.strftime('%d.%m.%Y')}"
            f" – {semester_end.strftime('%d.%m.%Y')}"
        )

    event_count = 0
    skipped_count = 0

    for i, row in enumerate(rows):
        donem = row.get("Dönem", "").strip()
        tarih = row.get("TARİH", "").strip()
        baslama = row.get("Başlama Saati", "").strip()
        bitis = row.get("Bitiş Saati", "").strip()
        konu = row.get("KONU", "").strip()
        dilim = row.get("DİLİM ADI / ANABİLİM DALI", "").strip()
        yer = row.get("YER", "").strip()

        # Filtreleme
        if should_exclude(konu):
            skipped_count += 1
            continue

        # Saat bilgisi yoksa atla (tatil günleri hariç)
        start_time = parse_time(baslama)
        end_time = parse_time(bitis)

        # Tekrarlayan mı yoksa tek seferlik mi?
        is_recurring = tarih.upper().startswith("HER HAFTA")
        specific_date = parse_turkish_date(tarih) if not is_recurring else None

        # Tarih veya tekrar bilgisi yoksa atla
        if not is_recurring and specific_date is None:
            skipped_count += 1
            continue

        # Ders bilgilerini temizle
        title, lecturer = clean_subject(konu)
        if not title:
            title = konu  # Temizleme başarısızsa orijinalini kullan

        # Açıklama oluştur
        description_parts = []
        if lecturer:
            description_parts.append(f"👨‍🏫 {lecturer}")
        if dilim:
            description_parts.append(f"📚 {dilim}")
        if donem:
            description_parts.append(f"📋 {donem}")
        description = "\n".join(description_parts)

        # Yer bilgisi
        location = yer if yer and "BAKINIZ" not in yer.upper() else ""
        if not location and "ONLİNE" in yer.upper():
            location = "Online"

        # ─── Etkinlik oluştur ───
        event = Event()
        event.add("uid", generate_uid(row, i))
        event.add("summary", title)
        if description:
            event.add("description", description)
        if location:
            event.add("location", location)
        event.add("dtstamp", datetime.now(tz=TIMEZONE))

        if is_recurring:
            # Tekrarlayan etkinlik
            weekday = parse_recurring_day(tarih)
            if weekday is None or semester_start is None or semester_end is None:
                skipped_count += 1
                continue

            # İlk oluşumu bul
            first_occurrence = find_first_weekday_in_range(
                weekday, semester_start, semester_end
            )
            if first_occurrence is None:
                skipped_count += 1
                continue

            if start_time and end_time:
                dtstart = first_occurrence.replace(
                    hour=start_time[0], minute=start_time[1], tzinfo=TIMEZONE
                )
                dtend = first_occurrence.replace(
                    hour=end_time[0], minute=end_time[1], tzinfo=TIMEZONE
                )
                event.add("dtstart", dtstart)
                event.add("dtend", dtend)
            else:
                # Tüm gün etkinlik
                event.add("dtstart", first_occurrence.date())
                event.add("dtend", (first_occurrence + timedelta(days=1)).date())

            # Haftalık tekrar kuralı
            until_date = semester_end.replace(
                hour=23, minute=59, second=59, tzinfo=TIMEZONE
            )
            rrule = {
                "freq": "weekly",
                "byday": ICAL_DAY_CODES[weekday],
                "until": until_date,
            }
            event.add("rrule", rrule)

        else:
            # Tek seferlik etkinlik
            if start_time and end_time:
                dtstart = specific_date.replace(
                    hour=start_time[0], minute=start_time[1], tzinfo=TIMEZONE
                )
                dtend = specific_date.replace(
                    hour=end_time[0], minute=end_time[1], tzinfo=TIMEZONE
                )
                event.add("dtstart", dtstart)
                event.add("dtend", dtend)
            else:
                # Tüm gün etkinlik (tatiller vb.)
                event.add("dtstart", specific_date.date())
                event.add("dtend", (specific_date + timedelta(days=1)).date())

        cal.add_component(event)
        event_count += 1

    print(f"✅ {event_count} etkinlik oluşturuldu, {skipped_count} satır atlandı.")
    return cal


def main():
    """Ana giriş noktası."""
    try:
        csv_data = fetch_csv_data()
    except requests.RequestException as e:
        print(f"❌ Google Sheets'ten veri indirilemedi: {e}")
        sys.exit(1)

    cal = create_calendar(csv_data)

    # Çıktı dizinini oluştur
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # .ics dosyasını yaz
    with open(OUTPUT_FILE, "wb") as f:
        f.write(cal.to_ical())

    print(f"📄 Takvim dosyası yazıldı: {OUTPUT_FILE}")
    print(f"🔗 GitHub Pages URL: https://aliefeakyol-lab.github.io/ders-takvim/ders-programi.ics")
    print(f"📱 iPhone abonelik URL: webcal://aliefeakyol-lab.github.io/ders-takvim/ders-programi.ics")


if __name__ == "__main__":
    main()
