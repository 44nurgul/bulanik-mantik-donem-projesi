"""Canlı gösterim: bulanık sisteme istediğin girdiyi ver, dört yöntemin puanını ve çalışan kuralları gör.

Girdiler [0, 1] aralığında normalize değerlerdir:
  ER: adayın kalan enerjisi (0 = bitik, 1 = dolu)
  DS: [d(aday, mevcut) + d(aday, SIU)] / 2, en büyük değere bölünmüş (0 = yakın, 1 = uzak)
  BW: bağlantının bant genişliği (0 = dar, 1 = geniş)

Kullanım (repo kökünden):
  python experiments/demo.py                              # soru-cevap şeklinde, boş satır çıkış
  python experiments/demo.py --er 0.8 --ds 0.2 --bw 0.9   # tek aday
  python experiments/demo.py --adaylar "0.9,0.2,0.9;0.5,0.5,0.5;0.15,0.85,0.2"   # 3 aday: rulet olasılıkları
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np

from fuzzy_system import METHODS, RULES, _memberships, influence

ISIM = {"centroid": "Centroid (makale, baseline)", "bisector": "Bisector", "mom": "MOM",
        "wavg": "Ağırlıklı ortalama (Sugeno-0)"}
KUME = {"L": "Düşük", "M": "Orta", "H": "Yüksek"}


def kontrol(deger, ad):
    """Girdinin [0, 1] aralığında olduğunu doğrular."""
    if not 0.0 <= deger <= 1.0:
        sys.exit(f"{ad} 0 ile 1 arasında olmalı (girilen: {deger})")
    return deger


def uyelikler(er, ds, bw):
    """Her girdinin Düşük / Orta / Yüksek üyelik dereceleri."""
    for ad, deger in (("ER", er), ("DS", ds), ("BW", bw)):
        mu = _memberships(np.array([deger]), ad)
        print(f"  {ad} = {deger:.2f}  ->  " + ", ".join(f"{KUME[k]} {float(mu[k][0]):.2f}" for k in "LMH"))


def kural_gucleri(er, ds, bw, en_cok=4):
    """En güçlü çalışan kurallar. Kural gücü = çarpım-AND, kural içi VEYA = max (makale)."""
    mu = {"BW": _memberships(np.array([bw]), "BW"), "DS": _memberships(np.array([ds]), "DS"),
          "ER": _memberships(np.array([er]), "ER")}
    guc = []
    for no, (b, d, e, cikti) in enumerate(RULES, 1):
        w = max(mu["BW"][c][0] for c in b) * max(mu["DS"][c][0] for c in d) * max(mu["ER"][c][0] for c in e)
        guc.append((float(w), no, cikti))
    guc = [g for g in sorted(guc, reverse=True) if g[0] > 0][:en_cok]
    for w, no, cikti in guc:
        print(f"  Kural {no:2d}: güç {w:.2f}  ->  çıktı {KUME[cikti]}")
    if not guc:
        print("  Hiçbir kural çalışmadı (puan 0 sayılır).")


def tek_aday(er, ds, bw):
    print("\nÜyelik dereceleri:")
    uyelikler(er, ds, bw)
    print("\nÇalışan kurallar (en güçlüler):")
    kural_gucleri(er, ds, bw)
    print("\nEtki katsayısı (durulaştırma yöntemine göre):")
    for m in METHODS:
        print(f"  {ISIM[m]:32s} {float(influence([er], [ds], [bw], m)[0]):.3f}")


def adaylar(metin):
    """'er,ds,bw;er,ds,bw;...' biçimindeki adayların puanı ve rulet seçilme olasılığı."""
    liste = [[kontrol(float(v), "girdi") for v in a.split(",")] for a in metin.split(";")]
    er, ds, bw = (np.array([a[i] for a in liste]) for i in range(3))
    print(f"\n{'Aday':5s} {'ER':>5s} {'DS':>5s} {'BW':>5s}   " + "   ".join(f"{m:>16s}" for m in METHODS))
    puan = {m: influence(er, ds, bw, m) for m in METHODS}
    for i in range(len(liste)):
        print(f"{i + 1:<5d} {er[i]:5.2f} {ds[i]:5.2f} {bw[i]:5.2f}   " +
              "   ".join(f"{puan[m][i]:7.3f} (%{100 * puan[m][i] / puan[m].sum() if puan[m].sum() else 100 / len(liste):5.1f})" for m in METHODS))
    print("\nParantez içi: rulet seçilme olasılığı = puan / puanların toplamı (hepsi 0 ise eşit olasılık).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--er", type=float)
    ap.add_argument("--ds", type=float)
    ap.add_argument("--bw", type=float)
    ap.add_argument("--adaylar", help='"er,ds,bw;er,ds,bw;..."')
    a = ap.parse_args()

    if a.adaylar:
        return adaylar(a.adaylar)
    if None not in (a.er, a.ds, a.bw):
        return tek_aday(kontrol(a.er, "ER"), kontrol(a.ds, "DS"), kontrol(a.bw, "BW"))

    print("Bulanık sistem demosu. Girdiler 0 ile 1 arası. Çıkmak için boş satır.")
    while True:
        satir = input("\nER DS BW (örn: 0.8 0.2 0.9): ").split()
        if not satir:
            break
        if len(satir) != 3:
            print("Üç sayı gir: ER DS BW")
            continue
        try:
            er, ds, bw = (float(v) for v in satir)
            tek_aday(kontrol(er, "ER"), kontrol(ds, "DS"), kontrol(bw, "BW"))
        except ValueError:
            print("Sayı gir.")


if __name__ == "__main__":
    main()
