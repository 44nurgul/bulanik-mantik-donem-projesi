"""Baseline deneyi: bulanık OSPF (makale) ve klasik OSPF, 30 seed, aynı ağlarda.

Çalıştırma (repo kökünden):  python experiments/baseline/run_baseline.py
Çıktılar: results/tables/baseline_per_seed.csv, baseline_summary.csv,
          results/figures/baseline_time_series.png
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

import config as C
from simulation import run

METHODS = {"fuzzy": "Bulanık OSPF (makale)", "ospf": "Klasik OSPF"}
METRICS = [("active_nodes", "Aktif düğüm sayısı"), ("residual_energy", "Kalan ağ enerjisi (J)"),
           ("lifetime", "Ağ ömrü (istek)"), ("delay", "Gecikme (s)"), ("pdr", "PDR (%)")]
# Makalenin Tablo 5'indeki "Önerilen yöntem" sütunu (yalnızca karşılaştırma için)
PAPER = {"active_nodes": 36, "residual_energy": 35.12, "lifetime": 6124, "delay": 11.52, "pdr": 68.54}

results = {m: [run(seed, m) for seed in C.SEEDS] for m in METHODS}

# --- Seed bazında ham sonuçlar
tables = ROOT / "results" / "tables"
tables.mkdir(parents=True, exist_ok=True)
cols = ["seed", "method"] + [k for k, _ in METRICS] + ["lifetime_censored", "avg_hops"]
with open(tables / "baseline_per_seed.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(cols)
    for m in METHODS:
        for r in results[m]:
            w.writerow([r[c] for c in cols])

# --- Özet: ortalama ± std
rows = []
for m, name in METHODS.items():
    row = {"Yöntem": name}
    for k, label in METRICS + [("avg_hops", "Ortalama hop")]:
        v = np.array([r[k] for r in results[m]], dtype=float)
        row[label] = f"{np.nanmean(v):.4g} ± {np.nanstd(v):.2g}"
    row["Ölüm görülmeyen seed"] = sum(r["lifetime_censored"] for r in results[m])
    rows.append(row)
rows.append({"Yöntem": "Makale (Tablo 5, önerilen)", **{l: str(PAPER[k]) for k, l in METRICS}})
with open(tables / "baseline_summary.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
    w.writeheader()
    w.writerows(rows)
for r in rows:
    print(r)

# --- Zaman grafiği: aktif düğüm ve kalan enerji (30 seed ortalaması)
fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
colors = {"fuzzy": "#009E73", "ospf": "#0072B2"}
for m, name in METHODS.items():
    s = np.array([[p[1:] for p in r["series"]] for r in results[m]])   # (seed, nokta, 2)
    x = [p[0] for p in results[m][0]["series"]]
    for j, (a, ylabel) in enumerate(zip(ax, ["aktif düğüm", "kalan ağ enerjisi (J)"])):
        a.plot(x, s[:, :, j].mean(axis=0), label=name, color=colors[m], lw=2)
        a.set_xlabel("istek sayısı")
        a.set_ylabel(ylabel)
        a.grid(alpha=0.3)
ax[0].legend()
fig.tight_layout()
figs = ROOT / "results" / "figures"
figs.mkdir(parents=True, exist_ok=True)
fig.savefig(figs / "baseline_time_series.png", dpi=200)
