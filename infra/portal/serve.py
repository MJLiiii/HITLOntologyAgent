#!/usr/bin/env python3
"""Serve the actual pinned portal build, with additive plugins and two real backends.

No API responses are simulated. Native TrustGraph routes retain their own IAM;
Studio routes retain their separate local-session approval boundary.
"""
import argparse
import asyncio
import json
from pathlib import Path

from aiohttp import ClientSession, DummyCookieJar, WSMsgType, web
from multidict import CIMultiDict

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
UI_PIN = "02efcac8adf04a1de1a4f601c1ecbb70ed910d6d"
TEMPLATE_PIN = "9b8763e0e9c833477004c59aafb5d5530d13d4a9"
PORTAL = HERE / "upstream" / f"trustgraph-ui-{UI_PIN}" / "packages/portal/dist"
TEMPLATE = HERE / "upstream" / f"ui-plugin-template-{TEMPLATE_PIN}" / "dist/template.iife.js"
STUDIO = ROOT / "apps/studio-plugin/dist-plugin"
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
               "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length"}


def studio_route(path):
    return any(path == prefix or path.startswith(prefix + "/") for prefix in (
        "/api/v1/session", "/api/v1/projects", "/api/v1/jobs", "/api/v1/health"))


async def proxy(request):
    target = request.app["studio"] if studio_route(request.path) else request.app["gateway"]
    url = target + request.rel_url.path_qs
    headers = CIMultiDict((k, v) for k, v in request.headers.items() if k.lower() not in HOP_HEADERS)
    session = request.app["client"]
    if request.headers.get("Upgrade", "").lower() == "websocket":
        # Each hop negotiates its own key and compression. Forwarding a browser's
        # Sec-WebSocket-Extensions offer would promise unsupported compression
        # on the Python client hop and close the real connection after auth.
        ws_headers = {k: v for k, v in headers.items() if not k.lower().startswith("sec-websocket-")}
        async with session.ws_connect(url, headers=ws_headers) as upstream:
            downstream = web.WebSocketResponse()
            await downstream.prepare(request)

            async def relay(source, destination):
                async for message in source:
                    if message.type == WSMsgType.TEXT:
                        await destination.send_str(message.data)
                    elif message.type == WSMsgType.BINARY:
                        await destination.send_bytes(message.data)
                    elif message.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                        break
                await destination.close()

            await asyncio.gather(relay(downstream, upstream), relay(upstream, downstream))
            return downstream
    async with session.request(request.method, url, headers=headers,
                               data=await request.read(), allow_redirects=False) as response:
        result_headers = CIMultiDict((k, v) for k, v in response.headers.items()
                                    if k.lower() not in HOP_HEADERS)
        return web.Response(status=response.status, body=await response.read(), headers=result_headers)


async def manifest(_request):
    sections = json.loads((PORTAL / "config/components.json").read_text())
    section = json.loads((HERE / "components-entry.json").read_text())
    section["components"].insert(0, {
        "id": "oe-upstream-template", "title": "Unchanged upstream template", "icon": "△",
        "paletteKey": "cyan", "description": "Pinned official plugin template contract smoke.",
        "url": "/plugins/oe-template.iife.js", "globalName": "TemplatePlugin",
    })
    return web.json_response([*sections, section])


async def static(request):
    additions = {
        "/plugins/oe-template.iife.js": TEMPLATE,
        "/plugins/ontology-studio.iife.js": STUDIO / "ontology-studio.iife.js",
        "/plugins/ontology-studio.css": STUDIO / "ontology-studio.css",
    }
    if request.path in additions:
        return web.FileResponse(additions[request.path])
    path = (PORTAL / request.path.lstrip("/")).resolve()
    if not path.is_relative_to(PORTAL.resolve()):
        raise web.HTTPForbidden()
    if path.is_file():
        return web.FileResponse(path)
    if request.path.startswith(("/assets/", "/plugins/", "/config/")) or path.suffix:
        raise web.HTTPNotFound()
    # React Router browser routes use the upstream index unchanged except for
    # the required plugin stylesheet. No React source or auth gate is patched.
    html = (PORTAL / "index.html").read_text().replace(
        "</head>", '<link rel="stylesheet" href="/plugins/ontology-studio.css"></head>')
    return web.Response(text=html, content_type="text/html")


async def client_lifecycle(app):
    async with ClientSession(cookie_jar=DummyCookieJar(), auto_decompress=False) as session:
        app["client"] = session
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5183)
    parser.add_argument("--gateway", default="http://127.0.0.1:18888")
    parser.add_argument("--studio", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    for file in (PORTAL / "index.html", TEMPLATE, STUDIO / "ontology-studio.iife.js"):
        if not file.exists():
            parser.error(f"Build prerequisite missing: {file}")
    app = web.Application(client_max_size=25 * 1024 * 1024)
    app["gateway"] = args.gateway.rstrip("/")
    app["studio"] = args.studio.rstrip("/")
    app.cleanup_ctx.append(client_lifecycle)
    app.router.add_route("*", "/api/v1/{path:.*}", proxy)
    app.router.add_get("/config/components.json", manifest)
    app.router.add_get("/{path:.*}", static)
    web.run_app(app, host="127.0.0.1", port=args.port, access_log=None)


if __name__ == "__main__":
    main()
