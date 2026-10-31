# Engine libraries and font

`engine/index.html` loads three libraries from `engine/vendor/`, and `engine.css` the font Exo 2 from
there. They ship with the plugin, so the graph page opens offline and no third party sees it opened
(ADR 0004). `tools/bundle_engine.py` inlines all of it into `engine/dist/index.html`: the libraries as
inline scripts, the font files as data URIs. Exact versions and Subresource Integrity hashes are pinned
in [`pins.json`](pins.json); the hash checks the committed file in `vendor/`, and the bundler refuses a
file that does not match. A range or `latest` in a pin, a missing licence or a changed file fails
`tests/test_engine_driver.py`.

| Library | Version | Licence | File in `vendor/` | SRI (sha384) |
|---|---|---|---|---|
| Cytoscape.js | 3.34.4 | MIT | `cytoscape.min.js` | `lyd1lDWZ623YSUJ/wMQH50y+T81dWKJk7ZoFdYWXQS83b0+QpW0pgdfXEnQnXL/X` |
| ELK.js | 0.12.0 | EPL-2.0 | `elk.bundled.js` | `ww57TDqx4cGknIavPm0QKO+aygLUR1BLSn2Vhbnt1XdYKWcwLyWTFKX7aZMaKIi2` |
| cytoscape-elk | 2.3.0 | MIT | `cytoscape-elk.js` | `VCqo69qSTjiAwEkpykDLjsy96VKDH33my5mKmDfk3HhB85Iy4QwZ9R0IXqYuxV1A` |
| Exo 2 regular (via @fontsource/exo-2, latin) | 5.3.0 | OFL-1.1 | `exo-2-latin-400-normal.woff2` | `5Qmi4xRYR6vs6Ts3+ivSvCsc5H4lPZR4LyWrUh/EAwyOMzvOr2ZiNwUhh+lHX0I4` |
| Exo 2 semibold (via @fontsource/exo-2, latin) | 5.3.0 | OFL-1.1 | `exo-2-latin-600-normal.woff2` | `ERgXv3Je1dnIGW5waT7Mu77zmVzI7iSnvtHoKDSg8JlHfOIcycRHAn1AtfIR8/TS` |

The licence texts sit next to the files (`LICENSE-*.txt`). The page's footer says that game icons
belong to Paradox Interactive and come from the viewer's own installation.

Load order: Cytoscape, ELK (sets the global `ELK`), then cytoscape-elk (registers itself when it
finds `cytoscape` and `ELK` as globals).

## Changing a pin

1. Edit `pins.json` (version, URL, licence URL) and set `integrity` to
   `sha384-` + base64 of `openssl dgst -sha384 -binary <file>` of the downloaded file.
2. Update the table above.
3. `uv run python tools/fetch_engine_libs.py --force` (checks the hash, writes `engine/vendor/`), then
   `uv run python tools/bundle_engine.py` and the full suite.
