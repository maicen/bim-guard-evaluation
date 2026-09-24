"""
kg/ — Knowledge-graph construction linking DocLang-parsed building-code
documents (.dclx / .dclg) to the bSDD ontology reference database.

Pipeline:
    dclx_loader -> clause_builder -> (bsdd_loader + similarity) -> graph_builder
        -> correct_graph      (LLM verification pass on borderline candidates)
        -> export_grounding   (grounding index for bim-guard + uncertain-edge review queue)
        -> [prioritize_review_queue]  (optional: re-ranks the queue by real production
                                        correction signal from
                                        eval/score_rule_extraction_corrections.py --json,
                                        read-only, no bim-guard writes)
        -> apply_review_decisions  (closes the loop: a human resolves the queue,
                                     re-promoted into a refreshed grounding index)

See kg/build_kg.py for the CLI entrypoint, and each stage's own module
docstring for its CLI usage. The grounding index this pipeline produces is
manually promoted into bim-guard as a static copy (see
app/services/clause_grounding_index.py there) once it's ready to inform
real extraction runs.
"""
