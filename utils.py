import sys
import logging


def init_log():
    lg = logging.getLogger('default')
    lg.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    lg.addHandler(handler)
    return lg


logger = init_log()


def log(string):
    logger.debug(string)


def err(string):
    logger.error(string)
