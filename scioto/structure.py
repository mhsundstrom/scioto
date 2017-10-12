""" From the "Python Cookbook", 3rd edition,
        by David Beazley and & Brian K. Jones

    Recipe 8.11: Simplifying the Initialization of Data Structures
    Page 270

    This simplifies the writing of __init__ methods that
    are just copying arguments into attributes.
"""


class Structure:
    """ Structure has a list of expected arguments, in
        _fields. These can be positional or keyword arguments.
    """
    _fields = []

    def __init__(self, *args, **kwargs):
        if len(args) > len(self._fields):
            raise TypeError(f'Expected {len(self._fields)} arguments')

        # Set the positional arguments
        for name, value in zip(self._fields, args):
            setattr(self, name, value)

        # Set the remaining keyword arguments.
        for name in self._fields[len(args):]:
            setattr(self, name, kwargs.pop(name))

        # Anything left over is an error.
        if kwargs:
            raise TypeError('Invalid argument(s): {}'.format(','.join(kwargs)))
