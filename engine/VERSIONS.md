# Engine libraries

`engine/index.html` loads three libraries from the jsDelivr CDN. Exact versions and Subresource
Integrity hashes are pinned in [`pins.json`](pins.json), which is the single source of truth for
`tools/fetch_engine_libs.py` (offline cache for the tests) and for the pins test. A range, `latest`
or a missing hash fails `tests/test_engine_driver.py`.

| Library | Version | File | SRI (sha384) |
|---|---|---|---|
| Cytoscape.js | 3.34.4 | `dist/cytoscape.min.js` | `lyd1lDWZ623YSUJ/wMQH50y+T81dWKJk7ZoFdYWXQS83b0+QpW0pgdfXEnQnXL/X` |
| ELK.js | 0.12.0 | `lib/elk.bundled.js` | `ww57TDqx4cGknIavPm0QKO+aygLUR1BLSn2Vhbnt1XdYKWcwLyWTFKX7aZMaKIi2` |
| cytoscape-elk | 2.3.0 | `dist/cytoscape-elk.js` | `VCqo69qSTjiAwEkpykDLjsy96VKDH33my5mKmDfk3HhB85Iy4QwZ9R0IXqYuxV1A` |

Load order: Cytoscape, ELK (sets the global `ELK`), then cytoscape-elk (registers itself when it
finds `cytoscape` and `ELK` as globals).

## Changing a pin

1. Edit `pins.json` (version, URL) and set `integrity` to
   `sha384-` + base64 of `openssl dgst -sha384 -binary <file>`.
2. Update the table above.
3. `uv run python tools/fetch_engine_libs.py --force`, then the full suite, then the `-m network` test.
