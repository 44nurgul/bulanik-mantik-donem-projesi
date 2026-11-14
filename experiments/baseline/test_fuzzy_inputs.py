"""Bulanık sistemi farklı girdilerle test eder (yönerge 5.2).

Çalıştırma (repo kökünden):  python experiments/baseline/test_fuzzy_inputs.py
Çıktılar: results/tables/fuzzy_sample_inputs.csv, results/tables/roulette_example.csv,
          results/figures/fuzzy_surfaces.png
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from fuzzy_system import RULES, _memberships, influence

tables, figs = ROOT / "results" / "tables", ROOT / "results" / "figures"
tables.mkdir(parents=True, exist_ok=True)
figs.mkdir(parents=True, exist_ok=True)


def fired_rules(er, ds, bw, top=2):
    """En güçlü ateşlenen kuralların numaraları (kural gücü = çarpım-AND)."""
    mu = {"BW": _memberships(np.array([bw]), "BW"), "DS": _memberships(np.array([ds]), "DS"),
          "ER": _memberships(np.array([er]), "ER")}
    power = []
    for i, (b, d, e, _) in enumerate(RULES, 1):
        w = max(mu["BW"][c][0] for c in b) * max(mu["DS"][c][0] for c in d) * max(mu["ER"][c][0] for c in e)
        power.append((w, i))
    return ", ".join(f"K{i} ({w:.2f})" for w, i in sorted(power, reverse=True)[:top] if w > 0)


# --- 1) Örnek girdiler: (ad, ER, DS, BW)
cases = [
    ("En iyi aday: enerji dolu, yakın, geniş bant", 1.0, 0.0, 1.0),
    ("En kötü aday: enerji bitik, uzak, dar bant", 0.0, 1.0, 0.0),
    ("Her şey orta", 0.5, 0.5, 0.5),
    ("Enerji dolu ama bant dar", 1.0, 0.2, 0.1),
    ("Enerji bitik ama yakın ve geniş bant", 0.1, 0.1, 0.9),
    ("Çelişkili kural bölgesi: BW=Y, DS=Y, ER=O (K8 / K11)", 0.5, 1.0, 1.0),
    ("Çelişkili kural bölgesi: BW=O, DS=Y, ER=Y (K7 / K12)", 1.0, 1.0, 0.5),
    ("Geçiş bölgesi (üyelikler karışık)", 0.4, 0.6, 0.3),
]
rows = []
for name, er, ds, bw in cases:
    y = float(influence([er], [ds], [bw])[0])
    rows.append({"Senaryo": name, "ER": er, "DS": ds, "BW": bw,
                 "Etki katsayısı": round(y, 3), "Ateşlenen kurallar": fired_rules(er, ds, bw)})
    print(f"{name:58s} ER={er} DS={ds} BW={bw} -> {y:.3f}  [{rows[-1]['Ateşlenen kurallar']}]")
with open(tables / "fuzzy_sample_inputs.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

# --- 2) Rulet örneği: 3 aday komşu, puanlar ve seçilme olasılıkları
cand = [("A: enerji yüksek, yakın, geniş bant", 0.9, 0.2, 0.9),
        ("B: enerji orta, orta uzaklık, orta bant", 0.5, 0.5, 0.5),
        ("C: enerji düşük, uzak, dar bant", 0.15, 0.85, 0.2)]
score = influence([c[1] for c in cand], [c[2] for c in cand], [c[3] for c in cand])
prob = score / score.sum()
with open(tables / "roulette_example.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Aday", "ER", "DS", "BW", "Etki katsayısı", "Seçilme olasılığı"])
    for c, s, p in zip(cand, score, prob):
        w.writerow([c[0], c[1], c[2], c[3], round(float(s), 3), f"{100 * p:.1f}%"])
        print(f"{c[0]:42s} puan={s:.3f}  rulet olasılığı={100 * p:.1f}%")

# --- 3) Yüzey: ER ve DS'ye göre etki katsayısı, üç BW düzeyi için
g = np.linspace(0, 1, 101)
ER, DS = np.meshgrid(g, g)
fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
for ax, bw, title in zip(axes, [0.1, 0.5, 0.9], ["BW düşük (0.1)", "BW orta (0.5)", "BW yüksek (0.9)"]):
    Z = influence(ER.ravel(), DS.ravel(), np.full(ER.size, bw)).reshape(ER.shape)
    im = ax.imshow(Z, origin="lower", extent=[0, 1, 0, 1], vmin=0, vmax=1, cmap="viridis", aspect="auto")
    ax.set_title(title)
    ax.set_xlabel("ER (kalan enerji)")
axes[0].set_ylabel("DS (mesafe)")
fig.colorbar(im, ax=axes, label="etki katsayısı", shrink=0.9)
fig.savefig(figs / "fuzzy_surfaces.png", dpi=200, bbox_inches="tight")
