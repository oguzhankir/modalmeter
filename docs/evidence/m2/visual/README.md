# Actual offline HTML visual QA

Final QA used an isolated headless Chrome with the DevTools Protocol, the actual
unchanged generated HTML/CSP, and explicitly overridden viewport dimensions.
The temporary standard-library CDP helper lives at
`/private/tmp/modalmeter-cdp-390-qa.py` in this session; final artifact hashes,
viewport widths and observed layout/image/network facts are in
[layout-390.json](layout-390.json).

Visually inspected:

- [Image at 390 px](image-390.png): image-only output, explicit missing metrics,
  responsive summary cards and no source media in the sanitized export.
- [Video at 390 px](video-390.png), [timeline](video-timeline-390.png): readable
  selected frames, PTS versus processor timestamps, preserved aspect ratios,
  final-source-frame padding, and no document overflow.
- [Comparison at 390 px](comparison-390.png): summary and intentional internal
  horizontal table scroll; document width stays 390.
- [Comparison at 1440 px](comparison-desktop-cdp.png): readable configuration
  columns, expandable long mappings, coupled-change explanation above the diff.
- [Video desktop](video-desktop.png), [image desktop](image-desktop.png): prior
  actual desktop captures; summary/input layout unchanged by the comparison fix.

All final observed page widths equal the requested CSS viewport widths.
All 3 video/24 comparison thumbnails decoded, and external src/href references
were empty. Offscreen lazy images were requested eagerly only through transient
browser DOM state for QA; original HTML and CSP were unchanged. No video upload,
external service, remote font, CDN or model download was involved.

The preliminary [layout-initial.json](layout-initial.json) is preserved as an
attempt record: Chrome window-size requested 390 but used a 500 CSS-pixel minimum.
Those clipped captures were removed and are not counted as narrow-screen success.
Inline QA code on a temporary copy was initially blocked by the report CSP, and
comparison image-readiness initially waited on offscreen lazy images. Final CDP
checks corrected those tooling issues without weakening the real report policy.
