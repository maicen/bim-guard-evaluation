"""
eval/tests/test_generate_publication_artifacts.py
-------------------------------------------------
Unit tests for automated LaTeX table and publication figures generation.
"""

from pathlib import Path
from eval.generate_publication_artifacts import (
    generate_latex_tables,
    generate_appendix_markdown,
)
from eval.score_arch_engines import run_benchmark as run_arch_benchmark
from eval.score_cross_code import run_cross_code_benchmark
from eval.score_iaa import IAACalculator
from eval.score_judge_sensitivity import generate_benchmark_report
import json


def test_generate_latex_tables_and_appendix(tmp_path: Path):
    eval_root = Path(__file__).resolve().parent.parent.parent
    corpus_path = eval_root / "research" / "annotations" / "dual_annotator_corpus.json"
    with open(corpus_path, encoding="utf-8") as f:
        tasks = json.load(f)

    iaa_calc = IAACalculator(tasks)
    iaa_data = iaa_calc.generate_full_results()
    arch_data = run_arch_benchmark()
    cross_data = run_cross_code_benchmark()
    judge_data = generate_benchmark_report()

    tables_dir = tmp_path / "tables"
    generate_latex_tables(iaa_data, arch_data, cross_data, judge_data, tables_dir)

    assert (tables_dir / "table_1_iaa_metrics.tex").exists()
    assert (tables_dir / "table_2_arch_confusion_matrix.tex").exists()
    assert (tables_dir / "table_3_cross_code_generalization.tex").exists()
    assert (tables_dir / "table_4_judge_sensitivity.tex").exists()

    # Check for booktabs commands
    t1 = (tables_dir / "table_1_iaa_metrics.tex").read_text(encoding="utf-8")
    assert "\\toprule" in t1
    assert "\\midrule" in t1
    assert "\\bottomrule" in t1

    appendix_file = tmp_path / "APPENDIX_A.md"
    generate_appendix_markdown(appendix_file)
    assert appendix_file.exists()
    assert "Appendix A" in appendix_file.read_text(encoding="utf-8")
