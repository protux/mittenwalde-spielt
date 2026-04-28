from __future__ import annotations

import argparse
import os
import smtplib
import sys
from dataclasses import dataclass
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Sequence

from icalendar import Calendar
from zoneinfo import ZoneInfo

from scripts.generate_cancelled_dates import (
    BERLIN_TIMEZONE,
    collect_effective_cancelled_dates,
)

MONTH_NAMES_GERMAN: dict[int, str] = {
    1: "Januar",
    2: "Februar",
    3: "März",
    4: "April",
    5: "Mai",
    6: "Juni",
    7: "Juli",
    8: "August",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Dezember",
}


@dataclass(frozen=True)
class QuarterlyCancelledDatesConfig:
    ics_file_path: Path


def get_previous_quarter(reference_date: date) -> tuple[int, int]:
    current_quarter = ((reference_date.month - 1) // 3) + 1
    if current_quarter == 1:
        return reference_date.year - 1, 4
    return reference_date.year, current_quarter - 1


def collect_cancelled_dates_for_quarter(
    config: QuarterlyCancelledDatesConfig,
    year: int,
    quarter: int,
) -> list[date]:
    calendar_bytes = config.ics_file_path.read_bytes()
    calendar = Calendar.from_ical(calendar_bytes)

    effective_cancelled_dates = collect_effective_cancelled_dates(calendar)
    first_month_of_quarter = (quarter - 1) * 3 + 1
    last_month_of_quarter = first_month_of_quarter + 2

    return [
        cancelled_date
        for cancelled_date in effective_cancelled_dates
        if cancelled_date.year == year
        and first_month_of_quarter <= cancelled_date.month <= last_month_of_quarter
    ]


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set.")
    return value


def build_email_subject(year: int, quarter: int) -> str:
    return f"Ausfalltermine Raummiete Brusendorf – Q{quarter} {year}"


def build_email_body(
    cancelled_dates: list[date],
    year: int,
    quarter: int,
    sender_name: str,
) -> str:
    if not cancelled_dates:
        lines = [
            "Guten Tag,",
            "",
            f"im Quartal Q{quarter} {year} sind keine Termine der Spielegruppe ausgefallen.",
            "",
            "Liebe Grüße,",
            sender_name,
            "",
        ]
        return "\n".join(lines)

    formatted_dates = [
        cancelled_date.strftime("%d.%m.%Y") for cancelled_date in cancelled_dates
    ]

    lines = [
        "Guten Tag,",
        "",
        f"im Quartal Q{quarter} {year} sind von unserer montäglichen Reservierung um 18 Uhr folgende Termine ausgefallen:",
        "",
    ]

    for formatted_date in formatted_dates:
        lines.append(f"- {formatted_date}")

    lines.extend(
        [
            "",
            "Liebe Grüße,",
            sender_name,
            "",
        ]
    )

    return "\n".join(lines)


def send_email(subject: str, body: str) -> None:
    smtp_host = _require_env("SMTP_HOST")
    smtp_port_raw = _require_env("SMTP_PORT")
    smtp_username = _require_env("SMTP_USERNAME")
    smtp_password = _require_env("SMTP_PASSWORD")
    to_address = _require_env("REPORT_TO_ADDRESS")
    sender_name = _require_env("REPORT_SENDER_NAME")

    cc_address = os.environ.get("REPORT_CC_ADDRESS")

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT must be an integer.") from exc

    from_address = smtp_username

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = to_address
    if cc_address:
        message["Cc"] = cc_address
        recipients = [to_address, cc_address]
    else:
        recipients = [to_address]

    message.set_content(body)

    with smtplib.SMTP(host=smtp_host, port=smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(message, from_addr=from_address, to_addrs=recipients)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send quarterly cancelled dates email for Spielegruppe."
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Target year for the report (default: previous quarter based on Berlin time).",
    )
    parser.add_argument(
        "--quarter",
        type=int,
        choices=range(1, 5),
        help="Target quarter for the report (1-4, default: previous quarter based on Berlin time).",
    )
    parser.add_argument(
        "--ics-file-path",
        type=Path,
        default=Path("static/Mittenwalde-spielt.ics"),
        help="Path to the calendar .ics file.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def determine_target_year_quarter(
    args: argparse.Namespace,
    timezone: ZoneInfo,
) -> tuple[int, int]:
    if (args.year is None) != (args.quarter is None):
        raise ValueError("Provide --year and --quarter together, or provide neither.")
    if args.year is not None and args.quarter is not None:
        return args.year, args.quarter

    now_in_timezone = datetime.now(timezone).date()
    return get_previous_quarter(now_in_timezone)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    target_year, target_quarter = determine_target_year_quarter(args, BERLIN_TIMEZONE)

    config = QuarterlyCancelledDatesConfig(
        ics_file_path=args.ics_file_path,
    )

    cancelled_dates = collect_cancelled_dates_for_quarter(
        config=config,
        year=target_year,
        quarter=target_quarter,
    )

    sender_name = _require_env("REPORT_SENDER_NAME")

    subject = build_email_subject(year=target_year, quarter=target_quarter)
    body = build_email_body(
        cancelled_dates=cancelled_dates,
        year=target_year,
        quarter=target_quarter,
        sender_name=sender_name,
    )

    print(
        f"Preparing to send quarterly cancelled dates email for Q{target_quarter}/{target_year}."
    )

    send_email(subject=subject, body=body)

    print("Quarterly cancelled dates email sent successfully.")


if __name__ == "__main__":
    main(sys.argv[1:])
