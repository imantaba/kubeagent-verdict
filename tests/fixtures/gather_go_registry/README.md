# What kubeagent does with the registry fixture

These files are what kubeagent v1.24.0 does with
`tests/fixtures/gather_fixture_registry.yaml`. One run of the Go harness
`contract/capture/kv_capture_test.go.txt` in its `registry` mode wrote them. Do
not edit them by hand: re-run the harness.

The format is the same as in `tests/fixtures/gather_go/README.md`. Read that file
for the record layout of dumps 1 to 10. Dump 0 works the same way too: compare it
as parsed values, not as bytes.

## What this fixture is for

It has 3 healthy nodes and 6 Deployments in the namespace `pull`. Each one is
failing to pull an image. Together they cover the registry rules:

- A connection error, an auth error and an image error in the pull event. The
  connection error wins over the auth error, and the auth error wins over the
  image error.
- A pull with no event that names the failure.
- A first pod whose events were not read, because the pull finding sits on a
  second pod.
- One workload that fails to pull from a host of its own. It is under the
  threshold of 2, so it is ruled out.

## What differs from the main fixture's dumps

- `03-candidates.txt` holds `registry` candidates only. A registry has no object
  to describe, so every action is `registry` or `ruled_out`.
- `04-nodes.txt` and `05-pvcs.txt` are empty files. `06-logs.txt` holds only
  `skip` records: a pull failure is not a crash, so no log is read.
- `09-decide.txt` holds the text the rules wrote for each pull event. These are
  the sentences the Python port must match.
- No golden file comes from this run.
