""" Handles a simple ephemeris listing from JPL with RA and Dec
    expressed in decimal degrees.
"""
import datetime

import numpy as np
from skyfield.api import Angle, Star
from . import Sky


class Ephemeris:
    def __init__(self, ts, source_lines):
        self.ts = ts
        times_table = []
        self.ra_table, self.dec_table = [], []

        # We now expect the data to be in decimal degrees -- easier to parse.
        for line in source_lines:
            date_str, _, ra_str, dec_str = line.split('  ')
            date = datetime.datetime.strptime(date_str, '%Y-%b-%d %H:%M')
            t = self.ts.utc(date.year, date.month, date.day, date.hour, date.minute)
            ra = Angle(degrees=float(ra_str), preference='hours')
            dec = Angle(degrees=float(dec_str))

            times_table.append(t)
            self.ra_table.append(ra.hours)
            self.dec_table.append(dec.degrees)
        self.times = [t.tt for t in times_table]

    def interpolate(self, when=None):
        if when is None:
            when = self.ts.now()
        ra = np.interp(when.tt, self.times, self.ra_table)
        dec = np.interp(when.tt, self.times, self.dec_table)
        return Star(ra_hours=ra, dec_degrees=dec)

    def date_range(self):
        start, finish = self.times_table[0], self.times_table[-1]
        return start.astimezone(sky.tz), finish.astimezone(sky.tz)


if __name__ == '__main__':
    sky = Sky()
    eph = Ephemeris(sky.ts, sky.parser['2016 HO3']['ephemeris'].splitlines())
    body = eph.interpolate()
    alt, az, _ = sky.home.at(sky.now()).observe(body).apparent().altaz('standard')
    print(f"RA {body.ra}, Dec {body.dec}, Alt {alt.degrees:+4.0f}°, AZ {az.degrees:4.0f}°")
