| frame size | threads first beat sequential at | sequential work then | >=2x from | >=4x from | best speedup (best worker count) |
|---|---|---|---|---|---|
| 32x18 | 256 frames | 2.16 ms | 1024 | - | 2.97x |
| 160x90 | 16 frames | 2.54 ms | 128 | 16384 | 5.88x |

'best worker count' picks, for each size, the worker count that happened to be fastest; a fixed worker count does worse on small inputs.
