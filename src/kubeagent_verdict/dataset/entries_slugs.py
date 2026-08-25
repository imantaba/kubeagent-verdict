"""Slug-keyed catalog entries — one per chaos fault slug (17 when complete)."""

from kubeagent_verdict.dataset.catalog import CatalogEntry

ENTRIES = [
    CatalogEntry(
        key="memory-limit-oomkill",
        covered_slugs=("memory-limit-oomkill",),
        covered_kinds=("OOMKilled",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="OOMKilled",
        reason="container killed: out of memory",
        evidence="container {container} last terminated with reason OOMKilled, exit code 137",
        next_step="raise the container's memory limit or fix the leak",
        command="kubectl -n {ns} describe pod {pod}",
        resources=("64Mi", "64Mi", "100m", "250m"),
        winner_cause="memory limit too low for the workload",
        winner_reason="the container is repeatedly OOMKilled at its 64Mi limit",
        losers=(
            ("node {node} under memory pressure", "ruled_out",
             "the node reports no MemoryPressure condition"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("44s Warning BackOff pod/{pod} back-off restarting failed container {container}\n"
              "2m Normal Pulled pod/{pod} container image already present on machine\n")),
        ),
        rationale="The container exits 137 with reason OOMKilled on every restart, which points "
                  "at its own memory limit rather than the node.",
        direct=True,
        contradiction="LAST SEEN  TYPE     REASON   MESSAGE\n"
                      "51s        Warning  BackOff  back-off restarting failed container "
                      "{container} in pod {pod}: last state terminated with exit code 1 (Error), "
                      "node reports ample allocatable memory\n",
        own_cause="container killed at its memory limit",
        own_cause_keywords=("memory", "limit"),
        grounding=("OOMKilled",),
    ),
    CatalogEntry(
        key="deployment-bad-image-tag",
        covered_slugs=("deployment-bad-image-tag",),
        covered_kinds=("ImagePullBackOff", "ErrImagePull"),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="ImagePullBackOff",
        reason="Back-off pulling image",
        evidence='Failed to pull image "{image}": not found',
        next_step="fix the image tag or push the missing image",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="image tag not found in the registry",
        winner_reason="the pull error names the tag as missing",
        losers=(
            ("registry unreachable from node {node}", "ruled_out",
             "other images pull fine on the same node"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ('3m Warning Failed pod/{pod} Failed to pull image "{image}": not found\n'
              "3m Warning Failed pod/{pod} Error: ErrImagePull\n"
              "2m Normal BackOff pod/{pod} Back-off pulling image \"{image}\"\n")),
        ),
        rationale="The pull failure names {image} as not found, so the tag itself is wrong "
                  "rather than the registry being unreachable.",
        direct=True,
        contradiction="LAST SEEN  TYPE     REASON  MESSAGE\n"
                      "2m         Normal   Pulled  Successfully pulled image \"{image}\"\n"
                      "90s        Warning  BackOff back-off restarting failed container "
                      "{container}\n",
        own_cause="the image tag does not exist in the registry",
        own_cause_keywords=("tag", "registry"),
        grounding=("ImagePullBackOff",),
    ),
    CatalogEntry(
        key="control-plane-docker-stop",
        covered_slugs=("control-plane-docker-stop",),
        covered_kinds=(),
        trains=False,
        notes="scan cannot reach the API server; no verdict call occurs (corpus asserts a "
              "non-zero exit and 'refused the connection', no cluster report rendered)",
    ),
    CatalogEntry(
        key="control-plane-cert-expiry",
        covered_slugs=("control-plane-cert-expiry",),
        covered_kinds=(),
        trains=False,
        notes="the client cannot connect; no verdict call occurs (every corpus row for this "
              "fault is skipped: control-plane certificate expiry cannot be forced quickly or "
              "safely)",
    ),
    CatalogEntry(
        key="node-cordon-diskfull",
        covered_slugs=("node-cordon-diskfull",),
        covered_kinds=(),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="Unschedulable",
        reason="No node can schedule this pod",
        evidence="0/3 nodes are available: 1 node(s) were unschedulable, 1 node(s) had disk "
                 "pressure.",
        next_step="uncordon the node or free disk space, then confirm DiskPressure clears",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="node {node} is cordoned and under disk pressure",
        winner_reason="the node carries unschedulable=true and a DiskPressure condition",
        losers=(
            ("insufficient cluster CPU for the pod's request", "ruled_out",
             "the other nodes report free allocatable CPU"),
        ),
        reads=(
            ("describe node /{node}",
             ("node {node}: unschedulable=true\n"
              "  condition DiskPressure=True (KubeletHasDiskPressure): disk usage is above "
              "the eviction threshold\n"
              "  taint node.kubernetes.io/disk-pressure=:NoSchedule\n")),
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  FailedScheduling: 0/3 nodes are available: 1 node(s) were unschedulable, "
              "1 node(s) had disk pressure. (x6)\n")),
        ),
        rationale="The node carries unschedulable=true plus a DiskPressure condition and taint, "
                  "and the FailedScheduling event names disk pressure directly, so the node's own "
                  "state explains the pending pod better than a cluster-wide CPU shortage.",
        direct=True,
        contradiction="node {node}: unschedulable=false\n"
                      "  condition DiskPressure=False (KubeletHasNoDiskPressure): disk usage is "
                      "below the eviction threshold\n",
        own_cause="the pod's node is cordoned and reporting disk pressure",
        own_cause_keywords=("cordon", "disk"),
        grounding=("Unschedulable",),
    ),
    CatalogEntry(
        key="networkpolicy-deny-all",
        covered_slugs=("networkpolicy-deny-all",),
        covered_kinds=(),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="ProbeFailure",
        reason="the readiness probe keeps failing — the pod is kept out of Service endpoints",
        evidence='Readiness probe failed: Get "{pod}:8080/healthz": dial tcp: i/o timeout',
        next_step="check whether a NetworkPolicy now blocks the probe's traffic",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="a deny-all NetworkPolicy now selects the pod",
        winner_reason="the probe began timing out at the same moment the policy was created, "
                      "with no code change",
        losers=(
            ("a bug in the application's health endpoint", "outranked",
             ("the probe passed continuously until the policy appeared, then failed on every "
              "replica at once")),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              '  Unhealthy: Readiness probe failed: Get "{pod}:8080/healthz": dial tcp: '
              "i/o timeout (x9)\n")),
        ),
        rationale="The probe timeouts start exactly when the deny-all policy is created and hit "
                  "every replica at once, which points at network reachability rather than an "
                  "application defect.",
        direct=False,
        contradiction="events for {ns}/{pod}:\n"
                      "  Unhealthy: Readiness probe failed: HTTP probe failed with statuscode: "
                      "500 (x9)\n",
        own_cause="a NetworkPolicy now blocks traffic to the pod's probe port",
        own_cause_keywords=("networkpolicy", "traffic"),
        network_policies=("default-deny",),
    ),
    CatalogEntry(
        key="coredns-corefile-broken",
        covered_slugs=("coredns-corefile-broken",),
        covered_kinds=(),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="CrashLoopBackOff",
        reason="Container repeatedly crashes after starting",
        evidence='container "coredns", restartCount=6',
        next_step="check the Corefile for a syntax or plugin error",
        command="kubectl -n kube-system describe pod {pod}",
        winner_cause="a broken Corefile is crashing CoreDNS on startup",
        winner_reason="the previous-instance log shows a Corefile parse error, and both replicas "
                      "crash the same way on different nodes",
        losers=(
            ("a failing node underneath the pods", "ruled_out",
             "the two crashing replicas run on two different nodes"),
        ),
        reads=(
            ("events kube-system/{pod}",
             ("events for kube-system/{pod}:\n"
              "  BackOff: Back-off restarting failed container coredns in pod {pod} (x14)\n")),
            ("log causes kube-system/{pod} container coredns",
             "log cause: configuration parse/validation error"),
        ),
        rationale="Both CoreDNS replicas crash the same way on different nodes, and the previous "
                  "log classifies as a configuration parse error, which points at the shared "
                  "Corefile rather than either node.",
        direct=True,
        contradiction="events for kube-system/{pod}:\n"
                      "  Killing: Stopping container coredns (node {node} shutting down) (x1)\n",
        own_cause="the Corefile has a syntax or plugin error that crashes CoreDNS on startup",
        own_cause_keywords=("corefile", "coredns"),
        grounding=("kube-system/coredns",),
        degraded=False,
    ),
    CatalogEntry(
        key="loadbalancer-no-provider",
        covered_slugs=("loadbalancer-no-provider",),
        covered_kinds=(),
        trains=False,
        notes="a pending LoadBalancer is a Service issue with no flagged workload; no verdict "
              "call occurs (corpus asserts only a pending Service and 'no external address', "
              "no workload finding)",
    ),
    CatalogEntry(
        key="namespace-deletion",
        covered_slugs=("namespace-deletion",),
        covered_kinds=(),
        trains=False,
        notes="the namespace and its workloads are gone; nothing is flagged (corpus shows "
              "'Cluster: Healthy' and 'No issues found.')",
    ),
    CatalogEntry(
        key="configmap-aws-key-leak",
        covered_slugs=("configmap-aws-key-leak",),
        covered_kinds=(),
        trains=False,
        notes="a credential-scan policy violation on a ConfigMap, not a workload finding; "
              "verdict mode never fires (corpus names the leak location and pattern, no "
              "workload issue)",
    ),
    CatalogEntry(
        key="worker-containerd-stop",
        covered_slugs=("worker-containerd-stop",),
        covered_kinds=(),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="ContainerStartError",
        reason="the container image was resolved but the container could not be started",
        evidence='container "{container}": RunContainerError: failed to create containerd task: '
                 "context deadline exceeded",
        next_step="check whether the container runtime on {node} is healthy",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="the container runtime is down on node {node}",
        winner_reason="the node reports NotReady and every pod scheduled to it fails the same way",
        losers=(
            ("a broken container image", "ruled_out",
             "the same image starts successfully on the cluster's other nodes"),
        ),
        reads=(
            ("describe node /{node}",
             ("node {node}: unschedulable=false\n"
              "  condition Ready=False (KubeletNotReady): container runtime is down\n")),
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  Failed: Error: RunContainerError: failed to create containerd task: context "
              "deadline exceeded (x4)\n")),
        ),
        rationale="Node {node} reports NotReady with its runtime down, and the same image runs "
                  "cleanly elsewhere in the cluster, so the node's runtime explains the failure "
                  "rather than the image.",
        direct=True,
        contradiction="node {node}: unschedulable=false\n"
                      "  condition Ready=True (KubeletReady): kubelet is posting ready status\n",
        own_cause="the container runtime on the pod's node is not responding",
        own_cause_keywords=("runtime", "node"),
        grounding=("NotReady",),
    ),
    CatalogEntry(
        key="certmanager-bad-issuer-ref",
        covered_slugs=("certmanager-bad-issuer-ref",),
        covered_kinds=(),
        trains=False,
        notes="flipped from the directive table's best-judgment True: the corpus asserts only a "
              "cert-manager Certificate adapter section ('cert-manager Certificate adapter "
              "fired', 'the failing Certificate is counted unhealthy') with no pod or workload "
              "finding, so no verdict call occurs",
    ),
    CatalogEntry(
        key="flux-gitrepo-dns-failure",
        covered_slugs=("flux-gitrepo-dns-failure",),
        covered_kinds=(),
        trains=False,
        notes="the failure lives in a GitRepository/Kustomization CR kubeagent does not scan as "
              "a workload; the corpus shows only a GitOps drift section, no pod finding",
    ),
    CatalogEntry(
        key="oversized-job-unschedulable",
        covered_slugs=("oversized-job-unschedulable",),
        covered_kinds=("Unschedulable",),
        trains=True,
        workload_kind="Job",
        status="Running",
        issue="Unschedulable",
        reason="No node can schedule this pod",
        evidence="0/3 nodes are available: 3 Insufficient memory.",
        next_step="lower the Job's memory request or add a node that can fit it",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="the Job's resource request is larger than any node's allocatable capacity",
        winner_reason="every node in the FailedScheduling message is rejected for Insufficient "
                      "memory, and none are cordoned",
        losers=(
            ("a cordoned node removed from scheduling", "ruled_out",
             "all three nodes are schedulable; the rejection reason is capacity, not cordon"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  FailedScheduling: 0/3 nodes are available: 3 Insufficient memory. (x5)\n")),
        ),
        rationale="Every node in the scheduler's message is rejected for Insufficient memory and "
                  "none carry SchedulingDisabled, so the request itself does not fit rather than "
                  "nodes being withdrawn.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      "  FailedScheduling: 0/3 nodes are available: 3 node(s) were "
                      "unschedulable. (x5)\n",
        own_cause="the pod's memory request is larger than any node can allocate",
        own_cause_keywords=("memory", "request"),
    ),
    CatalogEntry(
        key="crashloop-pod",
        covered_slugs=("crashloop-pod",),
        covered_kinds=("CrashLoopBackOff",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="CrashLoopBackOff",
        reason="Container repeatedly crashes after starting",
        evidence='container "{container}", restartCount={restarts}',
        log_cause="log cause: bad command or entrypoint",
        next_step="check the container's command and args against what the image expects to run",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="the container exits immediately on startup",
        winner_reason="the previous-instance log shows an entrypoint failure, and the image "
                      "pulled successfully before the first attempt",
        losers=(
            ("a broken container image", "ruled_out",
             "the image was pulled successfully and the same tag runs other replicas"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  BackOff: Back-off restarting failed container {container} in pod {pod} "
              "(x{restarts})\n")),
            ("log causes {ns}/{pod} container {container}",
             "log cause: bad command or entrypoint"),
        ),
        rationale="The previous log classifies as a bad entrypoint and the image itself pulled "
                  "successfully, so the container's own startup command explains the crash loop.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      '  Pulled: Successfully pulled image "{image}" (x1)\n',
        own_cause="the container's command or entrypoint is wrong and it exits immediately",
        own_cause_keywords=("entrypoint", "exit"),
    ),
    CatalogEntry(
        key="no-fault-healthy-readyz",
        covered_slugs=("no-fault-healthy-readyz",),
        covered_kinds=(),
        trains=False,
        notes="a healthy cluster with nothing flagged; the corpus shows a ready control plane "
              "and no issue section, so no verdict call occurs",
    ),
    CatalogEntry(
        key="coredns-servfail-template",
        covered_slugs=("coredns-servfail-template",),
        covered_kinds=(),
        trains=False,
        notes="CoreDNS pods stay Ready and answer queries (with SERVFAIL) while up, so nothing "
              "is flagged and no verdict call occurs; the fault surfaces only through the DNS "
              "health probe, which LocalClient.Investigate never reaches",
    ),
]
