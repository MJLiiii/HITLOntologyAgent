"""Dependency checks execute the required engines; they do not approve user bundles."""
from functools import lru_cache
import os
import httpx
from .artifacts import digest


@lru_cache(maxsize=4)
def engine_readiness(configuration_digest, time_bucket, assessment_python):
    from .validation import validate
    from .assessment import assess
    from .demo import ONTOLOGY, SHAPES, FIXTURES, TESTS, QUESTIONS
    probe_digest = digest({"purpose": "readiness", "configuration": configuration_digest})
    validation = validate(ONTOLOGY, bundle_digest=probe_digest, shapes_ttl=SHAPES, fixtures_ttl=FIXTURES, tests=TESTS)
    questions = [{**q, "sparql_query": q["sparql_query"].replace("demo:", "ex:")} for q in QUESTIONS]
    assessment = assess(ONTOLOGY, bundle_digest=probe_digest, questions=questions)
    return {"jena": "available" if validation["status"] == "passed" else validation["status"],
            "ontocheck": "available" if assessment["status"] == "completed" else assessment["status"]}


def dependencies(studio):
    import time
    result = engine_readiness(digest(studio.engine_configuration()), int(time.monotonic() // 60),
                              os.getenv("OE_ONTOCHECK_PYTHON", "default"))
    result = {**result, "model": "not_configured"}
    if studio.settings.model_url and studio.settings.model_name:
        try:
            with httpx.Client(timeout=2, follow_redirects=False) as client:
                response = client.get(studio.settings.model_url.rstrip("/") + "/api/tags",
                                      headers={"Authorization": "Bearer " + studio.settings.model_api_key} if studio.settings.model_api_key else {})
                response.raise_for_status()
                names = {m["name"] for m in response.json()["models"]}
                result["model"] = "available" if studio.settings.model_name in names else "missing_model"
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            result["model"] = "unavailable"
    return result
