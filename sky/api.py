from pathlib import Path
from configparser import ConfigParser
from itertools import chain
from collections import namedtuple
from operator import attrgetter
from math import pi
from enum import Enum

from skyfield.api import Loader, Topos, Time
import tzlocal
import astropy.units as u


SKYFIELD_CONFIG = Path.home() / 'skyfield-config.ini'
HOME_LOCATION = Path.home() / 'Location.txt'

twopi = pi * 2
halfpi = pi / 2
quarterpi = pi / 4
eighthpi = pi / 8
degree = pi / 180
arcminute = degree / 60
arcsecond = arcminute / 60
half_arcsecond = arcsecond / 2
tiny = arcsecond / 360

hour = 1 / 24
minute = hour / 60
second = minute / 60

default_newton_precision = second / 10


class Motions(Enum):
    Previous = -twopi
    Next = twopi


class Phase(Enum):
    NewMoon = 0
    FirstQuarter = halfpi
    FullMoon = pi
    LastQuarter = pi + halfpi


class Season(Enum):
    Spring = 0
    Winter = halfpi
    Fall = pi
    Summer = pi + halfpi


MotionEvent = namedtuple('MotionEvent', 'motion which tt')


def get_home_location(sky):
    # TODO we should check env $HOME_LOCATION if this fails.
    location_parser = ConfigParser()
    with HOME_LOCATION.open() as lines:
        lines = chain(("[location]",), lines)
        location_parser.read_file(lines)

    return sky.planets['earth'] + Topos(
        latitude_degrees=location_parser.getfloat('location', 'latitude'),
        longitude_degrees=location_parser.getfloat('location', 'longitude'),
        elevation_m=location_parser.getfloat('location', 'altitude (m)'))


class Sky:
    """
    `Sky` is a class containing all the useful items we typically
    use with `python-skyfield`. This includes:
    - planets
    - ts (timescale)
    - tz (current timezone)
    - home (home location)

    It also includes some useful methods, e.g. Phase of the Moon, and Seasons.

    """
    def __init__(self):
        self.parser = ConfigParser(allow_no_value=True)
        self.parser.read(SKYFIELD_CONFIG)
        self.loader = Loader(self.parser.get('skyfield', 'loader_directory'))
        self.planets = self.loader(self.parser.get('skyfield', 'spice_kernel'))
        self.ts = self.loader.timescale()
        self.now = self.ts.now
        self.tz = tzlocal.get_localzone()
        self.home = get_home_location(self)
        # These are often used, give them a special place.
        self.earth = self.planets['earth']
        self.sun = self.planets['sun']
        self.moon = self.planets['moon']

    def find_moon_phase(self, tt, motion, target):
        """
        Find the next or previous specified phase of the Moon.

        Derived from the same function in pyephem.
        """
        def f(tt):
            slon = self.earth.at(self.ts.tt(jd=tt)).observe(self.sun).ecliptic_latlon()[1]
            mlon = self.earth.at(self.ts.tt(jd=tt)).observe(self.moon).ecliptic_latlon()[1]
            return (mlon.radians - slon.radians - antitarget) % twopi - pi

        antitarget = target.value + pi
        f0 = f(tt)
        angle_to_cover = -f0 % motion.value
        if abs(angle_to_cover) < tiny:
            angle_to_cover = motion.value
        d = tt + 29.53 * angle_to_cover / twopi
        return self.ts.tt(jd=newton(f, d, d + hour))

    def season(self, t, motion, offset):
        """ Calculate a solstice or equinox.
            Derived from the same function in pyephem
        """
        def f(jd):
            ra, _, _ = self.earth.at(self.ts.tt(jd=jd)).observe(self.sun).radec(epoch='date')
            return (ra.radians + eighthpi) % quarterpi - eighthpi

        ra, _, _ = self.earth.at(t).observe(self.sun).radec(epoch='date')
        angle_to_cover = motion - (ra.radians + offset) % motion
        if abs(angle_to_cover) < tiny:
            angle_to_cover = motion
        d = t.tt + 365.25 * angle_to_cover / twopi
        return self.ts.tt(jd=newton(f, d, d + hour))


def newton(f, x0, x1, precision=default_newton_precision):
    """
    Newton's method. Derived from the same function in `pyephem`.

    Return an x-value at which the given function reaches zero.

    Declares victory and returns once the x-value is within ``precision``
    of the solution, which defaults to a half-second of clock time.
    """
    f0, f1 = f(x0), f(x1)
    while f1 and abs(x1 - x0) > precision and f1 != f0:
        x0, x1 = x1, x1 + (x1 - x0) / (f0/f1 - 1)
        f0, f1 = f1, f(x1)
    return x1


def calc_all_moon_phases(sky):
    """ Generate each of the previous and next moon phases from the specified time.
    """
    tt = sky.now().tt
    for motion in Motions:
        for phase in Phase:
            yield MotionEvent(motion, phase, sky.find_moon_phase(tt, motion, phase))


def calc_all_seasons(sky):
    """ Calculates the next and previous solstices and equinoxes for the given time."""
    when = sky.now()
    for motion in Motions:
        for which in Season:
            yield MotionEvent(motion, which, sky.season(when, motion.value, which.value))


if __name__ == '__main__':
    sky = Sky()
    fmt = '%a, %d %b %Y at %H:%M %Z'
    print("Phases of the Moon")
    for event in sorted(calc_all_moon_phases(sky), key=attrgetter('tt.tt')):
        print(f"{event.which:18} {event.tt.astimezone(sky.tz):{fmt}}")
    print(20 * "-")
    print("Seasons")
    for event in sorted(calc_all_seasons(sky), key=attrgetter('tt.tt')):
        print(f"{event.which:18} {event.tt.astimezone(sky.tz):{fmt}}")
