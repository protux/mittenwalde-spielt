from __future__ import annotations

from datetime import date
from pathlib import Path

from textwrap import dedent

from icalendar import Calendar

from scripts.send_email_with_skipped_dates import (
    MONTH_NAMES_GERMAN,
    MonthlyCancelledDatesConfig,
    build_email_body,
    build_email_subject,
    collect_cancelled_dates_for_month,
    get_previous_month,
)


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


def test_get_previous_month_wraps_year_boundary() -> None:
    # Arrange / Act
    year, month = get_previous_month(date(2025, 1, 15))

    # Assert
    assert year == 2024
    assert month == 12


def test_get_previous_month_same_year() -> None:
    # Arrange / Act
    year, month = get_previous_month(date(2025, 3, 1))

    # Assert
    assert year == 2025
    assert month == 2


def test_build_email_subject_uses_german_month_name() -> None:
    # Arrange / Act
    subject = build_email_subject(year=2025, month=3)

    # Assert
    assert "März 2025" in subject


def test_build_email_body_without_cancelled_dates() -> None:
    # Arrange
    cancelled_dates: list[date] = []
    sender_name = "Test Sender"

    # Act
    body = build_email_body(
        cancelled_dates=cancelled_dates,
        year=2025,
        month=2,
        sender_name=sender_name,
    )

    # Assert
    assert "keine Termine der Spielegruppe ausgefallen" in body
    assert "Liebe Grüße," in body
    assert sender_name in body


def test_build_email_body_with_cancelled_dates() -> None:
    # Arrange
    cancelled_dates = [date(2025, 2, 3), date(2025, 2, 10)]
    sender_name = "Test Sender"

    # Act
    body = build_email_body(
        cancelled_dates=cancelled_dates,
        year=2025,
        month=2,
        sender_name=sender_name,
    )

    # Assert
    assert "- 03.02.2025" in body
    assert "- 10.02.2025" in body
    assert "montäglichen Reservierung um 18 Uhr" in body
    assert "Liebe Grüße," in body
    assert sender_name in body


def test_collect_cancelled_dates_for_month_filters_to_given_month(
    tmp_path: Path,
) -> None:
    # Arrange
    ics_path = tmp_path / "static" / "calendar.ics"

    vevent_blocks = dedent("""
        BEGIN:VEVENT
        UID:series-1
        DTSTAMP:20250101T000000Z
        DTSTART;VALUE=DATE:20250203
        EXDATE;VALUE=DATE:20250210
        END:VEVENT
        BEGIN:VEVENT
        UID:instance-cancelled
        DTSTAMP:20250101T000000Z
        STATUS:CANCELLED
        RECURRENCE-ID;VALUE=DATE:20250217
        DTSTART;VALUE=DATE:20250217
        END:VEVENT
        BEGIN:VEVENT
        UID:replacement-instance
        DTSTAMP:20250101T000000Z
        RECURRENCE-ID;VALUE=DATE:20250224
        DTSTART;VALUE=DATE:20250224
        END:VEVENT
        BEGIN:VEVENT
        UID:other-month
        DTSTAMP:20250101T000000Z
        DTSTART;VALUE=DATE:20250301
        EXDATE;VALUE=DATE:20250310
        END:VEVENT
        """).strip()

    ics_bytes = _build_basic_calendar(vevent_blocks)
    ics_path.parent.mkdir(parents=True, exist_ok=True)
    ics_path.write_bytes(ics_bytes)

    config = MonthlyCancelledDatesConfig(ics_file_path=ics_path)

    # Act
    cancelled_dates = collect_cancelled_dates_for_month(
        config=config,
        year=2025,
        month=2,
    )

    # Assert
    assert date(2025, 2, 10) in cancelled_dates
    assert date(2025, 2, 17) in cancelled_dates
    assert all(cancelled_date.month == 2 for cancelled_date in cancelled_dates)
