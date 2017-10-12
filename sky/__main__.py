import astropy.units as u

from . import Sky
from .api import Phase, Motions

MOON_MEAN_DISTANCE = 238_855
MOON_MINIMUM_PERIGEE = 221_504
MOON_MAXIMUM_APOGEE = 252_766
UNICODE_MOON_PHASES = 0x1f311

INT_TO_PHASE = {
    0: Phase.NewMoon,
    1: Phase.FirstQuarter,
    2: Phase.FullMoon,
    3: Phase.LastQuarter,
}

mph = u.imperial.mile / u.hour


def moon():
    """Summary of the current position of the Moon."""
    sky = Sky()
    now = sky.now()
    print(f"The Moon at {now.astimezone(sky.tz)}")

    moon_apparent = sky.home.at(now).observe(sky.moon).apparent()
    ra, dec, _ = moon_apparent.radec(epoch='date')
    print(f"R.A. {ra}, Declination {dec}")

    # Use the geocentric distance
    centered = sky.earth.at(now).observe(sky.moon)
    distance = centered.distance().to(u.imperial.mile)
    distance_percentage = (distance.value - MOON_MINIMUM_PERIGEE) / (MOON_MAXIMUM_APOGEE - MOON_MINIMUM_PERIGEE)
    speed = centered.speed().to(mph)
    print(f"{distance:,.0f}, [{distance_percentage:.2%}], {speed:,.0f}")

    alt, az, _ = moon_apparent.altaz('standard')
    if alt.degrees >= 0:
        print(f"Above the horizon: Altitude {alt} at Azimuth {az}")
    else:
        print("Below the horizon.")

    # Figure out the phases.
    sun_longitude = sky.earth.at(now).observe(sky.sun).ecliptic_latlon()[1]
    moon_longitude = sky.earth.at(now).observe(sky.moon).ecliptic_latlon()[1]
    phase = divmod(moon_longitude.degrees - sun_longitude.degrees, 360)[1]
    index = (int(phase + 22.5) // 45) % 8
    ch = chr(UNICODE_MOON_PHASES + index)
    print(f"Phase: {phase:3.0f}° {ch}")
    ip = ((int(phase) // 90) + 1) % 4
    next_phase = INT_TO_PHASE[ip]
    previous_phase = INT_TO_PHASE[(ip - 1) % 4]

    phase_date = sky.find_moon_phase(now.tt, Motions.Previous, previous_phase)
    print(f"{previous_phase:18} {phase_date.astimezone(sky.tz):%a %-d %b at %H:%M:%S %Z},")

    phase_date = sky.find_moon_phase(now.tt, Motions.Next, next_phase)
    print(f"{next_phase:18} {phase_date.astimezone(sky.tz):%a %-d %b at %H:%M:%S %Z}")














moon()


