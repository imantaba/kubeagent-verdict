"""Kind-keyed catalog entries — one per issue kind no slug entry covers (11 when complete)."""

from kubeagent_verdict.dataset.catalog import CatalogEntry

ENTRIES = [
    CatalogEntry(
        key="probe-failure",
        covered_slugs=(),
        covered_kinds=("ProbeFailure",),
        trains=True,
        workload_kind="Deployment",
        status="Degraded",
        issue="ProbeFailure",
        reason="readiness probe failing",
        evidence="Readiness probe failed: HTTP probe failed with statuscode: 500",
        next_step="check what the probe endpoint returns and why",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="application failing its readiness probe",
        winner_reason="the probe returns HTTP 500 while the container keeps running",
        losers=(
            ("recent rollout introduced a bad revision", "outranked",
             "no rollout occurred in the lookback window"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("12s Warning Unhealthy pod/{pod} Readiness probe failed: HTTP probe failed "
              "with statuscode: 500\n"
              "42s Warning Unhealthy pod/{pod} Readiness probe failed: HTTP probe failed "
              "with statuscode: 500\n")),
        ),
        rationale="The probe consistently returns HTTP 500 with no restart or rollout, so the "
                  "application itself is unhealthy behind a running container.",
        direct=False,
        contradiction="LAST SEEN  TYPE    REASON   MESSAGE\n"
                      "30s        Normal  Started  Started container {container}\n"
                      "8s         Normal  Killing  Stopping container {container} "
                      "(node {node} shutting down)\n",
        own_cause="the application answers its readiness endpoint with errors",
        own_cause_keywords=("readiness", "500"),
        service_issue=("NoReadyEndpoints", "service has 0 ready endpoints"),
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
        next_step="check the image's command/entrypoint against what actually ships in the image",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="the image's command names an executable that does not exist in the image",
        winner_reason="the kubelet's own StartError names the missing executable path directly",
        losers=(
            ("the node's container runtime is unhealthy", "ruled_out",
             "other pods start normally on the same node"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              '  Failed: Error: StartError: exec: "/app/server": no such file or directory '
              "(x3)\n")),
        ),
        rationale="The kubelet's own StartError waiting message names the missing executable "
                  "path directly, and other pods on the same node start normally, so the image's "
                  "entrypoint is the cause rather than the node.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      "  Failed: Error: StartError: OCI runtime create failed: runc did not "
                      "terminate successfully (x3)\n",
        own_cause="the container's entrypoint names a path that does not exist in the image",
        own_cause_keywords=("entrypoint", "exec"),
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
        evidence="container {container}: couldn't find key API_TOKEN in ConfigMap {ns}/app-config",
        next_step="add the missing key to the ConfigMap or fix the key name in the pod spec",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="the pod spec references a ConfigMap key that does not exist",
        winner_reason="the kubelet's waiting message names the exact missing key",
        losers=(
            ("the ConfigMap itself is missing", "ruled_out",
             "kubectl get configmap shows the ConfigMap exists, just without that key"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  Failed: Error: CreateContainerConfigError: couldn't find key API_TOKEN in "
              "ConfigMap {ns}/app-config (x2)\n")),
        ),
        rationale="The waiting message names the exact key the container needs, and the "
                  "ConfigMap itself is present without that key, so the reference is stale "
                  "rather than the object missing.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      "  Failed: Error: CreateContainerConfigError: configmap app-config not "
                      "found (x2)\n",
        own_cause="the pod spec references a ConfigMap key that was never added or was renamed",
        own_cause_keywords=("configmap", "key"),
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
        log_cause="log cause: cannot reach a dependency — connection refused",
        next_step="check what the init container is waiting for and why it cannot reach it",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="the init container cannot reach the dependency it waits for",
        winner_reason="the previous-instance log classifies as a refused connection on every "
                      "restart",
        losers=(
            ("the init container's own script is broken", "ruled_out",
             "the same script runs to completion once the dependency is reachable"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  BackOff: Back-off restarting failed container {init_container} in pod {pod} "
              "(x{restarts})\n")),
        ),
        rationale="The init container's previous log classifies as a connection refused on "
                  "every restart, and the pod never gets past PodInitializing, which points at "
                  "the dependency it waits for rather than its own script.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      "  Started: Started container {init_container} (x1)\n",
        own_cause="the init container cannot reach a dependency it waits for before the pod "
                  "can start",
        own_cause_keywords=("init", "dependency"),
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
        evidence="init container {init_container} (1/2): secret migration-creds not found",
        next_step="create the missing Secret or fix its name in the init container's spec",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="a Secret the init container references does not exist",
        winner_reason="the kubelet's waiting message names the missing Secret directly",
        losers=(
            ("the Secret exists but a key inside it is missing", "ruled_out",
             "kubectl get secret shows no Secret of that name in the namespace at all"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  Failed: Error: CreateContainerConfigError: secret migration-creds not found "
              "(x2)\n")),
        ),
        rationale="The waiting message names a Secret that kubectl get secret confirms does not "
                  "exist in the namespace at all, which rules out a missing key inside an "
                  "otherwise-present Secret.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      "  Failed: Error: CreateContainerConfigError: couldn't find key "
                      "DB_PASSWORD in Secret {ns}/migration-creds (x2)\n",
        own_cause="a Secret the init container references was never created in this namespace",
        own_cause_keywords=("secret", "init"),
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
        evidence='init container "{init_container}": Failed to pull image '
                 '"registry.example.com/shop/migrate:v0.9.0": not found',
        next_step="fix the init image's tag or push the missing image",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="the init image's tag does not exist in the registry",
        winner_reason="the pull error names the init image's tag as missing, and the main image "
                      "pulls fine",
        losers=(
            ("the registry is unreachable from the node", "ruled_out",
             "the main container's image pulls from the same registry moments later"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              '  Failed: Failed to pull image "registry.example.com/shop/migrate:v0.9.0": '
              "not found (x1)\n")),
        ),
        rationale="The pull error names the init image's own tag as missing, and the workload's "
                  "main image pulls successfully from the same registry, so the tag is wrong "
                  "rather than the registry being unreachable.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      '  Failed: Failed to pull image "registry.example.com/shop/migrate:v0.9.0": '
                      "dial tcp: i/o timeout (x1)\n",
        own_cause="the init container's image tag does not exist in the registry",
        own_cause_keywords=("tag", "registry"),
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
        evidence='init container "{init_container}": Back-off pulling image '
                 '"registry.example.com/shop/migrate:v0.9.0"',
        next_step="fix the init image's tag or push the missing image",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="the init image's tag does not exist in the registry",
        winner_reason="the kubelet has been backing off the same pull error since the first "
                      "attempt",
        losers=(
            ("the registry is unreachable from the node", "ruled_out",
             "the main container's image pulls from the same registry moments later"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              '  BackOff: Back-off pulling image "registry.example.com/shop/migrate:v0.9.0" '
              "(x6)\n")),
        ),
        rationale="The kubelet has been backing off the same pull error since the first "
                  "attempt, and the main image pulls fine from the same registry, so the init "
                  "image's own tag is wrong.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      "  Pulled: Successfully pulled image "
                      '"registry.example.com/shop/migrate:v0.9.0" (x1)\n',
        own_cause="the init container's image tag does not exist in the registry",
        own_cause_keywords=("tag", "backoff"),
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
        next_step="raise the init container's memory limit or stream the migration instead of "
                  "loading it whole",
        command="kubectl -n {ns} describe pod {pod}",
        resources=("32Mi", "32Mi", "50m", "100m"),
        winner_cause="the init container's memory limit is too small for the migration it runs",
        winner_reason="the init container is OOMKilled at its 32Mi limit on every attempt",
        losers=(
            ("node {node} under memory pressure", "ruled_out",
             "the node reports no MemoryPressure condition"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  BackOff: Back-off restarting failed container {init_container} in pod {pod} "
              "(x3)\n")),
        ),
        rationale="The init container is OOMKilled at its own 32Mi limit on every attempt, and "
                  "the node reports no memory pressure, so the limit itself is undersized for "
                  "the migration.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      "  Failed: Error: OCI runtime create failed: runc did not terminate "
                      "successfully (x3)\n",
        own_cause="the init container's memory limit is too small for the work it does at "
                  "startup",
        own_cause_keywords=("memory", "init"),
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
        evidence="container {container}, {restarts} restarts, last exit 1 (Error), 90s ago",
        log_cause="log cause: application panic (code bug)",
        next_step="check the previous log for the panic and what request triggered it",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="the container panics intermittently under load",
        winner_reason="the previous-instance log carries a panic trace, and the restarts "
                      "cluster around the pod's busiest periods",
        losers=(
            ("a liveness probe restarting a healthy container", "ruled_out",
             "no liveness probe is configured on this container"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  BackOff: Back-off restarting failed container {container} in pod {pod} "
              "(x{restarts})\n")),
        ),
        rationale="The previous-instance log carries a panic trace and the restarts cluster "
                  "around load, and no liveness probe is configured to explain the restarts "
                  "instead, so the panic is the likelier cause though the correlation with load "
                  "is inferred rather than directly observed.",
        direct=False,
        contradiction="events for {ns}/{pod}:\n"
                      "  Unhealthy: Liveness probe failed: HTTP probe failed with statuscode: "
                      "503 (x{restarts})\n",
        own_cause="the container panics intermittently, most often under load",
        own_cause_keywords=("panic", "restart"),
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
        next_step="wait for the old node's attachment to release, or force-detach if that node "
                  "is gone",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="the PVC is still attached to the node the previous pod ran on",
        winner_reason="the FailedAttachVolume event names Multi-Attach, and the PVC describes "
                      "as still Bound to the old node's attachment",
        losers=(
            ("the CSI driver on the new node is unhealthy", "ruled_out",
             "the driver's own pod on the new node reports Running and Ready"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  FailedAttachVolume: Multi-Attach error for volume {pvc} Volume is already "
              "exclusively attached to one node and can't be attached to another (x8)\n")),
            ("describe pvc {ns}/{pvc}",
             "pvc {ns}/{pvc}: phase=Bound storageClass=fast-ssd volume=pv-0821\n"),
        ),
        rationale="The FailedAttachVolume event names Multi-Attach directly, and the PVC still "
                  "describes as Bound while the new node's CSI driver itself reports healthy, "
                  "which points at the stale attachment rather than the driver.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      "  FailedAttachVolume: rpc error: code = Internal desc = CSI driver not "
                      "responding (x8)\n",
        own_cause="the PVC is still attached to the node the previous pod ran on",
        own_cause_keywords=("multi-attach", "volume"),
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
        evidence="Unable to attach or mount volumes: unmounted volumes=[data], timed out "
                 "waiting for the condition",
        next_step="check the CSI driver and the underlying volume's health on {node}",
        command="kubectl -n {ns} describe pod {pod}",
        winner_cause="the PVC's underlying volume is unhealthy on node {node}",
        winner_reason="the mount times out repeatedly while the PVC itself describes as Bound",
        losers=(
            ("a ConfigMap or Secret volume source is missing", "ruled_out",
             "the pod's only volume is the PVC {pvc}; no ConfigMap or Secret volume is defined"),
        ),
        reads=(
            ("events {ns}/{pod}",
             ("events for {ns}/{pod}:\n"
              "  FailedMount: Unable to attach or mount volumes: unmounted volumes=[data], "
              "timed out waiting for the condition (x5)\n")),
            ("describe pvc {ns}/{pvc}",
             "pvc {ns}/{pvc}: phase=Bound storageClass=fast-ssd volume=pv-0821\n"),
        ),
        rationale="The mount times out repeatedly while the PVC itself already describes as "
                  "Bound and the pod defines no ConfigMap or Secret volume, which points at the "
                  "underlying volume on {node} rather than a missing object.",
        direct=True,
        contradiction="events for {ns}/{pod}:\n"
                      '  FailedMount: MountVolume.SetUp failed for volume "config": configmap '
                      '"app-config" not found (x5)\n',
        own_cause="the PVC's underlying volume is unhealthy or unreachable on the pod's node",
        own_cause_keywords=("mount", "timeout"),
    ),
]
