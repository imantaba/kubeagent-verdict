# The smoke set

These three pairs came from a kubeagent v1.24.0 run against a throwaway kind cluster with one injected fault.
The two node names became `worker-1` and `worker-2`; nothing else in the pairs changed. The model was 0908.
`kv-eval` scores these pairs with job 1 and prints them under a `smoke (not gated)` heading: 12 rule rows, the cause echoed on 4, job 1 scored 3 of 12.
The score never moves a pass bar — this set decides nothing.
To refresh it: capture a new v1.24.0 `--investigate` run's calls 02-04 under `out/live/calls/`, then rerun the redaction step in this task against them.
