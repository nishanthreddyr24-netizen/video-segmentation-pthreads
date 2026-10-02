"""Correctness invariant: the per-frame difference signal and the cut list must
be IDENTICAL for the sequential run, Architecture A at 1/2/4/8 threads with
several chunk granularities, and Architecture B at 1/2/4/8 threads.

run:  python -m unittest tests.test_invariance -v
(needs c/shotseg.exe built and data/synth_160x90.raw generated)"""
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "c", "shotseg.exe")
RAW = os.path.join(ROOT, "data", "synth_160x90.raw")


def run(mode, threads, extra=None):
    cmd = [EXE, RAW, "160", "90", mode, str(threads)]
    if extra:
        cmd.append(str(extra))
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True)
    with open(os.path.join(ROOT, "results", f"diffs_{mode}_{threads}.bin"), "rb") as f:
        d = f.read()
    with open(os.path.join(ROOT, "results", f"cuts_{mode}_{threads}.txt")) as f:
        c = f.read()
    return d, c


class Invariance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = run("seq", 1)

    def test_arch_a_threads(self):
        for t in (1, 2, 4, 8):
            with self.subTest(threads=t):
                self.assertEqual(run("a", t), self.ref)

    def test_arch_a_chunk_granularity(self):
        for cpt in (1, 4, 16, 64):
            with self.subTest(chunks_per_thread=cpt):
                self.assertEqual(run("a", 4, cpt), self.ref)

    def test_arch_b_threads(self):
        for t in (1, 2, 4, 8):
            with self.subTest(threads=t):
                self.assertEqual(run("b", t), self.ref)

    def test_arch_b_tiny_queue(self):        # stresses the cond-var logic
        self.assertEqual(run("b", 4, 2), self.ref)


if __name__ == "__main__":
    unittest.main()
