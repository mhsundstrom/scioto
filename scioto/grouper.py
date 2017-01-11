from itertools import zip_longest


def grouper(n, iterable, fillvalue=None):
    "Collect data into fixed-length blocks"
    # grouper(3, '1234567', 'x') --> 123 456 7xx
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)
