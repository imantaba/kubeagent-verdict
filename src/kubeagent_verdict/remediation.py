"""Mirror of kubeagent's internal/remediation.For — the deterministic
suggestion that fills a finding's `suggested fix` line.

Provenance: internal/remediation/remediation.go in the kubeagent repository.
kubeagent never lets a model choose this string; it switches on the finding's
issue kind and returns one of a fixed set. This module reproduces that switch
so a synthesised training prompt carries the same string the real binary would
have carried for the same issue.

Why it is a mirror and not a hand-written table: the field is an *input* to the
model, and the model learns what it means from how it varies. A catalog author
writing a more helpful, more specific string than kubeagent emits does not make
the training data better — it makes the field mean one thing in training and a
different thing at serve time, and the model reads it either way.

Keep this in step with the Go source. tests/test_remediation.py anchors the
covered arms against contract/golden/, which is captured from the real binary
rather than transcribed from the Go, so a drift in the anchored arms is caught
without trusting this file's author.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Suggestion:
    next_step: str
    command: str


def _logs(ns: str, pod: str, container: str) -> str:
    c = f" -c {container}" if container else ""
    return f"kubectl -n {ns} logs {pod}{c} --previous"


def _describe(ns: str, pod: str) -> str:
    return f"kubectl -n {ns} describe pod {pod}"


def _events(ns: str, name: str) -> str:
    return f"kubectl -n {ns} get events --field-selector involvedObject.name={name}"


def suggest(issue: str, *, ns: str, pod: str, container: str = "",
            kind: str = "") -> Suggestion:
    """Return the suggestion kubeagent would render for this finding."""
    if issue in ("CrashLoopBackOff", "RestartLoop"):
        return Suggestion("starts then crashes — inspect the crash output",
                          _logs(ns, pod, container))
    if issue in ("ImagePullBackOff", "ErrImagePull"):
        return Suggestion("the image can't be pulled — verify the tag exists and the "
                          "registry credentials", _describe(ns, pod))
    if issue == "OOMKilled":
        return Suggestion("the container exceeded its memory limit — raise the limit "
                          "or fix the leak", _describe(ns, pod))
    if issue == "Unschedulable":
        return Suggestion("no node can place the pod — check resource requests, "
                          "taints, and affinity", _describe(ns, pod))
    if issue in ("CreateContainerConfigError", "Init:CreateContainerConfigError"):
        return Suggestion("a referenced ConfigMap or Secret is missing — create it or "
                          "fix the reference", _describe(ns, pod))
    if issue == "ProbeFailure":
        return Suggestion("the probe keeps failing — check the probe config and the "
                          "app's health endpoint", _describe(ns, pod))
    if issue == "VolumeAttachError":
        return Suggestion("the volume can't attach — check the PVC/PV binding and the "
                          "CSI driver", _describe(ns, pod))
    if issue == "VolumeMountError":
        return Suggestion("a mounted ConfigMap or Secret is missing — create it or fix "
                          "the volume", _describe(ns, pod))
    if issue in ("Init:ImagePullBackOff", "Init:ErrImagePull"):
        return Suggestion("an init container's image can't be pulled — the pod cannot "
                          "start; verify the tag and registry credentials",
                          _describe(ns, pod))
    if issue in ("Init:CrashLoopBackOff", "Init:OOMKilled"):
        return Suggestion("an init container is failing — the pod cannot start until "
                          "it succeeds", _logs(ns, pod, container))
    if issue == "FailedCreate":
        return Suggestion("the controller can't create pods — check for quota, "
                          "LimitRange, or a rejecting admission webhook",
                          f"kubectl -n {ns} get events --field-selector reason=FailedCreate")
    if issue == "JobFailed":
        if kind == "CronJob":
            return Suggestion("the most recent scheduled run failed — inspect that run "
                              "and the schedule",
                              f"kubectl -n {ns} describe cronjob {pod}")
        return Suggestion("the Job exhausted its retries — inspect the failed pod's logs",
                          f"kubectl -n {ns} logs job/{pod}")
    if issue == "RolloutStuck":
        return Suggestion("the rollout is wedged — inspect the workload's pods and its "
                          "events", _events(ns, pod))
    return Suggestion("inspect the object for details", _describe(ns, pod))


#: Every next_step string suggest() can return. The fidelity guard in
#: tests/test_dataset_suggestions.py checks rendered prompts against this set.
VOCABULARY = frozenset(
    suggest(i, ns="n", pod="p", container="c", kind=k).next_step
    for i in ("CrashLoopBackOff", "ImagePullBackOff", "OOMKilled", "Unschedulable",
              "CreateContainerConfigError", "ProbeFailure", "VolumeAttachError",
              "VolumeMountError", "Init:ImagePullBackOff", "Init:CrashLoopBackOff",
              "FailedCreate", "JobFailed", "RolloutStuck", "?unknown?")
    for k in ("", "CronJob")
)
