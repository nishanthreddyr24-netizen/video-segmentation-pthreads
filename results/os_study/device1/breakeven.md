| frame size | threads first beat sequential at | sequential work then | >=2x from | >=4x from | best speedup (best worker count) |
|---|---|---|---|---|---|
| 32x18 | 256 frames | 1.36 ms | 4096 | 16384 | 4.31x |
| 160x90 | 8 frames | 0.41 ms | 32 | 256 | 6.80x |
| 640x360 | 2 frames | 6.28 ms | 8 | 128 | 5.98x |
| 1280x720 | 4 frames | 14.07 ms | 8 | 128 | 5.19x |

'best worker count' picks, for each size, the worker count that happened to be fastest; a fixed worker count does worse on small inputs.
