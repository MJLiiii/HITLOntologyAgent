"""Dependency checks execute the required engines; they do not approve user bundles."""
from functools import lru_cache
import os
from .artifacts import digest


@lru_cache(maxsize=4)
def engine_readiness(configuration_digest, time_bucket, assessment_python):
    from .validation import validate
    from .assessment import assess
    from .demo import ONTOLOGY, SHAPES, FIXTURES, TESTS, QUESTIONS
    probe_digest = digest({"purpose": "readiness", "configuration": configuration_digest})
    validation = validate(ONTOLOGY, bundle_digest=probe_digest, shapes_ttl=SHAPES, fixtures_ttl=FIXTURES, tests=TESTS)
    assessment = assess(ONTOLOGY, bundle_digest=probe_digest, questions=QUESTIONS)
    return {"jena": "available" if validation["status"] == "passed" else validation["status"],
            "ontocheck": "available" if assessment["status"] == "completed" else assessment["status"]}


def dependencies(studio):
    import time
    result = engine_readiness(digest(studio.engine_configuration()), int(time.monotonic() // 60),
                              os.getenv("OE_ONTOCHECK_PYTHON", "default"))
    from .llm_profiles import configuration_status
    return {**result, "model": configuration_status(studio.settings)}
