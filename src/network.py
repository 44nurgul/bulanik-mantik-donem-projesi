"""Ağ topolojisi: düğüm konumları, komşuluk ve bağlantı bant genişlikleri.

Aynı seed her zaman aynı ağı üretir. Böylece bulanık OSPF ve klasik OSPF
tıpatıp aynı ağda karşılaştırılır.
"""
import numpy as np

from config import (N_NODES, AREA, RADIO_RANGE, SIU_POS, BW_MIN, BW_MAX)


class Network:
    """Düğüm 0..N-1 sensörler, düğüm N (son indeks) SIU'dur."""

    def __init__(self, seed):
        rng = np.random.default_rng(seed)

        # N sensör alana düzgün rastgele yerleşir; SIU sabit konumdadır.
        sensors = rng.uniform(0.0, AREA, size=(N_NODES, 2))
        self.pos = np.vstack([sensors, SIU_POS])       # (N+1, 2)
        self.sink = N_NODES                            # SIU'nun indeksi

        # Her düğüm çifti arasındaki mesafe (N+1 x N+1 matris).
        diff = self.pos[:, None, :] - self.pos[None, :, :]
        self.dist = np.sqrt((diff ** 2).sum(axis=2))

        # Komşuluk: menzil içindeki (kendisi hariç) düğümler.
        self.adj = (self.dist <= RADIO_RANGE) & ~np.eye(N_NODES + 1, dtype=bool)

        # Bant genişliği: her bağlantıya U(BW_MIN, BW_MAX), simetrik ve sabit.
        bw = rng.uniform(BW_MIN, BW_MAX, size=self.dist.shape)
        bw = np.triu(bw, 1)
        self.bw = (bw + bw.T) * self.adj               # komşu olmayanlar 0

    def neighbors(self, i):
        """i düğümünün menzil içindeki komşularının indeksleri."""
        return np.flatnonzero(self.adj[i])
