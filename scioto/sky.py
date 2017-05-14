from skyfield.api import Loader, Topos, Time
import numpy as np
from scipy.optimize import brentq
import pendulum as dt

from scioto import pairwise


LOADER_DIRECTORY = '~/nb/sky'
SPICE_KERNEL = 'de421.bsp'
RISE_SET = ('Rise', 'Set')
TWILIGHT = ('Dawn', 'Dusk')
HOUR = 1 / 24


# TODO add the Loader as an optional argument at the end. If it's None,
# then do the loading. OR: pass in planets and timescale (ts) and if
# either are None then have them loaded.
def generate_horizon_events(
        earth_location: tuple,
        body_name: str,  # TODO could also be a tuple of names?
        starting_time=None,
        days: int=1,
        kind: tuple=RISE_SET,
        altitude: int=0):

    # Load everything
    load = Loader(LOADER_DIRECTORY)
    planets = load(SPICE_KERNEL)
    earth = planets['earth']
    where = earth + Topos(*earth_location)
    body = planets[body_name]
    ts = load.timescale()

    # Times every hour for the requested days
    tt = ts.now().tt if starting_time is None else starting_time
    hours = 24 * days + 1
    jd = ts.tt(jd=np.linspace(tt, tt + days, hours))

    alt, *_ = where.at(jd).observe(body).apparent().altaz('standard')

    # Is the next event a rising or a setting.
    current_altitude = alt._degrees[0]
    which_kind = 1 if current_altitude > altitude else 0
    change_dates = jd.tt[np.ediff1d(np.sign(alt._degrees - altitude), to_end=0) != 0]
    args = (where, body, ts, 'alt', altitude)
    for date in change_dates:
        # t = ts.tt(jd=brentq(get_altitude, date, date + HOUR))
        t = ts.tt(jd=brentq(observe, date, date + HOUR, args=args))
        alt, az, _ = where.at(jd=t).observe(body).apparent().altaz('standard')
        yield (t, body_name, kind[which_kind], az)
        which_kind = 1 - which_kind


def observe(time, where, body, ts, field, offset):
    if not isinstance(time, Time):
        time = ts.tt(jd=time)
        alt, az, _ = where.at(time).observe(body).apparent().altaz('standard')
        value = alt if field == 'alt' else az
        return value._degrees - offset



def upcoming_rise_and_set_events():
    events = []
    where = ('40 N', '83 W')
    for name in ('sun', 'moon', 'venus', 'jupiter barycenter', 'mars', 'saturn barycenter', 'mercury'):
        for event in generate_horizon_events(where, name, days=1):
            events.append(event)
        if name == 'sun':
            for event in generate_horizon_events(where, name, days=1, kind=TWILIGHT, altitude=-6):
                events.append(event)
    for t, name, kind, az in sorted(events, key=lambda x: x[0].tt):
        t = dt.Pendulum.instance(t.utc_datetime()).in_tz('local')
        print(f"{name.split()[0].title():8} {kind:4} {az} {t:%H:%M %a %-d %b}")

upcoming_rise_and_set_events()


def calculate_azimuth_event(
        earth_location: tuple,
        body_name: str,
        azimuth: int,
        starting_time=None,
        days: int=1):

    # Load everything
    load = Loader(LOADER_DIRECTORY)
    planets = load(SPICE_KERNEL)
    earth = planets['earth']
    where = earth + Topos(*earth_location)
    body = planets[body_name]
    ts = load.timescale()

    calculated_altitude = None  # Storage for the altitude we wish to return

    def get_azimuth(time):
        # For use with brentq below.
        nonlocal calculated_altitude

        if not isinstance(time, Time):
            time = ts.tt(jd=time)
        calculated_altitude, az, _ = where.at(time).observe(body).apparent().altaz('standard')
        return az._degrees - azimuth

    tt = ts.now().tt if starting_time is None else starting_time
    jd = ts.tt(jd=np.linspace(tt, tt + 1.2, 25))  # TODO good enough?
    _, az, _ = where.at(jd).observe(body).apparent().altaz('standard')
    for a, b in pairwise(zip(az._degrees, jd.tt)):
        aza, azb = a[0], b[0]
        if aza > azb:
            azb += 360
        if aza <= azimuth <= azb:
            t = ts.tt(jd=brentq(get_azimuth, a[1], b[1]))
            return t, calculated_altitude
    raise ValueError(f"Can't find azimuth={azimuth}")


# where = ('40 N', '83 W')
# azimuth = 180
# for name in ('sun', 'moon', 'mercury', 'venus', 'mars'):
#     t, alt = calculate_azimuth_event(where, name, azimuth=azimuth)
#     t = dt.Pendulum.instance(t.utc_datetime()).in_tz('local')
#     print(f"{name.title():8} {t:%H:%M %a %-d %b} At {azimuth}: {alt}")
