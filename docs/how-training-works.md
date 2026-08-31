# How the training works, in plain language

This page is the non-specialist tour of what this repository does. It answers
three questions in order:

1. **How does the training actually work?**
2. **What did we change after the first training run, and why?**
3. **Why are we training a second time?**

Everything here is also written down somewhere more formal —
[design.md](design.md) for the reasoning, [runbooks/train.md](runbooks/train.md)
for the exact commands, [model-card.md](model-card.md) for the measurements.
This page is the version you read first.

---

## Part 1 — How the training works

### What we are building, and what it is for

kubeagent can look at a broken Kubernetes cluster and work out, by fixed rules,
what is probably wrong. That deterministic part is already good. What it cannot
do by rules alone is *judge* — look at a shortlist of possible causes and say
"this one, because of this evidence."

kubeagent v1.23.0 added a mode for exactly that (`--investigate` in local
verdict mode). kubeagent gathers all the evidence itself, then asks a language
model one question, once: **which of these candidates is the real cause?** The
model never chooses what to read and never touches the cluster. It only
adjudicates.

Today you can point that at any model you like. This repository trains a small
one *specifically* for that job, so it can run on a normal CPU with no GPU, no
internet, and no API key.

The deliverable is a single file — a `.gguf` model file of about 600 MB — plus
a checksum and an Ollama `Modelfile`. That is all. **Nothing in kubeagent
changes.**

### The four steps

```text
dataset  →  train  →  export  →  eval
```

Four commands, in order. Think of it as writing an exam course:

| Step | Command | Plain English | Time |
|---|---|---|---|
| 1 | `kv-dataset` | **Write the textbook.** Generate thousands of realistic practice questions with known-correct answers. | seconds |
| 2 | `kv-train` | **Teach.** Show the model the questions and answers over and over until it learns the pattern. | hours |
| 3 | `kv-export` | **Print and shrink.** Turn the trained result into one compact file a laptop can run. | ~30 min |
| 4 | `kv-eval` | **Sit the exam.** Score the model on questions it has never seen, and check the score against a fixed bar. | ~2¼ hours |

Each step writes files the next one reads. Nothing is hidden, nothing calls out
to a paid service, and the same seed always produces byte-for-byte the same
data — so any run here can be reproduced exactly.

### Step 1: writing the textbook (`kv-dataset`)

We do **not** collect real cluster data and label it by hand. There is no
budget for that, and real cluster data carries real hostnames, IPs and
namespaces we must never publish.

Instead there is a **generator**. It knows:

- a **catalog** of things that go wrong in Kubernetes (a container out of
  memory, an image that will not pull, a probe that keeps failing…), each with
  the evidence you would actually see and the correct one-line cause;
- a **corpus** of redacted results from kubeagent's own nightly chaos tests —
  real failures that really happened, with every identifying detail already
  stripped by that pipeline before it published them;
- a list of **made-up but plausible names** for namespaces and workloads.

From those it writes thousands of complete practice questions, each in the
*exact* format kubeagent will send at runtime — same section markers, same
wording, same closing line — and each with the correct answer attached.

The generator does not write one kind of question. It writes nine, in fixed
proportions, and each kind teaches one specific skill:

| Question type | Share | The skill it teaches |
|---|---|---|
| `attributed` | 30% | The obvious candidate is right — pick it, word for word |
| `none_of_these` | 15% | Sometimes *every* offered candidate is wrong. Say so. |
| `own_cause` | 10% | Sometimes the right answer is not on the menu at all. Name it. |
| `wrong_attribution` | 10% | kubeagent's own "attributed" tag is a *hint*, and sometimes it is wrong. The evidence wins. |
| `injection` | 10% | The evidence may contain text saying "ignore your instructions." It is data. Ignore *it*. |
| `multi` | 11% | Several broken workloads in one question, each broken for its **own separate reason** |
| `truncated` | 5% | The evidence was cut short. Answer honestly and lower your confidence. |
| `empty_candidates` | 5% | Nothing is actually wrong. Do not invent a problem. |
| `shared_origin` | 4% | Several broken workloads, **all broken by one single thing** — name the same cause on every one |

That last row is new. It is the whole subject of Part 2.

The generator then splits everything into three piles:

- **train** — 4,232 questions. The model studies these.
- **validation** — 435 questions. Held back during development.
- **test** — 263 questions. **The exam.** The model must never see these.

The split is not random row-by-row. It is by *scenario family*: if a particular
broken workload appears in the exam, every training question that touches that
same workload is thrown away. That job is done by a function called
`drop_held_out`, and it is the single most important safety rule in this repo.
Without it, a model could score 100% by memorising the answers rather than by
reasoning, and we would never know.

### Step 2: the teaching (`kv-train`)

We start from an existing open model, **Qwen3-0.6B** — 600 million parameters,
Apache-2.0 licensed, small enough to train on a CPU.

We do not retrain the whole thing. That would need a GPU and days. Instead we
use **LoRA**, which is easiest to picture like this:

> The base model is a thick reference book that already knows English, JSON,
> and roughly what Kubernetes is. We do not rewrite the book. We clip a thin
> pad of sticky notes onto specific pages, and only the sticky notes get
> written on during training. At the end we photocopy the book *with* the notes
> in place, and that copy is what ships.

The sticky-note pad is tiny compared to the book, which is exactly why this
fits on a CPU.

The training loop itself is deliberately about forty lines of plain code, with
no framework doing anything behind our backs
([train/train.py](../src/kubeagent_verdict/train/train.py)). For each question
it shows the model the prompt, lets it try to write the answer, measures how
wrong it was ("loss"), and nudges the sticky notes slightly toward being less
wrong. Then the next question. Then the next.

The recipe is pinned in [train/config.py](../src/kubeagent_verdict/train/config.py)
and changing any of it is a deliberate, committed decision — because two
training runs are only comparable if they used the same recipe:

| Setting | Value | What it means |
|---|---|---|
| base | `Qwen/Qwen3-0.6B` | the reference book |
| epochs | 2 | it reads the whole textbook twice |
| learning rate | 0.0002 | how big a nudge each correction gives |
| grad_accum | 16 | it collects 16 questions' worth of corrections before nudging |
| max_seq_len | 4096 | the longest question it will accept |
| seed | 17 | fixed, so the shuffle is the same every run |
| LoRA rank | 16 | how many sticky notes |

Two epochs over 4,232 questions, nudging once per 16 questions, works out to
about **529 nudges** ("optimizer steps") in a run. On a 32-core CPU box that
takes several hours, and the program deliberately prints *nothing at all* until
it finishes — so "no output" during a run is normal, not a hang. The only
progress signal is that the process is still alive.

### Step 3: printing it (`kv-export`)

Training leaves the sticky-note pad in one folder. Export:

1. merges the notes into a copy of the base model,
2. converts it to GGUF, the format CPU runtimes read,
3. **quantizes** it to Q8_0 — storing each number in 8 bits instead of 32,
   which makes the file roughly four times smaller and four times faster, at a
   negligible cost in quality,
4. loads the finished file once to prove it actually runs.

Out comes `kubeagent-verdict-0.6b-q8_0.gguf` plus its checksum. If the load
check fails, nothing produced is trusted.

### Step 4: the exam (`kv-eval`)

We serve the finished model locally and ask it all 263 test questions, then
score every answer automatically.

The 263 questions are not one exam — they are thirteen, and several are traps
built specifically to catch a model that is cheating rather than reasoning:

| Slice | Rows | What it catches |
|---|---|---|
| `positional_probe` | 19 | A model that always picks the **first** candidate. The right answer is placed last. |
| `misattribution_probe` | 19 | A model that always trusts the `attributed` **tag**. The tag is deliberately on a wrong candidate. |
| `multi_misattribution_probe` | 19 | The same trap, but with two workloads at once. |
| `shared_origin_probe` | 10 | A model that always says workloads fail **independently**. Here they do not. |
| `shared_origin_decoy_probe` | 10 | The mirror of the row above, from the *same* ten scenarios: same workloads, same candidate menus, same order. Only the reads differ — here the cluster-wide thing is **healthy**, so the answer really is separate causes. A model that learned "say shared" scores zero. |
| `contradiction_probe` | 19 | Evidence that contradicts itself. |
| the other 7 slices | 167 | Ordinary competence across the nine question types |

A model that beats the untuned base model on every number is still not good
enough. **Six things decide whether a model may be released**, and they exist
because each one caught a real cheat that had already fooled us:

1. **Contract validity = 1.0.** Every answer must be valid JSON in the exact
   required shape. No exceptions.
2. **Decoy rate low on all three trap slices.** This is what proves it is
   reading evidence rather than following position or tags.
3. **Length gap ≤ 0.15.** In our catalog the correct cause happens to be the
   *longer* sentence 15 times out of 19. So a model that simply always picks
   the longest option scores well without reading anything. This gate measures
   the difference between "cases where length helps" and "cases where length
   misleads" — if it is wide, the model is counting words and the decoy rate
   above means nothing.
4. **Overconfidence rate.** Of the causes it got *wrong*, how many did it still
   mark `high` confidence? A model that is confidently wrong is worse than one
   that says `low`.
5. **Shared origin vs. coincidence — read as a pair.** Two numbers:
   `separate_reasons_rate` (it wrongly called one shared failure several
   independent ones) and `false_shared_rate` (it wrongly blamed one cause for
   genuinely unrelated failures). Either one alone is trivially cheatable, and
   the cheat for one is the failure mode of the other. **They must be read
   together.** The two now have a matched pair of slices to be measured on:
   `shared_origin_probe` for the first, `shared_origin_decoy_probe` for the
   second, built from the same ten scenarios so that no answering habit can win
   both.
6. **Suggestion echo = 0.** Every prompt contains kubeagent's own generic
   "suggested fix" line. Handing that back is the cheapest wrong answer
   available — fluent, on-topic, and already in the context. Zero tolerance.

---

## Part 2 — What we changed after the first training, and why

### What happened

The first retrain (the run of 30 August, scored into `out/eval-retrain-0830`)
improved almost everything and **failed decider 5 outright.**

On all ten `shared_origin_probe` rows — where two to four workloads are broken
by one single upstream thing — the model answered:

> "N workloads are failing for separate reasons"

and then gave each workload a *different, wrong* cause. Ten out of ten. Not
once did it notice the common cause.

Here is the slice, measured, against the shipped v0.1.0 model on the same
questions:

| `shared_origin_probe` (10 rows) | v0.1.0 | 30 Aug retrain | direction |
|---|---|---|---|
| answered in valid JSON | 1.0 | 1.0 | unchanged |
| named the correct shared cause | 0.4333 | **0.1667** | worse |
| fell for the decoy candidate | 0.8 | **1.0** | worse |
| said "separate reasons" (wrong) | 1.0 | **1.0** | still total |
| confidently wrong | 0.4583 (of 8) | **0.5 (of 10)** | worse |

Everything *else* got better in that run — contract validity 1.0, overall cause
accuracy 0.8531 → 0.9572, suggestion echo down to 0.0, length gap met at
+0.0000. Which is what made the failure worth taking seriously rather than
shrugging at: the model was clearly learning well. It was learning the wrong
thing.

A note on reading small slices honestly: this slice is only ten rows, so one
row is 0.1. The same shipped v0.1.0 model, served twice with different settings,
scored 1.0 and 0.9 on "separate reasons" in two different runs. Ten rows is
enough to see a total failure. It is not enough to argue about a 0.1 difference.

### Why it happened

We went and looked instead of guessing, and found two separate causes.

**Cause 1: we were examining a skill we had never taught.**

The `shared_origin_probe` exam slice existed. The matching *lesson* did not.
The training mix had eight question types and not one of them showed several
workloads sharing a cause. Worse, the `multi` type — 15% of the curriculum,
825 generated and 554 surviving into the training pile — showed the opposite
shape over and over, and always summarised it with the exact sentence:

> "N workloads are failing for separate reasons"

So on 825 examples the model was told that several broken workloads means
several separate reasons, and on **zero** examples was it ever shown otherwise.
It did not misbehave. It learned precisely what we taught it, and we then
tested it on the opposite. The 1.0 failure rate is what perfect learning of a
wrong lesson looks like.

**Cause 2: there was a giveaway, and fixing cause 1 alone would have taught the
giveaway instead.**

This is the subtler one and it is the reason the fix took thought rather than
five minutes.

A shared-origin question puts one **cluster-wide read** at the top — the
evidence about the broken shared component. The old `multi` questions had no
cluster-wide read at all; every read was about one specific workload.

So if we had simply added shared-origin questions, the model would have had a
perfect shortcut available: **"is there a cluster-wide read at the top? then
say shared. otherwise say separate."** It would have scored beautifully on the
exam without ever reading the evidence — and we would have shipped it believing
we had taught reasoning.

### What we changed

Three changes, all in the *textbook*. **No model code changed, and the exam did
not change at all.**

**Change 1 — a new lesson type, from its own private scenarios.**

`shared_origin` is now 4% of the curriculum: several workloads, one upstream
cause, the same answer on every row.

The obvious way to build it would have been to reuse the six scenarios the exam
already uses, with different names drawn. That would have been a trap. The
safety function `drop_held_out` compares *identities*, not text — so those
questions would have looked clean to it while teaching the model the exam's
literal answer strings word for word. We would have got a perfect score and a
completely worthless one.

So the training questions draw from a **separate, private pool of four
scenarios** that the exam never uses:

| Pool | Scenarios | Used by |
|---|---|---|
| exam-only | CoreDNS down · node NotReady · storage provisioner down · registry unreachable · node disk pressure · default-deny NetworkPolicy | `shared_origin_probe` only |
| train-only | expired internal CA · degraded kube-proxy · deleted shared ConfigMap · shared dependency scaled to zero | `shared_origin` only |

The two pools share no scenario key **and no answer sentence**, and a test
asserts both. The model learns the *shape* of shared-origin reasoning; it has
never seen a single one of the exam's answers.

**Change 2 — a counter-example that kills the giveaway.**

Roughly a third of the `multi` questions now carry **the very same cluster-wide
read** the shared-origin questions carry — with the component shown **healthy**.
Same read label. Same position. Healthy contents. And the correct answer on
those questions is still "separate reasons."

Now "is there a cluster-wide read?" no longer settles the answer. Among the
questions that have one, the training pile holds 220 shared against 133
separate — a **62 / 38 lean**, where before the change it was 100 / 0. Guessing
from the cue alone now buys 62%, not 100%; the rest has to come from *reading
whether the shared component is actually broken*, which is the skill we wanted.

Be precise about that number, because it is weaker than the one we designed
for. The generator emits the two classes close to even — 220 against 202, a
48 / 52 split. The `drop_held_out` safety filter then removes about a third of
the counter-examples and **none** of the positives, because a `multi` question
is built from two to four ordinary catalog entries (any one of which may
collide with an exam question and take the whole row with it), while a
`shared_origin` question is built from the private train-only pool, which the
exam never touches. Even balance going in, 62 / 38 coming out. See "What this
fix does not do" below.

**Change 3 — we paid for it out of `multi`, not by growing the mix.**

`multi` went 15% → 11%; `shared_origin` took the 4%.

This was deliberate and it has a cost. Decider 5 has two halves that pull in
opposite directions: teach too little shared-origin and the model calls
everything independent (the failure we had); teach too much and the model
starts blaming one cause for genuinely unrelated failures — which is the *same
decider*, failing from the other side. `false_shared_rate` is currently a clean
0.0 and we are not willing to trade one failure for its mirror. So
`shared_origin` is deliberately the smaller of the two, and a test enforces
that `multi` stays larger.

### What the change did to the data

| | before | after |
|---|---|---|
| `multi` questions | 554 | 404 |
| `shared_origin` questions | 0 | 220 |
| training questions total | 4,155 | 4,232 |
| validation | 432 | 435 |
| **exam (test.jsonl)** | **253** | **253 — byte-identical** |

That last row is the important one. We hashed the exam file on both versions of
the code and got the same value, `f565e61b…`, 253 rows. **The exam did not
move.** That is what makes the old score and the new score comparable at all,
and it is the difference between a fix and moving the goalposts.

(The exam has since grown to 263 questions, deliberately and by *appending* ten
new ones — the last section of this part explains why, and why appending is not
the same as moving. The run described here is still scored against the frozen
253, whose bytes the append did not touch.)

### What this fix does not do

Two things are worth writing down plainly, because both are easy to miss and
both would let us claim more than we have earned.

**One — the counter-examples are thinner than intended.** The goal was that
"was there a cluster-wide read?" should be a coin flip: useless as a shortcut.
The generator does produce them near evenly — 220 shared against 202 separate,
a 48 / 52 split. But the safety filter that keeps exam questions out of the
training pile removes about a third of the counter-examples and none of the
shared ones, for the structural reason described above, and what the model
actually reads is **220 shared against 133 separate — a 62 / 38 lean.**

That is still an enormous improvement on the 100 / 0 it saw before, and the
lean is spread evenly rather than hiding in one place. Every one of the four
cluster-wide reads used in training appears on both answers, at roughly the
same ratio:

| the cluster-wide read shown | answer: one shared cause | answer: separate causes |
|---|---|---|
| a node's condition | 55 | 33 |
| a shared Deployment | 55 | 35 |
| a shared ConfigMap | 55 | 33 |
| a shared Secret | 55 | 32 |

So no single read is a giveaway. But 62 / 38 is a lean, not a coin flip — and
the automated check that was supposed to guard this counted the questions
**before** the safety filter ran, where the split is 48 / 52 and passes. It
was measuring the pile we generate, not the pile the model reads.

That check has now been split in two, because they were always two different
claims. One measures what the generator emits and still demands a coin flip,
since that part is entirely under our control. The other measures the pile
that actually reaches the model and demands only that the smaller side stay
above 30% — which is what is true today, and which still fails loudly at the
0% this whole change exists to end. The second number is a narrowed claim, not
a satisfied one: making the trained pile genuinely even means generating more
counter-examples, and that changes the training questions, so it waits until
the run in flight has been scored.

**Two — the exam, as it stood, could not catch this particular shortcut.** This
is the more important one, and it is a limitation of the test, not of the
training. It has since been closed; the closure is described at the end of this
section, and the numbers below are about the 253-question exam as it was.

The exam has ten shared-origin questions. Seven of them show a cluster-wide
read whose label appears in **none** of the other 243 questions — a CoreDNS
deployment, a StorageClass, a NetworkPolicy, a cluster-wide event query. So a
model that never read a word of the evidence, and simply answered "one shared
cause" whenever it saw one of those four labels and "separate causes"
otherwise, would get those seven right *and* stay right on all 243 others.
It would pass both halves of the decider that is supposed to catch exactly
this.

The remaining three shared-origin questions use a node read, which also shows
up in 29 questions whose correct answer is "separate causes". Only those three
force the model to actually look. Three questions is not a test.

This does not undermine the fix — the training data now teaches the right
thing, and that is what we changed. It means the **scoreboard** could not tell
"learned to read the evidence" apart from "learned which label goes with which
answer". Closing it needs exam questions where a distinctive cluster-wide read
is present and the correct answer is still "separate causes" — the same
counter-example shape, on the exam side.

**That change has since been made, and it is why the exam is now 263 questions
rather than 253.** The new slice, `shared_origin_decoy_probe`, is built from the
same ten scenarios as `shared_origin_probe` and rendered from the same random
seeds, so the two are a matched pair: the same workloads, the same candidate
lists in the same order, the same evidence labels. The only thing that differs
is what the reads *say* — in the new slice the cluster-wide thing is healthy,
and each workload really is broken for its own local reason. The label a model
might have been keying on is now present in both worlds, so keying on it scores
100% on one slice and 0% on the other. The shortcut buys nothing.

Two honest limits on that, written down for the same reason as everything else
in this section. First, the new slice **could not have failed the model this
part is about** — a model that answers "separate causes" to everything aces it.
It is a trap for the model trained *next*, and what it buys is that the pair is
uncheatable in both directions from here on. Second, a decoy question's correct
confidence values are the ones already printed in the prompt, so the
"confidence carried" measure is weaker on this slice than elsewhere and should
not be read as evidence of judgement there.

The exam file was **appended to, never rewritten.** Its first 253 lines are
byte-identical to the file the run in flight is being scored against, and the
training and validation files regenerate unchanged, byte for byte. So this did
not move the goalposts mid-measurement: the run in flight is still judged on
its own frozen 253, and the 263-question exam is what the next model faces.

---

## Part 3 — Why we are training again

Because a change to the textbook does nothing until the model reads it.

The 30 August model was trained on a curriculum with no shared-origin lesson in
it. Nothing we can do to a dataset changes weights that already exist. The only
way to find out whether the new lesson works is to run the whole course again
from the base model and re-sit the same exam.

The rerun is the same recipe as before — same seed, same base model, same two
epochs, same everything — against the corrected textbook. That is on purpose:
if two runs differ in *two* ways you cannot attribute the difference to either.
One variable changed, and it is the curriculum.

### About the "negative control" we skipped

The runbook says that when the dataset or the exam changes, you must first
serve the *previous* model against the *new* exam and confirm it still fails —
because an exam that cannot fail the model it replaced is not a fix, it is a
softer exam.

Here the exam did not change; only the textbook did, and we proved the exam
file is byte-identical. And the previous model has already been run against
exactly these bytes: that is `out/eval-retrain-0830`, scoring `separate reasons`
1.0 on ten of ten. **That run is the control.** Re-running it would spend two
and a quarter hours reproducing identical numbers from an identical model over
identical bytes. It was skipped deliberately, and it is written down here rather
than passed over in silence.

### What counts as success, decided in advance

Written now, before the score exists, so it cannot be rationalised afterwards:

- **Success:** `separate_reasons_rate` drops well below 1.0 **and**
  `false_shared_rate` stays at or near 0.0 (bar: at most 1 of 19), **and**
  nothing else on the six deciders regresses.
- **Failure:** `separate_reasons_rate` stays at 1.0. Then the lesson did not
  take, and the honest response is to say so — not to look for a gentler
  measure.
- **Also failure:** `separate_reasons_rate` goes to 0.0 while
  `false_shared_rate` climbs. That is not a fix; that is the model learning to
  say "shared" to everything. It is the exact mirror failure decider 5 exists to
  catch, which is why those two numbers are never read apart.

These three are the bar for the run in flight, and they are judged on the
frozen 253-question exam — the `false_shared_rate` bar above is 19 rows of
`multi_misattribution_probe`, because that is the only place the measure had a
denominator when this was written. They are left exactly as written; a
pre-registered bar that gets edited once the score exists is not a bar.

For the run **after** this one, the same measure gets a second and much harder
denominator: the ten `shared_origin_decoy_probe` questions, where the tempting
"one shared cause" answer is present, plausible, and wrong. The bar there is
tighter for a reason — those ten are the mirror image of the ten the model is
currently failing, so passing both is the only result that can be read as
having learned to look.

### Where this currently stands

- Curriculum change: **done**, merged, 287 tests green at the time.
- Dataset regenerated and verified byte-identical on the training machine:
  **done**.
- Exam extension (`shared_origin_decoy_probe`, +10 questions): **done**, 303
  tests green, appended so the frozen 253 the run in flight is judged on did
  not move a byte. It applies to the *next* run, not this one.
- Training run: **in progress** on a CPU-only box, ~529 nudges, several hours,
  silent by design.
- Export to a `.gguf`: **not started**, and deliberately gated — it needs
  separate authorisation because it is what overwrites a shipped artifact.
- Scoring against the six deciders: **not started**, needs the export first.
- Publishing: nothing is published, and no claim about this model should be
  made anywhere until the exam is scored.

---

## Small glossary

| Term | Plain meaning |
|---|---|
| **base model** | The existing open model we start from. We did not build it. |
| **LoRA** | Training only a small add-on layer instead of the whole model, so a CPU can do it. |
| **adapter** | The trained add-on. Useless alone; must be merged into the base. |
| **GGUF** | The file format CPU runtimes (Ollama, llama.cpp) read. |
| **quantization** | Storing the model's numbers in fewer bits. Smaller and faster, slightly less precise. |
| **epoch** | One complete pass through the training questions. We do two. |
| **loss** | A number for how wrong an answer was. Training pushes it down. |
| **held out** | Deliberately kept out of training so it can be a fair exam. |
| **contamination** | An exam question the model already saw while studying. Makes its score meaningless. |
| **decoy** | A wrong candidate placed in the question on purpose, to see if the model bites. |
| **negative control** | Checking that a new exam actually *fails* the old model — proof the exam got harder, not that the model got better. |
| **slice** | One named group of exam questions, scored separately. |
| **decider** | One of the six numbers that must hold before a model may be released. |
