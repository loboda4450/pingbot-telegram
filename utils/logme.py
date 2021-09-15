import functools
import logging


def logme(f):
    @functools.wraps(f)
    def newf(*args, **kwargs):
        logging.debug(f"function call: {f.__name__}(*args={args}, **kwargs={kwargs})")
        return f(*args, **kwargs)

    return newf