// Final report: algorithm, data parallelism, accuracy, full OS-level analysis (two devices).
// run:  python tools/report_data.py && set NODE_PATH=D:\tools\nodework\node_modules && node tools/make_final_report.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  ImageRun, AlignmentType, LevelFormat, BorderStyle, Footer, PageNumber, PageBreak,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const R = (...p) => path.join(ROOT, ...p);
const exists = (...p) => fs.existsSync(R(...p));
const readJSON = (f) => (fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : null);
const DATA = readJSON(R("results", "report_data.json")) || {};
const INT = readJSON(R("results", "interpretation.json")) || {};      // hand-written interpretation, added after the data is in
const FONT = "Arial", BLUE = "1F3A5F";

// ---------------- helpers -------------------------------------------------
function runs(text, opts = {}) {
  const out = [];
  String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/).forEach((seg) => {
    if (!seg) return;
    if (seg.startsWith("**")) out.push(new TextRun({ text: seg.slice(2, -2), bold: true, font: FONT, ...opts }));
    else if (seg.startsWith("`")) out.push(new TextRun({ text: seg.slice(1, -1), font: "Consolas", size: 19, ...opts }));
    else out.push(new TextRun({ text: seg, font: FONT, ...opts }));
  });
  return out;
}
const P = (t, o = {}) => new Paragraph({ spacing: { after: 120, line: 276 }, alignment: o.align, children: runs(t, o.run || {}) });
const H1 = (t) => new Paragraph({ keepNext: true, heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 140 }, children: [new TextRun({ text: t, font: FONT, bold: true, size: 30, color: BLUE })] });
const H2 = (t) => new Paragraph({ keepNext: true, heading: HeadingLevel.HEADING_2, spacing: { before: 220, after: 100 }, children: [new TextRun({ text: t, font: FONT, bold: true, size: 24, color: BLUE })] });
const B = (t) => new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 60, line: 264 }, children: runs(t) });
let curList = "num1";
const N = (t) => new Paragraph({ numbering: { reference: curList, level: 0 }, spacing: { after: 60, line: 264 }, children: runs(t) });
const NOTE = (t, fill = "FFF7E0", bar = "D97706") => new Paragraph({
  spacing: { before: 60, after: 140, line: 264 }, shading: { type: ShadingType.CLEAR, fill },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: bar, space: 6 } }, children: runs(t),
});
const gap = () => new Paragraph({ spacing: { after: 80 }, children: [] });
const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: "BFC5CC" };
const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };

function table(headers, rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const mk = (txt, w, head, i, keep) => new TableCell({
    width: { size: w, type: WidthType.DXA }, borders, shading: head ? { type: ShadingType.CLEAR, fill: "DCE6F2" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ keepNext: keep, alignment: opts.center && !head && i > 0 ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: runs(String(txt), { size: opts.size || 18, bold: head }) })],
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => mk(h, widths[i], true, i, true)) }),
      ...rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((c, i) => mk(c, widths[i], false, i, ri < rows.length - 1)) }))],
  });
}
// parse the markdown tables of a results file -> [{header:[...], rows:[[...]]}]
function mdTables(...p) {
  if (!exists("results", ...p)) return [];
  const blocks = fs.readFileSync(R("results", ...p), "utf8").split(/\r?\n\s*\r?\n/);
  const out = [];
  for (const b of blocks) {
    const ls = b.split(/\r?\n/).filter((l) => l.trim().startsWith("|"));
    if (ls.length < 3) continue;
    const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
    out.push({ header: cells(ls[0]), rows: ls.slice(2).map(cells) });
  }
  return out;
}
function mdTable(tbl, widths, opts) {
  const total = 9638;
  const w = widths || tbl.header.map(() => Math.floor(total / tbl.header.length));
  return table(tbl.header, tbl.rows, w, { center: true, ...opts });
}
function pngSize(f) { const b = fs.readFileSync(f); return [b.readUInt32BE(16), b.readUInt32BE(20)]; }
function figure(rel, caption, widthIn = 6.4) {
  const f = R("results", ...rel.split("/"));
  if (!fs.existsSync(f)) return [NOTE(`Figure not available: ${caption}`)];
  const [w, h] = pngSize(f);
  const wpx = Math.round(widthIn * 96), hpx = Math.round((wpx * h) / w);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 100, after: 40 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: fs.readFileSync(f), transformation: { width: wpx, height: hpx }, altText: { title: caption, description: caption, name: path.basename(f) } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [new TextRun({ text: caption, font: FONT, size: 18, italics: true, color: "444444" })] }),
  ];
}
function extractFn(file, sig) {
  const lines = fs.readFileSync(R("c", file), "utf8").split(/\r?\n/);
  const s = lines.findIndex((l) => sig.test(l));
  if (s < 0) throw new Error("not found " + sig);
  let e = s; while (!/^}/.test(lines[e])) e++;
  return lines.slice(s, e + 1);
}
function code(title, lines) {
  const out = [new Paragraph({ keepNext: true, spacing: { before: 140, after: 40 }, children: [new TextRun({ text: title, font: FONT, size: 18, bold: true, color: BLUE })] })];
  lines.forEach((l) => out.push(new Paragraph({ spacing: { before: 0, after: 0, line: 228 }, keepLines: true, shading: { type: ShadingType.CLEAR, fill: "F3F4F6" },
    children: [new TextRun({ text: l.replace(/\t/g, "    ") || " ", font: "Consolas", size: 16 })] })));
  out.push(gap());
  return out;
}
const interp = (key, fallback) => (INT[key] ? (Array.isArray(INT[key]) ? INT[key] : [INT[key]]) : fallback);

// ---------------- numbers used in the text --------------------------------
const mainNew = !!DATA.main_new;
const mainTables = mainNew ? mdTables("main_study_table.md") : mdTables("run1", "main_study_table.md");
const mainRows = mainTables[0] ? mainTables[0].rows : [];
const rowAt = (w) => mainRows.find((r) => String(r[0]) === String(w)) || [];
const sp = (w) => (rowAt(w)[3] || "?");
const base = DATA.baseline;

// ---------------- document -------------------------------------------------
const c = [];
c.push(new Paragraph({ spacing: { before: 1500, after: 120 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Multi-Threaded Video Segmentation", font: FONT, bold: true, size: 50, color: BLUE })] }));
c.push(new Paragraph({ spacing: { after: 240 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "An operating-system-level study of chunk-based data parallelism with POSIX threads", font: FONT, size: 26, color: "444444" })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "Operating Systems course project report", font: FONT, size: 22 })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "Group members: ______________________________", font: FONT, size: 22 })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [new TextRun({ text: "8 October 2026", font: FONT, size: 22 })] }));

c.push(H2("Summary"));
c.push(P("A video is split in time into **shots** (where the camera cuts) and **scenes** (groups of shots). The classical method used is a colour histogram per frame, a distance between consecutive histograms, and an adaptive threshold. The frames are independent, which makes the job a natural case of **data parallelism**: worker threads claim chunks of frames, compute their histograms and write to their own slice of the result. The report explains the algorithm and the parallel design, gives the accuracy, and then studies, at the operating-system level, how well that parallelism uses the machine."));
c.push(B(`**Speed.** Throughput rises from about ${Number(rowAt(1)[2] || 11700).toLocaleString("en-US")} frames per second with one worker to about ${Number(rowAt(12)[2] || 60000).toLocaleString("en-US")} with twelve, a speedup of **${sp(12)}x** at 12 workers (${sp(4)}x at 4 workers), on 11 real videos. The output is bit-identical at every worker count.`));
if (base) c.push(B(`**Baseline check.** Left to the scheduler, the single-threaded baseline ran ${((base.unpinned_over_pinned_time - 1) * 100).toFixed(0)}% slower than when pinned to a performance core; against the pinned baseline the 12-worker speedup is **${base.speedup["12"].pinned}x** (${base.speedup["12"].unpinned}x against the unpinned one).`));
c.push(B("**Accuracy.** Hard cuts agree with an independent detector at F1 0.91. Scene grouping reaches F1 about 0.35 against human labels, measured by leave-one-video-out testing (Section 4)."));
c.push(B("**When threads pay off.** On this project's laptop (Device 2), a fixed number of workers beats a pure sequential loop from about **12 to 24 frames** of 160x90 video, roughly 1 to 2 ms of work, and gives 2x from about 48 frames and 5.0x at 14,000 frames; on the second laptop (measured by `zhaymn`) the break-even is 8 frames and the best speedup 6.8x (Section 5.2)."));
c.push(B("**What limits scaling.** Section 5 separates core type, hyper-threading, file I/O and compute with controlled experiments, and looks at what each worker thread actually did."));
c.push(new Paragraph({ children: [new PageBreak()] }));

// ---- 1
c.push(H1("1. Scope"));
c.push(P("Video segmentation here means **temporal** segmentation: finding where one shot ends and the next begins, and grouping shots into scenes. The algorithm is deliberately classical and light, so that the cost of the work is dominated by reading and processing frames. That makes it a clean workload for studying threads: what the operating system does with them, how the cores are used, and where the speedup stops."));
c.push(P("Two laptops were used, both under Windows 11 (Device 1's study also includes Linux under WSL2):"));
c.push(table(["", "Device 1", "Device 2 (this project's laptop)"], [
  ["CPU", "Intel Core i5-13450HX", "Intel Core i5-12450HX"],
  ["Cores", "6 performance + 4 efficiency, 16 hardware threads", "4 performance (hyper-threaded) + 4 efficiency, 12 hardware threads"],
  ["Memory", "15.7 GB", "15.7 GB"],
  ["Software", "Windows 11, MinGW-w64 GCC 16.2; WSL2 Ubuntu 24.04, GCC 13.3", "Windows 11, MinGW-w64 GCC 16.2; WSL2 Ubuntu 22.04, GCC 11.4"],
  ["Measured by", "`zhaymn` (benchmark harness `tools/osbench.c`)", "this project's author"],
], [1500, 4000, 4138]));
c.push(gap());
c.push(NOTE("**Credit.** The operating-system benchmark harness (`tools/osbench.c`, `tools/analyze_osbench.py`) and all Device 1 measurements and the HTML report in `results/os_analysis/` were written and produced by `zhaymn`, a collaborator on this repository. Device 1 numbers in this report are taken from those files; they were not re-measured by us.", "EAF3FF", "2563EB"));

// ---- 2 algorithm
c.push(H1("2. The algorithm: colour histograms, the classical way"));
c.push(H2("2.1 Input"));
c.push(P("Each video is decoded once into a **raw file of BGR frames** with no header. Frame i sits at byte offset `i x width x height x 3`, so any thread can jump straight to any frame with one seek. Decoding is therefore not part of the timings; reading a frame means a file read served from the operating system's cache. All main experiments use 160x90 frames (43 KB each)."));
c.push(H2("2.2 One histogram per frame"));
c.push(P("A **colour histogram** counts how many pixels of a frame fall into each colour bucket. Every pixel is converted to hue and saturation (brightness is ignored, so lighting changes matter less), hue is cut into 8 bins and saturation into 8 bins, giving **64 buckets**. The counts are divided by the number of pixels, so every frame becomes 64 numbers that add up to 1. Two frames of the same shot have almost the same histogram, even when objects inside the picture move, because the histogram says what colours are present and not where."));
c.push(...code("c/common.c: the histogram of one frame", extractFn("common.c", /^void frame_hist/)));
c.push(H2("2.3 Distance between consecutive frames"));
c.push(P("The difference between frame i-1 and frame i is the Bhattacharyya distance of their histograms p and q, in the form used by OpenCV:"));
c.push(P("**d(p, q) = sqrt( 1 - sum over buckets of sqrt( p_i x q_i ) )**", { align: AlignmentType.CENTER }));
c.push(P("d is 0 for identical histograms and 1 for histograms with no colour in common. Inside a shot d stays near 0.02; at a hard cut it jumps to between 0.4 and 0.8 for exactly one frame."));
c.push(...code("c/common.c: the distance", extractFn("common.c", /^float bhattacharyya/)));
c.push(...figure("step1_signal.png", "Figure 1. Frame-to-frame distance on a real video (first 1,500 frames). Each tall spike is a hard cut; the red lines in the lower panel are the detected cuts.", 6.2));
c.push(H2("2.4 Adaptive threshold: from distances to shots"));
c.push(P("A fixed threshold would fail, because busy scenes have a higher baseline than calm ones. Instead a frame is declared a cut when its distance (a) exceeds the **mean plus 4 standard deviations** of the 25 frames around it, centre excluded, (b) is above an absolute floor of 0.15, (c) is the local maximum of that window, and (d) is at least 8 frames away from a stronger cut. The window statistics come from prefix sums, so each frame costs constant time. The step runs **once, after all workers have finished**, on the merged signal, so chunk borders cannot create inconsistent thresholds. The frames between two cuts form a **shot**."));
c.push(...code("c/threshold.c: the adaptive threshold (serial stage)", extractFn("threshold.c", /^long adaptive_threshold/)));
c.push(...figure("cut_vs_fade.png", "Figure 2. A hard cut changes the picture in one frame (top); a fade changes it over many frames and does not produce a spike (middle). The method finds hard cuts and mostly misses fades.", 6.2));
c.push(H2("2.5 Grouping shots into scenes"));
c.push(P("A scene is a group of consecutive shots about one place or event. Each shot is described by three keyframes (at 30%, 50% and 70% of the shot), each with a global colour histogram, a 3x3 grid of colour histograms (which keeps layout) and a 3x3 grid of edge-orientation histograms. The distance between two shots is the smallest chi-square distance over their keyframe pairs. Shots are linked to similar shots shortly before them by a dynamic programme (an adaptation of the shot-thread formulation of Liu et al., 2013), overlapping links form phases, and a second dynamic programme groups phases into scenes. The parameters (distance limit, link cost, scene cost) are chosen by cross-validation (Section 4.2)."));

// ---- 3 data parallelism
c.push(H1("3. How the data parallelism works"));
c.push(H2("3.1 Why frames can be processed in parallel"));
c.push(P("The histogram of frame i depends only on frame i. The distance needs the histogram of frame i-1, but that is cheap to recompute, so the only coupling between frames is one extra frame at the start of each chunk. This is **data parallelism**: every thread does the same job on a different piece of the data."));
c.push(H2("3.2 The design"));
c.push(table(["Step", "What happens", "Why it is efficient"], [
  ["1. Split", "The video is cut into `workers x 4` contiguous chunks of frames.", "Contiguous chunks give sequential file reads; 4 per worker allows load balancing."],
  ["2. Claim", "Each worker repeatedly takes the next unclaimed chunk number from a shared counter protected by one `pthread_mutex_t`.", "The lock is held for a few nanoseconds and taken only about 4 times per worker; faster cores simply take more chunks."],
  ["3. Own file handle", "Each worker opens the file itself and seeks to its chunk.", "No shared file position, so no locking around reads."],
  ["4. Overlap", "A chunk starting at frame s first reads frame s-1 to obtain the previous histogram.", "Makes the first difference of every chunk correct; costs one extra frame per chunk."],
  ["5. Compute and store", "For each frame: read, histogram, distance to the previous histogram, write into `diffs[i]` and `hists[i]`.", "Each worker writes only its own slice, so there are no data races and no lock on the output."],
  ["6. Join, then serial stage", "`pthread_join` on all workers, then the adaptive threshold runs once.", "Join is the barrier; the only serial work is about 20 microseconds."],
], [1700, 4300, 3638]));
c.push(gap());
c.push(...code("c/arch_a.c: process one chunk (overlap frame, then histogram and distance per frame)", extractFn("arch_a.c", /^static void process_chunk/)));
c.push(...code("c/arch_a.c: the worker thread (claims chunks through the mutex-protected counter)", extractFn("arch_a.c", /^static void \*worker/)));
c.push(...code("c/arch_a.c: creating the workers, joining them, then the serial threshold", extractFn("arch_a.c", /^int detect_chunked/)));
c.push(H2("3.3 Parallel parts of the scene stage"));
c.push(P("Two scene-stage steps are data parallel in the same way: computing the keyframe descriptors (threads split the shots between them, each with its own file handle) and computing the shot-to-shot distances (threads split the rows). The dynamic programmes that follow are recurrences, where each step needs the previous one, so they run on one thread. For a typical video of a few hundred shots the whole scene stage takes well under a millisecond, so the frame stage dominates the run time."));
c.push(...code("c/features.c: the keyframe worker (each thread describes the keyframes of its own shots)", extractFn("features.c", /^static void \*kf_worker/)));
c.push(H2("3.4 Correctness"));
c.push(P("Parallelism changes the order of work, not the answer. The per-frame distance signal and the cut list are **bit-identical** between the single-threaded loop and the threaded detector at 1, 2, 4 and 8 workers, and at 1, 4, 16 and 64 chunks per worker (`tests/test_invariance.py`, all tests pass). That is direct evidence that the one-frame overlap is right."));

// ---- 4 accuracy
c.push(H1("4. Accuracy"));
c.push(H2("4.1 Shot (cut) detection"));
c.push(table(["Test", "Precision", "Recall", "F1", "Note"], [
  ["Synthetic video, 241 true cuts", "1.000", "1.000", "1.000", "Easy by construction; validates the pipeline"],
  ["Big Buck Bunny against the ffmpeg scene detector (122 reference cuts, 137 found)", "0.861", "0.967", "0.911", "The reference is another detector, not human labels; the extra 15 cuts were not inspected"],
], [3500, 1000, 900, 800, 3438], { center: true }));
c.push(gap());
c.push(P("Only hard cuts are found. A fade or dissolve changes the picture slowly and produces no spike, so it is mostly missed (Figure 2)."));
c.push(H2("4.2 Scene grouping against human labels"));
c.push(P("The RAI broadcast dataset provides human-marked scene boundaries for 10 videos: 126 scenes, **116 true boundaries**. Before tuning, the evaluation was audited: the labels are aligned with the frames (no gaps, last labelled frame equals the frame count), the scorer agrees with an independent re-implementation, and **91% of true scene boundaries lie within 2 seconds of a detected cut**, so shot detection is not the limit."));
c.push(P("To avoid scoring parameters on the data they were tuned on, **leave-one-video-out** testing was used: for each video, the parameters (672 combinations) are chosen on the other nine and scored on the held-out one. A boundary counts as correct within a tolerance of 2 seconds (1 and 5 seconds are also reported). Intervals come from resampling whole videos."));
c.push(table(["Shot description", "F1 1 s", "F1 2 s", "F1 5 s", "F1 2 s interval"], [
  ["Mean global histogram (original, tuned)", "0.219", "0.287", "0.362", "0.20-0.36"],
  ["Global histogram, 1 keyframe", "0.249", "0.304", "0.405", "0.22-0.36"],
  ["Global histogram, 3 keyframes", "0.242", "0.304", "0.394", "0.23-0.36"],
  ["3x3 colour grid, 3 keyframes", "0.247", "0.290", "0.328", "0.23-0.35"],
  ["3x3 edge orientation, 3 keyframes", "0.161", "0.239", "0.367", "0.17-0.32"],
  ["**Global + colour grid + edge orientation, 3 keyframes (main)**", "0.284", "**0.348**", "0.468", "0.25-0.44"],
  ["Reference: every detected cut called a scene boundary", "0.156", "0.167", "0.179", "0.13-0.21"],
  ["Reference: evenly spaced scenes (true scene count)", "0.017", "0.043", "0.172", "0.01-0.07"],
], [4300, 900, 900, 900, 2638], { center: true }));
c.push(gap());
c.push(B("**The honest scene score is about 0.35 (F1 at 2 s).** It clearly beats the references, which are the real bar. Most of the improvement over an earlier 0.13 came from tuning and evaluating properly (the original method already reaches 0.29 when tuned this way), not from the richer description; the 0.06 gain from the grid and edge features lies within the interval overlap on only 116 boundaries."));
c.push(B("**It still over-splits:** 176 scenes predicted against 126 true. A scene boundary is a change of story or place, which colour and edge statistics capture only partly."));
c.push(B("The test set is small, so differences of a few hundredths in F1 cannot be distinguished."));

// ---- 5 OS analysis
c.push(H1("5. Operating-system-level analysis"));
c.push(H2("5.1 Method and measurement conditions"));
c.push(B("**Harnesses.** `tools/osstudy.c` (Device 2) and `tools/osbench.c` (Device 1, by `zhaymn`), both linking the same detector code from `c/`. Frames come from the operating system's file cache (warm), so decoding is excluded."));
c.push(B("**Baselines.** The single-threaded baseline is the plain loop in `c/seq.c`. On a hybrid CPU it must be **pinned to a fast performance core**, otherwise Windows may run it on a slow efficiency core and inflate every speedup."));
c.push(B("**Controls.** CPU sets are applied with `SetProcessAffinityMask`; workload variants isolate causes; every point records the median, the best time, the 90th percentile and user and kernel CPU time."));
c.push(B("**Shared machine.** Device 2 was in use during the measurements, with other applications open. To keep the results trustworthy the studies ran at high priority, **interleaved all configurations in round-robin rounds** (so drifting background load hits every configuration equally) and used the **best of the rounds** (interference only ever adds time). Background load was logged around every stage, and the noise level of every set is reported. Sets that include the efficiency cores were the most disturbed (Windows places background work there); the sets restricted to performance cores were the cleanest."));
c.push(B("**Discarded data.** A first attempt at the crossover study and at the Device 2 replication was thrown away: launched from a background chain, it capped the speedup at 1.8x for every job size and for every worker count from 4 to 12, and 2 workers gave no speedup at all. That pattern matches four efficiency cores, and the same program started from the foreground scaled normally (5.0x at 14,000 frames), so the first attempt was a launch problem and not a property of the code or the algorithm. Its files are kept in `results/os_study/invalid_try1/`; every number reported here comes from a run that passed the check '12 workers must exceed 3.5x at 14,000 frames'."));
const loadLog = exists("results", "os_study", "load_log.txt") ? fs.readFileSync(R("results", "os_study", "load_log.txt"), "utf8").trim().split(/\r?\n/) : [];
const noiseLog = exists("results", "os_study", "noise.txt") ? fs.readFileSync(R("results", "os_study", "noise.txt"), "utf8").trim().split(/\r?\n/) : [];
if (noiseLog.length) { c.push(P("Noise indicator per CPU set (fraction of configurations whose 90th-percentile time exceeded 1.5x their best time):")); c.push(...noiseLog.map((l) => new Paragraph({ spacing: { before: 0, after: 0 }, children: [new TextRun({ text: l, font: "Consolas", size: 16 })] })), gap()); }
if (loadLog.length) { c.push(P("Background CPU load sampled just before and after each stage (percent of the whole CPU):")); c.push(...loadLog.map((l) => new Paragraph({ spacing: { before: 0, after: 0 }, children: [new TextRun({ text: l, font: "Consolas", size: 16 })] })), gap()); }

// 5.2 data size
c.push(H2("5.2 The data-size study: when do threads pay off, and how throughput grows with the job"));
c.push(P("Starting threads costs time, so a small job is faster sequentially. The study varies the number of frames in the job from 1 to 16,384 (and the frame size from 32x18 to 1280x720 on Device 1), measures the sequential loop and the threaded detector at several worker counts with many repetitions, and reports the best worker count at each size. The same harness ran on both laptops."));
c.push(P("**Crossover study on Device 2.** The practical question is: if a program uses a fixed number of workers (2, 4, 8 or 12), from what job size is that faster than a pure sequential loop, in which no thread is created at all? The sequential loop is pinned to the fastest performance-core thread; sizes from 0 to 14,000 frames of 160x90 video; 25 interleaved rounds, best of rounds. The fixed cost is measured directly with zero frames of work, and the break-even is compared with a model."));
c.push(...figure("os_study/crossover.png", "Figure 3. Left: speedup over the pure sequential loop against the number of frames (dotted lines: break-even). Middle: throughput against job size. Right: fixed cost of one parallel run, measured with zero frames of work. Device 2.", 6.6));
const cx = mdTables("os_study", "crossover.md");
if (cx[0]) c.push(mdTable(cx[0], [650, 1000, 1500, 1050, 900, 800, 1400, 1100, 1238], { size: 14 }), gap());
interp("crossover", []).forEach((p) => c.push(typeof p === "string" ? B(p) : p));
c.push(...figure("os_study/datasize.png", "Figure 4. Throughput (frames per second) of the sequential loop (dashed) and the threaded detector (solid) against the size of the job, for 160x90 and 32x18 frames, and the resulting speedup. Windows, both devices.", 6.6));
const dsz = mdTables("os_study", "datasize.md");
if (dsz[0]) c.push(mdTable(dsz[0], [800, 1100, 1000, 1100, 1500, 1800, 1100, 1238], { size: 15 }), gap());
const be = mdTables("os_study", "device1", "breakeven.md");
c.push(P("Break-even by frame size, Device 1 (`zhaymn`), best worker count at each size:"));
if (be[0]) c.push(mdTable(be[0], [1300, 2200, 1700, 1100, 1100, 2238]), gap());
c.push(...figure("os_study/device1/breakeven.png", "Figure 5. Speedup against the number of frames for four frame sizes (Device 1, Windows). Above the red line threads win.", 6.4));
interp("datasize", [
  B("**For 160x90 frames threads start to win at about 8 frames**, roughly 0.4 ms of sequential work, but only barely (1.1x); they give about 3x at 64 frames and 6 to 7x at thousands of frames."),
  B("**The rule is about work, not frame count:** threads win once the sequential job takes more than roughly 0.4 to 1.4 ms. With tiny 32x18 frames the same fixed cost needs 256 frames to pay off. The videos in this project have about 14,000 frames, far above break-even."),
]).forEach((p) => c.push(typeof p === "string" ? B(p) : p));
c.push(P("Caveats: the speedup at each size is the best over worker counts (a fixed count does worse on small jobs); the unpinned Windows baseline may flatter small sizes; the largest frame sizes show noisier times."));

// 5.3 overhead
c.push(H2("5.3 The overhead study: what a parallel run costs before it does any work"));
c.push(P("Running the threaded detector on **zero frames** isolates the fixed cost: creating the worker threads, each opening its own file handle and allocating its frame buffer, one claim from the mutex-protected counter, and the join. The cost grows roughly linearly with the worker count. Separately, the cost of individual operating-system operations was measured."));
c.push(...figure("os_study/overhead.png", "Figure 6. Left: fixed cost of one parallel run against the number of workers (dotted: straight-line fit). Middle: effect of the number of chunks per worker. Right: costs of OS primitives. Both devices, Windows.", 6.6));
const ovh = mdTables("os_study", "overhead.md");
if (ovh[0]) c.push(mdTable(ovh[0], [700, 3200, 1500, 1500, 1300, 1438], { size: 15 }), gap());
interp("overhead", [
  B("Thread creation and file opening dominate the fixed cost; the mutex is negligible (tens of nanoseconds per claim, about four claims per worker per run)."),
  B("Chunk count matters little from 1 to 64 chunks per worker; more chunks add redundant overlap frames and seeks, which is why the design uses 4 per worker."),
]).forEach((p) => c.push(typeof p === "string" ? B(p) : p));

// 5.4 reading
c.push(H2("5.4 Efficient reading: how frames get to the workers"));
c.push(P("Every frame must travel from the file cache to a worker. Eleven strategies were compared on Device 2, each at 1 to 12 workers: `fread` with one frame per call (what the detector uses), `fread` with 4, 16 and 64 frames per call, Win32 `ReadFile` with a sequential-access hint (1 and 16 frames per call), a memory-mapped file with and without prefetching, a **no-file-access ceiling** (histograms of frames already in memory) and read-only variants without any computation. The gap to the ceiling is the price of reading."));
c.push(...figure("os_study/readeff.png", "Figure 7. Throughput by read strategy (top left), one worker (top right), eight workers (bottom left), and kernel share of CPU time (bottom right). Device 2.", 6.6));
const rdt = mdTables("os_study", "readeff.md");
if (rdt[0]) c.push(mdTable(rdt[0], [3000, 1100, 1000, 1000, 1000, 1300, 1238], { size: 15 }), gap());
const ot = mdTables("os_study", "os_study_table.md");
c.push(P("The earlier four-way split on all 12 CPUs (full, compute only, read only, memory-mapped), frames per second:"));
if (ot[1]) c.push(mdTable(ot[1], [1500, 2000, 2000, 2000, 2138], { size: 16 }), gap());
c.push(P("Device 1 (`zhaymn`) measured on Windows that 35 to 50% of worker CPU time is kernel time, almost all of it copying frames out of the file cache inside `ReadFile`, against 10 to 15% on Linux (WSL2); at 16 workers the job used 1.7x (Linux) to 2.3x (Windows) the CPU time of the sequential loop for the same frames."));
interp("readeff", []).forEach((p) => c.push(typeof p === "string" ? B(p) : p));

// 5.5 scaling
c.push(H2("5.5 Throughput and scaling with the number of workers"));
c.push(P(`Chunk-based detector on ${mainNew && base ? base.videos : 11} real videos, one to twelve workers; speedup is relative to the single-threaded baseline${mainNew ? " pinned to the fastest performance-core thread" : " (left to the scheduler)"}.`));
c.push(...figure(mainNew ? "main_study.png" : "run1/main_study.png", "Figure 8. Speedup, throughput, efficiency and Karp-Flatt metric against the number of workers.", 5.9));
if (mainTables[0]) c.push(mdTable(mainTables[0], [900, 1200, 1250, 1100, 1100, 1100, 1488, 1500]), gap());
if (mainNew && base) {
  c.push(table(["Workers", "Speedup vs pinned baseline", "Speedup vs unpinned baseline"],
    ["2", "4", "6", "8", "10", "12"].filter((w) => base.speedup[w]).map((w) => [w, base.speedup[w].pinned + "x", base.speedup[w].unpinned + "x"]), [2000, 3800, 3838], { center: true }), gap());
}
interp("main", [
  B("**Near-linear to 4 workers, then a bend.** The Karp-Flatt serial fraction rises with the worker count; a fixed serial fraction would give a flat line, so the shortfall is overhead and contention, not serial code. The code that really is serial, the threshold step, is about 20 microseconds."),
]).forEach((p) => c.push(typeof p === "string" ? B(p) : p));

c.push(H2("5.6 Scaling inside different sets of CPUs (Device 2)"));
c.push(P("To find out what ends the scaling, the same workload was run with the process restricted to different sets of logical CPUs. The machine has 4 performance cores with two hardware threads each (logical CPUs 0 to 7) and 4 efficiency cores (8 to 11). The sets include one single logical CPU, so threads that share one core can be compared with threads on separate cores."));
if (exists("results", "os_study", "cpu_topology.csv")) {
  const rows = fs.readFileSync(R("results", "os_study", "cpu_topology.csv"), "utf8").trim().split(/\r?\n/).slice(1).map((l) => l.split(","));
  c.push(table(["Logical CPU", "Physical core", "Class (from Windows)"], rows.map((r) => [r[0], r[1], r[2] === "0" ? "efficiency core" : "performance core"]), [2500, 2500, 4638], { center: true, size: 17 }), gap());
}
c.push(...figure("os_study/os_study.png", "Figure 9. Top left: speed of one thread pinned to each logical CPU. Top right: scaling inside each CPU set. Bottom left: which part limits scaling. Bottom right: share of CPU time spent in the kernel.", 6.5));
if (ot[0]) c.push(P("Speedup of the full workload against one worker on one performance core, by CPU set:"), mdTable(ot[0], null, { size: 16 }), gap());
const sumTxt = exists("results", "os_study", "os_study_summary.txt") ? fs.readFileSync(R("results", "os_study", "os_study_summary.txt"), "utf8").trim().split(/\r?\n/) : [];
sumTxt.forEach((l) => c.push(B(l)));
interp("sets", []).forEach((p) => c.push(typeof p === "string" ? B(p) : p));

c.push(H2("5.7 Worker-level analysis (Device 2)"));
c.push(P("For each worker thread the harness recorded how many chunks and frames it processed, its busy time, its user and kernel CPU time, and the logical CPU each chunk started on. This shows how well dynamic scheduling balances the load and what the operating system does with the threads."));
if (DATA.dev2 && DATA.dev2.workers) {
  c.push(...figure("os_study/workers.png", "Figure 10. One bar per worker thread, for several CPU sets: frames processed, busy time, kernel share of CPU time, and number of different logical CPUs each worker ran on.", 6.5));
  const wt = mdTables("os_study", "workers.md");
  if (wt[0]) c.push(mdTable(wt[0], [2100, 900, 1300, 1300, 1400, 1300, 1338], { size: 15 }), gap());
} else c.push(NOTE("Worker-level data was not captured."));
interp("workers", []).forEach((p) => c.push(typeof p === "string" ? B(p) : p));

c.push(H2("5.8 Hybrid cores and the baseline problem"));
c.push(P("On a CPU with performance and efficiency cores, the operating system decides where a thread runs. Device 1 measured a single thread to be 2.6 to 5.4 times slower on an efficiency core than on a performance core and observed Windows placing the unpinned baseline on an efficiency core, which makes the sequential time too slow and every speedup too good. This is why Section 5.5 reports the speedup against a baseline pinned to a fast performance core, and against the unpinned one."));
interp("hybrid", []).forEach((p) => c.push(typeof p === "string" ? B(p) : p));

// ---- 6 efficient threading
c.push(H1("6. How the design uses threads efficiently, and where it does not"));
c.push(H2("6.1 What is efficient"));
[
  "**Independent work per frame.** No dependency between workers except one overlap frame per chunk, under 2% redundant work for chunks of at least 64 frames.",
  "**Dynamic chunk claiming.** One mutex, taken about four times per worker per run, costing 18 to 60 ns each: below 0.01% of the run. Faster or less loaded cores take more chunks, which matters on a hybrid CPU.",
  "**No locks on the results.** Each worker writes only its own slice of the output arrays.",
  "**One file handle per thread.** No shared file position and no lock around reads.",
  "**Almost no serial code.** After the join only the 20-microsecond threshold step runs, so Amdahl's law is not what limits scaling.",
  "**Threads only where worth it.** The worker count is fixed per run; the crossover study shows that jobs of about 1 to 2 ms of sequential work or more benefit.",
].forEach((t) => c.push(B(t)));
c.push(H2("6.2 What is not efficient"));
[
  "**Beyond the performance-core thread count, extra workers add little wall-clock speed and a lot of CPU time** (1.7 to 2.3x the sequential CPU time at 16 workers, Device 1).",
  "**The read path.** `fread` copies every frame out of the file cache; on Windows this is 35 to 50% of worker CPU time. Memory-mapping removes the copy and the read call (variant `mmap` in Section 5.5).",
  "**Thread start-up** is paid on every call; a small thread pool would remove 0.1 to 0.6 ms per call when the detector is called repeatedly.",
  "**A pipeline design (one reader feeding workers through a queue) scaled worse** than chunked workers (peak 3.8x against 5.2x on the same video), because the single reader and the queue lock become the bottleneck.",
].forEach((t) => c.push(B(t)));
c.push(H2("6.3 Recommendations"));
c.push(P("Fall back to a sequential loop below about 1 ms of work; cap the workers near the performance-core thread count; use chunks of at least 64 frames; memory-map the video; reuse threads through a small pool. These follow from the measurements and were suggested by `zhaymn`'s analysis; only the memory-mapping effect is tested here, in Section 5.4."));

// ---- 7 limits
c.push(H1("7. Limitations"));
[
  "**Decoding is not measured.** Frames are pre-decoded to raw; real codec decoding is excluded.",
  "**Two laptops and a warm file cache.** Numbers are not portable. Device 2 was measured on a shared machine using high priority, interleaved rounds and best-of-N; Device 1 was measured by `zhaymn` under their own conditions, with run-to-run variation of 15 to 30% on Windows.",
  "**Device 2 coverage.** Device 2 has the crossover study, the replicated sweeps (160x90 and 32x18), the overhead and primitive costs, the read-strategy study, the CPU-set scaling, the per-worker analysis and the pinned-baseline main study. It was not measured on Linux, nor with 640x360 and 1280x720 frames, nor at high priority in the replicated sweep (Device 1 only).",
  "**Absolute speedups differ by about 15% between harnesses**: 5.2x for the real detector on four videos (14,000 frames each), 5.0x in the crossover study (14,000 frames), 5.9x in the replicated sweep (16,384 synthetic frames) and 6.6x in the CPU-set harness (6,000 frames, equal static split, no result storage). This is the same size as the run-to-run variation; the real detector on real videos (5.2x, and 5.19x on 11 videos) is the headline figure.",
  "**Linux is WSL2**, a virtual machine, not native Linux.",
  "**Hybrid-core explanations** rest on the controlled CPU-set experiments; no hardware performance counters were used.",
  "**Hard cuts only**; fades and dissolves are mostly missed. The cut accuracy is measured against another detector, not human labels.",
  "**Scene accuracy** is moderate (F1 about 0.35) on a small test set of 116 boundaries; the gain from the richer shot description is not statistically established.",
].forEach((t) => c.push(B(t)));

// ---- 8 conclusion
c.push(H1("8. Conclusion"));
c.push(P(`The classical histogram detector is a clean case of data parallelism, and the chunk-based design with a mutex-protected chunk counter, one file handle per thread, disjoint output slices and a post-join threshold produces identical results at every worker count. It reaches a speedup of ${sp(12)}x at 12 workers on Device 2 (${sp(4)}x at 4), and 6 to 7x on Device 1, with almost no serial code. A fixed number of workers beats a pure sequential loop from about 12 to 24 frames of 160x90 video on Device 2 (about 1 to 2 ms of work) and from 8 frames on Device 1. The controlled experiments of Section 5 separate the effect of core type, hyper-threading, file reads and compute on the speedup, and the worker-level analysis shows how the scheduler spreads the chunks. Accuracy is good for hard cuts (F1 0.91) and moderate for scenes (F1 about 0.35).`));

// ---- appendices
c.push(H1("Appendix A. Files and how to run"));
c.push(table(["File", "Purpose"], [
  ["c/common.[ch], c/threshold.c", "histogram, distance, adaptive threshold"],
  ["c/seq.c, c/arch_a.c", "single-threaded baseline; chunk-based data-parallel detector"],
  ["c/arch_b.c", "pipeline (reader / queue / workers) used as a comparison"],
  ["c/scenes.[ch], c/features.[ch], c/scene_api.c", "scene stage and keyframe descriptors"],
  ["tools/osstudy.c, tools/cpu_topology.c", "Device 2 OS study: CPU sets, variants, per-worker analysis, per-CPU speed"],
  ["tools/osbench.c, tools/analyze_osbench.py (zhaymn)", "OS benchmark harness: break-even sweeps, overheads, primitives"],
  ["tools/replicate_zhaymn.py, plot_devices.py", "re-run of the whole Device 1 study on Device 2, and two-device comparison"],
  ["tools/run_all_os.py, quiet.py", "one command for the OS study; --level 1/2/3, --robust"],
  ["tools/study.py, plot_study.py, scene_cv.py, audit_metric.py", "main scaling study, scene evaluation and metric audit"],
  ["tests/test_invariance.py", "thread-count and chunk-size invariance tests"],
], [3900, 5738]));
c.push(gap());
c.push(P("Everything for the OS study: `python tools/run_all_os.py --level 1 --robust` (about 20 minutes, works on a busy laptop); `--level 3` adds the full replication of Device 1's study. Data and figures are written to `results/`."));
c.push(H1("Appendix B. References and credits"));
curList = "num2";
[
  "`zhaymn`: OS-level benchmark harness, Device 1 measurements and analysis (repository `results/os_analysis/`, `tools/osbench.c`).",
  "Zhang, H. J., Kankanhalli, A., Smoliar, S. W. (1993). Automatic partitioning of full-motion video. Multimedia Systems, 1(1).",
  "Yeo, B.-L., Liu, B. (1995). Rapid scene analysis on compressed video. IEEE Trans. Circuits and Systems for Video Technology, 5(6).",
  "Bhattacharyya, A. (1943). On a measure of divergence between two statistical populations defined by their probability distributions. Bull. Calcutta Math. Soc., 35.",
  "Liu, C., Wang, D., Zhu, J., Zhang, B. (2013). Learning a contextual multi-thread model for movie/TV scene segmentation. IEEE Trans. Multimedia, 15(4).",
  "Baraldi, L., Grana, C., Cucchiara, R. RAI scene dataset (ten broadcast videos with human scene labels).",
  "Blender Foundation. Big Buck Bunny (2008), Creative Commons Attribution 3.0.",
  "Karp, A. H., Flatt, H. P. (1990). Measuring parallel processor performance. Communications of the ACM, 33(5).",
].forEach((t) => c.push(new Paragraph({ numbering: { reference: curList, level: 0 }, spacing: { after: 30, line: 250 }, children: runs(t, { size: 19 }) })));

const doc = new Document({
  creator: "Project group", title: "Multi-Threaded Video Segmentation: an OS-level study",
  styles: { default: { document: { run: { font: FONT, size: 21 } } } },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    ...["num1", "num2"].map((r) => ({ reference: r, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 340 } } } }] })),
  ] },
  sections: [{
    properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text: "Multi-Threaded Video Segmentation  |  page ", font: FONT, size: 16, color: "777777" }),
      new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "777777" })] })] }) },
    children: c,
  }],
});
Packer.toBuffer(doc).then((buf) => {
  const out = R("Final_Report_OS_Study_Video_Segmentation.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out, buf.length, "bytes");
});
