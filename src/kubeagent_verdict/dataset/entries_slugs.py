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
        events=(
            ("BackOff", "back-off restarting failed container {container}", 1),
            ("Pulled", "container image already present on machine", 1),
        ),
        contradiction_events=(
            ("BackOff",
             ("back-off restarting failed container {container} in pod {pod}: last state "
              "terminated with exit code 1 (Error), node reports ample allocatable memory"), 1),
        ),
        rationale="The container exits 137 with reason OOMKilled on every restart, which points "
                  "at its own memory limit rather than the node.",
        direct=True,
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
        events=(
            ("Failed", 'Failed to pull image "{image}": not found', 1),
            ("Failed", "Error: ErrImagePull", 1),
            ("BackOff", 'Back-off pulling image "{image}"', 1),
        ),
        rationale="The pull failure names {image} as not found, so the tag itself is wrong "
                  "rather than the registry being unreachable.",
        direct=True,
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
        own_cause="the pod's node is cordoned and reporting disk pressure",
        own_cause_keywords=("node", "pod"),
        grounding=("Unschedulable",),
        # The pod is unscheduled, so no pod of the workload is on the node
        # and the rules rule it out: placement "off". No builder describes
        # it, so no prompt for this entry shows the disk pressure.
        objects=(
            Object(kind="node", name="{node}", scan_reason="no kubelet lease",
                   placement="off",
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
        events=(
            ("Unhealthy",
             'Readiness probe failed: Get "{pod}:8080/healthz": dial tcp: i/o timeout', 9),
        ),
        contradiction_events=(
            ("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 500", 9),
        ),
        rationale="The probe timeouts start exactly when the deny-all policy is created and hit "
                  "every replica at once, which points at network reachability rather than an "
                  "application defect.",
        direct=False,
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
        events=(
            ("BackOff", "Back-off restarting failed container coredns in pod {pod}", 14),
        ),
        contradiction_events=(
            ("Killing", "Stopping container coredns (node {node} shutting down)", 1),
        ),
        rationale="Both CoreDNS replicas crash the same way on different nodes, and the previous "
                  "log classifies as a configuration parse error, which points at the shared "
                  "Corefile rather than either node.",
        direct=True,
        own_cause="the Corefile has a syntax or plugin error that crashes CoreDNS on startup",
        own_cause_keywords=("coredns", "error"),
        grounding=("kube-system/coredns",),
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
        # The evidence fixes restartCount=6, and kubeagent's workload count
        # sums its pods' container restarts (internal/inventory/inventory.go:
        # 158-170, 488), so the workload line never shows fewer than 6.
        min_restarts=6,
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
        events=(
            ("Failed",
             ("Error: RunContainerError: failed to create containerd task: context deadline "
              "exceeded"), 4),
        ),
        rationale="Node {node} reports NotReady with its runtime down, and the same image runs "
                  "cleanly elsewhere in the cluster, so the node's runtime explains the failure "
                  "rather than the image.",
        direct=True,
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
        events=(
            ("FailedScheduling",
             ("0/3 nodes are available: 3 Insufficient memory. preemption: 0/3 nodes are "
              "available: 3 Preemption is not helpful for scheduling."), 5),
        ),
        rationale="Every node in the scheduler's message is rejected for Insufficient memory and "
                  "none carry SchedulingDisabled, so the request itself does not fit rather than "
                  "nodes being withdrawn.",
        direct=True,
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
        events=(
            ("BackOff", "Back-off restarting failed container {container} in pod {pod}",
             "{restarts}"),
        ),
        contradiction_events=(
            ("Pulled", 'Successfully pulled image "{image}"', 1),
        ),
        rationale="The previous log classifies as a bad entrypoint and the image itself pulled "
                  "successfully, so the container's own startup command explains the crash loop.",
        direct=True,
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
