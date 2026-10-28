"""csv_safe keeps spreadsheet formulas from running in exported CSV files."""

import pytest

from hubra.api.utils import csv_safe


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('=HYPERLINK("http://x","y")', '\'=HYPERLINK("http://x","y")'),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("+cmd|' /C calc'!A0", "'+cmd|' /C calc'!A0"),
        ("-2+3+cmd", "'-2+3+cmd"),
        ("\tTab", "'\tTab"),
        ("+41 79 123 45 67", "+41 79 123 45 67"),
        ("-12.50", "-12.50"),
        ("Anna", "Anna"),
        ("", ""),
        (42, 42),
        (None, None),
    ],
)
def test_csv_safe(raw, expected):
    assert csv_safe(raw) == expected
