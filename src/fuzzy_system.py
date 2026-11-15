"""Makaledeki bulanık etki katsayısı sistemi (Mamdani).

Girdiler : ER (kalan enerji), DS (mesafe), BW (bant genişliği), hepsi [0,1] normalize
Çıktı    : etki katsayısı [0,1]
Çıkarım  : kural içi VEYA = max, girdiler arası VE = çarpım (makale),
           implikasyon = min (varsayım), birleştirme = max, durulaştırma = centroid (baseline)
           veya bisector / MOM / ağırlıklı ortalama (katkı, bkz. influence)
"""
import numpy as np

from config import MF_PARAMS, CENTROID_POINTS, SUGENO_CENTERS


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


def _memberships(x, var):
    """Bir girdinin Low/Middle/High üyelik dereceleri (her değişken için bir kez hesaplanır)."""
    r, s, t = MF_PARAMS[var]
    return {lab: f(x, r, s, t) for lab, f in MF.items()}


# Durulaştırma yöntemleri (Karar 26-28). "centroid" makalenin yöntemi (baseline), diğerleri katkımız.
METHODS = ("centroid", "bisector", "mom", "wavg")


def influence(er, ds, bw, method="centroid"):
    """Aday düğümler için etki katsayısı. er, ds, bw: aynı uzunlukta [0,1] dizileri.

    method:
      "centroid": kırpılmış şeklin ağırlık merkezi (makale, baseline)
      "bisector": şeklin alanını ikiye bölen nokta
      "mom"     : şeklin tepe değerine ulaştığı noktaların ortalaması (mean of maximum)
      "wavg"    : her kuralın gücü x sabit merkezi (Low=0, Mid=0.5, High=1) toplamı / güç toplamı.
                  Bu, sıfırıncı derece Sugeno'ya denktir (kural sonuçları sabit sayılar).
    """
    er, ds, bw = (np.atleast_1d(np.asarray(a, dtype=float)) for a in (er, ds, bw))
    y = np.linspace(0.0, 1.0, CENTROID_POINTS)           # çıktı evreni
    r, s, t = MF_PARAMS["OUT"]
    mu = {"BW": _memberships(bw, "BW"), "DS": _memberships(ds, "DS"), "ER": _memberships(er, "ER")}

    def degree(labels, var):
        """Kural içi VEYA = max: listedeki kümelerin en yüksek üyeliği."""
        return max(mu[var][lab] for lab in labels) if len(labels) == 1 else np.max([mu[var][lab] for lab in labels], axis=0)

    # Her kuralın ateşleme gücü: VE = çarpım. Aynı çıktı kümesine giden kuralların
    # gücü max ile birleşir (min-kırpma + max-birleştirme sonucu bununla aynıdır).
    power = {"L": np.zeros(er.size), "M": np.zeros(er.size), "H": np.zeros(er.size)}
    rule_power = []                                      # her kuralın kendi gücü (wavg için)
    for bw_l, ds_l, er_l, out_l in RULES:
        w = degree(bw_l, "BW") * degree(ds_l, "DS") * degree(er_l, "ER")
        rule_power.append((w, out_l))
        power[out_l] = np.maximum(power[out_l], w)

    if method == "wavg":
        # Sugeno-0: her kuralın sonucu sabit bir merkez, çıktı güçlerin ağırlıklı ortalaması
        total = sum(w for w, _ in rule_power)
        weighted = sum(w * SUGENO_CENTERS[out_l] for w, out_l in rule_power)
        return np.where(total > 0, weighted / np.where(total > 0, total, 1), 0.0)

    # Çıktı kümelerini kendi güçlerinde kırp (min) ve üst üste koy (max)
    aggregated = np.zeros((er.size, y.size))
    for out_l, w in power.items():
        aggregated = np.maximum(aggregated, np.minimum(w[:, None], MF[out_l](y, r, s, t)[None, :]))

    area = aggregated.sum(axis=1)
    fired = area > 0                                     # hiçbir kural ateşlenmediyse etki 0 kabul edilir
    if method == "centroid":
        return np.where(fired, (aggregated * y).sum(axis=1) / np.where(fired, area, 1), 0.0)
    if method == "bisector":
        cum = np.cumsum(aggregated, axis=1)
        idx = (cum >= (area / 2.0)[:, None]).argmax(axis=1)   # alanın yarısına ilk ulaşılan nokta
        return np.where(fired, y[idx], 0.0)
    if method == "mom":
        at_max = aggregated >= (aggregated.max(axis=1) - 1e-12)[:, None]
        return np.where(fired, (at_max * y).sum(axis=1) / at_max.sum(axis=1), 0.0)
    raise ValueError(f"bilinmeyen durulaştırma yöntemi: {method}")
