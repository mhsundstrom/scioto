""" An updated version based on pendulum and my own preferences.
    Originally inspired by timesince from Django.

    Requires Python 3.6 or later. (eventually)
"""
import pendulum as dt

__all__ = ['timesince', 'timeuntil']

ATTRIBUTES = ['years', 'months', 'weeks', 'remaining_days',
              'hours', 'minutes', 'remaining_seconds']


def timesince(when, other=None, reversed=False):
    if other is None:
        other = dt.now()
    diff = when - other if reversed else other - when
    values = [getattr(diff, a) for a in ATTRIBUTES]
    pairs = [
        plurals(value, a)
        for value, a in zip(values, ATTRIBUTES)
        if value > 0
    ]
    # I want only the first two non-zero values,
    # and seconds only if the interval is less than one hour.
    if len(pairs) > 2:
        pairs = pairs[:2]
    if diff.total_hours() > 1 and pairs[-1][1].startswith('second'):
        pairs = pairs[:1]
    return ', '.join(f"{value} {a}" for value, a in pairs)


def timeuntil(when, other=None, reversed=True):
    return timesince(when, other, reversed)


def plurals(value, a):
    a = a.replace('remaining_', '')
    a = a[:-1] if value == 1 else a
    return (value, a)


if __name__ == '__main__':
    print(timesince(dt.parse('2017-08-21T13:25:32-05:00')))
