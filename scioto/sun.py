""" The Sun's position does not change annually in any appreciable way, so
    it's convenient to spend the time to calculate a set of positions
    once and then reuse them for many different purposes.

    Here we will calculate the Sun's position for every minute throughout
    the year and save it as a pickled file for later use.
"""
import os
import datetime
import pickle
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from bisect import bisect_right
from collections import UserList

from skyfield.api import Loader, Topos
import pytz
from scioto import pairwise


HERE = Path(__file__).parent
SUN_PICKLE = HERE / 'Sun-Minute-by-Minute.pickle'
HORIZON_EVENTS = HERE / 'Horizon-Events.pickle'
TWILIGHT = -6

loader = Loader(os.environ['SKYFIELD_LOADER_DIRECTORY'])
planets = loader(os.getenv('SKYFIELD_SPICE_KERNEL', 'de421.bsp'))
ts = loader.timescale()
latitude, longitude, elevation = map(float, os.environ['HOME_LOCATION'].split(','))
tz = pytz.timezone('US/Eastern')  # TODO generalize this a bit
where = planets['earth'] + Topos(latitude_degrees=latitude,
                                 longitude_degrees=longitude,
                                 elevation_m=elevation)


# TODO Add a call for a specific day that returns rise, set, day length, both azimuths
# TODO a call that builds a calendar of rise/set for a month or a year, text or html,
# TODO generate the pickle files somewhere else?

__all__ = ['load_sun', 'load_events']


@lru_cache(maxsize=1)
def load_sun():
    assert SUN_PICKLE.exists(), f"You must create {SUN_PICKLE.name} first!"
    return Sun(pickle.loads(SUN_PICKLE.read_bytes()))


@lru_cache(maxsize=1)
def load_events():
    assert HORIZON_EVENTS.exists(), f"You must create {HORIZON_EVENTS.name} first!"
    return Events(pickle.loads(HORIZON_EVENTS.read_bytes()))


class Position:
    def __init__(self, value, year=None):
        if year is None:
            year = datetime.date.today().year
        self.date = datetime.datetime(year, *value[:4])
        self.alt = value[4]
        self.az = value[5]

    def __repr__(self):
        return "{0.date:%a %d %b %H:%M} Alt={0.alt:.0f}° Az={0.az:.0f}°".format(self)

    def _repr_html_(self):
        """Having fun with display in the Jupyter Notebook"""
        if self.alt > 0:
            tag, front, behind = 'b', chr(0x1f31e), ''  # yellow sun, bold text
        else:
            tag, front, behind = 'em', '', chr(0x2600)  # black sun, italic text
        return f"️{front}<{tag}>{self!r}</{tag}>{behind}"


class Sun(UserList):
    """
    Wraps the list of sun positions with a handy class
    """
    def __str__(self):
        return "Minute-by-minute positions of the Sun for an entire year."

    def __getitem__(self, index):
        """Wraps a sun position in a more friendly class than the original tuple"""
        return Position(self.data[index])

    def at(self, *args):
        index = bisect_right(self.data, tuple(args))
        if index:
            return self[index-1]
        raise ValueError

    def now(self):
        date = datetime.datetime.now()
        return self.at(date.month, date.day, date.hour, date.minute)


class Events(UserList):
    def __repr__(self):
        return f"{len(self):,} events"

    def at(self, date):
        if isinstance(date, tuple):
            year = datetime.date.today().year
            date = datetime.date(year, *date)
        key = (date.month, date.day)
        index = bisect_right(self.data, key)
        return [
            Event(value, date.year)
            for value in self[index:]
            if value[:2] == key
        ]

    def today(self):
        date = datetime.date.today()
        key = (date.month, date.day)
        index = bisect_right(self.data, key)
        return [
            Event(value, date.year)
            for value in self[index:]
            if value[:2] == key
        ]


class Event:
    def __init__(self, value, year):
        self.date = datetime.datetime(year, *value[:4])
        self.name = value[4]
        self.az = value[5]

    def __repr__(self):
        return "{0.date:%a %d %b %H:%M} {0.name} {0.az}°".format(self)


def position(jd, alt, az):
    """Returns a convenient tuple for the calculated Sun position."""
    date = jd.astimezone(tz=tz)
    return date.month, date.day, date.hour, date.minute, round(alt, 2), round(az, 2)


def compute_positions_for_date(date):
    """Calculate the position of the Sun for every minute of the specified date."""
    every_minute = ts.utc(date.year, date.month, date.day, 0, range(1440))
    alt, az, _ = where.at(every_minute).observe(planets['sun']).apparent().altaz()
    return [
        position(jd, alt, az)
        for jd, alt, az in zip(every_minute, alt.degrees, az.degrees)
    ]


def generate_one_year(path):
    """
    Compute Sun locations for every minute over an entire year.
    Use `concurrent.futures` to calculate these days in parallel;
    it speeds up the process a fair amount.

    We calculate for a leap year so that the resulting table is
    useful for any year.
    """
    date = datetime.date(2016, 1, 1)
    one_year_later = date.replace(year=date.year + 1)
    fs = []
    results = []
    with ProcessPoolExecutor() as ex:
        while date < one_year_later:
            fs.append(ex.submit(compute_positions_for_date, date))
            date += datetime.timedelta(days=1)
        print(len(fs), "futures submitted.")
        for counter, future in enumerate(as_completed(fs), start=1):
            results.extend(future.result())
            print(f"{counter:3}. {len(results):,}")
    results.sort()
    path.write_bytes(pickle.dumps(results, pickle.HIGHEST_PROTOCOL))


def create_minute_by_minute():
    """Only need to do this once. This file is about 25.8 MB"""
    SUN_PICKLE.parent.mkdir(exist_ok=True, parents=True)
    generate_one_year(SUN_PICKLE)
    print(f"{SUN_PICKLE!s}: {SUN_PICKLE.stat().st_size:,} bytes.")


def create_horizon_events():
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
            rec = b[:4] + (name, int(b[-1]))
            events.append(rec)

        # Check for dawn and dusk
        if a[4] <= TWILIGHT < b[4]:
            name = 'Dawn'
        elif a[4] > TWILIGHT >= b[4]:
            name = 'Dusk'
        else:
            name = None
        if name is not None:
            rec = b[:4] + (name, int(b[-1]))
            events.append(rec)
    events.sort()
    HORIZON_EVENTS.write_bytes(pickle.dumps(events, pickle.HIGHEST_PROTOCOL))
    print(len(events), "horizon events")


if __name__ == '__main__':
    # create_minute_by_minute
    # create_horizon_events()

    events = load_events()
    for ev in events.today():
        print(ev)
