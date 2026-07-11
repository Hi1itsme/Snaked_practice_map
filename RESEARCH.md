# Snaked — Research Report

*Deep research run: 2026-07-08. 5 search angles, 25 sources fetched, 119 claims
extracted. **Caveat:** the adversarial verification pass hit the session usage
limit, so claims below are extracted from the cited sources but were not
independently double-checked. Sources are mostly primary (papers, official
repos, developer interviews); treat specific numbers as "per the source".*

---

## 1. Which snake mechanic? (design space)

**The genre splits on one axis: real-time vs turn-based.** Classic Snake's
constant forward motion makes it a reaction test; Snakebird's discrete
turn-based moves let players contemplate — that single choice determines
whether Snaked is an action game or a puzzle game
([taxonomy essay](https://joelthefox.github.io/2019-08-21-Snake-Puzzle-Games/)).
Everything already built in this project (pieces, solver, level JSON) presumes
the puzzle branch.

**The Snakebird formula** = discrete grid movement + gravity on the body +
growth by eating fruit ([Wikipedia](https://en.wikipedia.org/wiki/Snakebird_(video_game))).
Notable properties reported by the sources:

- It is *deep*: critics called Snakebird "the Dark Souls of puzzle games";
  Baba Is You's creator named it the single biggest influence on that game.
- It is *dangerous to onboard*: the original shipped only 53 levels, and the
  studio later shipped an entire standalone easier game (Snakebird Primer,
  70 levels) to fix the difficulty curve.
- The body itself is the puzzle: self-trapping after a fall is a core design
  element; growth is a "stationary move" that breaks player expectations
  ([Electron Dance analysis](http://www.electrondance.com/tail-meets-head/)).
- Multi-snake physics is a large complexity jump — introduce late and gently.
- There is a recognized hybrid lineage ("Snakeoban", Jack Lance's games,
  Snekburd, Growmi, etc.), so the design space between Snakebird and Sokoban
  is fertile and extensible — Snaked's height layers + ramps would be a novel
  entry (roughly "2.5D Snakebird without free gravity").

**Solver tractability is proven for the whole family.** An open-source C++
BFS solver solves all official Snakebird levels
([jsnell/snakebird-solver](https://github.com/jsnell/snakebird-solver)) —
i.e. full body-physics puzzles are machine-checkable, which the entire Snaked
pipeline depends on.

**Recommendation.** Commit to discrete, turn-based movement (Snakebird
family). Decide the two open sub-questions *empirically*: implement candidate
rule sets (with/without gravity along layers, with/without growth) as
alternative `moves()` functions in the solver and test the same hand-authored
pieces under each — the ruleset that yields the richest solution structure on
your existing pieces wins. Real-time classic Snake would invalidate the
solver/PCG pipeline and is not recommended.

---

## 2. AI / procedural level generation

**The strongest case study matches Snaked almost exactly.** For the
commercial grid puzzle *inbento* (piece-based, small hand-authored corpus)
([paper](https://www.researchgate.net/publication/352250878_Procedural_Level_Generation_with_Difficulty_Level_Estimation_for_Puzzle_Games)):

- Naive random generate-and-test made *solvable but boring* levels; an
  exhaustive BFS solver-assisted generator with filtering fixed it.
- Levels with the **fewest alternative solutions** were empirically the most
  interesting — duplicate-solution count became both a filter and a
  difficulty metric.
- A weighted combo of five solver-derived metrics, fitted against just **36
  hand-crafted shipped levels**, reproduced the designers' intended
  difficulty curve.
- They explicitly **deferred ML approaches (LSTM/GAN) because of training
  data cost** — the cold-start argument, from a team in Snaked's situation.

**Guaranteed-solvable construction beats post-hoc checking.** Two published
Sokoban techniques avoid the (PSPACE-complete) solvability check entirely:

- **Backward construction** (Taylor & Parberry,
  [paper](https://www.academia.edu/2600460/Procedural_Generation_of_Sokoban_Levels)):
  build the room from **3×3 template chunks** (directly analogous to Snaked's
  pieces), place goals, then search backward from the solved state — any
  state reachable in reverse is solvable forward. Their best difficulty
  metric was "box lines"; generation cost grows exponentially with box count
  (2 boxes: seconds; 5 boxes: ~26 h) → offline generation only.
- **Generation through simulated gameplay** (Kartal et al., MCTS,
  [paper](https://motion.cs.umn.edu/pub/SokobanMCTS/DataDrivenSokobanMCTS.pdf)):
  the generator *plays* while building, so every output is solvable; a cheap
  feature-based difficulty score correlated r²=0.91 with human-perceived
  difficulty; one anytime run emits a difficulty-sorted level sequence.

**Constraint solving (ASP)** can declaratively demand properties like
"minimum solution length ≥ N" and prunes invalid designs before completion
([Smith & Mateas](https://adamsmith.as/papers/tciaig-asp4pcg.pdf)) — but it
scaled poorly past ~21×21 grids in their experiments, so on Snaked's 22×40 it
fits *per-piece/per-region* generation, not whole levels.

**LLM generation works, with two hard lessons** (Todd et al., FDG 2023,
[paper](https://arxiv.org/pdf/2302.05817), [code](https://github.com/gdrtodd/lm-pcg)):

- Small models on small corpora fail: GPT-2 fine-tuned on 282 levels scored
  0.02–0.04; a GPT-3-class model on the *same* small corpus with flip/rotate
  augmentation reached 0.51 — comparable to GPT-2 trained on 438k levels.
  **Big pretrained model + augmentation rescues the small-corpus case** —
  and Snaked's orientation generator is exactly that augmentation.
- **Difficulty cannot be prompted for** (17% accuracy targeting solution
  length) — it must be measured post-hoc by the solver. All outputs were
  gated by an A* solver (rejection sampling), and the training corpus was
  solver-annotated first — precedent for Snaked's `ai_data` plan.

Related: a conditional VAE on ~198 match-3 levels worked at small scale
(validity 43.8%→51.4% when conditioned on bot-playtest stats, but difficulty
control stayed weak) ([paper](https://arxiv.org/html/2409.06349v2)); learned
solvability classifiers reached only 79% accuracy — useful as a *pre-filter*,
never as the sole validator
([paper](https://www.researchgate.net/publication/386403504_Predicting_Solvability_and_Difficulty_of_Sokoban_Puzzles)).
A user study found players equally engaged by generated and hand-crafted
Sokoban levels ([survey](https://www.researchgate.net/publication/333226463_Procedural_Puzzle_Generation_A_Survey)).

**Recommendation.** Phase 1: solver-guided generate-and-test that *composes
your existing pieces* onto the grid, filters by solvability, and scores by
solver metrics (the inbento recipe). Phase 2: consider backward-from-goal
construction inside pieces for guaranteed solvability. Phase 3 (optional):
LLM-driven whole-level generation with a large pretrained model, orientation
augmentation, and solver rejection — never prompt for difficulty, measure it.

---

## 3. Solver roadmap

Evidence-backed path from the current reachability-v0 to a full solver:

1. **Duplicate-state elimination is the single highest-leverage step** — a
   plain stringify-and-set transposition table cut one Sokoban search ~10×
   ([practitioner writeup](https://healeycodes.com/building-and-solving-sokoban)).
   (v0 already has a visited set; keep it central when body state arrives.)
2. **Use BFS, not A\*, for body-physics rules.** The Snakebird solver author
   found no viable admissible heuristic exists for body puzzles
   ([blog](https://www.snellman.net/blog/archive/2018-07-23-optimizing-breadth-first-search/)).
   A* + Minimum-Matching heuristics + deadlock pruning apply only if Snaked
   adds Sokoban-style box pushing
   ([Sokoban wiki](http://sokobano.de/wiki/index.php?title=Solver),
   [YASS notes](http://sokobano.de/wiki/index.php?title=Sokoban_solver_%22scribbles%22_by_Brian_Damgaard_about_the_YASS_solver):
   deadlock+corral pruning gave ~9× on benchmarks).
3. **Cheap wins for a Python solver** (from a pure-Python Snakebird solver,
   [apocalyptech/snakebirdsolver](https://github.com/apocalyptech/snakebirdsolver)):
   PyPy roughly halves runtime; prune on lose-conditions (e.g. losing a
   pushable object); per-level move caps. Warning from the same project:
   without good state encoding, memory explodes (~1 GB/min).
4. **If levels get genuinely hard**, the scaling techniques are documented:
   canonicalize states (drop snake/object identity: ~10× reduction),
   compress visited-state storage (8–10 bytes/state down to ~0.7 *bits*),
   successor generation is cheap (1–2 µs) — dedup dominates cost
   ([jsnell](https://github.com/jsnell/snakebird-solver)).
5. **Difficulty metrics from solver output** (for `training_examples.json`):
   solution length, duplicate-solution count (inbento), search effort,
   box-lines analog for pushes. Static board features alone are documented
   as weak difficulty predictors.

---

## 4. Automated playtesting agents (later-stage)

Industry evidence (mobile puzzle game *Lily's Garden*, validated against
~900k real players) says RL agents work as *difficulty probes* — with
counterintuitive rules
([completion-rate paper](https://arxiv.org/pdf/2306.14626),
[difficulty-prediction paper](https://arxiv.org/html/2401.17436v1)):

- The strongest predictor of human completion rate was the move count of the
  agent's **best ~5% of runs**, not average performance.
- Agents **don't need human-level skill** — relative per-level differences
  correlate with human differences.
- A **generalist agent trained once** on a level curriculum ranked unseen
  levels *better* than per-level fine-tuned agents; the overtrained agent was
  worse than random (memorization).
- Agent-derived features were ~5–6× more predictive than static level
  attributes.

**Recommendation:** solver metrics first (free — the solver already runs);
RL probes only if solver-metric difficulty prediction proves insufficient
once real players exist.

---

## 5. Puzzle design theory (for level sequencing + piece families)

- **Teach wordlessly, one mechanic at a time.** Snakebird's first level
  teaches movement, the win condition, and growth with zero text. Its abrupt
  multi-snake introduction is cited as the curve's failure point.
- **Plan the easy on-ramp from the start** — the cost of not doing so was an
  entire second game (Primer).
- **Difficulty curves can be engineered numerically**: fit solver metrics to
  a small set of hand-ranked levels (inbento's 36), then sort/sequence
  generated content; MCTS-style anytime generation naturally emits levels in
  rising difficulty order.
- **Piece families = motifs**: template/chunk reuse is standard in the
  literature (Taylor & Parberry's 3×3 templates; survey flags composing
  larger puzzles from smaller elements as the way to scale generation).
  Snaked's family/variation/orientation schema is ahead of the curve here.

---

## Decision list (proposed)

1. **Mechanic**: discrete turn-based snake; A/B-test gravity + growth
   variants through the solver on existing pieces before committing.
2. **Generator**: piece-composition + solver rejection + solver-metric
   difficulty scoring (inbento recipe). ML/LLM only as a later layer, always
   solver-gated, using orientations as augmentation.
3. **Solver**: evolve v0 to full body simulation with BFS + visited-set;
   PyPy if slow; jsnell's repo as the scaling reference.
4. **Difficulty**: hand-rank ~30–40 authored levels, fit solver metrics to
   them, use the fitted score everywhere.
5. **Progression**: one new mechanic per piece family; wordless tutorial
   levels; deliberately easy first world.

## Sources (25 fetched)

Primary papers/repos: [Kartal MCTS](https://motion.cs.umn.edu/pub/SokobanMCTS/DataDrivenSokobanMCTS.pdf) ·
[Taylor & Parberry](https://www.academia.edu/2600460/Procedural_Generation_of_Sokoban_Levels) ·
[ASP for PCG](https://adamsmith.as/papers/tciaig-asp4pcg.pdf) ·
[PCG survey](https://www.researchgate.net/publication/333226463_Procedural_Puzzle_Generation_A_Survey) ·
[inbento difficulty](https://www.researchgate.net/publication/352250878_Procedural_Level_Generation_with_Difficulty_Level_Estimation_for_Puzzle_Games) ·
[LLM level gen (FDG'23)](https://arxiv.org/pdf/2302.05817) · [lm-pcg](https://github.com/gdrtodd/lm-pcg) ·
[match-3 CVAE](https://arxiv.org/html/2409.06349v2) · [RL completion rate](https://arxiv.org/pdf/2306.14626) ·
[RL difficulty prediction](https://arxiv.org/html/2401.17436v1) ·
[solvability CNN](https://www.researchgate.net/publication/386403504_Predicting_Solvability_and_Difficulty_of_Sokoban_Puzzles) ·
[jsnell solver](https://github.com/jsnell/snakebird-solver) ·
[apocalyptech solver](https://github.com/apocalyptech/snakebirdsolver) ·
[Sokoban wiki: Solver](http://sokobano.de/wiki/index.php?title=Solver) ·
[YASS scribbles](http://sokobano.de/wiki/index.php?title=Sokoban_solver_%22scribbles%22_by_Brian_Damgaard_about_the_YASS_solver)

Secondary/design: [snake-puzzle taxonomy](https://joelthefox.github.io/2019-08-21-Snake-Puzzle-Games/) ·
[Snakebird history (Game Developer)](https://www.gamedeveloper.com/production/snakebird-development-images-and-history) ·
[Electron Dance: Tail Meets Head](http://www.electrondance.com/tail-meets-head/) ·
[Snakebird (Wikipedia)](https://en.wikipedia.org/wiki/Snakebird_(video_game)) ·
[Sokoban (Wikipedia)](https://en.wikipedia.org/wiki/Sokoban) ·
[Thinky Games](https://thinkygames.com/games/snakebird/similar/) ·
[Building & solving Sokoban](https://healeycodes.com/building-and-solving-sokoban) ·
[Optimizing BFS](https://www.snellman.net/blog/archive/2018-07-23-optimizing-breadth-first-search/)
