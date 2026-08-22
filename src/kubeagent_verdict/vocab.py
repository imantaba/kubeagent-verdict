"""Closed vocabularies shared by loaders, catalog, and generator.

FAULT_SLUGS mirrors kubeagent's chaos/run.sh scenario_fault table (23
scenarios, 17 distinct slugs; "unknown-scenario" is that table's never-fail
fallback and is deliberately NOT admitted here — a corpus row carrying it is
withheld). ISSUE_KINDS mirrors kubeagent's internal/knownissues 16-kind
reference. VERDICTS mirrors internal/inventory's attribution verdicts.
"""

FAULT_SLUGS = frozenset({
    "control-plane-docker-stop",
    "control-plane-cert-expiry",
    "node-cordon-diskfull",
    "networkpolicy-deny-all",
    "coredns-corefile-broken",
    "loadbalancer-no-provider",
    "memory-limit-oomkill",
    "namespace-deletion",
    "deployment-bad-image-tag",
    "configmap-aws-key-leak",
    "worker-containerd-stop",
    "certmanager-bad-issuer-ref",
    "flux-gitrepo-dns-failure",
    "oversized-job-unschedulable",
    "crashloop-pod",
    "no-fault-healthy-readyz",
    "coredns-servfail-template",
})

ISSUE_KINDS = frozenset({
    "ContainerStartError",
    "CrashLoopBackOff",
    "CreateContainerConfigError",
    "ErrImagePull",
    "ImagePullBackOff",
    "Init:CrashLoopBackOff",
    "Init:CreateContainerConfigError",
    "Init:ErrImagePull",
    "Init:ImagePullBackOff",
    "Init:OOMKilled",
    "OOMKilled",
    "ProbeFailure",
    "RestartLoop",
    "Unschedulable",
    "VolumeAttachError",
    "VolumeMountError",
})

VERDICTS = frozenset({"attributed", "ruled_out", "outranked"})
