# What kubeagent does with the cluster fixture

These files are what kubeagent v1.24.0 does with `gather_fixture_cluster.yaml`:
16 nodes, 19 workloads and 13 services. The Go harness
`contract/capture/kv_capture_test.go.txt` wrote them in its `cluster` mode. Do not
edit them by hand: re-run the harness. The format is the one in
`gather_go/README.md`. The fixture shows the prompt's cluster block: every way a
node can be down, and ten service lines (services s11 to s13 are cut by the
prompt's cap of 10).
