# What kubeagent does with the cluster fixture

These files are what kubeagent v1.24.0 does with
`tests/fixtures/gather_fixture_cluster.yaml`. One run of the Go harness
`contract/capture/kv_capture_test.go.txt` in its `cluster` mode wrote them. Do not
edit them by hand: re-run the harness.

The format is the same as in `tests/fixtures/gather_go/README.md`. Read that file
for the record layout of dumps 1 to 10. Dump 0 works the same way too: compare it
as parsed values, not as bytes.

## What this fixture is for

The main fixture has 3 nodes. This one has 16 nodes, 19 workloads and 13
services. It shows the cluster block of the prompt and the pure scan steps that
feed it:

- Every way a node can be down: a Ready condition that is False, a Ready
  condition that is missing, no kubelet lease, and a lease that is stale.
- Pressure conditions and cordoned nodes.
- Service issues, with and without a down node behind them.
- Network policy notes on workloads.

## What differs from the main fixture's dumps

- `03-candidates.txt` has many `down` records. Every down node is a candidate
  for every flagged workload, and the prompt keeps only 8 per workload.
- `10-prompt.txt` has `node_issue`, `system_issue` and `shared` records. The
  prompt keeps only the first 10 service issues, so services s11 to s13 are cut
  and never reach the dump.
- The gather spends its 8 reads on events reads and one node describe. No PVC is
  read, so `05-pvcs.txt` is an empty file.
- No golden file comes from this run.
