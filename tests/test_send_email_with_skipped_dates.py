from __future__ import annotations

from datetime import date
from pathlib import Path

from textwrap import dedent

from scripts.send_email_with_skipped_dates import (
    QuarterlyCancelledDatesConfig,
    build_email_body,
    build_email_subject,
    collect_cancelled_dates_for_quarter,
    get_previous_quarter,
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


def test_get_previous_quarter_wraps_year_boundary() -> None:
    # Arrange / Act
    year, quarter = get_previous_quarter(date(2025, 1, 15))

    # Assert
    assert year == 2024
    assert quarter == 4


def test_get_previous_quarter_same_year() -> None:
    # Arrange / Act
    year, quarter = get_previous_quarter(date(2025, 5, 1))

    # Assert
    assert year == 2025
    assert quarter == 1


def test_build_email_subject_uses_quarter() -> None:
    # Arrange / Act
    subject = build_email_subject(year=2025, quarter=3)

    # Assert
    assert "Q3 2025" in subject


def test_build_email_body_without_cancelled_dates() -> None:
    # Arrange
    cancelled_dates: list[date] = []
    sender_name = "Test Sender"

    # Act
    body = build_email_body(
        cancelled_dates=cancelled_dates,
        year=2025,
        quarter=1,
        sender_name=sender_name,
    )

    # Assert
    assert "Quartal Q1 2025" in body
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
        quarter=1,
        sender_name=sender_name,
    )

    # Assert
    assert "Quartal Q1 2025" in body
    assert "- 03.02.2025" in body
    assert "- 10.02.2025" in body
    assert "montäglichen Reservierung um 18 Uhr" in body
    assert "Liebe Grüße," in body
    assert sender_name in body


def test_collect_cancelled_dates_for_quarter_filters_to_given_quarter(
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
        BEGIN:VEVENT
        UID:other-quarter
        DTSTAMP:20250101T000000Z
        DTSTART;VALUE=DATE:20250401
        EXDATE;VALUE=DATE:20250407
        END:VEVENT
        """).strip()

    ics_bytes = _build_basic_calendar(vevent_blocks)
    ics_path.parent.mkdir(parents=True, exist_ok=True)
    ics_path.write_bytes(ics_bytes)

    config = QuarterlyCancelledDatesConfig(ics_file_path=ics_path)

    # Act
    cancelled_dates = collect_cancelled_dates_for_quarter(
        config=config,
        year=2025,
        quarter=1,
    )

    # Assert
    assert date(2025, 2, 10) in cancelled_dates
    assert date(2025, 2, 17) in cancelled_dates
    assert date(2025, 3, 10) in cancelled_dates
    assert date(2025, 4, 7) not in cancelled_dates
    assert all(cancelled_date.year == 2025 for cancelled_date in cancelled_dates)
    assert all(1 <= cancelled_date.month <= 3 for cancelled_date in cancelled_dates)
