"""Slug-keyed catalog entries — one per chaos fault slug (17 when complete)."""

from kubeagent_verdict.dataset.catalog import CatalogEntry
from kubeagent_verdict.dataset.objects import NODE_NOT_READY, Fresh, Object

ENTRIES = [
    CatalogEntry(
        key="memory-limit-oomkill",
        covered_slugs=("memory-limit-oomkill",),
        covered_kinds=("OOMKilled",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="OOMKilled",
        reason="Container exceeded its memory limit and was killed",
        evidence='container "{container}", exitCode=137',
        recommendation="raise the container's memory limit or fix the leak",
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
        events=(
            ("BackOff", "back-off restarting failed container {container}", 1),
            ("Pulled", "container image already present on machine", 1),
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
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
    ),
    CatalogEntry(
        key="deployment-bad-image-tag",
        covered_slugs=("deployment-bad-image-tag",),
        covered_kinds=("ImagePullBackOff", "ErrImagePull"),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="ImagePullBackOff",
        reason="Bad image reference or registry authentication",
        evidence='container "{container}": Failed to pull image "{image}": not found',
        recommendation="fix the image tag or push the missing image",
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
        events=(
            ("Failed", 'Failed to pull image "{image}": not found', 1),
            ("Failed", "Error: ErrImagePull", 1),
            ("BackOff", 'Back-off pulling image "{image}"', 1),
        ),
        rationale="The pull failure names {image} as not found, so the tag itself is wrong "
                  "rather than the registry being unreachable.",
        direct=True,
        contradiction="LAST SEEN  TYPE     REASON  MESSAGE\n"
                      "2m         Normal   Pulled  Successfully pulled image \"{image}\"\n"
                      "90s        Warning  BackOff back-off restarting failed container "
                      "{container}\n",
        own_cause="the image tag does not exist in the registry",
        own_cause_keywords=("image", "registry"),
        grounding=("ImagePullBackOff",),
        objects=(
            Object(kind="registry", name="registry.example.com", scan_reason="2",
                   placement="", fresh=Fresh(literal="dial tcp"), intent="decoy"),
        ),
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
        evidence="0/3 nodes are available: 1 node(s) were unschedulable, 2 node(s) had "
                 "untolerated taint(s). preemption: 0/3 nodes are available: 3 Preemption is "
                 "not helpful for scheduling.",
        recommendation="uncordon the node or free disk space, then confirm DiskPressure clears",
        winner_cause="node {node} is cordoned and under disk pressure",
        winner_reason="the node carries unschedulable=true and a DiskPressure condition",
        losers=(
            ("insufficient cluster CPU for the pod's request", "ruled_out",
             "the other nodes report free allocatable CPU"),
        ),
        reads=(
            ("describe node /{node}",
             ("node {node}: unschedulable=true\n"
              "  condition MemoryPressure=False (KubeletHasSufficientMemory): kubelet has "
              "sufficient memory available\n"
              "  condition DiskPressure=True (KubeletHasDiskPressure): kubelet has disk "
              "pressure\n"
              "  condition PIDPressure=False (KubeletHasSufficientPID): kubelet has "
              "sufficient PID available\n"
              "  condition Ready=True (KubeletReady): kubelet is posting ready status\n"
              "  taint node.kubernetes.io/unschedulable=:NoSchedule\n"
              "  taint node.kubernetes.io/disk-pressure=:NoSchedule\n")),
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  FailedScheduling: 0/3 nodes are available: 1 node(s) were unschedulable, "
              "2 node(s) had untolerated taint(s). preemption: 0/3 nodes are available: 3 "
              "Preemption is not helpful for scheduling. (x6)\n")),
        ),
        events=(
            ("FailedScheduling",
             ("0/3 nodes are available: 1 node(s) were unschedulable, 2 node(s) had untolerated "
              "taint(s). preemption: 0/3 nodes are available: 3 Preemption is not helpful for "
              "scheduling."), 6),
        ),
        rationale="The node carries unschedulable=true plus a DiskPressure condition and taint, "
                  "and the FailedScheduling event names disk pressure directly, so the node's own "
                  "state explains the pending pod better than a cluster-wide CPU shortage.",
        direct=True,
        contradiction=("node {node}: unschedulable=false\n"
                       "  condition MemoryPressure=False (KubeletHasSufficientMemory): kubelet "
                       "has sufficient memory available\n"
                       "  condition DiskPressure=False (KubeletHasNoDiskPressure): kubelet has "
                       "no disk pressure\n"
                       "  condition PIDPressure=False (KubeletHasSufficientPID): kubelet has "
                       "sufficient PID available\n"
                       "  condition Ready=True (KubeletReady): kubelet is posting ready status\n"),
        own_cause="the pod's node is cordoned and reporting disk pressure",
        own_cause_keywords=("node", "pod"),
        grounding=("Unschedulable",),
        objects=(
            Object(kind="node", name="{node}", scan_reason="no kubelet lease",
                   placement="on",
                   fresh=Fresh(ready="True", unschedulable=True, disk_pressure=True,
                               taints=(("node.kubernetes.io/unschedulable", "", "NoSchedule"),
                                       ("node.kubernetes.io/disk-pressure", "", "NoSchedule"))),
                   intent="decoy"),
        ),
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
        evidence='container "{container}": readiness probe failed — timed out',
        recommendation="check whether a NetworkPolicy now blocks the probe's traffic",
        winner_cause="a deny-all NetworkPolicy now selects the pod",
        winner_reason="the probe began timing out at the same moment the policy was created, "
                      "with no code change",
        losers=(
            ("a bug in the application's health endpoint", "outranked",
             ("the probe passed continuously until the policy appeared, then failed on every "
              "replica at once")),
            ("node {node} going NotReady", "ruled_out",
             ("the probe failures start and stop with the NetworkPolicy, not with the node's "
              "condition, which stays Ready throughout")),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              '  Unhealthy: Readiness probe failed: Get "{pod}:8080/healthz": dial tcp: '
              "i/o timeout (x9)\n")),
        ),
        events=(
            ("Unhealthy",
             'Readiness probe failed: Get "{pod}:8080/healthz": dial tcp: i/o timeout', 9),
        ),
        rationale="The probe timeouts start exactly when the deny-all policy is created and hit "
                  "every replica at once, which points at network reachability rather than an "
                  "application defect.",
        direct=False,
        contradiction="events for {ns}/{pod}:\n"
                      "  Unhealthy: Readiness probe failed: HTTP probe failed with statuscode: "
                      "500 (x9)\n",
        own_cause="a NetworkPolicy now blocks traffic to the pod's probe port",
        own_cause_keywords=("network", "policy"),
        network_policies=("default-deny",),
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
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
        evidence='container "coredns", restartCount=6, last exit 1 (Error), 42s ago',
        recommendation="check the Corefile for a syntax or plugin error",
        winner_cause="a broken Corefile is crashing CoreDNS on startup",
        winner_reason="the previous-instance log shows a Corefile parse error, and both replicas "
                      "crash the same way on different nodes",
        losers=(
            ("a failing node underneath the pods", "ruled_out",
             "the two crashing replicas run on two different nodes"),
            ("node {node} going NotReady", "ruled_out",
             "the two crashing replicas run on two different nodes, and both report Ready"),
        ),
        reads=(
            ("events kube-system/{pod}",
             ("events for kube-system/{pod}:\n"
              "  BackOff: Back-off restarting failed container coredns in pod {pod} (x14)\n")),
            ("log causes kube-system/{pod} container coredns",
             "log cause: configuration parse/validation error"),
        ),
        events=(
            ("BackOff", "Back-off restarting failed container coredns in pod {pod}", 14),
        ),
        rationale="Both CoreDNS replicas crash the same way on different nodes, and the previous "
                  "log classifies as a configuration parse error, which points at the shared "
                  "Corefile rather than either node.",
        direct=True,
        contradiction="events for kube-system/{pod}:\n"
                      "  Killing: Stopping container coredns (node {node} shutting down) (x1)\n",
        own_cause="the Corefile has a syntax or plugin error that crashes CoreDNS on startup",
        own_cause_keywords=("coredns", "error"),
        grounding=("kube-system/coredns",),
        degraded=False,
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
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
        recommendation="check whether the container runtime on {node} is healthy",
        winner_cause="the container runtime is down on node {node}",
        winner_reason="the node reports NotReady and every pod scheduled to it fails the same way",
        losers=(
            ("a broken container image", "ruled_out",
             "the same image starts successfully on the cluster's other nodes"),
        ),
        reads=(
            ("describe node /{node}",
             ("node {node}: unschedulable=false\n"
              "  condition MemoryPressure=False (KubeletHasSufficientMemory): kubelet has "
              "sufficient memory available\n"
              "  condition DiskPressure=False (KubeletHasNoDiskPressure): kubelet has no disk "
              "pressure\n"
              "  condition PIDPressure=False (KubeletHasSufficientPID): kubelet has "
              "sufficient PID available\n"
              "  condition Ready=False (KubeletNotReady): container runtime is down\n")),
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  Failed: Error: RunContainerError: failed to create containerd task: context "
              "deadline exceeded (x4)\n")),
        ),
        events=(
            ("Failed",
             ("Error: RunContainerError: failed to create containerd task: context deadline "
              "exceeded"), 4),
        ),
        rationale="Node {node} reports NotReady with its runtime down, and the same image runs "
                  "cleanly elsewhere in the cluster, so the node's runtime explains the failure "
                  "rather than the image.",
        direct=True,
        contradiction=("node {node}: unschedulable=false\n"
                       "  condition MemoryPressure=False (KubeletHasSufficientMemory): kubelet "
                       "has sufficient memory available\n"
                       "  condition DiskPressure=False (KubeletHasNoDiskPressure): kubelet has "
                       "no disk pressure\n"
                       "  condition PIDPressure=False (KubeletHasSufficientPID): kubelet has "
                       "sufficient PID available\n"
                       "  condition Ready=True (KubeletReady): kubelet is posting ready status\n"),
        own_cause="containerd on the pod's node is not responding (context deadline exceeded)",
        own_cause_keywords=("containerd", "deadline"),
        grounding=("NotReady",),
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="cause"),
        ),
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
        evidence="0/3 nodes are available: 3 Insufficient memory. preemption: 0/3 nodes are "
                 "available: 3 Preemption is not helpful for scheduling.",
        recommendation="lower the Job's memory request or add a node that can fit it",
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
              "  FailedScheduling: 0/3 nodes are available: 3 Insufficient memory. "
              "preemption: 0/3 nodes are available: 3 Preemption is not helpful for "
              "scheduling. (x5)\n")),
        ),
        events=(
            ("FailedScheduling",
             ("0/3 nodes are available: 3 Insufficient memory. preemption: 0/3 nodes are "
              "available: 3 Preemption is not helpful for scheduling."), 5),
        ),
        rationale="Every node in the scheduler's message is rejected for Insufficient memory and "
                  "none carry SchedulingDisabled, so the request itself does not fit rather than "
                  "nodes being withdrawn.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      "  FailedScheduling: 0/3 nodes are available: 3 node(s) were "
                      "unschedulable. preemption: 0/3 nodes are available: 3 Preemption is "
                      "not helpful for scheduling. (x5)\n",
        own_cause="the pod's memory request is larger than any node can allocate",
        own_cause_keywords=("memory", "node"),
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="off",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
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
        evidence='container "{container}", restartCount={restarts}, last exit 1 (Error), 3m0s ago',
        log_cause="bad command or entrypoint",
        recommendation="check the container's command and args against what the image expects to run",
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
        events=(
            ("BackOff", "Back-off restarting failed container {container} in pod {pod}",
             "{restarts}"),
        ),
        rationale="The previous log classifies as a bad entrypoint and the image itself pulled "
                  "successfully, so the container's own startup command explains the crash loop.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      '  Pulled: Successfully pulled image "{image}" (x1)\n',
        own_cause="the container's command or entrypoint is wrong and it exits immediately",
        own_cause_keywords=("entrypoint", "exit"),
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
        min_restarts=3,
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
