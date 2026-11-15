"""Yan analiz: üyelik fonksiyonu eşikleri (r, s, t) duyarlılığı (Karar 29-30).

İki grup ayrı ayrı denenir: girdi eşikleri (ER, DS, BW birlikte) ve çıktı (OUT) eşikleri.
Her yapılandırma centroid (baseline) ve ağırlıklı ortalama ile, aynı 30 seed'de koşulur.

Çalıştırma (repo kökünden):  python experiments/proposed/run_sensitivity.py [--seeds 30]
Çıktılar: results/tables/sensitivity_per_seed.csv, sensitivity_summary.csv,
          results/figures/sensitivity.png
"""
import argparse
import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import config as C
from simulation import run

BASE = (0.25, 0.5, 0.75)
# ad: (girdi eşikleri, çıktı eşikleri)
CONFIGS = {
    "baseline":      (BASE, BASE),
    "girdi dar":     ((0.35, 0.5, 0.65), BASE),
    "girdi geniş":   ((0.1, 0.5, 0.9), BASE),
    "girdi aşağı":   ((0.2, 0.4, 0.6), BASE),
    "girdi yukarı":  ((0.4, 0.6, 0.8), BASE),
    "çıktı dar":     (BASE, (0.4, 0.5, 0.6)),
    "çıktı geniş":   (BASE, (0.05, 0.5, 0.95)),
}
DEFUZZ = {"centroid": "Centroid (baseline)", "wavg": "Ağırlıklı ort. (Sugeno-0)"}
COLORS = {"centroid": "#0072B2", "wavg": "#009E73"}
METRICS = [("lifetime", "Ağ ömrü (istek)", 1, True),
           ("residual_energy", "Kalan ağ enerjisi (J)", 1, True),
           ("avg_hops", "Ortalama hop sayısı", 1, False),
           ("pdr", "PDR (%)", 1, True)]


def job(args):
    cfg, defuzz, seed = args
    inp, out = CONFIGS[cfg]
    for var in ("ER", "DS", "BW"):           # MF_PARAMS sözlüğü yerinde değiştirilir (fuzzy_system aynı nesneyi okur)
        C.MF_PARAMS[var] = inp
    C.MF_PARAMS["OUT"] = out
    r = run(seed, "fuzzy", defuzz)
    return {k: v for k, v in r.items() if k not in ("series", "score_hist")}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=len(C.SEEDS))
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()
    seeds = C.SEEDS[:args.seeds]

    jobs = [(c, d, s) for c in CONFIGS for d in DEFUZZ for s in seeds]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        out = list(ex.map(job, jobs, chunksize=1))
    print(f"{len(jobs)} koşu tamamlandı, {time.time() - t0:.0f} s")
    res = {}
    for (c, d, s), r in zip(jobs, out):
        res.setdefault((c, d), []).append(r)

    tables, figs = ROOT / "results" / "tables", ROOT / "results" / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    def arr(c, d, key):
        return np.array([r[key] for r in res[(c, d)]], dtype=float)

    cols = ["seed", "defuzz", "active_nodes", "residual_energy", "lifetime", "lifetime_censored",
            "delay", "pdr", "avg_hops", "score_min", "score_max", "zero_score_frac", "all_zero_events"]
    with open(tables / "sensitivity_per_seed.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["config"] + cols)
        for (c, d), rs in res.items():
            for r in rs:
                w.writerow([c] + [r[k] for k in cols])

    rows = []
    for c in CONFIGS:
        for d in DEFUZZ:
            row = {"Yapılandırma": c, "Girdi (r,s,t)": CONFIGS[c][0], "Çıktı (r,s,t)": CONFIGS[c][1],
                   "Yöntem": DEFUZZ[d]}
            for key, label, mult, _ in METRICS:
                v = arr(c, d, key) * mult
                row[label] = f"{np.nanmean(v):.4g} ± {np.nanstd(v):.2g}"
            row["Ölüm görülmeyen seed"] = int(arr(c, d, "lifetime_censored").sum())
            row["Puan min-max"] = f"{np.nanmin(arr(c, d, 'score_min')):.2f}-{np.nanmax(arr(c, d, 'score_max')):.2f}"
            # eşleşmiş fark: ağırlıklı ort. - centroid, aynı yapılandırmada
            if d == "wavg":
                for key, label, mult, higher in METRICS[:3]:
                    diff = (arr(c, "wavg", key) - arr(c, "centroid", key)) * mult
                    wins = int(((diff > 0) if higher else (diff < 0)).sum())
                    row[f"Fark {label} (wavg-centroid)"] = f"{np.nanmean(diff):+.4g} ± {np.nanstd(diff):.2g} (iyi {wins}/{len(diff)})"
            rows.append(row)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(tables / "sensitivity_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r["Yapılandırma"], "|", r["Yöntem"], "|", r["Ağ ömrü (istek)"], "|", r["Kalan ağ enerjisi (J)"],
              "|", r["Ortalama hop sayısı"], "|", r["Puan min-max"])

    # --- Grafik: yapılandırma başına iki yöntem (ortalama ± std)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4))
    x = np.arange(len(CONFIGS))
    for ax, (key, label, mult, _) in zip(axes, METRICS[:3]):
        for j, d in enumerate(DEFUZZ):
            m = [np.nanmean(arr(c, d, key)) * mult for c in CONFIGS]
            s = [np.nanstd(arr(c, d, key)) * mult for c in CONFIGS]
            ax.bar(x + (j - 0.5) * 0.38, m, 0.38, yerr=s, capsize=2, color=COLORS[d], label=DEFUZZ[d])
        ax.set_xticks(x)
        ax.set_xticklabels(list(CONFIGS), rotation=40, ha="right")
        ax.set_title(label, fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figs / "sensitivity.png", dpi=200)
    print("BITTI")
