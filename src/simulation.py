"""Simülatör: enerji modeli, iki yönlendirme yöntemi ve metrikler.

Yöntemler:
  "fuzzy" -> makaledeki bulanık OSPF (komşu puanı + rulet seçimi)   [baseline]
  "ospf"  -> klasik OSPF (1/BW maliyetli en kısa yol, Dijkstra)      [referans]
"""
import heapq
import time

import numpy as np

import config as C
from fuzzy_system import influence
from network import Network

# ------------------------------------------------------------ Enerji modeli (Denklem 16-21)
K = C.PACKET_BITS
E_RX = K * C.E_ELEC                           # alma
E_SENSE = C.P_SENSE * C.T_SENSE               # algılama (yalnızca kaynak)
E_PROC = C.P_PROC * C.T_PROC                  # işleme (pakete dokunan her düğüm)


def e_tx(d):
    """Gönderme enerjisi: d < d0 ise d^2 kolu, değilse d^4 kolu."""
    if d < C.RADIO_RANGE:
        return K * C.E_ELEC + K * C.EPS_FS * d ** 2
    return K * C.E_ELEC + K * C.EPS_MP * d ** 4


# ------------------------------------------------------------ Yönlendirme
HIST_BINS = 20                                                   # puan histogramı: [0,1] aralığında 20 dilim


def new_stats():
    """Hipotezi göstermek için tutulan ölçümler: puan dağılımı, sıfır puanlılar, süre."""
    return {"calls": 0, "time": 0.0, "hist": np.zeros(HIST_BINS, dtype=np.int64),
            "min": np.inf, "max": -np.inf, "cands": 0, "zero_cands": 0, "all_zero": 0}


def fuzzy_path(net, src, alive, energy, rng, ds_max, defuzz="centroid", stats=None):
    """Bulanık rulet yönlendirme (makalenin Şekil 5'i). (yol, hedefe_vardı_mı) döner.

    defuzz: durulaştırma yöntemi (centroid = makale). stats: puan ve süre ölçümleri için sözlük."""
    path, cur, visited = [src], src, {src}
    while cur != net.sink and len(path) <= C.TTL:
        if net.adj[cur, net.sink]:                               # SIU menzildeyse doğrudan teslim (Karar 24)
            path.append(net.sink)
            return path, True
        # Aday: menzildeki canlı komşular, daha önce geçilenler hariç
        cand = np.array([j for j in net.neighbors(cur) if alive[j] and j not in visited])
        if cand.size == 0:
            return path, False                                   # çıkmaz: paket kayıp
        er = np.minimum(energy[cand] / C.E0, 1.0)                # SIU'nun enerjisi sınırsız -> 1
        ds = (net.dist[cand, cur] + net.dist[cand, net.sink]) / 2.0 / ds_max
        bw = net.bw[cur, cand] / C.BW_MAX
        t0 = time.perf_counter()
        w = influence(er, np.minimum(ds, 1.0), bw, defuzz)
        if stats is not None:
            stats["time"] += time.perf_counter() - t0
            stats["calls"] += 1
            stats["hist"] += np.histogram(w, bins=HIST_BINS, range=(0.0, 1.0))[0]
            stats["min"], stats["max"] = min(stats["min"], w.min()), max(stats["max"], w.max())
            stats["cands"] += w.size
            stats["zero_cands"] += int((w == 0).sum())
            stats["all_zero"] += int(w.sum() == 0)
        # Tüm adayların puanı 0 ise yedek kural: eşit olasılıklı seçim (sayılır)
        p = w / w.sum() if w.sum() > 0 else np.full(cand.size, 1.0 / cand.size)
        nxt = int(rng.choice(cand, p=p))                         # rulet seçimi
        path.append(nxt)
        visited.add(nxt)
        cur = nxt
    return path, cur == net.sink


def dijkstra_next_hop(net, alive):
    """SIU'dan başlayıp her düğümün SIU'ya giden bir sonraki adımını bulur (maliyet = 1/BW)."""
    nxt = {}
    dist = {net.sink: 0.0}
    heap = [(0.0, net.sink)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v in net.neighbors(u):
            if not alive[v]:
                continue
            nd = d + 1.0 / net.bw[u, v]
            if nd < dist.get(v, np.inf):
                dist[v] = nd
                nxt[v] = u
                heapq.heappush(heap, (nd, v))
    return nxt


def ospf_path(net, src, nxt):
    if src not in nxt:
        return [src], False                                      # SIU'ya yol yok
    path = [src]
    while path[-1] != net.sink:
        path.append(nxt[path[-1]])
    return path, True


# ------------------------------------------------------------ Bir koşu
def run(seed, method, defuzz="centroid", record_every=100):
    """method: "fuzzy" veya "ospf". defuzz yalnızca "fuzzy" için kullanılır."""
    t_start = time.perf_counter()
    stats = new_stats() if method == "fuzzy" else None
    net = Network(seed)
    n = C.N_NODES
    alive = np.ones(n + 1, dtype=bool)
    energy = np.full(n + 1, C.E0)
    energy[net.sink] = np.inf                                    # SIU enerjisi sınırsız
    src_rng = np.random.default_rng([seed, 1])                   # kaynak seçimi (iki yöntemde aynı dizi)
    route_rng = np.random.default_rng([seed, 2])                 # rulet
    ds_max = (C.RADIO_RANGE + np.hypot(C.AREA / 2, C.AREA / 2)) / 2.0

    first_death, sent, delivered, delays, hops = None, 0, 0, [], []
    series, nxt, dirty = [], None, True

    for req in range(1, C.N_REQUESTS + 1):
        sensors = np.flatnonzero(alive[:n])
        if sensors.size == 0:
            break
        src = int(sensors[int(src_rng.random() * sensors.size)])
        sent += 1

        if method == "ospf":
            if dirty:                                            # yalnızca düğüm ölünce yeniden hesapla
                nxt, dirty = dijkstra_next_hop(net, alive), False
            path, reached = ospf_path(net, src, nxt)
        else:
            path, reached = fuzzy_path(net, src, alive, energy, route_rng, ds_max, defuzz, stats)

        # Enerji harcaması: yol boyunca. Yolda düğüm ölürse paket kaybolur.
        def charge(i, amount):
            nonlocal first_death, dirty
            energy[i] -= amount
            if energy[i] <= 0 and alive[i]:
                energy[i], alive[i], dirty = 0.0, False, True
                if first_death is None:
                    first_death = req
            return alive[i]

        ok = charge(src, E_SENSE + E_PROC)
        delay = 0.0
        for u, v in zip(path[:-1], path[1:]):
            if not ok:
                break
            charge(u, e_tx(net.dist[u, v]))
            delay += K / (net.bw[u, v] * 1e6) + C.T_PROC
            ok = True if v == net.sink else charge(v, E_RX + E_PROC)
        if reached and ok:
            delivered += 1
            delays.append(delay)
            hops.append(len(path) - 1)

        if req % record_every == 0:
            series.append((req, int(alive[:n].sum()), float(energy[:n].sum())))

    # Tüm sensörler erken ölürse zaman serisini son durumla sonuna kadar tamamla
    while len(series) < C.N_REQUESTS // record_every:
        series.append((len(series) * record_every + record_every, int(alive[:n].sum()), float(energy[:n].sum())))

    return {
        "seed": seed, "method": method,
        "active_nodes": int(alive[:n].sum()),
        "residual_energy": float(energy[:n].sum()),
        "lifetime": first_death if first_death is not None else C.N_REQUESTS,
        "lifetime_censored": first_death is None,     # 10.000 istekte hiç düğüm ölmediyse True
        "delay": float(np.mean(delays)) if delays else float("nan"),
        "pdr": 100.0 * delivered / max(sent, 1),
        "avg_hops": float(np.mean(hops)) if hops else float("nan"),
        "series": series,
        "defuzz": defuzz if method == "fuzzy" else "-",
        "run_time_s": time.perf_counter() - t_start,
        # Puan dağılımı ve süre (yalnızca bulanık yöntem)
        "score_min": float(stats["min"]) if stats and stats["calls"] else float("nan"),
        "score_max": float(stats["max"]) if stats and stats["calls"] else float("nan"),
        "score_hist": stats["hist"].tolist() if stats else None,
        "zero_score_frac": stats["zero_cands"] / stats["cands"] if stats and stats["cands"] else float("nan"),
        "all_zero_events": stats["all_zero"] if stats else 0,
        "score_calls": stats["calls"] if stats else 0,
        "score_time_us": 1e6 * stats["time"] / stats["calls"] if stats and stats["calls"] else float("nan"),
    }
