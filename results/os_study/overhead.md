| device | fixed cost of one parallel run (a + b x workers, us) | create+join 1 thread (us) | create+join 8 threads (us) | fopen+fclose (us) | mutex uncontended (ns) |
|---|---|---|---|---|---|
| 1 | 82 + 28 x P | 103 | 260 | 138 | 18 |
| 2 | 47 + 63 x P | 369 | 534 | 156 | 16 |
