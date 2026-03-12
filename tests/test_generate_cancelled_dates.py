from __future__ import annotations

from datetime import date
from pathlib import Path
from textwrap import dedent

from icalendar import Calendar, Event, vDDDTypes

from scripts.generate_cancelled_dates import (
    BEGIN_MARKER,
    END_MARKER,
    CancelledDateEntry,
    collect_effective_cancelled_dates,
    _extract_active_event_dates,
    _extract_cancelled_event_dates,
    _extract_exdates,
    _render_markdown_list,
    generate_cancelled_dates,
)


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _build_basic_calendar(vevent_blocks: str) -> bytes:
    stripped_vevent_blocks = vevent_blocks.strip()
    calendar_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Test Calendar//EN",
        stripped_vevent_blocks,
        "END:VCALENDAR",
        "",
    ]
    calendar_text = "\r\n".join(calendar_lines)
    return calendar_text.encode("utf-8")


def _build_calendar(vevent_blocks: str) -> Calendar:
    ics_bytes = _build_basic_calendar(vevent_blocks)
    return Calendar.from_ical(ics_bytes)


def test_render_markdown_list_with_and_without_labels() -> None:
    # Arrange
    entries = [
        CancelledDateEntry(cancelled_date=date(2025, 5, 1), label=None),
        CancelledDateEntry(cancelled_date=date(2025, 5, 2), label="Holiday"),
    ]

    # Act
    rendered = _render_markdown_list(entries)

    # Assert
    assert rendered == "- 01.05.2025\n- 02.05.2025 (Holiday)\n"


def test_render_markdown_list_when_empty() -> None:
    # Arrange
    entries: list[CancelledDateEntry] = []

    # Act
    rendered = _render_markdown_list(entries)

    # Assert
    assert "Aktuell sind keine Ausfalltermine geplant" in rendered


def test_extract_exdates_returns_all_exception_dates() -> None:
    # Arrange
    component = Event()
    component.add("uid", "series-1")
    component.add("dtstart", date(2025, 5, 1))
    component.add("exdate", vDDDTypes(date(2025, 5, 2)))
    component.add("exdate", vDDDTypes(date(2025, 5, 3)))

    # Act
    extracted_dates = list(_extract_exdates(component))

    # Assert
    assert date(2025, 5, 2) in extracted_dates
    assert date(2025, 5, 3) in extracted_dates


def test_extract_cancelled_event_dates_uses_recurrence_id_if_present() -> None:
    # Arrange
    component = Event()
    component.add("uid", "instance-1")
    component.add("status", "CANCELLED")
    component.add("recurrence-id", vDDDTypes(date(2025, 5, 4)))
    component.add("dtstart", vDDDTypes(date(2025, 5, 5)))

    # Act
    extracted_dates = list(_extract_cancelled_event_dates(component))

    # Assert
    assert extracted_dates == [date(2025, 5, 4)]


def test_extract_cancelled_event_dates_uses_dtstart_if_no_recurrence_id() -> None:
    # Arrange
    component = Event()
    component.add("uid", "single-1")
    component.add("status", "CANCELLED")
    component.add("dtstart", vDDDTypes(date(2025, 5, 6)))

    # Act
    extracted_dates = list(_extract_cancelled_event_dates(component))

    # Assert
    assert extracted_dates == [date(2025, 5, 6)]


def test_extract_active_event_dates_ignores_cancelled_events() -> None:
    # Arrange
    component = Event()
    component.add("uid", "cancelled-1")
    component.add("status", "CANCELLED")
    component.add("dtstart", vDDDTypes(date(2025, 5, 7)))

    # Act
    extracted_dates = list(_extract_active_event_dates(component))

    # Assert
    assert extracted_dates == []


def test_extract_active_event_dates_prefers_recurrence_id() -> None:
    # Arrange
    component = Event()
    component.add("uid", "instance-2")
    component.add("dtstart", vDDDTypes(date(2025, 5, 8)))
    component.add("recurrence-id", vDDDTypes(date(2025, 5, 9)))

    # Act
    extracted_dates = list(_extract_active_event_dates(component))

    # Assert
    assert extracted_dates == [date(2025, 5, 9)]


def test_generate_cancelled_dates_with_simple_exdate(tmp_path: Path) -> None:
    # Arrange
    ics_path = tmp_path / "static" / "calendar.ics"
    skip_markdown_path = tmp_path / "content" / "de" / "homepage" / "skip.md"
    labels_path = tmp_path / "data" / "skip_labels.yml"

    vevent_blocks = dedent("""
        BEGIN:VEVENT
        UID:series-1
        DTSTAMP:20250101T000000Z
        DTSTART;VALUE=DATE:20990501
        EXDATE;VALUE=DATE:20990510
        END:VEVENT
        """).strip()

    ics_bytes = _build_basic_calendar(vevent_blocks)
    ics_path.parent.mkdir(parents=True, exist_ok=True)
    ics_path.write_bytes(ics_bytes)

    _write_file(
        skip_markdown_path,
        f"{BEGIN_MARKER}\nOLD\n{END_MARKER}\n",
    )
    _write_file(labels_path, "")

    # Act
    generate_cancelled_dates(
        ics_file_path=ics_path,
        skip_markdown_file_path=skip_markdown_path,
        labels_file_path=labels_path,
    )

    # Assert
    updated_skip = _read_file(skip_markdown_path)
    assert "2099" in updated_skip
    assert "10.05.2099" in updated_skip
    assert "OLD" not in updated_skip


def test_generate_cancelled_dates_filters_replaced_cancelled_dates(
    tmp_path: Path,
) -> None:
    # Arrange
    ics_path = tmp_path / "static" / "calendar.ics"
    skip_markdown_path = tmp_path / "content" / "de" / "homepage" / "skip.md"
    labels_path = tmp_path / "data" / "skip_labels.yml"

    vevent_blocks = dedent("""
        BEGIN:VEVENT
        UID:series-1
        DTSTAMP:20250101T000000Z
        DTSTART;VALUE=DATE:20990501
        EXDATE;VALUE=DATE:20990510
        END:VEVENT
        BEGIN:VEVENT
        UID:instance-cancelled
        DTSTAMP:20250101T000000Z
        STATUS:CANCELLED
        RECURRENCE-ID;VALUE=DATE:20990520
        DTSTART;VALUE=DATE:20990520
        END:VEVENT
        BEGIN:VEVENT
        UID:replacement-instance
        DTSTAMP:20250101T000000Z
        RECURRENCE-ID;VALUE=DATE:20990520
        DTSTART;VALUE=DATE:20990520
        END:VEVENT
        """).strip()

    ics_bytes = _build_basic_calendar(vevent_blocks)
    ics_path.parent.mkdir(parents=True, exist_ok=True)
    ics_path.write_bytes(ics_bytes)

    _write_file(
        skip_markdown_path,
        f"{BEGIN_MARKER}\nOLD\n{END_MARKER}\n",
    )
    _write_file(labels_path, "")

    # Act
    generate_cancelled_dates(
        ics_file_path=ics_path,
        skip_markdown_file_path=skip_markdown_path,
        labels_file_path=labels_path,
    )

    # Assert
    updated_skip = _read_file(skip_markdown_path)
    assert "10.05.2099" in updated_skip
    assert "20.05.2099" not in updated_skip


def test_collect_effective_cancelled_dates_includes_exdates_and_cancelled_events() -> (
    None
):
    # Arrange
    vevent_blocks = dedent("""
        BEGIN:VEVENT
        UID:series-1
        DTSTAMP:20250101T000000Z
        DTSTART;VALUE=DATE:20250501
        EXDATE;VALUE=DATE:20250510
        END:VEVENT
        BEGIN:VEVENT
        UID:instance-cancelled
        DTSTAMP:20250101T000000Z
        STATUS:CANCELLED
        RECURRENCE-ID;VALUE=DATE:20250520
        DTSTART;VALUE=DATE:20250520
        END:VEVENT
        """).strip()
    calendar = _build_calendar(vevent_blocks)

    # Act
    effective_dates = collect_effective_cancelled_dates(calendar)

    # Assert
    assert date(2025, 5, 10) in effective_dates
    assert date(2025, 5, 20) in effective_dates


def test_collect_effective_cancelled_dates_excludes_replaced_dates() -> None:
    # Arrange
    vevent_blocks = dedent("""
        BEGIN:VEVENT
        UID:series-1
        DTSTAMP:20250101T000000Z
        DTSTART;VALUE=DATE:20250501
        EXDATE;VALUE=DATE:20250510
        END:VEVENT
        BEGIN:VEVENT
        UID:instance-cancelled
        DTSTAMP:20250101T000000Z
        STATUS:CANCELLED
        RECURRENCE-ID;VALUE=DATE:20250520
        DTSTART;VALUE=DATE:20250520
        END:VEVENT
        BEGIN:VEVENT
        UID:replacement-instance
        DTSTAMP:20250101T000000Z
        RECURRENCE-ID;VALUE=DATE:20250520
        DTSTART;VALUE=DATE:20250520
        END:VEVENT
        """).strip()
    calendar = _build_calendar(vevent_blocks)

    # Act
    effective_dates = collect_effective_cancelled_dates(calendar)

    # Assert
    assert date(2025, 5, 10) in effective_dates
    assert date(2025, 5, 20) not in effective_dates
