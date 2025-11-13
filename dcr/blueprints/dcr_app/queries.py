from dcr.generic.classes import CallSP
from dcr import db
from sqlalchemy import text
from dcr.generic.loggers import error_logger, info_logger
from dcr.settings.project_settings import SERVER_DB, LOCAL_DB, CURRENT_ENV, ALERT_ENGINE_DB
from flask import Blueprint, request, current_app, send_file, redirect
import json
from dcr.settings.project_settings import LOCAL_DB, SERVER_DB
from flask import request
from datetime import datetime
from dcr.modules.models import FabDailyClockIn

def dcr_daily_collection_email(collection_details):
    try:
        log_data = {
            'collection mail B4 Qry': 'B4 mail call'
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        query = f"EXEC {ALERT_ENGINE_DB}..ALERT_PROCESS @ALERT_CODE = 'DCR_DailyCollection_EMAIL',@EMAIL_ID = " \
                f"'{collection_details['Mail']}'" \
                f", @MOBILE_NO = null, @SUBJECT = '{collection_details['Store']} Daily Collection-{collection_details['CollectedDate']}', @DISPATCH_FLAG = 'OFF', @EMAIL_SENDER_ADD = NULL," \
                f"@SMS_SENDER_ADD = NULL, @P1 = '{collection_details['CollectedDate']}', @P2 = '{collection_details['DateFrom']}'," \
                f" @P3 = '{collection_details['DateTo']}'," \
                f"@P4 = '{collection_details['TotalAmount']}', @P5 = '{collection_details['CollectedAmount']}', " \
                f"@P6 = '{collection_details['Difference']}'," \
                f"@P7 = '{collection_details['filename']}', @P8 =  '{collection_details['Store']}'," \
                f"@P9 = '{collection_details['StoreInCharge']}', @P10 = '{collection_details['Remarks']}', " \
                f"@P11 = '{collection_details['CollectedBy']}', @P12 = '{collection_details['CityCode']}', @P13 = NULL," \
                f"@P14 = NULL, @P15 = NULL, @P16 = NULL, @P17 = NULL, @P18 = NULL, @P19 = NULL, @P20 = NULL, " \
                f"@REC_ID = '0'"
        db.engine.execute(text(query).execution_options(autocommit=True))

        log_data = {
            'collection mail After mail qry': query
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    except Exception as ex:
        error_logger(f'Route: {request.path}').error(ex)
        print("Un-able to send mail")
        log_data = {
            'mail Exception': query
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

def dcr_deposit_mail(deposit_details):
    try:
        query = f"EXEC {ALERT_ENGINE_DB}..ALERT_PROCESS @ALERT_CODE = 'DCR_DEPOSIT_EMAIL', " \
                f"@EMAIL_ID = '{deposit_details['ToMail']}'," \
                f"@MOBILE_NO = null ,@SUBJECT = 'Deposit - {deposit_details['depositDate']}',@DISPATCH_FLAG = 'OFF',@EMAIL_SENDER_ADD = NULL, " \
                f"@SMS_SENDER_ADD = NULL," \
                f"@P1 = '{deposit_details['depositDate']}',@P2 = '{deposit_details['TotalAmount']}',@P3 = '{deposit_details['DepositedBy']}', " \
                f"@P4= '{deposit_details['filename']}', " \
                f"@P5= '{deposit_details['ImageName']}'," \
                f"@P6 = '{deposit_details['CityCode']}', @P7 = NULL, @P8 = NULL,@P9 = NULL, @P10 = NULL, @P11 = NULL, @P12 = NULL, @P13 = NULL, " \
                f"@P14 = NULL," \
                f"@P15= NULL,@P16 = NULL, @P17 = NULL,@P18 = NULL, @P19 = NULL , @P20 = NULL,@REC_ID = '0'"
        db.engine.execute(text(query).execution_options(autocommit=True))

        log_data = {
            'deposit mail': query
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    except Exception as ex:
        error_logger(f'Route: {request.path}').error(ex)
        print("Un-able to send mail")

def invoice_collection(start_date, end_date, store_id):
    query = f"EXEC {SERVER_DB}.dbo.RPT_StatementOfDailyCollection_Mobile @InvoicePaymentFromDate='{start_date}'," \
            f"@InvoicePaymentToDate='{end_date}',@PaymentMode='{1}',@Branch='{store_id}' "
    result = CallSP(query).execute().fetchall()
    log_data = {
        'StatementOfDailyCollection_Mobile': query,
        'result': result
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    return result


def date_wise_collection(start_date, end_date, store_id):
    query = f"EXEC {SERVER_DB}.dbo.RPT_StatementOfDailyCollection_Mobile_TotalAmount @InvoicePaymentFromDate='{start_date}'," \
            f"@InvoicePaymentToDate='{end_date}',@PaymentMode='{1}',@Branch='{store_id}' "
    result = CallSP(query).execute().fetchall()
    log_data = {
        'date_wise_collection': query,
        'result': result
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    return result

def clockin_for_today(user_id, app_type):
    """
    Getting the attendance details for today.
    @param user_id: user id.
    @return: FabDailyUserAttendance record.
    """
    today = datetime.today().strftime("%Y-%m-%d")
    clockin_record_of_today = db.session.query(FabDailyClockIn.Date,
                                               FabDailyClockIn.ClockInTime, FabDailyClockIn.ClockInLat,
                                               FabDailyClockIn.ClockInLong,
                                               FabDailyClockIn.ClockOutTime,
                                               FabDailyClockIn.ClockOutLat,
                                               FabDailyClockIn.ClockOutLong).filter(
        FabDailyClockIn.UserId == user_id,FabDailyClockIn.Apptype == app_type,
        FabDailyClockIn.Date == today,
        FabDailyClockIn.IsDeleted == 0).one_or_none()
    return clockin_record_of_today