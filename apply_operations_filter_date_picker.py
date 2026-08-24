from pathlib import Path

path = Path(r"C:\turn-time-management\frontend\src\components\OperationsFilterBar.tsx")
text = path.read_text(encoding="utf-8")

# Add values used by the always-visible date range picker.
anchor = '''  const update = <K extends keyof OperationsGlobalFilters>(
    key: K,
    value: OperationsGlobalFilters[K],
  ) => onChange({ ...filters, [key]: value });

  return (
'''

replacement = '''  const update = <K extends keyof OperationsGlobalFilters>(
    key: K,
    value: OperationsGlobalFilters[K],
  ) => onChange({ ...filters, [key]: value });

  const activePickerRange = getPresetRange(
    filters.datePreset,
    filters.customDate,
    filters.customDateEnd,
  );

  const activePickerEnd = fromLocalDate(activePickerRange.dateTo);
  activePickerEnd.setDate(activePickerEnd.getDate() - 1);

  const pickerStart =
    filters.datePreset === "custom"
      ? filters.customDate ?? activePickerRange.dateFrom
      : activePickerRange.dateFrom;

  const pickerEnd =
    filters.datePreset === "custom"
      ? filters.customDateEnd ?? pickerStart
      : toLocalDate(activePickerEnd);

  return (
'''

if anchor not in text:
    raise RuntimeError("Could not find the update/return anchor in OperationsFilterBar.tsx.")

text = text.replace(anchor, replacement, 1)

# Replace preset buttons / custom mode with a single always-visible date range picker.
start_marker = '        {filters.datePreset === "custom" ? ('
end_marker = '        <label className="compare-control">'

start = text.find(start_marker)
end = text.find(end_marker, start)

if start == -1 or end == -1:
    raise RuntimeError("Could not find the existing date preset block.")

date_picker = '''        <div
          className="custom-date-range-control"
          aria-label="Operating date range"
        >
          <div className="custom-date-range-track">
            <label>
              <span>From</span>
              <input
                type="date"
                value={pickerStart}
                max={pickerEnd}
                onChange={(event) => {
                  const nextStart = event.target.value;
                  const nextEnd =
                    pickerEnd && pickerEnd < nextStart
                      ? nextStart
                      : pickerEnd;

                  onChange({
                    ...filters,
                    datePreset: "custom",
                    customDate: nextStart,
                    customDateEnd: nextEnd,
                  });
                }}
              />
            </label>

            <span
              className="custom-date-range-arrow"
              aria-hidden="true"
            >
              →
            </span>

            <label>
              <span>To</span>
              <input
                type="date"
                value={pickerEnd}
                min={pickerStart}
                onChange={(event) =>
                  onChange({
                    ...filters,
                    datePreset: "custom",
                    customDate: pickerStart,
                    customDateEnd: event.target.value,
                  })
                }
              />
            </label>
          </div>
        </div>

'''

text = text[:start] + date_picker + text[end:]

# Appointment dropdown: "All" is the empty/default value.
text = text.replace(
    '<option value="">Inbound & outbound</option>',
    '<option value="">All</option>',
    1,
)

# Reset returns to today's date, All appointments, comparison off.
old_reset = '''            onChange({
              datePreset: "today",
              compareMode: "off",
            })'''

new_reset = '''            onChange({
              datePreset: "today",
              compareMode: "off",
              appointmentType: undefined,
            })'''

if old_reset in text:
    text = text.replace(old_reset, new_reset, 1)

path.write_text(text, encoding="utf-8", newline="\n")
print("Updated OperationsFilterBar.tsx")
print("Default operating date: Today")
print("Default appointment filter: All")
