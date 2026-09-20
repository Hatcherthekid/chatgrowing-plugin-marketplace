# Website release history

GitHub Releases are the source for new versions. `sync.py` retrieves every API page, excludes drafts and prereleases, checks each tag's plugin manifest, and renders every version newest first. Release publication and edits/deletions trigger `.github/workflows/changelog.yml`; manual dispatch supports recovery. A plain commit does not trigger deployment.

`history.json` preserves all 14 entries recovered from the September 1 website (0.1.0–0.3.0), the documented 0.3.1 local candidate, and later marketplace versions. Original candidate/private/product-improvement status and full notes are retained. There is no invented 0.1.1 or 0.3.2 entry. Dates are explicitly labelled marketplace commit dates, not fabricated Release publication times. If a matching Release is later published, it takes precedence. Version 0.4.0 originally carried build metadata, which is retained in the record.

The website uses its existing shared styles and a version navigation list. Markdown is rendered as escaped text with limited headings, lists and HTTP(S) links; release content is never executed. Failed fetches or validation leave the previous page intact. Atomic replacement and a server lock protect concurrent deployments.

Deployment uses a dedicated restricted SSH key stored in repository Actions secrets. Its authorized-key forced command runs the root-owned renderer as an unprivileged `cg-changelog` user, with write access only to the managed changelog directory. SSH forwarding, PTY and arbitrary commands are disabled. The workflow does not transfer executable code. Updating the renderer/template/history requires an explicit operator deployment to `/opt/chatgrowing-changelog/`; ordinary Release updates need no manual deployment. No plugin version bump is needed for this website workflow.

Local validation:

```sh
cd website
python3 -m unittest -v test_sync.py
python3 sync.py --output /tmp/chatgrowing-changelog.html
```
