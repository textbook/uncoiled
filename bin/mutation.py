#!/usr/bin/env python3
"""Helper script to run all steps of a `Cosmic Ray`_ analysis automatically.

Per the `tutorial`_, this will:

* Ensure the tests can pass *without* mutations
* Create DB and populate with mutations to apply
* Work through the mutations and re-run the tests for each one
* Show report in text and HTML formats

.. _Cosmic Ray: https://cosmic-ray.readthedocs.io/en/latest/index.html
.. _tutorial: https://cosmic-ray.readthedocs.io/en/latest/tutorials/intro/index.html

"""

import logging
import pathlib
import tempfile
from argparse import Namespace
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from io import StringIO

import tqdm
import yattag
from cosmic_ray import commands
from cosmic_ray.config import ConfigDict, load_config
from cosmic_ray.plugins import get_distributor
from cosmic_ray.tools.filters.operators_filter import OperatorsFilter
from cosmic_ray.tools.filters.pragma_no_mutate import PragmaNoMutateFilter
from cosmic_ray.tools.html import _generate_html_report
from cosmic_ray.tools.survival_rate import kills_count, survival_rate
from cosmic_ray.work_db import WorkDB, use_db
from cosmic_ray.work_item import TestOutcome, WorkItem, WorkResult

ROOT = (pathlib.Path(__file__).parent / "..").resolve()
CONFIG_FILE = ROOT / "cosmic-ray.toml"
MUTATION_DIR = ROOT / "mutation"

MUTATION_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("cosmic_ray").setLevel(logging.WARNING)

config_dict = load_config(CONFIG_FILE)
modules = [
    ROOT / config_dict["module-path"] / module
    for module in (ROOT / config_dict["module-path"]).rglob("*.py")
]


@contextmanager
def temporary_log_level(level: int, *, name: str | None = None) -> Iterator[None]:
    """Reset a logger level for the duration of the context."""
    logger_ = logging.getLogger(name)
    original_level = logger_.level
    logger_.setLevel(level)
    yield
    logger_.setLevel(original_level)


def baseline(config: ConfigDict, /) -> None:
    """Ensure the tests can pass via Cosmic Ray before mutating."""
    with (
        tempfile.TemporaryDirectory() as temp_dir,
        use_db(
            pathlib.Path(temp_dir) / "baseline.sqlite", mode=WorkDB.Mode.create
        ) as db,
    ):
        db.clear()
        db.add_work_item(
            WorkItem(
                mutations=[],  # ty: ignore[invalid-argument-type] -- library definition is wrong
                job_id="baseline",
            ),
        )
        commands.execute(db, config=config)
        if next(db.results)[1] == TestOutcome.KILLED:
            raise RuntimeError("test baseline failed")  # noqa: EM101, TRY003


baseline(config_dict)

with use_db(MUTATION_DIR / "state.sqlite", mode=WorkDB.Mode.create) as work_db:
    commands.init(
        module_paths=modules,
        operator_cfgs=config_dict.operators_config,
        work_db=work_db,
    )

    args = Namespace(config=str(CONFIG_FILE))
    # Operators filter uses the root logger
    with temporary_log_level(logging.WARNING):
        OperatorsFilter().filter(work_db, args)
    # Pragma filter uses print
    with redirect_stdout(StringIO()):
        PragmaNoMutateFilter().filter(work_db, args)

    distributor = get_distributor(config_dict.distributor_name)

    with tqdm.tqdm(total=work_db.num_work_items) as progress:

        def on_task_complete(job_id: str, work_result: WorkResult) -> None:
            """Update database and progress bar."""
            work_db.set_result(job_id, work_result)
            progress.update(work_db.num_results - progress.n)

        distributor(
            work_db.pending_work_items,
            config_dict.test_command,
            config_dict.timeout,
            config_dict.distributor_config,
            on_task_complete=on_task_complete,
        )

    logger.info(
        "killed %d / %d mutants (survival rate: %.1f%%)",
        kills_count(work_db),
        work_db.num_results,
        survival_rate(work_db),
    )

    report_path = MUTATION_DIR / "index.html"
    with report_path.open(mode="w") as report:
        doc: yattag.Doc = _generate_html_report(
            work_db,
            hide_skipped=False,
            only_completed=False,
            skip_success=False,
        )
        report.write(doc.getvalue())
        logger.info("HTML report created")
        print(report_path)  # noqa: T201
