"""
------------------------
Wrapper module
The module consists decorator functions that can be used by various modules in various scenarios.
------------------------
Coded by: Krishna Prasad K
© Jyothy Fabricare Services LTD.
------------------------
"""

from functools import wraps
from flask import request, jsonify
from dcr.generic.functions import json_input, generate_final_data, get_today
from dcr import db
from dcr.modules.models import DcrUserLogins


def json_wrapper(func):
    """
    Wrapping up the functions that deals with the JSON requests. If the JSON request is invalid, it
    instantly returned the fail response. If the json is valid, then proceed to the function and
    finally wraps the final_data dictionary in JSON format.
    :param func:
    :return: JSON object
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        json_request = json_input(request)
        if json_request.get('status') == 'failed':
            return jsonify(json_request)
        else:
            function = func(*args, **kwargs)
            return jsonify(function)

    return wrapper


def clock_in_filter(auth_user):
    """
    Decorator function for filtering the APIs based on the auth_user.
    Only clocked in users will be allowed to perform any task on a day.
    :param func:
    :return:
    @param auth_user: Authentication user. i.e. delivery_user
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = request.headers.get('user-id')
            # Based on the auth user, check if the user has clocked in or not.
            if auth_user == 'dcr':
                # Check if the delivery user is clocked in for the day or not.
                clock_in_details = db.session.query(DcrUserLogins).filter(
                    DcrUserLogins.RecordCreatedDate == get_today(),
                    DcrUserLogins.DUserId == user_id).one_or_none()
                if clock_in_details is not None:
                    # The delivery user has clocked in for today.
                    return func(*args, **kwargs)
                else:
                    # The delivery user has NOT clocked in for today.
                    return generate_final_data('NOT_CLOCKED_IN'), 200

            # elif auth_user == 'store_user':
            #     # Check if the store user has clocked in for the day or not.
            #     clock_in_details = db.session.query(StoreUserAttendance).filter(
            #         StoreUserAttendance.Date == get_today(),
            #         StoreUserAttendance.SUserId == user_id).one_or_none()
            #     if clock_in_details is not None:
            #         # The store user has clocked in for today.
            #         return func(*args, **kwargs)
            #     else:
            #         # The store user has NOT clocked in for today.
            #         return generate_final_data('NOT_CLOCKED_IN'), 200
            else:
                return generate_final_data('FAILED')

        return wrapper

    return decorator
