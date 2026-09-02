"""Tests that need a live PostgreSQL.

Excluded from the default run (NFR-28: unit tests touch no network and no
database). These exist because defects 26, 31, 37 and 38 all shared a shape:
the rule read correctly, the unit test passed, and the behaviour only appeared
once a real transaction, a real thread pool or a real provider was involved.
"""
