"""Kind-keyed catalog entries — one per issue kind no slug entry covers (11 when complete)."""

from kubeagent_verdict.dataset.catalog import CatalogEntry

ENTRIES = [
    CatalogEntry(
        key="probe-failure",
        covered_slugs=(),
        covered_kinds=("ProbeFailure",),
        trains=True,
        workload_kind="Deployment",
        status="Available",
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
]
