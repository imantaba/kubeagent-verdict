"""The eval six's job-2 grading keywords.

Sixteen victims and six shared causes, one curated pair each. Three
properties, and the second and third are the ones that matter:

- COVERAGE: every eval scenario and victim carries a pair, so no exam
  workload can fall back to the empty list that scored 20 of them 0.0
  whatever the model answered.
- SELF-CONTAINMENT: each keyword is a substring of its own cause. A typo
  here would make the workload unanswerable -- the exact defect being
  fixed, re-introduced one layer up.
- DISCRIMINATION: a pair must not appear in full in any OTHER cause on the
  same menu. Spec section 3 measured what happens without this: a pair of
  `node`,`worker-3` scored `node worker-3 (no kubelet lease)` as correct
  against a gold answer about disk pressure.

The twin leg of the discrimination check is the one spec section 9 names:
a shared-origin workload's gold answer is its own local cause in the
healthy world and the scenario's shared cause in the broken one, so those
two strings are each other's twin and a pair that cannot tell them apart
grades both worlds the same.
"""
from kubeagent_verdict.dataset import propagation as prop


def test_every_eval_scenario_and_victim_carries_a_keyword_pair():
    for p in prop.all_scenarios():
        assert len(p.own_cause_keywords) == 2, p.key
        for v in p.victims:
            assert len(v.own_cause_keywords) == 2, (p.key, v.local_cause)


def test_every_eval_keyword_appears_in_its_own_cause():
    for p in prop.all_scenarios():
        shared = p.shared_cause.lower()
        for k in p.own_cause_keywords:
            assert k == k.lower(), (p.key, k)
            assert k in shared, (p.key, k)
        for v in p.victims:
            local = v.local_cause.lower()
            for k in v.own_cause_keywords:
                assert k == k.lower(), (p.key, k)
                assert k in local, (p.key, v.local_cause, k)


def test_every_eval_keyword_pair_discriminates_on_its_own_menu():
    """No pair matches in full any other cause the same menu prints.

    The menu is three candidates: the victim's own local cause
    (`attributed`), the scenario's distractor, and the shared cause. A
    scenario's victims also share a prompt, so a victim's pair is checked
    against its siblings' causes too.
    """
    for p in prop.all_scenarios():
        shared = p.shared_cause.lower()
        distractor = p.distractor_cause.lower()
        assert not all(k in distractor for k in p.own_cause_keywords), p.key
        for v in p.victims:
            local = v.local_cause.lower()
            kws = v.own_cause_keywords
            assert not all(k in shared for k in kws), (p.key, v.local_cause)
            assert not all(k in distractor for k in kws), (p.key, v.local_cause)
            assert not all(k in local for k in p.own_cause_keywords), (
                p.key, v.local_cause)
            for other in p.victims:
                if other is v:
                    continue
                assert not all(k in other.local_cause.lower() for k in kws), (
                    p.key, v.local_cause, other.local_cause)
