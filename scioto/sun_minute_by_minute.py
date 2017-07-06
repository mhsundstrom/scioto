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
from functools import lru_cache, singledispatch
from bisect import bisect_right

from skyfield.api import Loader, Topos
import pytz


HERE = Path(__file__).parent
SUN_PICKLE = HERE / 'Sun-Minute-by-Minute.pickle'

loader = Loader(os.environ['SKYFIELD_LOADER_DIRECTORY'])
planets = loader(os.getenv('SKYFIELD_SPICE_KERNEL', 'de421.bsp'))
ts = loader.timescale()
latitude, longitude, elevation = map(float, os.environ['HOME_LOCATION'].split(','))
tz = pytz.timezone('US/Eastern')  # TODO generalize this a bit
where = planets['earth'] + Topos(latitude_degrees=latitude,
                                 longitude_degrees=longitude,
                                 elevation_m=elevation)


@lru_cache(maxsize=1)
def load_sun_positions():
    assert SUN_PICKLE.exists(), f"You must create {SUN_PICKLE.name} first!"
    return pickle.loads(SUN_PICKLE.read_bytes())


class SunPosition:
    def __init__(self, value):
        today = datetime.date.today()
        self.date = datetime.datetime(today.year, *value[:4])
        self.alt = value[4]
        self.az = value[5]

    def __repr__(self):
        return "{0.date:%a %d %b %H:%M} Alt={0.alt:.0f}° Az={0.az:.0f}°".format(self)

    def _repr_html_(self):
        return f"☀️<b>{self!r}</b>"


@singledispatch
def get_sun_position(arg: tuple):
    sun_positions = load_sun_positions()
    index, value = search(sun_positions, arg)
    return SunPosition(value)


@get_sun_position.register(datetime.datetime)
def get_sun_from_datetime(date):
    return get_sun_position((date.month, date.day, date.hour, date.minute))


@get_sun_position.register(datetime.date)
def get_sun_from_date(date):
    return get_sun_position((date.month, date.day, 0, 0))


def search(a, x):
    """Find rightmost value less than or equal to x"""
    i = bisect_right(a, x)
    if i:
        return i-1, a[i-1]
    raise ValueError


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


if __name__ == '__main__':
    SUN_PICKLE.parent.mkdir(exist_ok=True, parents=True)
    generate_one_year(SUN_PICKLE)
    print(f"{SUN_PICKLE!s}: {SUN_PICKLE.stat().st_size:,} bytes.")
