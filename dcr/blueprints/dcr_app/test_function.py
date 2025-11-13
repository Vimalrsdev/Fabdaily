from dcr.generic.classes import CallSP
from dcr import db
from sqlalchemy import text
from dcr.generic.loggers import error_logger, info_logger
from flask import request
import json
from dcr.settings.project_settings import LOCAL_DB, SERVER_DB
from dcr.modules.models import DCR_DateWiseCollection
from datetime import datetime, timedelta, date
from decimal import Decimal
from dcr.generic.functions import json_input, generate_final_data, populate_errors, generate_hash, \
    get_current_date, get_today


def invoice_wise_collection(result, store_id, branch_name, collection_amount):
    if result is not None:
        for Daily_Collection in result:
            start_date_obj = datetime.strptime(Daily_Collection['Date'], "%d-%m-%Y")
            formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            bill_no = Daily_Collection['BillNo']
            egrn = Daily_Collection['EGRN']
            already_amount = db.session.query(DCR_DateWiseCollection).filter(
                DCR_DateWiseCollection.BranchCode == Daily_Collection['BranchCode'],
                DCR_DateWiseCollection.BillNo == bill_no,
                DCR_DateWiseCollection.IsDeleted == 0).one_or_none()
            if already_amount is not None:
                bill_amount = Daily_Collection['BillAmount']
                if already_amount.TotalAmount < bill_amount:
                    pending_amount = Decimal(bill_amount) - already_amount.TotalAmount
                    already_amount.TotalAmount = bill_amount
                    already_amount.PendingAmount = already_amount.PendingAmount + pending_amount
                    db.session.commit()
                else:
                    pass
            elif already_amount is None:
                total_amount = Daily_Collection['BillAmount']
                daily_collection = DCR_DateWiseCollection(
                    Date=formatted_start_date_date,
                    TotalAmount=total_amount,
                    PendingAmount=total_amount,
                    BranchCode=store_id,
                    RecordCreatedDate=get_current_date(),
                    RecordUpdatedDate=get_current_date(),
                    BranchName=branch_name,
                    EGRN=egrn,
                    IsDeleted=0,
                    BillNo=bill_no
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
            cash_to_be_collected = db.session.query(DCR_DateWiseCollection.PendingAmount).filter(
                DCR_DateWiseCollection.BranchCode == collection['BranchCode'],
                DCR_DateWiseCollection.BillNo == collection['BillNo'],
                DCR_DateWiseCollection.IsDeleted == 0).one_or_none()
            amount = cash_to_be_collected.PendingAmount
            collection_amount = collection_amount + amount
    else:
        error_msg = 'No amount to be collected'
    return collection_amount


def egrn_wise_collection(result, store_id, branch_name, collection_amount):
    if result is not None:
        for Daily_Collection in result:
            start_date_obj = datetime.strptime(Daily_Collection['Date'], "%d-%m-%Y")
            formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            if Daily_Collection['EGRN'] is not None:
                EGRN = Daily_Collection['EGRN']
            else:
                EGRN = Daily_Collection['BillNo']
            already_amount = db.session.query(DCR_DateWiseCollection).filter(
                DCR_DateWiseCollection.BranchCode == Daily_Collection['BranchCode'],
                DCR_DateWiseCollection.EGRN == EGRN,
                DCR_DateWiseCollection.IsDeleted == 0).one_or_none()
            if already_amount is not None:
                bill_amount = Daily_Collection['BillAmount']
                if already_amount.TotalAmount < bill_amount:
                    pending_amount = Decimal(bill_amount) - already_amount.TotalAmount
                    already_amount.TotalAmount = bill_amount
                    already_amount.PendingAmount = already_amount.PendingAmount + pending_amount
                    db.session.commit()
                else:
                    pass
            elif already_amount is None:
                total_amount = Daily_Collection['BillAmount']
                daily_collection = DCR_DateWiseCollection(
                    Date=formatted_start_date_date,
                    TotalAmount=total_amount,
                    PendingAmount=total_amount,
                    BranchCode=store_id,
                    RecordCreatedDate=get_current_date(),
                    RecordUpdatedDate=get_current_date(),
                    BranchName=branch_name,
                    EGRN=EGRN,
                    IsDeleted=0,
                    BillNo=Daily_Collection['BillNo']
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
            if collection['EGRN'] is not None:
                EGRN = collection['EGRN']
            else:
                EGRN = collection['BillNo']
            cash_to_be_collected = db.session.query(DCR_DateWiseCollection.PendingAmount).filter(
                DCR_DateWiseCollection.BranchCode == collection['BranchCode'],
                DCR_DateWiseCollection.EGRN == EGRN,
                DCR_DateWiseCollection.IsDeleted == 0).one_or_none()
            amount = cash_to_be_collected.PendingAmount
            collection_amount = collection_amount + amount
    else:
        error_msg = 'No amount to be collected'

    return collection_amount


def date_wise_collection(result, store_id, branch_name, collection_amount):
    if result is not None:
        for date_data in result:
            start_date_obj = datetime.strptime(date_data['Date'], "%Y-%m-%d")
            formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")

            already_amount = db.session.query(DCR_DateWiseCollection).filter(
                DCR_DateWiseCollection.BranchCode == date_data['BranchCode'],
                DCR_DateWiseCollection.Date == formatted_start_date_date,
                DCR_DateWiseCollection.IsDeleted == 0).one_or_none()

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
                daily_collection = DCR_DateWiseCollection(
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
            cash_to_be_collected = db.session.query(DCR_DateWiseCollection.PendingAmount).filter(
                DCR_DateWiseCollection.BranchCode == collection['BranchCode'],
                DCR_DateWiseCollection.Date == formatted_start_date_date,
                DCR_DateWiseCollection.IsDeleted == 0).one_or_none()
            amount = cash_to_be_collected.PendingAmount
            collection_amount = collection_amount + amount
    else:
        pass
    return collection_amount


def manual_collection(manual_start_date, end_date, store_id, branch_name, manual_amount):
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
            already_amount = db.session.query(DCR_DateWiseCollection).filter(
                DCR_DateWiseCollection.BranchCode == store_id,
                DCR_DateWiseCollection.Date == formatted_start_date_date,
                DCR_DateWiseCollection.IsDeleted == 0).one_or_none()
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
                already_amount = db.session.query(DCR_DateWiseCollection).filter(
                    DCR_DateWiseCollection.BranchCode == store_id,
                    DCR_DateWiseCollection.Date == formatted_start_date_date,
                    DCR_DateWiseCollection.IsDeleted == 0).one_or_none()
                if already_amount is not None:
                    manual_amount = manual_amount + already_amount.PendingAmount
                else:
                    manual_amount = manual_amount
        elif start_date <= '2023-01-31' and end_date <= '2023-01-31':
            start_date_obj = datetime.strptime('2023-01-31', "%Y-%m-%d")
            formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            already_amount = db.session.query(DCR_DateWiseCollection).filter(
                DCR_DateWiseCollection.BranchCode == store_id,
                DCR_DateWiseCollection.Date == formatted_start_date_date,
                DCR_DateWiseCollection.IsDeleted == 0).one_or_none()
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
                already_amount = db.session.query(DCR_DateWiseCollection).filter(
                    DCR_DateWiseCollection.BranchCode == store_id,
                    DCR_DateWiseCollection.Date == formatted_start_date_date,
                    DCR_DateWiseCollection.IsDeleted == 0).one_or_none()
                if already_amount is not None:
                    manual_amount = manual_amount + already_amount.PendingAmount
                else:
                    manual_amount = manual_amount
        elif start_date <= '2023-02-08' and end_date <= '2023-02-08':
            start_date_obj = datetime.strptime('2023-02-08', "%Y-%m-%d")
            formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            already_amount = db.session.query(DCR_DateWiseCollection).filter(
                DCR_DateWiseCollection.BranchCode == store_id,
                DCR_DateWiseCollection.Date == formatted_start_date_date,
                DCR_DateWiseCollection.IsDeleted == 0).one_or_none()
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
                already_amount = db.session.query(DCR_DateWiseCollection).filter(
                    DCR_DateWiseCollection.BranchCode == store_id,
                    DCR_DateWiseCollection.Date == formatted_start_date_date,
                    DCR_DateWiseCollection.IsDeleted == 0).one_or_none()
                if already_amount is not None:
                    manual_amount = manual_amount + already_amount.PendingAmount
                else:
                    manual_amount = manual_amount

    return manual_amount
