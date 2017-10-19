from pathlib import Path
from configparser import ConfigParser
from itertools import chain
from collections import namedtuple
from operator import attrgetter
from math import pi
from enum import Enum

from skyfield.api import Loader, Topos, Time, Star, Angle
import tzlocal
import astropy.units as u
import numpy as np
from scipy.optimize import brentq


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

    mph = u.imperial.mile / u.hour  # Often-used definition

    def __init__(self, latitude=None, longitude=None, elevation=None):
        # TODO: handle the latlon info
        self.parser = ConfigParser(
            allow_no_value=True,
            converters={'star': load_star}
        )
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
        # Load our stars and asterisms of interest
        self.stars = {}
        for name, value in self.parser['stars'].items():
            if value is None:
                continue
            self.stars[name.title()] = load_star(value)
        self.asterisms = {
            name.title(): load_star(value)
            for name, value in self.parser['asterisms'].items()
        }

    def __repr__(self):
        return str(self.home.positives[-1])

    def _repr_html_(self):
        return f"<h5>Sky at {self!r}</h5>"

    def local_sidereal_time(self, when=None):
        """Calculate the Local Sidereal Time"""
        # TODO: Not sure if `positives[-1]` is safe/reliable for recovering latlon.
        if when is None:
            when = self.now()
        return Angle(hours=(when.gmst + self.home.positives[-1].longitude._hours) % 24)

    def lst_str(self, when=None):
        """Local Sidereal Time as a nicely formatted string"""
        # TODO: The superscripts don't look great in a Jupyter notebook.
        lst = self.local_sidereal_time(when)
        sign, hh, mm, ss = lst.signed_hms()
        return f"{hh:.0f}ʰ{mm:.0f}ᵐ{ss:.0f}ˢ"

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

    def generate_horizon_events(self, name_or_body, tt=None, days: int = 1, altitude: int = 0):
        """
        Generates rise and set events (or twilight, using a non-zero altitude)
        """
        if tt is None:
            tt = self.now().tt

        hours = 24 * days + 1  # Space our positions every hour
        jd = self.ts.tt(jd=np.linspace(tt, tt + days, hours))

        if isinstance(name_or_body, str):
            body = self.planets[name_or_body]
        else:
            body = name_or_body
        alt, *_ = self.home.at(jd).observe(body).apparent().altaz('standard')

        # Is the next event a rising or a setting.
        current_altitude = alt._degrees[0]
        which_kind = 1 if current_altitude > altitude else 0
        change_dates = jd.tt[np.ediff1d(np.sign(alt._degrees - altitude), to_end=0) != 0]
        args = (body, 'alt', altitude)

        for date in change_dates:
            t = self.ts.tt(jd=brentq(self.get_alt_or_az, date, date + hour, args=args))
            alt, az, _ = self.home.at(jd=t).observe(body).apparent().altaz('standard')
            yield (t, which_kind, az)
            which_kind = 1 - which_kind

    def get_alt_or_az(self, time, body, field, offset):
        """Called by `brentq` as it iterates to a solution"""
        if not isinstance(time, Time):
            time = self.ts.tt(jd=time)
        alt, az, _ = self.home.at(time).observe(body).apparent().altaz('standard')
        value = alt if field == 'alt' else az
        return value._degrees - offset


def load_star(value):
    ra_str, dec_str = value.split(',', 1)
    h, m, s = map(float, ra_str.split(':'))
    ra = h + m / 60 + s / 3600
    d, m, s = map(float, dec_str.split(':'))
    dec = d + m / 60 + s / 3600
    return Star(ra_hours=ra, dec_degrees=dec)


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


def moon_phase_and_season_example():
    sky = Sky()
    fmt = '%a, %d %b %Y at %H:%M %Z'
    print("Phases of the Moon")
    for event in sorted(calc_all_moon_phases(sky), key=attrgetter('tt.tt')):
        print(f"{event.which:18} {event.tt.astimezone(sky.tz):{fmt}}")
    print(20 * "-")
    print("Seasons")
    for event in sorted(calc_all_seasons(sky), key=attrgetter('tt.tt')):
        print(f"{event.which:18} {event.tt.astimezone(sky.tz):{fmt}}")


if __name__ == '__main__':
    sky = Sky()
    print("Sky:", sky)
    print(f"Local Sidereal Time: {sky.lst_str()}")
    # moon_phase_and_season_example()

    # sky = Sky()
    # RISE_SET = ('Rise', 'Set')
    # for t, kind, az in sky.generate_horizon_events('sun', days=7):
    #     time = t.astimezone(sky.tz)
    #     print(f"{RISE_SET[kind]:4} {time:%d %a %b %H:%M %Z} {az.degrees:3.0f}°")
