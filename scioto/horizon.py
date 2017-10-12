from math import sqrt
from functools import singledispatch

from .distance import Distance
from .constants import EARTH_EQUATORIAL_RADIUS_KM

RADIUS = Distance(km=EARTH_EQUATORIAL_RADIUS_KM)


@singledispatch
def distance_to_horizon(height):
    """ At a height h above the ground, the distance to the horizon d, is given by:
            d = sqrt(2*R*h/b)

        b=0.8279 is a factor that accounts for atmospheric refraction
        and depends on the atmospheric temperature lapse rate, which is
        taken to be standard. R is the radius of the earth.
        Note that the earth is assumed smooth- likely only true over the oceans!

        For h in feet and d in nm:
            d =1.17*sqrt(h)
            i.e. from 10000 feet, the horizon is 117nm away

        (Reference Bowditch American Practical Navigator (1995) Table 12.)

        From:
            `Aviation Formulary V 1.46 <http://williams.best.vwh.net/avform.htm>`_
    """
    return Distance(feet=sqrt(2 * RADIUS.feet * height.feet / 0.8279))


@distance_to_horizon.register(int)
@distance_to_horizon.register(float)
def int_or_float_distance(height):
    return distance_to_horizon(Distance(feet=height))


if __name__ == '__main__':
    height = Distance(feet=4583)  # Height of Mont Pelée on the island of Martinique
    print(f"From Mont Pelée on Martinique, the distance to "
          f"the horizon is {distance_to_horizon(height).nm:.2f} nautical miles")
