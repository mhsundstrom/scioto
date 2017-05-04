""" Calculate the `Great Circle <https://en.wikipedia.org/wiki/Great_circle>`_
    distance between two points. This uses the higher accuracy version
    from Jean Meeus, Astronomical Algorithms, Chapter 11, page 85.

    I have used some Greek characters here, in part
    to more closely match the formulas in the book
    and also because I can.
"""
from math import radians, cos, sin, sqrt, atan

from .constants import EARTH_EQUATORIAL_RADIUS_KM
from .distance import Distance


def great_circle(lat1, lon1, lat2, lon2):
    α = EARTH_EQUATORIAL_RADIUS_KM
    𝑓 = 1 / 298.257  # Flattening of the Earth.
    φ1, L1, φ2, L2 = map(radians, (lat1, lon1, lat2, lon2))
    F = (φ1 + φ2) / 2
    G = (φ1 - φ2) / 2
    L = (L1 - L2) / 2
    cosL = cos(L)
    sinG = sin(G)
    cosF = cos(F)
    sinL = sin(L)
    cosG = cos(G)
    sinF = sin(F)
    S = sinG * sinG * cosL * cosL + cosF * cosF * sinL * sinL
    C = cosG * cosG * cosL * cosL + sinF * sinF * sinL * sinL
    tanω = sqrt(S / C)
    ω = atan(tanω)
    try:
        R = sqrt(S * C) / ω
    except ZeroDivisionError:
        return 0
    D = 2 * ω * α
    H1 = (3 * R - 1) / (2 * C)
    H2 = (3 * R + 1) / (2 * S)
    return Distance(km=D * (
        1 + 𝑓 * H1 * sinF * sinF * cosG * cosG -
        𝑓 * H2 * cosF * cosF * sinG * sinG))


