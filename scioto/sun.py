""" The Sun's position does not change annually in any appreciable way, so
    it's convenient to spend the time to calculate a set of positions
    once and then reuse them for many different purposes.

    Here we will calculate the Sun's position for every minute throughout
    the year and save it as a JSON file (15.4 MB) for later use.
"""
import os
import datetime
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from bisect import bisect_right
from collections import UserList
import time

from skyfield.api import Loader, Topos
import pytz
from . import pairwise


BASE_FOLDER = Path('~/.scioto').expanduser()  # TODO Need a better choice
SUN_BASE = 'Sun-Minute-by-Minute'
SUN_POSITION = BASE_FOLDER / "Sun-Minute-by-Minute.json"
HORIZON_EVENTS = BASE_FOLDER / 'Horizon-Events.json'
TWILIGHT = -6


# TODO Add a call for a specific day that returns rise, set, day length, both azimuths
# TODO a call that builds a calendar of rise/set for a month or a year, text or html,
# TODO generate the pickle files somewhere else?

__all__ = ['load_sun', 'load_events']


@lru_cache(maxsize=1)
def load_sun():
    assert SUN_POSITION.exists(), f"You must create {SUN_POSITION.name} first!"
    return Sun(json.loads(SUN_POSITION.read_text()))


@lru_cache(maxsize=1)
def load_events():
    assert HORIZON_EVENTS.exists(), f"You must create {HORIZON_EVENTS.name} first!"
    return SunEvents(json.loads(HORIZON_EVENTS.read_text()))


class Position:
    """
    Wraps the Sun position tuple into a friendlier format
    that looks better both on the command line and in the Notebook.
    """
    def __init__(self, value, year=None):
        if year is None:
            year = datetime.date.today().year
        self.date = datetime.datetime(year, *value[:4])
        self.alt = value[4]
        self.az = value[5]

    def __repr__(self):
        return "{0.date:%A %-d %b %-H:%M} Alt={0.alt:.0f}° Az={0.az:.0f}°".format(self)

    def _repr_html_(self):
        """Having fun with display in the Jupyter Notebook"""
        # Yellow Sun = 0x1f31e, Black Sun = 0x2600
        if self.alt > 0:
            tag, front, behind = 'b', '&#x1f31e;', ''  # yellow sun, bold text
        else:
            tag, front, behind = 'em', '', '&#x2600;'  # black sun, italic text
        return f"{front}<{tag}>{self!r}</{tag}>{behind}"


class Sun(UserList):
    """
    Minute-by-minute positions of the Sun for an entire year.

    The position for each minute is stored as a tuple:
        (month, day, hour, minute, altitude, azimuth)

    now() return the tuple associated with the current time.

    at(*args) searches for the specified tuple.
    """
    def __repr__(self):
        return f"<Sun: {len(self.data):,} minute-by-minute positions>"

    def __getitem__(self, index):
        """Returns the Position at the specified index"""
        return Position(self.data[index])

    def at(self, *args):
        """
        Returns the `Position` of the Sun at a specified
        (month, day, hour, minute). You can
        use up to 4 arguments, depending on how close you want to specify.
        """
        index = bisect_right(self.data, list(args))
        if index:
            return self[index-1]
        raise ValueError

    def now(self):
        """Return the `Position` of the Sun at the current time"""
        date = datetime.datetime.now()
        return self.at(date.month, date.day, date.hour, date.minute)


class SunEvents(UserList):
    """
    A list of sunrise, sunset, and civil twilight events for the entire year.
    """
    def __repr__(self):
        return f"<Sun: {len(self):,} Events>"

    def at(self, *args):
        index = bisect_right(self.data, tuple(args))
        return Event(self[index])

    def on_date(self, month, day):
        key = [month, day]
        index = bisect_right(self.data, key)
        return [
            Event(value, datetime.date.today().year)
            for value in self[index:]
            if value[:2] == key
        ]

    def today(self):
        """Returns a list of the events for the current date"""
        date = datetime.date.today()
        key = [date.month, date.day]
        index = bisect_right(self.data, key)
        return DayEvents([
            Event(value, date.year)
            for value in self[index:]
            if value[:2] == key
        ])


class DayEvents(UserList):
    """Wraps all events for a given day."""
    def _repr_html_(self):
        s = []
        a = s.append
        a(f"<h2>Sun Events on {self[0].date:%A, %-d %B %Y}</h2>")
        a(f"<ul>")
        for ev in self:
            a(f"<li>{ev!s}</li>")
        a("</ul>")
        return ''.join(s)


class Event:
    def __init__(self, value, year=None):
        if year is None:
            year = datetime.date.today().year
        self.date = datetime.datetime(year, *value[:4])
        self.name = value[4]
        self.az = value[5]

    def __repr__(self):
        return f"{self.date:%a %d %b %H:%M} {self.name} {self.az}°"

    def __str__(self):
        if self.name in ('Rise', 'Set'):  # suppress azimuth for twilight events
            az = f"@{self.az}°"
        else:
            az = ''
        return f"{self.date:%-H:%M} {self.name} {az}"


# The functions below are for generating the position and events files
# and won't normally be needed except to regenerate the files, perhaps
# for a new geographic location.


def position(jd, alt, az, tz):
    """Returns a convenient tuple for the calculated Sun position."""
    date = jd.astimezone(tz=tz)
    return date.month, date.day, date.hour, date.minute, round(alt, 1), round(az, 1)


def compute_positions_for_date(date, *, latitude, longitude, elevation=0, tz):
    """Calculate the position of the Sun for every minute of the specified date."""
    # Set up Skyfield.
    loader = Loader(os.environ['SKYFIELD_LOADER_DIRECTORY'])
    planets = loader(os.getenv('SKYFIELD_SPICE_KERNEL', 'de421.bsp'))
    ts = loader.timescale()
    where = planets['earth'] + Topos(latitude_degrees=latitude,
                                     longitude_degrees=longitude,
                                     elevation_m=elevation)

    every_minute = ts.utc(date.year, date.month, date.day, 0, range(1440))
    alt, az, _ = where.at(every_minute).observe(planets['sun']).apparent().altaz()
    return [
        position(jd, alt, az, tz)
        for jd, alt, az in zip(every_minute, alt.degrees, az.degrees)
    ]


def _create_sun_minute_by_minute(*, latitude, longitude, elevation, tz):
    """
    Compute Sun locations for every minute over an entire year.
    Use `concurrent.futures` to calculate these days in parallel;
    it speeds up the process a fair amount.

    We calculate for a leap year so that the resulting table is
    useful for any year.

    Most recently it took 54.5 seconds to calculate the minute-by-minute data.

    My testing shows the the difference between doing this for a leap year
    and a non-leap year is minimal.
    """
    date = datetime.date(year=2020, month=1, day=1)
    one_year_later = date.replace(year=date.year + 1)
    fs = []
    results = []
    beginning = time.perf_counter()
    with ProcessPoolExecutor() as ex:
        while date < one_year_later:
            fs.append(
                ex.submit(
                    compute_positions_for_date, date,
                    latitude=latitude, longitude=longitude, elevation=elevation, tz=tz))
            date += datetime.timedelta(days=1)
        print(len(fs), "futures submitted.")
        for counter, future in enumerate(as_completed(fs), start=1):
            results.extend(future.result())
            print(f"{counter:3}. {len(results):,}")
    results.sort()
    SUN_POSITION.write_text(json.dumps(results))
    print(f"{SUN_POSITION!s}: {SUN_POSITION.stat().st_size:,} bytes.")
    print(f"Elapsed time {time.perf_counter() - beginning:.1f} seconds")


def _create_horizon_event_data():
    """Sunrise, sunset, and civil twilight times"""
    data = load_sun().data
    events = []
    for a, b in pairwise(data):
        # Check for sunrise and sunset
        if a[4] <= 0 < b[4]:
            name = 'Rise'
        elif a[4] > 0 >= b[4]:
            name = 'Set'
        else:
            name = None
        if name is not None:
            rec = b[:4] + [name, int(b[-1])]
            events.append(rec)

        # Check for dawn and dusk
        if a[4] <= TWILIGHT < b[4]:
            name = 'Dawn'
        elif a[4] > TWILIGHT >= b[4]:
            name = 'Dusk'
        else:
            name = None
        if name is not None:
            rec = b[:4] + [name, int(b[-1])]
            events.append(rec)
    events.sort()
    HORIZON_EVENTS.write_text(json.dumps(events))
    print(len(events), "horizon events")


def _build_my_sun_position_data():
    """Use my home location and time zone to build the minute-by-minute Sun data."""
    latitude, longitude, elevation = map(float, os.environ['HOME_LOCATION'].split(','))
    tz = pytz.timezone('US/Eastern')
    _create_sun_minute_by_minute(
        latitude=latitude, longitude=longitude,
        elevation=elevation, tz=tz)


def main():
    """Print the Sun and horizon event data for today."""
    print(load_sun().now())
    for ev in load_events().today():
        print(ev)


if __name__ == '__main__':
    # _build_my_sun_position_data()  # only needed once
    # _create_horizon_event_data()  # only needed once
    main()

