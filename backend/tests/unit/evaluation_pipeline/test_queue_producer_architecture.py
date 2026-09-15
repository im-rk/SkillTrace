"""
Architectural invariant: the synchronous submit-answer fast path must never
import BKT computation -- that's the entire reason this pipeline exists (see
docs/adr/0011-durable-submission-pipeline.md). A regression here would not
necessarily fail any functional test, so it's checked directly rather than
relying on it staying true by review each time the file is edited.
"""
import ast
import inspect

from app.modules.evaluation_pipeline import queue_producer


def test_queue_producer_never_imports_bkt_domain():
    tree = ast.parse(inspect.getsource(queue_producer))
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any("quiz_engine.domain.bkt" in module for module in imported_modules), (
        "queue_producer.py must never import BKT computation -- mastery is "
        "only ever computed in the async Celery consumer (tasks.py)"
    )
