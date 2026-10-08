| read strategy | 1 worker (fps) | 4 workers | 8 workers | 12 workers | kernel share at 8 workers | best / ceiling at 8 |
|---|---|---|---|---|---|---|
| fread, 1 frame/call (current) | 12463 | 45379 | 66235 | 73523 | 24% | 93% |
| fread, 4 frames/call | 13366 | 48714 | 66233 | 77940 | 22% | 93% |
| fread, 16 frames/call | 13438 | 50443 | 68242 | 77237 | 19% | 96% |
| fread, 64 frames/call | 13280 | 51646 | 66447 | 77109 | 22% | 93% |
| ReadFile (sequential hint), 1/call | 13172 | 49861 | 66631 | 77123 | 21% | 94% |
| ReadFile (sequential hint), 16/call | 13540 | 53112 | 67047 | 78306 | 19% | 94% |
| memory-mapped | 14383 | 54758 | 68988 | 82973 | 18% | 97% |
| memory-mapped + prefetch | 14122 | 54687 | 62807 | 81119 | 17% | 88% |
| no file access (ceiling) | 15340 | 59966 | 71071 | 91747 | 18% | 100% |
| (read only, no compute) io | 114264 | 244200 | 264760 | 273560 | 66% | - |
| (read only, no compute) rfio16 | 204290 | 476380 | 438468 | 392259 | 48% | - |
