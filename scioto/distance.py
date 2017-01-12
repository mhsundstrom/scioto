from functools import total_ordering

# Conversion factors from 1 kilometer.
ONE_MILE = 1.609344
ONE_NM = 1.852
ONE_FOOT = ONE_MILE / 5280
RADIUS = 6366.71


@total_ordering
class Distance:
    """ The primary distance is kilometers (km), but it can
        also be entered or expressed in miles, nautical miles,
        or radians.

        This is similar to the Angle class that can be found in Skyfield.
    """
    def __init__(self, km=None, meters=None, miles=None, nm=None, feet=None, radians=None):
        if km is not None:
            self.km = km
        elif meters is not None:
            self.meters = meters
            self.km = meters / 1000
        elif miles is not None:
            self.miles = miles
            self.km = miles * ONE_MILE
        elif nm is not None:
            self.nm = nm
            self.km = nm * ONE_NM
        elif feet is not None:
            self.feet = feet
            self.km = feet * ONE_FOOT
        elif radians is not None:
            self.radians = radians
            self.km = RADIUS * radians
        else:
            raise ValueError("Enter km, meters, miles, nm, feet, or radians.")

    def __getattr__(self, name):
        if name in ('meters', 'm'):
            self.meters = meters = self.km * 1000
            return meters
        if name == 'miles':
            self.miles = miles = self.km / ONE_MILE
            return miles
        if name == 'nm':
            self.nm = nm = self.km / ONE_NM
            return nm
        if name == 'feet':
            self.feet = feet = self.km / ONE_FOOT
            return feet
        if name == 'radians':
            self.radians = radians = self.km / RADIUS
            return radians
        raise AttributeError(f"No attribute named {name!r}")

    def __str__(self):
        return f'{self.km:.0f}'

    def __repr__(self):
        return f'<{type(self).__name__} {self}>'

    def __eq__(self, other):
        return self.km == other.km

    def __lt__(self, other):
        return self.km < other.km


if __name__ == '__main__':
    print(Distance(feet=5281) > Distance(miles=1))
    print(Distance(km=1) < Distance(miles=1))
