# Third-party front-end assets (self-hosted)

PCI DSS 4.0 req. 6.4.3 requires an inventory of every script loaded by payment-adjacent
pages, with a justification and an integrity check. All libraries below are served from
this directory via `{% static %}` — no third-party script CDN is used by the shared layouts.

Each file was downloaded from the CDN URL previously used by the templates and verified
byte-for-byte against the npm registry tarball (whose `dist.integrity` SHA-512 was checked).

| Library | Version | Why | Loaded by |
|---|---|---|---|
| Bootstrap (CSS + bundle JS incl. Popper) | 5.3.8 | Layout, components, dropdowns/modals/tabs | `partials/_head_assets.html`, `partials/_body_scripts.html` |
| Font Awesome Free (CSS + webfonts) | 6.5.0 | Icons | `partials/_head_assets.html` |
| AOS | 2.3.1 | Scroll-in animations (`data-aos` used by several app templates) | both partials |
| NProgress | 0.2.0 | Page-navigation progress bar (`static/js/app.js`) | both partials |
| Chart.js (UMD) | 4.4.0 | Dashboard charts | `base_dashboard.html` `{% block chart_js %}` only |

Bootstrap 5.3.9 exists but was published less than two weeks before this vendoring;
5.3.8 was chosen as the latest patch with a settled release history.

Google Fonts (Inter) CSS is still loaded from `fonts.googleapis.com` (stylesheet + font
files only, no script). A CSP must allow `style-src https://fonts.googleapis.com` and
`font-src https://fonts.gstatic.com`, or the fonts can be self-hosted here.

## SHA-256 of served files

```
4d1f9c2c1c7597f1d3bb3c29aaa4e832cfc264737bccac42543486f6d202ea28  ./aos-2.3.1/LICENSE
1aa8845fd06e475aefe733d4e55b36a92fcd487975049c8172341827ac9cc03e  ./aos-2.3.1/aos.css
f268612ba59ead1b24353bb77d66783bcc435aff1c22be5f93c40bac3869968e  ./aos-2.3.1/aos.js
4620c84ad5ce8602ff65640ed6b7c8b78ebb9e036584f0ebc1ccc88206a4bb51  ./bootstrap-5.3.8/LICENSE
d85327d99c7a3ee1f9b5d0500d1370acea3ad2db39c163c2f51f232baedbdede  ./bootstrap-5.3.8/css/bootstrap.min.css
e4fd49181388c48ec5040bd3fe66f57c29c8e67fcd8502b3354b96ec7ab47cc7  ./bootstrap-5.3.8/js/bootstrap.bundle.min.js
5a0877ad6d818529be4f33009d0942cdf7e2ed7656156f4aba7308459a546030  ./chartjs-4.4.0/LICENSE.md
321e3a3fa98da4aaa957d10be57cbb514de0989eed8f9d726b5d05902cd01904  ./chartjs-4.4.0/chart.umd.js
0aa8f86525273b2efa4f40f4272a188e187704252170e979dc06879adf68d43c  ./fontawesome-6.5.0/LICENSE.txt
c880eb3d25c765d399840aa204fec22b3230310991089f14781f09a35ed80b8a  ./fontawesome-6.5.0/css/all.min.css
5afff0a4df2650e9e2689c6021eb968f983eae2b388c2ce32ad853c0dd7f3788  ./fontawesome-6.5.0/webfonts/fa-brands-400.ttf
b66b3da5ff7b2db79b6cb5a22c3e762e2bf16958a11987e69eeb1980bbbcdfb0  ./fontawesome-6.5.0/webfonts/fa-brands-400.woff2
69ec55d72001a374fe40cd26ab4325e6312d0459b22372527bf539d28e2e2e47  ./fontawesome-6.5.0/webfonts/fa-regular-400.ttf
3a74c08d486310c03731b458616f0172375fe3780e96165f8a1adc02d1355eaa  ./fontawesome-6.5.0/webfonts/fa-regular-400.woff2
4ea5c3ff563052c2bc6534767c009dea4e2801b7a848bafeae87e9790eb0fc64  ./fontawesome-6.5.0/webfonts/fa-solid-900.ttf
f4c5a5b297e623bc159679563a4d1eb16e409ca3b57698fbc00fd2c907dadae0  ./fontawesome-6.5.0/webfonts/fa-solid-900.woff2
4694ef58b99d135ec4a4e7cf4b60681dff2cccf06604817a47a53c6ab41d3d2d  ./fontawesome-6.5.0/webfonts/fa-v4compatibility.ttf
33e73fb0656f23945b0d160507dba4dbcd315c3c18eedd0c1fd128ba88272b41  ./fontawesome-6.5.0/webfonts/fa-v4compatibility.woff2
d90e3b520a248648dcb9aad1a1c932aa33bf8ea09fbb1965d3ca6a2bfcc4fd0a  ./nprogress-0.2.0/License.md
9e8d1ce5c703383070a7ef614a657956f3e92b01c2a5b5735c77b1224ba933a5  ./nprogress-0.2.0/nprogress.css
6b9611076ec2701c0115c4f9105fdfdc4e2fcc8ab21eb491f3bf27b1e358c3ae  ./nprogress-0.2.0/nprogress.js
```

## Upgrading

1. Download the new files from the npm tarball (`npm pack <pkg>@<ver>`) or the CDN,
   verify them against the registry `dist.integrity`, and place them in a new
   versioned folder (e.g. `bootstrap-5.3.9/`).
2. Update the paths in the partials, delete the old folder, refresh the table and hashes above.
3. Keep source maps next to minified files: `ManifestStaticFilesStorage` fails on
   `sourceMappingURL` references to missing files.
