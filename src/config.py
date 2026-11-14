"""Tüm simülasyon ve bulanık sistem parametreleri tek yerde.
"""

# ---------------------------------------------------------------- Ağ (Tablo 4)
N_NODES = 100            # [Makale] düğüm sayısı
AREA = 100.0             # [Makale] 100x100 m alan
RADIO_RANGE = 30.0       # [Makale] d0, yalnızca radyo menzili olarak kullanılır
SIU_POS = (50.0, 50.0)   # [VARSAYIM] SIU (sink) alanın merkezinde, enerjisi sınırsız
N_REQUESTS = 10_000      # [Makale] istek sayısı
TTL = 20                 # [VARSAYIM] bir paketin en fazla hop sayısı

# ---------------------------------------------------------------- Bant genişliği
BW_MIN = 1.0             # [VARSAYIM] Mbps, bağlantı başına U(BW_MIN, BW_MAX), simetrik, sabit
BW_MAX = 10.0

# ---------------------------------------------------------------- Enerji modeli (Denklem 16-21)
E0 = 2.0                 # [Makale] J, düğüm başına başlangıç enerjisi
PACKET_BITS = 512        # [Makale] k
E_ELEC = 50e-9           # [Makale] J/bit
EPS_FS = 100e-12         # [Makale] J/bit/m^2  (d < d0 için d^2 kolu)
EPS_MP = 100e-12         # [Makale] J/bit/m^4  (d >= d0 kolu; menzil 30 m olduğundan tetiklenmez)
P_SENSE = 0.5            # [Makale] W
P_PROC = 0.3             # [Makale] W
T_SENSE = 1e-3           # [VARSAYIM] s. Makale 1 s diyor ama bu 2-3 istekte ağı öldürür
T_PROC = 1e-3            # [VARSAYIM] s. Aynı gerekçe

# ---------------------------------------------------------------- Bulanık sistem
# Üyelik fonksiyonu eşikleri (r, s, t): makale "uzman belirledi" diyor, değerler yok.
# [VARSAYIM] Hepsi için 0.25 / 0.5 / 0.75. Duyarlılık analizi için buradan değiştirilir.
MF_PARAMS = {
    "BW":  (0.25, 0.5, 0.75),
    "DS":  (0.25, 0.5, 0.75),
    "ER":  (0.25, 0.5, 0.75),
    "OUT": (0.25, 0.5, 0.75),
}
CENTROID_POINTS = 101    # [VARSAYIM] durulaştırma için [0,1] aralığındaki nokta sayısı

# ---------------------------------------------------------------- Deney
SEEDS = list(range(30))  # [VARSAYIM] 30 tekrar, seed 0-29
