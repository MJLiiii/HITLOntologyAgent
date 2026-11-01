"""Install only the pinned small embedding model and capped local Qwen alias."""
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

EMBEDDING_DIGEST = '1b226e2802dbb772b5fc32a58f103ca1804ef7501331012de126ab22f67475ef'
QWEN_DIGEST = '8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7'
DERIVED_DIGEST = '84c467420f6d51cae7ca58914d67196eaa658b26d90b8af6705b7192b3947002'


def request(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    with urlopen(Request('http://127.0.0.1:11434/api/' + path, data=data,
                         headers={'Content-Type': 'application/json'}), timeout=120) as response:
        result = json.load(response)
    if result.get('error'):
        raise ValueError('Local model operation failed')
    return result


def main():
    with urlopen('https://registry.ollama.ai/v2/library/all-minilm/manifests/latest', timeout=30) as response:
        manifest = response.read(100_000)
    if hashlib.sha256(manifest).hexdigest() != EMBEDDING_DIGEST:
        raise ValueError('Embedding registry tag moved; refusing implicit upgrade')
    models = {m['name']: m['digest'] for m in request('tags')['models']}
    if models.get('qwen3:1.7b') != QWEN_DIGEST:
        raise ValueError('Pinned base Qwen is missing; run the project model setup first')
    if models.get('all-minilm:latest') != EMBEDDING_DIGEST:
        request('pull', {'model': 'all-minilm:latest', 'stream': False})
    request('create', {'model': 'oe-qwen3-smoke:1.7b', 'from': 'qwen3:1.7b', 'stream': False,
                       'parameters': {'num_predict': 512, 'num_ctx': 4096, 'temperature': 0}})
    models = {m['name']: m['digest'] for m in request('tags')['models']}
    if models.get('all-minilm:latest') != EMBEDDING_DIGEST or models.get('oe-qwen3-smoke:1.7b') != DERIVED_DIGEST:
        raise ValueError('Installed model digest differs from the frozen pipeline pin')
    (Path(__file__).resolve().parent / 'runtime/embedding-manifest.json').write_bytes(manifest)
    print('Verified pinned embedding and capped derived Qwen identities; original Qwen model unchanged.')


if __name__ == '__main__':
    main()
