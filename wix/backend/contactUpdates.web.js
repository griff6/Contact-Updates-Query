import { Permissions, webMethod } from "wix-web-module";
import { fetch } from "wix-fetch";

export const fetchContactUpdates = webMethod(
  Permissions.Admin,
  async (payload) => {
    const response = await fetch("https://YOUR-RENDER-SERVICE.onrender.com/api/contact-updates/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        odoo_url: payload.odooUrl,
        odoo_db: payload.odooDb,
        odoo_username: payload.odooUsername,
        odoo_password: payload.odooPassword,
        start_date: payload.startDate,
        end_date: payload.endDate,
        timezone_name: "America/Regina",
        limit: 250,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data?.detail || "Render API request failed");
    }

    return data;
  },
);

