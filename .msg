test(emissions): make the COPY placement test able to fail

The test existed to catch a transposition of the two new join keys in
the positional COPY tuple, and could not: in a fresh schema the first
carbon_report_module gets id 1 and DataEntryTypeEnum.member is also 1,
so swapping those two columns produced identical rows. Verified by
mutating write_row — the test passed, and so did the rest of the file.

Burning a module id first makes the two values differ, and an explicit
assertion fails loudly if that ever stops being true. Re-verified by
mutation: passes on correct code, fails on the swap.
