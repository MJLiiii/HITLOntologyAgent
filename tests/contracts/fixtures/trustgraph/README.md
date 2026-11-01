# Upstream loader fixture

`loadRemotePlugin.ts` is an unchanged source snapshot from TrustGraph UI, copyright its upstream contributors, under the included Apache-2.0 `LICENSE`.

Source: [pinned portal loader](https://github.com/trustgraph-ai/trustgraph-ui/blob/02efcac8adf04a1de1a4f601c1ecbb70ed910d6d/packages/portal/src/loadRemotePlugin.ts).

SHA-256: `9fedf934890719e70674f385cfa42096cd3688b5740917d8087d6e27fcb4fde2`.

Retrieved through the GitHub connector on 2026-11-01. This file documents the exact loader contract and can support component-mount contract tests without assuming a new SDK. It is not evidence that a live portal was mounted or authenticated. The loader accepts a global component function or a namespace whose `default` (or configured `componentName`) is a React component. It does not consume a plugin metadata descriptor as a default export.
