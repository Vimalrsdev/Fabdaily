"""
------------------------
Auth Guard module
Authentication module for the project.
------------------------
Coded by: Athira K
© Jyothy Fabricare Services LTD.
------------------------
"""

from datetime import datetime
from flask import request, current_app
from functools import wraps
from dcr.generic.functions import generate_final_data, get_current_date
from dcr import db
from dcr.modules.models import DcrUserLogins
import jwt
from dcr.settings.project_settings import ACCESSIBLE_FILE_TYPES
from dcr.generic.error_handlers import error_logger
import inspect


def api_key_required(func):
    """
    A wrapper function that deals with the checking of Api-Key token in the request header.
    :param func:
    :return:
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        api_key = request.headers.get('api-key')
        if api_key == current_app.config["API_KEY"]:
            valid = True
        else:
            valid = False
        if valid:
            return func(*args, **kwargs)
        else:
            return generate_final_data('INVALID_API_KEY')

    return wrapper


def asset_auth(func):
    """
    A wrapper function for auth guarding to the asset controller APIs.
    :param func:
    :return:
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        file_type = kwargs['file_type']
        # ACCESSIBLE_FILE_TYPES are the list of type of files that can be accessed without
        # a valid API key/Access key.
        if file_type in ACCESSIBLE_FILE_TYPES:
            # the file type is accessible without a key. So no need for further checks.
            return func(*args, **kwargs)
        else:
            # The file type is not present in the accessible file types list.
            # So further checks are needed.
            api_key = request.headers.get('api-key')
            if api_key == current_app.config["API_KEY"]:
                valid = True
            else:
                valid = False
            if valid:
                return func(*args, **kwargs)
            else:
                return generate_final_data('INVALID_API_KEY')

    return wrapper


def authenticate(auth_user):
    """
    Fabric authentication system. Api-Key and Access-Key is needed to authenticate.
    Access-Key is user specific, can be gained by invoking the login.
    :param func:
    :return:
    @param auth_user: Authentication user. i.e. delivery_user, store_user, customer
    """

    def auth_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            api_key = request.headers.get('api-key')
            access_key = request.headers.get('access-key')
            if api_key:
                if api_key != current_app.config['API_KEY']:
                    return generate_final_data('INVALID_API_KEY'), 401
                else:
                    # Reading the access key of a auth_user
                    access_key_check = validate_access_key(auth_user, access_key)
                    if access_key_check:
                        return func(*args, **kwargs)
                    else:
                        return generate_final_data('INVALID_ACCESS_KEY'), 401
            else:
                return generate_final_data('API_KEY_NOT_FOUND'), 401

        return wrapper

    return auth_decorator


def validate_access_key(auth_user, key):
    """
    Validating the user-specific Access-Key from the header.
    If the Access-Key is invalid, return False.
    @param key: Access Key Token of the user
    @param auth_user: Authentication type. i.e. delivery_user, store_user, customer
    @return: True if the token is valid, else False.
    """

    user_id = request.headers.get('user-id')
    is_valid = False
    if user_id is not None:
        try:
            jwt.decode(key, current_app.config['JWT_SECRET_KEY'] + str(user_id),
                       algorithms=['HS256'])

            # Decoded successfully. Now check if the auth token is expired or not.
            if auth_user == 'dcr' or auth_user == 'audit':
                # Dcr user authentication.
                try:
                    login_data = db.session.query(DcrUserLogins).filter(
                        DcrUserLogins.DUserId == user_id, DcrUserLogins.AuthKey == key,
                        DcrUserLogins.AuthKeyExpiry == 0).one_or_none()
                    is_valid = grant_or_deny(login_data)

                except Exception as e:
                    # Database exception
                    error_logger(f'Auth Guard: {inspect.stack()[0].function}()').error(e)

            # elif auth_user == 'store_user':
            #     # Store admin user authentication.
            #     try:
            #         login_data = db.session.query(StoreUserLogin).filter(
            #             StoreUserLogin.SUserId == user_id, StoreUserLogin.AuthKey == key,
            #             StoreUserLogin.AuthKeyExpiry == 0).one_or_none()
            #         is_valid = grant_or_deny(login_data)
            #     except Exception as e:
            #         error_logger(f'Auth Guard: {inspect.stack()[0].function}()').error(e)

            else:
                pass
        except Exception as e:
            # Decode exception
            error_logger(f'Auth Guard: {inspect.stack()[0].function}()').error(e)

    return is_valid


def grant_or_deny(login_data):
    """
    Granting/Denying the access by checking the access token. If the token is older than 2 weeks, deny. Else grant.
    @param login_data: Login data row.
    @return: True if the access is granted. Else return False.
    """
    is_granted = False
    if login_data is not None:
        # Check if the LastAccessTime is older than 2 weeks or not. If the token is older than 2 weeks,
        # make token expire.
        difference = datetime.now() - login_data.LastAccessTime
        difference_in_days = difference.days
        # Store user's token lasts 2 weeks. Delivery user's token
        # expires after a day.
        # if type(login_data) == StoreUserLogin:
        #     if difference_in_days >= 14:
        #         # LastAccessTime is older than 2 weeks. So make the token expire explicitly
        #         login_data.AuthKeyExpiry = 1
        #         login_data.IsActive = 0
        #         db.session.commit()
        #     else:
        #         # LastAccessTime happened within 2 weeks. So it is a valid token. Update the LastAccessTime
        #         login_data.LastAccessTime = get_current_date()
        #         db.session.commit()
        #         is_granted = True
        if type(login_data) == DcrUserLogins:
            if difference_in_days >= 1:
                # LastAccessTime is older than 1 day. So make the token expire explicitly
                login_data.AuthKeyExpiry = 1
                login_data.IsActive = 0
                db.session.commit()
            else:
                # LastAccessTime happened within 1 day. So it is a valid token. Update the LastAccessTime
                login_data.LastAccessTime = get_current_date()
                db.session.commit()
                is_granted = True
        else:
            pass
        return is_granted
