# Final delivery acceptance

19 November 2026, Hong Kong time. Codex ran this acceptance check at Haha Qi's request. Baseline commit: `82f3f38ba641ee7e10aad4e8f7493827a1aa1045`. The browser checks ran against the local FastAPI server on loopback with no model credentials configured.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Plastic bottle · HKU hall bin | Shows the plastic bottle bin and location exception, preparation steps, a working HKU source link, and date checked. | [Browser capture](normal.jpg) |
| Pencil · EPD smart bin | Explains that published rules do not cover the item and directs the user to the hall office. The previous bin result is cleared. | [Browser capture](unsupported.jpg) |
| Power bank · HKU hall bin | Warns that the item may be hazardous, omits ordinary bin advice, and directs the user to hall staff or a hazardous-waste collection point. | [Browser capture](hazard.jpg) |
| 501-character input | Originally produced a generic HTTP 422 error. After the form change, ordinary typing or pasting is limited to 500 characters, and an overlength value set programmatically shows a clear validation message before the form sends a request. | [Browser capture](input-limit.jpg) |

The existing regression suite passed all 58 tests. The existing offline evaluation passed all 30 cases. These checks cover the published-rule path and local browser behavior. Live model behavior was outside this acceptance run.

## Public submission

- **Repository:** The [public GitHub repository](https://github.com/yueliangxingren-cmyk/Hall_Recycling_Helper) opened and displayed its files.
- **Project webpage:** The standard [GitHub Pages address](https://yueliangxingren-cmyk.github.io/Hall_Recycling_Helper/) returned 404. The report listed a placeholder. Add the final deployment URL and rerun the three browser checks there. The current frontend sends a POST to `/ask`, so a static deployment alone cannot serve that route.
- **Videos:** The report still had placeholders for both YouTube URLs. Add and verify distinct presentation and demo links with teaching-team access.
