"""Üyelik fonksiyonlarını (Low / Middle / High) çizer ve results/figures/ altına kaydeder.

Çalıştırma (src/ klasöründen):  python plot_membership.py
Girdiler ve çıktı için eşikler config.py içindeki MF_PARAMS'tan okunur.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # ekran açmadan dosyaya çiz
import matplotlib.pyplot as plt
import numpy as np

from config import MF_PARAMS
from fuzzy_system import MF

TITLES = {"ER": "ER (kalan enerji)", "DS": "DS (mesafe)",
          "BW": "BW (bant genişliği)", "OUT": "Çıktı (etki katsayısı)"}
LABELS = {"L": "Low", "M": "Middle", "H": "High"}
COLORS = {"L": "#0072B2", "M": "#E69F00", "H": "#009E73"}   # renk körlüğüne uygun

x = np.linspace(0.0, 1.0, 501)
fig, axes = plt.subplots(1, 4, figsize=(14, 3.2), sharey=True)
for ax, var in zip(axes, ["ER", "DS", "BW", "OUT"]):
    r, s, t = MF_PARAMS[var]
    for key, f in MF.items():
        ax.plot(x, f(x, r, s, t), label=LABELS[key], color=COLORS[key], lw=2)
    ax.set_title(TITLES[var])
    ax.set_xlabel("normalize değer")
    ax.grid(alpha=0.3)
axes[0].set_ylabel("üyelik derecesi")
axes[0].legend(loc="center right")
fig.tight_layout()

out = Path(__file__).resolve().parent.parent / "results" / "figures"
out.mkdir(parents=True, exist_ok=True)
fig.savefig(out / "membership_functions.png", dpi=200)
print("Kaydedildi:", out / "membership_functions.png")
