"""Slug-keyed catalog entries — one per chaos fault slug (17 when complete)."""

from kubeagent_verdict.dataset.catalog import CatalogEntry

ENTRIES = [
    CatalogEntry(
        key="memory-limit-oomkill",
        covered_slugs=("memory-limit-oomkill",),
        covered_kinds=("OOMKilled",),
        trains=True,
        workload_kind="Deployment",
        status="Progressing",
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
        status="Progressing",
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
]
