# What kubeagent does with the shared fixture

These files are what kubeagent v1.24.0 does with `tests/fixtures/gather_fixture.yaml`.
One run of the Go harness `contract/capture/kv_capture_test.go.txt` wrote them. Its
header gives the seven steps of that run. Do not edit them by hand: re-run the
harness.

Each dump holds what one stage decides. When the Python side differs, the first
dump that differs names the stage that went wrong.

| # | File | Stage |
|---|---|---|
| 0 | `00-fixture.json` | The fixture, as Go loaded it |
| 1 | `01-order.txt` | Workload order (`Prioritize`, `flaggedScope`) |
| 2 | `02-events.txt` | Events reads |
| 3 | `03-candidates.txt` | The candidate walk: read, deduped, or skipped, and why |
| 4 | `04-nodes.txt` | Node describes |
| 5 | `05-pvcs.txt` | PVC describes |
| 6 | `06-logs.txt` | Log reads |
| 7 | `07-trail.txt` | The read trail |
| 8 | `08-bundle.txt` | The evidence bundle |
| 9 | `09-decide.txt` | What the rules see, and `Decide` per workload |
| 10 | `10-prompt.txt` | The cluster block, the shared-cause lines and the full prompt |

## Dump 0

`00-fixture.json` is the YAML file turned into JSON by `sigs.k8s.io/yaml`
(`YAMLToJSON`), then indented with two spaces, plus one final newline. The keys
of every object are sorted, because Go's JSON encoder sorts map keys. A key the
YAML leaves out is left out here too. Compare it with your own load **as parsed
values** (`json.loads` against your YAML load), not as bytes. That catches the
two YAML loaders reading one value differently.

## Dumps 1-10: the rules

- Plain UTF-8 text. One record per line. Every line, the last one included, ends
  in one `\n`. There is no `\r` anywhere.
- A record is fields joined by one TAB (`\t`). The first field names the record
  type. Each record type has a fixed number of fields, given below.
- An empty value is an empty field: nothing between two tabs, or nothing after
  the last tab. So a line can end in a tab.
- No field holds a tab, `\n` or `\r`. The harness fails if one would.
- A number is plain decimal with no padding. A boolean is `true` or `false`.
- Row numbers and read numbers count from 1.
- Nothing is printed in map order. Where a group comes from a map, the order is
  given below (always a byte-wise sort of the key).

### Blocks

A value that can hold a newline (a read's text, the bundle, the prompt) is a
block:

```
block\t<name>\t<N>\n
<the N bytes of the value>\n
```

`<N>` is the value's length in **bytes** (UTF-8), not characters. The value is
written raw, with nothing escaped, and one `\n` always follows it, even when the
value already ends in `\n`. To read a block: read the header line, take exactly
N bytes, then check that the next byte is `\n` and skip it.

A block's name is `content`, `bundle` or `prompt`. A `content` block is one
read's section body as the bundle holds it: the read's text after
`capContent` (cut to 4096 bytes), with trailing `\n`s removed
(`investigate/gather.go:163-169`).

## 01-order.txt

The workloads the report shows, in report order (`inventory.Prioritize`, the
scan's order), then counts, then the workloads it drops.

```
row\t<row>\t<namespace>\t<name>\t<kind>\t<priority>\t<scope>
hidden_restarts\t<n>
hidden_cron\t<n>
dropped\t<namespace>\t<name>\t<kind>
```

- `row`: 7 fields, one per shown workload. `<row>` is its 1-based place in
  report order. `<priority>` is `Workload.Priority` (2 a problem, 3 a restart,
  4 a CronJob). `<scope>` is `scoped` for the workloads `flaggedScope` keeps (the
  first 10 flagged ones), else `unscoped`.
- `hidden_restarts` and `hidden_cron`: 2 fields each, once each, from
  `Result.HiddenRestarts` and `Result.HiddenCron`.
- `dropped`: 4 fields, one per fixture workload that has no row, sorted by
  (namespace, name, kind).

Every later dump names a workload by this `<row>`.

## 02-events.txt

One entry per events read, in trail order.

```
events\t<read>\t<namespace>\t<pod>\t<status>\t<count>\t<message>
event\t<reason>\t<message>\t<count>
block\tcontent\t<N>
```

- `events`: 7 fields. `<read>` is the read's 1-based place in the trail.
  `<pod>` is the object whose events were listed (the first finding's pod, else
  the workload name). `<status>` is `ok` or `failed`.
  - `ok`: `<count>` is how many events came back, and `<message>` is empty.
  - `failed`: `<count>` is empty, and `<message>` is the refusal as the rules see
    it (`Reads.Failed["events/<namespace>/<pod>"]`).
- `event`: 4 fields, one per event that came back, in the order the API
  returned them. The reason and message are **raw**: as the API holds them,
  before `formatEvents` sanitizes them and redacts addresses. The block shows
  the redacted text. `<count>` is the event's `count`.
- Then the read's `content` block.

## 03-candidates.txt

First the down nodes the scan found, in `ClusterHealth.DownNodes` order (the node
list's order, by name):

```
down\t<node>\t<reason>
```

3 fields. `<reason>` is `NotReady` or `no kubelet lease`.

Then, for each scoped workload in row order, a `workload` record and one
`candidate` record per entry of its root-cause trace, in trace order:

```
workload\t<row>\t<namespace>\t<name>\t<root_cause>\t<confidence>
candidate\t<kind>\t<object>\t<verdict>\t<action>\t<ref>\t<cause>\t<reason>
```

- `workload`: 6 fields. `<root_cause>` is `Workload.RootCause` and
  `<confidence>` is `Workload.RootCauseConfidence`. Both are empty when nothing
  was attributed.
- `candidate`: 8 fields. `<kind>` is `node`, `pvc` or `registry`. `<object>` is
  the node, PVC or registry host. `<verdict>` is `attributed`, `ruled_out` or
  `outranked`. `<cause>` and `<reason>` are the trace entry's own text.
- `<action>` is what the gather did with the candidate, checked in the gather's
  own order (`investigate/gather.go:92-133`):
  - `budget`: the gather stopped before it reached the candidate, because 8
    reads were already spent. Every candidate of a workload the gather never
    reached is `budget`.
  - `ruled_out`: the verdict is `ruled_out`, so there is nothing to read.
  - `no_object`: the candidate names no object.
  - `registry`: a registry candidate. A registry has no object to describe.
  - `deduped`: an earlier candidate already read this object.
  - `read`: the gather described the object.
- `<ref>` is the 1-based trail place of the read it made (`read`) or reused
  (`deduped`). It is empty for every other action.

## 04-nodes.txt and 05-pvcs.txt

One entry per describe, in trail order.

```
node\t<read>\t<node>\t<status>\t<message>
block\tcontent\t<N>

pvc\t<read>\t<namespace>\t<name>\t<status>\t<message>
block\tcontent\t<N>
```

- `node`: 5 fields. `pvc`: 6 fields.
- `<status>` is `ok` or `failed`. `<message>` is empty for `ok`. For `failed`
  it is the refusal as the rules see it (`Reads.Failed["node/<node>"]` or
  `Reads.Failed["pvc/<namespace>/<name>"]`).
- Then the read's `content` block.

## 06-logs.txt

For each scoped workload in row order, one record per finding, in finding order:

```
log\t<row>\t<namespace>\t<pod>\t<container>\t<issue>\t<action>\t<ref>
block\tcontent\t<N>
```

- `log`: 8 fields. `<pod>` is the finding's pod name without its namespace.
  `<container>` is empty when the finding names none.
- `<action>`, checked in the gather's own order (`investigate/gather.go:135-154`):
  - `budget`: the gather stopped first (8 reads spent).
  - `skip`: not a crash-family issue (`CrashLoopBackOff`, `ContainerStartError`,
    `OOMKilled`), no container, or no pod name.
  - `deduped`: an earlier finding already read this pod's container log.
  - `read`: the gather read the previous log.
- `<ref>` is as in dump 3.
- A `content` block follows only a `read` record.

## 07-trail.txt

One record per read, in the order the gather made them:

```
<read>\t<label>
```

2 fields, with no record-type field. `<label>` is the trail label, for example
`events app/api-6d5f7c8b9-k2m4p` or `describe node /worker-1` (a node's label
keeps the empty namespace, so it reads `node /<name>`).

## 08-bundle.txt

One block:

```
block\tbundle\t<N>
```

The bundle is every read as `== <label> ==\n<body>\n\n`, in trail order. So it
ends in `\n\n`, and the block's own `\n` makes three.

## 09-decide.txt

First what the rules see (`hypothesis.Reads`), each group sorted by key:

```
read_node\t<node>
read_pvc\t<namespace>/<name>
read_events\t<namespace>/<pod>\t<count>
failed\t<key>\t<message>
```

- `read_node`: 2 fields. `read_pvc`: 2 fields. `read_events`: 3 fields, where
  `<count>` is how many events the read returned.
- `failed`: 3 fields. `<key>` is `events/<namespace>/<pod>`, `node/<node>` or
  `pvc/<namespace>/<name>`.

Then, for each scoped workload in row order, its `hypothesis.Result` and one
`decision` record per `Decision`, in order:

```
result\t<row>\t<namespace>/<name>\t<decided>\t<outcome>\t<cause>\t<evidence>\t<group_key>\t<group_text>
decision\t<kind>\t<object>\t<outcome>\t<cause>\t<evidence>
```

- `result`: 9 fields. `<decided>` is `true` or `false`. For an undecided
  workload, `<outcome>`, `<cause>`, `<evidence>`, `<group_key>` and
  `<group_text>` are empty.
- `decision`: 6 fields. `<outcome>` is `confirmed`, `refuted` or `unverified`.
  `<cause>` is the candidate's cause.

## 10-prompt.txt

```
cluster\t<verdict>\t<ready>\t<total>
node_issue\t<text>
system_issue\t<text>
shared\t<line>
block\tprompt\t<N>
```

- `cluster`: 4 fields, once: `ClusterHealth.Verdict` (`Degraded` or
  `Healthy`), `NodesReady` and `NodesTotal`.
- `node_issue` and `system_issue`: 2 fields each, in `ClusterHealth` order.
- `shared`: 2 fields, one per line `hypothesis.Shared` returns, in order.
- The `prompt` block is the whole user message `buildVerdictPrompt` returns. It
  is byte-for-byte the `contract/golden/user_message.txt` the same run wrote. The
  harness checks this.

## The log fixture

`tests/fixtures/gather_go_logs/` holds the same eleven dumps for
`tests/fixtures/gather_fixture_logs.yaml`, in the same format as the files here.
The same run of the harness writes both folders.

Why a second fixture: the gather has a budget of 8 reads. The main fixture spends
all 8 on events, node and PVC reads before it reaches a crashed container, so its
`06-logs.txt` holds only `budget` and `skip` records, and no log read is compared.
The main fixture cannot make room, because its 8 reads are the ones rule-path
coverage needs. So the log fixture is a small, healthy cluster where 5 of the 8
reads are log reads. Its `06-logs.txt` holds all four actions (`read`, `deduped`,
`skip` and `budget`), and its log reads give all four answers: a cause, no
classifiable output, a refused read and no previous-instance log. The harness
fails the run if one is missing.

What differs from the main fixture's dumps:

- No workload has a node or PVC candidate. `03-candidates.txt` holds only
  `workload` records, and `04-nodes.txt` and `05-pvcs.txt` are empty files.
- One read is over 4 KiB on purpose: the events of `shop/api-7d4b9c6f5-k8m2p`.
  `02-events.txt` lists all 32 events, and the `content` block holds the text
  `capContent` cut on a line, ending in `[truncated by kubeagent]`.
- The cluster is `Healthy`, so the prompt has no cluster-health line.
- `10-prompt.txt`'s prompt block is the prompt the same run built. There is no
  `user_message.txt` to compare it with.

All four golden files (`contract/golden/input.json`,
`contract/golden/user_message.txt`, `contract/system_prompt.txt` and
`tests/fixtures/rules_golden.json`) come from the main fixture. The log fixture
writes none.
