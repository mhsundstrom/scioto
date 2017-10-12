""" Read the contents of a special file.

    Typically used for passwords or API keys.
    Set the environment variable READ_SPECIAL to the directory
    where these are located.
"""
import os
from pathlib import Path


def read_special(filename):
    folder = Path(os.environ['READ_SPECIAL'])
    return (folder / filename).read_text().strip()
