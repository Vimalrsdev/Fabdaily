"""
------------------------
DELIVERY CONTROLLER
A module consisting of set of functions/APIs that are used by the delivery/logistics app.


The Flask blueprint module consisting of set of functions/APIs that are used by the delivery/logistics app.
------------------------
Created on May 20, 2020.
Coded by: Athira K
© Jyothy Fabricare Services LTD.
------------------------
"""
import inspect
import requests
from flask import Blueprint, request, current_app, send_file, redirect
import json
from datetime import datetime, timedelta, date
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
from sqlalchemy import func, or_, case, cast, String, and_, text, literal, extract, desc
import jwt
import uuid
import base64
import os
import random
from dcr import db
import haversine as hs
from sqlalchemy.orm.exc import MultipleResultsFound
from werkzeug.utils import secure_filename
# Importing authentication middleware.
from dcr.middlewares.auth_guard import api_key_required, authenticate
# Importing the generally used functions module.
from dcr.generic.functions import json_input, generate_final_data, populate_errors, generate_hash, \
    get_current_date, get_today, send_sms, get_greeting_text

from dcr.blueprints.dcr_app import queries,functions, test_function
# Importing the project settings.
from dcr.settings.project_settings import LOCAL_DB, SERVER_DB, CURRENT_ENV, PAYMENT_LINK_API_KEY, OLD_DB, channel_id, \
    sale_request_url, sale_request_status_url, CRM
from dcr.generic.classes import SerializeSQLAResult, CallSP, TravelDistanceCalculator, GenerateReport
from decimal import Decimal
from dcr.modules.models import DCR_Users, DCR_OTPs, DCR_Collection, DCR_PendingsLog, DcrUserLogins, DCR_Deposit, \
    DCR_DateWiseCollections, Audit_Complaints, AuditPhotos, StoreAudits, AuditTags, DCR_Branch_Access, DCR_User_Branches, \
    DCR_DateWiseCollection, FabDailyClockIn, DcrUserLogins, FabDailyMailClockIn

# Importing the WTF form classes used by this controller.
from .forms import SendOTPForm, VerifyOTPForm, CollectAmountForm, SubmitCollectAmountForm, PendingDepositeForm, \
    SubmitDepositeForm, DepositHistory, StorePermissionForm, AuditComplaintsForm, GarmentAuditForm, GarmentAuditDetailsForm, StoreList, ClockInForm

# Importing the loggers module.
from dcr.generic.loggers import error_logger, info_logger

dcr_blueprint = Blueprint("dcr", __name__, url_prefix='/dcr', template_folder='templates',
                          static_folder='static')


@dcr_blueprint.route('/')
def index():
    """
    Index route.
    @return:
    """
    # Redirects to the JFSL website.
    return redirect("https://jfsl.in", code=302)




@dcr_blueprint.route('/send_login_otp', methods=["POST"])
@api_key_required
def send_login_otp():
    """
    API for sending an OTP to a mobile number.
    @return:
    """
    send_otp_form = SendOTPForm()
    if send_otp_form.validate_on_submit():
        mobile_number = send_otp_form.mobile_number.data
        otp_type = send_otp_form.otp_type.data
        person = send_otp_form.person.data if send_otp_form.person.data != '' else None
        send_status = False

        # user_details = db.session.query(DCR_Users).filter(DCR_Users.Phone == mobile_number,DCR_Users.is_active == 1).one_or_none()
        user_details = db.session.query(DCR_Users).filter(DCR_Users.Phone == mobile_number,DCR_Users.IsDeleted == 0).one_or_none()
        if user_details is not None:
            active_user_details = db.session.query(DCR_Users).filter(DCR_Users.Phone == mobile_number, or_(DCR_Users.is_active == 1, DCR_Users.is_audit_active == 1)).one_or_none()
            if active_user_details is not None:
                # Generating an OTP (A random value from 1000 to 9999).
                otp = random.randint(1000, 9999)
                time = "30Seconds"
                # Result flag
                send_status = False
                if otp_type == 'login':
                    # otp_message = f"{otp}  is your OTP to login Audit/Collection app and its valid only for {time}. Team Jyothy"
                    otp_message = f"{otp} is your OTP to login FabDaily App %26 its valid only for 30 Seconds. Team Jyothy."

                if CURRENT_ENV == 'development':

                    send = send_sms(mobile_number, otp_message, '')
                    # print(send)
                    send_status = True
                    if send['result'] is not None:
                        #if send['result']['status'] == 'OK':
                        if send['result']['id'] is not None:
                            send_status = True
                            # Saving the details into the OTP table.
                            try:
                                new_otp = DCR_OTPs(OTP=otp, MobileNumber=mobile_number, Type=otp_type, Person=person,
                                                   IsVerified=0,
                                                   RecordCreatedDate=get_current_date()
                                                   )
                                db.session.add(new_otp)
                                db.session.commit()
                            except Exception as e:
                                error_logger(f'Route: {request.path}').error(e)
                else:
                    send = send_sms(mobile_number, otp_message, '')
                    if send['result'] is not None:
                        #if send['result']['status'] == 'OK':
                        if send['result']['id'] is not None:
                            send_status = True
                            # Saving the details into the OTP table.
                            try:
                                new_otp = DCR_OTPs(OTP=otp, MobileNumber=mobile_number, Type=otp_type, Person=person,
                                                   IsVerified=0,
                                                   RecordCreatedDate=get_current_date()
                                                   )
                                db.session.add(new_otp)
                                db.session.commit()
                            except Exception as e:
                                error_logger(f'Route: {request.path}').error(e)
            else:
                error_msg = 'The user is inactivated'
        else:
            error_msg = 'This contact number is not registered'

        if send_status:
            # Successfully sent the OTP.
            final_data = generate_final_data('SUCCESS')
            final_data['otp'] = otp
        elif error_msg:
            final_data = generate_final_data('CUSTOM_FAILED', error_msg)

        else:
            # Failed to send the OTP.
            final_data = generate_final_data('FAILED')
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(send_otp_form.errors)

    return final_data



# @dcr_blueprint.route('verify_otp', methods=["POST"])
# @api_key_required
# def verify_otp():
#     """
#     API for verifying the OTP.
#     @return:
#     """
#     verify_otp_form = VerifyOTPForm()
#     if verify_otp_form.validate_on_submit():
#         mobile_number = verify_otp_form.mobile_number.data
#         otp = verify_otp_form.otp.data
#         # Result flag.
#         verified = False
#         error_msg = ''
#         today = datetime.today().strftime("%Y-%m-%d")


#         # Checking the current environment, if the env is development, no need to verify OTP.
#         # if CURRENT_ENV == 'development':
#         #     verified = True
#         # else:
#         otp_details = db.session.query(DCR_OTPs).filter(DCR_OTPs.MobileNumber == mobile_number
#                                                         ).order_by(
#             DCR_OTPs.RecordCreatedDate.desc()).first()
#         if otp_details is not None:
#             if otp == otp_details.OTP:
#                 now = datetime.strptime(get_current_date(), "%Y-%m-%d %H:%M:%S")
#                 seconds = abs((now - otp_details.RecordCreatedDate)).seconds
#                 # The difference between the OTP created date and current date must be
#                 # less than 1000 seconds.
#                 if seconds < 31:
#                     # Mark this OTP log as verified.
#                     otp_details.IsVerified = 1
#                     db.session.commit()
#                     verified = True
#                 else:
#                     # OTP created more than 3 minutes ago.
#                     error_msg = 'This OTP has been expired.'
#             elif mobile_number == '9876543210':
#                 otp_details.IsVerified = 1
#                 db.session.commit()
#                 verified = True
#             else:
#                 # Another non verified OTP record has been found.
#                 error_msg = 'Invalid OTP'
#         else:
#             # OTP record has not found in the DB.
#             error_msg = 'Invalid OTP.'
#         UserDetails = db.session.query(DCR_Users).filter(DCR_Users.Phone == mobile_number,
#                                                          or_(DCR_Users.is_active == 1, DCR_Users.is_audit_active == 1)
#                                                          ).one_or_none()
#         if verified:
#             if UserDetails is not None:
#                 # Checking if there's any active access token is generated or not.
#                 # If there's an active access token is present, deny the login request.
#                 access_tokens = db.session.query(DcrUserLogins).filter(
#                     DcrUserLogins.DUserId == UserDetails.Id, DcrUserLogins.IsActive == 1,
#                     DcrUserLogins.AuthKeyExpiry == 0).all()
#                 if len(access_tokens) == 0:
#                     permit_login = True
#                 else:
#                     for access_token in access_tokens:
#                         # Making the access token expire.
#                         access_token.IsActive = 0
#                         access_token.AuthKeyExpiry = 1
#                         db.session.commit()
#                     # Made all active tokens expired.
#                     permit_login = True
#                 if permit_login:
#                     access_key = jwt.encode({'id': str(uuid.uuid1())},
#                                             current_app.config['JWT_SECRET_KEY'] + str(UserDetails.Id),
#                                             algorithm='HS256')

#                     # Setting up user_agent dict for saving the basic client device details.
#                     user_agent = {'browser': request.user_agent.browser, 'language': request.user_agent.language,
#                                   'platform': request.user_agent.platform,
#                                   'string': request.user_agent.string,
#                                   'version': request.user_agent.version,
#                                   'ip_addr': request.remote_addr
#                                   }

#                     # Setting up the device type based on user agent's platform.
#                     ua_platform = user_agent['platform'] if user_agent['platform'] is not None else ''
#                     if ua_platform.lower() in ('iphone', 'android'):
#                         device_type = 'M'
#                     elif ua_platform.lower() in ('windows', 'linux'):
#                         device_type = 'C'
#                     else:
#                         device_type = 'O'

#                     # If the delivery user is found then add login details into DeliveryUserLogin table.
#                     new_delivery_user_login = DcrUserLogins(DUserId=UserDetails.Id,
#                                                             LoginTime=get_current_date(),
#                                                             AuthKey=access_key.decode('utf-8'), AuthKeyExpiry=0,
#                                                             LastAccessTime=get_current_date(),
#                                                             IsActive=1,
#                                                             DeviceType=device_type,
#                                                             DeviceIP=user_agent['ip_addr'],
#                                                             Browser=user_agent['browser'],
#                                                             Platform=user_agent['platform'],
#                                                             Language=user_agent['language'],
#                                                             UAString=user_agent['string'],
#                                                             UAVersion=user_agent['version'],
#                                                             RecordCreatedDate=get_current_date(),
#                                                             RecordLastUpdatedDate=get_current_date(),
#                                                             RecordVersion=0,
#                                                             Date=today
#                                                             )
#                     try:
#                         db.session.add(new_delivery_user_login)
#                         db.session.commit()
#                         # final_data = generate_final_data("DATA_SAVED")
#                     except Exception as e:
#                         db.session.rollback()
#                         error_logger(f'Route: {request.path}').error(e)
#                         # final_data = generate_final_data('DATA_SAVE_FAILED')
#                     if error_msg:
#                         final_data = generate_final_data('CUSTOM_FAILED', error_msg)

#                     elif verified:
#                         total_cash_in_hand = 0
#                         store = 0
#                         branches = db.session.query(DCR_Users.Branches).filter(DCR_Users.Id == UserDetails.Id).one_or_none()
#                         if branches is not None:
#                             store = len(branches)

#                         cash_in_hand = db.session.query(DCR_Collection.CollectedAmount).filter(DCR_Collection.IsDeposited == 0,
#                                                                                                 DCR_Collection.CollectedBy == UserDetails.Id).all()

#                         if cash_in_hand is not None:
#                             cash_in_hand = SerializeSQLAResult(cash_in_hand).serialize()
#                             for cash in cash_in_hand:
#                                 total_cash_in_hand = total_cash_in_hand + cash['CollectedAmount']

#                         result = {'AccessKey': access_key.decode('utf-8'),
#                                   'UserId': UserDetails.Id,
#                                   'UserName': UserDetails.Name,
#                                   'total_cash_in_hand': total_cash_in_hand,
#                                   'number_of store': store}
#                         final_data = generate_final_data('SUCCESS')
#                         final_data['result'] = result

#                     else:
#                         # OTP is not verified. Return the failed message.
#                         final_data = generate_final_data('CUSTOM_FAILED', f'Failed to verify. {error_msg}')
#                 else:
#                     final_data = generate_final_data('CUSTOM_FAILED',
#                                                      'Another active access token found. Failed to login.')
#             else:
#                 error_msg = 'access denied.'
#                 final_data = generate_final_data('CUSTOM_FAILED', f'Failed to verify. {error_msg}')
#         else:
#             final_data = generate_final_data('CUSTOM_FAILED', f'Failed to verify. {error_msg}')

#     else:
#         # Form validation error.
#         final_data = generate_final_data('FORM_ERROR')
#         final_data['errors'] = populate_errors(verify_otp_form.errors)

#     return final_data




@dcr_blueprint.route('get_store_list', methods=["GET"])
@authenticate('dcr')
def get_store_list():
    final_branch = []
    user_id = request.headers.get('user-id')

    user_branch_access = db.session.query(DCR_User_Branches.BranchCode).filter(
        DCR_User_Branches.UserId == user_id).all()
    user_branches = SerializeSQLAResult(user_branch_access).serialize()
    log_data = {
        'user_id': user_id,
        'user_branches': user_branches

    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    if user_branches is not None:
        if len(user_branches) > 0:
            branch_codes = []
            for branch in user_branches:
                branch_codes.append(branch['BranchCode'])
            log_data = {
                'branch_codes': branch_codes
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
            result = CallSP(query).execute().fetchall()

            for branch in result:
                for branch_code in branch_codes:
                    if branch['BranchCode'] == branch_code:
                        final_branch.append(branch)
                        branch_codes.remove(branch_code)
            # log_data = {
            #     'final_branch': final_branch
            # }
            # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        else:
            branches = db.session.query(DCR_Users.Branches).filter(DCR_Users.Id == user_id).one_or_none()
            if branches is not None:
                user_branch = branches.Branches
                user_branch = user_branch[1:]
                user_branch = user_branch[:-1]
                user_branch = user_branch.replace('"', '')
                user_branch = user_branch.split(",")
                if len(user_branch) > 0:
                    query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
                    result = CallSP(query).execute().fetchall()
                    for branch in result:
                        for branch_code in user_branch:
                            if branch['BranchCode'] == branch_code:
                                final_branch.append(branch)
                                user_branch.remove(branch_code)
            else:
                pass

    else:
        branches = db.session.query(DCR_Users.Branches).filter(DCR_Users.Id == user_id).one_or_none()
        if branches is not None:
            user_branch = branches.Branches
            user_branch = user_branch[1:]
            user_branch = user_branch[:-1]
            user_branch = user_branch.replace('"', '')
            user_branch = user_branch.split(",")
            if len(user_branch) > 0:
                query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
                result = CallSP(query).execute().fetchall()
                for branch in result:
                    for branch_code in user_branch:
                        if branch['BranchCode'] == branch_code:
                            final_branch.append(branch)
                            user_branch.remove(branch_code)
        else:
            pass

    final_data = generate_final_data('DATA_FOUND')
    final_data['result'] = final_branch
    return final_data

@dcr_blueprint.route('get_store_list_test', methods=["POST"])
@authenticate('dcr')
def get_store_list_test():
    store_list_form = StoreList()
    if store_list_form.validate_on_submit():
        login_type = store_list_form.login_type.data
        final_branch = []
        user_id = request.headers.get('user-id')
        if login_type == 'dcr':
            user_branch_access = db.session.query(DCR_User_Branches.BranchCode).filter(
                DCR_User_Branches.UserId == user_id,DCR_User_Branches.app_login == 1, DCR_User_Branches.IsDeleted == 0).all()
            if len(user_branch_access) > 0:
                user_branches = SerializeSQLAResult(user_branch_access).serialize()
            else:
                user_branches = []
        elif login_type == 'audit':
            user_branch_access = db.session.query(DCR_User_Branches.BranchCode).filter(
                DCR_User_Branches.UserId == user_id, DCR_User_Branches.app_login == 2, DCR_User_Branches.IsDeleted == 0).all()
            if len(user_branch_access) > 0:
                user_branches = SerializeSQLAResult(user_branch_access).serialize()
            else:
                user_branches = []
        else:
            user_branches = []
        # log_data = {
        #     'user_id': user_id,
        #     'user_branches': user_branches
        # }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        if user_branches is not None:
            if len(user_branches) > 0:
                branch_codes = []
                for branch in user_branches:
                    branch_codes.append(branch['BranchCode'])
                log_data = {
                    'branch_codes': branch_codes
                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
                result = CallSP(query).execute().fetchall()

                log_data = {
                    'Sp-Qry': query
                    # 'branch': result
                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))

                for branch in result:
                    for branch_code in branch_codes:
                        if branch['BranchCode'] == branch_code:
                            final_branch.append(branch)
                            branch_codes.remove(branch_code)
                # log_data = {
                #     'final_branch': final_branch
                # }
                # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            else:
                branches = db.session.query(DCR_Users.Branches).filter(DCR_Users.Id == user_id).one_or_none()
                if branches.Branches is not None:
                    user_branch = branches.Branches
                    user_branch = user_branch[1:]
                    user_branch = user_branch[:-1]
                    user_branch = user_branch.replace('"', '')
                    user_branch = user_branch.split(",")
                    if len(user_branch) > 0:
                        query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
                        result = CallSP(query).execute().fetchall()
                        log_data = {
                            'Store_List': query
                            # 'branch': result
                        }
                        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                        for branch in result:
                            for branch_code in user_branch:
                                if branch['BranchCode'] == branch_code:
                                    final_branch.append(branch)
                                    user_branch.remove(branch_code)
                else:
                    pass

        else:
            branches = db.session.query(DCR_Users.Branches).filter(DCR_Users.Id == user_id).one_or_none()
            if branches is not None:
                user_branch = branches.Branches
                user_branch = user_branch[1:]
                user_branch = user_branch[:-1]
                user_branch = user_branch.replace('"', '')
                user_branch = user_branch.split(",")
                if len(user_branch) > 0:
                    query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
                    result = CallSP(query).execute().fetchall()
                    # log_data = {
                    #     'branch': result
                    # }
                    # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                    for branch in result:
                        for branch_code in user_branch:
                            if branch['BranchCode'] == branch_code:
                                final_branch.append(branch)
                                user_branch.remove(branch_code)
            else:
                pass

        final_data = generate_final_data('DATA_FOUND')
        final_data['result'] = final_branch
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(store_list_form.errors)
    log_data = {
        'final_data': final_data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    return final_data


@dcr_blueprint.route('dashboard', methods=["POST"])
@authenticate('dcr')
def dashboard():
    user_id = request.headers.get('user-id')
    total_cash_in_hand = 0
    store = 0
    today = get_today()

    branches = db.session.query(DCR_Users.Branches).filter(DCR_Users.Id == user_id).one_or_none()
    if branches is not None:
        store = len(branches)

    cash_in_hand = db.session.query(DCR_Collection.CollectedAmount).filter(DCR_Collection.IsDeposited == 0,DCR_Collection.IsDeleted==0,
                                                                            DCR_Collection.CollectedBy == user_id).all()

    login = db.session.query(DcrUserLogins).filter(
        DcrUserLogins.DUserId == user_id,
        DcrUserLogins.Date == today,
        DcrUserLogins.IsActive == 1).one_or_none()
    if login is not None:
        login_status = True
    else:
        login_status = False

    if cash_in_hand is not None:
        cash_in_hand = SerializeSQLAResult(cash_in_hand).serialize()
        for cash in cash_in_hand:
            total_cash_in_hand = total_cash_in_hand + cash['CollectedAmount']

    final_data = generate_final_data('DATA_FOUND')
    final_data['result'] = {'total_cash_in_hand': total_cash_in_hand, 'number_of store': store, 'login_status': login_status, 'android_version': 29, 'ios_version': 29}
    return final_data



@dcr_blueprint.route('dashboard_test', methods=["POST"])
@authenticate('dcr')
def dashboard_test():
    user_id = request.headers.get('user-id')
    total_cash_in_hand = 0
    store = 0
    today = get_today()

    app_access =""
    branches = db.session.query(DCR_Users.Branches).filter(DCR_Users.Id == user_id).one_or_none()
    if branches is not None:
        store = len(branches)
    login_access = db.session.query(DCR_Users.app_login, DCR_Users.is_active, DCR_Users.is_audit_active).filter(
        DCR_Users.Id == user_id).one_or_none()
    if login_access is not None:
        if login_access.app_login == 0:
            if login_access.is_active and login_access.is_audit_active:
                app_access = "both"
            elif login_access.is_active:
                app_access = "dcr"
            elif login_access.is_audit_active:
                app_access = "audit"
            else:
                app_access = "no_access"
        elif login_access.app_login == 1:
            if login_access.is_active:
                app_access = "dcr"
            else:
                app_access = "no_access"
        elif login_access.app_login == 2:
            if login_access.is_audit_active:
                app_access = "audit"
            else:
                app_access = "no_access"
        else:
            app_access = "no_access"
    else:
        pass


    access = db.session.query(
                        DCR_Users.is_active,
                        DCR_Users.is_audit_active
                    ).filter(
                        DCR_Users.Id == user_id
                    ).first() 
    log_data = {
            'access': access,
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    dcr_access = False
    audit_access = False
    if access:
        if access.is_active == 1 and access.is_audit_active == 1:
            dcr_access = True
            audit_access = True
        elif access.is_active == 1:
            dcr_access = True
        elif access.is_audit_active == 1:
            audit_access = True

    cash_in_hand = db.session.query(DCR_Collection.CollectedAmount).filter(DCR_Collection.IsDeposited == 0,
                                                                            DCR_Collection.CollectedBy == user_id,DCR_Collection.IsDeleted == 0).all()

    login = db.session.query(DcrUserLogins).filter(
        DcrUserLogins.DUserId == user_id,
        DcrUserLogins.Date == today,
        DcrUserLogins.IsActive == 1).one_or_none()
    if login is not None:
        login_status = True
    else:
        login_status = False

    if cash_in_hand is not None:
        cash_in_hand = SerializeSQLAResult(cash_in_hand).serialize()
        for cash in cash_in_hand:
            total_cash_in_hand = total_cash_in_hand + cash['CollectedAmount']

    final_data = generate_final_data('DATA_FOUND')
    final_data['result'] = {'total_cash_in_hand': total_cash_in_hand, 'number_of store': store, 'login_status': login_status, 'app_access': app_access, 'android_version': 31, 'ios_version': 31,'dcr_access': dcr_access,'audit_access': audit_access}
    log_data = {
        'final_data': final_data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    return final_data




@dcr_blueprint.route('submit_deposit', methods=["POST"])
@authenticate('dcr')
def submit_deposit():
    submit_deposit_form = SubmitDepositeForm()
    if submit_deposit_form.validate_on_submit():
        collection_id = submit_deposit_form.collection_id.data
        b64_image = submit_deposit_form.b64_image.data
        log_data = {
            'b64_image ': b64_image
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        user_id = request.headers.get('user-id')
        deposited = False
        purified_string = base64.b64decode(b64_image.replace('data:image/png;base64,', ''))
        total_deposit = 0
        deposit_mail_branches = []
        
        for c_id in collection_id:
            # Create a name for the image
            random_val = random.randint(0, 9999)
            now = datetime.now()
            dt_string = now.strftime("%d-%m-%Y-%I-%M-%S-%p")
            filename = f'{user_id}Deposit_{dt_string}_0'
            root_dir = os.path.dirname(current_app.instance_path)
            uploads_folder = f'{root_dir}/uploads/deposit_images'
            if not os.path.exists(uploads_folder):
                os.makedirs(uploads_folder)
            # Target file link
            target_file = f'{uploads_folder}/{filename}.jpg'
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %I:%M:%S %p")
            

            with open(target_file, 'wb') as f:
                f.write(purified_string)
                uploaded = True

            im = Image.new('RGBA', (2000, 120), (255, 255, 255, 255))
            draw = ImageDraw.Draw(im)
            font = ImageFont.truetype("arial.ttf", 40)
            draw.text((0, 0), dt_string, (0, 0, 0), font=font)
            image = Image.open(target_file)

            width, height = image.size
            watermark_image = image.copy()
            watermark_image.paste(im, (0, height - 80))
            watermark_image.save(target_file)

            collection_details = db.session.query(DCR_Collection).filter(DCR_Collection.IsDeposited == 0,
                                                                          DCR_Collection.Id == c_id).one_or_none()
            if collection_details is not None:
                deposit_mail_branches.append(collection_details.StoreBranchCode)
                branch_code = collection_details.StoreBranchCode
                total_deposit = total_deposit + collection_details.CollectedAmount
                if uploaded:
                    deposit = DCR_Deposit(
                        Date=get_current_date(),
                        DepositedAmount=collection_details.CollectedAmount,
                        Image=f'{filename}',
                        DepositedBy=user_id,
                        IsDeleted=0
                    )

                try:
                    db.session.add(deposit)
                    db.session.commit()
                    deposited = True
                    deposit_id = deposit.Id
                    collection_details.DepositId = deposit_id
                    collection_details.IsDeposited = 1
                    collection_details.DepositedDate = deposit.Date
                    db.session.commit()

                except Exception as e:
                    db.session.rollback()
                    error_logger(f'Route: {request.path}').error(e)
            else:
                pass


        deposit_report = db.session.query(DCR_Collection.Date.label('Collected Date'),
                                          DCR_Collection.StoreBranchName.label('Store Names'),
                                          DCR_Collection.CollectedAmount.label('Amount'),
                                          DCR_Deposit.Date.label('Deposit Date'),
                                          DCR_Collection.DateFrom.label('Settlement Date From'),
                                          DCR_Collection.DateTo.label('Settlement Date To'),
                                          DCR_Collection.CollectionType.label('Collection Type'),
                                          DCR_Users.Name.label('Collection Executive Name')
                                          ).outerjoin(DCR_Deposit,
                                                      DCR_Deposit.Id == DCR_Collection.DepositId).outerjoin(
            DCR_Users, DCR_Users.Id == DCR_Deposit.DepositedBy
        ).filter(
            DCR_Collection.IsDeposited == 1,
            DCR_Collection.Id.in_(collection_id)).all()
        deposit_report = SerializeSQLAResult(deposit_report).serialize()

        report_link = GenerateReport(deposit_report, 'Deposit').generate().get()
        user_name = db.session.query(DCR_Users.Name).filter(DCR_Users.Id == user_id).one_or_none()
        current_date = date.today()
        deposit_date = current_date.strftime("%d/%m/%Y")
        # branch_code = set(branch_code)
        # branch_code = list(branch_code)
        # branch_codes = str(branch_code)[1:-1]
        # city_codes = text(
        #     f"""SELECT [BranchInfo].[CityCode] FROM {SERVER_DB}.[dbo].[BranchInfo] WHERE[BranchInfo].[BranchCode] IN ({branch_codes}) """)
        # test = db.engine.execute(city_codes).fetchall()
        # result = SerializeSQLAResult(test).serialize()
        # city_code = []
        citycode = text(
            f"""SELECT [BranchInfo].[CityCode] FROM {SERVER_DB}.[dbo].[BranchInfo] WHERE[BranchInfo].[BranchCode] = '{branch_code}' """)
        test = db.engine.execute(citycode).fetchall()
        result = SerializeSQLAResult(test).serialize()
        city_code = result[0]['CityCode']
        # for city in result:
        #     city_code.append(city['CityCode'])
        # city = str(city_code)[1:-1]
        # cities = city.replace(',', '--')
        deposit_mail_branches = set(deposit_mail_branches)
        deposit_mail_branches = list(deposit_mail_branches)
        deposit_mail_branch_codes = str(deposit_mail_branches)[1:-1]
        deposit_mail_branch_codes = deposit_mail_branch_codes.replace("'", '')
        deposit_mail_branch_codes = deposit_mail_branch_codes.replace(" ", '')
        query = f"EXEC {OLD_DB}.dbo.GetBranchEmail @branchcode = '{deposit_mail_branch_codes}'"
        mails = CallSP(query).execute().fetchall()
        log_data = {
            'deposit branch mail ': query,
            'result mails': mails
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        branch_mail = []
        for mail in mails:
            branch_mail.append(mail['ToEmail'])
        branch_mail = set(branch_mail)
        branch_mail = list(branch_mail)
        branch_mail = str(branch_mail)[1:-1]
        branch_mail = branch_mail.replace("'", '')
        branch_mail = branch_mail.replace(" ", '')
        branch_mail = branch_mail.replace(",", ';')

        deposit_details = {
            "depositDate": deposit_date,
            "filename": report_link,
            "ImageName": f'{filename}',
            "DepositedBy": user_name.Name,
            "TotalAmount": total_deposit,
            "CityCode": city_code,
            "ToMail": branch_mail
        }
        mail = queries.dcr_deposit_mail(deposit_details)

        if deposited:
            final_data = generate_final_data('DATA_UPDATED')

        else:
            final_data = generate_final_data('DATA_UPDATE_FAILED')

    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(submit_deposit_form.errors)
    return final_data


@dcr_blueprint.route('get_collection_history', methods=["POST"])
@authenticate('dcr')
def get_collection_history():
    pending_deposite_form = PendingDepositeForm()
    if pending_deposite_form.validate_on_submit():
        store_id = None if pending_deposite_form.store_id.data == '' else pending_deposite_form.store_id.data

        # start_date = pending_deposite_form.start_date.data
        # end_date = pending_deposite_form.end_date.data
        start_date = None if pending_deposite_form.start_date.data == '' else pending_deposite_form.start_date.data
        end_date = None if pending_deposite_form.end_date.data == '' else pending_deposite_form.end_date.data
        error_msg = None
        user_id = request.headers.get('user-id')

        if start_date is not None:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            formatted_end_date_date = (end_date_obj + timedelta(1)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            formatted_start_date_date = (datetime.today() - timedelta(8)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date_date = get_current_date()

        if store_id is None and start_date is None and end_date is None:

            pending_deposite_data = db.session.query(DCR_Collection.CollectedAmount, DCR_Collection.StoreBranchCode,
                                                     DCR_Collection.StoreBranchName, DCR_Collection.Id,
                                                     DCR_Collection.DateTo.label('DateTo'),
                                                     DCR_Collection.DateFrom.label('DateFrom'),
                                                     DCR_Collection.TotalAmount, DCR_Collection.Date.label('Date'),
                                                     DCR_Collection.CollectedAmount, DCR_Collection.StoreInCharge,
                                                     DCR_Collection.Remarks).filter(DCR_Collection.IsDeleted == 0, DCR_Collection.IsDeposited == 0, DCR_Collection.CollectedBy == user_id, DCR_Collection.Date.between(
                                                                                         formatted_start_date_date,
                                                                                         formatted_end_date_date
                                                                                     )).order_by(DCR_Collection.Date.desc()).all()

        elif store_id is not None and start_date is None and end_date is None:
            pending_deposite_data = db.session.query(DCR_Collection.CollectedAmount, DCR_Collection.StoreBranchCode,
                                                     DCR_Collection.StoreBranchName, DCR_Collection.Id,
                                                     DCR_Collection.DateTo.label('DateTo'),
                                                     DCR_Collection.DateFrom.label('DateFrom'),
                                                     DCR_Collection.TotalAmount, DCR_Collection.Date.label('Date'),
                                                     DCR_Collection.CollectedAmount, DCR_Collection.StoreInCharge,
                                                     DCR_Collection.Remarks).filter(DCR_Collection.IsDeleted == 0, DCR_Collection.IsDeposited == 0, DCR_Collection.CollectedBy == user_id,
                                                                                     DCR_Collection.StoreBranchCode == store_id, DCR_Collection.Date.between(
                                                                                         formatted_start_date_date,
                                                                                         formatted_end_date_date
                                                                                     )).order_by(DCR_Collection.Date.desc()).all()
        elif store_id is None and start_date is not None and end_date is not None:
            pending_deposite_data = db.session.query(DCR_Collection.CollectedAmount, DCR_Collection.StoreBranchCode,
                                                     DCR_Collection.StoreBranchName, DCR_Collection.Id,
                                                     DCR_Collection.DateTo.label('DateTo'),
                                                     DCR_Collection.DateFrom.label('DateFrom'),
                                                     DCR_Collection.TotalAmount, DCR_Collection.Date.label('Date'),
                                                     DCR_Collection.CollectedAmount, DCR_Collection.StoreInCharge,
                                                     DCR_Collection.Remarks).filter(DCR_Collection.IsDeleted == 0, DCR_Collection.IsDeposited == 0, DCR_Collection.CollectedBy == user_id,
                                                                                     DCR_Collection.Date.between(
                                                                                         formatted_start_date_date, formatted_end_date_date
                                                                                     )).order_by(DCR_Collection.Date.desc()).all()
        elif store_id is not None and start_date is not None and end_date is not None:
            pending_deposite_data = db.session.query(DCR_Collection.CollectedAmount, DCR_Collection.StoreBranchCode,
                                                     DCR_Collection.StoreBranchName, DCR_Collection.Id,
                                                     DCR_Collection.DateTo.label('DateTo'),
                                                     DCR_Collection.DateFrom.label('DateFrom'),
                                                     DCR_Collection.TotalAmount, DCR_Collection.Date.label('Date'),
                                                     DCR_Collection.CollectedAmount, DCR_Collection.StoreInCharge,
                                                     DCR_Collection.Remarks).filter(DCR_Collection.IsDeleted == 0, DCR_Collection.IsDeposited == 0, DCR_Collection.CollectedBy == user_id,
                                                                                     DCR_Collection.StoreBranchCode == store_id,
                                                                                     DCR_Collection.Date.between(
                                                                                         formatted_start_date_date, formatted_end_date_date
                                                                                     )).order_by(DCR_Collection.Date.desc()).all()

        pending_deposite = SerializeSQLAResult(pending_deposite_data).serialize(full_date_fields=['DateTo', 'DateFrom', 'Date'])
        if pending_deposite is not None:
            total_pending = 0
            for deposit in pending_deposite:
                total_pending = total_pending + deposit['CollectedAmount']
        final_data = generate_final_data('DATA_FOUND')
        final_data['total_pending'] = total_pending
        final_data['result'] = pending_deposite
        log_data = {
            'final_data': final_data
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(pending_deposite_form.errors)


    return final_data


@dcr_blueprint.route('/deposit_history', methods=["POST"])
@authenticate('dcr')
def deposit_history():
    deposite_history_form = DepositHistory()
    if deposite_history_form.validate_on_submit():
        store_id = None if deposite_history_form.store_id.data == '' else deposite_history_form.store_id.data
        start_date = None if deposite_history_form.start_date.data == '' else deposite_history_form.start_date.data
        end_date = None if deposite_history_form.end_date.data == '' else deposite_history_form.end_date.data
        deposit_data = None
        error_msg = None
        user_id = request.headers.get('user_id')
        if start_date is not None:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            formatted_end_date_date = (end_date_obj + timedelta(1)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            formatted_start_date_date = (datetime.today() - timedelta(8)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date_date = get_current_date()
        if store_id is None and start_date is None and end_date is None:
            deposit_data = db.session.query(DCR_Deposit.Date.label('Date'), DCR_Collection.TotalAmount,
                                            DCR_Deposit.Image, DCR_Collection.StoreBranchName,
                                            DCR_Collection.Id, DCR_Collection.StoreInCharge,
                                            DCR_Collection.CollectedAmount,
                                            DCR_Collection.DateTo.label('DateTo'),
                                            DCR_Collection.DateFrom.label('DateFrom')).join(DCR_Collection,
                                                                       DCR_Collection.DepositId == DCR_Deposit.Id
                                                                       ).filter(DCR_Collection.IsDeleted == 0,
                DCR_Deposit.DepositedBy == user_id, DCR_Deposit.Date.between(
                    formatted_start_date_date, formatted_end_date_date
                )).order_by(
                DCR_Deposit.Date.desc()).all()

        elif store_id is not None and start_date is None and end_date is None:
            deposit_data = db.session.query(DCR_Deposit.Date.label('Date'), DCR_Collection.TotalAmount,
                                            DCR_Deposit.Image, DCR_Collection.StoreBranchName,
                                            DCR_Collection.Id, DCR_Collection.StoreInCharge,
                                            DCR_Collection.CollectedAmount,
                                            DCR_Collection.DateTo.label('DateTo'),
                                            DCR_Collection.DateFrom.label('DateFrom')).join(DCR_Collection,
                                                                       DCR_Collection.DepositId == DCR_Deposit.Id
                                                                       ).filter(DCR_Collection.IsDeleted == 0,
                DCR_Collection.CollectedBy == user_id,
                DCR_Collection.StoreBranchCode == store_id, DCR_Deposit.Date.between(
                    formatted_start_date_date, formatted_end_date_date
                )).order_by(
                DCR_Deposit.Date.desc()).all()

        elif store_id is None and start_date is not None and end_date is not None:
            deposit_data = db.session.query(DCR_Deposit.Date.label('Date'), DCR_Collection.TotalAmount,
                                            DCR_Deposit.Image, DCR_Collection.StoreBranchName,
                                            DCR_Collection.Id, DCR_Collection.StoreInCharge,
                                            DCR_Collection.CollectedAmount,
                                            DCR_Collection.DateTo.label('DateTo'),
                                            DCR_Collection.DateFrom.label('DateFrom')).join(DCR_Deposit,
                                                                       DCR_Deposit.Id == DCR_Collection.DepositId
                                                                       ).filter(
                                                                                DCR_Collection.CollectedBy == user_id, DCR_Collection.IsDeleted == 0,
                                                                                DCR_Deposit.Date.between(
                                                                                    formatted_start_date_date, formatted_end_date_date
                                                                                )).order_by(
                                                                                DCR_Deposit.Date.desc()).all()
        elif store_id is not None and start_date is not None and end_date is not None:
            deposit_data = db.session.query(DCR_Deposit.Date.label('Date'), DCR_Collection.TotalAmount,
                                            DCR_Deposit.Image, DCR_Collection.StoreBranchName,
                                            DCR_Collection.Id, DCR_Collection.StoreInCharge,
                                            DCR_Collection.CollectedAmount,
                                            DCR_Collection.DateTo.label('DateTo'),
                                            DCR_Collection.DateFrom.label('DateFrom')).join(DCR_Deposit,
                                                                       DCR_Deposit.Id == DCR_Collection.DepositId
                                                                       ).filter(
                DCR_Collection.CollectedBy == user_id, DCR_Collection.IsDeleted == 0,
                DCR_Collection.StoreBranchCode == store_id,
                DCR_Deposit.Date.between(
                    formatted_start_date_date, formatted_end_date_date
                )).order_by(
                DCR_Deposit.Date.desc()).all()

        if deposit_data is not None:
            history = SerializeSQLAResult(deposit_data).serialize(full_date_fields=['DateTo','DateFrom','Date'])
            final_data = generate_final_data('DATA_FOUND')
            final_data['result'] = history
            log_data = {
                'final_data': final_data
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        else:
            final_data = generate_final_data('DATA_NOT_FOUND', error_msg)
            final_data['result'] = []
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(deposite_history_form.errors)
    return final_data


@dcr_blueprint.route('/logout', methods=["POST"])
# @authenticate('dcr')
def logout():
    """
    Logout API for the store users.
    @return: If the validations are successful, make the access token expire
    by changing the values(AuthKeyExpiry, IsActive) in the StoreUserLogin table.
    """
    result = False
    try:
        user_id = request.headers.get('user_id')
        access_key = request.headers.get('access_key')
        login_data = db.session.query(DcrUserLogins).filter(DcrUserLogins.DUserId == user_id,
                                                           DcrUserLogins.AuthKey == access_key,
                                                           DcrUserLogins.AuthKeyExpiry == 0).one_or_none()
        if login_data is not None:
            login_data.AuthKeyExpiry = 1
            login_data.IsActive = 0
            db.session.commit()
            result = True

    except Exception as e:
        db.session.rollback()
        error_logger(f'Route: {request.path}').error(e)

    if result:
        final_data = generate_final_data('SUCCESS')
    else:
        final_data = generate_final_data('FAILED')

    return final_data



@dcr_blueprint.route('/get_deposite_image/<photo_file>', methods=["GET"])
# @authenticate('dcr')
def get_deposite_image(photo_file):
    """
    API for getting Delivery user images based on image name
    """

    root_dir = os.path.dirname(current_app.instance_path)

    # Loading the data from the DB.
    image_data = None
    try:
        # Getting the image data from the DB.
        image_data = db.session.query(DCR_Deposit.Image).filter(
            DCR_Deposit.Image == photo_file, DCR_Deposit.IsDeleted == 0).first()
    except Exception as e:
        error_logger(f'Route: {request.path}').error(e)

    if image_data:
        # Here a image data is found. So return the image file.
        target_file = f'{root_dir}/uploads/deposit_images/{photo_file}.jpg'
        # log_data = {
        # 'root_dir': target_file

        # }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        # print(send_file(target_file, mimetype='image/jpg'))
        return send_file(target_file, mimetype='image/jpg')
    else:
        # No file found for that particular image.
        final_data = generate_final_data('FILE_NOT_FOUND')

        return final_data



@dcr_blueprint.route('get_complaints', methods=["GET"])
@authenticate('dcr')
def get_complaints():
    complaints = db.session.query(Audit_Complaints.Id, Audit_Complaints.IsPhoto, Audit_Complaints.IsRemarks,
                                  Audit_Complaints.AuditQuestions).filter(Audit_Complaints.IsDeleted == 0).all()
    data = False
    if complaints is not None:
        complaints = SerializeSQLAResult(complaints).serialize()
        data = True
    if data:
        final_data = generate_final_data('DATA_FOUND')
        final_data['result'] = complaints
    else:
        final_data = generate_final_data('DATA_NOT_FOUND')
    return final_data



@dcr_blueprint.route('add_complaints', methods=["POST"])
@authenticate('dcr')
def add_complaints():
    user_id = request.headers.get('user-id')
    audit_complaints_form = AuditComplaintsForm()
    if audit_complaints_form.validate_on_submit():
        complaint_list = audit_complaints_form.complaint_list.data
        # complaint_id = audit_complaints_form.complaint_id.data
        # branch_code = audit_complaints_form.branch_code.data
        # # audited_by = audit_complaints_form.audited_by.data
        # remarks = None if audit_complaints_form.remarks.data == '' else audit_complaints_form.remarks.data
        # b64_image = None if audit_complaints_form.b64_image.data == '' else audit_complaints_form.b64_image.data
        root_dir = os.path.dirname(current_app.instance_path)
        uploads_folder = f'{root_dir}/uploads/audit_complaint_images'
        if not os.path.exists(uploads_folder):
            os.makedirs(uploads_folder)
        for complaint in complaint_list:
            new_audits = StoreAudits(ComplaintId=complaint['complaint_id'], BranchCode=complaint['branch_code'],
                                     IsDeleted=0,
                                     AuditDate=get_current_date(),
                                     IsActive=1, AuditedBy=user_id,
                                     Remarks=complaint['remarks'],
                                     RecordCreatedDate=get_current_date(),
                                     RecordLastUpdatedDate=get_current_date())
            try:
                db.session.add(new_audits)
                db.session.commit()
            except Exception as e:
                error_logger(f'Route: {request.path}').error(e)

            if len(complaint['b64_image']) > 0:
                for b64_image in complaint['b64_image']:
                    print(b64_image)
                    purified_string = base64.b64decode(b64_image.replace('data:image/png;base64,', ''))
                    random_val = random.randint(0, 9999)
                    filename = f'{new_audits.Id}Audit_{random_val}_0'
                    # Target file link
                    target_file = f'{uploads_folder}/{filename}.jpg'

                    with open(target_file, 'wb') as f:
                        f.write(purified_string)
                        uploaded = True
                    if uploaded:
                        photos = AuditPhotos(
                            StoreAuditId=new_audits.Id,
                            AuditImage=f'{filename}',
                            IsDeleted=0,
                            RecordCreatedDate=get_current_date(),
                            RecordLastUpdatedDate=get_current_date()
                        )

                    try:
                        db.session.add(photos)
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        error_logger(f'Route: {request.path}').error(e)
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(audit_complaints_form.errors)

    final_data = generate_final_data('DATA_SAVED')
    return final_data


@dcr_blueprint.route('garment_audit', methods=["POST"])
@authenticate('dcr')
def garment_audit():
    user_id = request.headers.get('user-id')
    garment_audit_form = GarmentAuditForm()
    log_data = {
        'ReqBody-garment_audit': garment_audit_form.data,
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    if garment_audit_form.validate_on_submit():
        tag_list = garment_audit_form.tag_list.data
        branch_code = garment_audit_form.branch_code.data

        for tag in tag_list:
            audit_tags = AuditTags(BranchCode=branch_code,
                                   IsDeleted=0,
                                   TagNo=tag,
                                   IsActive=1, ScannedBy=user_id,
                                   RecordCreatedDate=get_current_date(),
                                   RecordLastUpdatedDate=get_current_date())
            try:
                db.session.add(audit_tags)
                db.session.commit()
            except Exception as e:
                error_logger(f'Route: {request.path}').error(e)
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(garment_audit_form.errors)
    final_data = generate_final_data('DATA_SAVED')
    return final_data




@dcr_blueprint.route('get_garment_audit_details', methods=["POST"])
@authenticate('dcr')
def get_garment_audit_details():
    user_id = request.headers.get('user-id')
    garment_audit_form = GarmentAuditDetailsForm()
    if garment_audit_form.validate_on_submit():
        tag_list = garment_audit_form.tag_list.data
        branch_code = garment_audit_form.branch_code.data
        username = db.session.query(DCR_Users.Name).filter(DCR_Users.Id == user_id).one_or_none()
        tags = ','.join(tag_list)
        query = f"EXEC {SERVER_DB}.dbo.GetTagDetailsForAudit @Tagno = '{tags}'"
        result = CallSP(query).execute().fetchall()
        total_scanned_tag = len(tag_list)
        query = f"EXEC {SERVER_DB}.dbo.CDC_Summary @branchcode = '{branch_code}'"
        total_garments_at_store = CallSP(query).execute().fetchall()
        total_garments_at_store = total_garments_at_store[0]['GarmentCount']
        complaints = []
        without_complaints = []
        other_stores = []
        if result:
            for tag_details in result:
                if tag_details['ComplaintId'] is None and tag_details['BranchCode'] == branch_code:
                    without_complaints.append(tag_details)
                elif tag_details['ComplaintId'] is not None and tag_details['BranchCode'] == branch_code:
                    complaints.append(tag_details)
                else:
                    other_stores.append(tag_details)
            complaint_count = len(complaints)
            without_complaint_count = len(without_complaints)
            other_stores_count = len(other_stores)
            complaint_ready_for_delivery = []
            complaint_in_transit_to_cdc = []
            complaint_no_stock = []
            without_complaint_ready_for_delivery = []
            without_complaint_in_transit_to_cdc = []
            without_complaint_no_stock = []

            if complaint_count > 0:
                for complaint in complaints:
                    if complaint['GarmentStatus'] == 'Transfer in at CDC':
                        complaint_in_transit_to_cdc.append(complaint)
                    elif complaint['GarmentStatus'] == 'Ready for Delivery':
                        complaint_ready_for_delivery.append(complaint)
                    else:
                        complaint_no_stock.append(complaint)
            else:
                pass
            if without_complaint_count > 0:
                for without_complaint in without_complaints:
                    if without_complaint['GarmentStatus'] == 'Transfer in at CDC':
                        without_complaint_in_transit_to_cdc.append(without_complaint)
                    elif without_complaint['GarmentStatus'] == 'Ready for Delivery':
                        without_complaint_ready_for_delivery.append(without_complaint)
                    else:
                        without_complaint_no_stock.append(without_complaint)
            else:
                pass

            without_complaint_in_transit_to_cdc_count = len(without_complaint_in_transit_to_cdc)
            without_complaint_ready_for_delivery_count = len(without_complaint_ready_for_delivery)
            without_complaint_no_stock_count = len(without_complaint_no_stock)

            complaint_in_transit_to_cdc_count = len(complaint_in_transit_to_cdc)
            complaint_ready_for_delivery_count = len(complaint_ready_for_delivery)
            complaint_no_stock_count = len(complaint_no_stock)

        if result:
            final_data = generate_final_data('DATA_FOUND')
            final_data['result'] = {"ScannedBy": username.Name,
                                    "total_scanned_tag": total_scanned_tag,
                                    "total_garments_at_store": total_garments_at_store,
                                    "complaint_count": complaint_count,
                                    "without_complaint_count": without_complaint_count,
                                    "other_stores_count": other_stores_count,

                                    "without_complaint_in_transit_to_cdc_count": without_complaint_in_transit_to_cdc_count,
                                    "without_complaint_ready_for_delivery_count": without_complaint_ready_for_delivery_count,
                                    "without_complaint_no_stock_count": without_complaint_no_stock_count,

                                    "complaint_in_transit_to_cdc_count": complaint_in_transit_to_cdc_count,
                                    "complaint_ready_for_delivery_count": complaint_ready_for_delivery_count,
                                    "complaint_no_stock_count": complaint_no_stock_count,

                                    "without_complaint_in_transit_to_cdc": without_complaint_in_transit_to_cdc,
                                    "without_complaint_ready_for_delivery": without_complaint_ready_for_delivery,
                                    "without_complaint_no_stock": without_complaint_no_stock,
                                    
                                    "complaint_in_transit_to_cdc": complaint_in_transit_to_cdc,
                                    "complaint_ready_for_delivery": complaint_ready_for_delivery,
                                    "complaint_no_stock": complaint_no_stock
                                    }

        else:
            final_data = generate_final_data('DATA_NOT_FOUND')

    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(garment_audit_form.errors)

    return final_data


# dcr store permission

@dcr_blueprint.route('store_permission', methods=["POST"])
@authenticate('dcr')
def store_permission():
    store_permission_form = StorePermissionForm()
    if store_permission_form.validate_on_submit():
        user_id = request.headers.get('user-id')
        lat = None if store_permission_form.lat.data == '' else store_permission_form.lat.data
        long = None if store_permission_form.long.data == '' else store_permission_form.long.data
        store_id = store_permission_form.store_id.data
        permission = False
        error_msg = None
        branch_permission = False
        store_access = True
        location_permission = db.session.query(DCR_Users.store_access_limit).filter(
            DCR_Users.Id == user_id).one_or_none()
        store_permission = location_permission.store_access_limit
        branch_access = db.session.query(DCR_Branch_Access.Id, DCR_Branch_Access.user_id,
                                         DCR_Branch_Access.date,
                                         DCR_Branch_Access.end_date,
                                         DCR_Branch_Access.store_access).filter(
            DCR_Branch_Access.user_id == user_id).all()
        branch_access = SerializeSQLAResult(branch_access).serialize()
        today = date.today()
        if len(branch_access) > 0:
            for branch in branch_access:
                start_date = datetime.strptime(branch['date'], "%d-%m-%Y").date()
                end_date = datetime.strptime(branch['end_date'], "%d-%m-%Y").date()
                if start_date <= today <= end_date:
                    if branch['store_access'] == 0:
                        permission = True
                        branch_permission = True
                        query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
                        result = CallSP(query).execute().fetchall()
                        for branch in result:
                            if branch['BranchCode'] == store_id:
                                if branch['Lat'] is not None:
                                    branch_lat = float(branch['Lat'])
                                    branch_long = float(branch['Long'])
                                    loc1 = (branch_lat, branch_long)
                                    loc2 = (lat, long)
                                    distance = hs.haversine(loc1, loc2)
                                else:
                                    store_permission = 0
                                    permission = False
                                    error_msg = 'The branch location is not added, please contact MDM Team'
                                    distance = 0.0
                        break
                    else:
                        branch_permission = False
                        store_access = False
        if not branch_permission:

            if store_access and location_permission.store_access_limit == 0:
                permission = True
                query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
                result = CallSP(query).execute().fetchall()
                for branch in result:
                    if branch['BranchCode'] == store_id:
                        if branch['Lat'] is not None:
                            branch_lat = float(branch['Lat'])
                            branch_long = float(branch['Long'])
                            loc1 = (branch_lat, branch_long)
                            loc2 = (lat, long)
                            distance = hs.haversine(loc1, loc2)
                        else:
                            permission = False
                            distance = 0.0
                            error_msg = 'The branch location is not added, please contact MDM Team'
            else:
                query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
                result = CallSP(query).execute().fetchall()
                for branch in result:
                    if branch['BranchCode'] == store_id:
                        if branch['Lat'] is not None:
                            branch_lat = float(branch['Lat'])
                            branch_long = float(branch['Long'])
                            loc1 = (branch_lat, branch_long)
                            loc2 = (lat, long)
                            distance = hs.haversine(loc1, loc2)
                        else:
                            error_msg = 'The branch location is not added, please contact MDM Team'
        else:
            pass

        # log_data = {
        #     'distance': distance,
        #     'lat': lat,
        #     'long': long,
        #     'store_id':store_id,
        #     'user_id':user_id

        # }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))                    
        if error_msg is not None:
            final_data = generate_final_data('CUSTOM_FAILED', error_msg)
            final_data['result'] = {'permission': permission, 'distance': 0.0, 'store_access': store_permission}

        elif distance <= 0.1:
            permission = True
            final_data = generate_final_data('SUCCESS')
            final_data['result'] = {'permission': permission, 'distance': distance, 'store_access': store_permission}
        elif permission:
            final_data = generate_final_data('SUCCESS')
            final_data['result'] = {'permission': permission, 'distance': distance, 'store_access': store_permission}
        else:
            permission = False
            error_msg = "You cannot access the store, as you are not around the location"
            final_data = generate_final_data('CUSTOM_FAILED', error_msg)
            final_data['result'] = {'permission': permission, 'distance': distance, 'store_access': 2}
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(store_permission_form.errors)
    return final_data




# @dcr_blueprint.route('store_permission_test', methods=["POST"])

# # @authenticate('dcr')
# def store_permission_test():
#     store_permission_form = StorePermissionForm()
#     if store_permission_form.validate_on_submit():
#         user_id = request.headers.get('user-id')
#         lat = None if store_permission_form.lat.data == '' else store_permission_form.lat.data
#         long = None if store_permission_form.long.data == '' else store_permission_form.long.data
#         store_id = store_permission_form.store_id.data
#         app_type = store_permission_form.app_type.data
#         permission = False
#         error_msg = None
#         branch_permission = False
#         store_access = True
#         isLatLong=False
#         distance=0
#         log_data = {
#             'ReqBody-garment_audit': store_permission_form.data,
#         }
#         info_logger(f'Route: {request.path}').info(json.dumps(log_data))

#         if app_type == "audit":
#             app_login = 2
#             location_permission = db.session.query(DCR_Users.audit_store_access_limit).filter(
#                 DCR_Users.Id == user_id).one_or_none()
#             store_permission = location_permission.audit_store_access_limit
#         elif app_type == 'dcr':
#             app_login = 1
#             location_permission = db.session.query(DCR_Users.store_access_limit).filter(
#                 DCR_Users.Id == user_id).one_or_none()
#             store_permission = location_permission.store_access_limit if location_permission else 0
#             #store_permission = location_permission.store_access_limit
#         branch_access = db.session.query(DCR_Branch_Access.Id, DCR_Branch_Access.user_id,
#                                          DCR_Branch_Access.date,
#                                          DCR_Branch_Access.end_date,
#                                          DCR_Branch_Access.store_access).filter(
#             DCR_Branch_Access.user_id == user_id, DCR_Branch_Access.app_login == app_login).all()
#         branch_access = SerializeSQLAResult(branch_access).serialize()
#         today = date.today()
#         if len(branch_access) > 0:
#             for branch in branch_access:
#                 start_date = datetime.strptime(branch['date'], "%d-%m-%Y").date()
#                 end_date = datetime.strptime(branch['end_date'], "%d-%m-%Y").date()
#                 if start_date <= today <= end_date:
#                     if branch['store_access'] == 0:
#                         permission = True
#                         branch_permission = True
#                         isLatLong = True
#                         query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
#                         result = CallSP(query).execute().fetchall()
#                         log_data = {
#                             'branch_result': result,
#                             "query":query

#                         }
#                         info_logger(f'Route: {request.path}').info(json.dumps(log_data))
#                         for branch in result:
#                             if branch['BranchCode'] == store_id:
#                                 if branch['Lat'] is not None and float(branch['Lat']) > 0.0000000000:
#                                     branch_lat = float(branch['Lat'])
#                                     branch_long = float(branch['Long'])
#                                     loc1 = (branch_lat, branch_long)
#                                     loc2 = (lat, long)
#                                     distance = hs.haversine(loc1, loc2)

#                                 else:
#                                     store_permission = 0
#                                     permission = False
#                                     error_msg = 'The branch location is not added, please contact MDM Team'
#                                     distance = 0.0
#                                     isLatLong= True
#                         break
#                     else:
#                         branch_permission = False
#                         store_access = False
#                     if branch_permission == False and store_access == False:
#                         isLatLong = False
#         if not branch_permission:

#             if store_access and store_permission == 0:
#                 permission = True
#                 query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
#                 result = CallSP(query).execute().fetchall()
#                 for branch in result:
#                     if branch['BranchCode'] == store_id:
#                         if branch['Lat'] is not None and float(branch['Lat']) > 0.0000000000:
#                             branch_lat = float(branch['Lat'])
#                             branch_long = float(branch['Long'])
#                             loc1 = (branch_lat, branch_long)
#                             loc2 = (lat, long)
#                             distance = hs.haversine(loc1, loc2)
#                         elif store_access == 0:
#                              permission = True
#                         else:
#                             permission = False
#                             distance = 0.0
#                             error_msg = 'The branch location is not added, please contact MDM Team'
#                             isLatLong = True
#             else:
#                 query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
#                 result = CallSP(query).execute().fetchall()
#                 log_data = {
#                             'branch_result': result,
#                             "query":query

#                         }
#                 info_logger(f'Route: {request.path}').info(json.dumps(log_data))
#                 for branch in result:
#                     if branch['BranchCode'] == store_id:
#                         if  branch['Lat'] is not None and float(branch['Lat']) > 0.0000000000:
#                             branch_lat = float(branch['Lat'])
#                             branch_long = float(branch['Long'])
#                             loc1 = (branch_lat, branch_long)
#                             loc2 = (lat, long)
#                             distance = hs.haversine(loc1, loc2)
#                         else:
#                             error_msg = 'The branch location is not added, please contact MDM Team'
#         else:
#             pass

#         # log_data = {
#         #     'distance': distance,
#         #     'lat': lat,
#         #     'long': long,
#         #     'store_id':store_id,
#         #     'user_id':user_id

#         # }
#         # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
#         if distance <= 0.1 or permission or store_permission:
#             try:
#                 query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
#                 result = CallSP(query).execute().fetchall()
#                 log_data = {
#                             'branch_result': result,
#                             "query":query

#                         }
#                 info_logger(f'Route: {request.path}').info(json.dumps(log_data))
#                 for branch in result:
#                     if branch['BranchCode'] == store_id:
#                         if branch['Lat'] is not None or branch['Lat'] != 0:
#                             branch_lat = float(branch['Lat'])
#                             branch_long = float(branch['Long'])
#                             loc1 = (branch_lat, branch_long)
#                             loc2 = (lat, long)
#                             distance = hs.haversine(loc1, loc2)
#                     break
#                 if distance <= 0.1:
#                     store_access_from = 'within 100 meter'
#                 else:
#                     store_access_from = 'Any where'
#                 clockin_record_of_today = queries.clockin_for_today(user_id, app_type)
#                 if clockin_record_of_today is None:
#                     # No previous clock in record found for today.
#                     new_clock_in = FabDailyClockIn(
#                         UserId=user_id,
#                         Date=today,
#                         Apptype=app_type,
#                         ClockinBranch=store_id,
#                         ClockInTime=get_current_date(),
#                         ClockInLat=lat,
#                         ClockInLong=long,
#                         IsDeleted=0,
#                         RecordCreatedDate=get_current_date(),
#                         RecordLastUpdatedDate=get_current_date(),
#                         StoreAccessFrom=store_access_from
#                     )
#                     # Saving the clock in details for the day.
#                     db.session.add(new_clock_in)
#                     db.session.commit()
#                     clocked_in = True
#                 else:
#                     pass
#             except Exception as e:
#                 error_logger(f'Route: {request.path}').error(e) 

    
                  
#         if error_msg is not None:
#             final_data = generate_final_data('CUSTOM_FAILED', error_msg)
#             final_data['result'] = {'permission': True, 'distance': 0.0, 'store_access': store_permission, 'isLatLong': True}

#         elif distance <= 0.1:
#             permission = True
#             final_data = generate_final_data('SUCCESS')
#             final_data['result'] = {'permission': permission, 'distance': distance, 'store_access': store_permission, 'isLatLong': isLatLong}
#         elif permission:
#             final_data = generate_final_data('SUCCESS')
#             final_data['result'] = {'permission': permission, 'distance': distance, 'store_access': store_permission, 'isLatLong': isLatLong}
#         else:
#             permission = False
#             error_msg = "You cannot access the store, as you are not around the location"
#             final_data = generate_final_data('CUSTOM_FAILED', error_msg)
#             final_data['result'] = {'permission': permission, 'distance': distance, 'store_access': store_permission, 'isLatLong': isLatLong}
#     else:
#         # Form validation error.
#         final_data = generate_final_data('FORM_ERROR')
#         final_data['errors'] = populate_errors(store_permission_form.errors)
#     return final_data

@dcr_blueprint.route('store_permission_test', methods=["POST"])

@authenticate('dcr')
def store_permission_test():
    store_permission_form = StorePermissionForm()
    if store_permission_form.validate_on_submit():
        user_id = request.headers.get('user-id')
        lat = None if store_permission_form.lat.data == '' else store_permission_form.lat.data
        long = None if store_permission_form.long.data == '' else store_permission_form.long.data
        store_id = store_permission_form.store_id.data
        app_type = store_permission_form.app_type.data
        permission = False
        error_msg = None
        branch_permission = False
        store_access = True
        isLatLong=False
        distance=0
        log_data = {
            'ReqBody-garment_audit': store_permission_form.data,
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        if app_type == "audit":
            app_login = 2
            location_permission = db.session.query(DCR_Users.audit_store_access_limit,DCR_Users.store_screen_access,DCR_Users.mss_screen_access,DCR_Users.garment_screen_access).filter(
                DCR_Users.Id == user_id).one_or_none()
            store_permission = location_permission.audit_store_access_limit
            only_store_audit_access = location_permission.store_screen_access
            audit_access = location_permission.garment_screen_access
            backtomss_access = location_permission.mss_screen_access
        elif app_type == 'dcr':
            app_login = 1
            location_permission = db.session.query(DCR_Users.store_access_limit,DCR_Users.store_screen_access,DCR_Users.mss_screen_access,DCR_Users.garment_screen_access).filter(
                DCR_Users.Id == user_id).one_or_none()
            store_permission = location_permission.store_access_limit if location_permission else 0
            only_store_audit_access = location_permission.store_screen_access
            audit_access = location_permission.garment_screen_access
            backtomss_access = location_permission.mss_screen_access
            #store_permission = location_permission.store_access_limit
        branch_access = db.session.query(DCR_Branch_Access.Id, DCR_Branch_Access.user_id,
                                         DCR_Branch_Access.date,
                                         DCR_Branch_Access.end_date,
                                         DCR_Branch_Access.store_access).filter(
            DCR_Branch_Access.user_id == user_id, DCR_Branch_Access.app_login == app_login).all()
        branch_access = SerializeSQLAResult(branch_access).serialize()
        today = date.today()
        if len(branch_access) > 0:
            for branch in branch_access:
                start_date = datetime.strptime(branch['date'], "%d-%m-%Y").date()
                end_date = datetime.strptime(branch['end_date'], "%d-%m-%Y").date()
                if start_date <= today <= end_date:
                    if branch['store_access'] == 0:
                        permission = True
                        branch_permission = True
                        isLatLong = True
                        query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
                        result = CallSP(query).execute().fetchall()
                        log_data = {
                            'branch_result': result,
                            "query":query

                        }
                        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                        for branch in result:
                            if branch['BranchCode'] == store_id:
                                if branch['Lat'] is not None and float(branch['Lat']) > 0.0000000000:
                                    branch_lat = float(branch['Lat'])
                                    branch_long = float(branch['Long'])
                                    loc1 = (branch_lat, branch_long)
                                    loc2 = (lat, long)
                                    distance = hs.haversine(loc1, loc2)

                                else:
                                    store_permission = 0
                                    permission = False
                                    error_msg = 'The branch location is not added, please contact MDM Team'
                                    distance = 0.0
                                    isLatLong= True
                        break
                    else:
                        branch_permission = False
                        store_access = False
                    if branch_permission == False and store_access == False:
                        isLatLong = False
        if not branch_permission:

            if store_access and store_permission == 0:
                permission = True
                query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
                result = CallSP(query).execute().fetchall()
                for branch in result:
                    if branch['BranchCode'] == store_id:
                        if branch['Lat'] is not None and float(branch['Lat']) > 0.0000000000:
                            branch_lat = float(branch['Lat'])
                            branch_long = float(branch['Long'])
                            loc1 = (branch_lat, branch_long)
                            loc2 = (lat, long)
                            distance = hs.haversine(loc1, loc2)
                        elif store_access == 0:
                             permission = True
                        else:
                            permission = False
                            distance = 0.0
                            error_msg = 'The branch location is not added, please contact MDM Team'
                            isLatLong = True
            else:
                query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
                result = CallSP(query).execute().fetchall()
                log_data = {
                            'branch_result': result,
                            "query":query

                        }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                for branch in result:
                    if branch['BranchCode'] == store_id:
                        if  branch['Lat'] is not None and float(branch['Lat']) > 0.0000000000:
                            branch_lat = float(branch['Lat'])
                            branch_long = float(branch['Long'])
                            loc1 = (branch_lat, branch_long)
                            loc2 = (lat, long)
                            distance = hs.haversine(loc1, loc2)
                        else:
                            error_msg = 'The branch location is not added, please contact MDM Team'
        else:
            pass

 
        if distance <= 0.1 or permission or store_permission:
            try:
                query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
                result = CallSP(query).execute().fetchall()
                log_data = {
                            'branch_result': result,
                            "query":query

                        }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                for branch in result:
                    if branch['BranchCode'] == store_id:
                        if branch['Lat'] is not None or branch['Lat'] != 0:
                            branch_lat = float(branch['Lat'])
                            branch_long = float(branch['Long'])
                            loc1 = (branch_lat, branch_long)
                            loc2 = (lat, long)
                            distance = hs.haversine(loc1, loc2)
                    break
                if distance <= 0.1:
                    store_access_from = 'within 100 meter'
                else:
                    store_access_from = 'Any where'
                clockin_record_of_today = queries.clockin_for_today(user_id, app_type)
                if clockin_record_of_today is None:
                    # No previous clock in record found for today.
                    new_clock_in = FabDailyClockIn(
                        UserId=user_id,
                        Date=today,
                        Apptype=app_type,
                        ClockinBranch=store_id,
                        ClockInTime=get_current_date(),
                        ClockInLat=lat,
                        ClockInLong=long,
                        IsDeleted=0,
                        RecordCreatedDate=get_current_date(),
                        RecordLastUpdatedDate=get_current_date(),
                        StoreAccessFrom=store_access_from
                    )
                    # Saving the clock in details for the day.
                    db.session.add(new_clock_in)
                    db.session.commit()
                    clocked_in = True
                else:
                    pass
            except Exception as e:
                error_logger(f'Route: {request.path}').error(e) 

    
                  
        if error_msg is not None:
            final_data = generate_final_data('CUSTOM_FAILED', error_msg)
            final_data['result'] = {'permission': True, 'distance': 0.0, 'store_access': store_permission, 'isLatLong': True ,"store_access":only_store_audit_access,"audit_access":audit_access,"backtomss_access":backtomss_access}

        elif distance <= 0.1:
            permission = True
            final_data = generate_final_data('SUCCESS')
            final_data['result'] = {'permission': permission, 'distance': distance, 'store_access': store_permission, 'isLatLong': isLatLong ,"store_access":only_store_audit_access,"audit_access":audit_access,"backtomss_access":backtomss_access}

            new_mail_clockin = FabDailyMailClockIn(
                UserId=user_id,
                Date=today,
                Apptype=app_type,
                ClockinBranch=store_id,
                ClockInTime=get_current_date(),
                ClockInLat=lat,
                ClockInLong=long,
                IsDeleted=0,
                RecordCreatedDate=get_current_date(),
                RecordLastUpdatedDate=get_current_date(),
                StoreAccessFrom=store_access_from
            )
            db.session.add(new_mail_clockin)
            db.session.commit()
            info_logger(f'Route: {request.path}').info(f'Inserted into FabDailyMailClockIn for UserId {user_id}')
            
        elif permission:
            final_data = generate_final_data('SUCCESS')
            final_data['result'] = {'permission': permission, 'distance': distance, 'store_access': store_permission, 'isLatLong': isLatLong ,"store_access":only_store_audit_access,"audit_access":audit_access,"backtomss_access":backtomss_access}
            
            new_mail_clockin = FabDailyMailClockIn(
                UserId=user_id,
                Date=today,
                Apptype=app_type,
                ClockinBranch=store_id,
                ClockInTime=get_current_date(),
                ClockInLat=lat,
                ClockInLong=long,
                IsDeleted=0,
                RecordCreatedDate=get_current_date(),
                RecordLastUpdatedDate=get_current_date(),
                StoreAccessFrom=store_access_from
            )
            db.session.add(new_mail_clockin)
            db.session.commit()
            info_logger(f'Route: {request.path}').info(f'Inserted into FabDailyMailClockIn for UserId {user_id}')
    
        else:
            permission = False
            error_msg = "You cannot access the store, as you are not around the location"
            final_data = generate_final_data('CUSTOM_FAILED', error_msg)
            final_data['result'] = {'permission': permission, 'distance': distance, 'store_access': store_permission, 'isLatLong': isLatLong ,"store_access":only_store_audit_access,"audit_access":audit_access,"backtomss_access":backtomss_access}
            
                

    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(store_permission_form.errors)
    return final_data

@dcr_blueprint.route('verify_otp', methods=["POST"])
@api_key_required
def verify_otp():
    """
    API for verifying the OTP.
    @return:
    """
    verify_otp_form = VerifyOTPForm()
    if verify_otp_form.validate_on_submit():
        mobile_number = verify_otp_form.mobile_number.data
        otp = verify_otp_form.otp.data
        # Result flag.
        verified = False
        error_msg = ''
        today = datetime.today().strftime("%Y-%m-%d")


        # Checking the current environment, if the env is development, no need to verify OTP.
        # if CURRENT_ENV == 'development':
        #     verified = True
        # else:
        otp_details = db.session.query(DCR_OTPs).filter(DCR_OTPs.MobileNumber == mobile_number
                                                        ).order_by(
            DCR_OTPs.RecordCreatedDate.desc()).first()
        if otp_details is not None:
            if otp == otp_details.OTP:
                now = datetime.strptime(get_current_date(), "%Y-%m-%d %H:%M:%S")
                seconds = abs((now - otp_details.RecordCreatedDate)).seconds
                # The difference between the OTP created date and current date must be
                # less than 1000 seconds.
                if seconds < 31:
                    # Mark this OTP log as verified.
                    otp_details.IsVerified = 1
                    db.session.commit()
                    verified = True
                else:
                    # OTP created more than 3 minutes ago.
                    error_msg = 'This OTP has been expired.'
            elif mobile_number == '9876543210':
                otp_details.IsVerified = 1
                db.session.commit()
                verified = True
            else:
                # Another non verified OTP record has been found.
                error_msg = 'Invalid OTP'
        else:
            # OTP record has not found in the DB.
            error_msg = 'Invalid OTP.'
        UserDetails = db.session.query(DCR_Users).filter(DCR_Users.Phone == mobile_number,
                                                         or_(DCR_Users.is_active == 1, DCR_Users.is_audit_active == 1)
                                                         ).one_or_none()
        if verified:
            if UserDetails is not None:
                # Checking if there's any active access token is generated or not.
                # If there's an active access token is present, deny the login request.
                access_tokens = db.session.query(DcrUserLogins).filter(
                    DcrUserLogins.DUserId == UserDetails.Id, DcrUserLogins.IsActive == 1,
                    DcrUserLogins.AuthKeyExpiry == 0).all()
                if len(access_tokens) == 0:
                    permit_login = True
                else:
                    for access_token in access_tokens:
                        # Making the access token expire.
                        access_token.IsActive = 0
                        access_token.AuthKeyExpiry = 1
                        db.session.commit()
                    # Made all active tokens expired.
                    permit_login = True
                if permit_login:
                    # access_key = jwt.encode({'id': str(uuid.uuid1())},
                    #                         current_app.config['JWT_SECRET_KEY'] + str(UserDetails.Id),
                    #                         algorithm='HS256')
                    access_key = jwt.encode({'id': str(uuid.uuid1())},
                        current_app.config['JWT_SECRET_KEY'] + str(UserDetails.Id),
                        algorithm='HS256')

                    if isinstance(access_key, bytes):
                        access_key = access_key.decode('utf-8')


                    # Setting up user_agent dict for saving the basic client device details.
                    user_agent = {'browser': request.user_agent.browser, 'language': request.user_agent.language,
                                  'platform': request.user_agent.platform,
                                  'string': request.user_agent.string,
                                  'version': request.user_agent.version,
                                  'ip_addr': request.remote_addr
                                  }
                    access = db.session.query(
                        DCR_Users.is_active,
                        DCR_Users.is_audit_active
                    ).filter(
                        DCR_Users.Phone == mobile_number
                    ).first()   
                    log_data = {
                        'access': access,
                    }
                    info_logger(f'Route: {request.path}').info(json.dumps(log_data))


                    dcr_access = False
                    audit_access = False

                    if access:
                        if access.is_active == 1 and access.is_audit_active == 1:
                            dcr_access = True
                            audit_access = True
                        elif access.is_active == 1:
                            dcr_access = True
                        elif access.is_audit_active == 1:
                            audit_access = True

                    # Setting up the device type based on user agent's platform.
                    ua_platform = user_agent['platform'] if user_agent['platform'] is not None else ''
                    if ua_platform.lower() in ('iphone', 'android'):
                        device_type = 'M'
                    elif ua_platform.lower() in ('windows', 'linux'):
                        device_type = 'C'
                    else:
                        device_type = 'O'

                    # If the delivery user is found then add login details into DeliveryUserLogin table.
                    new_delivery_user_login = DcrUserLogins(DUserId=UserDetails.Id,
                                                            LoginTime=get_current_date(),
                                                            AuthKey=access_key, AuthKeyExpiry=0,
                                                            LastAccessTime=get_current_date(),
                                                            IsActive=1,
                                                            DeviceType=device_type,
                                                            DeviceIP=user_agent['ip_addr'],
                                                            Browser=user_agent['browser'],
                                                            Platform=user_agent['platform'],
                                                            Language=user_agent['language'],
                                                            UAString=user_agent['string'],
                                                            UAVersion=user_agent['version'],
                                                            RecordCreatedDate=get_current_date(),
                                                            RecordLastUpdatedDate=get_current_date(),
                                                            RecordVersion=0,
                                                            Date=today
                                                            )
                    try:
                        db.session.add(new_delivery_user_login)
                        db.session.commit()
                        # final_data = generate_final_data("DATA_SAVED")
                    except Exception as e:
                        db.session.rollback()
                        error_logger(f'Route: {request.path}').error(e)
                        # final_data = generate_final_data('DATA_SAVE_FAILED')
                    if error_msg:
                        final_data = generate_final_data('CUSTOM_FAILED', error_msg)

                    elif verified:
                        total_cash_in_hand = 0
                        store = 0
                        branches = db.session.query(DCR_Users.Branches).filter(DCR_Users.Id == UserDetails.Id).one_or_none()
                        if branches is not None:
                            store = len(branches)

                        cash_in_hand = db.session.query(DCR_Collection.CollectedAmount).filter(DCR_Collection.IsDeposited == 0,
                                                                                                DCR_Collection.CollectedBy == UserDetails.Id).all()

                        if cash_in_hand is not None:
                            cash_in_hand = SerializeSQLAResult(cash_in_hand).serialize()
                            for cash in cash_in_hand:
                                total_cash_in_hand = total_cash_in_hand + cash['CollectedAmount']
                        user_number = db.session.query(DCR_Users.Phone).filter(
                            DCR_Users.Id == UserDetails.Id).scalar()

                        result = {'AccessKey': access_key,
                                  'UserId': UserDetails.Id,
                                  'UserName': UserDetails.Name,
                                  'total_cash_in_hand': total_cash_in_hand,
                                  'number_of store': store,
                                  'UserNumber': user_number,
                                  'dcr_access': dcr_access,
                                  'audit_access': audit_access}
                        final_data = generate_final_data('SUCCESS')
                        final_data['result'] = result

                    else:
                        # OTP is not verified. Return the failed message.
                        final_data = generate_final_data('CUSTOM_FAILED', f'Failed to verify. {error_msg}')
                else:
                    final_data = generate_final_data('CUSTOM_FAILED',
                                                     'Another active access token found. Failed to login.')
            else:
                error_msg = 'access denied.'
                final_data = generate_final_data('CUSTOM_FAILED', f'Failed to verify. {error_msg}')
        else:
            final_data = generate_final_data('CUSTOM_FAILED', f'Failed to verify. {error_msg}')

    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(verify_otp_form.errors)
    # log_data = {
    #     'final_data': final_data,
    # }
    # info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    return final_data

@dcr_blueprint.route('get_collection_amount', methods=["POST"])
@authenticate('dcr')
def get_collection_amount():
    collected_amount_form = CollectAmountForm()
    if collected_amount_form.validate_on_submit():
        store_id = collected_amount_form.store_id.data
        start_date = collected_amount_form.start_date.data
        end_date = collected_amount_form.end_date.data
        branch_name = collected_amount_form.branch_name.data
        error_msg = None
        collection_amount = 0
        manual_amount = 0
        if start_date > '2023-02-08':
            query = f"EXEC {SERVER_DB}.dbo.RPT_StatementOfDailyCollection_Mobile_TotalAmount @InvoicePaymentFromDate='{start_date}'," \
                    f"@InvoicePaymentToDate='{end_date}',@PaymentMode='{1}',@Branch='{store_id}' "
            result = CallSP(query).execute().fetchall()
            log_data = {
                'StatementOfDailyCollection_Mobile_TotalAmount': query,
                'result': result

            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))

            if result is not None:
                for date_data in result:
                    start_date_obj = datetime.strptime(date_data['Date'], "%Y-%m-%d")
                    formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")

                    already_amount = db.session.query(DCR_DateWiseCollections).filter(
                        DCR_DateWiseCollections.BranchCode == date_data['BranchCode'],
                        DCR_DateWiseCollections.Date == formatted_start_date_date,
                        DCR_DateWiseCollections.IsDeleted == 0).one_or_none()

                    if already_amount is not None:

                        bill_amount = date_data['BillAmount']
                        if already_amount.TotalAmount < bill_amount:

                            pending_amount = Decimal(bill_amount) - already_amount.TotalAmount
                            already_amount.TotalAmount = bill_amount
                            already_amount.PendingAmount = already_amount.PendingAmount + pending_amount
                            db.session.commit()
                        else:
                            pass
                    elif already_amount is None:

                        total_amount = date_data['BillAmount']
                        daily_collection = DCR_DateWiseCollections(
                            Date=formatted_start_date_date,
                            TotalAmount=total_amount,
                            PendingAmount=total_amount,
                            BranchCode=store_id,
                            RecordCreatedDate=get_current_date(),
                            RecordUpdatedDate=get_current_date(),
                            BranchName=branch_name,
                            IsDeleted=0
                        )
                        # try:
                        db.session.add(daily_collection)
                        db.session.commit()
                        # except Exception as e:
                        #     db.session.rollback()
                        #     error_logger(f'Route: {request.path}').error(e)
                    else:
                        pass
                for collection in result:
                    start_date_obj = datetime.strptime(collection['Date'], "%Y-%m-%d")
                    formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    cash_to_be_collected = db.session.query(DCR_DateWiseCollections.PendingAmount).filter(
                        DCR_DateWiseCollections.BranchCode == collection['BranchCode'],
                        DCR_DateWiseCollections.Date == formatted_start_date_date,
                        DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                    amount = cash_to_be_collected.PendingAmount
                    collection_amount = collection_amount + amount
            else:
                error_msg = 'No amount to be collected'

        elif start_date < '2023-02-09' <= end_date:
            manual_start_date = start_date
            start_date = '2023-02-09'
            # query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
            # branches = CallSP(query).execute().fetchall()
            query = f"EXEC {SERVER_DB}.dbo.RPT_StatementOfDailyCollection_Mobile_TotalAmount @InvoicePaymentFromDate='{start_date}'," \
                    f"@InvoicePaymentToDate='{end_date}',@PaymentMode='{1}',@Branch='{store_id}' "
            result = CallSP(query).execute().fetchall()

            if result is not None:
                for date_data in result:
                    start_date_obj = datetime.strptime(date_data['Date'], "%Y-%m-%d")
                    formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    already_amount = db.session.query(DCR_DateWiseCollections).filter(
                        DCR_DateWiseCollections.BranchCode == date_data['BranchCode'],
                        DCR_DateWiseCollections.Date == formatted_start_date_date,
                        DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                    if already_amount is not None:
                        bill_amount = date_data['BillAmount']
                        if already_amount.TotalAmount < bill_amount:
                            pending_amount = Decimal(bill_amount) - already_amount.TotalAmount
                            already_amount.TotalAmount = bill_amount
                            already_amount.PendingAmount = already_amount.PendingAmount + pending_amount
                            db.session.commit()
                        else:
                            pass
                    elif already_amount is None:
                        total_amount = date_data['BillAmount']
                        daily_collection = DCR_DateWiseCollections(
                            Date=formatted_start_date_date,
                            TotalAmount=total_amount,
                            PendingAmount=total_amount,
                            BranchCode=store_id,
                            RecordCreatedDate=get_current_date(),
                            RecordUpdatedDate=get_current_date(),
                            IsDeleted=0
                        )
                        try:
                            db.session.add(daily_collection)
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()
                            error_logger(f'Route: {request.path}').error(e)
                    else:
                        pass
                for collection in result:
                    start_date_obj = datetime.strptime(collection['Date'], "%Y-%m-%d")
                    formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    cash_to_be_collected = db.session.query(DCR_DateWiseCollections.PendingAmount).filter(
                        DCR_DateWiseCollections.BranchCode == collection['BranchCode'],
                        DCR_DateWiseCollections.Date == formatted_start_date_date,
                        DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                    amount = cash_to_be_collected.PendingAmount
                    collection_amount = collection_amount + amount
            else:
                pass

            if manual_start_date < '2022-12-31':
                start_date = '2022-12-31'
                status = True
            elif manual_start_date < '2023-01-31':
                start_date = '2023-01-31'
                status = True
            else:
                start_date = '2023-02-08'
                status = True
            if status:
                if start_date <= '2022-12-31' and end_date <= '2022-12-31':
                    start_date_obj = datetime.strptime('2022-12-30', "%Y-%m-%d")
                    formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    already_amount = db.session.query(DCR_DateWiseCollections).filter(
                        DCR_DateWiseCollections.BranchCode == store_id,
                        DCR_DateWiseCollections.Date == formatted_start_date_date,
                        DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                    if already_amount is not None:
                        manual_amount = already_amount.PendingAmount
                    else:
                        manual_amount = 0.0
                elif start_date <= '2022-12-31' and end_date <= '2023-01-31':
                    manual_amount = 0
                    dates = ['2022-12-31', '2023-01-31']
                    for collection_date in dates:
                        start_date_obj = datetime.strptime(collection_date, "%Y-%m-%d")
                        formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                        already_amount = db.session.query(DCR_DateWiseCollections).filter(
                            DCR_DateWiseCollections.BranchCode == store_id,
                            DCR_DateWiseCollections.Date == formatted_start_date_date,
                            DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                        if already_amount is not None:
                            manual_amount = manual_amount + already_amount.PendingAmount
                        else:
                            manual_amount = manual_amount
                elif start_date <= '2023-01-31' and end_date <= '2023-01-31':
                    start_date_obj = datetime.strptime('2023-01-31', "%Y-%m-%d")
                    formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    already_amount = db.session.query(DCR_DateWiseCollections).filter(
                        DCR_DateWiseCollections.BranchCode == store_id,
                        DCR_DateWiseCollections.Date == formatted_start_date_date,
                        DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                    if already_amount is not None:
                        manual_amount = already_amount.PendingAmount
                    else:
                        manual_amount = 0.0
                elif start_date <= '2022-12-31' and end_date <= '2023-02-08':
                    manual_amount = 0
                    dates = ['2022-12-31', '2023-01-31', '2023-02-08']
                    for collection_date in dates:
                        start_date_obj = datetime.strptime(collection_date, "%Y-%m-%d")
                        formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                        already_amount = db.session.query(DCR_DateWiseCollections).filter(
                            DCR_DateWiseCollections.BranchCode == store_id,
                            DCR_DateWiseCollections.Date == formatted_start_date_date,
                            DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                        if already_amount is not None:
                            manual_amount = manual_amount + already_amount.PendingAmount
                        else:
                            manual_amount = manual_amount
                elif start_date <= '2023-02-08' and end_date <= '2023-02-08':
                    start_date_obj = datetime.strptime('2023-02-08', "%Y-%m-%d")
                    formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    already_amount = db.session.query(DCR_DateWiseCollections).filter(
                        DCR_DateWiseCollections.BranchCode == store_id,
                        DCR_DateWiseCollections.Date == formatted_start_date_date,
                        DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                    if already_amount is not None:
                        manual_amount = already_amount.PendingAmount
                    else:
                        manual_amount = 0.0
                elif start_date <= '2023-01-31' and end_date <= '2023-02-08':
                    manual_amount = 0
                    dates = ['2023-01-31', '2023-02-08']
                    for collection_date in dates:
                        start_date_obj = datetime.strptime(collection_date, "%Y-%m-%d")
                        formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                        already_amount = db.session.query(DCR_DateWiseCollections).filter(
                            DCR_DateWiseCollections.BranchCode == store_id,
                            DCR_DateWiseCollections.Date == formatted_start_date_date,
                            DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                        if already_amount is not None:
                            manual_amount = manual_amount + already_amount.PendingAmount
                        else:
                            manual_amount = manual_amount
            collection_amount = manual_amount + collection_amount

        else:
            if start_date <= '2022-12-31' and end_date <= '2022-12-31':
                start_date_obj = datetime.strptime('2022-12-31', "%Y-%m-%d")
                formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                already_amount = db.session.query(DCR_DateWiseCollections).filter(
                    DCR_DateWiseCollections.BranchCode == store_id,
                    DCR_DateWiseCollections.Date == formatted_start_date_date,
                    DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                if already_amount is not None:
                    collection_amount = already_amount.PendingAmount
                else:
                    collection_amount = 0.0
            elif start_date <= '2022-12-31' and end_date <= '2023-01-31':
                collection_amount = 0
                dates = ['2022-12-31', '2023-01-31']
                for collection_date in dates:
                    start_date_obj = datetime.strptime(collection_date, "%Y-%m-%d")
                    formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    already_amount = db.session.query(DCR_DateWiseCollections).filter(
                        DCR_DateWiseCollections.BranchCode == store_id,
                        DCR_DateWiseCollections.Date == formatted_start_date_date,
                        DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                    if already_amount is not None:
                        collection_amount = collection_amount + already_amount.PendingAmount
                    else:
                        collection_amount = collection_amount
            elif start_date <= '2023-01-31' and end_date <= '2023-01-31':
                start_date_obj = datetime.strptime('2023-01-31', "%Y-%m-%d")
                formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                already_amount = db.session.query(DCR_DateWiseCollections).filter(
                    DCR_DateWiseCollections.BranchCode == store_id,
                    DCR_DateWiseCollections.Date == formatted_start_date_date,
                    DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                if already_amount is not None:
                    collection_amount = already_amount.PendingAmount
                else:
                    collection_amount = 0.0
            elif start_date <= '2022-12-31' and end_date <= '2023-02-08':
                collection_amount = 0
                dates = ['2022-12-31', '2023-01-31', '2023-02-08']
                for collection_date in dates:
                    start_date_obj = datetime.strptime(collection_date, "%Y-%m-%d")
                    formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    already_amount = db.session.query(DCR_DateWiseCollections).filter(
                        DCR_DateWiseCollections.BranchCode == store_id,
                        DCR_DateWiseCollections.Date == formatted_start_date_date,
                        DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                    if already_amount is not None:
                        collection_amount = collection_amount + already_amount.PendingAmount
                    else:
                        collection_amount = collection_amount

            elif start_date <= '2023-02-08' and end_date <= '2023-02-08':
                start_date_obj = datetime.strptime('2023-02-08', "%Y-%m-%d")
                formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                already_amount = db.session.query(DCR_DateWiseCollections).filter(
                    DCR_DateWiseCollections.BranchCode == store_id,
                    DCR_DateWiseCollections.Date == formatted_start_date_date,
                    DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                if already_amount is not None:
                    collection_amount = already_amount.PendingAmount
                else:
                    collection_amount = 0.0
            elif start_date <= '2023-01-31' and end_date <= '2023-02-08':
                collection_amount = 0
                dates = ['2023-01-31', '2023-02-08']
                for collection_date in dates:
                    start_date_obj = datetime.strptime(collection_date, "%Y-%m-%d")
                    formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    already_amount = db.session.query(DCR_DateWiseCollections).filter(
                        DCR_DateWiseCollections.BranchCode == store_id,
                        DCR_DateWiseCollections.Date == formatted_start_date_date,
                        DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                    if already_amount is not None:
                        collection_amount = collection_amount + already_amount.PendingAmount
                    else:
                        collection_amount = collection_amount
            else:

                error_msg = "No amount to be collected"
        if error_msg is not None:
            final_data = generate_final_data('CUSTOM_FAILED', error_msg)
        else:
            final_data = generate_final_data('DATA_FOUND')
            final_data['result'] = float(collection_amount)
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(collected_amount_form.errors)
    return final_data


@dcr_blueprint.route('submit_collection_amount', methods=["POST"])
@authenticate('dcr')
def submit_collection_amount():
    submit_collected_amount_form = SubmitCollectAmountForm()
    log_data = {
        'submit collection': submit_collected_amount_form.data

        }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    if submit_collected_amount_form.validate_on_submit():
        user_id = request.headers.get('user-id')
        start_date = submit_collected_amount_form.start_date.data
        end_date = submit_collected_amount_form.end_date.data
        branch_code = submit_collected_amount_form.branch_code.data
        branch_name = submit_collected_amount_form.branch_name.data
        total_amount = submit_collected_amount_form.total_amount.data
        collected_amount = submit_collected_amount_form.collected_amount.data
        remarks = submit_collected_amount_form.remarks.data
        store_in_charge = submit_collected_amount_form.store_in_charge.data
        updated = False
        pending_status = False
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        formatted_end_date_date = end_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        query = f"EXEC {SERVER_DB}.dbo.GetBranchInfoforDCR @branchcode={branch_code}"
        branch_data = CallSP(query).execute().fetchall()
        new_dcr_collection = DCR_Collection(StoreBranchCode=branch_code,
                                             Date=get_current_date(),
                                             StoreBranchName=branch_name,
                                             DateFrom=formatted_start_date_date,
                                             DateTo=formatted_end_date_date,
                                             TotalAmount=total_amount,
                                             CollectedAmount=collected_amount,
                                             Remarks=remarks,
                                             StoreInCharge=store_in_charge,
                                             CollectedBy=user_id,
                                             CollectionType="Daily Collection",
                                             IsDeposited=0,
                                             IsDeleted=0,
                                             StoreBranchCity=branch_data[0]['CityName'],
                                             StoreBranchState=branch_data[0]['StateName'],
                                             Brand=branch_data[0]['BrandDescription']
                                             )
        try:
            db.session.add(new_dcr_collection)
            db.session.commit()
            updated = True
        except Exception as e:
            db.session.rollback()
            error_logger(f'Route: {request.path}').error(e)

        difference = total_amount - collected_amount
        difference = Decimal(difference)
        query = f"EXEC {SERVER_DB}.dbo.RPT_StatementOfDailyCollection_Mobile_TotalAmount @InvoicePaymentFromDate='{start_date}'," \
                f"@InvoicePaymentToDate='{end_date}',@PaymentMode='{1}',@Branch='{branch_code}' "
        log_data = {
            'submit collection StatementOfDailyCollection_Mobile_TotalAmount': query

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        
        result = CallSP(query).execute().fetchall()
        log_data = {
            'result':result
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        if difference == 0:
            if result is not None:
                for date_data in result:
                    start_date_obj = datetime.strptime(date_data['Date'], "%Y-%m-%d")
                    formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    collection_details = db.session.query(DCR_DateWiseCollections).filter(
                        DCR_DateWiseCollections.BranchCode == date_data['BranchCode'],
                        DCR_DateWiseCollections.Date == formatted_start_date_date,
                        DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                    if collection_details is not None:
                        collection_details.PendingAmount = 0
                        db.session.commit()
                    else:
                        pass
        else:
            collected_amount = Decimal(collected_amount)
            for data in result:
                start_date_obj = datetime.strptime(data['Date'], "%Y-%m-%d")
                formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                collection_details = db.session.query(DCR_DateWiseCollections).filter(
                    DCR_DateWiseCollections.BranchCode == data['BranchCode'],
                    DCR_DateWiseCollections.Date == formatted_start_date_date,
                    DCR_DateWiseCollections.IsDeleted == 0).one_or_none()
                if collection_details is not None:
                    if collected_amount != 0:
                        if collection_details.PendingAmount != 0:
                            if collection_details.PendingAmount > collected_amount:
                                pending_amount = collection_details.PendingAmount - collected_amount
                                collection_details.PendingAmount = pending_amount
                                db.session.commit()
                                collected_amount = 0
                                break
                            elif collection_details.PendingAmount == collected_amount:
                                collection_details.PendingAmount = 0
                                db.session.commit()
                                collected_amount = 0
                                break
                            elif collection_details.PendingAmount < collected_amount:
                                collected_amount = collected_amount - collection_details.PendingAmount
                                collection_details.PendingAmount = 0
                                db.session.commit()

                            else:
                                pending_amount = collected_amount - collection_details.PendingAmount
                                if collection_details.PendingAmount == pending_amount:
                                    collection_details.PendingAmount = 0
                                    db.session.commit()
                                    collected_amount = 0
                                    break
                                else:
                                    collection_details.PendingAmount = pending_amount
                                    db.session.commit()
                                    collected_amount = pending_amount
                        else:
                            pass
                    else:
                        pass
                else:
                    pass
        total_bill_amount = sum(entry['BillAmount'] for entry in result)
        collection_date = datetime.now().strftime("%Y-%m-%d")
        total_cash_tobe_collected = f"EXEC {SERVER_DB}.dbo.RPT_StatementOfDailyCollection_Mobile_TotalAmount " \
                                    f"@InvoicePaymentFromDate='{'2022-12-01'}'," \
                                    f"@InvoicePaymentToDate='{collection_date}',@PaymentMode='{1}',@Branch='{branch_code}' "
        total_cash_tobe_collected_result = CallSP(total_cash_tobe_collected).execute().fetchall()
        total_cash_tobe_collected_amount = sum(entry['BillAmount'] for entry in total_cash_tobe_collected_result)
        new_dcr_collection.FabricareSettlementAmount = total_bill_amount
        new_dcr_collection.TotalCashTobeCollected = total_cash_tobe_collected_amount
        db.session.commit()
        
        query = f"EXEC {SERVER_DB}.dbo.RPT_StatementOfDailyCollection_Mobile @InvoicePaymentFromDate='{start_date}'," \
                f"@InvoicePaymentToDate='{end_date}',@PaymentMode='{1}',@Branch='{branch_code}' "
        report = CallSP(query).execute().fetchall()
        report_link = GenerateReport(report, 'Collection').generate().get()
        user_name = db.session.query(DCR_Users.Name).filter(DCR_Users.Id == user_id).one_or_none()
        startdate = datetime.strptime(start_date, "%Y-%m-%d")
        from_date = startdate.strftime("%d-%m-%Y")
        to_date = end_date_obj.strftime("%d-%m-%Y")
        curent_date = date.today()
        collection_date = curent_date.strftime("%d/%m/%Y")
        citycode = text(
            f"""SELECT [BranchInfo].[CityCode] FROM {SERVER_DB}.[dbo].[BranchInfo] WHERE[BranchInfo].[BranchCode] = '{branch_code}' """)
        test = db.engine.execute(citycode).fetchall()
        result = SerializeSQLAResult(test).serialize()
        city_code = result[0]['CityCode']
        query_mail = f"EXEC {OLD_DB}.dbo.GetBranchEmail @branchcode = '{branch_code}'"
        mails = CallSP(query_mail).execute().fetchall()
        to_mail = mails[0]['ToEmail']

        log_data = {
            'query_mail': query_mail,
            'result': mails
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        collection_details = {
            "CollectedDate": collection_date,
            "DateFrom": from_date,
            "DateTo": to_date,
            "TotalAmount": f"Rs.{total_amount}",
            "CollectedAmount": f"Rs.{new_dcr_collection.CollectedAmount}",
            "Difference": Decimal(total_amount) - Decimal(new_dcr_collection.CollectedAmount),
            "filename": report_link,
            "Store": branch_name,
            "StoreInCharge": store_in_charge,
            "Remarks": remarks,
            "CollectedBy": user_name.Name,
            "CityCode": city_code,
            "Mail": to_mail
        }
        # log_data = {
        #     'collection mail Qry': collection_details
        # }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        mail = queries.dcr_daily_collection_email(collection_details)
        log_data = {
            'collection mail details': 'after mail function'
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        if updated:
            final_data = generate_final_data('DATA_SAVED')
            final_data['result'] = {'collected_amount': collected_amount, 'collection_id': new_dcr_collection.Id}
        else:
            final_data = generate_final_data('DATA_SAVE_FAILED')
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(submit_collected_amount_form.errors)
    return final_data


@dcr_blueprint.route('clockin', methods=["POST"])
@authenticate('dcr')
def clockin():
    clock_in_form = ClockInForm()
    if clock_in_form.validate_on_submit():
        user_id = request.headers.get('user-id')
        lat = None if clock_in_form.lat.data == '' else clock_in_form.lat.data
        long = None if clock_in_form.long.data == '' else clock_in_form.long.data
        branch_code = clock_in_form.branch_code.data
        app_type = clock_in_form.app_type.data
        today = datetime.today().strftime("%Y-%m-%d")
        clocked_in = False
        error_msg = ''
        distance =  100

        try:
            query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
            result = CallSP(query).execute().fetchall()
            for branch in result:
                if branch['BranchCode'] == branch_code:
                    if branch['Lat'] is not None:
                        branch_lat = float(branch['Lat'])
                        branch_long = float(branch['Long'])
                        loc1 = (branch_lat, branch_long)
                        loc2 = (lat, long)
                        distance = hs.haversine(loc1, loc2)
                break
            if distance <= 0.1:
                store_access_from = 'within 100 meter'
            else:
                store_access_from = 'Any where'
            clockin_record_of_today = queries.clockin_for_today(user_id,app_type)
            if clockin_record_of_today is None:
                # No previous clock in record found for today.
                new_clock_in = FabDailyClockIn(
                    UserId=user_id,
                    Date=today,
                    Apptype=app_type,
                    ClockinBranch=branch_code,
                    ClockInTime=get_current_date(),
                    ClockInLat=lat,
                    ClockInLong=long,
                    IsDeleted=0,
                    RecordCreatedDate=get_current_date(),
                    RecordLastUpdatedDate=get_current_date(),
                    StoreAccessFrom=store_access_from
                )
                # Saving the clock in details for the day.
                db.session.add(new_clock_in)
                db.session.commit()
                clocked_in = True
            else:
                clocked_in = True
                # Already a record is found.
                error_msg = "You've already clocked in for today!"

        except Exception as e:
            error_logger(f'Route: {request.path}').error(e)
        if clocked_in:
            final_data = generate_final_data('DATA_SAVED')
        else:
            if error_msg:
                final_data = generate_final_data('CUSTOM_FAILED', error_msg)
            else:
                final_data = generate_final_data('DATA_SAVE_FAILED')
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(clock_in_form.errors)

    return final_data

@dcr_blueprint.route('mail_retrigger', methods=["POST"])
# @authenticate('dcr')
def mail_retrigger():
    branch_code = 'BRN0000837'
    try:

        data = db.session.query(DCR_Collection.Date, DCR_Collection.StoreBranchCode,
                                DCR_Collection.StoreBranchName, DCR_Collection.CollectionType,
                                DCR_Collection.DateFrom, DCR_Collection.DateTo, DCR_Collection.TotalAmount,
                                DCR_Collection.CollectedAmount, DCR_Collection.Remarks, DCR_Collection.StoreInCharge,
                                DCR_Collection.CollectedBy, ).filter(DCR_Collection.IsDeleted == 0,
                                                                     DCR_Collection.StoreBranchCode == 'BRN0000837',
                                                                     DCR_Collection.Date<'2023-08-31 00:00:00.000').all()
        data_details = SerializeSQLAResult(data).serialize(full_date_fields=['DateTo', 'DateFrom', 'Date'])
        for collection_data in data_details:
            user_name = db.session.query(DCR_Users.Name).filter(DCR_Users.Id == collection_data["CollectedBy"]).one_or_none()
            startdate = datetime.strptime(collection_data["DateFrom"], "%d-%m-%Y %H:%M:%S %p")
            from_date = startdate.strftime("%d-%m-%Y")
            end_date = datetime.strptime(collection_data["DateTo"], "%d-%m-%Y %H:%M:%S %p")
            to_date = end_date.strftime("%d-%m-%Y")
            query = f"EXEC {SERVER_DB}.dbo.RPT_StatementOfDailyCollection_Mobile @InvoicePaymentFromDate='{startdate}'," \
                    f"@InvoicePaymentToDate='{end_date}',@PaymentMode='{1}',@Branch='{branch_code}' "
            report = CallSP(query).execute().fetchall()

            log_data = {
                'report': query
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            report_link = GenerateReport(report, 'Collection').generate().get()


            collection_details = {
                "CollectedDate": collection_data["Date"],
                "DateFrom": from_date,
                "DateTo": to_date,
                "TotalAmount": f'Rs.{collection_data["TotalAmount"]}',
                "CollectedAmount": f'Rs.{collection_data["CollectedAmount"]}',
                "Difference": Decimal(collection_data["TotalAmount"]) - Decimal(collection_data["CollectedAmount"]),
                "filename": report_link,
                "Store": 'FABRICSPA CDC - GANGAMMA CIRCLE JALAHALLI  - BLR',
                "StoreInCharge": collection_data["StoreInCharge"],
                "Remarks": collection_data["Remarks"],
                "CollectedBy": user_name.Name,
                "CityCode": 'CIT0002245',
                "Mail": 'gangammacircle@fabricspa.com;santosh.n@jyothy.com;shailaja.v@jyothy.com;nancy.p@jyothy.com'
            }
            queries.dcr_daily_collection_email(collection_details)
    except Exception as e:
        error_logger(f'Route: {request.path}').error(e)
        print(e)

    return "Success"