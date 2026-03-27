# Contact Updates Query Builder

This repository contains the Render-side API for a small internal Wix application that lets users:

- choose a date range, defaulting to the last 7 days
- enter their Odoo SaaS credentials
- query for contacts whose notes or activities changed during that window
- display the matching contacts back in Wix

The project is intentionally small and reuses the same Odoo XML-RPC connection pattern already used in:

- `wix-odoo-webhook`
- `odoo-shipment-report-render`

## Recommended architecture

1. The Wix page collects the date range and Odoo credentials.
2. Wix frontend calls a Wix backend web module.
3. The Wix backend web module sends a POST request to this Render API.
4. The Render API authenticates to Odoo and queries:
   - `mail.message` for contact notes
   - `mail.activity` for contact activities
   - `res.partner` for contact details
5. The Render API returns normalized results to Wix for display.

Using a Wix backend web module is the right fit here because Wix documents that web modules are backend files that can be called from the frontend, and they help centralize third-party API calls while avoiding CORS issues. Odoo documents that `search_read()` is the standard shortcut for this style of external API query.

## Important Odoo version note

This code uses Odoo XML-RPC because that matches your existing working integrations and is the fastest way to get this live.

That is still compatible with Odoo 17 and Odoo 19, but Odoo 19 documentation now says XML-RPC and JSON-RPC are scheduled for removal in Odoo 20, expected in fall 2026. Because of that, this repo keeps the Odoo query logic isolated in `src/odoo_client.py`, so we can swap the transport layer later without rewriting the whole app.

## Project layout

```text
src/
  main.py
  models.py
  odoo_client.py
wix/
  contact-updates-page.js
  backend/contactUpdates.web.js
render.yaml
requirements.txt
```

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

Then open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## Render deployment

1. Push this repository to GitHub.
2. Create a new Render Blueprint or Web Service from the repo.
3. Use the included `render.yaml`.
4. After deploy, confirm `/health` returns `{"status":"ok"}`.
5. Paste the Render URL into `wix/backend/contactUpdates.web.js`.

## Wix setup

Create these page elements in Wix and match the IDs in `wix/contact-updates-page.js`:

- `#startDatePicker`
- `#endDatePicker`
- `#odooUrlInput`
- `#odooDbInput`
- `#odooUsernameInput`
- `#odooPasswordInput`
- `#runButton`
- `#statusText`
- `#resultsTable`

Suggested `#resultsTable` columns:

- `name`
- `company`
- `email`
- `phone`
- `updatedAt`
- `sources`
- `note`
- `activity`

Then:

1. Copy `wix/backend/contactUpdates.web.js` into your Wix site's backend code.
2. Copy `wix/contact-updates-page.js` into the page code for your contact updates page.
3. Replace `https://YOUR-RENDER-SERVICE.onrender.com` with your real Render URL.
4. Publish the site.

## Security note

Your requested design has each user typing their own Odoo credentials into the Wix page. That will work with this API, but for an internal app with 4 to 5 users, a shared Odoo integration account stored in Wix Secrets Manager or in Render environment variables would usually be safer and easier to support.

If you want, the next step can be either:

- keep the current per-user login design
- switch to a shared service account design
- add Wix member login restrictions so only approved internal users can run the query

## Query behavior

The API:

- defaults to the last 7 days if no dates are supplied
- looks for `mail.message` records on `res.partner` updated in the window
- keeps note-like messages whose subtype includes `note`
- looks for `mail.activity` records on `res.partner` updated in the window
- returns the most recent note and activity details for each matching contact
- sorts the final result by most recent update first

## Sources used for the design

- Wix web modules: https://dev.wix.com/docs/develop-websites/articles/coding-with-velo/backend-code/web-modules/about-web-modules
- Wix HTTP functions: https://dev.wix.com/docs/velo/api-reference/wix-http-functions/introduction
- Wix Secrets Manager: https://dev.wix.com/docs/velo/apis/wix-secrets-backend/introduction
- Render Blueprint reference: https://render.com/docs/blueprint-spec
- Odoo 17 external API: https://www.odoo.com/documentation/17.0/developer/reference/external_api.html
- Odoo 19 external RPC API: https://www.odoo.com/documentation/19.0/developer/reference/external_rpc_api.html
