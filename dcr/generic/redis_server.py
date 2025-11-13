"""
------------------------
Redis server module
The module consists functions related to Redis server can be used by various modules in various scenarios.
------------------------
Coded by: Krishna Prasad K
© Jyothy Fabricare Services LTD.
------------------------
"""

import redis
import json
from dcr.settings.project_settings import REDIS_SERVER_HOST, REDIS_SERVER_PORT
from .loggers import error_logger

# redis server instance
r = redis.Redis(host=REDIS_SERVER_HOST, port=REDIS_SERVER_PORT, db=0)

error_logger = error_logger()


def get_redis(key):
    """
    Function to get the key value from the redis server
    @param key: key that needs to be fetched from the redis server
    @return: value of the key. None if no corresponding key value is present in the server.
    """
    try:
        value = r.get(key)
        return value
    except Exception as e:
        error_logger.error(e)
        return None


def set_redis(key, value):
    """
    Function to set the key and its value into redis server
    @param key:
    @param value:
    @return: True if the operation is successful or False if the operation is failed.
    """
    try:
        r.set(key, value)
        return True
    except Exception as e:
        error_logger.error(e)
        return False
