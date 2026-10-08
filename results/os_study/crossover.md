| workers | fixed cost O(P) | break-even (first size from which threads win) | sequential work there | data there | 2x from | 90% of best speedup from | model prediction N* | best speedup |
|---|---|---|---|---|---|---|---|---|
| 2 | 434 us | 12 frames | 0.83 ms | 0.52 MB | - frames | 96 frames | 11 frames | 1.91x |
| 4 | 431 us | 12 frames | 0.83 ms | 0.52 MB | 48 frames | 8192 frames | 8 frames | 3.24x |
| 8 | 668 us | 16 frames | 1.12 ms | 0.69 MB | 48 frames | 1024 frames | 10 frames | 4.32x |
| 12 | 894 us | 24 frames | 1.76 ms | 1.04 MB | 48 frames | 2048 frames | 13 frames | 5.01x |

Sequential time per frame at large sizes: 84.7 us. Model: N* = O(P) / (t1 x (1 - 1/S)), S = speedup at large sizes.
