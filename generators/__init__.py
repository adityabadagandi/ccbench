"""Generators package for CCBench synthetic data (schema 0.2).

Pipeline::

    build_scenario(seed, defect)   ->  one source of truth for a consignment
        |-- build_invoice / build_eway_bill / build_erp_order / build_flag
        |-- build_thread            ->  chat + evidence spans
        |-- build_events            ->  case timeline
    assemble_case(spec, ...)       ->  question, answer and gold facts

The 0.1 modules ``invoice``, ``ewaybill``, ``erp``, ``gstin`` and ``noise``
were removed. They generated documents independently of one another and of the
label, and ``noise`` mutated documents *after* gold facts had been extracted.
Their replacements are ``identity``, ``scenario`` and ``whatsapp``.
"""

from .assembler import TASKS, TaskSpec, assemble_case, generate_dataset, redact
from .identity import GENERATOR_VERSION
from .scenario import DEFECTS, Scenario, build_scenario

__all__ = [
    "DEFECTS",
    "GENERATOR_VERSION",
    "Scenario",
    "TASKS",
    "TaskSpec",
    "assemble_case",
    "build_scenario",
    "generate_dataset",
    "redact",
]
