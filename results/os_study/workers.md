| config | wall (median run, s) | frames/worker min-max | load imbalance (max/mean frames) | chunks started on P / E cores | distinct CPUs per worker (mean) | kernel share of CPU time |
|---|---|---|---|---|---|---|
| all 12 CPUs, 12 workers | 0.115 | 500-500 | 1.00 | 71% / 29% | 3.2 | 44% |
| all 12 CPUs, 8 workers | 0.142 | 749-751 | 1.00 | 69% / 31% | 3.5 | 30% |
| P-cores+HT, 8 workers | 0.145 | 748-752 | 1.00 | 100% / 0% | 3.1 | 23% |
| 1 thread/core, 8 workers | 0.137 | 562-939 | 1.25 | 69% / 31% | 3.2 | 31% |
| 4 P-cores, 4 workers | 0.158 | 1500-1500 | 1.00 | 100% / 0% | 2.8 | 28% |
| 4 E-cores, 4 workers | 0.238 | 1500-1500 | 1.00 | 0% / 100% | 3.0 | 22% |
| ONE CPU, 4 workers | 0.810 | 750-1875 | 1.25 | 100% / 0% | 1.0 | 27% |
