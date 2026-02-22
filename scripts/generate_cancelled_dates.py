from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import yaml
from icalendar import Calendar
from zoneinfo import ZoneInfo


BERLIN_TIMEZONE = ZoneInfo("Europe/Berlin")
BEGIN_MARKER = "<!-- BEGIN GENERATED: cancelled-dates -->"
END_MARKER = "<!-- END GENERATED: cancelled-dates -->"


@dataclass(frozen=True)
class CancelledDateEntry:
    cancelled_date: date
    label: str | None


def _to_berlin_date(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=BERLIN_TIMEZONE)
        return value.astimezone(BERLIN_TIMEZONE).date()
    return None


def _load_labels(labels_file_path: Path) -> dict[date, str]:
    if not labels_file_path.exists():
        return {}

    raw_mapping = yaml.safe_load(labels_file_path.read_text(encoding="utf-8")) or {}
    labels_by_date: dict[date, str] = {}
    for iso_date_string, label in raw_mapping.items():
        if not isinstance(iso_date_string, str) or not isinstance(label, str):
            continue
        labels_by_date[date.fromisoformat(iso_date_string)] = label.strip()
    return labels_by_date


def _extract_exdates(component: object) -> Iterable[date]:
    exdate_property = getattr(component, "get", lambda _: None)("exdate")
    if not exdate_property:
        return []

    extracted_dates: list[date] = []

    # transform to list, if icalendar returns a single instance
    exdate_items = (
        exdate_property if isinstance(exdate_property, list) else [exdate_property]
    )
    for exdate_item in exdate_items:
        date_times = getattr(exdate_item, "dts", None)
        if not date_times:
            continue
        for date_time in date_times:
            cancelled_date = _to_berlin_date(getattr(date_time, "dt", None))
            if cancelled_date:
                extracted_dates.append(cancelled_date)

    return extracted_dates


def _extract_cancelled_event_dates(component: object) -> Iterable[date]:
    status = str(getattr(component, "get", lambda _: "")("status") or "").upper()
    if status != "CANCELLED":
        return []

    recurrence_id = getattr(component, "get", lambda _: None)("recurrence-id")
    dtstart = getattr(component, "get", lambda _: None)("dtstart")

    recurrence_value = getattr(recurrence_id, "dt", None) if recurrence_id else None
    dtstart_value = getattr(dtstart, "dt", None) if dtstart else None

    cancelled_date = _to_berlin_date(recurrence_value) or _to_berlin_date(dtstart_value)
    return [cancelled_date] if cancelled_date else []


def _render_markdown_list(entries: list[CancelledDateEntry]) -> str:
    if not entries:
        return "Aktuell sind keine Ausfalltermine geplant! 🥳\n"

    lines: list[str] = []
    for entry in entries:
        formatted_date = entry.cancelled_date.strftime("%d.%m.%Y")
        if entry.label:
            lines.append(f"- {formatted_date} ({entry.label})")
        else:
            lines.append(f"- {formatted_date}")
    return "\n".join(lines) + "\n"


def _replace_generated_block(full_text: str, generated_text: str) -> str:
    begin_index = full_text.find(BEGIN_MARKER)
    end_index = full_text.find(END_MARKER)
    if begin_index == -1 or end_index == -1 or end_index < begin_index:
        raise ValueError("Markers not found or in wrong order in skip.md")

    before = full_text[: begin_index + len(BEGIN_MARKER)]
    after = full_text[end_index:]
    return before + "\n" + generated_text + after


def main() -> None:
    ics_file_path = Path("static/Mittenwalde-spielt.ics")
    skip_markdown_file_path = Path("content/de/homepage/skip.md")
    labels_file_path = Path("data/skip_labels.yml")

    calendar_text = ics_file_path.read_bytes()
    calendar = Calendar.from_ical(calendar_text)

    today_in_berlin = datetime.now(BERLIN_TIMEZONE).date()
    labels_by_date = _load_labels(labels_file_path)

    cancelled_dates: set[date] = set()

    for component in calendar.walk():
        if getattr(component, "name", "").upper() != "VEVENT":
            continue

        for cancelled_date in _extract_exdates(component):
            cancelled_dates.add(cancelled_date)

        for cancelled_date in _extract_cancelled_event_dates(component):
            cancelled_dates.add(cancelled_date)

    filtered_sorted_dates = sorted(d for d in cancelled_dates if d >= today_in_berlin)
    entries = [
        CancelledDateEntry(
            cancelled_date=cancelled_date, label=labels_by_date.get(cancelled_date)
        )
        for cancelled_date in filtered_sorted_dates
    ]

    generated_block_text = _render_markdown_list(entries)

    skip_text = skip_markdown_file_path.read_text(encoding="utf-8")
    updated_skip_text = _replace_generated_block(skip_text, generated_block_text)

    skip_markdown_file_path.write_text(updated_skip_text, encoding="utf-8")


if __name__ == "__main__":
    main()
