from skyfield.api import Loader, Topos, Time
import numpy as np
from scipy.optimize import brentq
import pendulum as dt

LOADER_DIRECTORY = '~/nb/sky'
SPICE_KERNEL = 'de421.bsp'
RISE_SET = ('Rise', 'Set')
TWILIGHT = ('Dawn', 'Dusk')
HOUR = 1 / 24


def generate_horizon_events(
        earth_location: tuple,
        body_name: str,
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

    calculated_azimuth = None  # Storage for the azimuth we wish to return

    def get_altitude(time):
        # For use with brentq below.
        nonlocal calculated_azimuth  # Save the azimuth in the outer level.

        if not isinstance(time, Time):
            time = ts.tt(jd=time)
        alt, calculated_azimuth, _ = where.at(time).observe(body).apparent().altaz('standard')
        return alt._degrees - altitude

    alt, *_ = where.at(jd).observe(body).apparent().altaz('standard')

    # Is the next event a rising or a setting.
    current_altitude = alt._degrees[0]
    which_kind = 1 if current_altitude > altitude else 0
    change_dates = jd.tt[np.ediff1d(np.sign(alt._degrees - altitude), to_end=0) != 0]
    for date in change_dates:
        t = ts.tt(jd=brentq(get_altitude, date, date + HOUR))
        yield (t, body_name, kind[which_kind], calculated_azimuth)
        which_kind = 1 - which_kind


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

# upcoming_rise_and_set_events()

