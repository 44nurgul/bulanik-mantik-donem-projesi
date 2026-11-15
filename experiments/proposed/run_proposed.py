"""Özgün katkı deneyi: durulaştırma yöntemlerinin karşılaştırılması (Karar 26-28).

Aynı 30 ağda (aynı seed'ler, aynı topoloji ve bant genişlikleri) beş yöntem koşulur:
  centroid (baseline, makale), bisector, mom, wavg (ağırlıklı ortalama = Sugeno-0)
  ve referans olarak klasik OSPF.

Çalıştırma (repo kökünden):  python experiments/proposed/run_proposed.py [--seeds 30]
Çıktılar: results/tables/proposed_per_seed.csv, proposed_summary.csv,
          proposed_paired_vs_centroid.csv, execution_time.csv
          results/figures/proposed_comparison.png, score_distribution.png
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
from fuzzy_system import METHODS, influence
from simulation import HIST_BINS, run

NAMES = {"centroid": "Centroid (baseline)", "bisector": "Bisector", "mom": "MOM",
         "wavg": "Ağırlıklı ort. (Sugeno-0)", "ospf": "Klasik OSPF"}
COLORS = {"centroid": "#0072B2", "bisector": "#E69F00", "mom": "#CC79A7",
          "wavg": "#009E73", "ospf": "#7F7F7F"}
# (anahtar, başlık, birim çarpanı, "büyük iyi mi")
METRICS = [("lifetime", "Ağ ömrü (istek)", 1, True),
           ("residual_energy", "Kalan ağ enerjisi (J)", 1, True),
           ("avg_hops", "Ortalama hop sayısı", 1, False),
           ("delay", "Gecikme (ms)", 1e3, False),
           ("pdr", "PDR (%)", 1, True)]
EXTRA = [("active_nodes", "Aktif düğüm sayısı", 1, True)]


def job(args):
    seed, key = args
    return run(seed, "ospf") if key == "ospf" else run(seed, "fuzzy", key)


def benchmark_time(repeats=7, n_sets=3000, n_cand=20):
    """Kontrollü süre ölçümü: aynı girdiler, her yöntem için tekrarlı ölçüm, medyan (µs / çağrı).
    Simülasyon sırasındaki süre ölçümü diğer süreçlerden etkilendiği için bu test ayrıca yapılır."""
    rng = np.random.default_rng(0)
    data = rng.random((n_sets, 3, n_cand))
    out = {}
    for m in METHODS:
        times = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            for er, ds, bw in data:
                influence(er, ds, bw, m)
            times.append(1e6 * (time.perf_counter() - t0) / n_sets)
        out[m] = (float(np.median(times)), float(np.min(times)), float(np.max(times)))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=len(C.SEEDS))
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    seeds = C.SEEDS[:args.seeds]
    keys = list(METHODS) + ["ospf"]

    t0 = time.time()
    jobs = [(sd, k) for k in keys for sd in seeds]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        out = list(ex.map(job, jobs, chunksize=1))
    res = {k: [r for (sd, kk), r in zip(jobs, out) if kk == k] for k in keys}
    print(f"{len(jobs)} koşu tamamlandı, {time.time() - t0:.0f} s")

    tables, figs = ROOT / "results" / "tables", ROOT / "results" / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    def arr(k, key):
        return np.array([r[key] for r in res[k]], dtype=float)

    # --- Seed bazında ham sonuçlar
    cols = ["seed", "method", "defuzz", "active_nodes", "residual_energy", "lifetime", "lifetime_censored",
            "delay", "pdr", "avg_hops", "score_min", "score_max", "zero_score_frac", "all_zero_events"]
    with open(tables / "proposed_per_seed.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for k in keys:
            for r in res[k]:
                w.writerow([r[c] for c in cols])

    # --- Kontrollü süre ölçümü
    bench = benchmark_time()
    with open(tables / "execution_time.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Yöntem", "Medyan (µs/çağrı, 20 aday)", "Min", "Max"])
        for m in METHODS:
            w.writerow([NAMES[m]] + [f"{v:.0f}" for v in bench[m]])

    # --- Özet tablo: ortalama ± std
    summary = []
    for k in keys:
        row = {"Yöntem": NAMES[k]}
        for key, label, mult, _ in METRICS + EXTRA:
            v = arr(k, key) * mult
            row[label] = f"{np.nanmean(v):.4g} ± {np.nanstd(v):.2g}"
        row["Ölüm görülmeyen seed (ömür = alt sınır)"] = int(arr(k, "lifetime_censored").sum())
        if k != "ospf":
            row["Puan min"] = f"{np.nanmin(arr(k, 'score_min')):.3f}"
            row["Puan max"] = f"{np.nanmax(arr(k, 'score_max')):.3f}"
            row["Sıfır puanlı aday (%)"] = f"{100 * np.nanmean(arr(k, 'zero_score_frac')):.1f}"
            row["'Tüm adaylar 0' olayı (seed başına ort.)"] = f"{arr(k, 'all_zero_events').mean():.0f}"
            row["Puan hesabı (µs/çağrı, kontrollü)"] = f"{bench[k][0]:.0f}"
        summary.append(row)
    fields = list(dict.fromkeys(c for r in summary for c in r))
    with open(tables / "proposed_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(summary)
    for r in summary:
        print(r)

    # --- Eşleşmiş karşılaştırma (aynı seed'lerde fark): centroid'e göre
    paired = []
    for k in METHODS[1:]:
        row = {"Yöntem": NAMES[k]}
        for key, label, mult, higher in METRICS + EXTRA:
            d = (arr(k, key) - arr("centroid", key)) * mult
            wins = int(((d > 0) if higher else (d < 0)).sum())
            row[label] = f"{np.nanmean(d):+.4g} ± {np.nanstd(d):.2g} (iyi: {wins}/{len(d)})"
        paired.append(row)
    with open(tables / "proposed_paired_vs_centroid.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(paired[0]))
        w.writeheader()
        w.writerows(paired)
    print("\nCentroid'e göre eşleşmiş fark (ortalama ± std, kaç seed'de daha iyi):")
    for r in paired:
        print(r)

    # --- Grafik 1: metrik karşılaştırması (ortalama ± std)
    fig, axes = plt.subplots(1, 5, figsize=(16, 3.8))
    for ax, (key, label, mult, _) in zip(axes, METRICS):
        means = [np.nanmean(arr(k, key)) * mult for k in keys]
        stds = [np.nanstd(arr(k, key)) * mult for k in keys]
        ax.bar(range(len(keys)), means, yerr=stds, capsize=3, color=[COLORS[k] for k in keys])
        ax.set_xticks(range(len(keys)))
        ax.set_xticklabels(["centroid", "bisector", "MOM", "wavg", "OSPF"], rotation=45, ha="right")
        ax.set_title(label, fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(figs / "proposed_comparison.png", dpi=200)

    # --- Grafik 2: etki puanlarının dağılımı (hipotezi doğrudan gösteren grafik)
    fig, axes = plt.subplots(1, 4, figsize=(15, 3.6), sharey=True)
    edges = np.linspace(0, 1, HIST_BINS + 1)
    for ax, k in zip(axes, METHODS):
        h = np.sum([r["score_hist"] for r in res[k]], axis=0).astype(float)
        ax.bar(edges[:-1], 100 * h / h.sum(), width=1 / HIST_BINS, align="edge", color=COLORS[k], edgecolor="white")
        ax.set_title(f"{NAMES[k]}\naralık {np.nanmin(arr(k, 'score_min')):.2f} - {np.nanmax(arr(k, 'score_max')):.2f}", fontsize=10)
        ax.set_xlabel("etki puanı")
        ax.set_xlim(0, 1)
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("adayların oranı (%)")
    fig.tight_layout()
    fig.savefig(figs / "score_distribution.png", dpi=200)
