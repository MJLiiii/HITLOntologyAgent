"""Initialize the isolated synthetic pipeline storage or official flow config."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent


def garage(*args, required=True):
    result = subprocess.run(["docker", "exec", "oe-portal-smoke-garage-1", "/garage", "-c", "/etc/garage.toml", *args],
                            capture_output=True, text=True)
    if required and result.returncode:
        raise RuntimeError("Synthetic Garage initialization command failed (private output withheld)")
    return result.stdout


def storage():
    status = garage("status")
    if "NO ROLE ASSIGNED" in status:
        node = re.search(r"^([0-9a-f]{16})\s", status, re.M).group(1)
        garage("layout", "assign", "-z", "synthetic", "-c", "1G", node)
        garage("layout", "apply", "--version", "1")
    private = json.loads((BASE / "runtime/pipeline-secrets.json").read_text())
    garage("key", "import", "--yes", "-n", "oe-synthetic", private["access_key"], private["secret_key"])
    garage("bucket", "create", "library", required=False)
    garage("bucket", "allow", "--read", "--write", "--owner", "library", "--key", private["access_key"])
    print("Synthetic Garage layout and library permissions initialized.")


def post(path, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request("http://127.0.0.1:18888/api/v1/" + path,
                         data=json.dumps(body).encode(), headers=headers), timeout=120) as response:
        value = json.load(response)
    if value.get("error"):
        raise RuntimeError("TrustGraph operation failed: " + str(value["error"]))
    return value


def api():
    from trustgraph.api import Api
    credentials = json.loads((BASE / "runtime/login.json").read_text())
    token = post("auth/login", credentials)["jwt"]
    return Api("http://127.0.0.1:18888", token=token, workspace="default", timeout=120)


def flows(config_name="pipeline-config.json"):
    from trustgraph.api import ConfigValue
    client = api()
    cfg = json.loads((BASE / config_name).read_text())
    values = []
    def add(kind, key, value):
        values.append(ConfigValue(type=kind, key=key, value=json.dumps(value)))
    for key, value in cfg["blueprints"].items():
        add("flow-blueprint", key, value)
    add("prompt", "system", cfg["prompts"]["system"])
    for key, value in cfg["prompts"]["templates"].items():
        add("prompt", "template." + key, value)
    ontology = {"metadata": {"name": "Synthetic service ownership", "description": "Only invented smoke-test entities"},
                "classes": {}, "objectProperties": {}, "datatypeProperties": {}}
    for name in ("Service", "Team"):
        uri = "https://example.org/demo#" + name
        ontology["classes"][name] = {"uri": uri, "type": "owl:Class", "rdfs:label": [{"value": name, "language": "en"}],
                                     "rdfs:comment": "Synthetic " + name.lower()}
    ontology["objectProperties"]["ownedBy"] = {
        "uri": "https://example.org/demo#ownedBy", "type": "owl:ObjectProperty",
        "rdfs:label": [{"value": "owned by", "language": "en"}],
        "rdfs:domain": "https://example.org/demo#Service", "rdfs:range": "https://example.org/demo#Team",
        "rdfs:comment": "A service is owned by a team."}
    add("ontology", "oe-synthetic-ownership", ontology)
    for name in cfg["blueprints"]:
        add("collection", name, {"collection": name, "name": name, "description": "Synthetic engineering smoke", "tags": ["synthetic"]})
    client.config().put(values)
    existing = client.flow().list()
    parameters = {"llm-model": "qwen3:1.7b", "llm-rag-model": "qwen3:1.7b",
                  "llm-temperature": "0", "llm-rag-temperature": "0", "embeddings-model": "all-minilm:latest",
                  "reranker-model": "ms-marco-TinyBERT-L-2-v2", "chunk-size": "2000", "chunk-overlap": "0"}
    if config_name.endswith(('-v3.json', '-v4.json')):
        parameters.update({'llm-model': 'oe-qwen3-smoke:1.7b', 'llm-rag-model': 'oe-qwen3-smoke:1.7b'})
    for name in cfg["blueprints"]:
        if name not in existing:
            client.flow().start(name, name, "Synthetic Ontology Studio provenance smoke", parameters=parameters)
    print("Pinned synthetic blueprints, seed ontology, prompts, collections and flows initialized.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["storage", "flows"])
    parser.add_argument("--structured-ontology", action="store_true")
    parser.add_argument("--bounded-model", action="store_true")
    parser.add_argument("--nonthinking-provider", action="store_true")
    args = parser.parse_args()
    if args.phase == "storage":
        storage()
    else:
        flows('pipeline-config-v4.json' if args.nonthinking_provider else ("pipeline-config-v3.json" if args.bounded_model else ("pipeline-config-v2.json" if args.structured_ontology else "pipeline-config.json")))
