import { Permissions, webMethod } from "wix-web-module";
import { fetch } from "wix-fetch";
import { getSecret } from "wix-secrets-backend";

export const fetchContactUpdates = webMethod(
  Permissions.Admin,
  async (payload) => {
    const internalApiToken = await getSecret("renderInternalApiToken");
    const response = await fetch("https://YOUR-RENDER-SERVICE.onrender.com/api/contact-updates/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Token": internalApiToken,
      },
      body: JSON.stringify({
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
