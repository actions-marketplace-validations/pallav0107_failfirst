# Conformance vectors

Language-neutral JSON test vectors; see `spec/SPEC.md` section 8 for the format. An implementation conforms when every vector in `protocol.json` and `hashes.json` produces the expected result. `python/tests/test_conformance.py` and `js/test/conformance.test.ts` are reference runners (about 40 lines each).
