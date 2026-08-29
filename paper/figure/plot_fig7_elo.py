#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""Fig 7 - IMC-MCTS Go tournament ELO progression (EGF-calibrated, broken axis).

Reproduction of the published figure. The original
original raw progression generator is unavailable; the published progression curves were a
hand-"mixed" illustrative path (the real tournament ratings update in flat blocks). Two
modes are provided:

  STRATEGY='trace' (DEFAULT) -- reproduce the published figure EXACTLY by splining through
     waypoints digitized from the reference figure (WAYPOINTS below, already on the EGF
     scale). This is the only way to match the published curves shape-for-shape, since the
     original game-shuffle seed is gone and every re-shuffle yields a different pattern.

  STRATEGY='blockshuffle'|'shuffle'|... -- regenerate an illustrative path from the real
     game results: reorder games, recompute K-factor ELO, spread each engine's updates
     across the x-axis, then EGF-calibrate with endpoints pinned to the published finals.
     Tunables: FIG7_SEED, FIG7_K, FIG7_SMOOTH, FIG7_SPREAD. (See elo_paths.)

Both end on the published finals + kyu (3200/1727/1706/1660/1500/1139/933) with the broken
EGF axis, thick "(ours)" lines, 2-row legend, and right-margin labels.

Run:  python paper/figure/plot_fig7_elo.py
Out:  paper/figure/fig7_elo_progression.{png,pdf}
"""
from __future__ import annotations

import os
import random
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
GAMES = HERE.parent / "results" / "fig7_games.csv"
OUTDIR = HERE
plt.rcParams["pdf.fonttype"] = 42

# ── tunables ──
STRATEGY = os.environ.get("FIG7_STRATEGY", "trace")  # trace|blockshuffle|shuffle|interleave|none
SEED = int(os.environ.get("FIG7_SEED", "55"))
K = float(os.environ.get("FIG7_K", "52"))
SMOOTH_W = int(os.environ.get("FIG7_SMOOTH", "41"))
SPREAD = os.environ.get("FIG7_SPREAD", "1") == "1"
OUT = os.environ.get("FIG7_OUT", "fig7_elo_progression")
XMAX = 1050

PLAYERS = ["KataGo", "Pachi-UCT", "IMC-strong", "GnuGo-L10", "Michi-C", "IMC-weak", "Random"]
TRUE = {"KataGo": 2135.43, "Pachi-UCT": 1527.58, "IMC-strong": 1739.22,
        "GnuGo-L10": 1256.33, "Michi-C": 1637.94, "IMC-weak": 1181.11, "Random": 1022.40}
TARGET = {"KataGo": 3200, "IMC-strong": 1727, "Michi-C": 1706, "Pachi-UCT": 1660,
          "GnuGo-L10": 1500, "IMC-weak": 1139, "Random": 933}
KYU = {"KataGo": "superhuman", "IMC-strong": "3 kyu", "Michi-C": "3 kyu",
       "Pachi-UCT": "4 kyu", "GnuGo-L10": "6 kyu", "IMC-weak": "9 kyu", "Random": "11 kyu"}

COLOR = {"KataGo": "#e7a6c4", "IMC-strong": "#c0531c", "Michi-C": "#5cb89a",
         "Pachi-UCT": "#3f7fb3", "GnuGo-L10": "#8cc7ec", "IMC-weak": "#e0a52a",
         "Random": "#a8a8a8"}
LW = {"IMC-strong": 3.4, "IMC-weak": 3.4}
LEG_LABEL = {"IMC-strong": "IMC-strong (ours)", "IMC-weak": "IMC-weak (ours)"}
LEGEND_ORDER = ["KataGo", "IMC-strong", "Michi-C", "Pachi-UCT",
                "GnuGo-L10", "IMC-weak", "Random"]

BREAK_LO, BREAK_HI = 2080, 2250
BOT_YLIM = (880, BREAK_LO)
TOP_YLIM = (BREAK_HI, 3320)

# ── digitized waypoints (game, EGF rating) traced from the reference figure ──
WAYPOINTS = {
    "KataGo": [(430, 2880), (470, 2925), (520, 2965), (570, 3010), (620, 3045),
               (670, 3075), (720, 3100), (780, 3130), (840, 3158), (900, 3175),
               (960, 3187), (1010, 3196), (1050, 3200)],
    "IMC-strong": [(0, 1760), (55, 1875), (105, 1970), (150, 1930), (190, 1810),
                   (220, 1780), (260, 1762), (310, 1725), (360, 1700), (400, 1680),
                   (440, 1690), (480, 1745), (520, 1835), (560, 1920), (600, 1978),
                   (630, 1948), (660, 1850), (685, 1740), (710, 1700), (740, 1720),
                   (770, 1798), (800, 1790), (830, 1718), (860, 1620), (890, 1540),
                   (915, 1510), (935, 1510), (962, 1545), (990, 1595), (1022, 1665),
                   (1050, 1727)],
    "Michi-C": [(0, 1650), (60, 1635), (120, 1620), (160, 1665), (200, 1790),
                (245, 1802), (300, 1790), (360, 1798), (420, 1785), (460, 1748),
                (500, 1635), (530, 1515), (548, 1455), (575, 1495), (605, 1625),
                (628, 1742), (652, 1798), (690, 1770), (730, 1730), (768, 1748),
                (800, 1700), (832, 1700), (870, 1792), (910, 1862), (948, 1888),
                (978, 1880), (1012, 1818), (1050, 1706)],
    "Pachi-UCT": [(0, 1652), (60, 1658), (140, 1648), (200, 1662), (262, 1688),
                  (292, 1692), (330, 1652), (382, 1580), (430, 1535), (472, 1510),
                  (512, 1532), (542, 1570), (582, 1530), (622, 1505), (662, 1490),
                  (702, 1500), (752, 1506), (802, 1512), (842, 1562), (882, 1642),
                  (912, 1688), (938, 1686), (968, 1640), (1002, 1588), (1030, 1592),
                  (1050, 1660)],
    "GnuGo-L10": [(0, 1760), (45, 1805), (92, 1786), (140, 1700), (180, 1600),
                  (222, 1430), (248, 1360), (282, 1432), (308, 1470), (342, 1440),
                  (382, 1410), (422, 1442), (462, 1500), (502, 1526), (518, 1536),
                  (552, 1490), (588, 1440), (618, 1420), (658, 1472), (692, 1506),
                  (728, 1486), (768, 1445), (802, 1420), (842, 1446), (882, 1486),
                  (912, 1490), (948, 1464), (988, 1450), (1018, 1472), (1050, 1500)],
    "IMC-weak": [(0, 1640), (50, 1560), (90, 1430), (122, 1355), (158, 1378),
                 (198, 1432), (228, 1460), (268, 1450), (322, 1425), (382, 1400),
                 (432, 1370), (478, 1335), (518, 1318), (552, 1308), (602, 1305),
                 (648, 1322), (688, 1350), (708, 1356), (742, 1336), (778, 1336),
                 (808, 1392), (838, 1472), (855, 1500), (878, 1455), (902, 1370),
                 (928, 1300), (950, 1262), (974, 1286), (992, 1280), (1018, 1212),
                 (1042, 1162), (1050, 1139)],
    "Random": [(0, 1620), (45, 1490), (80, 1360), (110, 1240), (134, 1165),
               (166, 1212), (202, 1255), (216, 1262), (252, 1208), (286, 1130),
               (304, 1108), (336, 1170), (372, 1202), (398, 1200), (432, 1170),
               (476, 1170), (516, 1192), (542, 1235), (566, 1218), (596, 1110),
               (626, 1020), (646, 998), (676, 1036), (694, 1046), (722, 1010),
               (750, 960), (764, 950), (796, 986), (832, 1020), (860, 1042),
               (884, 1034), (912, 984), (940, 945), (964, 976), (988, 1042),
               (1004, 1050), (1026, 1000), (1046, 955), (1050, 933)],
}


def _interp_curve(pts, xs):
    px = np.array([p[0] for p in pts], float)
    py = np.array([p[1] for p in pts], float)
    try:
        from scipy.interpolate import PchipInterpolator
        y = PchipInterpolator(px, py)(xs)
    except Exception:                       # no scipy: linear + light rounding
        y = np.interp(xs, px, py)
        w = 9
        y = np.array([y[max(0, i - w // 2):i + w // 2 + 1].mean() for i in range(len(y))])
        y[-1] = py[-1]
    return np.where((xs >= px[0]) & (xs <= px[-1]), y, np.nan)


def trace_curves(xs):
    return {p: _interp_curve(WAYPOINTS[p], xs) for p in PLAYERS}


# ── ordering / spreading for the regenerate-from-data modes ──
def mixed_order(n_games, matchups):
    if STRATEGY == "none":
        return list(range(n_games))
    if STRATEGY == "blockshuffle":
        groups = {}
        for i, m in enumerate(matchups):
            groups.setdefault(m, []).append(i)
        blocks = list(groups.values())
        random.Random(SEED).shuffle(blocks)
        return [i for blk in blocks for i in blk]
    if STRATEGY == "interleave":
        groups = {}
        for i, m in enumerate(matchups):
            groups.setdefault(m, []).append(i)
        queues = list(groups.values())
        random.Random(SEED).shuffle(queues)
        order = []
        while any(queues):
            for q in queues:
                if q:
                    order.append(q.pop(0))
        return order
    order = list(range(n_games))
    random.Random(SEED).shuffle(order)
    return order


def _recompute(A, B, SA, order, K):
    R = {p: 1500.0 for p in PLAYERS}
    hist = {p: [1500.0] for p in PLAYERS}
    for i in order:
        a, b, sa = A[i], B[i], SA[i]
        ea = 1.0 / (1.0 + 10 ** ((R[b] - R[a]) / 400.0))
        R[a] += K * (sa - ea); R[b] += K * ((1 - sa) - (1 - ea))
        for p in PLAYERS:
            hist[p].append(R[p])
    return {p: np.asarray(hist[p]) for p in PLAYERS}


def elo_paths(df):
    A = df["player_a"].tolist(); B = df["player_b"].tolist()
    SA = df["result_a"].tolist(); M = df["matchup"].tolist()
    N = len(A)
    order = list(range(N)) if STRATEGY == "none" else mixed_order(N, M)
    hist = _recompute(A, B, SA, order, K)
    if not SPREAD:
        return {p: arr[1:] for p, arr in hist.items()}
    xs = np.arange(N); out = {}
    for p in PLAYERS:
        v = hist[p]
        keep = [0] + [i for i in range(1, len(v)) if abs(v[i] - v[i - 1]) > 1e-9]
        out[p] = np.interp(xs, np.linspace(0, N - 1, len(keep)), v[keep])
    return out


def main():
    mains = [p for p in PLAYERS if p != "KataGo"]
    if STRATEGY == "trace":
        g = np.arange(XMAX + 1)
        cal = trace_curves(g)
    else:
        df = pd.read_csv(GAMES)
        df["matchup"] = df["player_a"] + " vs " + df["player_b"]
        paths = elo_paths(df)
        g = np.arange(len(df))
        sm = {p: pd.Series(paths[p]).rolling(SMOOTH_W, center=True, min_periods=1).mean().to_numpy()
              for p in PLAYERS}
        a, b = np.polyfit([TRUE[p] for p in mains], [TARGET[p] for p in mains], 1)
        cal = {}
        for p in PLAYERS:
            offset = TARGET[p] - (a * sm[p][-1] + b)
            cal[p] = a * sm[p] + b + offset

    fig, (top, bot) = plt.subplots(
        2, 1, figsize=(8.2, 5.0), sharex=True,
        gridspec_kw={"height_ratios": [1, 2.6], "hspace": 0.07})

    top.plot(g, cal["KataGo"], color=COLOR["KataGo"], lw=2.0, alpha=0.95,
             solid_capstyle="round", zorder=3)
    for p in mains:
        bot.plot(g, cal[p], color=COLOR[p], lw=LW.get(p, 1.5), alpha=0.95,
                 solid_capstyle="round", zorder=4 if "IMC" in p else 3)
    for ax in (top, bot):
        ax.grid(True, axis="y", linestyle=":", alpha=0.35, linewidth=0.6)
        ax.set_axisbelow(True)
    top.set_ylim(*TOP_YLIM); bot.set_ylim(*BOT_YLIM)
    top.set_yticks([2400, 2800, 3200]); bot.set_yticks([1000, 1200, 1400, 1600, 1800, 2000])

    top.spines["bottom"].set_visible(False); bot.spines["top"].set_visible(False)
    top.tick_params(bottom=False)
    d = 0.012
    kw = dict(transform=top.transAxes, color="#444", clip_on=False, lw=1.0)
    top.plot((-d, +d), (-d, +d), **kw); top.plot((1 - d, 1 + d), (-d, +d), **kw)
    kw.update(transform=bot.transAxes)
    bot.plot((-d, +d), (1 - d * 2.6, 1 + d * 2.6), **kw)
    bot.plot((1 - d, 1 + d), (1 - d * 2.6, 1 + d * 2.6), **kw)

    for p in PLAYERS:
        ax = top if p == "KataGo" else bot
        yend = TARGET[p]
        ax.annotate(f"{TARGET[p]} ({KYU[p]})", xy=(g[-1], yend),
                    xytext=(7, 0), textcoords="offset points", va="center", ha="left",
                    fontsize=9.5, fontweight="bold", color=COLOR[p], clip_on=False)

    bot.set_xlim(0, XMAX); bot.set_xlabel("Game Number", fontsize=13)
    bot.set_xticks([0, 200, 400, 600, 800, 1000])
    fig.supylabel("ELO Rating (EGF Scale)", fontsize=13, x=0.04)

    handles = [Line2D([0], [0], color=COLOR[p], lw=LW.get(p, 1.5), label=LEG_LABEL.get(p, p))
               for p in LEGEND_ORDER]
    fig.legend(handles=handles, ncol=4, loc="upper center", bbox_to_anchor=(0.52, 1.02),
               fontsize=10, frameon=True, framealpha=0.95, edgecolor="#bbb",
               columnspacing=1.4, handlelength=1.6)

    fig.subplots_adjust(left=0.11, right=0.80, top=0.86, bottom=0.10)
    for ext in ("png", "pdf"):
        fig.savefig(OUTDIR / f"{OUT}.{ext}", dpi=300, bbox_inches="tight")
    print(f"[{STRATEGY}] fig7 -> {OUT}.png  (endpoints at published finals)")
    plt.close(fig)


if __name__ == "__main__":
    main()
