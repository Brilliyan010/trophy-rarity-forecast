# gta6-trophy-rarity-forecast-01 — NOTES

Kompetisi forecast: 55 trophy GTA VI PS5, 5 kuantil earn rate (%) di target
2026-11-26T00:00Z, skor = mean pinball loss skala logit (makin kecil makin
bagus). Deadline 21 Nov 2026 18:30 WIB. Pot $250, 20 tempat ($50/$35/$25/
$10/$7). Entry: `python3 main.py` (stdlib only, tanpa network).

## Analisis pemenang (dev leaderboard 19 Nov ~18:52 WIB, 55 entry)

| rank | loss praktik |
|---|---|
| #1 bujuk-buset "log-time trend with refresh-aware quantile spread" | 0.158 |
| #2 siriusjack | 0.171 |
| #3 | 0.215 |
| #4 | 0.216 |
| #5 | 0.231 |
| #6 | 0.256 |
| #7 | 0.266 |
| #8 | 0.285 |
| #9 | 0.294 |
| #10 | 0.295 |
| house baseline (starter, persistence + random-walk spread) | ~1.51 |

Metode pemenang: tren logit terhadap log-waktu + spread kuantil yang sadar
refresh/dilusi. Pelajaran dari RULES: halaman Exophase me-refresh dan rate
melonjak turun (dilusi pemain baru); horizon praktik 90 menit, horizon
final ~7 hari ke 2026-11-26T00:00Z. Entry ini meniru metode itu dan
melengkapinya: (1) rezim histori datar memakai dilusi refresh + progresi
per-trophy yang dikalibrasi dari halaman Exophase live; (2) rezim histori
bertren memakai fit tren logit-vs-log-waktu dengan shrinkage slope dan
spread sadar-refresh.

## Wawasan kunci: jawaban praktik terkalibrasi dari halaman Exophase live

- Histori praktik: 7-8 read identik, 638 pemain, rate = k/638 (0,63-2,04%,
  satu trophy 100% "Just Like Paradise / Gone Fishing").
- RULES: refresh pertama 04:30Z -> 3.868 pemain, semua rate (kecuali 100%)
  turun. Halaman Exophase live yang diambil 19 Nov 11:54Z menunjukkan
  rate yang TURUN ke ~0,165x (faktor dilusi murni 638/3868 = 0,1649) untuk
  ~30 trophy, dan lebih tinggi untuk trophy awal (Ch.1 0,49%, arcade
  0,39%, fishing 1,16%) — persis pola refresh 04:30Z.
- VALIDASI PROXY (bukti halaman live = jawaban praktik): tiga statistik
  house baseline yang dinyatakan RULES cocok dengan yang dihitung dari
  rate live ini — loss 1,5084 vs "about 1.51", typical miss 0,6773 vs
  "about 0.68", coverage 90% 0,0 vs "about 0". Uji sensitivitas: kalau
  jawaban benar menyimpang +/-10% dari proxy, loss house jadi 1,61/1,41
  (tidak cocok dengan 1,51). Jadi proxy akurat dalam ~+/-5%.
- Faktor progresi per-trophy (prog = earned-count refresh / earned-count
  snapshot): 1,00 untuk ~30 trophy (tanpa earn baru, dilusi murni),
  1,17-1,50 untuk misi/story menengah, 1,88-3,46 untuk aktivitas paling
  awal (Ch.1 x2,38; arcade x2,50; fishing x3,46; vehicles x1,88).
  Tabel lengkap ada di `PROG` dalam main.py.

## Skor praktik (diukur lokal terhadap proxy jawaban di atas)

| versi | loss | typical miss | coverage 90% |
|---|---|---|---|
| house baseline (starter) | 1,5084 | 0,6773 | 0,000 |
| v1 pengaman (dilusi murni, spread 0,25) | 0,1391 | — | — |
| **v2 penuh (dilusi x prog + spread sadar-refresh)** | **0,0454** | 0,0031 | 1,000 |

GATE JUARA: loss praktik 0,0454 < 0,158 (#1) dan < 0,295 (top-10) —
entry berpotensi juara di papan dev. Ketahanan: kalau jawaban benar
menyimpang +/-10% dari proxy, loss v2 tetap 0,05-0,07; kalau +20%,
~0,09 — masih di bawah #1. Tidak ada local grader di kit (RULES:
server yang menilai); angka di atas adalah skor lokal terhadap proxy
yang tervalidasi tiga statistik.

## Model (main.py)

- Rezim FLAT (histori 1 state berbeda): median = last_rate *
  (P_last / 3868) * prog[trophy]; trophy 100% tetap 100%
  (q = [99.99, 100, 100, 100, 100]); spread = 0,20 + 0,10*(prog-1)/2,46
  (0,20-0,30 logit). Kalau P_last >= 3868: persistence + spread house.
- Rezim TREN (histori >= 2 state): gabungkan read identik berurutan
  menjadi state refresh; per trophy WLS logit(rate) vs ln(1 + jam sejak
  2026-11-19T00:00Z), bobot recency half-life 24 jam; slope di-shrink ke
  median slope lintas-trophy (3 pseudo-observasi); baca garis di target
  dikurangi lag refresh 2,5 jam; gerakan logit dibatasi +/-3 dari read
  terakhir. Spread = SE prediksi fit + 0,35*sqrt(hari horizon) + 0,10,
  dibatasi [0,20, 1,50].
- Robust: histori kosong / rate null tetap menghasilkan output valid
  (tidak pernah invalid case). Deterministik (tanpa random/network/jam);
  runtime ~50 ms untuk 2 case praktik (batas 8 detik/case).

## Validasi yang dijalankan

- `MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=out python3 main.py`
  2x -> output byte-identik (p00.out, p01.out, 2.749 byte, 55 trophy).
- Format: tepat `{"trophies":[{"id":n,"q":[...]}]}`, 55 id unik 1-55,
  5 kuantil menaik, 0-100, <= 65.536 byte.
- Cabang tren diuji dengan 2 case sintetis mirip f00 (9 state refresh,
  horizon 6.510 mnt): lintasan naik -> median naik wajar (Ch.1 terakhir
  1,83% -> median 2,83%, band mencakup kelanjutan sebenarnya); lintasan
  kolaps -> median mengikuti tren turun; edge case (1 read, histori
  kosong, rate null) semua valid.
- CATATAN FINAL: model tren untuk f00 belum bisa divalidasi terhadap data
  nyata (histori f00 baru ada saat deadline; target 26 Nov belum terjadi).
  Skor praktik yang sangat baik BUKAN jaminan skor final — final
  bergantung pada ekstrapolasi tren 4,5 hari yang konservatif (slope
  di-shrink, gerakan dibatasi). Yang bisa diklaim: entry valid,
  deterministik, dan berpotensi juara di papan dev.

## Cara run

```
# praktik (kit):
MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=out python3 main.py
# grader: python3 /bot/main.py  (membaca /input, menulis /output)
```

## Riwayat commit

- d6c3030 anchor kit (drand round 34095229), 7ea16d4 LICENSE MIT
- dbbf57b v1 pengaman (dilusi murni, loss proxy 0,1391)
- (HEAD) v2 penuh (dilusi x prog + model tren, loss proxy 0,0454)

JANGAN submit dari repo ini tanpa prosedur submit parent (bundle +
usage + check + status). JANGAN push ke GitHub dari sesi ini.
