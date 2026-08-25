from pathlib import Path

path = Path(r"C:\turn-time-management\frontend\src\pages\OperationsPage.tsx")
text = path.read_text(encoding="utf-8")
original = text

replacements = [
    (
        """    dateFrom: activeDateRange.dateFrom,
    dateTo: activeDateRange.dateTo,
  };

  const {
    dashboard,
""",
        """    dateFrom: activeDateRange.dateFrom,
    dateTo: activeDateRange.dateTo,
    timeFrom: globalFilters.timeFrom,
    timeTo: globalFilters.timeTo,
  };

  const {
    dashboard,
""",
    ),
    (
        """      dateFrom: weekComparisonRanges.current.dateFrom,
      dateTo: weekComparisonRanges.current.dateTo,
    },
    globalFilters.compareMode === "previous-week",
""",
        """      dateFrom: weekComparisonRanges.current.dateFrom,
      dateTo: weekComparisonRanges.current.dateTo,
      timeFrom: globalFilters.timeFrom,
      timeTo: globalFilters.timeTo,
    },
    globalFilters.compareMode === "previous-week",
""",
    ),
    (
        """      dateFrom: comparisonRange?.dateFrom,
      dateTo: comparisonRange?.dateTo,
    },
    globalFilters.compareMode !== "off",
""",
        """      dateFrom: comparisonRange?.dateFrom,
      dateTo: comparisonRange?.dateTo,
      timeFrom: globalFilters.timeFrom,
      timeTo: globalFilters.timeTo,
    },
    globalFilters.compareMode !== "off",
""",
    ),
]

for old, new in replacements:
    if old in text:
        text = text.replace(old, new, 1)

if text == original:
    raise SystemExit(
        "No changes applied. The expected OperationsPage blocks "
        "may already be updated."
    )

path.write_text(text, encoding="utf-8", newline="\n")
print("Updated:", path)
print("Added timeFrom/timeTo to live and comparison dashboard filters.")
