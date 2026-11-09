## 2023-11-09 - Method dispatch via dictionary lookup

**Learning:** `getattr` on every node/statement evaluation (`execute`, `eval`) adds up to significant execution time in `sparky/lang/interpreter.py`. By caching the methods into a class-level dictionary indexed by node type, we significantly speed up interpreter execution loops. Doing exact `type(node)` rather than `isinstance` for AST nodes speed up `eval` significantly.
**Action:** Use a `_exec_dispatch` and exact `type(node)` lookups inside heavily repeated interpreter methods (`execute`, `eval`) to reduce function call and type resolution overheads.
