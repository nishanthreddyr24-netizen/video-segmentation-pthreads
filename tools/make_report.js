// Builds Report_MultiThreaded_Video_Segmentation.docx
// run:  set NODE_PATH=D:\tools\nodework\node_modules && node tools\make_report.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, ImageRun, AlignmentType, LevelFormat, BorderStyle,
  Footer, PageNumber, PageBreak,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const R = (...p) => path.join(ROOT, ...p);
const FONT = "Arial";
const CW = 9638; // content width in DXA (A4, 0.79in margins)
const BLUE = "1F3A5F";

// ---------- helpers -------------------------------------------------------
function runs(text, opts = {}) {            // **bold** and `code` inline markup
  const out = [];
  text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).forEach((seg) => {
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
const NR = (t) => new Paragraph({ numbering: { reference: curList, level: 0 }, spacing: { after: 20, line: 250 }, children: runs(t, { size: 19 }) });
const NOTE = (t) => new Paragraph({
  spacing: { before: 60, after: 140, line: 264 },
  shading: { type: ShadingType.CLEAR, fill: "FFF7E0" },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: "D97706", space: 6 } },
  children: runs(t),
});

const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: "BFC5CC" };
const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
function table(headers, rows, widths, opts = {}) {
  const mk = (txt, w, head, bold, i, keep) => new TableCell({
    width: { size: w, type: WidthType.DXA }, borders,
    shading: head ? { type: ShadingType.CLEAR, fill: "DCE6F2" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ keepNext: keep, alignment: opts.center && !head && i > 0 ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: runs(String(txt), { size: 18, bold: head || bold }) })],
  });
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => mk(h, widths[i], true, false, i, true)) }),
      ...rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((c, i) => mk(c, widths[i], false, false, i, ri < rows.length - 1)) })),
    ],
  });
}
const gap = () => new Paragraph({ spacing: { after: 80 }, children: [] });

function pngSize(f) { const b = fs.readFileSync(f); return [b.readUInt32BE(16), b.readUInt32BE(20)]; }
function figure(file, caption, widthIn = 6.4) {
  const f = R("results", file), [w, h] = pngSize(f);
  const wpx = Math.round(widthIn * 96), hpx = Math.round((wpx * h) / w);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 100, after: 40 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: fs.readFileSync(f), transformation: { width: wpx, height: hpx },
        altText: { title: caption, description: caption, name: file } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
      children: [new TextRun({ text: caption, font: FONT, size: 18, italics: true, color: "444444" })] }),
  ];
}

function extractFn(file, sigRegex) {         // C function body from signature to closing "}" at col 0
  const lines = fs.readFileSync(R("c", file), "utf8").split(/\r?\n/);
  const s = lines.findIndex((l) => sigRegex.test(l));
  if (s < 0) throw new Error("not found: " + sigRegex);
  let e = s; while (!/^}/.test(lines[e])) e++;
  return lines.slice(s, e + 1);
}
function code(title, lines) {
  const out = [new Paragraph({ keepNext: true, spacing: { before: 140, after: 40 },
    children: [new TextRun({ text: title, font: FONT, size: 18, bold: true, color: BLUE })] })];
  lines.forEach((l) => out.push(new Paragraph({
    spacing: { before: 0, after: 0, line: 228 }, keepLines: true,
    shading: { type: ShadingType.CLEAR, fill: "F3F4F6" },
    children: [new TextRun({ text: l.replace(/\t/g, "    ") || " ", font: "Consolas", size: 16 })] })));
  out.push(gap());
  return out;
}

// ---------- content -------------------------------------------------------
const c = [];

// Title block
c.push(new Paragraph({ spacing: { before: 1800, after: 120 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Multi-Threaded Design for Video Segmentation", font: FONT, bold: true, size: 48, color: BLUE })] }));
c.push(new Paragraph({ spacing: { after: 300 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Data-parallel shot boundary detection and scene segmentation in C with POSIX threads", font: FONT, size: 26, color: "444444" })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
  children: [new TextRun({ text: "Operating Systems course project report", font: FONT, size: 22 })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
  children: [new TextRun({ text: "Group members: ______________________________", font: FONT, size: 22 })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
  children: [new TextRun({ text: "29 September 2026", font: FONT, size: 22 })] }));

c.push(H2("Summary"));
c.push(P("This project splits a video into shots (detecting the frames where the camera cut changes) and groups shots into scenes, and asks how each stage should be parallelised with threads. The primary design is **chunk-based data parallelism** using POSIX threads (pthreads) in C: the video is cut into contiguous chunks, worker threads claim chunks through a mutex-protected counter, and each worker writes only its own slice of the result array."));
c.push(P("**Main results (11 real videos, 1 to 12 workers, median of 5 runs):** the output is bit-identical at every worker count; throughput rises from about 11,700 to about 60,500 frames per second, a speedup of **5.19x** at 12 workers (3.55x at 4 workers, 89% efficiency). Speedup flattens after about 4 workers; the Karp-Flatt analysis shows this comes from growing overhead and contention, not from serial code. Hard-cut detection agrees well with an independent detector (F1 0.91). **Scene grouping is moderate:** with parameters chosen by leave-one-video-out on all 10 human-labelled videos, boundary F1 is about **0.35** at 2 s tolerance (95% interval 0.25-0.44, 116 true boundaries) against 0.17 for the best trivial baseline. Most of the gain over our earlier 0.13 came from better tuning, not from richer features (Section 7.7)."));

c.push(new Paragraph({ children: [new PageBreak()] }));

// 1
c.push(H1("1. Problem and scope"));
c.push(P("\"Video segmentation\" is interpreted here as **temporal segmentation**: (1) **shot boundary detection**, splitting the video at the frames where the camera cut changes, and (2) **scene segmentation**, grouping consecutive shots into scenes (a dialogue cut as A-B-A-B is many shots but one scene). This interpretation was chosen because the work is genuinely data-parallel and its design trade-offs can be measured without a GPU or a trained model."));
c.push(P("The project question is: **which parts of this pipeline can be parallelised with threads, how well, and where does the speedup stop?**"));

// 2
c.push(H1("2. Literature review"));
c.push(NOTE("**Verification status.** These summaries come from the project brief and recollection. Only abstracts and excerpts were checked, not full texts. Confirm claims, page numbers and the author list of Paper 2 before submission."));
c.push(H2("2.1 Paper 1 - background and evaluation protocol"));
c.push(P("Smeaton, Over and Doherty (2010), \"Video shot boundary detection: Seven years of TRECVid activity\", Computer Vision and Image Understanding 114(4), 411-418. A survey of the TRECVid shot-boundary track (2001-2007) that defines the task and the evaluation protocol (precision, recall and F1 with a tolerance window) and notes that decoding is typically the most expensive stage. We reuse its evaluation protocol."));
c.push(H2("2.2 Classical technique used"));
c.push(P("Colour-histogram differencing (Nagasaka and Tanaka 1992; Zhang, Kankanhalli and Smoliar 1993, Multimedia Systems 1(1)) with a sliding-window adaptive threshold (Yeo and Liu 1995, IEEE TCSVT 5(6)). The distance is the Bhattacharyya distance (Bhattacharyya 1943; Kailath 1967)."));
c.push(H2("2.3 Paper 2 - parallel design template"));
c.push(P("\"Video shot extraction on parallel architectures\" (2006), Springer LNCS chapter, DOI 10.1007/11946441_78 (author list to be confirmed). It parallelises a shot detector two ways, shared-memory threads on a symmetric multiprocessor and MPI on a cluster, and evaluates speedup against Amdahl's law. It justifies our choice of shared-memory threads and our speedup and efficiency methodology."));
c.push(H2("2.4 Paper 3 - scene segmentation algorithm"));
c.push(P("Liu, Wang, Zhu and Zhang (2013), \"Learning a contextual multi-thread model for movie/TV scene segmentation\", IEEE Transactions on Multimedia 15(4), 884-897. Shots are linked into **shot threads** (chains of visually similar shots, for example one camera angle); overlapping threads form **phases**, and phases are grouped into scenes by dynamic programming."));
c.push(NOTE("**Terminology.** A shot thread is an editing concept. It is **not** a CPU thread. In this report \"thread\" alone always means a CPU (pthread) thread."));
c.push(H2("2.5 Modern methods (context, not implemented)"));
c.push(P("Deep detectors such as TransNet V2 (Soucek and Lokoc, 2020) and AutoShot (2023) are more accurate, particularly on gradual transitions; multi-modal scene models (Rao et al., CVPR 2020; BaSSL, 2022) exceed Liu et al. They need trained weights and a GPU, and their parallel structure is dominated by model inference. We kept the classical pipeline so the parallel structure could be measured cleanly. This is a limitation (Section 9)."));
c.push(H2("2.6 The gap"));
c.push(P("No paper reviewed here parallelises scene segmentation. This project combines a parallel shot-extraction design (Paper 2) with a scene-segmentation algorithm (Paper 3) that has not been threaded, and measures which parts thread and which do not."));

// 3
c.push(H1("3. Type of parallelism used"));
c.push(H2("3.1 Decision: data parallelism"));
c.push(P("The main design uses **data parallelism**: the same operation (compute a colour histogram and a frame-to-frame distance) is applied by many threads to *different pieces of data* (different chunks of frames). The alternative, **task parallelism**, gives different operations to different threads (reader, feature extractor, merger). We chose data parallelism because:"));
c.push(N("The work is independent per frame. There are 14,000+ frames per video and no frame's histogram depends on another's."));
c.push(N("It scaled best in our measurements (5.2x for data parallelism against a 3.8x peak for the task pipeline)."));
c.push(N("A task pipeline is capped by its slowest stage and by the number of distinct stages; a data-parallel design scales with the amount of data."));
c.push(N("It matches the design of Paper 2, the paper the project is grounded in."));
c.push(table(["", "Data parallelism (main design)", "Task parallelism (comparison)"], [
  ["Idea", "Same job, different data chunks", "Different jobs on different threads"],
  ["Our implementation", "Architecture A: chunk workers", "Architecture B: reader, workers, merger"],
  ["Limit on speedup", "Memory bandwidth, cores, overhead", "Slowest stage; serial reader"],
  ["Synchronisation", "One mutex, taken once per chunk", "Queue mutex + 2 condition variables per frame"],
  ["Best measured speedup", "5.19x (mean of 11 videos)", "3.82x (Big Buck Bunny)"],
], [2000, 3819, 3819]));
c.push(gap());
c.push(H2("3.2 Threading model and synchronisation"));
c.push(B("**POSIX threads (pthreads)**, via MinGW-w64 winpthreads on Windows: real kernel threads scheduled by the OS (1:1 model), shared address space."));
c.push(B("**Dynamic scheduling.** The video is split into `workers x 4` contiguous chunks. Each worker repeatedly takes the next unclaimed chunk number from a shared counter guarded by `pthread_mutex_t`. Faster workers therefore take more chunks (load balancing)."));
c.push(B("**No lock on results.** Chunk k writes only `diffs[start..end)` and `hists[start..end)`. Different chunks never touch the same elements, so there is no data race and no lock is needed for output."));
c.push(B("**No shared file position.** Each worker opens its own file handle and seeks to its own chunk."));
c.push(B("**Overlap by one frame.** A chunk starting at frame s first reads frame s-1 to obtain the previous histogram for its first difference."));
c.push(B("**Join as barrier.** `pthread_join` on every worker before the serial post-merge stage."));
c.push(H2("3.3 What is and is not parallel"));
c.push(table(["Stage", "Type", "Parallel?"], [
  ["Read frame, HSV histogram, frame distance", "Data parallel over chunks", "Yes (Architecture A)"],
  ["Adaptive threshold on merged signal", "Sequential, after merge", "No (about 0.2 ms per video)"],
  ["Scene stage 1: shot-to-shot similarity", "Data parallel over shot rows", "Yes"],
  ["Scene stage 2: shot-thread inference (Viterbi DP)", "Recurrence, each step needs the last", "No"],
  ["Scene stage 3: phase grouping", "Linear sweep", "No"],
  ["Scene stage 4: phases-to-scenes DP", "Recurrence", "No"],
], [4300, 3238, 2100]));
c.push(gap());

// 4
c.push(H1("4. System design"));
c.push(H2("4.1 Input format and what is measured"));
c.push(P("Videos are decoded once by `ffmpeg` into a **raw BGR file** with no header. Frame i sits at byte offset `i x width x height x 3`, so any thread can jump to its chunk with one seek. Consequence: **codec decoding is not inside the timings**; \"read\" means a file read served from a warm OS cache. The decoding bottleneck described by Smeaton et al. is therefore not measured (Section 9)."));
c.push(H2("4.2 Per-frame feature and distance"));
c.push(P("Each frame becomes an 8x8-bin histogram over Hue and Saturation (Value ignored so brightness changes matter less), normalised to sum to 1. The frame difference is the OpenCV form of the Bhattacharyya distance between the histograms p and q of consecutive frames:"));
c.push(P("**d(p, q) = sqrt( 1 - BC(p, q) ),   BC(p, q) = sum over bins of sqrt( p_i x q_i )**", { align: AlignmentType.CENTER }));
c.push(P("d is 0 for identical histograms and 1 for histograms with no overlap. Inside a shot d stays near 0.02; at a hard cut it jumps to 0.4-0.8 for one frame."));
c.push(H2("4.3 Algorithm (Architecture A)"));
c.push(...code("Pseudocode", [
  "n_chunks = n_workers * 4",
  "worker():",
  "    loop:",
  "        lock; k = next++; unlock                 # only shared write",
  "        if k >= n_chunks: exit",
  "        (s, e) = chunk k",
  "        open own file; if s > 0: read frame s-1 -> prev histogram   # overlap",
  "        for i in [s, e): h = hist(frame i); diffs[i] = dist(prev, h); prev = h",
  "main: start workers; join all; cuts = adaptive_threshold(diffs)     # serial, post-merge",
]));
c.push(P("**Threshold after the merge.** Applying it once on the merged signal means chunk borders cannot create inconsistent thresholds. Rule: d exceeds the mean plus 4 standard deviations of the surrounding 25 frames (centre excluded), exceeds an absolute floor of 0.15, is the local maximum of the window, and cuts closer than 8 frames keep only the stronger."));
c.push(H2("4.4 Scene layer (simplified Liu et al.)"));
c.push(table(["Stage", "Description"], [
  ["0. Keyframe features", "Each shot is described by 3 to 5 keyframes (at 10-90% of the shot). A keyframe descriptor has three blocks: a global HSV histogram, a 3x3 grid of HSV histograms (keeps layout), and a 3x3 grid of edge-orientation histograms (Sobel, magnitude weighted; texture). Computed by worker threads that split the shots between them (data parallel over shots); about 0.04-0.16 s per video with 8 threads."],
  ["1. Similarity", "Distance between each shot and the next T = 18 shots: weighted mean over blocks of the cell-wise chi-square distance, minimum over keyframe pairs. Independent per pair, so rows are split across pthreads. With 3 keyframes this does 9 distance evaluations per pair, which makes the parallel stage heavier."],
  ["2. Shot-thread inference", "Viterbi DP: each shot chooses a parent among the previous k = 9 shots (allowed only if distance < tau) or starts a new shot thread; switching the parent offset has a small cost."],
  ["3. Phases", "Merge shot threads whose shot spans overlap."],
  ["4. Scenes", "DP that groups consecutive phases into scenes: a cost per scene plus the within-scene distance to the group mean."],
], [2200, 7438]));
c.push(gap());
c.push(NOTE("**Simplifications.** Liu et al. learn the distance and weights with EM and MI-SVM; that is **not implemented**. We use a fixed chi-square distance, equal block weights (1:1:1), and parameters chosen by cross-validation (Section 7.7). No public code exists for that paper, so the DP is **our interpretation of its structure** (parent assignment with a jump limit, phases, second DP) and was not checked line by line against its equations."));

// 5
c.push(H1("5. Core code"));
c.push(P("Excerpts are taken directly from the project source (`c/` folder). Full code is in the submitted archive."));
c.push(...code("common.c - colour histogram of one frame", extractFn("common.c", /^void frame_hist/)));
c.push(...code("common.c - Bhattacharyya distance (OpenCV form)", extractFn("common.c", /^float bhattacharyya/)));
c.push(...code("arch_a.c - one chunk: overlap frame, then histogram and distance per frame", extractFn("arch_a.c", /^static void process_chunk/)));
c.push(...code("arch_a.c - worker thread: claims chunks through a mutex-protected counter", extractFn("arch_a.c", /^static void \*worker/)));
c.push(...code("arch_a.c - creating and joining the worker threads, then the serial threshold", extractFn("arch_a.c", /^int detect_chunked/)));
c.push(...code("threshold.c - adaptive threshold (serial stage, O(1) window statistics via prefix sums)", extractFn("threshold.c", /^long adaptive_threshold/)));
c.push(...code("features.c - keyframe feature worker: each thread describes the keyframes of its own shots", extractFn("features.c", /^static void \*kf_worker/)));
c.push(...code("scenes.c - descriptor distance (weighted blocks of cell-wise chi-square)", extractFn("scenes.c", /^static float feat_dist/)));
c.push(...code("scenes.c - scene stage 1: parallel similarity worker (data parallel over rows, min over keyframe pairs)", extractFn("scenes.c", /^static void \*sim_worker/)));
c.push(...code("arch_b.c (comparison) - bounded queue insert: producer/consumer with condition variables", extractFn("arch_b.c", /^static void q_put/)));
c.push(...code("arch_b.c (comparison) - bounded queue remove", extractFn("arch_b.c", /^static Item q_get/)));

// 6
c.push(H1("6. Experimental setup"));
c.push(table(["Item", "Value"], [
  ["CPU", "Intel Core i5-12450HX: 8 physical cores, 12 logical processors (hybrid design)"],
  ["OS / compiler", "Windows 11; GCC 16.2 (WinLibs MinGW-w64 UCRT, POSIX threads), -O2"],
  ["Timing", "clock_gettime(CLOCK_MONOTONIC); per configuration 1 untimed warm-up + 5 timed runs; the median is used"],
  ["Baseline", "Separate single-threaded implementation (no threads, no chunking)"],
  ["Workers", "Every value from 1 to 12"],
], [2400, 7238]));
c.push(gap());
c.push(table(["Dataset", "Frames", "Frame rate", "Source", "Labels"], [
  ["Big Buck Bunny (Blender Foundation, CC-BY)", "14,315", "24", "480p H.264", "None; ffmpeg detector used as reference"],
  ["RAI dataset, videos 1-10 (Baraldi et al.; broadcast documentaries and talk shows)", "14,266-15,000 each", "25", "960x540 H.264", "Human scene boundaries"],
  ["Synthetic video (generated by us)", "14,862", "-", "160x90 raw", "Exact shot and scene ground truth"],
], [3200, 1500, 1000, 1400, 2538]));
c.push(gap());
c.push(P("All videos were downscaled to 160x90 raw BGR for the main runs. The RAI dataset is used only locally for this coursework; its licence terms are not stated on the download page."));
c.push(H2("Metrics"));
c.push(B("**Speedup** S(P) = T_baseline / T(P). **Efficiency** = S(P) / P. **Throughput** = frames / seconds."));
c.push(B("**Amdahl's law:** S(P) = 1 / ((1 - p) + p / P), where 1 - p is the serial fraction."));
c.push(B("**Karp-Flatt metric:** e(P) = (1/S - 1/P) / (1 - 1/P). If e stays constant with P, a fixed serial fraction explains the shortfall; if e grows, overhead or contention does."));
c.push(B("**Boundary F1:** a predicted boundary is correct if within a tolerance window of an unmatched true boundary (one-to-one matching; TRECVid-style protocol)."));

// 7
c.push(H1("7. Results"));
c.push(H2("7.1 Correctness"));
c.push(P("The per-frame difference signal is **bit-identical**, and the cut list identical, between the single-threaded run, Architecture A at 1, 2, 4 and 8 workers, Architecture A at 1, 4, 16 and 64 chunks per worker, and Architecture B at 1, 2, 4 and 8 workers plus a 2-slot queue that stresses the condition-variable logic. All four automated test groups pass (`tests/test_invariance.py`)."));

c.push(H2("7.2 Main study: speedup against number of workers"));
c.push(P("Architecture A, 11 real videos (Big Buck Bunny plus RAI videos 1-10), worker counts 1 to 12, median of 5 runs per point. The table shows the mean over the 11 videos."));
c.push(...figure("main_study.png", "Figure 1. Speedup, throughput, efficiency and Karp-Flatt metric against number of workers (Architecture A).", 5.9));
c.push(table(["Workers", "Time (s)", "Frames/s", "Speedup", "Min-max speedup", "Efficiency", "Karp-Flatt"], [
  ["1", "1.286", "11,513", "0.99", "0.91-1.08", "99%", "-"],
  ["2", "0.658", "22,442", "1.93", "1.72-2.14", "96%", "3.7%"],
  ["3", "0.454", "32,516", "2.79", "2.55-3.06", "93%", "3.7%"],
  ["4", "0.358", "41,358", "3.55", "3.22-3.82", "89%", "4.3%"],
  ["5", "0.336", "44,865", "3.84", "2.57-4.36", "77%", "7.5%"],
  ["6", "0.297", "50,233", "4.31", "3.42-4.84", "72%", "7.9%"],
  ["7", "0.276", "53,722", "4.61", "4.07-4.94", "66%", "8.7%"],
  ["8", "0.262", "56,483", "4.85", "4.34-5.25", "61%", "9.3%"],
  ["9", "0.254", "58,303", "5.00", "4.51-5.42", "56%", "10.0%"],
  ["10", "0.247", "59,926", "5.14", "4.73-5.64", "51%", "10.5%"],
  ["11", "0.244", "60,473", "5.19", "4.78-5.57", "47%", "11.2%"],
  ["12", "0.245", "60,451", "5.19", "4.79-5.76", "43%", "11.9%"],
], [1000, 1200, 1350, 1200, 1900, 1500, 1488], { center: true }));
c.push(gap());
c.push(P("Single-threaded baseline: 11,661 frames per second (mean over the 11 videos)."));
c.push(H2("Interpretation"));
c.push(B("**Near-linear up to 4 workers** (3.55x, 89% efficiency), then a visible bend; speedup saturates at about 5.2x from 11 workers on."));
c.push(B("**Karp-Flatt rises from 3.7% to 11.9%** and steps up between 4 and 5 workers. If a fixed serial fraction were the cause, this line would be flat. The shortfall is therefore due to growing overhead and contention, not serial code."));
c.push(B("**The Amdahl fit (serial fraction 0.102) matches the curve but must not be over-read.** The code that is actually serial, the threshold stage, is about 0.2 ms out of about 1.3 s (about 0.015%). The fitted 10% stands in for contention."));
c.push(B("**Likely cause (hypothesis, not proven):** the CPU has 4 performance cores with hyperthreading plus 4 efficiency cores, and all threads share memory bandwidth and the file cache. Workers beyond 4 land on hyperthread siblings or slower cores. No affinity or hardware-counter experiment was run to confirm this."));
c.push(B("**Run-to-run noise is real.** Big Buck Bunny at 12 workers measured 4.79x in an earlier single-video run and 5.76x in this one, about 15% apart. Quote ranges, not single numbers. One video dipped to 2.57x at 5 workers, which looks like operating-system noise."));
c.push(B("With 1 worker, Architecture A is 0.99x the plain loop: the small cost of chunking and opening file handles."));

c.push(H2("7.3 Supporting studies (Architecture A)"));
c.push(P("These two studies were run earlier, as single runs on Big Buck Bunny, before the main study; treat them as indicative."));
c.push(P("**Chunk granularity** (8 workers; 1, 4, 16, 64, 256 chunks per worker): 0.274, 0.260, 0.263, 0.272 and 0.313 seconds. The curve is flat from 1 to 64 and worse at 256 (extra seeks and one recomputed overlap frame per chunk). The load-balancing benefit of more chunks does not appear because the cost per frame is nearly uniform here."));
c.push(...figure("e2_chunks.png", "Figure 2. Time against chunks per worker (8 workers).", 3.6));
c.push(P("**Resolution scaling** (1,500 frames, 8 workers):"));
c.push(table(["Resolution", "Sequential (s)", "Speedup, Architecture A", "Speedup, Architecture B"], [
  ["160 x 90", "0.125", "3.57", "2.78"],
  ["320 x 180", "0.487", "4.68", "3.25"],
  ["640 x 360", "1.996", "4.82", "3.69"],
  ["1280 x 720", "8.653", "3.55", "2.38"],
], [2400, 2200, 2519, 2519], { center: true }));
c.push(gap());
c.push(P("Speedup rises from 160x90 to 640x360 (thread start-up cost amortised) and drops at 720p, where each 2.8 MB frame stresses memory and cache bandwidth. This fits the expectation that bandwidth-heavy work scales worse, but the cause was not isolated."));
c.push(...figure("e3_resolution.png", "Figure 3. Speedup at 8 workers against frame resolution.", 3.9));

c.push(H2("7.4 Task-parallel comparison (Architecture B, short)"));
c.push(P("Architecture B is a pipeline: one reader thread fills a bounded queue, N worker threads compute histograms, and a merger thread orders the results and computes distances. Its \"workers\" count excludes the reader and merger. Measured on Big Buck Bunny, speedup over the plain loop:"));
c.push(table(["Workers", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"], [
  ["A (data)", "0.91", "1.92", "2.72", "3.37", "3.58", "3.89", "4.10", "5.25", "5.42", "5.64", "5.57", "5.76"],
  ["B (task)", "1.21", "2.39", "3.43", "3.82", "3.43", "3.27", "3.14", "3.25", "3.11", "2.85", "3.06", "3.27"],
], [1100, 700, 700, 700, 700, 700, 700, 700, 700, 700, 700, 720, 718], { center: true }));
c.push(gap());
c.push(P("B is faster for 1-4 workers (its reader and merger add two extra live threads) but **peaks at 3.82x with 4 workers and then declines**, because one serial reader feeds every worker and all workers contend for one queue lock. A keeps improving to 5.8x on this video. This supports the choice of data parallelism as the main design."));

c.push(H2("7.5 Accuracy of shot (cut) detection"));
c.push(...figure("step1_signal.png", "Figure 4. Frame-to-frame difference on Big Buck Bunny (first 1,500 frames). Spikes are hard cuts; red lines are detected cuts.", 6.2));
c.push(table(["Test", "Precision", "Recall", "F1", "Notes"], [
  ["Synthetic video (241 true cuts)", "1.000", "1.000", "1.000", "Deliberately easy; validates the pipeline only"],
  ["Big Buck Bunny vs ffmpeg scene detector (122 reference cuts, 137 ours)", "0.861", "0.967", "0.911", "Reference is another classical detector, not human labels; the 15 extra cuts were not inspected"],
], [3300, 1000, 900, 800, 3638], { center: false }));
c.push(gap());
c.push(P("**Limitation - gradual transitions.** A hard cut changes the picture in one frame and shows as one tall spike. A fade or dissolve changes it slowly over 10-50 frames and produces a low bump, not a spike. The opening fade-in of Big Buck Bunny (frames 0-40) was not reported as a cut. Handling this needs a method such as twin-comparison (Zhang et al. 1993) or a deep model, and is out of scope."));
c.push(...figure("cut_vs_fade.png", "Figure 5. Top: hard cut between frames 284 and 285. Middle: fade-in from black (frames 0, 8, 16, 30). Bottom: two more hard cuts.", 6.4));
c.push(P("**Histograms and object motion.** A histogram counts how many pixels have each colour, not where they are. Swapping two patches of a frame (like moving a chair) changes many pixels but leaves the histogram unchanged (distance 0.000), and even shuffling every pixel leaves it unchanged. A genuinely different shot gives 0.720. This makes histograms robust to motion within a shot (few false cuts) but blind to spatial layout, so two different shots with the same colour mix can look identical."));
c.push(...figure("spatial_demo.png", "Figure 6. Original frame, two patches swapped, all pixels shuffled, and a different shot.", 6.4));

c.push(H2("7.6 Scene layer: speed and serial fraction"));
c.push(P("Measured on synthetic shot features (no video I/O), best of 3 runs. \"Serial share\" is the time in the three sequential stages divided by total time."));
c.push(table(["Shots", "1 worker (s)", "Serial share, 1 worker", "8 workers (s)", "Serial share, 8 workers", "Speedup"], [
  ["1,000", "0.0021", "29%", "0.0018", "33%", "1.1x"],
  ["10,000", "0.0181", "36%", "0.0094", "62%", "1.9x"],
  ["100,000", "0.1765", "35%", "0.0853", "64%", "2.1x"],
  ["1,000,000", "2.018", "37%", "0.868", "68%", "2.3x"],
], [1500, 1400, 1800, 1400, 1900, 1638], { center: true }));
c.push(gap());
c.push(...figure("e6_scenes.png", "Figure 7. Share of scene-layer time spent in the sequential DP stages.", 4.2));
c.push(P("With 1 million shots the parallel similarity stage speeds up about 4.5x at 8 workers (1.27 s to 0.28 s), but the DP stages barely move (0.75 s to 0.59 s). The layer as a whole is capped near 2.3x, close to the Amdahl bound of 1/0.37 = 2.7x for a 37% serial fraction. The phases-to-scenes DP is the largest serial cost. For a typical video (about 240 shots) the scene layer takes well under a millisecond, so end-to-end speed is set by the shot stage; the scene layer's serial cost matters only for very long inputs."));

c.push(H2("7.7 Accuracy of scene grouping on human labels"));
c.push(H2("Metric audit (done before tuning)"));
c.push(P("The RAI dataset provides human-marked scene boundaries for 10 videos. Before tuning anything we audited the evaluation (`tools/audit_metric.py`, output in `results/audit_metric.md`):"));
c.push(B("**Labels are aligned.** No gaps between scenes, and each video's last labelled frame equals its frame count."));
c.push(B("**The test set is small:** 126 scenes, **116 true boundaries** over 10 videos. One video can move a pooled score a lot, so every number carries a resampling interval."));
c.push(B("**The scorer is correct.** A clean re-implementation (optimal one-to-one matching) reproduces the earlier scores exactly (0.105 / 0.105 / 0.144 at 1 / 2 / 5 s for the default parameters)."));
c.push(B("**Shot detection is not the bottleneck:** 91% of true scene boundaries lie within 2 s of a detected cut (97% within 5 s; 84% within 1 s)."));
c.push(B("**The earlier random baseline was too weak.** Calling every detected cut a scene boundary scores F1 0.167 at 2 s, and evenly spaced scenes score 0.172 at 5 s. A scene method has to beat these, not random guessing."));
c.push(B("Coverage/overflow was also tried and dropped: our implementation could not be verified against a reference and gave implausible values."));
c.push(H2("Leave-one-video-out comparison of features"));
c.push(P("For each feature set and each video, the scene parameters (tau, new-thread cost, parent-switch cost, new-scene cost, maximum phases per scene; 672 combinations) are chosen **only on the other 9 videos** by maximising pooled F1 at 2 s, then scored on the held-out video. Results are pooled over the 10 held-out videos. The main method, fixed in advance, is the full descriptor with 3 keyframes; the other rows are ablations."));
c.push(table(["Features", "F1 1 s", "F1 2 s", "F1 5 s", "P / R at 2 s", "Pred. / true scenes", "F1 2 s interval"], [
  ["Old method (mean global histogram), properly tuned", "0.219", "0.287", "0.362", "0.26 / 0.33", "159 / 126", "0.20-0.36"],
  ["Global histogram, 1 keyframe", "0.249", "0.304", "0.405", "0.28 / 0.34", "151 / 126", "0.22-0.36"],
  ["Global histogram, 3 keyframes", "0.242", "0.304", "0.394", "0.25 / 0.38", "183 / 126", "0.23-0.36"],
  ["Spatial 3x3 colour grid, 3 keyframes", "0.247", "0.290", "0.328", "0.19 / 0.59", "363 / 126", "0.23-0.35"],
  ["Edge orientation 3x3, 3 keyframes", "0.161", "0.239", "0.367", "0.18 / 0.37", "254 / 126", "0.17-0.32"],
  ["Spatial + edge, 3 keyframes", "0.192", "0.244", "0.347", "0.21 / 0.28", "165 / 126", "0.17-0.31"],
  ["**Full: global + spatial + edge, 3 keyframes (main)**", "0.284", "**0.348**", "0.468", "0.30 / 0.42", "176 / 126", "0.25-0.44"],
  ["Full, 5 keyframes (post-hoc ablation)", "0.296", "0.361", "0.462", "0.31 / 0.43", "171 / 126", "0.27-0.45"],
  ["Baseline: every detected cut is a boundary", "0.156", "0.167", "0.179", "0.09 / 0.91", "-", "0.13-0.21"],
  ["Baseline: evenly spaced, true number of scenes", "0.017", "0.043", "0.172", "0.04 / 0.04", "-", "0.01-0.07"],
], [3000, 700, 800, 700, 1100, 1250, 2088], { center: true }));
c.push(gap());
c.push(H2("Interpretation"));
c.push(B("**The honest scene score is now about 0.35 (F1 at 2 s), not 0.13.** Most of that change is better tuning and evaluation, not better features: the old method scores 0.29 when tuned over 10 videos with held-out testing. The earlier 0.13 came from tuning on only 5 videos with a small grid, so the two numbers are not directly comparable."));
c.push(B("**Richer features help only a little, and the evidence is weak.** The full descriptor beats the old method by about 0.06, but the intervals overlap heavily; with 116 boundaries this is not a proven gain. One keyframe with the plain histogram already reaches 0.30. The spatial grid alone (0.29) and the edge feature alone (0.24) did not help; only the combination did."));
c.push(B("**It now clearly beats the trivial baselines** (every-cut 0.167, interval 0.13-0.21), which is the real bar."));
c.push(B("**It still over-splits:** 176 predicted scenes against 126 true ones."));
c.push(B("**Remaining optimism.** About 8 feature sets x 672 parameter sets were searched. The held-out protocol removes tuning leakage, but reporting the best row would still be mildly optimistic, which is why the main method was fixed in advance. The 5-keyframe row is a post-hoc extra. The chosen new-scene cost was the same in every fold and is not at the edge of the (widened) grid."));
c.push(H2("Comparison with a simple classical baseline"));
c.push(P("To check that the shot-thread DP is a reasonable classical choice, we also ran spectral clustering of the shot-similarity matrix with a temporal kernel. This is the simple baseline of Baraldi et al. (ACM MM 2015), which they found superior or equivalent to two published classical methods (an audio-visual shot-transition graph and colour clustering with sequence alignment) on BBC Planet Earth. Same features, same leave-one-video-out protocol (84 parameter combinations for spectral clustering against 672 for the DP). M_iou is the symmetric intersection-over-union measure from that paper."));
c.push(table(["Method", "Features", "F1 2 s", "F1 2 s interval", "M_iou", "Pred. / true scenes"], [
  ["**DP (ours)**", "**Full, 3 keyframes**", "**0.348**", "0.25-0.44", "**0.527**", "176 / 126"],
  ["Spectral clustering", "Full, 3 keyframes", "0.311", "0.24-0.38", "0.473", "274 / 126"],
  ["DP", "Old (mean global histogram)", "0.287", "0.20-0.36", "0.430", "159 / 126"],
  ["Spectral clustering", "Old (mean global histogram)", "0.244", "0.20-0.29", "0.432", "279 / 126"],
  ["Baseline: evenly spaced (true number of scenes)", "-", "0.043", "0.01-0.07", "0.432", "-"],
  ["Baseline: every detected cut", "-", "0.167", "0.13-0.21", "0.231", "-"],
], [2600, 2300, 900, 1400, 900, 1538], { center: true }));
c.push(gap());
c.push(B("**The DP is at least as good as the simple classical baseline on both metrics**, so switching to spectral clustering would not help. The two intervals overlap, so the ranking is suggestive, not proven."));
c.push(B("Spectral clustering over-segments much more (about 275 predicted scenes against 126 true) because cluster labels switch back and forth between neighbouring shots. Our version is our own implementation of the described baseline, not the authors' code."));
c.push(B("M_iou rewards even spacing (0.432), and that baseline is given the true number of scenes. By M_iou the old features and the spectral variant are no better than that oracle baseline; only the full-feature DP (0.527) is clearly above it."));
c.push(B("**Untested classical cue:** in the same paper the strongest system added the speech transcript (text topic information) to the visual features. We did not use audio or transcripts; that is the most promising classical extension and is listed as future work."));
c.push(P("**Why scene grouping stays hard.** A cut is visual; a scene boundary is about meaning (a change of topic or place). Colour and edge statistics cannot capture meaning. Liu et al. report F1 of 0.67-0.72 using learned features on movies and TV drama, which is not comparable to this setting. Learned embeddings are the next step and are not part of this work."));

// 8
curList = "num2";
c.push(H1("8. Discussion: explaining the results"));
c.push(N("**Why does speedup flatten after about 4 workers?** Not because of serial code (about 0.015% of the run). The Karp-Flatt metric rises with worker count, pointing to overhead and contention; the knee coincides with the machine's 4 performance cores (hypothesis)."));
c.push(N("**Why is the pipeline (task parallelism) worse than chunks (data parallelism)?** A single serial reader feeds all workers and all of them share one queue lock; extra workers add contention, and speedup falls after 4 workers."));
c.push(N("**Why can the scene layer not scale like the shot stage?** Its DP stages are recurrences (each step needs the previous state), so they cannot be split across threads. Measured serial share: 29-68%."));
c.push(N("**Why is the correctness invariant important?** Chunked processing is only valid if the 1-frame overlap is right. Identical output at every worker count and chunk size is direct evidence that it is."));

// 9
c.push(H1("9. Limitations"));
c.push(B("**Decoding not measured.** Frames are pre-decoded; real codec decoding (the bottleneck noted by Smeaton et al.) is not in the timings."));
c.push(B("**One machine, one hybrid CPU, warm file cache.** Numbers are not portable; the main study has run-to-run variation of about 15%."));
c.push(B("**Cause of the plateau unproven.** The hybrid-core explanation was not tested with affinity or hardware counters."));
c.push(B("**Classical detector only.** No deep model; gradual transitions (fades, dissolves) are mostly missed."));
c.push(B("**Cut accuracy** on real footage was compared with another classical detector, not human labels; PySceneDetect was not run."));
c.push(B("**Scene layer** is a simplified Liu et al. (no EM or MI-SVM, fixed 1:1:1 block weights, DP is our interpretation). On human labels it reaches F1 about 0.35 at 2 s tolerance (interval 0.25-0.44) on a small test set of 116 boundaries; the gain from richer classical features over a tuned global histogram is not statistically established."));
c.push(B("**Supporting studies** (chunk size, resolution) are single runs on one video."));
c.push(B("**Literature** not fully verified against full texts."));

// 10
c.push(H1("10. Conclusion"));
c.push(P("A chunk-based data-parallel design in C with POSIX threads, per-thread file handles, a mutex-guarded chunk counter and a post-merge threshold produces bit-identical results at every worker count and reaches about 5.2x speedup (60,000 frames per second against 11,700) on a 12-thread CPU across 11 real videos. Scaling is near-linear to 4 workers and then limited by overhead and contention, not serial code. A task-parallel pipeline scaled worse (peak 3.8x). Hard-cut detection agrees well with an independent detector (F1 0.91). The scene layer's similarity stage parallelises, but its dynamic-programming stages do not, capping that layer near 2.3x; and with leave-one-video-out tuning its accuracy against human scene labels is moderate (F1 about 0.35 at 2 s, against 0.17 for the best trivial baseline), with richer classical features adding little beyond tuning."));

// Appendix
c.push(H1("Appendix A. Project files and how to run"));
c.push(table(["File", "Purpose"], [
  ["c/common.[ch]", "timing, file access, HSV histogram, Bhattacharyya distance"],
  ["c/threshold.c", "adaptive threshold (serial stage)"],
  ["c/seq.c", "single-threaded baseline"],
  ["c/arch_a.c", "Architecture A: data-parallel chunk workers (main design)"],
  ["c/arch_b.c", "Architecture B: reader/queue/workers/merger pipeline (comparison)"],
  ["c/scenes.[ch], c/scene_bench.c", "scene layer and its synthetic benchmark"],
  ["c/features.[ch], c/scene_api.c", "keyframe descriptors (parallel over shots); flat C entry point used by Python"],
  ["c/main.c", "command-line front end"],
  ["tools/gen_synth.py, evaluate.py, eval_rai.py, tune_scenes.py", "synthetic data, F1 scoring, RAI evaluation, early parameter search"],
  ["tools/scene_metrics.py, scene_lib.py, audit_metric.py, scene_cv.py, scene_compare.py", "scene metrics (incl. M_iou), ctypes access to the C scene layer, metric audit, leave-one-video-out study, DP vs spectral clustering"],
  ["tools/study.py, plot_study.py, benchmark.py", "main worker study, figure and table, supporting experiments"],
  ["tests/test_invariance.py", "thread-count and chunk-size invariance tests"],
], [3600, 6038]));
c.push(gap());
c.push(...code("Build and run (bash, with D:\\tools\\mingw64\\bin on PATH)", [
  "gcc -O2 -Wall -Wextra -pthread -o c/shotseg.exe c/main.c c/common.c c/threshold.c \\",
  "    c/seq.c c/arch_a.c c/arch_b.c c/scenes.c c/scene_bench.c c/features.c -lm",
  "",
  "c/shotseg.exe data/bbb_160x90.raw 160 90 a 8      # Architecture A, 8 workers",
  "                                       modes: seq | a | b | scenes",
  "python -m unittest tests.test_invariance -v       # correctness tests",
  "python tools/study.py && python tools/plot_study.py   # main study and figure",
]));
curList = "num3";
c.push(H1("Appendix B. References"));
c.push(NOTE("Reference details come from the project brief and recollection; verify each against the source before submission."));
[
  "Smeaton, A. F., Over, P., Doherty, A. R. (2010). Video shot boundary detection: Seven years of TRECVid activity. Computer Vision and Image Understanding, 114(4), 411-418.",
  "Video shot extraction on parallel architectures (2006). Springer LNCS chapter, DOI 10.1007/11946441_78 (author list to be confirmed).",
  "Liu, C., Wang, D., Zhu, J., Zhang, B. (2013). Learning a contextual multi-thread model for movie/TV scene segmentation. IEEE Transactions on Multimedia, 15(4), 884-897.",
  "Zhang, H. J., Kankanhalli, A., Smoliar, S. W. (1993). Automatic partitioning of full-motion video. Multimedia Systems, 1(1), 10-28.",
  "Nagasaka, A., Tanaka, Y. (1992). Automatic video indexing and full-video search for object appearances.",
  "Yeo, B.-L., Liu, B. (1995). Rapid scene analysis on compressed video. IEEE Trans. Circuits and Systems for Video Technology, 5(6).",
  "Bhattacharyya, A. (1943). On a measure of divergence between two statistical populations defined by their probability distributions. Bull. Calcutta Math. Soc., 35, 99-109.",
  "Kailath, T. (1967). The divergence and Bhattacharyya distance measures in signal selection. IEEE Trans. Communication Technology, 15(1), 52-60.",
  "Soucek, T., Lokoc, J. (2020). TransNet V2: An effective deep network architecture for fast shot transition detection. arXiv:2008.04838.",
  "Rao, A. et al. (2020). A local-to-global approach to multi-modal movie scene segmentation. CVPR.",
  "Baraldi, L., Grana, C., Cucchiara, R. (2015). Shot and scene detection via hierarchical clustering for re-using broadcast video. (RAI dataset).",
  "Baraldi, L., Grana, C., Cucchiara, R. (2015). A deep siamese network for scene detection in broadcast videos. ACM Multimedia (MM 15), arXiv:1510.08893. (source of the spectral-clustering baseline and the M_iou measure).",
  "Blender Foundation. Big Buck Bunny (2008), Creative Commons Attribution 3.0.",
].forEach((t) => c.push(NR(t)));

// ---------- document ------------------------------------------------------
const doc = new Document({
  creator: "Project group",
  title: "Multi-Threaded Design for Video Segmentation",
  styles: { default: { document: { run: { font: FONT, size: 21 } } } },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    ...["num1", "num2", "num3"].map((r) => ({ reference: r, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 340 } } } }] })),
  ] },
  sections: [{
    properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Multi-Threaded Design for Video Segmentation  |  page ", font: FONT, size: 16, color: "777777" }),
                 new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "777777" })] })] }) },
    children: c,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = R("Report_MultiThreaded_Video_Segmentation.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out, buf.length, "bytes");
});
