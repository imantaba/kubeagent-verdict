# What kubeagent does with the registry fixture

These files are what kubeagent v1.24.0 does with `gather_fixture_registry.yaml`:
3 healthy nodes and 6 Deployments that fail to pull an image. The Go harness
`contract/capture/kv_capture_test.go.txt` wrote them in its `registry` mode. Do
not edit them by hand: re-run the harness. The format is the one in
`gather_go/README.md`. The fixture reaches each registry rule: a connection, an
auth and an image error, a pull with no event that names the failure, a pulling
pod whose events were not read, and a host with only one failing workload.
