import unittest
from datetime import datetime, timedelta

from src.discord.sitestatus import (
    STATUS_GOOD_SYMBOL,
    STATUS_MAJOR_OUTAGE_SYMBOL,
    STATUS_MINOR_OUTAGE_SYMBOL,
    STATUS_OFFLINE_SYMBOL,
    SiteStatus,
)
from src.discord.sitestatusmodels import AggregateStatus, SiteHTTPResult


class SiteStatusTest(unittest.TestCase):
    """
    Test cases for generating uptime strings from polling results
    """

    @classmethod
    def key_sort(cls, agg: AggregateStatus):
        return agg.recordedAt

    def test_small_nominal_uptime(self):
        domain_uptime_results: list[AggregateStatus] = [
            AggregateStatus(
                ping=30.2,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=0,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=35.7,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=10,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=26.8,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=20,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=31.4,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=30,
                    second=0,
                ),
            ),
        ]

        domain_uptime_results.sort(key=SiteStatusTest.key_sort)

        EMBED_LENGTH = 4
        LOOKBACK_LENGTH = 40
        expected_last_element = domain_uptime_results[-1]
        (
            embed_string,
            circle_interval,
            uptime_percent,
            last_element,
        ) = SiteStatus.construct_uptime_string(
            domain_uptime_results,
            datetime(
                year=2024,
                month=2,
                day=1,
                hour=6,
                minute=33,
                second=21,
            ),
            lookback_range=timedelta(
                minutes=LOOKBACK_LENGTH,
            ),
            embed_field_length=EMBED_LENGTH,
        )
        self.assertEqual(
            embed_string,
            f"{STATUS_GOOD_SYMBOL * 4}",
        )
        self.assertEqual(
            circle_interval,
            timedelta(minutes=LOOKBACK_LENGTH / EMBED_LENGTH),
        )
        self.assertEqual(
            uptime_percent,
            1.0,
        )
        self.assertEqual(last_element, expected_last_element)

    def test_padded_nominal_uptime(self):
        domain_uptime_results: list[AggregateStatus] = [
            AggregateStatus(
                ping=30.2,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=0,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=35.7,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=10,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=26.8,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=20,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=31.4,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=30,
                    second=0,
                ),
            ),
        ]

        domain_uptime_results.sort(key=SiteStatusTest.key_sort)

        EMBED_LENGTH = 24
        LOOKBACK_LENGTH = 240
        expected_last_element = domain_uptime_results[-1]
        (
            embed_string,
            circle_interval,
            uptime_percent,
            last_element,
        ) = SiteStatus.construct_uptime_string(
            domain_uptime_results,
            datetime(
                year=2024,
                month=2,
                day=1,
                hour=6,
                minute=33,
                second=21,
            ),
            lookback_range=timedelta(
                minutes=LOOKBACK_LENGTH,
            ),
            embed_field_length=EMBED_LENGTH,
        )
        self.assertEqual(
            embed_string,
            f"{STATUS_OFFLINE_SYMBOL * (EMBED_LENGTH - 4)}{STATUS_GOOD_SYMBOL * 4}",
        )
        self.assertEqual(
            circle_interval,
            timedelta(minutes=LOOKBACK_LENGTH / EMBED_LENGTH),
        )
        self.assertEqual(
            uptime_percent,
            1.0,
        )
        self.assertEqual(last_element, expected_last_element)

    def test_no_uptime_reults(self):
        domain_uptime_results: list[AggregateStatus] = []

        EMBED_LENGTH = 24
        LOOKBACK_LENGTH = 240
        (
            embed_string,
            circle_interval,
            uptime_percent,
            last_element,
        ) = SiteStatus.construct_uptime_string(
            domain_uptime_results,
            datetime(
                year=2024,
                month=2,
                day=1,
                hour=6,
                minute=33,
                second=21,
            ),
            lookback_range=timedelta(
                minutes=LOOKBACK_LENGTH,
            ),
            embed_field_length=EMBED_LENGTH,
        )
        self.assertEqual(
            embed_string,
            f"{STATUS_OFFLINE_SYMBOL * EMBED_LENGTH}",
        )
        self.assertEqual(
            circle_interval,
            timedelta(minutes=LOOKBACK_LENGTH / EMBED_LENGTH),
        )
        self.assertEqual(
            uptime_percent,
            None,
        )
        self.assertEqual(last_element, None)

    def test_small_range_anomaly(self):
        domain_uptime_results: list[AggregateStatus] = [
            AggregateStatus(
                ping=30.2,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=0,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=35.7,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=503),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=10,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=26.8,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=503),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=20,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=31.4,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=30,
                    second=0,
                ),
            ),
        ]

        domain_uptime_results.sort(key=SiteStatusTest.key_sort)

        EMBED_LENGTH = 4
        LOOKBACK_LENGTH = 40
        expected_last_element = domain_uptime_results[-1]
        (
            embed_string,
            circle_interval,
            uptime_percent,
            last_element,
        ) = SiteStatus.construct_uptime_string(
            domain_uptime_results,
            datetime(
                year=2024,
                month=2,
                day=1,
                hour=6,
                minute=33,
                second=21,
            ),
            lookback_range=timedelta(
                minutes=LOOKBACK_LENGTH,
            ),
            embed_field_length=EMBED_LENGTH,
        )
        self.assertEqual(
            embed_string,
            f"{STATUS_GOOD_SYMBOL}{STATUS_MAJOR_OUTAGE_SYMBOL * 2}{STATUS_GOOD_SYMBOL}",
        )
        self.assertEqual(
            circle_interval,
            timedelta(minutes=LOOKBACK_LENGTH / EMBED_LENGTH),
        )
        self.assertEqual(
            uptime_percent,
            2 / 4,
        )
        self.assertEqual(last_element, expected_last_element)

    def test_major_and_minor_anomaly(self):
        domain_uptime_results: list[AggregateStatus] = [
            AggregateStatus(
                ping=35.7,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=503),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=10,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=31.4,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=20,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=26.8,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=503),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=30,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=36.1,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=40,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=39.8,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=6,
                    minute=50,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=27.3,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=7,
                    minute=0,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=31.2,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=7,
                    minute=10,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=34.4,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=7,
                    minute=20,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=35.2,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=7,
                    minute=30,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=None,
                http=None,
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=7,
                    minute=40,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=41.2,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=7,
                    minute=50,
                    second=0,
                ),
            ),
            AggregateStatus(
                ping=31.0,
                http=SiteHTTPResult(url="www.scioly.org/forums", status_code=200),
                recordedAt=datetime(
                    year=2024,
                    month=2,
                    day=1,
                    hour=8,
                    minute=0,
                    second=0,
                ),
            ),
        ]

        domain_uptime_results.sort(key=SiteStatusTest.key_sort)

        EMBED_LENGTH = 4
        LOOKBACK_LENGTH = 120
        expected_last_element = domain_uptime_results[-1]
        (
            embed_string,
            circle_interval,
            uptime_percent,
            last_element,
        ) = SiteStatus.construct_uptime_string(
            domain_uptime_results,
            datetime(
                year=2024,
                month=2,
                day=1,
                hour=8,
                minute=4,
                second=12,
            ),
            lookback_range=timedelta(
                minutes=LOOKBACK_LENGTH,
            ),
            embed_field_length=EMBED_LENGTH,
        )
        self.assertEqual(
            embed_string,
            f"{STATUS_MAJOR_OUTAGE_SYMBOL}{STATUS_GOOD_SYMBOL * 2}{STATUS_MINOR_OUTAGE_SYMBOL}",
        )
        self.assertEqual(
            circle_interval,
            timedelta(minutes=LOOKBACK_LENGTH / EMBED_LENGTH),
        )
        self.assertEqual(
            uptime_percent,
            9 / 12,
        )
        self.assertEqual(last_element, expected_last_element)
