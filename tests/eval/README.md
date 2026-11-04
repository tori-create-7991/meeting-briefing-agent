# Briefing writer evaluation

Three hand-written cases check the briefing writer on its own, with
`briefing_contexts` seeded straight into session state (no Calendar or Docs
access):

| Case | Checks |
|---|---|
| `no_related_docs` | An event without documents says that no related documents were found |
| `past_trends_not_available` | Past meeting trends are reported as not yet available, never invented; the document is used |
| `no_invented_facts` | No names, numbers or dates beyond the input; a failed document fetch is reported, not guessed; one section per meeting |

Each case is scored by an LLM judge against its rubrics
(`rubric_based_final_response_quality_v1`, threshold 0.8 in
`test_config.json`). `test_config.json` adds one rubric to every case
(written in Japanese); ADK refuses to run this metric without at least one
there.

The judge sees the request and the response, not the session state, so it
cannot look up the seeded events or documents. Each rubric therefore states
the facts it checks (for example the exact terms the response may use)
instead of pointing at "the document".

## Run

```bash
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=<your project>
export GOOGLE_CLOUD_LOCATION=global
uv run --with "google-adk[eval]" adk eval tests/eval/writer_agent tests/eval/briefing.evalset.json \
  --config_file_path tests/eval/test_config.json --print_detailed_results
```

`--with "google-adk[eval]"` adds ADK's evaluation extras for this run only;
the project does not depend on them. Each run's details are written to
`tests/eval/writer_agent/.adk/eval_history/` (gitignored).

Both the writer (`BRIEFING_MODEL`) and the judge call Gemini on Vertex AI,
so each run is billed to that project. Gemini 3 models are served only from
the `global` location, not from regions such as `us-central1`.

## Why this is not in CI

LLM output varies from run to run, so a failing score is a prompt to look at
the output, not a reliable regression signal, and every run costs money. CI
only checks that these files still load (`tests/test_eval_files.py`).
