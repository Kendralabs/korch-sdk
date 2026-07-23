"""Repository maintenance scripts (isolation gate, env-read check, version validation).

Not part of the installed package — never imported by ``src/korchestrator``. Importable as a
plain package only so ``tests/unit/test_config_isolation.py`` can reuse
``check_env_reads.find_offenders`` instead of duplicating the scan.
"""
