"""
kg/ — Knowledge-graph construction linking DocLang-parsed building-code
documents (.dclx / .dclg) to the bSDD ontology reference database.

Pipeline: dclx_loader -> clause_builder -> (bsdd_loader + similarity) -> graph_builder.
See kg/build_kg.py for the CLI entrypoint.
"""
