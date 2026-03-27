import { fetchContactUpdates } from "backend/contactUpdates.web";

$w.onReady(() => {
  const today = new Date();
  const start = new Date(today);
  start.setDate(today.getDate() - 6);

  $w("#startDatePicker").value = start;
  $w("#endDatePicker").value = today;
  $w("#resultsTable").rows = [];
  $w("#statusText").text = "";

  $w("#runButton").onClick(runQuery);
});

async function runQuery() {
  $w("#statusText").text = "Loading contact updates...";
  $w("#runButton").disable();

  try {
    const result = await fetchContactUpdates({
      startDate: toIsoDate($w("#startDatePicker").value),
      endDate: toIsoDate($w("#endDatePicker").value),
    });

    $w("#resultsTable").rows = result.contacts.map((contact) => ({
      name: contact.name,
      company: contact.company_name || contact.parent_company,
      email: contact.email,
      phone: contact.phone || contact.mobile,
      updatedAt: contact.last_update_at,
      sources: contact.update_sources.join(", "),
      note: contact.latest_note_preview,
      activity: contact.latest_activity_summary || contact.latest_activity_note,
    }));

    $w("#statusText").text = `${result.contact_count} contacts found from ${result.start_date} to ${result.end_date}.`;
  } catch (error) {
    const message = error?.message || "Unexpected error";
    $w("#statusText").text = `Request failed: ${message}`;
  } finally {
    $w("#runButton").enable();
  }
}

function toIsoDate(value) {
  if (!value) {
    return null;
  }

  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, "0");
  const day = `${value.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}
