"""Makaledeki bulanık etki katsayısı sistemi (Mamdani).

Girdiler : ER (kalan enerji), DS (mesafe), BW (bant genişliği), hepsi [0,1] normalize
Çıktı    : etki katsayısı [0,1]
Çıkarım  : kural içi VEYA = max, girdiler arası VE = çarpım (makale),
           implikasyon = min (varsayım), birleştirme = max, durulaştırma = centroid
"""
import numpy as np

from config import MF_PARAMS, CENTROID_POINTS


# ------------------------------------------------------------ Üyelik fonksiyonları
# Makale Denklem 13-15. x numpy dizisi olabilir.
def mu_low(x, r, s, t):
    """x<r ise 1, r..s arasında düşer, x>=s ise 0 (t kullanılmaz)."""
    return np.clip((s - x) / (s - r), 0.0, 1.0)


def mu_mid(x, r, s, t):
    """r'de 0, s'de 1, t'de 0 olan üçgen."""
    return np.clip(np.minimum((x - r) / (s - r), (t - x) / (t - s)), 0.0, 1.0)


def mu_high(x, r, s, t):
    """x<s ise 0, s..t arasında yükselir, x>=t ise 1 (r kullanılmaz)."""
    return np.clip((x - s) / (t - s), 0.0, 1.0)


MF = {"L": mu_low, "M": mu_mid, "H": mu_high}

# ------------------------------------------------------------ Kural tabanı (Tablo 3)
# (BW kümeleri, DS kümeleri, ER kümeleri, çıktı kümesi). Çoklu küme = VEYA (max).
RULES = [
    ("LM",  "L",  "L",  "L"),   # 1
    ("H",   "L",  "L",  "M"),   # 2
    ("LMH", "HM", "L",  "L"),   # 3
    ("L",   "L",  "MH", "M"),   # 4
    ("MH",  "L",  "M",  "H"),   # 5
    ("LM",  "M",  "M",  "M"),   # 6
    ("LM",  "H",  "MH", "L"),   # 7
    ("H",   "H",  "M",  "M"),   # 8
    ("MH",  "L",  "H",  "H"),   # 9
    ("LM",  "M",  "H",  "M"),   # 10
    ("H",   "MH", "HM", "H"),   # 11
    ("M",   "H",  "H",  "M"),   # 12
]


def _degree(labels, x, var):
    """Bir girdinin 'labels' içindeki kümelerden en yüksek üyeliği (VEYA = max)."""
    r, s, t = MF_PARAMS[var]
    return np.max([MF[lab](x, r, s, t) for lab in labels], axis=0)


def influence(er, ds, bw):
    """Aday düğümler için etki katsayısı. er, ds, bw: aynı uzunlukta [0,1] dizileri."""
    er, ds, bw = (np.atleast_1d(np.asarray(a, dtype=float)) for a in (er, ds, bw))
    y = np.linspace(0.0, 1.0, CENTROID_POINTS)           # çıktı evreni
    r, s, t = MF_PARAMS["OUT"]
    out_mf = {k: f(y, r, s, t) for k, f in MF.items()}   # çıktı kümeleri (101,)

    aggregated = np.zeros((er.size, y.size))
    for bw_l, ds_l, er_l, out_l in RULES:
        # VE operatörü = çarpım
        w = _degree(bw_l, bw, "BW") * _degree(ds_l, ds, "DS") * _degree(er_l, er, "ER")
        # implikasyon = min (kırpma), birleştirme = max
        aggregated = np.maximum(aggregated, np.minimum(w[:, None], out_mf[out_l][None, :]))

    area = aggregated.sum(axis=1)
    # Centroid. Hiçbir kural ateşlenmediyse (kural tabanında boşluk) etki 0 kabul edilir.
    return np.where(area > 0, (aggregated * y).sum(axis=1) / np.where(area > 0, area, 1), 0.0)
