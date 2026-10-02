# Reproduce

Everything on this site is generated from files in
[`maicen/bim-guard-evaluation`](https://github.com/maicen/bim-guard-evaluation). Install
[uv](https://docs.astral.sh/uv/), then:

```bash
git clone https://github.com/maicen/bim-guard-evaluation.git
cd bim-guard-evaluation
uv sync
```

## Real, reproducible harnesses

```bash
# Architecture engines: 22 cases, Wilson 95% CIs
uv run python eval/score_arch_engines.py

# NLP annotation suite: 60 cases across the annotator capabilities
uv run python eval/score_nlp_annotation.py
```

Each run can record its environment (platform, git revision, `uv.lock` SHA-256) with
`eval/env_snapshot.py`, so a reported number can be tied to the exact code and dependency set.

## Regenerating the tables and figures

```bash
uv run python eval/generate_publication_artifacts.py
```

This writes `docs/publication/tables/*.tex` and `docs/publication/figures/*.png`, which this site renders.

## Building this site locally

```bash
uv run site/build.py
python3 -m http.server -d site/dist 8000
```

## Cite

Citation metadata is in [`CITATION.cff`](https://github.com/maicen/bim-guard-evaluation/blob/main/CITATION.cff).
Licensing of source documents: [`docs/DATA_LICENSING.md`](https://github.com/maicen/bim-guard-evaluation/blob/main/docs/DATA_LICENSING.md).
