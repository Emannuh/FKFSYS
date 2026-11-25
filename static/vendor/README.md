# Third-party front-end assets (self-hosted)

PCI DSS 4.0 req. 6.4.3 requires an inventory of every script loaded by payment-adjacent
pages, with a justification and an integrity check. All libraries below are served from
this directory via `{% static %}` — no third-party script CDN is used by the shared layouts.

Each file was downloaded from the CDN URL previously used by the templates and verified
byte-for-byte against the npm registry tarball (whose `dist.integrity` SHA-512 was checked).

| Library | Version | Why | Loaded by |
|---|---|---|---|
| Bootstrap (CSS + bundle JS incl. Popper) | 5.3.8 | Layout, components, dropdowns/modals/tabs | `partials/_head_assets.html`, `partials/_body_scripts.html` |
| Font Awesome Free (CSS + webfonts) | 6.7.2 | Icons | `partials/_head_assets.html` |
| AOS | 2.3.4 | Scroll-in animations (`data-aos` used by several app templates) | both partials |
| NProgress | 0.2.0 | Page-navigation progress bar (`static/js/app.js`) | both partials |
| Chart.js (UMD) | 4.4.9 | Dashboard charts | explicit `{% block chart_js %}` on chart pages only |
| Inter (variable font woff2) | 5.1.1 | Body font (self-hosted, replaces Google Fonts call) | `static/css/inter.css` → `partials/_head_assets.html` |

## Notes

- Chart.js is now loaded **only on pages that render charts** (via `{% block chart_js %}`).
  Previously it was loaded on every dashboard page (~200 KB saved on most pages).
- Inter is now fully self-hosted. The `fonts.googleapis.com` preconnect and stylesheet
  link have been removed from `_head_assets.html`. A single variable font file covers
  all weights (100–900), replacing the five separate weight files previously fetched.
- Bootstrap 5.3.8 is retained; 5.3.9+ can be dropped in here following the upgrade steps
  below once it has a settled release history.

## Upgrading

1. Download the new files from the npm tarball (`npm pack <pkg>@<ver>`) or the CDN,
   verify them against the registry `dist.integrity`, and place them in a new
   versioned folder (e.g. `bootstrap-5.3.9/`).
2. Update the paths in the partials, delete the old folder, refresh the table and hashes above.
3. Keep source maps next to minified files: `ManifestStaticFilesStorage` fails on
   `sourceMappingURL` references to missing files.

## SHA-256 of served files

Run `sha256sum static/vendor/**/*` after any upgrade and paste the output here.
The hashes below are from the initial download of each version.

```
# Bootstrap 5.3.8
d85327d99c7a3ee1f9b5d0500d1370acea3ad2db39c163c2f51f232baedbdede  ./bootstrap-5.3.8/css/bootstrap.min.css
e4fd49181388c48ec5040bd3fe66f57c29c8e67fcd8502b3354b96ec7ab47cc7  ./bootstrap-5.3.8/js/bootstrap.bundle.min.js

# Font Awesome 6.7.2  (re-run sha256sum after download to verify)
# AOS 2.3.4           (re-run sha256sum after download to verify)
# Chart.js 4.4.9      (re-run sha256sum after download to verify)
# Inter 5.1.1         (re-run sha256sum after download to verify)
```
