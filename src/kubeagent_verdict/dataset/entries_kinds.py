"""Kind-keyed catalog entries — one per issue kind no slug entry covers (11),
then `pvc-unbound-unschedulable`, which covers neither a slug nor a kind."""

from kubeagent_verdict.dataset.catalog import INIT_CONTAINER, CatalogEntry
from kubeagent_verdict.dataset.objects import NODE_NOT_READY, Fresh, Object
from kubeagent_verdict.dataset.stories import Answer

_UNBOUND_CLAIM = ("0/3 nodes are available: pod has unbound immediate PersistentVolumeClaims. "
                  "preemption: 0/3 nodes are available: 3 Preemption is not helpful for "
                  "scheduling.")

ENTRIES = [
    CatalogEntry(
        key="probe-failure",
        covered_slugs=(),
        covered_kinds=("ProbeFailure",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="ProbeFailure",
        reason="the readiness probe keeps failing — the pod is kept out of Service endpoints",
        evidence='container "{container}": readiness probe failed — HTTP 500',
        recommendation="check what the probe endpoint returns and why",
        # Two identical table rows (12s and 42s ago): one event, counted twice.
        events=(
            ("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 500", 2),
        ),
        contradiction_events=(
            ("Started", "Started container {container}", 1),
            ("Killing", "Stopping container {container} (node {node} shutting down)", 1),
        ),
        rationale="The probe consistently returns HTTP 500 with no restart or rollout, so the "
                  "application itself is unhealthy behind a running container.",
        direct=False,
        own_cause="the application answers its readiness endpoint with errors",
        own_cause_keywords=("readiness", "endpoint"),
        answer=Answer(
            anchor="http 500",
            cause="the application answers its readiness endpoint with errors",
            keys=("readiness", "endpoint"),
            rationale="The readiness probe fails with HTTP 500, so the application answers its "
                      "health endpoint with an error."),
        none_phrase="its readiness probe fails",
        service_issue=("NoReadyEndpoints", "service has 0 ready endpoints"),
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
    ),
    CatalogEntry(
        key="container-start-error",
        covered_slugs=(),
        covered_kinds=("ContainerStartError",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="ContainerStartError",
        reason="the container image was resolved but the container could not be started",
        evidence='container "{container}": StartError: exec: "/app/server": no such file or '
                 "directory",
        recommendation="check the image's command/entrypoint against what actually ships in the image",
        events=(
            ("Failed", 'Error: StartError: exec: "/app/server": no such file or directory', 3),
        ),
        contradiction_events=(
            ("Failed",
             "Error: StartError: OCI runtime create failed: runc did not terminate successfully",
             3),
        ),
        rationale="The kubelet's own StartError waiting message names the missing executable "
                  "path directly, and other pods on the same node start normally, so the image's "
                  "entrypoint is the cause rather than the node.",
        direct=True,
        own_cause="the container's entrypoint names a path that does not exist in the image",
        own_cause_keywords=("container", "image"),
        own_cause_must_not=(*INIT_CONTAINER, "tag"),
        answer=Answer(
            anchor="no such file or directory",
            cause="the container's entrypoint names a path that does not exist in the image",
            keys=("container", "image"),
            rationale="The container cannot start: its entrypoint path gives \"no such file or "
                      "directory\", so that path is not in the image."),
        none_phrase="its container fails to start",
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
    ),
    CatalogEntry(
        key="create-container-config-error",
        covered_slugs=(),
        covered_kinds=("CreateContainerConfigError",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="CreateContainerConfigError",
        reason="a referenced ConfigMap or Secret is missing, or a required key is absent — the "
               "container cannot start",
        evidence='container "{container}": couldn\'t find key API_TOKEN in ConfigMap '
                 "{ns}/app-config",
        recommendation="add the missing key to the ConfigMap or fix the key name in the pod spec",
        events=(
            ("Failed",
             ("Error: CreateContainerConfigError: couldn't find key API_TOKEN in ConfigMap "
              "{ns}/app-config"), 2),
        ),
        contradiction_events=(
            ("Failed", "Error: CreateContainerConfigError: configmap app-config not found", 2),
        ),
        rationale="The waiting message names the exact key the container needs, and the "
                  "ConfigMap itself is present without that key, so the reference is stale "
                  "rather than the object missing.",
        direct=True,
        own_cause="the pod spec references a ConfigMap key that was never added or was renamed",
        own_cause_keywords=("configmap", "key"),
        answer=Answer(
            anchor="couldn't find key",
            cause="the pod spec references a ConfigMap key that was never added or was renamed",
            keys=("configmap", "key"),
            rationale="The kubelet couldn't find the key the container needs in the ConfigMap it "
                      "names, so the pod spec points at a key that is not there."),
        none_phrase="its container fails to start",
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
    ),
    CatalogEntry(
        key="init-crashloop",
        covered_slugs=(),
        covered_kinds=("Init:CrashLoopBackOff",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="Init:CrashLoopBackOff",
        reason="an init container is crash-looping — the pod cannot start its main containers",
        evidence='init container "{init_container}" (1/2), restartCount={restarts}',
        log_cause="cannot reach a dependency — connection refused",
        recommendation="check what the init container is waiting for and why it cannot reach it",
        events=(
            ("BackOff", "Back-off restarting failed container {init_container} in pod {pod}",
             "{restarts}"),
        ),
        contradiction_events=(
            ("Started", "Started container {init_container}", 1),
        ),
        rationale="The init container's previous log classifies as a connection refused on "
                  "every restart, and the pod never gets past PodInitializing, which points at "
                  "the dependency it waits for rather than its own script.",
        direct=True,
        own_cause="the init container cannot reach a dependency it waits for before the pod "
                  "can start",
        own_cause_keywords=("init", "dependency"),
        answer=Answer(
            anchor="log cause: cannot reach a dependency",
            cause="the init container cannot reach a dependency it waits for before the pod can "
                  "start",
            keys=("init", "dependency"),
            rationale="The init container keeps crashing, and its previous log classifies as "
                      "connection refused, so it cannot reach a dependency it waits for."),
        none_phrase="its init container keeps crashing",
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
    ),
    CatalogEntry(
        key="init-config-error",
        covered_slugs=(),
        covered_kinds=("Init:CreateContainerConfigError",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="Init:CreateContainerConfigError",
        reason="an init container's ConfigMap or Secret is missing, or a required key is "
               "absent — the pod cannot start",
        evidence='init container "{init_container}" (1/2): secret migration-creds not found',
        recommendation="create the missing Secret or fix its name in the init container's spec",
        events=(
            ("Failed", "Error: CreateContainerConfigError: secret migration-creds not found", 2),
        ),
        contradiction_events=(
            ("Failed",
             ("Error: CreateContainerConfigError: couldn't find key DB_PASSWORD in Secret "
              "{ns}/migration-creds"), 2),
        ),
        rationale="The waiting message names a Secret that kubectl get secret confirms does not "
                  "exist in the namespace at all, which rules out a missing key inside an "
                  "otherwise-present Secret.",
        direct=True,
        own_cause="a Secret the init container references was never created in this namespace",
        own_cause_keywords=("secret", "init"),
        answer=Answer(
            anchor="secret migration-creds not found",
            cause="a Secret the init container references does not exist",
            keys=("secret", "init"),
            rationale="The init container cannot start because the Secret it references is not "
                      "found."),
        none_phrase="its init container fails to start",
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
    ),
    CatalogEntry(
        key="init-errimagepull",
        covered_slugs=(),
        covered_kinds=("Init:ErrImagePull",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="Init:ErrImagePull",
        reason="an init container's image cannot be pulled — the pod cannot start",
        evidence='init container "{init_container}" (1/2): Failed to pull image '
                 '"registry.example.com/shop/migrate:v0.9.0": not found',
        recommendation="fix the init image's tag or push the missing image",
        events=(
            ("Failed",
             'Failed to pull image "registry.example.com/shop/migrate:v0.9.0": not found', 1),
        ),
        contradiction_events=(
            ("Failed",
             'Failed to pull image "registry.example.com/shop/migrate:v0.9.0": dial tcp: i/o timeout',
             1),
        ),
        rationale="The pull error names the init image's own tag as missing, and the workload's "
                  "main image pulls successfully from the same registry, so the tag is wrong "
                  "rather than the registry being unreachable.",
        direct=True,
        own_cause="the init container's image tag does not exist in the registry",
        own_cause_keywords=("init", "registry", "tag"),
        answer=Answer(
            anchor="\": not found",
            cause="the init container's image tag does not exist in the registry",
            keys=("init", "registry", "tag"),
            rationale="The init container's image pull fails with \"not found\", so its tag does "
                      "not exist in the registry."),
        none_phrase="its init container's image cannot be pulled",
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
    ),
    CatalogEntry(
        key="init-imagepullbackoff",
        covered_slugs=(),
        covered_kinds=("Init:ImagePullBackOff",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="Init:ImagePullBackOff",
        reason="an init container's image cannot be pulled — the pod cannot start",
        evidence='init container "{init_container}" (1/2): Back-off pulling image '
                 '"registry.example.com/shop/migrate:v0.9.0"',
        recommendation="check the init image's tag and the registry credentials",
        events=(
            ("BackOff", 'Back-off pulling image "registry.example.com/shop/migrate:v0.9.0"', 6),
        ),
        contradiction_events=(
            ("Pulled", 'Successfully pulled image "registry.example.com/shop/migrate:v0.9.0"', 1),
        ),
        rationale="The kubelet has been backing off the same pull error since the first "
                  "attempt, and the main image pulls fine from the same registry, so the init "
                  "image's own tag is wrong.",
        direct=True,
        own_cause="the init container's image tag does not exist in the registry",
        own_cause_keywords=("init", "tag", "registry"),
        answer=Answer(
            anchor="back-off pulling image",
            cause="the init container's image cannot be pulled, and the kubelet keeps backing off",
            keys=("init", "pull"),
            rationale="The kubelet keeps backing off pulling the init container's image, so the "
                      "pod cannot start. Its own lines do not say why the pull fails."),
        none_phrase="its init container's image cannot be pulled",
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
    ),
    CatalogEntry(
        key="init-oomkilled",
        covered_slugs=(),
        covered_kinds=("Init:OOMKilled",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="Init:OOMKilled",
        reason="an init container was killed for exceeding its memory limit — the pod cannot "
               "start",
        evidence='init container "{init_container}" (1/2), exitCode=137',
        recommendation="raise the init container's memory limit",
        resources=("32Mi", "32Mi", "50m", "100m"),
        events=(
            ("BackOff", "Back-off restarting failed container {init_container} in pod {pod}", 3),
        ),
        contradiction_events=(
            ("Failed", "Error: OCI runtime create failed: runc did not terminate successfully", 3),
        ),
        rationale="The init container is OOMKilled at its own 32Mi limit on every attempt, and "
                  "the node reports no memory pressure, so the limit itself is undersized for "
                  "the migration.",
        direct=True,
        own_cause="the init container's memory limit is too small for the work it does at "
                  "startup",
        own_cause_keywords=("memory", "init"),
        answer=Answer(
            anchor="init:oomkilled",
            cause="the init container is killed at its memory limit",
            keys=("memory", "init"),
            rationale="The init container is OOMKilled with exit code 137, so it is killed at its "
                      "own memory limit."),
        none_phrase="its init container keeps being killed for memory",
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
    ),
    CatalogEntry(
        key="restart-loop",
        covered_slugs=(),
        covered_kinds=("RestartLoop",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="RestartLoop",
        reason="Container keeps exiting with an error and restarting",
        evidence='container "{container}", {restarts} restarts, last exit 1 (Error), 1m30s ago',
        log_cause="application panic (code bug)",
        recommendation="check the previous log for the panic",
        events=(
            ("BackOff", "Back-off restarting failed container {container} in pod {pod}",
             "{restarts}"),
        ),
        contradiction_events=(
            ("Unhealthy", "Liveness probe failed: HTTP probe failed with statuscode: 503",
             "{restarts}"),
        ),
        rationale="The previous-instance log carries a panic trace and the restarts cluster "
                  "around load, and no liveness probe is configured to explain the restarts "
                  "instead, so the panic is the likelier cause though the correlation with load "
                  "is inferred rather than directly observed.",
        direct=False,
        own_cause="the container panics intermittently, most often under load",
        own_cause_keywords=("panic", "container"),
        answer=Answer(
            anchor="log cause: application panic",
            cause="the container panics (a code bug) and keeps restarting",
            keys=("panic", "container"),
            rationale="The container keeps exiting with an error, and its previous log classifies "
                      "as an application panic."),
        none_phrase="its container keeps restarting",
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
        min_restarts=3,
    ),
    CatalogEntry(
        key="volume-attach-error",
        covered_slugs=(),
        covered_kinds=("VolumeAttachError",),
        trains=True,
        workload_kind="StatefulSet",
        status="Degraded",
        issue="VolumeAttachError",
        reason="the volume is attached to another node (Multi-Attach) — the pod cannot mount it",
        evidence="Multi-Attach error for volume {pvc} Volume is already exclusively attached to "
                 "one node and can't be attached to another",
        recommendation="wait for the old node's attachment to release, or force-detach if that node "
                  "is gone",
        events=(
            ("FailedAttachVolume",
             ("Multi-Attach error for volume {pvc} Volume is already exclusively attached to "
              "one node and can't be attached to another"), 8),
        ),
        contradiction_events=(
            ("FailedAttachVolume", "rpc error: code = Internal desc = CSI driver not responding",
             8),
        ),
        rationale="The FailedAttachVolume event names Multi-Attach directly, and the PVC still "
                  "describes as Bound while the new node's CSI driver itself reports healthy, "
                  "which points at the stale attachment rather than the driver.",
        direct=True,
        own_cause="the PVC is still attached to the node the previous pod ran on",
        own_cause_keywords=("attached", "node"),
        answer=Answer(
            anchor="multi-attach error",
            cause="the volume is still attached to another node",
            keys=("attached", "node"),
            rationale="Attaching fails with a multi-attach error: the volume is already attached "
                      "to another node."),
        none_phrase="its volume cannot attach",
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
    ),
    CatalogEntry(
        key="volume-mount-error",
        covered_slugs=(),
        covered_kinds=("VolumeMountError",),
        trains=True,
        workload_kind="StatefulSet",
        status="Degraded",
        issue="VolumeMountError",
        reason="a volume the pod needs could not be mounted — the pod cannot start",
        evidence="Unable to attach or mount volumes: unmounted volumes=[data], unattached "
                 "volumes=[], failed to process volumes=[]: timed out waiting for the condition",
        recommendation="check why the volume does not mount on the pod's node",
        events=(
            ("FailedMount",
             ("Unable to attach or mount volumes: unmounted volumes=[data], unattached "
              "volumes=[], failed to process volumes=[]: timed out waiting for the condition"),
             5),
        ),
        contradiction_events=(
            ("FailedMount",
             'MountVolume.SetUp failed for volume "config": configmap "app-config" not found', 5),
        ),
        rationale="The mount times out repeatedly while the PVC itself already describes as "
                  "Bound and the pod defines no ConfigMap or Secret volume, which points at the "
                  "underlying volume on {node} rather than a missing object.",
        direct=True,
        own_cause="the PVC's underlying volume is unhealthy or unreachable on the pod's node",
        own_cause_keywords=("volume", "pod"),
        own_cause_must_not=("provision",),
        answer=Answer(
            anchor="issue: volumemounterror",
            cause="the pod's volume times out while mounting on its node",
            keys=("volume", "pod"),
            rationale="Mounting the pod's volume times out waiting for the condition, so the "
                      "volume does not mount on its node."),
        none_phrase="its volume cannot be mounted",
        objects=(
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=NODE_NOT_READY, intent="decoy"),
        ),
    ),
    # The one job-1 entry whose winner is a claim. It covers no slug and no
    # kind, and sits last in the catalog so every other entry keeps its
    # place in `trainable()`.
    CatalogEntry(
        key="pvc-unbound-unschedulable",
        covered_slugs=(),
        covered_kinds=(),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="Unschedulable",
        reason="No node can schedule this pod",
        evidence=_UNBOUND_CLAIM,
        recommendation="check why the pod's claim has no bound volume yet",
        # The pod's own event only. kubeagent reads a pod's events by its name
        # (FieldSelector "involvedObject.name=" + name,
        # internal/investigate/reader.go:302), and the volume controller
        # records ProvisioningFailed on the claim, not on the pod. So the
        # events read shows the scheduler's FailedScheduling and never
        # ProvisioningFailed. The storage class still reaches the prompt: in
        # the candidate line's MissingStorageClass and in the claim's describe.
        events=(("FailedScheduling", _UNBOUND_CLAIM, 5),),
        # Every row shows the events line; the describe and the candidate's
        # verdict differ by case, so the rationale cites the events line only.
        rationale="The scheduler's FailedScheduling event says the pod has unbound immediate "
                  "PersistentVolumeClaims, so the pod cannot be placed until the claim it "
                  "mounts gets a volume.",
        direct=True,
        own_cause="a claim the pod mounts is still waiting for its volume to be provisioned",
        own_cause_keywords=("claim", "volume"),
        answer=Answer(
            anchor="unbound immediate persistentvolumeclaims",
            cause="a claim the pod mounts is still waiting for its volume to be provisioned",
            keys=("claim", "volume"),
            rationale="The scheduler says the pod has unbound immediate PersistentVolumeClaims, "
                      "so a claim it mounts has no volume yet."),
        none_phrase="its pod cannot be scheduled",
        objects=(
            Object(kind="pvc", name="{pvc}", scan_reason="MissingStorageClass",
                   placement="mounted", fresh=Fresh(phase="Pending", storage_class="fast-ssd"),
                   intent="cause"),
        ),
    ),
]
