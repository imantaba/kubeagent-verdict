"""Slug-keyed catalog entries — one per chaos fault slug (17 when complete)."""

from kubeagent_verdict.dataset.catalog import INIT_CONTAINER, CatalogEntry
from kubeagent_verdict.dataset.objects import NODE_NOT_READY, Fresh, Object
from kubeagent_verdict.dataset.stories import Answer

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
        own_cause_must_not=INIT_CONTAINER,
        answer=Answer(
            anchor="issue: oomkilled",
            cause="container killed at its memory limit",
            keys=("memory", "limit"),
            rationale="Its finding says the container exceeded its memory limit and was killed, "
                      "with exit code 137."),
        none_phrase="its container keeps being killed for memory",
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
        own_cause_must_not=INIT_CONTAINER,
        answer=Answer(
            anchor="\": not found",
            cause="the image tag does not exist in the registry",
            keys=("image", "registry"),
            rationale="The pull of {image} fails with \"not found\", so the tag does not exist in "
                      "the registry."),
        none_phrase="its image cannot be pulled",
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
        evidence="0/{nodes} nodes are available: 1 node(s) were unschedulable, {other_nodes} node(s) had "
                 "untolerated taint(s). preemption: 0/{nodes} nodes are available: {nodes} Preemption is "
                 "not helpful for scheduling.",
        recommendation="uncordon the node, or check why the other nodes are tainted",
        events=(
            ("FailedScheduling",
             ("0/{nodes} nodes are available: 1 node(s) were unschedulable, {other_nodes} node(s) had untolerated "
              "taint(s). preemption: 0/{nodes} nodes are available: {nodes} Preemption is not helpful for "
              "scheduling."), 6),
        ),
        answer=Answer(
            anchor="were unschedulable",
            cause="one node is unschedulable (cordoned) and the others have taints the pod does "
                  "not tolerate",
            keys=("unschedulable", "taint"),
            rationale="The scheduler says 1 node was unschedulable and {other_nodes} had taints the pod does "
                      "not tolerate, so no node can take it."),
        none_phrase="its pod cannot be scheduled",
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
        answer=Answer(
            anchor="network policy: pods selected by",
            cause="a default-deny network policy blocks the probe's traffic to the pod",
            keys=("network", "policy"),
            confidence="medium",
            rationale="The readiness probe times out, and kubeagent names the default-deny "
                      "network policy that selects its pods as a possible cause, so the policy "
                      "likely blocks the probe."),
        none_phrase="its readiness probe fails",
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
        answer=Answer(
            anchor="log cause: configuration parse",
            cause="the Corefile has a syntax or plugin error that crashes CoreDNS on startup",
            keys=("coredns", "error"),
            rationale="The coredns container keeps crashing, and its previous log classifies as a "
                      "configuration parse or validation error, so CoreDNS cannot load its "
                      "Corefile."),
        none_phrase="its container keeps crashing",
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
        recommendation="check whether the container runtime on the pod's node is healthy",
        events=(
            ("Failed",
             ("Error: RunContainerError: failed to create containerd task: context deadline "
              "exceeded"), 4),
        ),
        answer=Answer(
            anchor="containerd task: context deadline exceeded",
            cause="containerd on the pod's node is not responding (context deadline exceeded)",
            keys=("containerd", "deadline"),
            rationale="Starting the container fails with \"failed to create containerd task: "
                      "context deadline exceeded\", so containerd on the pod's node does not "
                      "answer in time."),
        none_phrase="its container fails to start",
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
        evidence="0/{nodes} nodes are available: {nodes} Insufficient memory. preemption: 0/{nodes} nodes are "
                 "available: {nodes} Preemption is not helpful for scheduling.",
        recommendation="lower the Job's memory request or add a node that can fit it",
        events=(
            ("FailedScheduling",
             ("0/{nodes} nodes are available: {nodes} Insufficient memory. preemption: 0/{nodes} nodes are "
              "available: {nodes} Preemption is not helpful for scheduling."), 5),
        ),
        own_cause_must_not=("cordon", "pressure"),
        answer=Answer(
            anchor="insufficient memory",
            cause="the pod's memory request is larger than any node can allocate",
            keys=("memory", "node"),
            rationale="The scheduler rejects all {nodes} nodes for insufficient memory, so the pod's "
                      "memory request is larger than any node can give."),
        none_phrase="its pod cannot be scheduled",
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
        answer=Answer(
            anchor="log cause: bad command or entrypoint",
            cause="the container's command or entrypoint is wrong and it exits immediately",
            keys=("entrypoint", "exit"),
            rationale="The container keeps exiting after it starts, and its previous log "
                      "classifies as a bad command or entrypoint."),
        none_phrase="its container keeps crashing",
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
