# Runbook: the live tier (kubeagent's chaos gate)

The offline eval (kv-eval) is this repo's own gate. The live tier — running
kubeagent's chaos harness with the model serving local verdict mode — is
**owned by the kubeagent operator and never run from this repository**.
The harness injects real outages into a cluster and requires the
operator's explicit authorization every time; nothing in kubeagent-verdict
invokes it, ever.

What this repo hands over:

1. Serve the model where the operator's kubeagent can reach it:

       ollama create kubeagent-verdict -f dist/Modelfile
       ollama serve   # or: llama-server -m dist/kubeagent-verdict-0.6b-q8_0.gguf --port 11434

2. The operator points kubeagent at it — no ANTHROPIC_API_KEY in the
   environment (the key would win over the endpoint), e.g.:

       env -u ANTHROPIC_API_KEY \
         KUBEAGENT_EXPLAIN_ENDPOINT=http://localhost:11434/v1 \
         KUBEAGENT_MODEL=kubeagent-verdict \
         kubeagent scan --investigate ...

3. The operator runs their chaos gate per kubeagent's own release process
   and reads the verdict sections of the reports. Findings come back here
   as issues against the dataset or the catalog.

A quick handover sanity check that IS safe from this repo: with the model
served, `kv-eval --test out/dataset/test.jsonl --limit 10 ...` — live
contract behavior, no cluster involved.
