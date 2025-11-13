from flask import Blueprint, request, current_app, send_file, redirect, send_from_directory
import json
from datetime import datetime, timedelta, date
from sqlalchemy import func, or_, case, cast, String, and_, text, literal, extract, desc, Date, distinct
import jwt
import uuid
import base64
import os
import random
from dcr import db
import haversine as hs
from dcr.middlewares.auth_guard import api_key_required, authenticate
from dcr.generic.functions import json_input, generate_final_data, populate_errors, generate_hash, \
    get_current_date, get_today, send_sms, get_greeting_text
from dcr.settings.project_settings import LOCAL_DB, SERVER_DB, CURRENT_ENV, PAYMENT_LINK_API_KEY, OLD_DB, channel_id, \
    sale_request_url, sale_request_status_url, CRM
from dcr.generic.classes import SerializeSQLAResult, CallSP, TravelDistanceCalculator, GenerateReport,SerializeSQLAResult_
from decimal import Decimal
from collections import Counter
from dcr.generic.loggers import error_logger, info_logger
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
from collections import defaultdict
from dcr.blueprints.audit_app import audit_mail
from dcr.blueprints.audit_app import common
from dcr.modules.models import DCR_Users, Audit_Complaints, Audit_Complaints_Branches, StoreAudits, \
    AuditPhotos, AuditAttachements, AuditGarmentCount, AuditTags,SavedTags,DCR_User_Branches, FabDailyClockIn, FabDailyMailClockIn

from .forms import GetComplaintsForm, AuditComplaintsForm, GarmentAuditForm, \
    GarmentAuditDetailsForm, TagDetailsForm, GarmentPreviousDetailsForm, ComplaintHistoryForm, \
    AuditUpdatesForm, AuditSummaryReportForm, AuditDetailedReportForm, GarmentAuditReportForm, StoreAuditReportForm,\
    StockDetailForm,ScannedTagsForm,SavedTagForm,GetTagForm,GarmentAuditReportFormMss
from mimetypes import guess_extension, guess_type

audit_blueprint = Blueprint("audit", __name__, url_prefix='/audit', template_folder='templates',
                            static_folder='static')


@audit_blueprint.route('audit_screen_access', methods=["GET"])
@authenticate('audit')
def audit_screen_access():
    user_id = request.headers.get('user-id')
    screen_access = db.session.query(DCR_Users.garment_screen_access, DCR_Users.store_screen_access,
                                     DCR_Users.mss_screen_access
                                     ).filter(
        DCR_Users.Id == user_id, DCR_Users.is_audit_active == 1).one_or_none()
    if screen_access is not None:
        final_data = generate_final_data('DATA_FOUND')
        final_data['result'] = {'garment_screen_access': screen_access.garment_screen_access,
                                'store_screen_access': screen_access.store_screen_access,
                                'mss_screen_access': screen_access.mss_screen_access}
    else:
        final_data = generate_final_data('DATA_NOT_FOUND')
    return final_data


@audit_blueprint.route('get_garment_audit_details', methods=["POST"])
@authenticate('audit')
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


@audit_blueprint.route('/get_audit_image/<photo_file>', methods=["GET"])
# @api_key_required
def get_audit_image(photo_file):
    """
    API for getting Audit Complaint images based on image name
    """

    root_dir = os.path.dirname(current_app.instance_path)
    log_data = {
        'root_dir': root_dir

    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    # Loading the data from the DB.
    image_data = None
    try:
        # Getting the image data from the DB.
        image_data = db.session.query(AuditPhotos.AuditImage).filter(
            AuditPhotos.AuditImage == photo_file, AuditPhotos.IsDeleted == 0).one_or_none()
    except Exception as e:
        error_logger(f'Route: {request.path}').error(e)

    if image_data:
        # Here a image data is found. So return the image file.
        target_file = f'{root_dir}/uploads/audit_complaint_images/{photo_file}.jpg'
        log_data = {
            'root_dir': target_file

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        return send_file(target_file, mimetype='image/jpg')
    else:
        # No file found for that particular image.
        final_data = generate_final_data('FILE_NOT_FOUND')

        return final_data
 

def db_result_to_dict(result):
    """
    Method for converting sql Queryset to dictionary & change date format of date values
    """
    return [
        {column: value.strftime("%d-%m-%Y") if isinstance(value, date) else value for column, value in row.items()}
        for row in result]


@audit_blueprint.route('/get_attachment/<file>', methods=["GET"])
# @authenticate('audit')
def get_attachment(file):
    """
    API for getting Delivery user images based on image name
    """

    root_dir = os.path.dirname(current_app.instance_path)
    log_data = {
        'root_dir': root_dir
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    # Loading the data from the DB.
    attached_file = None
    try:
        # Getting the image data from the DB.
        attached_file = db.session.query(AuditAttachements.AuditAttachement).filter(
            AuditAttachements.AuditAttachement == file, AuditAttachements.IsDeleted == 0).one_or_none()
    except Exception as e:
        error_logger(f'Route: {request.path}').error(e)

    if attached_file:
        # Here a attached file data is found. So return the file.
        target_file = f'{root_dir}/uploads/audit_attachments/{file}'
        log_data = {
            'root_dir': target_file
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        return send_file(target_file, as_attachment=True)
    else:
        # No file found for that particular image.
        final_data = generate_final_data('FILE_NOT_FOUND')

        return final_data


@audit_blueprint.route('audit_summary_report', methods=["POST"])
@authenticate('audit')
def audit_summary_report():
    user_id = request.headers.get('user-id')
    audit_summary_report_form = AuditSummaryReportForm()
    if audit_summary_report_form.validate_on_submit():
        audit_summary_list = audit_summary_report_form.audit_summary_list.data
        data = 'summary-screen.html'
        subject = 'Audit Summary Report'
        report = ''
        audit_update_mail = audit_mail.audit_mail(data, audit_summary_list, subject, report)
        if audit_update_mail:
            final_data = generate_final_data('SUCCESS')
        else:
            final_data = generate_final_data('DATA_NOT_FOUND')
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(audit_summary_report_form.errors)
    return final_data


@audit_blueprint.route('audit_detailed_report', methods=["POST"])
@authenticate('audit')
def audit_detailed_report():
    user_id = request.headers.get('user-id')
    audit_detailed_report_form = AuditDetailedReportForm()
    if audit_detailed_report_form.validate_on_submit():
        audit_detailed_list = audit_detailed_report_form.audit_detailed_list.data
        data = 'Detailed-screen.html'
        subject = 'Audit Detailed Report'
        report = ''
        audit_update_mail = audit_mail.audit_mail(data, audit_detailed_list, subject,report)
        if audit_update_mail:
            final_data = generate_final_data('SUCCESS')
        else:
            final_data = generate_final_data('DATA_NOT_FOUND')
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(audit_detailed_report_form.errors)
    return final_data


@audit_blueprint.route('save_scanned_tags', methods=['POST'])
@authenticate('audit')
def save_scanned_tags():
    scanned_tag_form = SavedTagForm()
    if scanned_tag_form.validate_on_submit():
        log_data = {
            'StartTime': scanned_tag_form.data
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        user_id = request.headers.get('user-id')
        tag_list = scanned_tag_form.tag_list.data
        branch_code = scanned_tag_form.branch_code.data
        is_mss = scanned_tag_form.is_mss.data
        today_date = date.today()

        try:
            db.session.query(SavedTags).filter(
                and_(
                    SavedTags.ScannedBy == user_id,
                    cast(SavedTags.RecordCreatedDate, Date) <= today_date,
                    SavedTags.BranchCode == branch_code
                )
            ).delete(synchronize_session=False)
            # db.session.commit()
        except Exception as e:
            error_logger(f'Route: {request.path}').error(e)
            print(f"Error: {e}")
            db.session.rollback()
        # Extract TagNo values from the query result
        existing_tags = db.session.query(SavedTags.TagNo).filter(
            SavedTags.ScannedBy == user_id, cast(SavedTags.RecordCreatedDate, Date) == today_date,
            SavedTags.BranchCode == branch_code).all()

        for tag in tag_list:
            existing_tags = [tag[0] for tag in existing_tags]

            if tag['tag_no'] not in existing_tags:
                saved_tags = SavedTags(
                    BranchCode=branch_code,
                    TagNo=tag['tag_no'],
                    ScannedBy=user_id,
                    RecordCreatedDate=get_current_date(),
                    RecordLastUpdatedDate=get_current_date(),
                    IsMSS=is_mss,
                    EntryType=tag['entry_type']
                )
                db.session.add(saved_tags)
                db.session.commit()

        final_data = generate_final_data('DATA_SAVED')
        log_data = {
            'ReqBodyresult': final_data
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(scanned_tag_form.errors)

    return final_data

@audit_blueprint.route('get_saved_tags', methods=['POST'])
@authenticate('audit')
def get_saved_tags():
    """
    Api for getting the temporarily scanned tags, based on branch code, user id and date.
    """
    user_id = request.headers.get('user-id')
    get_tag_form = GetTagForm()
    if get_tag_form.validate_on_submit():
        branch_code = get_tag_form.branch_code.data
        is_mss = get_tag_form.is_mss.data
        today_date = date.today()
        result = db.session.query(distinct(SavedTags.TagNo), SavedTags.EntryType, SavedTags.BranchCode).filter(
            SavedTags.ScannedBy == user_id, SavedTags.BranchCode == branch_code,
            SavedTags.IsMSS == is_mss, cast(SavedTags.RecordCreatedDate, Date) == today_date).all()
        get_tags = [{"TagNo": tag[0], "EntryType": tag[1], "BranchCode": tag[2]} for tag in result]
        if result:
            final_data = generate_final_data('DATA_FOUND')
            final_data['result'] = get_tags
        else:
            final_data = generate_final_data('DATA_NOT_FOUND')
            final_data['result'] = []
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(get_tag_form.errors)

    return final_data


@audit_blueprint.route('delete_saved_tags', methods=['POST'])
@authenticate('audit')
def delete_saved_tags():
    """
    Api for deleting the temporarily scanned tags, based on branch code, user id and date.
    """
    user_id = request.headers.get('user-id')
    get_tag_form = GetTagForm()
    if get_tag_form.validate_on_submit():
        branch_code = get_tag_form.branch_code.data
        is_mss = get_tag_form.is_mss.data
        today_date = date.today()
        try:
            db.session.query(SavedTags).filter(
                and_(SavedTags.ScannedBy == user_id, cast(SavedTags.RecordCreatedDate, Date) == today_date,
                     SavedTags.BranchCode == branch_code)).delete(synchronize_session=False)

            db.session.commit()
            final_data = generate_final_data('DATA_DELETED')
        except Exception as e:
            error_logger(f'Route: {request.path}').error(e)

            # db.session.rollback()
            final_data = generate_final_data('DATA_DELETE_FAILED')
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(get_tag_form.errors)

    return final_data


#     # AUDIT PHASE 3 -- 19-JUN-2024-------
# @audit_blueprint.route('stock_details', methods=["POST"])
# @authenticate('audit')
# def stock_details():
#     stock_detail_form = StockDetailForm()
#     if stock_detail_form.validate_on_submit():
#         start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#         log_data = {
#             'StartTime': stock_detail_form.data
#         }
#         info_logger(f'Route: {request.path}').info(json.dumps(log_data))
#         user_id = request.headers.get('user-id')
#         branch_code = stock_detail_form.branch_code.data
#         today_date = date.today()
#         # total_tags_scanned = len(tag_list)
#         # query = f"EXEC {SERVER_DB}.dbo.CDC_Summary @branchcode = '{branch_code}'"
#         # total_garments_at_store = CallSP(query).execute().fetchall()
#         # total_garments_at_store = total_garments_at_store[0]['GarmentCount']

#         scanned_tags = """SELECT COUNT(TagNo) as scannedtag from AuditTags WHERE Date =:today_date and 
#         BranchCode=:branch_code and ScannedBy=:user_id and IsNoStock=:IsNoStock and IsValidTag=:IsValidTag"""
#         result = db.session.execute(scanned_tags,
#                                     {'today_date': today_date, 'branch_code': branch_code, 'user_id': user_id,
#                                      'IsNoStock': 0, 'IsValidTag': 1})
#         scanned_tag_count = result.scalar()

#         # total_tag_query = f"EXEC {SERVER_DB}.dbo.GetBranchTagDetailsForAudit'{branch_code}'"
#         # total_tag_at_store = CallSP(total_tag_query).execute().fetchall()
#         # total_garments_at_store = len(total_tag_at_store)
#         # result = db.engine.execute(text(scanned_tags), {'today_date': today_date})

#         total_garments_at_store = 0
#         try:
#             total_tag_query = f"EXEC {OLD_DB}.dbo.USP_GarmentAtStore @branchcode='{branch_code}'"
#             result = CallSP(total_tag_query).execute().fetchone()
#             db.session.commit()

#             total_garments_at_store = result['']

#         except Exception as ex:
#             print(ex)

#         log_data = {
#             'Log-test': scanned_tags,
#             'total_tag_query': total_tag_query,
#             'result': result
#         }
#         info_logger(f'Route: {request.path}').info(json.dumps(log_data))

#         if total_garments_at_store:
#             final_data = generate_final_data('DATA_FOUND')
#             final_data['result'] = {
#                 "TotalTagsScanned": scanned_tag_count,
#                 "TotalGarmentCount": total_garments_at_store
#             }
#         else:
#             if total_garments_at_store == 0:
#                 final_data = generate_final_data('DATA_FOUND')
#                 # final_data['errors'] = populate_errors('No data Exists in the selected branch')
#                 final_data['result'] =\
#                     {"TotalTagsScanned": 0,
#                 "TotalGarmentCount": total_garments_at_store}
#             else:
#                 final_data = generate_final_data('DATA_NOT_FOUND')

#     else:
#         # Form validation error.
#         final_data = generate_final_data('FORM_ERROR')
#         final_data['errors'] = populate_errors(stock_detail_form.errors)

#     end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#     log_data = {
#         'EndTime': end_time
#     }
#     info_logger(f'Route: {request.path}').info(json.dumps(log_data))
#     return final_data

@audit_blueprint.route('stock_details', methods=["POST"])
@authenticate('audit')
def stock_details():
    stock_detail_form = StockDetailForm()
    if stock_detail_form.validate_on_submit():
        start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_data = {
            'StartTime': stock_detail_form.data
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        user_id = request.headers.get('user-id')
        branch_code = stock_detail_form.branch_code.data
        today_date = date.today()
        # total_tags_scanned = len(tag_list)
        # query = f"EXEC {SERVER_DB}.dbo.CDC_Summary @branchcode = '{branch_code}'"
        # total_garments_at_store = CallSP(query).execute().fetchall()
        # total_garments_at_store = total_garments_at_store[0]['GarmentCount']

        scanned_tags = """SELECT COUNT(TagNo) as scannedtag from AuditTags WHERE Date =:today_date and 
        BranchCode=:branch_code and ScannedBy=:user_id and IsNoStock=:IsNoStock and IsValidTag=:IsValidTag"""
        result = db.session.execute(text(scanned_tags),
                                    {'today_date': today_date, 'branch_code': branch_code, 'user_id': user_id,
                                     'IsNoStock': 0, 'IsValidTag': 1})
        scanned_tag_count = result.scalar()

        # total_tag_query = f"EXEC {SERVER_DB}.dbo.GetBranchTagDetailsForAudit'{branch_code}'"
        # total_tag_at_store = CallSP(total_tag_query).execute().fetchall()
        # total_garments_at_store = len(total_tag_at_store)
        # result = db.engine.execute(text(scanned_tags), {'today_date': today_date})

        total_garments_at_store = 0
        try:
            total_tag_query = f"EXEC {OLD_DB}.dbo.USP_GarmentAtStore @branchcode='{branch_code}',@AuditedBy='{user_id}'"
            result = CallSP(total_tag_query).execute().fetchone()
            db.session.commit()

            total_garments_at_store = result['']

        except Exception as ex:
            print(ex)

        log_data = {
            'Log-test': scanned_tags,
            'total_tag_query': total_tag_query,
            'result': result
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        if total_garments_at_store:
            final_data = generate_final_data('DATA_FOUND')
            final_data['result'] = {
                "TotalTagsScanned": scanned_tag_count,
                "TotalGarmentCount": total_garments_at_store
            }
        else:
            if total_garments_at_store == 0:
                final_data = generate_final_data('NO_BRANCH_DATA')
                # final_data['errors'] = populate_errors('No data Exists in the selected branch')
                final_data['result'] =\
                    {"TotalTagsScanned": 0,
                "TotalGarmentCount": total_garments_at_store}
            else:
                final_data = generate_final_data('DATA_NOT_FOUND')

    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(stock_detail_form.errors)

    end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_data = {
        'EndTime': end_time
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    return final_data



@audit_blueprint.route('add_complaints', methods=["POST"])
@authenticate('audit') 
def add_complaints():
    user_id = request.headers.get('user-id')
    audit_complaints_form = AuditComplaintsForm()
    if audit_complaints_form.validate_on_submit():

        log_data = {
            'audit_complaints_form': audit_complaints_form.data
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        
        complaint_list = audit_complaints_form.complaint_list.data
        branch = complaint_list[0]['branch_code']
        branch_details = f"EXEC {SERVER_DB}.dbo.GetBranchInfoforDCR @branchcode = {branch}"
        branch_details = CallSP(branch_details).execute().fetchone()

        branch_name=branch_details['BranchName']
        log_data = {
                "branch_query": branch_details ,
                "branch_name":branch_name,

            }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        root_dir = os.path.dirname(current_app.instance_path)
        uploads_folder = f'{root_dir}/uploads/audit_complaint_images'
        if not os.path.exists(uploads_folder):
            os.makedirs(uploads_folder)
        file_uploads_folder = f'{root_dir}/uploads/audit_attachments'
        if not os.path.exists(file_uploads_folder):
            os.makedirs(file_uploads_folder)
        query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
        result = CallSP(query).execute().fetchall()
        for complaint in complaint_list:
            lat1 = complaint.get('lat')
            lat1 = float(lat1)
            # lat1 = 19.1212321476
           
            long1 = complaint.get('long')
            long1 = float(long1)
            # long1 = 72.9166174868

            log_data = {
                "lat": lat1,
                "long": long1,
                "result":result
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            distance = 0
            in_location =0
            branch_data = next((b for b in result if b['BranchCode'] == branch), None)
            if branch_data['BranchCode'] == branch:
                if branch_data is not None:
                    branch_lat = float(branch_data['Lat'])

                    branch_long = float(branch_data['Long'])

                    loc1 = (branch_lat, branch_long)
                    loc2 = (lat1, long1)
                    distance = hs.haversine(loc1, loc2)
                    if distance <= 0.1:
                        in_location = 1
                    else:
                        in_location = 0
                    
                     
                    log_data = {
                                "loc1":loc1,
                                "long1":long1,
                                "branch_lat ":branch_lat ,
                                "branch_long ":branch_long ,
                                "distance ":distance,
                                "in_location":in_location
                                }
                    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                               
            
            new_audits = StoreAudits(ComplaintId=complaint['complaint_id'], BranchCode=complaint['branch_code'],
                                     IsDeleted=0,
                                     AuditDate=date.today(),
                                     IsActive=1, AuditedBy=user_id,
                                     Remarks=complaint['remarks'],
                                     RecordCreatedDate=get_current_date(),
                                     RecordLastUpdatedDate=get_current_date(),
                                     BranchName=branch_details['BranchName'],
                                     BranchCity=branch_details['CityName'],
                                     BranchState=branch_details['StateName'],
                                     IsYesNo=complaint['yes_or_no'],
                                     lat=complaint['lat'],
                                     long=complaint['long'],
                                     InLocation=in_location)

            try:
                db.session.add(new_audits)
                db.session.commit()
            except Exception as e:
                error_logger(f'Route: {request.path}').error(e)
            width = 719
            height = 1280
            if len(complaint['b64_image']) > 0:
                for b64_image in complaint['b64_image']:
                    file_type = guess_extension(guess_type(b64_image)[0])
                    file_type = 'jpeg' if file_type == '.jpg' else 'png'
                    purified_string = base64.b64decode(b64_image.replace(f'data:image/{file_type};base64,', ''))
                    random_val = random.randint(0, 9999)
                    filename = f'{new_audits.Id}Audit_{random_val}_0'
                    # Target file link
                    target_file = f'{uploads_folder}/{filename}.jpg'

                    with open(target_file, 'wb') as f:
                        f.write(purified_string)
                        uploaded = True
                    with Image.open(target_file) as image:
                        image = image.resize((width, height), Image.ANTIALIAS)
                        image.save(target_file)
                    now = datetime.now()
                    dt_string = now.strftime("%d/%m/%Y %I:%M:%S %p")
                    im = Image.new('RGBA', (2000, 120), (255, 255, 255, 255))
                    draw = ImageDraw.Draw(im)
                    font = ImageFont.truetype("arial.ttf", 40)
                    draw.text((0, 0), dt_string, (0, 0, 0), font=font)
                    image = Image.open(target_file)

                    width, height = image.size
                    watermark_image = image.copy()
                    watermark_image.paste(im, (0, height - 80))
                    watermark_image.save(target_file)
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
            if complaint.get('file'):
                for file in complaint['file']:
                    data = base64.b64decode(file['base64'])
                    random_val = random.randint(0, 9999)
                    filename = f'{datetime.now().strftime("%d-%m-%Y_%I-%M-%S_%p")}Audit_compalint{random_val}_0'
                    target_file = f'{file_uploads_folder}/{filename}.{file["type"]}'

                    with open(target_file, 'wb') as f:
                        f.write(data)
                    file_name = f'{filename}.{file["type"]}'
                    new_file = AuditAttachements(
                        StoreAuditId=new_audits.Id,
                        AuditAttachement=file_name,
                        IsDeleted=0,
                        RecordCreatedDate=get_current_date(),
                        RecordLastUpdatedDate=get_current_date()
                    )
                    db.session.add(new_file)
                    db.session.commit()
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(audit_complaints_form.errors)

    final_data = generate_final_data('DATA_SAVED')
    return final_data

@audit_blueprint.route('audit_updates_report', methods=["POST"])
@authenticate('audit')
def audit_updates_report():
    user_id = request.headers.get('user-id')
    audit_updates_form = AuditUpdatesForm()
    if audit_updates_form.validate_on_submit():
        log_data = {
            'audit_updates_report': audit_updates_form.data
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        audit_updates_list = audit_updates_form.audit_updates_list.data
        is_mss = audit_updates_list[0]['is_mss']
        store_name = audit_updates_list[0]['branch_name']
        branch_code = audit_updates_list[0]['branch_code']
        is_history = audit_updates_list[0]['is_history']
        if is_mss == 1:
            subject = f'Back to MSS-Audited tags submitted - {store_name}'
            data = 'Audit-updates_mss.html'
        else:
            subject = f'Audited tags submitted - {store_name}'
            data = 'Audit-updates.html'

        # subject = 'Audit Updates Report'
        report = ''
        auditor_name = db.session.query(DCR_Users.Name, DCR_Users.email).filter(DCR_Users.Id == user_id).one_or_none()
        auditor_mail = auditor_name.email
        # mails = f'{auditor_mail};sukanta.kishor@jyothy.com;magesh.r@jyothy.com;vidhya.r@jyothy.com'
        mails = f'{auditor_mail}'
        audit_update_mail = audit_mail.audit_mail(data, audit_updates_list, subject, report, mails, branch_code, cc_mail=None, is_history=is_history)
        
        #audit_update_mail = audit_mail.audit_mail(data, audit_updates_list, subject, report, mails, branch_code)
        if audit_update_mail:
            final_data = generate_final_data('SUCCESS')
        else:
            final_data = generate_final_data('DATA_NOT_FOUND')
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(audit_updates_form.errors)
    return final_data

@audit_blueprint.route('garment_audit', methods=["POST"])
@authenticate('audit')
def garment_audit():
    user_id = request.headers.get('user-id')
    garment_audit_form = GarmentAuditForm()
    log_data = {
        'ReqBody-garment_audit': garment_audit_form.data,
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    if garment_audit_form.validate_on_submit():
        tag_list = garment_audit_form.tag_list.data
        scanned_tag = len(tag_list)
        # print(scanned_tag)
        branch_code = garment_audit_form.branch_code.data
        is_mss = garment_audit_form.is_mss.data
        scan_id = garment_audit_form.scan_id.data if garment_audit_form.scan_id.data != 0 else None
        lat = None if garment_audit_form.lat.data == '' else garment_audit_form.lat.data
        long = None if garment_audit_form.long.data == '' else garment_audit_form.long.data
        entry_type = 'manual'
        # sp to get branch information based on branch code
        branch_details = f"EXEC {SERVER_DB}.dbo.GetBranchInfoforDCR @branchcode = {branch_code}"
        branch_details = CallSP(branch_details).execute().fetchone()
        tags_list = []
        result_list = []
        Garment_Count = None
        query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
        result = CallSP(query).execute().fetchall()
        i=0
        for branch in result:
            if branch['BranchCode'] == branch_code:
                if branch['Lat'] is not None:
                    branch_lat = float(branch['Lat'])
                    branch_long = float(branch['Long'])
                    loc1 = (branch_lat, branch_long)
                    loc2 = (lat, long)
                    distance = hs.haversine(loc1, loc2)
                else:
                    permission = db.session.query(DCR_Users.audit_store_access_limit).filter(
                        DCR_Users.Id == user_id).one_or_none()
                    if permission.audit_store_access_limit == 1:
                        distance = 0
                    else:
                        distance = 1
                break
        if distance <= 0.1:
            in_location = 1
        else:
            in_location = 0
        # return {"1":1, "in_location":in_location}
        today_date = date.today()
        tags_sp = []
        
        for data_dict in tag_list:
            # Iterate through each key-value pair in the dictionary
            for key, value in data_dict.items():
                # Check if the value contains a single quote
                if "'" in value:
                    # Replace single quote with two single quotes
                    data_dict[key] = value.replace("'", "''")
        
        # log_data = {
        #             'tag_list': tag_list
        #         }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        for tag in tag_list:
            # tags_list.append(tag['tag_no'])
            tags_sp.append(tag['tag_no'])
            try:
                qry = "INSERT INTO Temp_AllScannedTags(tag_no, entry_type,ScannedBy,BranchCode) VALUES (:tag_no, :entry_type,:ScannedBy,:BranchCode)"
                db.session.execute(text(qry), {'tag_no': tag['tag_no'], 'entry_type': tag['entry_type'], 'ScannedBy': user_id,
                                         'BranchCode': branch_code})
                db.session.commit()
            except Exception as e:
                # Handle the exception
                db.session.rollback()
        tags = ','.join(tags_sp)
        sp_results_scanned_tags = None
        if scan_id is None:
            try:
                scan_id_qry = """SELECT ISNULL((SELECT MAX(ScanId) + 1 FROM AuditTags WHERE CONVERT(DATE, Date) = CONVERT(DATE, GETDATE()) and IsMss=:is_mss and BranchCode=:branch_code AND AuditedBy=:user_id), 1)"""
                result = db.session.execute(text(scan_id_qry),
                                            {'branch_code': branch_code, 'user_id': user_id, 'is_mss': is_mss})
                scan_id = result.scalar()
            except Exception as ex:
                print(ex)
            sp_status=''
            value = 0
            try:

                
                if is_mss:

                    total_tag_query= "" 
                    value = 0
                    # f"EXEC {OLD_DB}.dbo.UpdateAuditTagMSS @branchcode='{branch_code}', @ScannedBy=0,@IsNoStock=1,@IsScanned=0, @InLocation={in_location}," \
                    #                   f"@RecordCreatedDate='{today_date}',@Date='{today_date}',@AuditedBy='{user_id}',@ScanId='{scan_id}',@IsMSS=1,@Action='ADD-ALL-TAGS'"

                else:

                    total_tag_query = f"EXEC {OLD_DB}.dbo.UpdateAuditTag @branchcode='{branch_code}', @ScannedBy=0,@IsNoStock=1,@IsScanned=0, @InLocation={in_location}," \
                                       f"@RecordCreatedDate='{today_date}',@Date='{today_date}',@AuditedBy='{user_id}',@ScanId='{scan_id}',@IsMSS=0,@Action='ADD-ALL-TAGS'"

                    result = CallSP(total_tag_query).execute().fetchone()
                    # print(result)
                    db.session.commit()
                    value = 0
                    # value = float(result['GarmentCount'])
                    value = result['GarmentCount']
                    log_data = {
                        'ADD-ALL-TAGS-sp-result': total_tag_query
                    }
                    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                sp_status ='ALL-TAGS'


                if is_mss:
                    
                    scanned_tag_query = f"EXEC {OLD_DB}.dbo.UpdateAuditTagMSS @branchcode='{branch_code}', @ScannedBy='{user_id}',@ScanId='{scan_id}',@IsNoStock=0,@RecordCreatedDate='{today_date}',@Date='{today_date}',@Action='SCANNED-TAGS',@IsMSS=1,@InLocation={in_location},@IsScanned=1,@AuditedBy='{user_id}',@EntryType='{entry_type}',@Tagno = '{tags}'"
                    i+=1
                else:
                   
                    scanned_tag_query = f"EXEC {OLD_DB}.dbo.UpdateAuditTag @branchcode='{branch_code}', @ScannedBy='{user_id}',@ScanId='{scan_id}',@IsNoStock=0,@RecordCreatedDate='{today_date}',@Date='{today_date}',@Action='SCANNED-TAGS',@IsMSS=0,@InLocation={in_location},@IsScanned=1,@AuditedBy='{user_id}',@EntryType='{entry_type}',@Tagno = '{tags}'"


                log_data = {
                    'SCANNED-TAG-sp-result': scanned_tag_query,
                    'count':i
                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                
                sp_results_scanned_tags = CallSP(scanned_tag_query).execute().fetchall()
                sp_status ='SCANNED-TAGS'
                log_data = {
                    'SCANNED-TAG-sp-result': scanned_tag_query
                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                result_dict = sp_results_scanned_tags[0]
                result_list = [result_dict['TagNo']]
                db.session.commit()
                
                total_garments_at_store = result
                sp_status ='SCANNED-TAGS'

            except Exception as ex:
                print(ex)
            # list_of_values = [(value1, value2), (value3, value4), ...]  # Replace with your list of values
        else:
            previous_invalid_tags = []
            sp_status =''
            try:
                invalid_tags_qry = """select  TagNo as tag_no, EntryType as entry_type FROM AuditTags WHERE AuditedBy=:user_id AND ScanId = :scan_id AND  CONVERT(DATE, Date) = CONVERT(DATE, GETDATE())  AND BranchCode=:branch_code and IsScanned=1 AND IsValidTag =0 """
                result = db.session.execute(text(invalid_tags_qry),
                                            {'branch_code': branch_code, 'user_id': user_id,
                                             'scan_id': scan_id}).fetchall()
                previous_invalid_tags = SerializeSQLAResult(result).serialize()
            except Exception as ex:
                print(ex)

            try:
                # removing duplicate entries from tag list.
                # previous_invalid_tags variable contains previous invalid tags
                invalid_tags_duplicates_removed = list(filter(lambda d: d not in previous_invalid_tags, tag_list))
                comma_separated_tags_for_sp = ','.join(str(d[next(iter(d))]) for d in invalid_tags_duplicates_removed)
                value = 0
                if is_mss:
                    total_tag_query=""

                else:
                    total_tag_query = f"EXEC {OLD_DB}.dbo.UpdateAuditTagWithScanId @branchcode='{branch_code}', @ScannedBy=0,@IsNoStock=1,@IsScanned=0, @InLocation={in_location}," \
                                       f"@RecordCreatedDate='{today_date}',@Date='{today_date}',@AuditedBy='{user_id}',@ScanId='{scan_id}',@IsMSS={1 if is_mss else 0},@Action='ADD-ALL-TAGS'"
                    # print(total_tag_query)
                    result = CallSP(total_tag_query).execute().fetchone()
                    # print('sp result', result)
                    db.session.commit()
                    # value = 0
                    # value = float(result['GarmentCount'])
                    value = result['GarmentCount']
                    log_data = {
                        'ALL-TAG-sp-result': total_tag_query
                    }
                    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                sp_status = 'ALL-TAGS'

                if is_mss:
                    scanned_tag_query = f"EXEC {OLD_DB}.dbo.UpdateAuditTagMSSWithScanId @branchcode='{branch_code}', @ScannedBy='{user_id}',@ScanId='{scan_id}',@IsNoStock=0,@RecordCreatedDate='{today_date}',@Date='{today_date}',@Action='SCANNED-TAGS',@IsMSS={1 if is_mss else 0},@InLocation={in_location},@IsScanned=1,@AuditedBy='{user_id}',@EntryType='{entry_type}',@Tagno = '{comma_separated_tags_for_sp}'"
                
                else:
                    scanned_tag_query = f"EXEC {OLD_DB}.dbo.UpdateAuditTagWithScanId @branchcode='{branch_code}', @ScannedBy='{user_id}',@ScanId='{scan_id}',@IsNoStock=0,@RecordCreatedDate='{today_date}',@Date='{today_date}',@Action='SCANNED-TAGS',@IsMSS={1 if is_mss else 0},@InLocation={in_location},@IsScanned=1,@AuditedBy='{user_id}',@EntryType='{entry_type}',@Tagno = '{comma_separated_tags_for_sp}'"
                # print(scanned_tag_query)
                sp_results_scanned_tags = CallSP(scanned_tag_query).execute().fetchall()
                sp_status = 'SCANNED-TAGS'
                log_data = {
                    'SCANNED-TAG-SP-sp-result': scanned_tag_query
                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                result_dict = sp_results_scanned_tags[0]
                result_list = [result_dict['TagNo']]
                db.session.commit()
                

            except Exception as ex:
                print(ex)
        log_data = {
            'sp_status': sp_status
            }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        if (sp_status == 'ALL-TAGS'):
            try:
                qry = "DELETE FROM AuditTags WHERE ScanId =:scan_id and AuditedBy =:ScannedBy and BranchCode =:BranchCode and Date= :today_date and IsMSS = :is_mss"
                db.session.execute(text(qry), {'scan_id': scan_id, 'is_mss': is_mss, 'ScannedBy': user_id,
                                         'today_date': today_date,
                                         'BranchCode': branch_code})

                db.session.commit()
                valid_tags = []
                invalid_tags = []
                invalid_tag_count = 0
                ValidTagsCount = 0
                scan_id =0
                already_exist = []
                if value == 'Manual' or value == 'Scanned':
                    valeue=0
                else:
                    value=value
                final_data = generate_final_data('FAILED')
                final_data['result'] = {'ValidTags': valid_tags, 'InValidTags': invalid_tags,
                                        'DuplicateTags': already_exist,
                                        'Garment_Count': value,
                                        'ScanId': scan_id,
                                        'ValidTagsCount': ValidTagsCount, 'InvalidTagsCount': invalid_tag_count,
                                        'TotalTagsScanned': scanned_tag}
                sp_status_flag = 'FAILED'
            except Exception as e:
                print(ex)
        elif (sp_status == 'SCANNED-TAGS'):
            sp_status_flag = 'SUCCESS'

            valid_tags = []
            invalid_tags = []
            ValidTagsCount = 0
            invalid_tag_count = 0
            ValidTagsCount = 0
            if sp_status_flag == 'SUCCESS':
                for tags_item in tag_list:
                    exist_flag = 0
                    if sp_results_scanned_tags is not None:
                        for sp_result in sp_results_scanned_tags:
                            if tags_item['tag_no'] == sp_result['TagNo']:
                                valid_tags.append(tags_item['tag_no'])
                                ValidTagsCount += 1
                                exist_flag = 1
                                pass
                    if exist_flag == 0:
                        invalid_tags.append(tags_item['tag_no'])
                        invalid_tag_count += 1

                invalid_tags = invalid_tags
                valid_tags = valid_tags

                invalid_tag_count = invalid_tag_count
                already_exist = []
                modified_invalid_tags = []

                for i in range(len(invalid_tags)):
                    modified_invalid = invalid_tags[i].replace("''", "'")
                    modified_invalid_tags.append(modified_invalid)



                final_data = generate_final_data('DATA_SAVED')
                if value == 'Mannual' or value == 'Scanned':
                    valeue=0
                else:
                    value=value

                final_data['result'] = {'ValidTags': valid_tags, 'InValidTags': modified_invalid_tags,
                                        'DuplicateTags': already_exist,
                                        'Garment_Count': value,
                                        'ScanId': scan_id,
                                        'ValidTagsCount': ValidTagsCount, 'InvalidTagsCount': invalid_tag_count,
                                        'TotalTagsScanned': scanned_tag}
                # else:
                #     final_data = generate_final_data('DATA_SAVED')
                #     final_data['result'] = {'ValidTags': filter_tag, 'InValidTags': tags_list,
                #                             'Garment_Count': total_garments_at_store}
            else:
                valid_tags = []
                invalid_tags = []
                invalid_tag_count = 0
                ValidTagsCount = 0
                scan_id = 0
                already_exist = []
                # if value == 'Mannual' or value == 'Scanned':
                #     valeue = 0
                # else:
                #     value=value
                final_data = generate_final_data('FAILED')
                final_data['result'] = {'ValidTags': valid_tags, 'InValidTags': invalid_tags,
                                        'DuplicateTags': already_exist,
                                        'Garment_Count': value,
                                        'ScanId': scan_id,
                                        'mss_tags':"mss_tags",
                                        'ValidTagsCount': ValidTagsCount, 'InvalidTagsCount': invalid_tag_count,
                                        'TotalTagsScanned': scanned_tag}
                sp_status_flag = 'FAILED'
            log_data = {
                'ReqBodyresult': final_data
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(garment_audit_form.errors)
    return final_data






@audit_blueprint.route('garment_audit_report', methods=["POST"])
@authenticate('audit') 
def garment_audit_report():
    user_id = request.headers.get('user-id')
    garment_audit_report_form = GarmentAuditReportForm()
    log_data = {
        'Req body': garment_audit_report_form.data,
        "nostock_dtls_list":"nostock_dtls_list"
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    if garment_audit_report_form.validate_on_submit():
        audit_date = None if garment_audit_report_form.audit_date.data == '' else garment_audit_report_form.audit_date.data
        # is_mss = garment_audit_report_form.is_mss.data
        is_mss = 0
        branch_code = garment_audit_report_form.branch_code.data
        branch_name = garment_audit_report_form.branch_name.data
        is_history = garment_audit_report_form.is_history.data

        in_location = garment_audit_report_form.in_location.data
        # tags = [] if garment_audit_report_form.tags.data is None else garment_audit_report_form.tags.data
        # auditor_name = garment_audit_report_form.auditor_name.data
        audit_date_obj = datetime.strptime(audit_date, "%d-%m-%Y")
        formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        no_stock_tags = garment_audit_report_form.tag_list.data
        noStock_count_data = garment_audit_report_form.noStock_coun.data

        auditor_name = db.session.query(DCR_Users.Name, DCR_Users.email).filter(DCR_Users.Id == user_id).one_or_none()
        total_with_complaint_count = 0
        total_without_complaint_count = 0
        total_other_stores_count = 0
        total_no_stock_count = 0
        stock = 0
        back_to_mss_count = 0
        other_store_mss_count = 0

        garment_audit_data = [{'status': status, 'details': [], 'count': {}} for status in
                              ['In Transits to CDC', 'Resorted', 'Work Order Created ', 'In Transits to mss',
                               'Pending Transfer Out From CDC', 'Invoiced & Delivered', 'Transfer in at CDC',
                               'Pending for QC Verification', 'Transfer in at mss', 'QC Approved', 'QC Rejected ',
                               'Moved Back to Mss', 'Invoiced & Pending Delivery',
                               'Under clearance of Invoice settlement',
                               'Missing', 'Damaged', 'Disputed Garment']]
        with_complaint_count = defaultdict(int)
        without_complaint_count = defaultdict(int)
        other_stores_count = defaultdict(int)
        no_stock_count = defaultdict(int)
        back_to_mss_value = defaultdict(int)
        other_store_mss_value = defaultdict(int)
        # garment_audit_data_details = db.session.query(AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus,
        #                                               AuditTags.ComplaintDepartment, AuditTags.ComplaintDate,
        #                                               AuditTags.GarmentBranchCode, AuditTags.GarmentBranchName,
        #                                               AuditTags.OrderStatus,
        #                                               AuditTags.EntryType, AuditTags.ComplaintId,
        #                                               AuditTags.GarmentStatus,
        #                                               case([(AuditTags.IsNoStock == 1, literal('Yes'))],
        #                                                    else_=literal('No')).label('NoStock'), AuditTags.IsValidTag
        #                                               ).filter(AuditTags.ScannedBy == user_id,
        #                                                        AuditTags.Date == formatted_audit_date,
        #                                                        AuditTags.IsMSS == is_mss,
        #                                                        AuditTags.BranchCode == branch_code).all()

        latest_scan_id = db.session.query(func.max(AuditTags.ScanId)).filter(
            AuditTags.AuditedBy == user_id,AuditTags.IsMSS==0,
            AuditTags.Date == formatted_audit_date, AuditTags.BranchCode == branch_code
        ).scalar()

        garment_audit_data_details = db.session.query(AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus,
                                                      AuditTags.ComplaintDepartment, AuditTags.ComplaintDate,
                                                      AuditTags.GarmentBranchCode, AuditTags.GarmentBranchName,
                                                      AuditTags.OrderStatus,
                                                      AuditTags.EntryType, AuditTags.ComplaintId,
                                                      AuditTags.GarmentAmount, AuditTags.GarmentName,
                                                      AuditTags.OrderType, AuditTags.CustomerName, AuditTags.CustomerId,
                                                      AuditTags.GarmentStatus, AuditTags.isScannedInMss,
                                                      AuditTags.IsMSS, AuditTags.ScanId, AuditTags.IsNoStock,
                                                      case([(AuditTags.IsNoStock == 1, literal('Yes'))],
                                                           else_=literal('No')).label('NoStock'),
                                                      AuditTags.Execptionflag.label('24hrs & Current day')
                                                      ).filter(AuditTags.ScannedBy == user_id,
                                                               AuditTags.Date == formatted_audit_date,
                                                               AuditTags.IsMSS == is_mss,
                                                               AuditTags.BranchCode == branch_code,
                                                               AuditTags.IsNoStock == 0,
                                                               AuditTags.IsDeleted == 0,
                                                               AuditTags.IsValidTag == 1,

                                                               AuditTags.ScanId == latest_scan_id).all()
        garment_audit_data_details = SerializeSQLAResult(garment_audit_data_details).serialize(
            full_date_fields=['ComplaintDate'])

        log_data = {

        "nostock_dtls_list":"nostock_dtls_list1",
        "ScanId_grmnt_rpt11": latest_scan_id,
        "Branch:" :branch_code,
        "Date:":formatted_audit_date,
        "user_id:":user_id

       
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))


        for garment in garment_audit_data_details:

            if garment['IsMSS'] == 1 or garment['isScannedInMss'] == 1 and garment['GarmentBranchCode'] != branch_code:
                garment["category"] = 'Back to Mss Other Store'
            elif garment['IsMSS'] == 1 or garment['isScannedInMss'] == 1:
                garment["category"] = 'Back to Mss'

            elif garment['GarmentBranchCode'] != branch_code:
                garment["category"] = 'Others Stores'
            elif garment['ComplaintStatus'] == None:
                garment["category"] = 'Without Complaint'
            elif garment['ComplaintStatus'] != None:
                garment["category"] = 'With Complaint'
            else:
                pass


        extra_query = db.session.query(
            AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus,
            AuditTags.ComplaintDepartment, AuditTags.ComplaintDate,
            AuditTags.GarmentBranchCode, AuditTags.GarmentBranchName,
            AuditTags.OrderStatus, AuditTags.EntryType, AuditTags.ComplaintId, AuditTags.ScanId, AuditTags.IsNoStock,
            AuditTags.GarmentAmount, AuditTags.GarmentName, AuditTags.OrderType, AuditTags.CustomerName,
            AuditTags.CustomerId,
            AuditTags.GarmentStatus, AuditTags.Execptionflag.label('24hrs & Current day')
        ).filter(
            AuditTags.Date == formatted_audit_date, AuditTags.Execptionflag == 0, AuditTags.IsDeleted == 0,
            AuditTags.IsValidTag == 1,
            AuditTags.IsMSS == 0,
            AuditTags.isScannedInMss == 0,
            # AuditTags.IsScanned == 1,
            AuditTags.BranchCode == branch_code,
            AuditTags.IsNoStock == 1, AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id,
            AuditTags.GarmentStatus.in_(
                ['In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC', 'Invoiced & Delivered'])
        ).all()
        # print(extra_query)

        # Serialize the additional data
        extra_data_details = SerializeSQLAResult(extra_query).serialize(full_date_fields=['ComplaintDate'])
        for nostock in extra_data_details:
            nostock["category"] = 'No stock'

        garment_dtls = [{key: val for key, val in d.items() if key not in ['IsValidTag']} for d in
                        garment_audit_data_details]
        # Combine the two data sets
        combined_data_details = garment_dtls + extra_data_details

        # combined_data_details = garment_audit_data_details + extra_data_details
        # print(garment_dtls)
        # print(extra_data_details)
        for datadtls in combined_data_details:
            # if datadtls['ScanId'] > 1 and datadtls['IsNoStock'] == 0 and (
            #         datadtls['IsMSS'] == 1 or datadtls['isScannedInMss'] == 1):
            #     datadtls['scan status'] = 'Already scanned'
            if datadtls['24hrs & Current day'] == 1 and datadtls['GarmentStatus'] == 'In Transits to CDC':
                datadtls['24hrs & Current day'] = 'Transferred-in within 24hrs'
            elif datadtls['24hrs & Current day'] == 1 and datadtls['GarmentStatus'] == 'Pending Transfer Out From CDC':
                datadtls['24hrs & Current day'] = 'Tag generated Today'
            else:
                datadtls['24hrs & Current day'] = ' '

        # garment_audit_data_details = [{key: val for key, val in d.items() if key not in ['IsValidTag','IsMSS','isScannedInMss']} for d in
        #                 garment_audit_data_details]
        excluded_data_details = [{key: val for key, val in d.items() if
                                  key not in ['ScanId', 'IsNoStock', 'NoStock', 'IsMSS', 'isScannedInMss']}
                                 for d in combined_data_details]

        log_data = {

        "excluded_data_details":excluded_data_details,
        'combined_data_details':combined_data_details

       
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

  

        if is_mss:
            audit_type = "Back to MSS"
        else:
            audit_type = "Garment Audit"

        # report = GenerateReport(combined_data_details, audit_type).generate().get()
        report = GenerateReport(excluded_data_details, audit_type).generate().get()

        # nostock_dtls = db.session.query(func.count(AuditTags.GarmentStatus).label('Count'),
        #                                 AuditTags.GarmentStatus
        #                                 ).filter(AuditTags.Date == formatted_audit_date,
        #                                          AuditTags.IsMSS == is_mss,
        #                                          AuditTags.BranchCode == branch_code,
        #                                          AuditTags.IsNoStock == 1).group_by(AuditTags.GarmentStatus).all()

        # nostock_dtls = db.session.query(
        #     func.count(AuditTags.GarmentStatus).label('Count'),
        #     AuditTags.GarmentStatus
        # ).filter(
        #     # AuditTags.Date == formatted_audit_date,
        #     AuditTags.Date == date.today(),
        #     AuditTags.IsMSS == is_mss, AuditTags.Execptionflag == 1, AuditTags.IsDeleted == 0,
        #     AuditTags.isScannedInMss == 0,
        #     AuditTags.IsValidTag == 1,
        #     AuditTags.BranchCode == branch_code, AuditTags.GarmentBranchCode == branch_code,
        #     AuditTags.IsNoStock == 1, AuditTags.AuditedBy == user_id, AuditTags.ScanId == latest_scan_id,
        #     AuditTags.GarmentStatus.in_(
        #         ['In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC', 'Invoiced & Delivered'])
        # ).group_by(AuditTags.GarmentStatus).all()

        nostock_dtls = db.session.query(AuditTags.TagNo, AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                AuditTags.InLocation, AuditTags.GarmentStatus
                                                ).filter(AuditTags.BranchCode == branch_code,
                                                         AuditTags.IsNoStock == 1,
                                                         AuditTags.IsMSS == is_mss,
                                                         AuditTags.IsValidTag == 1, AuditTags.IsDeleted == 0,
                                                         AuditTags.Date == date.today(),
                                                         AuditTags.ScanId == latest_scan_id,
                                                         AuditTags.Execptionflag == 0,
                                                         AuditTags.isScannedInMss == 0,
                                                         AuditTags.AuditedBy == user_id, AuditTags.GarmentStatus.in_(
                ['In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC',
                 'Invoiced & Delivered'])).all()

        nostock_dtls_list = SerializeSQLAResult(nostock_dtls).serialize()

        log_data = {
            'nostock_dtls_list': garment_audit_data_details
       
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        for garment in garment_audit_data_details:
            # print(garment)
            found = False
            for garment_audit in garment_audit_data:
                if garment_audit['status'] == garment['GarmentStatus']:
                    if garment['GarmentBranchCode'] == branch_code and garment['GarmentStatus'] in [
                        'In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC',
                        'Invoiced & Delivered'] and garment['24hrs & Current day'] == 0:
                        stock = stock + 1
                    else:
                        pass
                    if garment['GarmentBranchCode'] != branch_code and (
                            garment['IsMSS'] == 1 or garment['isScannedInMss'] == 1):
                        other_store_mss_value[garment_audit['status']] += 1
                        other_store_mss_count = other_store_mss_count + 1

                    elif garment['IsMSS'] == 1 or garment['isScannedInMss'] == 1:
                        garment['Back to mss'] = True
                        back_to_mss_count = back_to_mss_count + 1
                        back_to_mss_value[garment_audit['status']] += 1

                    elif garment['GarmentBranchCode'] != branch_code:
                        # print(branch_code)
                        garment['other_stores'] = True
                        total_other_stores_count = total_other_stores_count + 1
                        other_stores_count[garment_audit['status']] += 1
                    elif garment['ComplaintStatus'] is None:
                        garment['without_complaint'] = True
                        total_without_complaint_count = total_without_complaint_count + 1
                        # print(total_without_complaint_count)
                        without_complaint_count[garment_audit['status']] += 1

                    elif garment['ComplaintStatus'] != None and garment['NoStock'] in (0, 'No') :
                        garment['with_complaint'] = True
                        total_with_complaint_count = total_with_complaint_count + 1
                        with_complaint_count[garment_audit['status']] += 1

                    else:
                        pass
                        # garment['no_stock'] = True
                        # #print(garment['no_stock'])
                        # total_no_stock_count = total_no_stock_count + 1
                        # no_stock_count[garment_audit['status']] += 1

                    garment['no_stock'] = True

                    # total_no_stock_count = db.session.query(AuditGarmentCount).filter(
                    #     AuditGarmentCount.Date == formatted_audit_date,
                    #     AuditGarmentCount.BranchCode == branch_code, AuditGarmentCount.AuditedBy == user_id,
                    #     AuditGarmentCount.ScanId == latest_scan_id).one_or_none()

                    total_no_stock_count = db.session.query(func.count(AuditTags.TagNo)).filter(
                        and_(
                            AuditTags.Date == formatted_audit_date,
                            AuditTags.IsNoStock == 1,
                            AuditTags.IsMSS == is_mss,
                            AuditTags.Execptionflag == 0,
                            AuditTags.BranchCode == branch_code,
                            AuditTags.IsValidTag == 1,
                            AuditTags.AuditedBy == user_id, AuditTags.IsDeleted == 0, AuditTags.isScannedInMss == 0,
                            AuditTags.ScanId == latest_scan_id, AuditTags.GarmentBranchCode == branch_code,
                            AuditTags.GarmentStatus.in_([
                                'In Transits to CDC',
                                'Pending Transfer Out From CDC',
                                'Transfer in at CDC',
                                'Invoiced & Delivered'
                            ])
                        )
                    ).scalar()

                    if total_no_stock_count:
                        count = total_no_stock_count
                        total_no_stock_count = count - stock
                        # no_stock_count[garment_audit['status']] = total_no_stock_count
                        no_stock_count[garment_audit['status']] = count
                   
                    else:
                        pass
                        # print("No stock count found for the specified date and branch.")
                    garment_audit['details'].append(garment)
                    found = True
                    break

            if not found:
                garment_audit_data[-1]['details'].append(garment)

            for garment_audit in garment_audit_data:
                status = garment_audit['status']
                garment_audit['count'] = {
                    'with_complaint': with_complaint_count[status],
                    'without_complaint': without_complaint_count[status],
                    'other_stores': other_stores_count[status],
                    'no_stock': 0,
                    'mss_count': back_to_mss_value[status],
                    'other_store_mss_value': other_store_mss_value[status]
                    # 'no_stock': no_stock_count[status]

                }
        if is_mss:
            audit_type = "Back to MSS"
        else:
            audit_type = "Garment Audit"
        current_date = datetime.now().strftime("%d-%m-%Y %H:%M:%S %p")

        status_items = []

        # log_data = {
        #     'status_items': status_items,
        #     'garment_audit_data': garment_audit_data
        #
        # }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        for item in garment_audit_data:
            status = item.get('status')

            if status and status not in ['In Transits to CDC', 'Invoiced & Delivered', 'Pending Transfer Out From CDC',
                                         'Transfer in at CDC']:
                count_dict = item.get('count', {})

                # if isinstance(count_dict, dict) and any(value != 0 for value in count_dict.values()):
                if any(value != 0 for value in count_dict.values()):
                    status_items.append(item)
            else:
                status_items.append(item)
        log_data = {
            'status_items': status_items,
            'garment_audit_data':garment_audit_data

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        # for item in status_items:
        #     print(item)
        # print(status_items)
        if status_items is not None:
            status_data = status_items
            # print(status_data)
        else:
            pass


        # for item in garment_audit_data:
        #     status = item.get('status')

            

        #     if status and status not in ['In Transits to CDC', 'Invoiced & Delivered', 'Pending Transfer Out From CDC',
        #                                  'Transfer in at CDC']:
        #         count_dict = item.get('count', {})

        #         status_items.append(item)
        #         if any(value != 0 for value in count_dict.values()):
        #             status_items.append(item)
                # else:
                #     pass
                # else:
                #     status_items.append(item)
                # for value in count_dict.values():
                #     status_items.append(item)
                
            # else:
            #     status_items.append(item)




        # if status_items is not None:
        #     status_data = status_items
        #     # print(status_data)
        # else:
        #     pass

        BranchName = db.session.query(DCR_User_Branches.BranchName).filter(DCR_User_Branches.BranchCode ==branch_code).first()
        # BranchName = BranchName[0]
        # BranchName = str(BranchName)
        BranchName = str(BranchName[0]).replace("'", "")

      

        no_stock_tags_count = len(no_stock_tags)
        garment_audit_data_report = {"audit_type": audit_type,
                                     "audit_date": current_date,
                                     "branch_name": branch_name,
                                     "in_location": in_location,
                                     "auditor_name": auditor_name.Name,
                                     "garment_audit_data": status_data,
                                     "total_other_stores_count": total_other_stores_count,
                                     "total_with_complaint_count": total_with_complaint_count,
                                     "total_without_complaint_count": total_without_complaint_count,
                                     # "total_no_stock_count": total_no_stock_count,
                                     "total_no_stock_count1": noStock_count_data,
                                     "back_to_mss_count": back_to_mss_count,
                                     "other_store_mss_count": other_store_mss_count
                                     }
        data = 'summary-screen.html'
        if is_mss:
            subject = "Detailed garment audit report - " + BranchName
            # subject = "Detailed garment audit report - " + branch_name
        else:
            subject = "Detailed garment audit report - " + BranchName
        query_mail = f"EXEC {OLD_DB}.dbo.GetBranchEmail @branchcode = '{branch_code}'"
        mails = CallSP(query_mail).execute().fetchall()
        to_mail = mails[0]['ToEmail']

        cc_mail = mails[0]['CCEmail']
        auditor_mail = auditor_name.email
        mails = f'{to_mail};{auditor_mail}'
        # mails = f'{to_mail};{auditor_mail}'
        # for obj in garment_audit_data_report['garment_audit_data']:
        #     status = obj['status']
        #     index = next((index for (index, d) in enumerate(nostock_dtls_list) if d['GarmentStatus'] == status), None)
        #     # if index is not None:
        #     #     if isinstance(obj['count'], dict):
        #     #         obj['count']['no_stock'] += nostock_dtls_list[index]['Count']
        #     #     else:
        #     #         obj['count'] = nostock_dtls_list[index]['Count']
        #     if index is not None:
        #         if isinstance(obj['count'], dict):
        #             count_value = nostock_dtls_list[index].get('Count', 0)  # Default to 0 if 'Count' key is missing
        #             obj['count']['no_stock'] += count_value
        #         else:
        #             obj['count'] = nostock_dtls_list[index].get('Count', 0)  # Default to 0 if 'Count' key is missing

        status_counts = defaultdict(int)
        for item in nostock_dtls_list:
            status_counts[item['GarmentStatus']] += 1

        # Step 2: Update garment_audit_data_report with aggregated counts
        for obj in garment_audit_data_report['garment_audit_data']:
            status = obj['status']
            count_value = status_counts.get(status, 0)  # Get the count for the status, default to 0 if not found

            if isinstance(obj['count'], dict):
                obj['count'].setdefault('no_stock', 0)
                obj['count']['no_stock'] += count_value
            else:
                obj['count'] = count_value

                


        # for obj in garment_audit_data_report['garment_audit_data']:
        #     status = obj['status']
        #     index = next((index for (index, d) in enumerate(nostock_dtls_list) if d['GarmentStatus'] == status), None)
        #     if index is not None:
        #         count = nostock_dtls_list[index].get('Count', 0) 
        #         if isinstance(obj['count'], dict):
        #             obj['count']['no_stock'] += count
        #         else:
        #             obj['count'] = count
       
        

        log_data = {
            'audit_mail': garment_audit_data_report,
            'Auditor_mail': mails,
            "query_mail": query_mail,
            "cc_mail": cc_mail
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        #audit_update_mail = audit_mail.audit_mail(data, garment_audit_data_report, subject, report, mails, cc_mail)
        #audit_update_mail = audit_mail.audit_mail(data, garment_audit_data_report, subject, report, mails, branch_code, cc_mail,is_history)
        audit_update_mail = audit_mail.audit_mail(data, garment_audit_data_report, subject, report, mails, branch_code, cc_mail,is_history)
        if audit_update_mail:
            final_data = generate_final_data('SUCCESS')
            final_data['result'] = garment_audit_data_report
        else:
            final_data = generate_final_data('DATA_NOT_FOUND')

    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(garment_audit_report_form.errors)
    return final_data



@audit_blueprint.route('garment_audit_report_mss', methods=["POST"])
def garment_audit_report_mss():
    user_id = request.headers.get('user-id')
    garment_audit_report_form1 = GarmentAuditReportFormMss()
    log_data = {'Req body': garment_audit_report_form1.data}
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    if garment_audit_report_form1.validate_on_submit():
        garment_audit_updates_list = garment_audit_report_form1.garment_audit_updates_list.data

        for update in garment_audit_updates_list:
            # Extract individual fields from the update entry
            # print(update)
            ScanId = update.get('ScanId')
            # print(ScanId)
            branch_code = update.get('branchcode')
            branch_name = update.get('store')
            in_location = update.get('inLocation')
            mss_list = update.get('mss_list')
            # print(mss_list)
            other_store_list = update.get('other_store_list')
            audit_date = update.get('audit_date')
            # print(audit_date)
            is_mss = update.get('is_mss')
            is_history = update.get('is_history')

            # audit_date_obj = datetime.strptime(audit_date, "%d-%m-%Y %H:%M:%S")
            # formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            date_obj = datetime.strptime(audit_date, "%d-%m-%Y %H:%M:%S %p")
            #date_obj = datetime.strptime(audit_date, "%d-%m-%Y %H:%M:%S")
            formatted_date = date_obj.strftime("%Y-%m-%d")
            log_data = {'formatted_date': formatted_date}
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            # auditor data
            auditor_name = db.session.query(DCR_Users.Name, DCR_Users.email).filter(
                DCR_Users.Id == user_id).one_or_none()

            # mss_list_count = len(mss_list)

            other_store_count = len(other_store_list)
            total_without_complaint_count = 0
            total_with_complaint_count = 0

            garment_audit_data = [
                {'status': status, 'details': [], 'count': {'mss_count': 0, 'other_store_mss_value': 0}} for status in
                ['In Transits to CDC', 'Resorted', 'Work Order Created ', 'In Transits to mss',
                 'Pending Transfer Out From CDC', 'Invoiced & Delivered', 'Transfer in at CDC',
                 'Pending for QC Verification', 'Transfer in at mss', 'QC Approved', 'QC Rejected ',
                 'Moved Back to Mss', 'Invoiced & Pending Delivery',
                 'Under clearance of Invoice settlement',
                 'Missing', 'Damaged', 'Disputed Garment']]

            # print(ScanId)
            mss_tag_details = db.session.query(
                AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus, AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate, AuditTags.GarmentBranchCode, AuditTags.GarmentBranchName,
                AuditTags.OrderStatus,
                AuditTags.EntryType, AuditTags.ComplaintId, AuditTags.GarmentAmount, AuditTags.GarmentName,
                AuditTags.OrderType, AuditTags.CustomerName, AuditTags.CustomerId, AuditTags.GarmentStatus,
                AuditTags.isScannedInMss, AuditTags.IsMSS, AuditTags.ScanId, AuditTags.IsNoStock,AuditTags.IsValidTag
            ).filter(
                AuditTags.TagNo.in_(mss_list),
                AuditTags.ScannedBy == user_id,
                AuditTags.ScanId == ScanId,
                AuditTags.Date == formatted_date,
                AuditTags.BranchCode == branch_code,
                AuditTags.IsNoStock == 0,
                AuditTags.IsDeleted == 0,
                AuditTags.IsValidTag == 1,
                AuditTags.IsMSS == 1).all()
            #print("mss_tag_details",mss_tag_details)

            other_store_details = db.session.query(
                AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus, AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate, AuditTags.GarmentBranchCode, AuditTags.GarmentBranchName,
                AuditTags.OrderStatus,
                AuditTags.EntryType, AuditTags.ComplaintId, AuditTags.GarmentAmount, AuditTags.GarmentName,
                AuditTags.OrderType, AuditTags.CustomerName, AuditTags.CustomerId, AuditTags.GarmentStatus,
                AuditTags.isScannedInMss, AuditTags.IsMSS, AuditTags.ScanId, AuditTags.IsNoStock,AuditTags.IsValidTag
            ).filter(
                AuditTags.TagNo.in_(other_store_list),
                AuditTags.ScannedBy == user_id,
                AuditTags.Date == formatted_date,
                AuditTags.BranchCode == branch_code,
                AuditTags.IsNoStock == 0,
                AuditTags.IsDeleted == 0,
                AuditTags.IsValidTag == 1,
                AuditTags.ScanId == ScanId
            ).all()

            other_store_details = SerializeSQLAResult(other_store_details).serialize(full_date_fields=['ComplaintDate'])
            mss_tag_details = SerializeSQLAResult(mss_tag_details).serialize(full_date_fields=['ComplaintDate'])
            #print(mss_tag_details)

            combined_data_details = other_store_details + mss_tag_details
            # print('combined_data_details',combined_data_details)
            log_data = {'combined_data_details': combined_data_details, "other_store_details": other_store_details}
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))

            for garment in combined_data_details:
                if garment['GarmentBranchCode'] != branch_code and (
                        garment['IsMSS'] == 1 or garment['isScannedInMss'] == 1):
                    garment["category"] = 'Back to Mss Other Store'
                
                elif garment['IsMSS'] == 1 or garment['isScannedInMss'] == 1:
                    garment["category"] = 'Back to Mss'
                elif garment['ComplaintStatus'] == None:
                    garment["category"] = 'Without Complaint'
                elif garment['ComplaintStatus'] != None:
                    garment["category"] = 'With Complaint'
            for garment in combined_data_details:
                if garment['ScanId'] > 1 and garment['IsNoStock'] == 0 and (
                        garment['IsMSS'] == 1 or garment['isScannedInMss'] == 1):
                    garment['scan status'] = 'Already scanned'

            garment_dtls = [{key: val for key, val in d.items() if key not in ['IsValidTag']} for d in
                            combined_data_details]

            other_store_mss_value = defaultdict(int)
            back_to_mss_value = defaultdict(int)
            without_complaint_value = defaultdict(int)
            with_complaint_value = defaultdict(int)

            for garment in combined_data_details:
                for garment_audit in garment_audit_data:
                    if garment_audit['status'] == garment['GarmentStatus']:
                        if garment['GarmentBranchCode'] != branch_code and (
                                garment['IsMSS'] == 1 or garment['isScannedInMss'] == 1):
                            other_store_mss_value[garment_audit['status']] += 1
                        elif garment['ComplaintStatus'] is None:
                            total_without_complaint_count += 1
                            without_complaint_value[garment_audit['status']] += 1
                        elif garment['ComplaintStatus'] != None and garment['IsNoStock'] in (0, 'No') and garment[
                            "IsValidTag"] == 1:
                            total_with_complaint_count += 1
                            with_complaint_value[garment_audit['status']] += 1

            for garment_audit in garment_audit_data:
                status = garment_audit['status']
                garment_audit['count'] = {
                    'with_complaint': with_complaint_value[status],
                    'other_store_mss': other_store_mss_value[status],
                    'without_complaint': without_complaint_value[status],
                }

            audit_type = "Back to MSS" if is_mss else "Garment Audit"
            current_date = datetime.now().strftime("%d-%m-%Y %H:%M:%S %p")

            status_items = [item for item in garment_audit_data if any(value != 0 for value in item['count'].values())]


            # already_scanned = db.session.query(AuditTags.TagNo).filter(AuditTags.IsMSS ==1 or AuditTags.isScannedInMss == 1).all()
            already_scanned = db.session.query(AuditTags.TagNo).filter(AuditTags.IsMSS ==1).all()

            already_scanned = SerializeSQLAResult(already_scanned).serialize(
                full_date_fields=['ComplaintDate'])
            already_scanned_tags = [record['TagNo'] for record in already_scanned]

            for datadtls in garment_dtls:
                if datadtls['TagNo'] in already_scanned_tags:
                    datadtls['scan status'] = 'Already scanned'


            excluded_data_details = [
                {key: val for key, val in d.items() if
                 key not in ['ScanId', 'IsNoStock', 'NoStock', 'IsMSS', 'isScannedInMss']}
                for d in combined_data_details]

            report = GenerateReport(excluded_data_details, audit_type).generate().get()

            garment_audit_data_report = {
                "audit_type": audit_type,
                "audit_date": audit_date,
                "branch_name": branch_name,
                "garment_audit_data": garment_audit_data,
                "in_location": in_location,
                "auditor_name": auditor_name.Name,
                "total_with_complaint_count": total_with_complaint_count,
                "total_without_complaint_count": total_without_complaint_count,
                "other_store_count": other_store_count
            }

            data = 'summary-screen-mss.html'
            subject = f"Detailed back to MSS report - {branch_name}"
            query_mail = f"EXEC {OLD_DB}.dbo.GetBranchEmail @branchcode = '{branch_code}'"
            mails = CallSP(query_mail).execute().fetchall()
            log_data = {'mail': mails}
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            to_mail = mails[0]['ToEmail']
            cc_mail = mails[0]['CCEmail']
            auditor_mail = auditor_name.email
            mails = f'{to_mail};{auditor_mail}'

            log_data = {'audit_mail': garment_audit_data_report, "mails_test": mails}
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))

            #audit_update_mail = audit_mail.audit_mail(data, garment_audit_data_report, subject, report, mails, cc_mail,is_history)
            audit_update_mail = audit_mail.audit_mail(data, garment_audit_data_report, subject, report, mails, branch_code, cc_mail, is_history)
            final_data = generate_final_data('SUCCESS') if audit_update_mail else generate_final_data('DATA_NOT_FOUND')
            final_data['result'] = garment_audit_data_report

    else:
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(garment_audit_report_form1.errors)

    return final_data

@audit_blueprint.route('get_audit_tag_detailsLive', methods=["POST"])
# @authenticate('audit')
def get_audit_tag_detailsLive():
    user_id = request.headers.get('user-id')
    # print(user_id)
    garment_audit_form = GarmentAuditDetailsForm()
    log_data = {
        
        'garment_audit_form.data': garment_audit_form.data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    if garment_audit_form.validate_on_submit():
        tag_list = None if garment_audit_form.tag_list.data == '' else garment_audit_form.tag_list.data
        branch_code = garment_audit_form.branch_code.data
        is_mss = garment_audit_form.is_mss.data
        complaints = []
        without_complaints = []
        other_stores = []
        mss_pending_transfer_out_from_cdc = []
        mss_in_transit_to_mss = []
        mss_pending_for_qc_verification = []
        mss_transfer_in_at_mss = []
        mss_qc_approved = []
        mss_qc_rejected = []
        mss_work_order_created = []
        mss_missing = []
        mss_damaged = []
        mss_resorted = []
        mss_in_transit_to_cdc = []
        mss_transfer_in_at_cdc = []
        mss_disputed_garment = []
        mss_invoiced_and_delivered = []
        mss_under_clearance_of_invoice_settlement = []
        mss_invoiced_and_pending_delivery = []
        mss_moved_back_to_mss = []
        mss_no_stock = []

        user_id = user_id.strip() if user_id else None  # Strip whitespace if it exists
        username = db.session.query(DCR_Users.Name).filter(DCR_Users.Id == user_id).one_or_none()
        # print(username)

        if username is not None:
            # Extract the first element from the tuple (assuming it's the only element)
            username = username[0]
            # print(username)
        else:
            username = None

        # user_id = user_id.strip() if user_id else None  # Strip whitespace if it exists
        # print(user_id)
        # username = db.session.query(DCR_Users.Name).filter(DCR_Users.Id == user_id).one_or_none()

        # print(username)

        # tag_details = db.session.query(AuditTags.TagNo, AuditTags.BranchCode, AuditTags.GarmentBranchCode,
        #                                AuditTags.GarmentStatus, AuditTags.IsDelivered,
        #                                AuditTags.ComplaintId, AuditTags.RecordCreatedDate.label('ScannedDate'),
        #                                AuditTags.InLocation
        #                                ).filter(
        #     AuditTags.TagNo.in_(tag_list), AuditTags.IsMSS == is_mss, AuditTags.BranchCode == branch_code,
        #                                    AuditTags.ScannedBy == user_id, AuditTags.IsNoStock == 0,
        #                                    AuditTags.IsValidTag == 1, AuditTags.IsDeleted == 0,
        #                                    AuditTags.Date == date.today()).all()

        # tag_details = db.session.query(AuditTags.TagNo, AuditTags.BranchCode, AuditTags.GarmentBranchCode,
        #                                AuditTags.GarmentStatus, AuditTags.IsDelivered,
        #                                AuditTags.ComplaintId, AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
        #                                AuditTags.InLocation
        #                                ).filter(
        #     AuditTags.TagNo.in_(tag_list), AuditTags.BranchCode == branch_code,
        #                                    AuditTags.ScannedBy == user_id, AuditTags.IsNoStock == 0,
        #                                    AuditTags.IsValidTag == 1, AuditTags.IsDeleted == 0,
        #                                    AuditTags.IsMSS == is_mss,
        #                                    AuditTags.Date == date.today()).all()
        from sqlalchemy import func
        latest_scan_id = db.session.query(func.max(AuditTags.ScanId)).filter(
            AuditTags.AuditedBy == user_id,
            AuditTags.Date == date.today(), AuditTags.BranchCode == branch_code, AuditTags.IsMSS == is_mss,
            AuditTags.ScannedBy == user_id).scalar()

        # print(latest_scan_id)
        log_data = {
            'latest_scan_id': latest_scan_id,
            'garment_audit_form':garment_audit_form.data,
            "tag_list ":tag_list 
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        tag_details = db.session.query(
            AuditTags.TagNo,
            AuditTags.BranchCode,
            AuditTags.Execptionflag,
            AuditTags.GarmentBranchCode,
            AuditTags.GarmentStatus,
            AuditTags.IsDelivered,
            AuditTags.ComplaintId,
            AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
            AuditTags.InLocation, AuditTags.ScanId,
            AuditTags.IsMSS
        ).filter(
            AuditTags.TagNo.in_(tag_list),
            AuditTags.BranchCode == branch_code,
            AuditTags.ScannedBy == user_id,
            AuditTags.IsNoStock == 0,
            AuditTags.IsValidTag == 1,
            AuditTags.IsDeleted == 0,
            AuditTags.IsMSS == is_mss,
            AuditTags.isScannedInMss == 0,
            AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
        ).group_by(
            AuditTags.TagNo,
            AuditTags.IsMSS,
            AuditTags.ScanId,
            AuditTags.Execptionflag,
            AuditTags.BranchCode,
            AuditTags.GarmentBranchCode,
            AuditTags.GarmentStatus,
            AuditTags.IsDelivered,
            AuditTags.ComplaintId,
            AuditTags.RecordLastUpdatedDate,
            AuditTags.InLocation
        ).all()

        # print(tag_details)
        # print("Fetched Tag Details1:", tag_details)
        tag_details = SerializeSQLAResult(tag_details).serialize(full_date_fields=['ScannedDate'])
        log_data = {
            'tag_details__': tag_details
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        # print("Fetched Tag Details:", tag_details)
        # last_tag = tag_details[-1]
        # ScannedDate=last_tag['ScannedDate']
        branch_tags = []
        scanned_dates = []
        in_location = False
        scanned_dates = ''
        for tag in tag_details:
            scanned_dates = tag['ScannedDate']
            # print(scanned_date)
            in_location = tag['InLocation']
            # print(tag['GarmentBranchCode'])
            if tag['GarmentBranchCode'] == branch_code and tag['Execptionflag'] == 0:
                # print("hai")
                # print(tag['GarmentBranchCode'])
                # print(tag['GarmentStatus'])
                if tag['GarmentStatus'] == 'In Transits to CDC':
                    branch_tags.append(tag['TagNo'])
                    # print(branch_tags)
                elif tag['GarmentStatus'] == 'Pending Transfer Out From CDC':
                    branch_tags.append(tag['TagNo'])
                    # print(branch_tags)
                elif tag['GarmentStatus'] == 'Transfer in at CDC':
                    branch_tags.append(tag['TagNo'])
                    # print(branch_tags)
                elif tag['GarmentStatus'] == 'Invoiced & Delivered' and tag['IsDelivered'] in ('', 'Un-Delivered'):

                    branch_tags.append(tag['TagNo'])
                    # print(branch_tags)
                else:
                    pass

            if tag['ComplaintId'] is None and tag['GarmentBranchCode'] == branch_code:
                # print(branch_code)
                without_complaints.append(tag['TagNo'])
                # print(without_complaints)
            elif tag['ComplaintId'] is not None and tag['GarmentBranchCode'] == branch_code:
                complaints.append(tag['TagNo'])
                # print("tag",complaints)
            elif tag['GarmentBranchCode'] != branch_code:
                other_stores.append(tag['TagNo'])
            else:
                pass

        no_stock_tag_details = db.session.query(AuditTags.TagNo, AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                AuditTags.InLocation, AuditTags.GarmentStatus
                                                ).filter(AuditTags.BranchCode == branch_code,
                                                         AuditTags.IsNoStock == 1, 
                                                         AuditTags.IsMSS == is_mss,
                                                         AuditTags.IsValidTag == 1, AuditTags.IsDeleted == 0,
                                                         AuditTags.Date == date.today(),
                                                         AuditTags.ScanId == latest_scan_id,
                                                         AuditTags.Execptionflag == 0,
                                                         AuditTags.isScannedInMss == 0,
                                                         AuditTags.AuditedBy == user_id, AuditTags.GarmentStatus.in_(
                ['In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC',
                 'Invoiced & Delivered'])).all()
        no_stock_tags = SerializeSQLAResult(no_stock_tag_details).serialize(full_date_fields=['ScannedDate'])
        # print("Fetched Tag Details:", no_stock_tags)
        no_stock_tag = []
        for nostock_tag in no_stock_tags:
            # print(nostock_tag)
            scanned_date = nostock_tag['ScannedDate']
            # print("scanned_date",scanned_date)
            in_location = nostock_tag['InLocation']
            no_stock_tag.append(nostock_tag["TagNo"])
        # print(len(no_stock_tag))
        # no_stock_tag = [item[0] for item in no_stock_tag_details]
        without_complaints = set(without_complaints)
        without_complaints = list(without_complaints)
        without_complaints_count = len(without_complaints)
        complaints_count = len(complaints)
        other_stores_count = len(other_stores)
        # print(date.today())
        # total_garment_count = db.session.query(AuditGarmentCount).filter(
        #     AuditGarmentCount.Date == date.today(), AuditGarmentCount.BranchCode == branch_code).one_or_none()
        try:
            scan_id_qry = """SELECT GarmentCount AS AuditGarmentCount FROM AuditGarmentCount WHERE ScanId= (SELECT MAX(ScanId) FROM AuditGarmentCount WHERE CONVERT(DATE, Date) = CONVERT(DATE, GETDATE()) and BranchCode=:branch_code AND AuditedBy=:user_id) and  CONVERT(DATE, Date) = CONVERT(DATE, GETDATE()) and BranchCode=:branch_code AND AuditedBy=:user_id"""
            # SELECT garmntNo FROM table1 WHERE id = (SELECT MAX(id) FROM table1 WHERE branchcode = 1)
            result = db.session.execute(text(scan_id_qry),
                                        {'branch_code': branch_code, 'user_id': user_id})
            total_garment_count = result.scalar()

            log_data = {
            'total_garment_count': total_garment_count
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))

            # print(total_garment_count)
        except Exception as ex:
            print(ex)

        # print(total_garment_count.GarmentCount)
        # total_garment_count = int(total_garment_count.GarmentCount)

        # last modification
        # if total_garment_count is not None:
        #     total_garment_count = int(total_garment_count)
        # else:
        #     pass
        if is_mss:
            back_to_mss_tags1 = db.session.query(AuditTags.TagNo, AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                AuditTags.InLocation, AuditTags.GarmentStatus).filter(
                AuditTags.TagNo.in_(tag_list),
                AuditTags.BranchCode == branch_code,
                AuditTags.GarmentBranchCode == branch_code,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsNoStock == 0,
                AuditTags.IsValidTag == 1,
                AuditTags.IsDeleted == 0,
                # AuditTags.isScannedInMss == 1,
                AuditTags.IsMSS == is_mss,
                AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
            ).group_by().all()
        else:
            back_to_mss_tags1 = db.session.query(AuditTags.TagNo,AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                    AuditTags.InLocation, AuditTags.GarmentStatus).filter(
                AuditTags.TagNo.in_(tag_list),
                AuditTags.BranchCode == branch_code,
                AuditTags.GarmentBranchCode == branch_code,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsNoStock == 0,
                AuditTags.IsValidTag == 1,
                AuditTags.IsDeleted == 0,
                AuditTags.isScannedInMss==1,
                AuditTags.IsMSS==0,
                AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
            ).group_by().all()

        back_to_mss_tags = [tag[0] for tag in back_to_mss_tags1]

        mss_tag_details = SerializeSQLAResult(back_to_mss_tags1).serialize(full_date_fields=['ScannedDate'])

        for mss in mss_tag_details:
            if mss['GarmentStatus'] == 'In Transits to CDC':
                mss_in_transit_to_cdc.append(mss)
            elif mss['GarmentStatus'] == 'Resorted':
                mss_resorted.append(mss)
            elif mss['GarmentStatus'] == 'Work Order Created ':
                mss_work_order_created.append(mss)
            elif mss['GarmentStatus'] == 'In Transits to mss':
                mss_in_transit_to_mss.append(mss)
            elif mss['GarmentStatus'] == 'Pending Transfer Out From CDC':
                mss_pending_transfer_out_from_cdc.append(mss)
            elif mss['GarmentStatus'] == 'Invoiced & Delivered':
                mss_invoiced_and_delivered.append(mss)
            elif mss['GarmentStatus'] == 'Transfer in at CDC':
                mss_transfer_in_at_cdc.append(mss)
            elif mss['GarmentStatus'] == 'Pending for QC Verification':
                mss_pending_for_qc_verification.append(mss)
            elif mss['GarmentStatus'] == 'Transfer in at mss':
                mss_transfer_in_at_mss.append(mss)
            elif mss['GarmentStatus'] == 'QC Approved':
                mss_qc_approved.append(mss)
            elif mss['GarmentStatus'] == 'QC Rejected ':
                mss_qc_rejected.append(mss)
            elif mss['GarmentStatus'] == 'Moved Back to Mss':
                mss_moved_back_to_mss.append(mss)
            elif mss['GarmentStatus'] == 'Invoiced & Pending Delivery':
                mss_invoiced_and_pending_delivery.append(mss)
            elif mss['GarmentStatus'] == 'Under clearance of Invoice settlement':
                mss_under_clearance_of_invoice_settlement.append(mss)
            elif mss['GarmentStatus'] == 'Missing':
                mss_missing.append(mss)
            elif mss['GarmentStatus'] == 'Damaged':
                mss_damaged.append(mss)
            elif mss['GarmentStatus'] == 'Disputed Garment':
                mss_disputed_garment.append(mss)
            else:
                mss_no_stock.append(mss)



        scanned_dates = datetime.today().strftime("%d-%m-%Y %H:%M:%S %p")
        log_data = {
         'scanned_dates': scanned_dates
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        if is_mss:
            mss_tags_other_store = db.session.query(AuditTags.TagNo,AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                AuditTags.InLocation, AuditTags.GarmentStatus).filter(
            AuditTags.TagNo.in_(tag_list),
            AuditTags.GarmentBranchCode != branch_code,
            AuditTags.ScannedBy == user_id,
            AuditTags.IsNoStock == 0,
            AuditTags.IsValidTag == 1,
            AuditTags.IsDeleted == 0,
            AuditTags.IsMSS == 1,
            AuditTags.BranchCode == branch_code,
            AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
            ).group_by().all()
        else:
            mss_tags_other_store = db.session.query(AuditTags.TagNo,AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                    AuditTags.InLocation, AuditTags.GarmentStatus).filter(
                AuditTags.isScannedInMss == 1, AuditTags.TagNo.in_(tag_list),
                AuditTags.GarmentBranchCode != branch_code,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsNoStock == 0,
                AuditTags.IsValidTag == 1,
                AuditTags.IsDeleted == 0,
                AuditTags.IsMSS == 0,
                AuditTags.BranchCode == branch_code,
                AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
                ).group_by().all()

        mss_tags_other_store = [tag[0] for tag in mss_tags_other_store]
        
        if back_to_mss_tags is not None:
            back_to_mss_count = len(back_to_mss_tags)
        else:
            back_to_mss_count = 0

        if mss_tags_other_store is not None:
            mss_tags_other_store_count = len(mss_tags_other_store)
        else:
            mss_tags_other_store_count = 0

        total_scnned_branch_count = len(branch_tags) 
        if total_garment_count is not None:
            total_garment_count = int(total_garment_count)
        else:
            pass

        total_tags_scanned = len(tag_list)
        total = without_complaints_count + complaints_count
        total_scnned_branch_count = len(branch_tags)

        # print(total_scnned_branch_count)


        if total_garment_count is not None and total_scnned_branch_count is not None:
            # no_stock_count = total_garment_count - total_scnned_branch_count + back_to_mss_count
            no_stock_count = total_garment_count - total_scnned_branch_count 
            # print(no_stock_count)
        else:
            no_stock_count = total_garment_count 

        # back_to_mss_tags=list(back_to_mss_tags)
        
        # scanned_dates = datetime.today().strftime("%d-%m-%Y %H:%M:%S")
        # scanned_dates = scanned_dates.strftime("%d-%m-%Y %I:%M:%S %p")
        log_data = {
         'scanned_dates': scanned_dates,
         "without_complaints":without_complaints,
         "complaints":complaints

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        final_data = generate_final_data('DATA_SAVED')
        final_data['result'] = {'ScannedBy': username, 'WithoutComplaints': without_complaints,
                                'WithComplaints': complaints,
                                'OtherStores': other_stores, 'WithoutComplaintsCount': without_complaints_count,
                                'WithComplaintsCount': complaints_count, 'OtherStoresCount': other_stores_count,
                                'TotalGarmentCount': total_garment_count, 'TotalTagsScanned': total_tags_scanned,
                                'NoStock': no_stock_count, 'ScannedDate': scanned_dates, 'InLocation': in_location,
                                'NoStockTag': no_stock_tag,
                                'scan_id': latest_scan_id,
                                "mss_tags":back_to_mss_tags,
                                "mss_count":back_to_mss_count,
                                "mss_other_store":mss_tags_other_store,
                                "mss_other_store_count":mss_tags_other_store_count,
                                
                                }

        final_data['mss_tags'] = [{'status': 'Pending transfer out from CDC',
                                   'count': len(mss_pending_transfer_out_from_cdc),
                                   'details': mss_pending_transfer_out_from_cdc
                                   },
                                  {'status': 'In Transits to MSS',
                                   'count': len(mss_in_transit_to_mss),
                                   'details': mss_in_transit_to_mss
                                   },
                                  {'status': 'Transfer in at MSS',
                                   'count': len(mss_transfer_in_at_mss),
                                   'details': mss_transfer_in_at_mss
                                   },
                                  {'status': 'Pending for QC Verification',
                                   'count': len(mss_pending_for_qc_verification),
                                   'details': mss_pending_for_qc_verification
                                   },
                                  {'status': 'QC Approved',
                                   'count': len(mss_qc_approved),
                                   'details': mss_qc_approved
                                   },
                                  {'status': 'QC Rejected ',
                                   'count': len(mss_qc_rejected),
                                   'details': mss_qc_rejected
                                   },
                                  {'status': 'Work Order Created ',
                                   'count': len(mss_work_order_created),
                                   'details': mss_work_order_created
                                   },
                                  {'status': 'Resorted',
                                   'count': len(mss_resorted),
                                   'details': mss_resorted
                                   },
                                  {'status': 'In Transits to CDC',
                                   'count': len(mss_in_transit_to_cdc),
                                   'details': mss_in_transit_to_cdc
                                   },
                                  {'status': 'Transfer in at CDC',
                                   'count': len(mss_transfer_in_at_cdc),
                                   'details': mss_transfer_in_at_cdc
                                   },
                                  {'status': 'Invoiced & Delivered',
                                   'count': len(mss_invoiced_and_delivered),
                                   'details': mss_invoiced_and_delivered
                                   },
                                  {'status': 'Under Clearance of Invoice settlement',
                                   'count': len(mss_under_clearance_of_invoice_settlement),
                                   'details': mss_under_clearance_of_invoice_settlement
                                   },
                                  {'status': 'Missing',
                                   'count': len(mss_missing),
                                   'details': mss_missing
                                   },
                                  {'status': 'Damaged',
                                   'count': len(mss_damaged),
                                   'details': mss_damaged
                                   },
                                  {'status': 'Disputed Garment',
                                   'count': len(mss_disputed_garment),
                                   'details': mss_disputed_garment
                                   },
                                  {'status': 'Invoiced and Pending Delivery',
                                   'count': len(mss_invoiced_and_pending_delivery),
                                   'details': mss_invoiced_and_pending_delivery
                                   },
                                  {'status': 'Moved Back to Mss',
                                   'count': len(mss_moved_back_to_mss),
                                   'details': mss_moved_back_to_mss
                                   }
                                  ]
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(garment_audit_form.errors)

    return final_data

@audit_blueprint.route('get_audit_tag_detailsNew', methods=["POST"])
# @authenticate('audit')
def get_audit_tag_detailsNew():
    user_id = request.headers.get('user-id')
    # print(user_id)
    garment_audit_form = GarmentAuditDetailsForm()
    log_data = {
        
        'garment_audit_form.data': garment_audit_form.data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    if garment_audit_form.validate_on_submit():
        tag_list = None if garment_audit_form.tag_list.data == '' else garment_audit_form.tag_list.data
        branch_code = garment_audit_form.branch_code.data
        is_mss = garment_audit_form.is_mss.data
        complaints = []
        without_complaints = []
        other_stores = []
        mss_pending_transfer_out_from_cdc = []
        mss_in_transit_to_mss = []
        mss_pending_for_qc_verification = []
        mss_transfer_in_at_mss = []
        mss_qc_approved = []
        mss_qc_rejected = []
        mss_work_order_created = []
        mss_missing = []
        mss_damaged = []
        mss_resorted = []
        mss_in_transit_to_cdc = []
        mss_transfer_in_at_cdc = []
        mss_disputed_garment = []
        mss_invoiced_and_delivered = []
        mss_under_clearance_of_invoice_settlement = []
        mss_invoiced_and_pending_delivery = []
        mss_moved_back_to_mss = []
        mss_no_stock = []

        user_id = user_id.strip() if user_id else None  # Strip whitespace if it exists
        username = db.session.query(DCR_Users.Name).filter(DCR_Users.Id == user_id).one_or_none()
        # print(username)

        if username is not None:
            # Extract the first element from the tuple (assuming it's the only element)
            username = username[0]
            # print(username)
        else:
            username = None

        # user_id = user_id.strip() if user_id else None  # Strip whitespace if it exists
        # print(user_id)
        # username = db.session.query(DCR_Users.Name).filter(DCR_Users.Id == user_id).one_or_none()

        # print(username)

        # tag_details = db.session.query(AuditTags.TagNo, AuditTags.BranchCode, AuditTags.GarmentBranchCode,
        #                                AuditTags.GarmentStatus, AuditTags.IsDelivered,
        #                                AuditTags.ComplaintId, AuditTags.RecordCreatedDate.label('ScannedDate'),
        #                                AuditTags.InLocation
        #                                ).filter(
        #     AuditTags.TagNo.in_(tag_list), AuditTags.IsMSS == is_mss, AuditTags.BranchCode == branch_code,
        #                                    AuditTags.ScannedBy == user_id, AuditTags.IsNoStock == 0,
        #                                    AuditTags.IsValidTag == 1, AuditTags.IsDeleted == 0,
        #                                    AuditTags.Date == date.today()).all()

        # tag_details = db.session.query(AuditTags.TagNo, AuditTags.BranchCode, AuditTags.GarmentBranchCode,
        #                                AuditTags.GarmentStatus, AuditTags.IsDelivered,
        #                                AuditTags.ComplaintId, AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
        #                                AuditTags.InLocation
        #                                ).filter(
        #     AuditTags.TagNo.in_(tag_list), AuditTags.BranchCode == branch_code,
        #                                    AuditTags.ScannedBy == user_id, AuditTags.IsNoStock == 0,
        #                                    AuditTags.IsValidTag == 1, AuditTags.IsDeleted == 0,
        #                                    AuditTags.IsMSS == is_mss,
        #                                    AuditTags.Date == date.today()).all()
        from sqlalchemy import func
        latest_scan_id = db.session.query(func.max(AuditTags.ScanId)).filter(
            AuditTags.AuditedBy == user_id,
            AuditTags.Date == date.today(), AuditTags.BranchCode == branch_code, AuditTags.IsMSS == is_mss,
            AuditTags.ScannedBy == user_id).scalar()

        # print(latest_scan_id)
        log_data = {
            'latest_scan_id': latest_scan_id,
            'garment_audit_form':garment_audit_form.data,
            "tag_list ":tag_list 
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        tag_details = db.session.query(
            AuditTags.TagNo,
            AuditTags.BranchCode,
            AuditTags.Execptionflag,
            AuditTags.GarmentBranchCode,
            AuditTags.GarmentStatus,
            AuditTags.IsDelivered,
            AuditTags.ComplaintId,
            AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
            AuditTags.InLocation, AuditTags.ScanId,
            AuditTags.IsMSS
        ).filter(
            AuditTags.TagNo.in_(tag_list),
            AuditTags.BranchCode == branch_code,
            AuditTags.ScannedBy == user_id,
            AuditTags.IsNoStock == 0,
            AuditTags.IsValidTag == 1,
            AuditTags.IsDeleted == 0,
            AuditTags.IsMSS == is_mss,
            AuditTags.isScannedInMss == 0,
            AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
        ).group_by(
            AuditTags.TagNo,
            AuditTags.IsMSS,
            AuditTags.ScanId,
            AuditTags.Execptionflag,
            AuditTags.BranchCode,
            AuditTags.GarmentBranchCode,
            AuditTags.GarmentStatus,
            AuditTags.IsDelivered,
            AuditTags.ComplaintId,
            AuditTags.RecordLastUpdatedDate,
            AuditTags.InLocation
        ).all()

        # print(tag_details)
        # print("Fetched Tag Details1:", tag_details)
        tag_details = SerializeSQLAResult(tag_details).serialize(full_date_fields=['ScannedDate'])
        log_data = {
            'tag_details__': tag_details
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        # print("Fetched Tag Details:", tag_details)
        # last_tag = tag_details[-1]
        # ScannedDate=last_tag['ScannedDate']
        branch_tags = []
        scanned_dates = []
        in_location = False
        scanned_dates = ''
        for tag in tag_details:
            scanned_dates = tag['ScannedDate']
            # print(scanned_date)
            in_location = tag['InLocation']
            # print(tag['GarmentBranchCode'])
            if tag['GarmentBranchCode'] == branch_code and tag['Execptionflag'] == 0:
                # print("hai")
                # print(tag['GarmentBranchCode'])
                # print(tag['GarmentStatus'])
                if tag['GarmentStatus'] == 'In Transits to CDC':
                    branch_tags.append(tag['TagNo'])
                    # print(branch_tags)
                elif tag['GarmentStatus'] == 'Pending Transfer Out From CDC':
                    branch_tags.append(tag['TagNo'])
                    # print(branch_tags)
                elif tag['GarmentStatus'] == 'Transfer in at CDC':
                    branch_tags.append(tag['TagNo'])
                    # print(branch_tags)
                elif tag['GarmentStatus'] == 'Invoiced & Delivered' and tag['IsDelivered'] in ('', 'Un-Delivered'):

                    branch_tags.append(tag['TagNo'])
                    # print(branch_tags)
                else:
                    pass

            if tag['ComplaintId'] is None and tag['GarmentBranchCode'] == branch_code:
                # print(branch_code)
                without_complaints.append(tag['TagNo'])
                # print(without_complaints)
            elif tag['ComplaintId'] is not None and tag['GarmentBranchCode'] == branch_code:
                complaints.append(tag['TagNo'])
                # print("tag",complaints)
            elif tag['GarmentBranchCode'] != branch_code:
                other_stores.append(tag['TagNo'])
            else:
                pass

        no_stock_tag_details = db.session.query(AuditTags.TagNo, AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                AuditTags.InLocation, AuditTags.GarmentStatus
                                                ).filter(AuditTags.BranchCode == branch_code,
                                                         AuditTags.IsNoStock == 1, 
                                                         AuditTags.IsMSS == is_mss,
                                                         AuditTags.IsValidTag == 1, AuditTags.IsDeleted == 0,
                                                         AuditTags.Date == date.today(),
                                                         AuditTags.ScanId == latest_scan_id,
                                                         AuditTags.Execptionflag == 0,
                                                         AuditTags.isScannedInMss == 0,
                                                         AuditTags.AuditedBy == user_id, AuditTags.GarmentStatus.in_(
                ['In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC',
                 'Invoiced & Delivered'])).all()
        no_stock_tags = SerializeSQLAResult(no_stock_tag_details).serialize(full_date_fields=['ScannedDate'])
        # print("Fetched Tag Details:", no_stock_tags)
        no_stock_tag = []
        for nostock_tag in no_stock_tags:
            # print(nostock_tag)
            scanned_date = nostock_tag['ScannedDate']
            # print("scanned_date",scanned_date)
            in_location = nostock_tag['InLocation']
            no_stock_tag.append(nostock_tag["TagNo"])
        # print(len(no_stock_tag))
        # no_stock_tag = [item[0] for item in no_stock_tag_details]
        without_complaints = set(without_complaints)
        without_complaints = list(without_complaints)
        without_complaints_count = len(without_complaints)
        complaints_count = len(complaints)
        other_stores_count = len(other_stores)
        # print(date.today())
        # total_garment_count = db.session.query(AuditGarmentCount).filter(
        #     AuditGarmentCount.Date == date.today(), AuditGarmentCount.BranchCode == branch_code).one_or_none()
        try:
            # scan_id_qry = """SELECT GarmentCount AS AuditGarmentCount FROM AuditGarmentCount WHERE ScanId= (SELECT MAX(ScanId) FROM AuditGarmentCount WHERE CONVERT(DATE, Date) = CONVERT(DATE, GETDATE()) and BranchCode=:branch_code AND AuditedBy=:user_id) and  CONVERT(DATE, Date) = CONVERT(DATE, GETDATE()) and BranchCode=:branch_code AND AuditedBy=:user_id"""
            # # SELECT garmntNo FROM table1 WHERE id = (SELECT MAX(id) FROM table1 WHERE branchcode = 1)
            
            #  scan_id_qry modified on 31-jul-2024 
            scan_id_qry = """SELECT count(distinct TagNo) FROM  AuditTags WHERE 
                            ScanId= (SELECT MAX(ScanId) FROM AuditTags WHERE CONVERT(DATE, Date) = CONVERT(DATE, GETDATE()) 
                            and BranchCode=:branch_code AND AuditedBy=:user_id) 
                            and  CONVERT(DATE, Date) = CONVERT(DATE, GETDATE()) 
                            and BranchCode=:branch_code AND AuditedBy=:user_id
                            AND  Execptionflag = 0 AND   IsDeleted = 0 AND  IsValidTag = 1 AND   IsMSS = 0 AND  isScannedInMss = 0 AND 
                            GarmentBranchCode = :branch_code AND
                            GarmentStatus IN ('In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC', 'Invoiced & Delivered')"""

            result = db.session.execute(text(scan_id_qry),
                                        {'branch_code': branch_code, 'user_id': user_id})
            total_garment_count = result.scalar()

            log_data = {
            'total_garment_count': total_garment_count
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))

            # print(total_garment_count)
        except Exception as ex:
            print(ex)

        # print(total_garment_count.GarmentCount)
        # total_garment_count = int(total_garment_count.GarmentCount)

        # last modification
        # if total_garment_count is not None:
        #     total_garment_count = int(total_garment_count)
        # else:
        #     pass
        if is_mss:
            back_to_mss_tags1 = db.session.query(AuditTags.TagNo, AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                AuditTags.InLocation, AuditTags.GarmentStatus).filter(
                AuditTags.TagNo.in_(tag_list),
                AuditTags.BranchCode == branch_code,
                AuditTags.GarmentBranchCode == branch_code,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsNoStock == 0,
                AuditTags.IsValidTag == 1,
                AuditTags.IsDeleted == 0,
                # AuditTags.isScannedInMss == 1,
                AuditTags.IsMSS == is_mss,
                AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
            ).group_by().all()
        else:
            back_to_mss_tags1 = db.session.query(AuditTags.TagNo,AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                    AuditTags.InLocation, AuditTags.GarmentStatus).filter(
                AuditTags.TagNo.in_(tag_list),
                AuditTags.BranchCode == branch_code,
                AuditTags.GarmentBranchCode == branch_code,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsNoStock == 0,
                AuditTags.IsValidTag == 1,
                AuditTags.IsDeleted == 0,
                AuditTags.isScannedInMss==1,
                AuditTags.IsMSS==0,
                AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
            ).group_by().all()

        back_to_mss_tags = [tag[0] for tag in back_to_mss_tags1]

        mss_tag_details = SerializeSQLAResult(back_to_mss_tags1).serialize(full_date_fields=['ScannedDate'])

        for mss in mss_tag_details:
            if mss['GarmentStatus'] == 'In Transits to CDC':
                mss_in_transit_to_cdc.append(mss)
            elif mss['GarmentStatus'] == 'Resorted':
                mss_resorted.append(mss)
            elif mss['GarmentStatus'] == 'Work Order Created ':
                mss_work_order_created.append(mss)
            elif mss['GarmentStatus'] == 'In Transits to mss':
                mss_in_transit_to_mss.append(mss)
            elif mss['GarmentStatus'] == 'Pending Transfer Out From CDC':
                mss_pending_transfer_out_from_cdc.append(mss)
            elif mss['GarmentStatus'] == 'Invoiced & Delivered':
                mss_invoiced_and_delivered.append(mss)
            elif mss['GarmentStatus'] == 'Transfer in at CDC':
                mss_transfer_in_at_cdc.append(mss)
            elif mss['GarmentStatus'] == 'Pending for QC Verification':
                mss_pending_for_qc_verification.append(mss)
            elif mss['GarmentStatus'] == 'Transfer in at mss':
                mss_transfer_in_at_mss.append(mss)
            elif mss['GarmentStatus'] == 'QC Approved':
                mss_qc_approved.append(mss)
            elif mss['GarmentStatus'] == 'QC Rejected ':
                mss_qc_rejected.append(mss)
            elif mss['GarmentStatus'] == 'Moved Back to Mss':
                mss_moved_back_to_mss.append(mss)
            elif mss['GarmentStatus'] == 'Invoiced & Pending Delivery':
                mss_invoiced_and_pending_delivery.append(mss)
            elif mss['GarmentStatus'] == 'Under clearance of Invoice settlement':
                mss_under_clearance_of_invoice_settlement.append(mss)
            elif mss['GarmentStatus'] == 'Missing':
                mss_missing.append(mss)
            elif mss['GarmentStatus'] == 'Damaged':
                mss_damaged.append(mss)
            elif mss['GarmentStatus'] == 'Disputed Garment':
                mss_disputed_garment.append(mss)
            else:
                mss_no_stock.append(mss)



        scanned_dates = datetime.today().strftime("%d-%m-%Y %H:%M:%S %p")
        log_data = {
         'scanned_dates': scanned_dates
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        if is_mss:
            mss_tags_other_store = db.session.query(AuditTags.TagNo,AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                AuditTags.InLocation, AuditTags.GarmentStatus).filter(
            AuditTags.TagNo.in_(tag_list),
            AuditTags.GarmentBranchCode != branch_code,
            AuditTags.ScannedBy == user_id,
            AuditTags.IsNoStock == 0,
            AuditTags.IsValidTag == 1,
            AuditTags.IsDeleted == 0,
            AuditTags.IsMSS == 1,
            AuditTags.BranchCode == branch_code,
            AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
            ).group_by().all()
        else:
            mss_tags_other_store = db.session.query(AuditTags.TagNo,AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                    AuditTags.InLocation, AuditTags.GarmentStatus).filter(
                AuditTags.isScannedInMss == 1, AuditTags.TagNo.in_(tag_list),
                AuditTags.GarmentBranchCode != branch_code,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsNoStock == 0,
                AuditTags.IsValidTag == 1,
                AuditTags.IsDeleted == 0,
                AuditTags.IsMSS == 0,
                AuditTags.BranchCode == branch_code,
                AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
                ).group_by().all()

        mss_tags_other_store = [tag[0] for tag in mss_tags_other_store]
        
        if back_to_mss_tags is not None:
            back_to_mss_count = len(back_to_mss_tags)
        else:
            back_to_mss_count = 0

        if mss_tags_other_store is not None:
            mss_tags_other_store_count = len(mss_tags_other_store)
        else:
            mss_tags_other_store_count = 0

        total_scnned_branch_count = len(branch_tags) 
        if total_garment_count is not None:
            total_garment_count = int(total_garment_count)
        else:
            pass

        total_tags_scanned = len(tag_list)
        total = without_complaints_count + complaints_count
        total_scnned_branch_count = len(branch_tags)

        # print(total_scnned_branch_count)


        if total_garment_count is not None and total_scnned_branch_count is not None:
            # no_stock_count = total_garment_count - total_scnned_branch_count + back_to_mss_count
            no_stock_count = total_garment_count - total_scnned_branch_count 
            # print(no_stock_count)
        else:
            no_stock_count = total_garment_count 

        # back_to_mss_tags=list(back_to_mss_tags)
        
        # scanned_dates = datetime.today().strftime("%d-%m-%Y %H:%M:%S")
        # scanned_dates = scanned_dates.strftime("%d-%m-%Y %I:%M:%S %p")
        log_data = {
         'scanned_dates': scanned_dates,
         "without_complaints":without_complaints,
         "complaints":complaints

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        final_data = generate_final_data('DATA_SAVED')
        final_data['result'] = {'ScannedBy': username, 'WithoutComplaints': without_complaints,
                                'WithComplaints': complaints,
                                'OtherStores': other_stores, 'WithoutComplaintsCount': without_complaints_count,
                                'WithComplaintsCount': complaints_count, 'OtherStoresCount': other_stores_count,
                                'TotalGarmentCount': total_garment_count, 'TotalTagsScanned': total_tags_scanned,
                                'NoStock': no_stock_count, 'ScannedDate': scanned_dates, 'InLocation': in_location,
                                'NoStockTag': no_stock_tag,
                                'scan_id': latest_scan_id,
                                "mss_tags":back_to_mss_tags,
                                "mss_count":back_to_mss_count,
                                "mss_other_store":mss_tags_other_store,
                                "mss_other_store_count":mss_tags_other_store_count,
                                
                                }

        final_data['mss_tags'] = [{'status': 'Pending transfer out from CDC',
                                   'count': len(mss_pending_transfer_out_from_cdc),
                                   'details': mss_pending_transfer_out_from_cdc
                                   },
                                  {'status': 'In Transits to MSS',
                                   'count': len(mss_in_transit_to_mss),
                                   'details': mss_in_transit_to_mss
                                   },
                                  {'status': 'Transfer in at MSS',
                                   'count': len(mss_transfer_in_at_mss),
                                   'details': mss_transfer_in_at_mss
                                   },
                                  {'status': 'Pending for QC Verification',
                                   'count': len(mss_pending_for_qc_verification),
                                   'details': mss_pending_for_qc_verification
                                   },
                                  {'status': 'QC Approved',
                                   'count': len(mss_qc_approved),
                                   'details': mss_qc_approved
                                   },
                                  {'status': 'QC Rejected ',
                                   'count': len(mss_qc_rejected),
                                   'details': mss_qc_rejected
                                   },
                                  {'status': 'Work Order Created ',
                                   'count': len(mss_work_order_created),
                                   'details': mss_work_order_created
                                   },
                                  {'status': 'Resorted',
                                   'count': len(mss_resorted),
                                   'details': mss_resorted
                                   },
                                  {'status': 'In Transits to CDC',
                                   'count': len(mss_in_transit_to_cdc),
                                   'details': mss_in_transit_to_cdc
                                   },
                                  {'status': 'Transfer in at CDC',
                                   'count': len(mss_transfer_in_at_cdc),
                                   'details': mss_transfer_in_at_cdc
                                   },
                                  {'status': 'Invoiced & Delivered',
                                   'count': len(mss_invoiced_and_delivered),
                                   'details': mss_invoiced_and_delivered
                                   },
                                  {'status': 'Under Clearance of Invoice settlement',
                                   'count': len(mss_under_clearance_of_invoice_settlement),
                                   'details': mss_under_clearance_of_invoice_settlement
                                   },
                                  {'status': 'Missing',
                                   'count': len(mss_missing),
                                   'details': mss_missing
                                   },
                                  {'status': 'Damaged',
                                   'count': len(mss_damaged),
                                   'details': mss_damaged
                                   },
                                  {'status': 'Disputed Garment',
                                   'count': len(mss_disputed_garment),
                                   'details': mss_disputed_garment
                                   },
                                  {'status': 'Invoiced and Pending Delivery',
                                   'count': len(mss_invoiced_and_pending_delivery),
                                   'details': mss_invoiced_and_pending_delivery
                                   },
                                  {'status': 'Moved Back to Mss',
                                   'count': len(mss_moved_back_to_mss),
                                   'details': mss_moved_back_to_mss
                                   }
                                  ]
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(garment_audit_form.errors)

    return final_data


@audit_blueprint.route('get_audit_tag_details', methods=["POST"])
# @authenticate('audit')
def get_audit_tag_details():
    user_id = request.headers.get('user-id')
    # print(user_id)
    garment_audit_form = GarmentAuditDetailsForm()
    log_data = {
        
        'garment_audit_form.data': garment_audit_form.data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    if garment_audit_form.validate_on_submit():
        tag_list = None if garment_audit_form.tag_list.data == '' else garment_audit_form.tag_list.data
        branch_code = garment_audit_form.branch_code.data
        is_mss = garment_audit_form.is_mss.data
        complaints = []
        without_complaints = []
        other_stores = []
        mss_pending_transfer_out_from_cdc = []
        mss_in_transit_to_mss = []
        mss_pending_for_qc_verification = []
        mss_transfer_in_at_mss = []
        mss_qc_approved = []
        mss_qc_rejected = []
        mss_work_order_created = []
        mss_missing = []
        mss_damaged = []
        mss_resorted = []
        mss_in_transit_to_cdc = []
        mss_transfer_in_at_cdc = []
        mss_disputed_garment = []
        mss_invoiced_and_delivered = []
        mss_under_clearance_of_invoice_settlement = []
        mss_invoiced_and_pending_delivery = []
        mss_moved_back_to_mss = []
        mss_no_stock = []

        user_id = user_id.strip() if user_id else None  # Strip whitespace if it exists
        username = db.session.query(DCR_Users.Name).filter(DCR_Users.Id == user_id).one_or_none()
        # print(username)

        if username is not None:
            # Extract the first element from the tuple (assuming it's the only element)
            username = username[0]
            # print(username)
        else:
            username = None

        
        from sqlalchemy import func
        latest_scan_id = db.session.query(func.max(AuditTags.ScanId)).filter(
            AuditTags.AuditedBy == user_id,
            AuditTags.Date == date.today(), AuditTags.BranchCode == branch_code, AuditTags.IsMSS == is_mss,
            AuditTags.ScannedBy == user_id).scalar()

        # print(latest_scan_id)
        log_data = {
            'latest_scan_id': latest_scan_id,
            'garment_audit_form':garment_audit_form.data,
            "tag_list ":tag_list 
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        tag_details = db.session.query(
            AuditTags.TagNo,
            AuditTags.BranchCode,
            AuditTags.Execptionflag,
            AuditTags.GarmentBranchCode,
            AuditTags.GarmentStatus,
            AuditTags.IsDelivered,
            AuditTags.ComplaintId,
            AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
            AuditTags.InLocation, AuditTags.ScanId,
            AuditTags.IsMSS
        ).filter(
            # AuditTags.TagNo.in_(tag_list),
            AuditTags.BranchCode == branch_code,
            AuditTags.ScannedBy == user_id,
            AuditTags.IsNoStock == 0,
            AuditTags.IsValidTag == 1,
            AuditTags.IsDeleted == 0,
            AuditTags.IsMSS == is_mss,
            AuditTags.isScannedInMss == 0,
            AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
        ).group_by(
            AuditTags.TagNo,
            AuditTags.IsMSS,
            AuditTags.ScanId,
            AuditTags.Execptionflag,
            AuditTags.BranchCode,
            AuditTags.GarmentBranchCode,
            AuditTags.GarmentStatus,
            AuditTags.IsDelivered,
            AuditTags.ComplaintId,
            AuditTags.RecordLastUpdatedDate,
            AuditTags.InLocation
        ).all()

        # print(tag_details)
        # print("Fetched Tag Details1:", tag_details)
        tag_details = SerializeSQLAResult(tag_details).serialize(full_date_fields=['ScannedDate'])
        log_data = {
            'tag_details__': tag_details
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        # print("Fetched Tag Details:", tag_details)
        # last_tag = tag_details[-1]
        # ScannedDate=last_tag['ScannedDate']
        branch_tags = []
        scanned_dates = []
        in_location = False
        scanned_dates = ''
        for tag in tag_details:
            scanned_dates = tag['ScannedDate']
            # print(scanned_date)
            in_location = tag['InLocation']
            # print(tag['GarmentBranchCode'])
            if tag['GarmentBranchCode'] == branch_code and tag['Execptionflag'] == 0:
                # print("hai")
                # print(tag['GarmentBranchCode'])
                # print(tag['GarmentStatus'])
                if tag['GarmentStatus'] == 'In Transits to CDC':
                    branch_tags.append(tag['TagNo'])
                    # print(branch_tags)
                elif tag['GarmentStatus'] == 'Pending Transfer Out From CDC':
                    branch_tags.append(tag['TagNo'])
                    # print(branch_tags)
                elif tag['GarmentStatus'] == 'Transfer in at CDC':
                    branch_tags.append(tag['TagNo'])
                    # print(branch_tags)
                elif tag['GarmentStatus'] == 'Invoiced & Delivered' and tag['IsDelivered'] in ('Un-Delivered'):
                     branch_tags.append(tag['TagNo'])
                    # print(branch_tags)
                else:
                    pass

            if tag['ComplaintId'] is None and tag['GarmentBranchCode'] == branch_code:
                # print(branch_code)
                without_complaints.append(tag['TagNo'])
                # print(without_complaints)
            elif tag['ComplaintId'] is not None and tag['GarmentBranchCode'] == branch_code:
                complaints.append(tag['TagNo'])
                # print("tag",complaints)
            elif tag['GarmentBranchCode'] != branch_code:
                other_stores.append(tag['TagNo'])
            else:
                pass

        no_stock_tag_details = db.session.query(AuditTags.TagNo, AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                AuditTags.InLocation, AuditTags.GarmentStatus
                                                ).filter(AuditTags.BranchCode == branch_code,
                                                         AuditTags.IsNoStock == 1, 
                                                         AuditTags.IsMSS == is_mss,
                                                         AuditTags.IsValidTag == 1, AuditTags.IsDeleted == 0,
                                                         AuditTags.Date == date.today(),
                                                         AuditTags.ScanId == latest_scan_id,
                                                         AuditTags.Execptionflag == 0,
                                                         AuditTags.isScannedInMss == 0,
                                                         AuditTags.AuditedBy == user_id,
                                                         or_(
                                                            AuditTags.GarmentStatus.in_(['In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC']),
                                                            and_(
                                                                AuditTags.GarmentStatus == 'Invoiced & Delivered',
                                                                AuditTags.IsDelivered == 'Un-Delivered'
                                                                )
                                                            )
                                                        ).all()
        no_stock_tags = SerializeSQLAResult(no_stock_tag_details).serialize(full_date_fields=['ScannedDate'])
        # print("Fetched Tag Details:", no_stock_tags)
        no_stock_tag = []
        for nostock_tag in no_stock_tags:
            # print(nostock_tag)
            scanned_date = nostock_tag['ScannedDate']
            # print("scanned_date",scanned_date)
            in_location = nostock_tag['InLocation']
            no_stock_tag.append(nostock_tag["TagNo"])
        # print(len(no_stock_tag))
        # no_stock_tag = [item[0] for item in no_stock_tag_details]
        without_complaints = set(without_complaints)
        without_complaints = list(without_complaints)
        without_complaints_count = len(without_complaints)
        complaints_count = len(complaints)
        other_stores_count = len(other_stores)
        # print(date.today())
        # total_garment_count = db.session.query(AuditGarmentCount).filter(
        #     AuditGarmentCount.Date == date.today(), AuditGarmentCount.BranchCode == branch_code).one_or_none()
        try:
            # scan_id_qry = """SELECT GarmentCount AS AuditGarmentCount FROM AuditGarmentCount WHERE ScanId= (SELECT MAX(ScanId) FROM AuditGarmentCount WHERE CONVERT(DATE, Date) = CONVERT(DATE, GETDATE()) and BranchCode=:branch_code AND AuditedBy=:user_id) and  CONVERT(DATE, Date) = CONVERT(DATE, GETDATE()) and BranchCode=:branch_code AND AuditedBy=:user_id"""
            # # SELECT garmntNo FROM table1 WHERE id = (SELECT MAX(id) FROM table1 WHERE branchcode = 1)
            
            #  scan_id_qry modified on 31-jul-2024 
            scan_id_qry = """SELECT count(distinct TagNo) FROM  AuditTags WHERE 
                            ScanId= (SELECT MAX(ScanId) FROM AuditTags WHERE CONVERT(DATE, Date) = CONVERT(DATE, GETDATE()) 
                            and BranchCode=:branch_code AND AuditedBy=:user_id) 
                            and  CONVERT(DATE, Date) = CONVERT(DATE, GETDATE()) 
                            and BranchCode=:branch_code AND AuditedBy=:user_id
                            AND  Execptionflag = 0 AND   IsDeleted = 0 AND  IsValidTag = 1 AND   IsMSS = 0 AND  isScannedInMss = 0 AND 
                            GarmentBranchCode = :branch_code AND
                            (
                                GarmentStatus IN ('In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC')
                                OR (GarmentStatus = 'Invoiced & Delivered' AND IsDelivered = 'Un-Delivered')
                            )"""

            result = db.session.execute(text(scan_id_qry),
                                        {'branch_code': branch_code, 'user_id': user_id})
            total_garment_count = result.scalar()

            log_data = {
            'total_garment_count': total_garment_count
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))

            # print(total_garment_count)
        except Exception as ex:
            print(ex)

        # print(total_garment_count.GarmentCount)
        # total_garment_count = int(total_garment_count.GarmentCount)

        # last modification
        # if total_garment_count is not None:
        #     total_garment_count = int(total_garment_count)
        # else:
        #     pass
        if is_mss:
            back_to_mss_tags1 = db.session.query(AuditTags.TagNo, AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                AuditTags.InLocation, AuditTags.GarmentStatus).filter(
                AuditTags.TagNo.in_(tag_list),
                AuditTags.BranchCode == branch_code,
                AuditTags.GarmentBranchCode == branch_code,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsNoStock == 0,
                AuditTags.IsValidTag == 1,
                AuditTags.IsDeleted == 0,
                # AuditTags.isScannedInMss == 1,
                AuditTags.IsMSS == is_mss,
                AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
            ).group_by().all()
        else:
            back_to_mss_tags1 = db.session.query(AuditTags.TagNo,AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                    AuditTags.InLocation, AuditTags.GarmentStatus).filter(
                # AuditTags.TagNo.in_(tag_list),
                AuditTags.BranchCode == branch_code,
                AuditTags.GarmentBranchCode == branch_code,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsNoStock == 0,
                AuditTags.IsValidTag == 1,
                AuditTags.IsDeleted == 0,
                AuditTags.isScannedInMss==1,
                AuditTags.IsMSS==0,
                AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
            ).group_by().all()

        back_to_mss_tags = [tag[0] for tag in back_to_mss_tags1]

        mss_tag_details = SerializeSQLAResult(back_to_mss_tags1).serialize(full_date_fields=['ScannedDate'])

        for mss in mss_tag_details:
            if mss['GarmentStatus'] == 'In Transits to CDC':
                mss_in_transit_to_cdc.append(mss)
            elif mss['GarmentStatus'] == 'Resorted':
                mss_resorted.append(mss)
            elif mss['GarmentStatus'] == 'Work Order Created ':
                mss_work_order_created.append(mss)
            elif mss['GarmentStatus'] == 'In Transits to mss':
                mss_in_transit_to_mss.append(mss)
            elif mss['GarmentStatus'] == 'Pending Transfer Out From CDC':
                mss_pending_transfer_out_from_cdc.append(mss)
            elif mss['GarmentStatus'] == 'Invoiced & Delivered':
                mss_invoiced_and_delivered.append(mss)
            elif mss['GarmentStatus'] == 'Transfer in at CDC':
                mss_transfer_in_at_cdc.append(mss)
            elif mss['GarmentStatus'] == 'Pending for QC Verification':
                mss_pending_for_qc_verification.append(mss)
            elif mss['GarmentStatus'] == 'Transfer in at mss':
                mss_transfer_in_at_mss.append(mss)
            elif mss['GarmentStatus'] == 'QC Approved':
                mss_qc_approved.append(mss)
            elif mss['GarmentStatus'] == 'QC Rejected ':
                mss_qc_rejected.append(mss)
            elif mss['GarmentStatus'] == 'Moved Back to Mss':
                mss_moved_back_to_mss.append(mss)
            elif mss['GarmentStatus'] == 'Invoiced & Pending Delivery':
                mss_invoiced_and_pending_delivery.append(mss)
            elif mss['GarmentStatus'] == 'Under clearance of Invoice settlement':
                mss_under_clearance_of_invoice_settlement.append(mss)
            elif mss['GarmentStatus'] == 'Missing':
                mss_missing.append(mss)
            elif mss['GarmentStatus'] == 'Damaged':
                mss_damaged.append(mss)
            elif mss['GarmentStatus'] == 'Disputed Garment':
                mss_disputed_garment.append(mss)
            else:
                mss_no_stock.append(mss)



        scanned_dates = datetime.today().strftime("%d-%m-%Y %H:%M:%S %p")
        log_data = {
         'scanned_dates': scanned_dates
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        if is_mss:
            mss_tags_other_store = db.session.query(AuditTags.TagNo,AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                AuditTags.InLocation, AuditTags.GarmentStatus).filter(
            AuditTags.TagNo.in_(tag_list),
            AuditTags.GarmentBranchCode != branch_code,
            AuditTags.ScannedBy == user_id,
            AuditTags.IsNoStock == 0,
            AuditTags.IsValidTag == 1,
            AuditTags.IsDeleted == 0,
            AuditTags.IsMSS == 1,
            AuditTags.BranchCode == branch_code,
            AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
            ).group_by().all()
        else:
            mss_tags_other_store = db.session.query(AuditTags.TagNo,AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                                    AuditTags.InLocation, AuditTags.GarmentStatus).filter(
                AuditTags.isScannedInMss == 1,
                 # AuditTags.TagNo.in_(tag_list),
                AuditTags.GarmentBranchCode != branch_code,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsNoStock == 0,
                AuditTags.IsValidTag == 1,
                AuditTags.IsDeleted == 0,
                AuditTags.IsMSS == 0,
                AuditTags.BranchCode == branch_code,
                AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
                ).group_by().all()

        mss_tags_other_store = [tag[0] for tag in mss_tags_other_store]
        
        if back_to_mss_tags is not None:
            back_to_mss_count = len(back_to_mss_tags)
        else:
            back_to_mss_count = 0

        if mss_tags_other_store is not None:
            mss_tags_other_store_count = len(mss_tags_other_store)
        else:
            mss_tags_other_store_count = 0

        total_scnned_branch_count = len(branch_tags) 
        if total_garment_count is not None:
            total_garment_count = int(total_garment_count)
        else:
            pass

        total_tags_scanned = len(tag_list)
        total = without_complaints_count + complaints_count
        total_scnned_branch_count = len(branch_tags)

        # print(total_scnned_branch_count)


        if total_garment_count is not None and total_scnned_branch_count is not None:
            # no_stock_count = total_garment_count - total_scnned_branch_count + back_to_mss_count
            no_stock_count = total_garment_count - total_scnned_branch_count 
        else:
            no_stock_count = total_garment_count 

        # back_to_mss_tags=list(back_to_mss_tags)
        
        # scanned_dates = datetime.today().strftime("%d-%m-%Y %H:%M:%S")
        # scanned_dates = scanned_dates.strftime("%d-%m-%Y %I:%M:%S %p")
        log_data = {
         'scanned_dates': scanned_dates,
         "without_complaints":without_complaints,
         "complaints":complaints

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))


        final_data = generate_final_data('DATA_SAVED')
        final_data['result'] = {'ScannedBy': username, 'WithoutComplaints': without_complaints,
                                'WithComplaints': complaints,
                                'OtherStores': other_stores, 'WithoutComplaintsCount': without_complaints_count,
                                'WithComplaintsCount': complaints_count, 'OtherStoresCount': other_stores_count,
                                'TotalGarmentCount': total_garment_count, 'TotalTagsScanned': total_tags_scanned,
                                'NoStock': len(no_stock_tags), 'ScannedDate': scanned_dates, 'InLocation': in_location,
                                'NoStockTag': no_stock_tag,
                                'scan_id': latest_scan_id,
                                "mss_tags":back_to_mss_tags,
                                "mss_count":back_to_mss_count,
                                "mss_other_store":mss_tags_other_store,
                                "mss_other_store_count":mss_tags_other_store_count,
                                
                                }

        final_data['mss_tags'] = [{'status': 'Pending transfer out from CDC',
                                   'count': len(mss_pending_transfer_out_from_cdc),
                                   'details': mss_pending_transfer_out_from_cdc
                                   },
                                  {'status': 'In Transits to MSS',
                                   'count': len(mss_in_transit_to_mss),
                                   'details': mss_in_transit_to_mss
                                   },
                                  {'status': 'Transfer in at MSS',
                                   'count': len(mss_transfer_in_at_mss),
                                   'details': mss_transfer_in_at_mss
                                   },
                                  {'status': 'Pending for QC Verification',
                                   'count': len(mss_pending_for_qc_verification),
                                   'details': mss_pending_for_qc_verification
                                   },
                                  {'status': 'QC Approved',
                                   'count': len(mss_qc_approved),
                                   'details': mss_qc_approved
                                   },
                                  {'status': 'QC Rejected ',
                                   'count': len(mss_qc_rejected),
                                   'details': mss_qc_rejected
                                   },
                                  {'status': 'Work Order Created ',
                                   'count': len(mss_work_order_created),
                                   'details': mss_work_order_created
                                   },
                                  {'status': 'Resorted',
                                   'count': len(mss_resorted),
                                   'details': mss_resorted
                                   },
                                  {'status': 'In Transits to CDC',
                                   'count': len(mss_in_transit_to_cdc),
                                   'details': mss_in_transit_to_cdc
                                   },
                                  {'status': 'Transfer in at CDC',
                                   'count': len(mss_transfer_in_at_cdc),
                                   'details': mss_transfer_in_at_cdc
                                   },
                                  {'status': 'Invoiced & Delivered',
                                   'count': len(mss_invoiced_and_delivered),
                                   'details': mss_invoiced_and_delivered
                                   },
                                  {'status': 'Under Clearance of Invoice settlement',
                                   'count': len(mss_under_clearance_of_invoice_settlement),
                                   'details': mss_under_clearance_of_invoice_settlement
                                   },
                                  {'status': 'Missing',
                                   'count': len(mss_missing),
                                   'details': mss_missing
                                   },
                                  {'status': 'Damaged',
                                   'count': len(mss_damaged),
                                   'details': mss_damaged
                                   },
                                  {'status': 'Disputed Garment',
                                   'count': len(mss_disputed_garment),
                                   'details': mss_disputed_garment
                                   },
                                  {'status': 'Invoiced and Pending Delivery',
                                   'count': len(mss_invoiced_and_pending_delivery),
                                   'details': mss_invoiced_and_pending_delivery
                                   },
                                  {'status': 'Moved Back to Mss',
                                   'count': len(mss_moved_back_to_mss),
                                   'details': mss_moved_back_to_mss
                                   }
                                  ]
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(garment_audit_form.errors)

    return final_data



@audit_blueprint.route('get_audit_tag_detailsmss', methods=["POST"])
# @authenticate('audit')
def get_audit_tag_detailsmss():
    user_id = request.headers.get('user-id')
    garment_audit_form = GarmentAuditDetailsForm()
    log_data = {
        'GarmentAuditDetailsForm': garment_audit_form.data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    # print(garment_audit_form)
    mss_pending_transfer_out_from_cdc = []
    mss_in_transit_to_mss = []
    mss_pending_for_qc_verification = []
    mss_transfer_in_at_mss = []
    mss_qc_approved = []
    mss_qc_rejected = []
    mss_work_order_created = []
    mss_missing = []
    mss_damaged = []
    mss_resorted = []
    mss_in_transit_to_cdc = []
    mss_transfer_in_at_cdc = []
    mss_disputed_garment = []
    mss_invoiced_and_delivered = []
    mss_under_clearance_of_invoice_settlement = []
    mss_invoiced_and_pending_delivery = []
    mss_moved_back_to_mss = []
    mss_no_stock = []

    mss_other_pending_transfer_out_from_cdc = []
    mss_other_in_transit_to_mss = []
    mss_other_pending_for_qc_verification = []
    mss_other_transfer_in_at_mss = []
    mss_other_qc_approved = []
    mss_other_qc_rejected = []
    mss_other_work_order_created = []
    mss_other_missing = []
    mss_other_damaged = []
    mss_other_resorted = []
    mss_other_in_transit_to_cdc = []
    mss_other_transfer_in_at_cdc = []
    mss_other_disputed_garment = []
    mss_other_invoiced_and_delivered = []
    mss_other_under_clearance_of_invoice_settlement = []
    mss_other_invoiced_and_pending_delivery = []
    mss_other_moved_back_to_mss = []
    other_work_order_created = []
    scanned_dates = datetime.today().strftime("%d-%m-%Y %H:%M:%S %p")


    if garment_audit_form.validate_on_submit():
        tag_list = None if garment_audit_form.tag_list.data == '' else garment_audit_form.tag_list.data
        # print(tag_list)
        branch_code = garment_audit_form.branch_code.data
        is_mss = garment_audit_form.is_mss.data
        in_location = False
        user_id = user_id.strip() if user_id else None  # Strip whitespace if it exists
        username = db.session.query(DCR_Users.Name).filter(DCR_Users.Id == user_id).one_or_none()
        # print(username)
        total_tag_scanned = len(tag_list)
        if username is not None:
            # Extract the first element from the tuple (assuming it's the only element)
            username = username[0]
            # print(username)
        else:
            username = None
        from sqlalchemy import func
        latest_scan_id = db.session.query(func.max(AuditTags.ScanId)).filter(
            AuditTags.AuditedBy == user_id,
            AuditTags.Date == date.today(), AuditTags.BranchCode == branch_code, AuditTags.IsMSS == is_mss,
            AuditTags.ScannedBy == user_id).scalar()
        # print(latest_scan_id)
        
        latest_scan_id = db.session.query(func.max(AuditTags.ScanId)).filter(
            AuditTags.AuditedBy == user_id,
            AuditTags.Date == date.today(), AuditTags.BranchCode == branch_code, AuditTags.IsMSS == is_mss,
            AuditTags.ScannedBy == user_id).scalar()
        # print(latest_scan_id)

        back_to_mss_tags = db.session.query(
            AuditTags.TagNo,
            AuditTags.BranchCode,
            AuditTags.Execptionflag,
            AuditTags.GarmentBranchCode,
            AuditTags.GarmentStatus,
            AuditTags.IsDelivered,
            AuditTags.ComplaintId,
            AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
            AuditTags.InLocation, AuditTags.ScanId,
            AuditTags.IsMSS,
            AuditTags.BranchName
        ).filter(
            AuditTags.TagNo.in_(tag_list),
            AuditTags.BranchCode == branch_code,
            AuditTags.ScannedBy == user_id,
            AuditTags.IsNoStock == 0,
            AuditTags.IsValidTag == 1,
            AuditTags.IsDeleted == 0,
            AuditTags.GarmentBranchCode == branch_code,
            AuditTags.IsMSS == is_mss,
            # AuditTags.isScannedInMss == 0,
            AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
        ).group_by(
            AuditTags.TagNo,
            AuditTags.IsMSS,
            AuditTags.ScanId,
            AuditTags.Execptionflag,
            AuditTags.BranchCode,
            AuditTags.GarmentBranchCode,
            AuditTags.GarmentStatus,
            AuditTags.IsDelivered,
            AuditTags.ComplaintId,
            AuditTags.RecordLastUpdatedDate,
            AuditTags.InLocation,
            AuditTags.BranchName,
        ).all()
        mss_tags = [tag.TagNo for tag in back_to_mss_tags]
        mss_count =len(mss_tags)
        mss_tag_details = SerializeSQLAResult(back_to_mss_tags).serialize(full_date_fields=['ScannedDate'])

        
        for mss in mss_tag_details:
            in_location = mss['InLocation']
            # log_data = {
            #     'garment status': mss['GarmentStatus']
            # }
            # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            if mss['GarmentStatus'] == 'In Transits to CDC':
                mss_in_transit_to_cdc.append(mss)
            elif mss['GarmentStatus'] == 'Resorted':
                mss_resorted.append(mss)
            elif mss['GarmentStatus'] == 'Work Order Created ':
                mss_work_order_created.append(mss)
            elif mss['GarmentStatus'] == 'In Transits to mss':
                mss_in_transit_to_mss.append(mss)
            elif mss['GarmentStatus'] == 'Pending Transfer Out From CDC':
                mss_pending_transfer_out_from_cdc.append(mss)
            elif mss['GarmentStatus'] == 'Invoiced & Delivered':
                mss_invoiced_and_delivered.append(mss)
            elif mss['GarmentStatus'] == 'Transfer in at CDC':
                mss_transfer_in_at_cdc.append(mss)
            elif mss['GarmentStatus'] == 'Pending for QC Verification':
                mss_pending_for_qc_verification.append(mss)
            elif mss['GarmentStatus'] == 'Transfer in at mss':
                mss_transfer_in_at_mss.append(mss)
            elif mss['GarmentStatus'] == 'QC Approved':
                mss_qc_approved.append(mss)
            elif mss['GarmentStatus'] == 'QC Rejected ':
                mss_qc_rejected.append(mss)
            elif mss['GarmentStatus'] == 'Moved Back to Mss':
                mss_moved_back_to_mss.append(mss)
            elif mss['GarmentStatus'] == 'Invoiced & Pending Delivery':
                mss_invoiced_and_pending_delivery.append(mss)
            elif mss['GarmentStatus'] == 'Under clearance of Invoice settlement':
                mss_under_clearance_of_invoice_settlement.append(mss)
            elif mss['GarmentStatus'] == 'Missing':
                mss_missing.append(mss)
            elif mss['GarmentStatus'] == 'Damaged':
                mss_damaged.append(mss)
            elif mss['GarmentStatus'] == 'Disputed Garment':
                mss_disputed_garment.append(mss)
            else:
                mss_no_stock.append(mss)

        back_to_mss_tags = db.session.query(
            AuditTags.TagNo,
            AuditTags.BranchCode,
            AuditTags.Execptionflag,
            AuditTags.GarmentBranchCode,
            AuditTags.GarmentStatus,
            AuditTags.IsDelivered,
            AuditTags.ComplaintId,
            AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
            AuditTags.InLocation, AuditTags.ScanId,
            AuditTags.IsMSS,
            AuditTags.BranchName,
            AuditTags.GarmentBranchName
        ).filter(
            AuditTags.TagNo.in_(tag_list),
            AuditTags.BranchCode == branch_code,
            AuditTags.ScannedBy == user_id,
            AuditTags.IsNoStock == 0,
            AuditTags.GarmentBranchCode != branch_code,
            AuditTags.IsValidTag == 1,
            AuditTags.IsDeleted == 0,
            AuditTags.IsMSS == is_mss,
            # AuditTags.isScannedInMss == 0,
            AuditTags.Date == date.today(), AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id
        ).group_by(
            AuditTags.BranchName,
            AuditTags.TagNo,
            AuditTags.GarmentBranchName,
            AuditTags.IsMSS,
            AuditTags.ScanId,
            AuditTags.Execptionflag,
            AuditTags.BranchCode,
            AuditTags.GarmentBranchCode,
            AuditTags.GarmentStatus,
            AuditTags.IsDelivered,
            AuditTags.ComplaintId,
            AuditTags.RecordLastUpdatedDate,
            AuditTags.InLocation
        ).all()
        branch_codes = [tag.GarmentBranchCode for tag in back_to_mss_tags]
        print(branch_codes)

        mss_other_store = [tag.TagNo for tag in back_to_mss_tags]
        mss_other_store_count = len(mss_other_store)


        mss_tag_details_other_store = SerializeSQLAResult(back_to_mss_tags).serialize(full_date_fields=['ScannedDate'])
        for mss_other in mss_tag_details_other_store:
            in_location = mss_other['InLocation']
            # for mss_other in back_to_mss_tags:
            if mss_other['GarmentStatus'] == 'In Transits to CDC':
                mss_other_in_transit_to_cdc.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Resorted':
                mss_other_resorted.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Work Order Created ':
                mss_other_work_order_created.append(mss_other)
            elif mss_other['GarmentStatus'] == 'In Transits to mss':
                mss_other_in_transit_to_mss.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Pending Transfer Out From CDC':
                mss_other_pending_transfer_out_from_cdc.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Invoiced & Delivered':
                mss_other_invoiced_and_delivered.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Transfer in at CDC':
                mss_other_transfer_in_at_cdc.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Pending for QC Verification':
                mss_other_pending_for_qc_verification.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Transfer in at mss':
                mss_other_transfer_in_at_mss.append(mss_other)
            elif mss_other['GarmentStatus'] == 'QC Approved':
                mss_other_qc_approved.append(mss_other)
            elif mss_other['GarmentStatus'] == 'QC Rejected ':
                mss_other_qc_rejected.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Moved Back to Mss':
                mss_other_moved_back_to_mss.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Invoiced & Pending Delivery':
                mss_other_invoiced_and_pending_delivery.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Under clearance of Invoice settlement':
                mss_other_under_clearance_of_invoice_settlement.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Missing':
                mss_other_missing.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Damaged':
                mss_other_damaged.append(mss_other)
            elif mss_other['GarmentStatus'] == 'Disputed Garment':
                mss_other_disputed_garment.append(mss_other)
            else:
                mss_other_no_stock.append(mss_other)
        branch_codes = branch_codes


        final_data = generate_final_data('DATA_SAVED')
        final_data['result'] = {"TotalTagsScanned" : total_tag_scanned,
                                "ScannedDate": scanned_dates,
                                "InLocation": in_location,
                                "scan_id":latest_scan_id,
                                "ScannedBy":username,
                                "mss_count":mss_count,
                                "mss_tags":mss_tags,
                                "mss_other_store":mss_other_store,
                                "mss_other_store_count":mss_other_store_count

                                    }
            
        final_data["mssTags"] = [
                    {
                        'status': 'Pending transfer out from CDC',
                        'count': len(mss_pending_transfer_out_from_cdc),
                        'details': mss_pending_transfer_out_from_cdc
                    },
                    {
                        'status': 'In Transits to MSS',
                        'count': len(mss_in_transit_to_mss),
                        'details': mss_in_transit_to_mss
                    },
                    {
                        'status': 'Transfer in at MSS',
                        'count': len(mss_transfer_in_at_mss),
                        'details': mss_transfer_in_at_mss
                    },
                    {
                        'status': 'Pending for QC Verification',
                        'count': len(mss_pending_for_qc_verification),
                        'details': mss_pending_for_qc_verification
                    },
                    {
                        'status': 'QC Approved',
                        'count': len(mss_qc_approved),
                        'details': mss_qc_approved
                    },
                    {
                        'status': 'QC Rejected ',
                        'count': len(mss_qc_rejected),
                        'details': mss_qc_rejected
                    },
                    {
                        'status': 'Work Order Created ',
                        'count': len(mss_work_order_created),
                        'details': mss_work_order_created
                    },
                    {
                        'status': 'Resorted',
                        'count': len(mss_resorted),
                        'details': mss_resorted
                    },
                    {
                        'status': 'In Transits to CDC',
                        'count': len(mss_in_transit_to_cdc),
                        'details': mss_in_transit_to_cdc
                    },
                    {
                        'status': 'Transfer in at CDC',
                        'count': len(mss_transfer_in_at_cdc),
                        'details': mss_transfer_in_at_cdc
                    },
                    {
                        'status': 'Invoiced & Delivered',
                        'count': len(mss_invoiced_and_delivered),
                        'details': mss_invoiced_and_delivered
                    },
                    {
                        'status': 'Under Clearance of Invoice settlement',
                        'count': len(mss_under_clearance_of_invoice_settlement),
                        'details': mss_under_clearance_of_invoice_settlement
                    },
                    {
                        'status': 'Missing',
                        'count': len(mss_missing),
                        'details': mss_missing
                    },
                    {
                        'status': 'Damaged',
                        'count': len(mss_damaged),
                        'details': mss_damaged
                    },
                    {
                        'status': 'Disputed Garment',
                        'count': len(mss_disputed_garment),
                        'details': mss_disputed_garment
                    },
                    {
                        'status': 'Invoiced and Pending Delivery',
                        'count': len(mss_invoiced_and_pending_delivery),
                        'details': mss_invoiced_and_pending_delivery
                    },
                    {
                        'status': 'Moved Back to Mss',
                        'count': len(mss_moved_back_to_mss),
                        'details': mss_moved_back_to_mss
                    }
                ]
            
        
        final_data['mss other store'] = [
            {
                'status': 'Pending transfer out from CDC',
                'count': len(mss_other_pending_transfer_out_from_cdc),
                'details': mss_other_pending_transfer_out_from_cdc
            },
            {
                'status': 'In Transits to MSS',
                'count': len(mss_other_in_transit_to_mss),
                'details': mss_other_in_transit_to_mss
            },
            {
                'status': 'Transfer in at MSS',
                'count': len(mss_other_transfer_in_at_mss),
                'details': mss_other_transfer_in_at_mss
            },
            {
                'status': 'Pending for QC Verification',
                'count': len(mss_other_pending_for_qc_verification),
                'details': mss_other_pending_for_qc_verification
            },
            {
                'status': 'QC Approved',
                'count': len(mss_other_qc_approved),
                'details': mss_other_qc_approved
            },
            {
                'status': 'QC Rejected ',
                'count': len(mss_other_qc_rejected),
                'details': mss_other_qc_rejected
            },
            {
                'status': 'Work Order Created ',
                'count': len(mss_other_work_order_created),
                'details': mss_other_work_order_created
            },
            {
                'status': 'Resorted',
                'count': len(mss_other_resorted),
                'details': mss_other_resorted
            },
            {
                'status': 'In Transits to CDC',
                'count': len(mss_other_in_transit_to_cdc),
                'details': mss_other_in_transit_to_cdc
            },
            {
                'status': 'Transfer in at CDC',
                'count': len(mss_other_transfer_in_at_cdc),
                'details': mss_other_transfer_in_at_cdc
            },
            {
                'status': 'Invoiced & Delivered',
                'count': len(mss_other_invoiced_and_delivered),
                'details': mss_other_invoiced_and_delivered
            },
            {
                'status': 'Under Clearance of Invoice settlement',
                'count': len(mss_other_under_clearance_of_invoice_settlement),
                'details': mss_other_under_clearance_of_invoice_settlement
            },
            {
                'status': 'Missing',
                'count': len(mss_other_missing),
                'details': mss_other_missing
            },
            {
                'status': 'Damaged',
                'count': len(mss_other_damaged),
                'details': mss_other_damaged
            },
            {
                'status': 'Disputed Garment',
                'count': len(mss_other_disputed_garment),
                'details': mss_other_disputed_garment
            },
            {
                'status': 'Invoiced and Pending Delivery',
                'count': len(mss_other_invoiced_and_pending_delivery),
                'details': mss_other_invoiced_and_pending_delivery
            },
            {
                'status': 'Moved Back to Mss',
                'count': len(mss_other_moved_back_to_mss),
                'details': mss_other_moved_back_to_mss
            }
        ]

        # categorized_results = {}
        # for entry in final_data['mss other store']:
        #     status = entry['status']
        #     if entry['details']:
        #         for detail in entry['details']:
        #             branch_code = detail.get('GarmentBranchName')
        #             if branch_code:
        #                 if branch_code not in categorized_results:
        #                     categorized_results[branch_code] = {'details': [], 'status_counts': {}}

        #                 categorized_results[branch_code]['details'].append(detail)
        #                 if status in categorized_results[branch_code]['status_counts']:
        #                     categorized_results[branch_code]['status_counts'][status] += 1
        #                 else:
        #                     categorized_results[branch_code]['status_counts'][status] = 1

        # # Convert categorized_results to a list of dictionaries for response format consistency
        # mss_other_store_data = [{
        #     "branch name": branch_code,
        #     "count": len(data['details']),
        #     "details": data['details'],
        #     "status counts": data['status_counts']
        # } for branch_code, data in categorized_results.items()]
        categorized_results = {}

        # Iterate over each entry in final_data['mss other store']
        for entry in final_data.get('mss other store', []):
            # Ensure that details contain entries
            if entry.get('details'):
                for detail in entry['details']:
                    # Extract the branch code from the detail dictionary
                    branch_name = detail.get('GarmentBranchName')
                    if branch_name:
                        # Initialize the branch entry if it doesn't exist
                        if branch_name not in categorized_results:
                            categorized_results[branch_name] = {
                                "branch": branch_name,
                                "count": 0,
                                "details": []
                            }
                        # Increment the count for the branch
                        categorized_results[branch_name]["count"] += 1

                        # Add status details
                        status = detail.get('GarmentStatus')
                        status_entry = next(
                            (item for item in categorized_results[branch_name]["details"] if item["status"] == status),
                            None)
                        if not status_entry:
                            status_entry = {
                                "status": status,
                                "count": 0,
                                "details": []
                            }
                            categorized_results[branch_name]["details"].append(status_entry)

                        status_entry["count"] += 1
                        status_entry["details"].append(detail)

        # Convert categorized_results to the desired format
        mss_other_store_data = list(categorized_results.values())

        
        final_data['mss other store data'] = mss_other_store_data
        log_data = {
            'GarmentAuditDetailsResponse': final_data
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(garment_audit_form.errors)

    return final_data


@audit_blueprint.route('get_complaint_history', methods=["POST"])
# @authenticate('audit')
def get_complaint_history():
    user_id = request.headers.get('user-id')
    complaint_hostory_form = ComplaintHistoryForm()
    log_data = {
        "complaint_historyReqbdy":complaint_hostory_form.data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    # for complaints in complaint_history:
    if complaint_hostory_form.validate_on_submit():
        branch_code = complaint_hostory_form.branch_code.data
        complaint_date = None if complaint_hostory_form.complaint_date.data == '' else complaint_hostory_form.complaint_date.data
        start_date = None if complaint_hostory_form.start_date.data == '' else complaint_hostory_form.start_date.data
        end_date = None if complaint_hostory_form.end_date.data == '' else complaint_hostory_form.end_date.data
        if start_date is not None:
            start_date_obj = datetime.strptime(start_date, "%d-%m-%Y")
            formatted_start_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            end_date_obj = datetime.strptime(end_date, "%d-%m-%Y")
            # formatted_end_date = (end_date_obj + timedelta(1)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date = end_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        else:
            formatted_start_date = (datetime.today() - timedelta(10)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date = get_current_date()

        # if complaint_date is not None:
        #     complaint_date = datetime.strptime(complaint_date, "%d-%m-%Y")
        #     complaint_date = complaint_date.strftime("%Y-%m-%d %H:%M:%S")
        base_complaint_history = db.session.query(StoreAudits.Id,StoreAudits.RecordCreatedDate,StoreAudits.Remarks, Audit_Complaints.AuditQuestions,StoreAudits.InLocation,
                                                  StoreAudits.IsYesNo, Audit_Complaints.IsYesNoRequired
                                                  ).join(
            Audit_Complaints, Audit_Complaints.Id == StoreAudits.ComplaintId)

     

   
        # if complaint_date is not None:
        #     complaint_history = base_complaint_history.filter(
        #         StoreAudits.AuditDate == complaint_date, StoreAudits.BranchCode == branch_code,
        #         StoreAudits.AuditedBy == user_id).all()
        # else:
        complaint_history = base_complaint_history.filter(
            StoreAudits.BranchCode == branch_code,
            StoreAudits.AuditedBy == user_id, StoreAudits.AuditDate.between(
                formatted_start_date, formatted_end_date)).all()
        complaint_history = SerializeSQLAResult_(complaint_history).serialize_()

        log_data = {
        "complaint_history":complaint_history
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        # for complaints in complaint_history:
        #
        #     lat1=complaints.get('lat')
        #     long1=complaints.get('long')
        #     lat=float(lat1)
        #     long_=float(long1)
        #     branch_details = f"EXEC {SERVER_DB}.dbo.GetBranchInfoforDCR @branchcode = {branch_code}"
        #     branch_details = CallSP(branch_details).execute().fetchone()
        #
        #     query = f"EXEC {SERVER_DB}.dbo.sp_GetAllBranchDetails"
        #     result = CallSP(query).execute().fetchall()
            # distance=0
            # for branch in result:
            #     if branch['BranchCode'] == branch_code:
            #         if branch['Lat'] is not None:
            #             branch_lat = float(branch['Lat'])
            #             print(branch_lat)
            #             branch_long = float(branch['Long'])
            #             print(branch_long)
            #             loc1 = (branch_lat, branch_long)
            #             loc2 = (lat, long_)
            #             distance = hs.haversine(loc1, loc2)
            #         else:
            #             permission = db.session.query(DCR_Users.audit_store_access_limit).filter(
            #                 DCR_Users.Id == user_id).one_or_none()

            #             if permission.audit_store_access_limit == 1:
            #                 distance = 0
            #             else:
            #                 distance = 1
            # if distance <= 0.1:
            #     in_location = 1
            # else:
            #     in_location = 0

        for complaint in complaint_history:
            photos = db.session.query(AuditPhotos.AuditImage,AuditPhotos.RecordCreatedDate).filter(
                AuditPhotos.StoreAuditId == complaint['Id']).all()
            images = SerializeSQLAResult_(photos).serialize_()
            complaint['Images'] = images
            attachments = db.session.query(AuditAttachements.AuditAttachement,AuditAttachements.RecordCreatedDate).filter(
                AuditAttachements.StoreAuditId == complaint['Id']).all()
            files = SerializeSQLAResult_(attachments).serialize_()
            complaint['files'] = files
        if complaint_history is not None:
            final_data = generate_final_data('DATA_FOUND')
            final_data['result'] = complaint_history
            final_data['date_range'] = 5
            # final_data['in_location'] = in_location
        else:
            final_data = generate_final_data('DATA_NOT_FOUND')

    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(complaint_hostory_form.errors)
    return final_data

@audit_blueprint.route('get_complaints', methods=["POST"])
# @authenticate('audit')
def get_complaints():
    get_complaints_form = GetComplaintsForm()
    if get_complaints_form.validate_on_submit():
        filtered_complaints=[]
        user_id = request.headers.get('user-id')
        branch_code = get_complaints_form.branch_code.data
        complaints = db.session.query(Audit_Complaints.Id, Audit_Complaints.IsPhoto, Audit_Complaints.IsRemarks,
                                      Audit_Complaints.AuditQuestions, Audit_Complaints.IsYesNo,
                                      Audit_Complaints.IsAttachment, Audit_Complaints_Branches.BranchCode,
                                      Audit_Complaints.IsRemarksRequired,
                                      Audit_Complaints.IsAttachmentRequired, Audit_Complaints.IsPhotoRequired,
                                      Audit_Complaints.IsYesNoRequired, Audit_Complaints.IsQuestionRequired,Audit_Complaints.Roles).join(
            Audit_Complaints_Branches, Audit_Complaints_Branches.QstnId == Audit_Complaints.Id).filter(
            Audit_Complaints_Branches.BranchCode == branch_code, Audit_Complaints.IsDeleted == 0).all()
        # print(len(complaints))
        if complaints is not None:
            complaints = SerializeSQLAResult(complaints).serialize()
            # print(complaints)

            complaint_roles_set = set()
            complaints_for_user = []
            data=False
            for complaint in complaints:
                already_answered = db.session.query(StoreAudits.ComplaintId).filter(
                    StoreAudits.ComplaintId == complaint['Id'], StoreAudits.AuditDate == date.today()
                    , StoreAudits.BranchCode == branch_code, StoreAudits.AuditedBy == user_id).all()
                complaint['already_answered'] = 'Yes' if already_answered else 'No'

                # complaint_roles = complaint['Roles'].split(',')
                if complaint['Roles'] is not None:
                    complaint_roles = complaint['Roles'].split(',')
                else:
                    complaint_roles = []
                complaint_roles_set.update(complaint_roles)
            # print(complaint_roles_set)
            # log_data = {
            #     'Roles': complaint_roles
            # }
            # info_logger(f'Route: {request.path}').info(json.dumps(log_data))

            user_roles_record = db.session.query(DCR_Users.Roles).filter(DCR_Users.Id == user_id).first()
            # user_roles=tuple(user_roles_record[0].split(', '))
            if user_roles_record and user_roles_record[0]:
                user_roles = tuple(user_roles_record[0].split(', '))
            else:
                user_roles = ()
            # print(user_roles)
            complaints_for_user = []
            for complaint in complaints:
                if complaint['Roles']:
                    complaint_roles = [r.strip() for r in complaint['Roles'].split(',')]
                    if any(role in complaint_roles for role in user_roles):
                        complaints_for_user.append(complaint)
                        data = True


                # if complaint['Roles'] is not None and any(role in complaint['Roles'].split(',') for role in user_roles):
                # # if any(role in complaint['Roles'].split(',') for role in user_roles):
                #     complaints_for_user.append(complaint)
                #     data=True

            # print(complaints_for_user)
        if data:
            final_data = generate_final_data('DATA_FOUND')
            final_data['result'] = complaints_for_user
        else:
            final_data = generate_final_data('DATA_NOT_FOUND')

    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(get_complaints_form.errors)
    return final_data


@audit_blueprint.route('get_previous_details_B4SP', methods=["POST"])
# @authenticate('audit')
def get_previous_details_B4SP():
    user_id = request.headers.get('user-id')
    get_previous_details_form = GarmentPreviousDetailsForm()

    log_data = {
        'previous_details_form': get_previous_details_form.data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    if get_previous_details_form.validate_on_submit():
        branch_code = get_previous_details_form.branch_code.data
        is_mss = get_previous_details_form.is_mss.data
        start_date = None if get_previous_details_form.start_date.data == '' else get_previous_details_form.start_date.data
        end_date = None if get_previous_details_form.end_date.data == '' else get_previous_details_form.end_date.data
        complaints = []
        without_complaints = []
        other_stores = []
        # back_to_mss_other_store1 = []
        back_to_mss2 = []
        back_to_mss_other2 = []
        # back_mss_tags = []
        normal_tags = []

        if start_date is not None:
            star_date = start_date.strip() 
            start_date_obj = datetime.strptime(start_date, "%d-%m-%Y")
            formatted_start_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            end_date_obj = datetime.strptime(end_date, "%d-%m-%Y")
            # formatted_end_date = (end_date_obj + timedelta(1)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date = end_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        else:
            formatted_start_date = (datetime.today() - timedelta(10)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date = get_current_date()
        

        dates = db.session.query(AuditTags.Date.label('ScannedDate')).filter(AuditTags.ScannedBy == user_id,
                                                                             AuditTags.BranchCode == branch_code,
                                                                             AuditTags.IsValidTag == 1
                                                                             , AuditTags.Date.between(
                formatted_start_date, formatted_end_date)).order_by(
            AuditTags.Date.desc()).group_by(
            AuditTags.Date).all()
        dates = SerializeSQLAResult(dates).serialize()

        
        # previous_details = []
        audit_history = []
        audit_history_details = []
        no_stock_tags = []
        for date in dates:
            
            previous_details = []
            if date['ScannedDate'] is not None:
                start_date_obj = datetime.strptime(date['ScannedDate'], "%d-%m-%Y")
                formatted_start_date_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
                # log_data = {

                #  'GarmentCount DATE 02': formatted_start_date_date
                #         }
                # info_logger(f'Route: {request.path}').info(json.dumps(log_data))

                previous_data = db.session.query(
                    AuditTags.TagNo, AuditTags.BranchCode, AuditTags.GarmentBranchCode,
                    AuditTags.ComplaintId, AuditTags.Date.label('Date'),
                    DCR_Users.Name.label('ScannedBy'), AuditTags.InLocation,
                    AuditTags.OrderStatus, AuditTags.GarmentStatus,
                    func.min(AuditTags.RecordCreatedDate).label('CreatedDate'),
                    AuditTags.IsDelivered, AuditTags.IsNoStock, AuditTags.ScanId,AuditTags.isScannedInMss,AuditTags.IsMSS,AuditTags.IsScanned
                ).join(DCR_Users, DCR_Users.Id == AuditTags.ScannedBy).filter(
                    AuditTags.ScannedBy == user_id, AuditTags.Date == formatted_start_date_date,
                    AuditTags.BranchCode == branch_code, AuditTags.IsValidTag == 1,
                    AuditTags.IsMSS == is_mss
                ).group_by(AuditTags.ScanId, AuditTags.TagNo, AuditTags.BranchCode,
                           AuditTags.GarmentBranchCode, AuditTags.ComplaintId, AuditTags.Date,
                           DCR_Users.Name, AuditTags.InLocation, AuditTags.OrderStatus, AuditTags.GarmentStatus,AuditTags.isScannedInMss,
                           AuditTags.IsDelivered, AuditTags.IsNoStock,AuditTags.IsMSS,AuditTags.IsScanned).order_by(func.min(AuditTags.RecordCreatedDate).desc())

                previous_data = SerializeSQLAResult(previous_data).serialize(full_date_fields=['Date', 'CreatedDate'])
                # print(previous_data)

                # print(previous_data)
                previous_details.append(previous_data)
                log_data = {
                    'previous_details': previous_details
                        }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                #     info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                branch_tags = []
                for tag_details in previous_details:
                    # branch_tags = []
                    scan_id = None

                    if len(tag_details) > 0:
                        for tag in tag_details:
                            # print(tag)
                            # branch_tags = []
                            scan_id = tag['ScanId']
                            if tag['GarmentBranchCode'] == branch_code and tag['isScannedInMss'] == 0:
                                if tag['GarmentStatus'] == 'In Transits to CDC' and tag['IsNoStock'] == 0:
                                    branch_tags.append(tag['TagNo'])
                                elif tag['GarmentStatus'] == 'Pending Transfer Out From CDC' and tag[
                                    'IsNoStock'] == 0:
                                    branch_tags.append(tag['TagNo'])
                                elif tag['GarmentStatus'] == 'Transfer in at CDC' and tag['IsNoStock'] == 0:
                                    branch_tags.append(tag['TagNo'])
                                elif tag['GarmentStatus'] == 'Invoiced & Delivered' and tag['IsDelivered'] in [
                                        '', 'Un-Delivered'] and \
                                        tag['IsNoStock'] == 0:
                                    branch_tags.append(tag['TagNo'])
                                else:
                                    pass
                            scanned_date = tag['Date']
                            
                            created_date = tag['CreatedDate']
                            # print(scanned_date, type(scanned_date))
                            # print(datetime(datetime.strftime(datetime.strptime(scanned_date, 'YYYY-MM-DD'))).date())
                            scanned_by = tag['ScannedBy']
                            in_location = tag['InLocation']
                            if tag['GarmentBranchCode'] == branch_code and tag['IsNoStock'] == 0 and(tag['isScannedInMss'] == 1 or tag['IsMSS'] ==1)  :
                                back_to_mss2.append(tag['TagNo'])
                            elif tag['ComplaintId'] is None and tag['GarmentBranchCode'] == branch_code and tag[
                                'IsNoStock'] == 0 and tag['isScannedInMss'] == 0:
                                without_complaints.append(tag['TagNo'])
                            elif tag['ComplaintId'] is not None and tag['GarmentBranchCode'] == branch_code and tag[
                                'IsNoStock'] == 0 and tag['isScannedInMss'] == 0:
                                complaints.append(tag['TagNo'])
                            elif tag['GarmentBranchCode'] != branch_code and tag['IsNoStock'] == 0 and tag['isScannedInMss'] == 0:
                                other_stores.append(tag['TagNo'])
                            elif tag['GarmentBranchCode'] != branch_code and tag['IsNoStock'] == 0 and tag['isScannedInMss'] == 1:
                                back_to_mss_other2.append(tag['TagNo'])
                            
                                

                            else:
                                pass

                            # no_stock_tags.append(tag['TagNo'])
                            
                            # start_date_obj = datetime.strptime(scanned_date, "%d-%m-%Y %H:%M:%S %p")
                            # datetime_object = start_date_obj.replace(hour=0, minute=0, second=0)
                            # formatted_start_date_date = datetime_object.strftime("%Y-%m-%d %H:%M:%S")

                            # Parse the original datetime string to a datetime object
                            parsed_datetime = datetime.strptime(scanned_date, "%d-%m-%Y %I:%M:%S %p")
                            # Replace the hour, minute, and second to zero
                            modified_datetime = parsed_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
                            # Format the datetime object to the desired string format
                            formatted_start_date_date = modified_datetime.strftime("%Y-%m-%d %H:%M:%S")
                            # log_data = {
                            #  'vimal': GcOUNT,
                            #  'scan id':scan_id
                            #         }
                            # info_logger(f'Route: {request.path}').info(json.dumps(log_data))

                            if formatted_start_date_date <= '2024-01-10':

                                
                                total_garment_count = db.session.query(AuditGarmentCount).filter(
                                    AuditGarmentCount.Date == formatted_start_date_date,
                                    AuditGarmentCount.BranchCode == branch_code,
                                    AuditGarmentCount.IsDeleted == 0).one_or_none()
                            else:
                                
                                total_garment_count = db.session.query(AuditGarmentCount).filter(
                                    AuditGarmentCount.Date == formatted_start_date_date,
                                    AuditGarmentCount.BranchCode == branch_code,
                                    AuditGarmentCount.IsDeleted == 0, AuditGarmentCount.ScanId == scan_id,
                                    AuditGarmentCount.AuditedBy == user_id).one_or_none()
                                
                                tmp=1
                                GcOUNT=0
                                if total_garment_count or tmp==1:
                                    if total_garment_count:
                                        GcOUNT = int(total_garment_count.GarmentCount)

                                        branch_tags = list(branch_tags)
                                        branch_tags_count = len(branch_tags)
                                        # total_scanned_branch_count = branch_tags_count
                                        total_scanned_branch_count = len(branch_tags)


                                        log_data = {
                                         'GcOUNT': GcOUNT,
                                         'scan id':scan_id,
                                         'user':user_id
                                                }
                                        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

                                        no_stock_count = GcOUNT - total_scanned_branch_count

                                        # no_stock_count = total_garment_count.GarmentCount - total_scanned_branch_count
                                        # tot_count = len(without_complaints) + len(complaints) + len(other_stores)
                                        # no_stock_count = total_garment_count.GarmentCount - tot_count
                                        no_stock_count = Decimal(no_stock_count)
                                        without_complaints = set(without_complaints)
                                        complaints = set(complaints)
                                        other_stores = set(other_stores)

                                        back_to_mss_other2 = set(back_to_mss_other2)
                                        # back_to_mss_other_store1 = set(back_to_mss_other_store1)
                                        back_to_mss2 = set(back_to_mss2)


                                        lenofnostock = 0

                                        no_stock_tags = [tag[0] for tag in db.session.query(AuditTags.TagNo).filter(
                                            AuditTags.Date == formatted_start_date_date,
                                            AuditTags.GarmentBranchCode == branch_code,
                                            AuditTags.BranchCode == branch_code,
                                            AuditTags.ScanId == scan_id,
                                            AuditTags.Execptionflag == 0,
                                            AuditTags.IsValidTag == 1,
                                            AuditTags.AuditedBy == user_id,
                                            AuditTags.IsNoStock == 1,
                                            AuditTags.IsMSS == is_mss,
                                            AuditTags.GarmentStatus.in_(
                                                ['In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC',
                                                 'Invoiced & Delivered'])
                                        ).all()]
                                   
                                    # back_to_mss_tags =[]
                                    # if is_mss:
                                    #     back_to_mss_tags = db.session.query(AuditTags.TagNo).filter(
                                    #         AuditTags.isScannedInMss == 0,
                                    #         AuditTags.Date == formatted_start_date_date,
                                    #         AuditTags.GarmentBranchCode == branch_code,
                                    #         AuditTags.BranchCode == branch_code,
                                    #         AuditTags.ScanId == scan_id,
                                    #         AuditTags.IsValidTag == 1,
                                    #         AuditTags.AuditedBy == user_id,
                                    #         AuditTags.IsNoStock == 0,
                                    #         AuditTags.IsMSS == 1).all()
                                    # else:
                                    #     back_to_mss_tags = db.session.query(AuditTags.TagNo).filter(AuditTags.isScannedInMss == 1,
                                    #         AuditTags.Date == formatted_start_date_date,
                                    #         AuditTags.GarmentBranchCode == branch_code,
                                    #         AuditTags.BranchCode == branch_code,
                                    #         AuditTags.ScanId == scan_id,
                                    #         AuditTags.Execptionflag == 0,
                                    #         AuditTags.IsValidTag == 1,
                                    #         AuditTags.AuditedBy == user_id,
                                    #         AuditTags.IsNoStock == 0,
                                    #         AuditTags.IsMSS == 0).all()
                                    #
                                    #
                                    # # back_to_mss_tags=list(back_to_mss_tags)
                                    # back_to_mss_tags = [tag[0] for tag in back_to_mss_tags]
                                    #
                                    # if back_to_mss_tags:
                                    #     mss_count=len(back_to_mss_tags)
                                    # else:
                                    #     mss_count=0
                                    #
                                    #
                                    # if is_mss:
                                    #     back_to_mss_other_store = db.session.query(AuditTags.TagNo).filter(
                                    #         AuditTags.isScannedInMss == 0,
                                    #         AuditTags.Date == formatted_start_date_date,
                                    #         AuditTags.GarmentBranchCode != branch_code,
                                    #         AuditTags.BranchCode == branch_code,
                                    #         AuditTags.ScanId == scan_id,
                                    #         AuditTags.IsValidTag == 1,
                                    #         AuditTags.AuditedBy == user_id,
                                    #         AuditTags.IsNoStock == 0,
                                    #         AuditTags.IsMSS == 1).all()
                                    # else:
                                    #     log_data = {
                                    #      'b2mss': is_mss
                                    #
                                    #         }
                                    #     info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                                    #     back_to_mss_other_store = db.session.query(AuditTags.TagNo).filter(AuditTags.isScannedInMss == 1,
                                    #     AuditTags.Date == formatted_start_date_date,
                                    #     AuditTags.GarmentBranchCode != branch_code,
                                    #     AuditTags.BranchCode == branch_code,
                                    #     AuditTags.ScanId == scan_id,
                                    #     # AuditTags.Execptionflag == 0,
                                    #     AuditTags.IsValidTag == 1,
                                    #     AuditTags.ScannedBy == user_id,
                                    #     AuditTags.IsNoStock == 0,
                                    #     AuditTags.IsScanned == 1,
                                    #     AuditTags.IsMSS == 0,
                                    #      ).all()
                                    #
                                    #
                                    #
                                    # back_to_mss_other_store = [tag[0] for tag in back_to_mss_other_store]
                                    # log_data = {
                                    #      # 'b2mss': bk2mss,
                                    #      "back_to_mss_other_store1 ":back_to_mss_other_store1
                                    #
                                    #         }
                                    # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                                    #
                                    #
                                    #
                                    # if back_to_mss_other_store:
                                    #     mss_other_store_count=len(back_to_mss_other_store)
                                    # else:
                                    #     mss_other_store_count=0


                                    query = text("""select count(*)  from AuditTags 
                                    WHERE 
                                        Date = :formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss = 1 AND IsMSS=0  
                                    """)

                                    no_stock_c = db.session.execute(query, {
                                        'formatted_start_date_date': formatted_start_date_date,
                                        'branch_code': branch_code, 'scan_id': scan_id,
                                        "ScannedBy": user_id}).scalar()

                                    query2 = text("""select count(*)  from AuditTags 
                                    WHERE 
                                        Date = :formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id and Execptionflag=0
                                        AND isScannedInMss = 0 AND IsMSS=0 and GarmentBranchCode =:branch_code AND IsScanned=1 AND GarmentStatus in
                                                ('In Transits to CDC','Pending Transfer Out From CDC','Transfer in at CDC','Invoiced & Delivered')
                                    """)

                                    no_stock_valid = db.session.execute(query2, {
                                        'formatted_start_date_date': formatted_start_date_date,
                                        'branch_code': branch_code, 'scan_id': scan_id,
                                        "ScannedBy": user_id}).scalar()



                                    if is_mss:
                                        no_stock_counts = len(no_stock_tags)
                                    else:
                                        no_stock_counts = GcOUNT -  no_stock_valid
                                    log_data = {
                                        "other_stores":list(other_stores),
                                        'cnt12': no_stock_valid,
                                        'cnt22':no_stock_c,
                                        'gcc':GcOUNT,
                                        'no stk':no_stock_counts
                                    }
                                    info_logger(f'Route: {request.path}').info(json.dumps(log_data))

                                    total_tags_scanned = len(without_complaints) + len(complaints) + len(other_stores) + len(back_to_mss_other2) + len(back_to_mss2)

                                    without_complaints = list(without_complaints)
                                    without_complaints_count = len(without_complaints)
                                    complaints = list(complaints)
                                    complaints_count = len(complaints)
                                    other_stores = list(other_stores)
                                    # mss_other_store = list(mss_other_store)
                                    other_stores_count = len(other_stores)

                                    back_to_mss_other2 = list(back_to_mss_other2)
                                    back_to_mss_other2_count = len(back_to_mss_other2)

                                    back_to_mss2 = list(back_to_mss2)
                                    back_to_mss2_count = len(back_to_mss2)

                                    # total_garment_count = total_garment_count
                                    total_garment_count = GcOUNT
                                    total_tags_scanned = total_tags_scanned
                                    original_datetime = datetime.strptime(scanned_date, "%d-%m-%Y %I:%M:%S %p")

                                    # Format the datetime object as a new string
                                    formatted_string = original_datetime.strftime("%d-%m-%Y")






                                    
                                    index = next((index for (index, d) in enumerate(audit_history) if
                                                  d['scan_id'] == tag['ScanId'] and d['scanned_date_only'] == formatted_string),
                                                 None)
                                    # if  tag['TagNo'] in ['F10100000205252']:
                                    #     print("kjh")
                                    log_data = {
                                     'HIST 26': scan_id,
                                     'scan id':index
                                            }
                                    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                                    
                                    if index is None:
                                        if len(complaints) == 0 and len(without_complaints) == 0 and len(other_stores) == 0 and len(back_to_mss_other2) == 0 and len(back_to_mss2) == 0:
                                            pass
                                        else:
                                            
                                            previous_tag_details = {
                                                "without_complaints": without_complaints,
                                                "without_complaints_count": without_complaints_count,
                                                "complaints": complaints,
                                                "complaints_count": complaints_count,
                                                "other_stores": other_stores,
                                                "mss_tags": back_to_mss2,
                                                "mss_count":back_to_mss2_count,
                                                # "mss_other_store":back_to_mss_other_store,back_mss_tags
                                                "mss_other_store":back_to_mss_other2,
                                                "mss_other_store_count":back_to_mss_other2_count,
                                                # back_to_mss1,mss_other_store1
                                                 # "mss_other_store_count":len(back_mss_tags),
                                                # "mss_other_store_count":0,
                                                # "other_stores_count":len(normal_tags),
                                                "other_stores_count": other_stores_count,
                                                "total_garment_count": total_garment_count,
                                                # "total_garment_count": GcOUNT,
                                                "total_tags_scanned": total_tags_scanned,
                                                "no_stock_count":no_stock_counts,
                                                # "no_stock_count": len(no_stock_tags),
                                                "scanned_date_only": formatted_string,
                                                "scanned_date": created_date,
                                                "scanned_by": scanned_by,
                                                "InLocation": in_location,
                                                "scanned_by_id":user_id,
                                                "scan_id": scan_id,
                                                "NoStockTag": no_stock_tags}
                                            audit_history.append(previous_tag_details)
                                            # log_data = {
                                            #  'GcOUNT': 'B4 INDEX 22'
                                            #         }
                                            # info_logger(f'Route: {request.path}').info(json.dumps(log_data))

                                    else:
                                        log_data = {
                                         'HIST 22': 'audit_history'
                                                }
                                        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                                        update_dict = audit_history[index]
                                        without_complaints_list = list(
                                            set(without_complaints + update_dict['without_complaints']))
                                        complaints_list = list(set(update_dict['complaints'] + complaints))


                                        # other_stores_list = list(set(update_dict['other_stores'] + other_stores))

                                        other_stores_list = list(
                                            set(other_stores + update_dict.get('other_stores', [])))
                                        update_dict['without_complaints'] = without_complaints_list
                                        update_dict['without_complaints_count'] = len(without_complaints_list)
                                        update_dict['complaints'] = complaints_list
                                        update_dict['complaints_count'] = len(complaints_list)
                                        update_dict['other_stores'] = other_stores_list
                                        update_dict['other_stores_count'] = len(other_stores_list)
                                        
                                        update_dict['total_tags_scanned'] += total_tags_scanned

                                        # update_dict['no_stock_count'] = len(no_stock_tags)
                                        update_dict['no_stock_count'] = no_stock_counts

                                        # back_to_mss_other2_list = list(set(update_dict['back_to_mss_other2'] + back_to_mss_other2))
                                        back_to_mss_other2_list = list(
                                            set(back_to_mss_other2 + update_dict.get('back_to_mss_other2', [])))
                                        update_dict['back_to_mss_other2'] = back_to_mss_other2_list
                                        update_dict['back_to_mss_other2_count'] = len(back_to_mss_other2_list)

                                        # back_to_mss2_list = list(set(update_dict['back_to_mss2'] + back_to_mss2))
                                        back_to_mss2_list = list(
                                            set(back_to_mss2 + update_dict.get('back_to_mss2', [])))
                                        update_dict['back_to_mss2'] = back_to_mss2_list
                                        update_dict['back_to_mss2_count'] = len(back_to_mss2_list)
                                        log_data = {
                                         'count bmss': len(back_to_mss2_list)
                                                }
                                        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
                                        # back_to_mss1
                                    complaints = []
                                    without_complaints = []
                                    other_stores = []
                                    back_to_mss2 = []
                                    back_to_mss_other2 = []

                                # else:
                                #     final_data = generate_final_data('DATA_NOT_FOUND')
                                #     return json.dumps({'error': 'No data found'})



            else:
                pass
                # no_stock_tags = []
                # audit_history_details.append(audit_history)
       
        final_data = generate_final_data('DATA_FOUND')

        # audit_history = dict(audit_history)
        final_data['result'] = {"audit_history_details": audit_history, "date_range": 5}
       
        log_data = {
         'HIST': audit_history
                }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(get_previous_details_form.errors)
    return final_data

def db_result_to_dict(result):
    """
    Method for converting sql Queryset to dictionary & change date format of date values
    """
    return [
        {column: value.strftime("%d-%m-%Y") if isinstance(value, date) else value for column, value in row.items()}
        for row in result]

@audit_blueprint.route('get_tag_details_live', methods=["POST"])
# @authenticate('audit')#after change in other store issue
def get_tag_details_live():
    user_id = request.headers.get('user-id')
    tag_details_form = TagDetailsForm()
    log_data = {
        'tag_details_ReqBdyNew': tag_details_form.data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    if tag_details_form.validate_on_submit():

        with_complaints = None if tag_details_form.with_complaints.data == '' else tag_details_form.with_complaints.data
        without_complaints = None if tag_details_form.without_complaints.data == '' else tag_details_form.without_complaints.data
        other_stores = None if tag_details_form.other_stores.data == '' else tag_details_form.other_stores.data
        no_stock = None if tag_details_form.no_stock.data == '' else tag_details_form.no_stock.data
        audit_date = None if tag_details_form.audit_date.data == '' else tag_details_form.audit_date.data
        is_mss = tag_details_form.is_mss.data
        mss_other_store = None if tag_details_form.mss_other_store.data == '' else tag_details_form.mss_other_store.data
        back_to_mss_tags_form = None if tag_details_form.mss_tags.data == '' else tag_details_form.mss_tags.data
        back_to_mss_tags_list = back_to_mss_tags_form
        # latest_scan_id = tag_details_form.latest_scan_id.data
        scan_id = tag_details_form.latest_scan_id.data
        branch_code = tag_details_form.branch_code.data
        audit_date_obj = datetime.strptime(audit_date, "%d-%m-%Y")
        # formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        # audit_date_obj = datetime.strptime(audit_date, "%d-%m-%Y")
        # formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        # formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        # log_data = {
        # 'tag_details_ReqBdy without_complaints': without_complaints
        # }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        without_complaint_pending_transfer_out_from_cdc = []
        without_complaint_in_transit_to_mss = []
        without_complaint_pending_for_qc_verification = []
        without_complaint_transfer_in_at_mss = []
        without_complaint_qc_approved = []
        without_complaint_qc_rejected = []
        without_complaint_work_order_created = []
        without_complaint_missing = []
        without_complaint_damaged = []
        without_complaint_resorted = []
        without_complaint_in_transit_to_cdc = []
        without_complaint_transfer_in_at_cdc = []
        without_complaint_disputed_garment = []
        without_complaint_invoiced_and_delivered = []
        without_complaint_under_clearance_of_invoice_settlement = []
        without_complaint_invoiced_and_pending_delivery = []
        without_complaint_moved_back_to_mss = []
        without_complaint_no_stock = []

        complaint_pending_transfer_out_from_cdc = []
        complaint_in_transit_to_mss = []
        complaint_transfer_in_at_mss = []
        complaint_pending_for_qc_verification = []
        complaint_qc_approved = []
        complaint_qc_rejected = []
        complaint_work_order_created = []
        complaint_missing = []
        complaint_damaged = []
        complaint_resorted = []
        complaint_in_transit_to_cdc = []
        complaint_transfer_in_at_cdc = []
        complaint_disputed_garment = []
        complaint_invoiced_and_delivered = []
        complaint_under_clearance_of_invoice_settlement = []
        complaint_invoiced_and_pending_delivery = []
        complaint_moved_back_to_mss = []
        complaint_no_stock = []

        mss_pending_transfer_out_from_cdc = []
        mss_in_transit_to_mss = []
        mss_pending_for_qc_verification = []
        mss_transfer_in_at_mss = []
        mss_qc_approved = []
        mss_qc_rejected = []
        mss_work_order_created = []
        mss_missing = []
        mss_damaged = []
        mss_resorted = []
        mss_in_transit_to_cdc = []
        mss_transfer_in_at_cdc = []
        mss_disputed_garment = []
        mss_invoiced_and_delivered = []
        mss_under_clearance_of_invoice_settlement = []
        mss_invoiced_and_pending_delivery = []
        mss_moved_back_to_mss = []
        mss_no_stock = []

        mss_other_pending_transfer_out_from_cdc = []
        mss_other_in_transit_to_mss = []
        mss_other_pending_for_qc_verification = []
        mss_other_transfer_in_at_mss = []
        mss_other_qc_approved = []
        mss_other_qc_rejected = []
        mss_other_work_order_created = []
        mss_other_missing = []
        mss_other_damaged = []
        mss_other_resorted = []
        mss_other_in_transit_to_cdc = []
        mss_other_transfer_in_at_cdc = []
        mss_other_disputed_garment = []
        mss_other_invoiced_and_delivered = []
        mss_other_under_clearance_of_invoice_settlement = []
        mss_other_invoiced_and_pending_delivery = []
        mss_other_moved_back_to_mss = []
        mss_other_no_stock = []

        # log_data = {
        #     'NoStock': len(no_stock)

        # }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        # max_scan_id_subquery = db.session.query(func.max(AuditTags.ScanId)).scalar()
        # from sqlalchemy import func
        # latest_scan_id = db.session.query(func.max(AuditTags.ScanId)).filter(
        #     AuditTags.AuditedBy == user_id,
        #     AuditTags.Date == date.today(), AuditTags.BranchCode == branch_code
        # ).scalar()

        if with_complaints is not None:
            # complaint_tag_details = db.session.query(AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus,
            #                                          AuditTags.ComplaintDepartment, AuditTags.ComplaintDate,
            #                                          AuditTags.EntryType, AuditTags.ComplaintId,
            #                                          AuditTags.GarmentStatus, AuditTags.OrderStatus,
            #                                          AuditTags.CustomerName, AuditTags.CustomerId
            #                                          ).filter(AuditTags.TagNo.in_(with_complaints),
            #                                                   AuditTags.Date == formatted_audit_date,
            #                                                   AuditTags.ScannedBy == user_id,
            #                                                   AuditTags.IsMSS == is_mss,
            #                                                   AuditTags.BranchCode == branch_code).all()
            complaint_tag_details = db.session.query(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).filter(
                AuditTags.TagNo.in_(with_complaints),
                AuditTags.Date == formatted_audit_date,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsMSS == is_mss,
                AuditTags.BranchCode == branch_code,
                AuditTags.ScanId == scan_id,
                AuditTags.isScannedInMss == 0
            ).group_by(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount, AuditTags,
                AuditTags.OrderType
            ).all()

            complaint_tag_details = SerializeSQLAResult(complaint_tag_details).serialize()
            for complaint in complaint_tag_details:
                if complaint['GarmentStatus'] == 'In Transits to CDC':
                    complaint_in_transit_to_cdc.append(complaint)
                elif complaint['GarmentStatus'] in ['Resorted']:
                    complaint_resorted.append(complaint)
                elif complaint['GarmentStatus'] in ['Work Order Created ']:
                    complaint_work_order_created.append(complaint)
                elif complaint['GarmentStatus'] in ['In Transits to mss']:
                    complaint_in_transit_to_mss.append(complaint)
                elif complaint['GarmentStatus'] in ['Pending Transfer Out From CDC']:
                    complaint_pending_transfer_out_from_cdc.append(complaint)
                elif complaint['GarmentStatus'] in ['Invoiced & Delivered']:
                    complaint_invoiced_and_delivered.append(complaint)
                elif complaint['GarmentStatus'] in ['Transfer in at CDC']:
                    complaint_transfer_in_at_cdc.append(complaint)
                elif complaint['GarmentStatus'] in ['Pending for QC Verification']:
                    complaint_pending_for_qc_verification.append(complaint)
                elif complaint['GarmentStatus'] in ['Transfer in at mss']:
                    complaint_transfer_in_at_mss.append(complaint)
                elif complaint['GarmentStatus'] in ['QC Approved']:
                    complaint_qc_approved.append(complaint)
                elif complaint['GarmentStatus'] in ['QC Rejected ']:
                    complaint_qc_rejected.append(complaint)
                elif complaint['GarmentStatus'] in ['Moved Back to Mss']:
                    complaint_moved_back_to_mss.append(complaint)
                elif complaint['GarmentStatus'] in ['Invoiced & Pending Delivery']:
                    complaint_invoiced_and_pending_delivery.append(complaint)
                elif complaint['GarmentStatus'] in ['Under clearance of Invoice settlement']:
                    complaint_under_clearance_of_invoice_settlement.append(complaint)
                elif complaint['GarmentStatus'] in ['Missing']:
                    complaint_missing.append(complaint)
                elif complaint['GarmentStatus'] in ['Damaged']:
                    complaint_damaged.append(complaint)
                elif complaint['GarmentStatus'] in ['Disputed Garment']:
                    complaint_disputed_garment.append(complaint)
                else:
                    complaint_no_stock.append(complaint)

        log_data = {
            'with_complaints': 'with_complaints'

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        if without_complaints is not None:
            log_data = {
                'without_complaints 1': 'without_complaints 1'

            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            without_complaints_tag_details = db.session.query(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).filter(
                AuditTags.TagNo.in_(without_complaints),
                AuditTags.Date == formatted_audit_date,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsMSS == is_mss,
                AuditTags.BranchCode == branch_code, AuditTags.ScanId == scan_id,
                AuditTags.isScannedInMss == 0
            ).all()


            # group_by(
            #     AuditTags.TagNo,
            #     AuditTags.EGRN,
            #     AuditTags.ComplaintStatus,
            #     AuditTags.ComplaintDepartment,
            #     AuditTags.ComplaintDate,
            #     AuditTags.EntryType,
            #     AuditTags.ComplaintId,
            #     AuditTags.GarmentStatus,
            #     AuditTags.OrderStatus,
            #     AuditTags.CustomerName,
            #     AuditTags.CustomerId,
            #     AuditTags.GarmentName,
            #     AuditTags.GarmentAmount,
            #     AuditTags.OrderType
            # ).all()

            # without_complaints_tag_details = db.session.query(AuditTags.TagNo, AuditTags.EGRN,
            #                                                   AuditTags.ComplaintStatus,
            #                                                   AuditTags.ComplaintDepartment,
            #                                                   AuditTags.ComplaintDate, AuditTags.EntryType,
            #                                                   AuditTags.ComplaintId,
            #                                                   AuditTags.GarmentStatus, AuditTags.OrderStatus,
            #                                                   AuditTags.CustomerName, AuditTags.CustomerId).filter(
            #     AuditTags.TagNo.in_(without_complaints), AuditTags.Date == formatted_audit_date,
            #                                              AuditTags.ScannedBy == user_id,
            #                                              AuditTags.IsMSS == is_mss,
            #                                              AuditTags.BranchCode == branch_code).all()
            without_complaints_tag_details = SerializeSQLAResult(without_complaints_tag_details).serialize()

            log_data = {
                'without_complaints': 'without_complaints'

            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            for without_complaint in without_complaints_tag_details:
                if without_complaint['GarmentStatus'] == 'In Transits to CDC':
                    without_complaint_in_transit_to_cdc.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Resorted']:
                    without_complaint_resorted.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Work Order Created ']:
                    without_complaint_work_order_created.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['In Transits to mss']:
                    without_complaint_in_transit_to_mss.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Pending Transfer Out From CDC']:
                    without_complaint_pending_transfer_out_from_cdc.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Invoiced & Delivered']:
                    without_complaint_invoiced_and_delivered.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Transfer in at CDC']:
                    without_complaint_transfer_in_at_cdc.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Pending for QC Verification']:
                    without_complaint_pending_for_qc_verification.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Transfer in at mss']:
                    without_complaint_transfer_in_at_mss.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['QC Approved']:
                    without_complaint_qc_approved.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['QC Rejected ']:
                    without_complaint_qc_rejected.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Moved Back to Mss']:
                    without_complaint_moved_back_to_mss.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Invoiced & Pending Delivery']:
                    without_complaint_invoiced_and_pending_delivery.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Under clearance of Invoice settlement']:
                    without_complaint_under_clearance_of_invoice_settlement.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Missing']:
                    without_complaint_missing.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Damaged']:
                    without_complaint_damaged.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Disputed Garment']:
                    without_complaint_disputed_garment.append(without_complaint)
                else:
                    without_complaint_no_stock.append(without_complaint)
        if other_stores is not None:
            other_store_tag_details = db.session.query(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.GarmentBranchName,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).filter(
                AuditTags.TagNo.in_(other_stores),
                AuditTags.Date == formatted_audit_date,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsMSS == is_mss,
                AuditTags.BranchCode == branch_code,
                AuditTags.ScanId == scan_id,
                AuditTags.isScannedInMss == 0
            ).group_by(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.GarmentBranchName,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).all()

            other_store_tag_details = SerializeSQLAResult(other_store_tag_details).serialize()
            # stores = []
            # for other_store in other_store_tag_details:
            #     stores.append(other_store['GarmentBranchName'])
            # store_count = []
            # for store in stores:
            #     count = stores.count(store)
            #     branches = {store: count}
            #     store_count.append(branches)
            #     stores.remove(store)

            # Group tag details by branch name
            branch_tags = defaultdict(list)
            for tag_detail in other_store_tag_details:
                branch_tags[tag_detail['GarmentBranchName']].append(tag_detail)

            # Create the final data structure
            other_stores_data = []
            for branch_name, tags in branch_tags.items():
                other_stores_data.append({
                    'status': 'Other stores',
                    'count': len(tags),
                    'details': tags
                })
            if not other_stores_data:
                other_stores_data.append({
                    'status': 'Other stores',
                    'count': 0,
                    'details': []
                })
        log_data = {
            # 'back_to_mss_tags': back_to_mss_tags
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        if back_to_mss_tags_form is not None:

            log_data = {
                'ScanId': scan_id,
                'formatted_audit_date': formatted_audit_date
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            if is_mss:
                log_data = {
                    'ScanId_is_mss:': is_mss

                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))

                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date =:formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss=0 AND IsMSS=1                                      
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()

                log_data = {
                    'route': query,
                    'DATE': formatted_audit_date,
                    'query_result': [dict(row) for row in result]
                }

                # Logging the result with proper JSON formatting
                info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

                # query = text("""
                # SELECT  TagNo, EGRN, ComplaintStatus,  ComplaintDepartment,  ComplaintDate, EntryType,  ComplaintId, GarmentStatus,  GarmentBranchName,
                #     OrderStatus,  CustomerName, CustomerId,  GarmentName,  GarmentAmount, OrderType FROM  AuditTags
                # WHERE  TagNo IN :back_to_mss_tags
                #     AND Date = :formatted_audit_date
                #     AND ScannedBy = :user_id
                #     AND IsMSS = 0
                #     AND BranchCode = :branch_code
                #     AND ScanId = :scan_id
                #     AND isScannedInMss = 1
                #     AND GarmentBranchCode = :branch_code
                # GROUP BY  TagNo, EGRN,  ComplaintStatus, ComplaintDepartment,  ComplaintDate,  EntryType, ComplaintId, GarmentStatus, GarmentBranchName,
                #     OrderStatus,  CustomerName,  CustomerId,  GarmentName,  GarmentAmount,  OrderType """)
                # # Execute the query and fetch results
                # result = db.session.execute(query, {
                #     'back_to_mss_tags': tuple(back_to_mss_tags_list),
                #     'formatted_audit_date': formatted_audit_date, 'user_id': user_id,  'branch_code': branch_code,  'scan_id': scan_id
                # }).fetchall()
            else:
                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date = :formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss = 1 AND IsMSS=0  
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()
                # query = text("""
                #                SELECT  TagNo, EGRN, ComplaintStatus,  ComplaintDepartment,  ComplaintDate, EntryType,  ComplaintId, GarmentStatus,  GarmentBranchName,
                #                    OrderStatus,  CustomerName, CustomerId,  GarmentName,  GarmentAmount, OrderType FROM  AuditTags
                #                WHERE  Date = :formatted_audit_date
                #                    AND ScannedBy = :user_id
                #                    AND IsMSS = 0
                #                    AND BranchCode = :branch_code
                #                    AND ScanId = :scan_id
                #                    AND GarmentBranchCode = :branch_code
                #                GROUP BY  TagNo, EGRN,  ComplaintStatus, ComplaintDepartment,  ComplaintDate,  EntryType, ComplaintId, GarmentStatus, GarmentBranchName,
                #                    OrderStatus,  CustomerName,  CustomerId,  GarmentName,  GarmentAmount,  OrderType """)
                # # Execute the query and fetch results
                # result = db.session.execute(query, {
                #     'formatted_audit_date': formatted_audit_date, 'user_id': user_id, 'branch_code': branch_code,
                #     'scan_id': scan_id
                # }).fetchall()

                log_data = {
                    'route': query,
                    'DATE': formatted_audit_date,
                    'query_result': [dict(row) for row in result]
                }

                # Logging the result with proper JSON formatting
                info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

            back_to_mss_tags = SerializeSQLAResult(result).serialize()

            log_data = {
                'back_to_mss_tags11': back_to_mss_tags
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

            for mss in back_to_mss_tags:
                if mss['GarmentStatus'] == 'In Transits to CDC':
                    mss_in_transit_to_cdc.append(mss)
                elif mss['GarmentStatus'] == 'Resorted':
                    mss_resorted.append(mss)
                elif mss['GarmentStatus'] == 'Work Order Created':
                    mss_work_order_created.append(mss)
                elif mss['GarmentStatus'] == 'In Transits to mss':
                    mss_in_transit_to_mss.append(mss)
                elif mss['GarmentStatus'] == 'Pending Transfer Out From CDC':
                    mss_pending_transfer_out_from_cdc.append(mss)
                elif mss['GarmentStatus'] == 'Invoiced & Delivered':
                    mss_invoiced_and_delivered.append(mss)
                elif mss['GarmentStatus'] == 'Transfer in at CDC':
                    mss_transfer_in_at_cdc.append(mss)
                elif mss['GarmentStatus'] == 'Pending for QC Verification':
                    mss_pending_for_qc_verification.append(mss)
                elif mss['GarmentStatus'] == 'Transfer in at mss':
                    mss_transfer_in_at_mss.append(mss)
                elif mss['GarmentStatus'] == 'QC Approved':
                    mss_qc_approved.append(mss)
                elif mss['GarmentStatus'] == 'QC Rejected ':
                    mss_qc_rejected.append(mss)
                elif mss['GarmentStatus'] == 'Moved Back to Mss':
                    mss_moved_back_to_mss.append(mss)
                elif mss['GarmentStatus'] == 'Invoiced & Pending Delivery':
                    mss_invoiced_and_pending_delivery.append(mss)
                elif mss['GarmentStatus'] == 'Under clearance of Invoice settlement':
                    mss_under_clearance_of_invoice_settlement.append(mss)
                elif mss['GarmentStatus'] == 'Missing':
                    mss_missing.append(mss)
                elif mss['GarmentStatus'] == 'Damaged':
                    mss_damaged.append(mss)
                elif mss['GarmentStatus'] == 'Disputed Garment':
                    mss_disputed_garment.append(mss)
                else:
                    mss_no_stock.append(mss)
        log_data = {
            'back_to_mss_tagsmss': complaint_in_transit_to_mss
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

        if mss_other_store is not None:
            log_data = {
                'mss_tagsmss': is_mss
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

            if is_mss:
                log_data = {
                    'ScanId_is_mss:': is_mss

                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))

                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date =:formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss=0 AND IsMSS=1 
                                        AND GarmentBranchCode != :branch_code                                 
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()

                # query = text("""
                # SELECT  TagNo, EGRN, ComplaintStatus,  ComplaintDepartment,  ComplaintDate, EntryType,  ComplaintId, GarmentStatus,  GarmentBranchName,
                #     OrderStatus,  CustomerName, CustomerId,  GarmentName,  GarmentAmount, OrderType FROM  AuditTags
                # WHERE  TagNo IN :back_to_mss_tags
                #     AND Date = :formatted_audit_date
                #     AND ScannedBy = :user_id
                #     AND IsMSS = 0
                #     AND BranchCode = :branch_code
                #     AND ScanId = :scan_id
                #     AND isScannedInMss = 1
                #     AND GarmentBranchCode = :branch_code
                # GROUP BY  TagNo, EGRN,  ComplaintStatus, ComplaintDepartment,  ComplaintDate,  EntryType, ComplaintId, GarmentStatus, GarmentBranchName,
                #     OrderStatus,  CustomerName,  CustomerId,  GarmentName,  GarmentAmount,  OrderType """)
                # # Execute the query and fetch results
                # result = db.session.execute(query, {
                #     'back_to_mss_tags': tuple(back_to_mss_tags_list),
                #     'formatted_audit_date': formatted_audit_date, 'user_id': user_id,  'branch_code': branch_code,  'scan_id': scan_id
                # }).fetchall()
            else:
                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date = :formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss = 1 AND IsMSS=0  
                                        AND GarmentBranchCode != :branch_code 
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()
            log_data = {
                'route': query,
                'DATE': formatted_audit_date,
                'query_result': [dict(row) for row in result]
            }

            # Logging the result with proper JSON formatting
            info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

            mss_other_store = SerializeSQLAResult(result).serialize()

            log_data = {
                'mss_tagsmss': mss_other_store
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

            for mss_other in mss_other_store:
                # for mss_other in back_to_mss_tags:
                if mss_other['GarmentStatus'] == 'In Transits to CDC':
                    mss_other_in_transit_to_cdc.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Resorted':
                    mss_other_resorted.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Work Order Created':
                    other_work_order_created.append(mss_other)
                elif mss_other['GarmentStatus'] == 'In Transits to mss':
                    mss_other_in_transit_to_mss.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Pending Transfer Out From CDC':
                    mss_other_pending_transfer_out_from_cdc.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Invoiced & Delivered':
                    mss_other_invoiced_and_delivered.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Transfer in at CDC':
                    mss_other_transfer_in_at_cdc.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Pending for QC Verification':
                    mss_other_pending_for_qc_verification.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Transfer in at mss':
                    mss_other_transfer_in_at_mss.append(mss_other)
                elif mss_other['GarmentStatus'] == 'QC Approved':
                    mss_other_qc_approved.append(mss_other)
                elif mss_other['GarmentStatus'] == 'QC Rejected ':
                    mss_other_qc_rejected.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Moved Back to Mss':
                    mss_other_moved_back_to_mss.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Invoiced & Pending Delivery':
                    mss_other_invoiced_and_pending_delivery.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Under clearance of Invoice settlement':
                    mss_other_under_clearance_of_invoice_settlement.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Missing':
                    mss_other_missing.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Damaged':
                    mss_other_damaged.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Disputed Garment':
                    mss_other_disputed_garment.append(mss_other)
                else:
                    mss_other_no_stock.append(mss_other)

        if no_stock is not None:
            chunk_size = 1000
            no_stock_tag_details = []
            serialized_result = []
            for i in range(0, len(no_stock), chunk_size):
                chunk = no_stock[i:i + chunk_size]
                # print(chunk)
                query_result = db.session.query(AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus,
                                                AuditTags.ComplaintDepartment, AuditTags.ComplaintDate,
                                                AuditTags.ComplaintId, AuditTags.EntryType,
                                                AuditTags.GarmentStatus, AuditTags.GarmentBranchName,
                                                AuditTags.GarmentName, AuditTags.GarmentAmount,
                                                AuditTags.OrderStatus, AuditTags.OrderType,
                                                AuditTags.CustomerName, AuditTags.CustomerId).filter(
                    AuditTags.TagNo.in_(chunk), AuditTags.Date == formatted_audit_date,
                                                AuditTags.BranchCode == branch_code, AuditTags.IsMSS == 0,
                                                AuditTags.isScannedInMss == 0,
                                                AuditTags.ScanId == scan_id, AuditTags.AuditedBy == user_id,
                                                AuditTags.IsValidTag == 1,
                                                AuditTags.IsNoStock == 1).all()
                serialized_result = SerializeSQLAResult(query_result).serialize()
                # print(serialized_result)
                no_stock_tag_details.extend(serialized_result)

        final_data = generate_final_data('DATA_FOUND')
        final_data['complaint'] = [{'status': 'Pending transfer out from CDC',
                                    'count': len(complaint_pending_transfer_out_from_cdc),
                                    'details': complaint_pending_transfer_out_from_cdc
                                    },
                                   {'status': 'In Transits to MSS',
                                    'count': len(complaint_in_transit_to_mss),
                                    'details': complaint_in_transit_to_mss
                                    },
                                   {'status': 'Transfer in at MSS',
                                    'count': len(complaint_transfer_in_at_mss),
                                    'details': complaint_transfer_in_at_mss
                                    },
                                   {'status': 'Pending for QC Verification',
                                    'count': len(complaint_pending_for_qc_verification),
                                    'details': complaint_pending_for_qc_verification
                                    },
                                   {'status': 'QC Approved',
                                    'count': len(complaint_qc_approved),
                                    'details': complaint_qc_approved
                                    },
                                   {'status': 'QC Rejected',
                                    'count': len(complaint_qc_rejected),
                                    'details': complaint_qc_rejected
                                    },
                                   {'status': 'Work Order Created',
                                    'count': len(complaint_work_order_created),
                                    'details': complaint_work_order_created
                                    },
                                   {'status': 'Resorted',
                                    'count': len(complaint_resorted),
                                    'details': complaint_resorted
                                    },
                                   {'status': 'In Transits to CDC',
                                    'count': len(complaint_in_transit_to_cdc),
                                    'details': complaint_in_transit_to_cdc
                                    },
                                   {'status': 'Transfer in at CDC',
                                    'count': len(complaint_transfer_in_at_cdc),
                                    'details': complaint_transfer_in_at_cdc
                                    },
                                   {'status': 'Invoiced & Delivered',
                                    'count': len(complaint_invoiced_and_delivered),
                                    'details': complaint_invoiced_and_delivered
                                    },
                                   {'status': 'Under Clearance of Invoice settlement',
                                    'count': len(complaint_under_clearance_of_invoice_settlement),
                                    'details': complaint_under_clearance_of_invoice_settlement
                                    },
                                   {'status': 'Missing',
                                    'count': len(complaint_missing),
                                    'details': complaint_missing
                                    },
                                   {'status': 'Damaged',
                                    'count': len(complaint_damaged),
                                    'details': complaint_damaged
                                    },
                                   {'status': 'Disputed Garment',
                                    'count': len(complaint_disputed_garment),
                                    'details': complaint_disputed_garment
                                    },
                                   {'status': 'Invoiced and Pending Delivery',
                                    'count': len(complaint_invoiced_and_pending_delivery),
                                    'details': complaint_invoiced_and_pending_delivery
                                    },
                                   {'status': 'Moved Back to Mss',
                                    'count': len(complaint_moved_back_to_mss),
                                    'details': complaint_moved_back_to_mss
                                    }
                                   ]
        final_data['without_complaint'] = [{'status': 'Pending transfer out from CDC',
                                            'count': len(without_complaint_pending_transfer_out_from_cdc),
                                            'details': without_complaint_pending_transfer_out_from_cdc
                                            },
                                           {'status': 'In Transits to MSS',
                                            'count': len(without_complaint_in_transit_to_mss),
                                            'details': without_complaint_in_transit_to_mss
                                            },
                                           {'status': 'Transfer in at MSS',
                                            'count': len(without_complaint_transfer_in_at_mss),
                                            'details': without_complaint_transfer_in_at_mss
                                            },
                                           {'status': 'Pending for QC Verification',
                                            'count': len(without_complaint_pending_for_qc_verification),
                                            'details': without_complaint_pending_for_qc_verification
                                            },
                                           {'status': 'QC Approved',
                                            'count': len(without_complaint_qc_approved),
                                            'details': without_complaint_qc_approved
                                            },
                                           {'status': 'QC Rejected',
                                            'count': len(without_complaint_qc_rejected),
                                            'details': without_complaint_qc_rejected
                                            },
                                           {'status': 'Work Order Created',
                                            'count': len(without_complaint_work_order_created),
                                            'details': without_complaint_work_order_created
                                            },
                                           {'status': 'Resorted',
                                            'count': len(without_complaint_resorted),
                                            'details': without_complaint_resorted
                                            },
                                           {'status': 'In Transits to CDC',
                                            'count': len(without_complaint_in_transit_to_cdc),
                                            'details': without_complaint_in_transit_to_cdc
                                            },
                                           {'status': 'Transfer in at CDC',
                                            'count': len(without_complaint_transfer_in_at_cdc),
                                            'details': without_complaint_transfer_in_at_cdc
                                            },
                                           {'status': 'Invoiced & Delivered',
                                            'count': len(without_complaint_invoiced_and_delivered),
                                            'details': without_complaint_invoiced_and_delivered
                                            },
                                           {'status': 'Under Clearance of Invoice settlement',
                                            'count': len(without_complaint_under_clearance_of_invoice_settlement),
                                            'details': without_complaint_under_clearance_of_invoice_settlement
                                            },
                                           {'status': 'Missing',
                                            'count': len(without_complaint_missing),
                                            'details': without_complaint_missing
                                            },
                                           {'status': 'Damaged',
                                            'count': len(without_complaint_damaged),
                                            'details': without_complaint_damaged
                                            },
                                           {'status': 'Disputed Garment',
                                            'count': len(without_complaint_disputed_garment),
                                            'details': without_complaint_disputed_garment
                                            },
                                           {'status': 'Invoiced and Pending Delivery',
                                            'count': len(without_complaint_invoiced_and_pending_delivery),
                                            'details': without_complaint_invoiced_and_pending_delivery
                                            },
                                           {'status': 'Moved Back to Mss',
                                            'count': len(without_complaint_moved_back_to_mss),
                                            'details': without_complaint_moved_back_to_mss
                                            }
                                           ]
        # final_data['other_stores'] = [
        #     {
        #         'status': 'Other stores',
        #         'count': len(store_count),
        #         'details': other_store_tag_details

        #     }]

        final_data['mss_tags'] = [{'status': 'Pending transfer out from CDC',
                                   'count': len(mss_pending_transfer_out_from_cdc),
                                   'details': mss_pending_transfer_out_from_cdc
                                   },
                                  {'status': 'In Transits to MSS',
                                   'count': len(mss_in_transit_to_mss),
                                   'details': mss_in_transit_to_mss
                                   },
                                  {'status': 'Transfer in at MSS',
                                   'count': len(mss_transfer_in_at_mss),
                                   'details': mss_transfer_in_at_mss
                                   },
                                  {'status': 'Pending for QC Verification',
                                   'count': len(mss_pending_for_qc_verification),
                                   'details': mss_pending_for_qc_verification
                                   },
                                  {'status': 'QC Approved',
                                   'count': len(mss_qc_approved),
                                   'details': mss_qc_approved
                                   },
                                  {'status': 'QC Rejected ',
                                   'count': len(mss_qc_rejected),
                                   'details': mss_qc_rejected
                                   },
                                  {'status': 'Work Order Created',
                                   'count': len(mss_work_order_created),
                                   'details': mss_work_order_created
                                   },
                                  {'status': 'Resorted',
                                   'count': len(mss_resorted),
                                   'details': mss_resorted
                                   },
                                  {'status': 'In Transits to CDC',
                                   'count': len(mss_in_transit_to_cdc),
                                   'details': mss_in_transit_to_cdc
                                   },
                                  {'status': 'Transfer in at CDC',
                                   'count': len(mss_transfer_in_at_cdc),
                                   'details': mss_transfer_in_at_cdc
                                   },
                                  {'status': 'Invoiced & Delivered',
                                   'count': len(mss_invoiced_and_delivered),
                                   'details': mss_invoiced_and_delivered
                                   },
                                  {'status': 'Under Clearance of Invoice settlement',
                                   'count': len(mss_under_clearance_of_invoice_settlement),
                                   'details': mss_under_clearance_of_invoice_settlement
                                   },
                                  {'status': 'Missing',
                                   'count': len(mss_missing),
                                   'details': mss_missing
                                   },
                                  {'status': 'Damaged',
                                   'count': len(mss_damaged),
                                   'details': mss_damaged
                                   },
                                  {'status': 'Disputed Garment',
                                   'count': len(mss_disputed_garment),
                                   'details': mss_disputed_garment
                                   },
                                  {'status': 'Invoiced and Pending Delivery',
                                   'count': len(mss_invoiced_and_pending_delivery),
                                   'details': mss_invoiced_and_pending_delivery
                                   },
                                  {'status': 'Moved Back to Mss',
                                   'count': len(mss_moved_back_to_mss),
                                   'details': mss_moved_back_to_mss
                                   }
                                  ]
        final_data['mss other store'] = [{'status': 'Pending transfer out from CDC',
                                          'count': len(mss_other_pending_transfer_out_from_cdc),
                                          'details': mss_other_pending_transfer_out_from_cdc
                                          },
                                         {'status': 'In Transits to MSS',
                                          'count': len(mss_other_in_transit_to_mss),
                                          'details': mss_other_in_transit_to_mss
                                          },
                                         {'status': 'Transfer in at MSS',
                                          'count': len(mss_other_transfer_in_at_mss),
                                          'details': mss_other_transfer_in_at_mss
                                          },
                                         {'status': 'Pending for QC Verification',
                                          'count': len(mss_other_pending_for_qc_verification),
                                          'details': mss_other_pending_for_qc_verification
                                          },
                                         {'status': 'QC Approved',
                                          'count': len(mss_other_qc_approved),
                                          'details': mss_other_qc_approved
                                          },
                                         {'status': 'QC Rejected',
                                          'count': len(mss_other_qc_rejected),
                                          'details': mss_other_qc_rejected
                                          },
                                         {'status': 'Work Order Created',
                                          'count': len(mss_other_work_order_created),
                                          'details': mss_other_work_order_created
                                          },
                                         {'status': 'Resorted',
                                          'count': len(mss_other_resorted),
                                          'details': mss_other_resorted
                                          },
                                         {'status': 'In Transits to CDC',
                                          'count': len(mss_other_in_transit_to_cdc),
                                          'details': mss_other_in_transit_to_cdc
                                          },
                                         {'status': 'Transfer in at CDC',
                                          'count': len(mss_other_transfer_in_at_cdc),
                                          'details': mss_other_transfer_in_at_cdc
                                          },
                                         {'status': 'Invoiced & Delivered',
                                          'count': len(mss_other_invoiced_and_delivered),
                                          'details': mss_other_invoiced_and_delivered
                                          },
                                         {'status': 'Under Clearance of Invoice settlement',
                                          'count': len(mss_other_under_clearance_of_invoice_settlement),
                                          'details': mss_other_under_clearance_of_invoice_settlement
                                          },
                                         {'status': 'Missing',
                                          'count': len(mss_other_missing),
                                          'details': mss_other_missing
                                          },
                                         {'status': 'Damaged',
                                          'count': len(mss_other_damaged),
                                          'details': mss_other_damaged
                                          },
                                         {'status': 'Disputed Garment',
                                          'count': len(mss_other_disputed_garment),
                                          'details': mss_other_disputed_garment
                                          },
                                         {'status': 'Invoiced and Pending Delivery',
                                          'count': len(mss_other_invoiced_and_pending_delivery),
                                          'details': mss_other_invoiced_and_pending_delivery
                                          },
                                         {'status': 'Moved Back to Mss',
                                          'count': len(mss_other_moved_back_to_mss),
                                          'details': mss_other_moved_back_to_mss
                                          }
                                         ]

        # [{
        #     "status":"Other store back to mss tags",
        #     "count":len(mss_other_store),
        #     "details":mss_other_store
        # }]

        log_data = {
            'back_to_mss_tags final2': back_to_mss_tags
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

     

        log_data = {
            'back_to_mss_tags final': back_to_mss_tags
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

        final_data['other_stores'] = other_stores_data
        final_data['noStockTag'] = [
            {
                'status': 'No Stock',
                'count': len(no_stock_tag_details),
                'details': no_stock_tag_details
            }
        ]
        
    else:
        final_data = generate_final_data('DATA_NOT_FOUND')
    return final_data


@audit_blueprint.route('get_tag_detailsNew', methods=["POST"])
# @authenticate('audit')#after change in other store issue
def get_tag_detailsNew():
    user_id = request.headers.get('user-id')
    tag_details_form = TagDetailsForm()
    log_data = {
        'tag_details_ReqBdyNew': tag_details_form.data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    if tag_details_form.validate_on_submit():

        with_complaints = None if tag_details_form.with_complaints.data == '' else tag_details_form.with_complaints.data
        without_complaints = None if tag_details_form.without_complaints.data == '' else tag_details_form.without_complaints.data
        other_stores = None if tag_details_form.other_stores.data == '' else tag_details_form.other_stores.data
        no_stock = None if tag_details_form.no_stock.data == '' else tag_details_form.no_stock.data
        audit_date = None if tag_details_form.audit_date.data == '' else tag_details_form.audit_date.data
        is_mss = tag_details_form.is_mss.data
        mss_other_store = None if tag_details_form.mss_other_store.data == '' else tag_details_form.mss_other_store.data
        back_to_mss_tags_form = None if tag_details_form.mss_tags.data == '' else tag_details_form.mss_tags.data
        back_to_mss_tags_list = back_to_mss_tags_form
        # latest_scan_id = tag_details_form.latest_scan_id.data
        scan_id = tag_details_form.latest_scan_id.data
        branch_code = tag_details_form.branch_code.data
        audit_date_obj = datetime.strptime(audit_date, "%d-%m-%Y")
        # formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        # audit_date_obj = datetime.strptime(audit_date, "%d-%m-%Y")
        # formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        # formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        # log_data = {
        # 'tag_details_ReqBdy without_complaints': without_complaints
        # }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        without_complaint_pending_transfer_out_from_cdc = []
        without_complaint_in_transit_to_mss = []
        without_complaint_pending_for_qc_verification = []
        without_complaint_transfer_in_at_mss = []
        without_complaint_qc_approved = []
        without_complaint_qc_rejected = []
        without_complaint_work_order_created = []
        without_complaint_missing = []
        without_complaint_damaged = []
        without_complaint_resorted = []
        without_complaint_in_transit_to_cdc = []
        without_complaint_transfer_in_at_cdc = []
        without_complaint_disputed_garment = []
        without_complaint_invoiced_and_delivered = []
        without_complaint_under_clearance_of_invoice_settlement = []
        without_complaint_invoiced_and_pending_delivery = []
        without_complaint_moved_back_to_mss = []
        without_complaint_no_stock = []

        complaint_pending_transfer_out_from_cdc = []
        complaint_in_transit_to_mss = []
        complaint_transfer_in_at_mss = []
        complaint_pending_for_qc_verification = []
        complaint_qc_approved = []
        complaint_qc_rejected = []
        complaint_work_order_created = []
        complaint_missing = []
        complaint_damaged = []
        complaint_resorted = []
        complaint_in_transit_to_cdc = []
        complaint_transfer_in_at_cdc = []
        complaint_disputed_garment = []
        complaint_invoiced_and_delivered = []
        complaint_under_clearance_of_invoice_settlement = []
        complaint_invoiced_and_pending_delivery = []
        complaint_moved_back_to_mss = []
        complaint_no_stock = []

        mss_pending_transfer_out_from_cdc = []
        mss_in_transit_to_mss = []
        mss_pending_for_qc_verification = []
        mss_transfer_in_at_mss = []
        mss_qc_approved = []
        mss_qc_rejected = []
        mss_work_order_created = []
        mss_missing = []
        mss_damaged = []
        mss_resorted = []
        mss_in_transit_to_cdc = []
        mss_transfer_in_at_cdc = []
        mss_disputed_garment = []
        mss_invoiced_and_delivered = []
        mss_under_clearance_of_invoice_settlement = []
        mss_invoiced_and_pending_delivery = []
        mss_moved_back_to_mss = []
        mss_no_stock = []

        mss_other_pending_transfer_out_from_cdc = []
        mss_other_in_transit_to_mss = []
        mss_other_pending_for_qc_verification = []
        mss_other_transfer_in_at_mss = []
        mss_other_qc_approved = []
        mss_other_qc_rejected = []
        mss_other_work_order_created = []
        mss_other_missing = []
        mss_other_damaged = []
        mss_other_resorted = []
        mss_other_in_transit_to_cdc = []
        mss_other_transfer_in_at_cdc = []
        mss_other_disputed_garment = []
        mss_other_invoiced_and_delivered = []
        mss_other_under_clearance_of_invoice_settlement = []
        mss_other_invoiced_and_pending_delivery = []
        mss_other_moved_back_to_mss = []
        mss_other_no_stock = []

        # log_data = {
        #     'NoStock': len(no_stock)

        # }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        # max_scan_id_subquery = db.session.query(func.max(AuditTags.ScanId)).scalar()
        # from sqlalchemy import func
        # latest_scan_id = db.session.query(func.max(AuditTags.ScanId)).filter(
        #     AuditTags.AuditedBy == user_id,
        #     AuditTags.Date == date.today(), AuditTags.BranchCode == branch_code
        # ).scalar()

        if with_complaints is not None:
            # complaint_tag_details = db.session.query(AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus,
            #                                          AuditTags.ComplaintDepartment, AuditTags.ComplaintDate,
            #                                          AuditTags.EntryType, AuditTags.ComplaintId,
            #                                          AuditTags.GarmentStatus, AuditTags.OrderStatus,
            #                                          AuditTags.CustomerName, AuditTags.CustomerId
            #                                          ).filter(AuditTags.TagNo.in_(with_complaints),
            #                                                   AuditTags.Date == formatted_audit_date,
            #                                                   AuditTags.ScannedBy == user_id,
            #                                                   AuditTags.IsMSS == is_mss,
            #                                                   AuditTags.BranchCode == branch_code).all()
            complaint_tag_details = db.session.query(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).filter(
                AuditTags.TagNo.in_(with_complaints),
                AuditTags.Date == formatted_audit_date,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsMSS == is_mss,
                AuditTags.BranchCode == branch_code,
                AuditTags.ScanId == scan_id,
                AuditTags.isScannedInMss == 0
            ).group_by(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount, AuditTags,
                AuditTags.OrderType
            ).all()

            complaint_tag_details = SerializeSQLAResult(complaint_tag_details).serialize()
            for complaint in complaint_tag_details:
                if complaint['GarmentStatus'] == 'In Transits to CDC':
                    complaint_in_transit_to_cdc.append(complaint)
                elif complaint['GarmentStatus'] in ['Resorted']:
                    complaint_resorted.append(complaint)
                elif complaint['GarmentStatus'] in ['Work Order Created ']:
                    complaint_work_order_created.append(complaint)
                elif complaint['GarmentStatus'] in ['In Transits to mss']:
                    complaint_in_transit_to_mss.append(complaint)
                elif complaint['GarmentStatus'] in ['Pending Transfer Out From CDC']:
                    complaint_pending_transfer_out_from_cdc.append(complaint)
                elif complaint['GarmentStatus'] in ['Invoiced & Delivered']:
                    complaint_invoiced_and_delivered.append(complaint)
                elif complaint['GarmentStatus'] in ['Transfer in at CDC']:
                    complaint_transfer_in_at_cdc.append(complaint)
                elif complaint['GarmentStatus'] in ['Pending for QC Verification']:
                    complaint_pending_for_qc_verification.append(complaint)
                elif complaint['GarmentStatus'] in ['Transfer in at mss']:
                    complaint_transfer_in_at_mss.append(complaint)
                elif complaint['GarmentStatus'] in ['QC Approved']:
                    complaint_qc_approved.append(complaint)
                elif complaint['GarmentStatus'] in ['QC Rejected ']:
                    complaint_qc_rejected.append(complaint)
                elif complaint['GarmentStatus'] in ['Moved Back to Mss']:
                    complaint_moved_back_to_mss.append(complaint)
                elif complaint['GarmentStatus'] in ['Invoiced & Pending Delivery']:
                    complaint_invoiced_and_pending_delivery.append(complaint)
                elif complaint['GarmentStatus'] in ['Under clearance of Invoice settlement']:
                    complaint_under_clearance_of_invoice_settlement.append(complaint)
                elif complaint['GarmentStatus'] in ['Missing']:
                    complaint_missing.append(complaint)
                elif complaint['GarmentStatus'] in ['Damaged']:
                    complaint_damaged.append(complaint)
                elif complaint['GarmentStatus'] in ['Disputed Garment']:
                    complaint_disputed_garment.append(complaint)
                else:
                    complaint_no_stock.append(complaint)


        if without_complaints is not None:
            log_data = {
                'without_complaints 1': 'without_complaints 1'

            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            # without_complaints_tag_details = db.session.query(
            #     AuditTags.TagNo,
            #     AuditTags.EGRN,
            #     AuditTags.ComplaintStatus,
            #     AuditTags.ComplaintDepartment,
            #     AuditTags.ComplaintDate,
            #     AuditTags.EntryType,
            #     AuditTags.ComplaintId,
            #     AuditTags.GarmentStatus,
            #     AuditTags.OrderStatus,
            #     AuditTags.CustomerName,
            #     AuditTags.CustomerId,
            #     AuditTags.GarmentName,
            #     AuditTags.GarmentAmount,
            #     AuditTags.OrderType
            # ).filter(
            #     AuditTags.TagNo.in_(without_complaints),
            #     AuditTags.Date == formatted_audit_date,
            #     AuditTags.ScannedBy == user_id,
            #     AuditTags.IsMSS == is_mss,
            #     AuditTags.BranchCode == branch_code, AuditTags.ScanId == scan_id,
            #     AuditTags.isScannedInMss == 0
            # ).all()

            # without_complaints_tag_details = SerializeSQLAResult(without_complaints_tag_details).serialize()

            # Splitting the list into batches of 1000 (or a smaller number if necessary)
            batch_size = 1000
            without_complaints_tag_details = []
            log_data = {
                'batched_results 11': user_id

            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))

            for i in range(0, len(without_complaints), batch_size):
                batch = without_complaints[i:i + batch_size]
                params = {
                    'without_complaints': tuple(batch),
                    'formatted_audit_date': formatted_audit_date,
                    'user_id': user_id,
                    'is_mss': is_mss,
                    'branch_code': branch_code,
                    'scan_id': scan_id
                }
                
                sql_query = """
                SELECT
                    AuditTags.TagNo,
                    AuditTags.EGRN,
                    AuditTags.ComplaintStatus,
                    AuditTags.ComplaintDepartment,
                    AuditTags.ComplaintDate,
                    AuditTags.EntryType,
                    AuditTags.ComplaintId,
                    AuditTags.GarmentStatus,
                    AuditTags.OrderStatus,
                    AuditTags.CustomerName,
                    AuditTags.CustomerId,
                    AuditTags.GarmentName,
                    AuditTags.GarmentAmount,
                    AuditTags.OrderType
                FROM AuditTags
                WHERE
                    AuditTags.TagNo IN :without_complaints AND
                    AuditTags.Date = :formatted_audit_date AND
                    AuditTags.ScannedBy = :user_id AND
                    AuditTags.IsMSS = :is_mss AND
                    AuditTags.BranchCode = :branch_code AND
                    AuditTags.ScanId = :scan_id AND
                    AuditTags.isScannedInMss = 0
                """
                
                result = db.session.execute(text(sql_query), params).fetchall()
                without_complaints_tag_details.extend(result)

            # for row in batched_results:
            log_data = {
                'batched_results': 'without_complaints',
                'User:':user_id

            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))

            for without_complaint in without_complaints_tag_details:
                if without_complaint['GarmentStatus'] == 'In Transits to CDC':
                    without_complaint_in_transit_to_cdc.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Resorted']:
                    without_complaint_resorted.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Work Order Created ']:
                    without_complaint_work_order_created.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['In Transits to mss']:
                    without_complaint_in_transit_to_mss.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Pending Transfer Out From CDC']:
                    without_complaint_pending_transfer_out_from_cdc.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Invoiced & Delivered']:
                    without_complaint_invoiced_and_delivered.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Transfer in at CDC']:
                    without_complaint_transfer_in_at_cdc.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Pending for QC Verification']:
                    without_complaint_pending_for_qc_verification.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Transfer in at mss']:
                    without_complaint_transfer_in_at_mss.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['QC Approved']:
                    without_complaint_qc_approved.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['QC Rejected ']:
                    without_complaint_qc_rejected.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Moved Back to Mss']:
                    without_complaint_moved_back_to_mss.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Invoiced & Pending Delivery']:
                    without_complaint_invoiced_and_pending_delivery.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Under clearance of Invoice settlement']:
                    without_complaint_under_clearance_of_invoice_settlement.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Missing']:
                    without_complaint_missing.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Damaged']:
                    without_complaint_damaged.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Disputed Garment']:
                    without_complaint_disputed_garment.append(without_complaint)
                else:
                    without_complaint_no_stock.append(without_complaint)
        if other_stores is not None:
            other_store_tag_details = db.session.query(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.GarmentBranchName,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).filter(
                AuditTags.TagNo.in_(other_stores),
                AuditTags.Date == formatted_audit_date,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsMSS == is_mss,
                AuditTags.BranchCode == branch_code,
                AuditTags.ScanId == scan_id,
                AuditTags.isScannedInMss == 0
            ).group_by(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.GarmentBranchName,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).all()

            other_store_tag_details = SerializeSQLAResult(other_store_tag_details).serialize()
            # stores = []
            # for other_store in other_store_tag_details:
            #     stores.append(other_store['GarmentBranchName'])
            # store_count = []
            # for store in stores:
            #     count = stores.count(store)
            #     branches = {store: count}
            #     store_count.append(branches)
            #     stores.remove(store)

            # Group tag details by branch name
            branch_tags = defaultdict(list)
            for tag_detail in other_store_tag_details:
                branch_tags[tag_detail['GarmentBranchName']].append(tag_detail)

            # Create the final data structure
            other_stores_data = []
            for branch_name, tags in branch_tags.items():
                other_stores_data.append({
                    'status': 'Other stores',
                    'count': len(tags),
                    'details': tags
                })
            if not other_stores_data:
                other_stores_data.append({
                    'status': 'Other stores',
                    'count': 0,
                    'details': []
                })
        log_data = {
            # 'back_to_mss_tags': back_to_mss_tags
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        if back_to_mss_tags_form is not None:

            log_data = {
                'ScanId': scan_id,
                'formatted_audit_date': formatted_audit_date
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            if is_mss:
                log_data = {
                    'ScanId_is_mss:': is_mss

                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))

                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date =:formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss=0 AND IsMSS=1                                      
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()

                log_data = {
                    'route': query,
                    'DATE': formatted_audit_date,
                    'query_result': [dict(row) for row in result]
                }

                # Logging the result with proper JSON formatting
                info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

                # query = text("""
                # SELECT  TagNo, EGRN, ComplaintStatus,  ComplaintDepartment,  ComplaintDate, EntryType,  ComplaintId, GarmentStatus,  GarmentBranchName,
                #     OrderStatus,  CustomerName, CustomerId,  GarmentName,  GarmentAmount, OrderType FROM  AuditTags
                # WHERE  TagNo IN :back_to_mss_tags
                #     AND Date = :formatted_audit_date
                #     AND ScannedBy = :user_id
                #     AND IsMSS = 0
                #     AND BranchCode = :branch_code
                #     AND ScanId = :scan_id
                #     AND isScannedInMss = 1
                #     AND GarmentBranchCode = :branch_code
                # GROUP BY  TagNo, EGRN,  ComplaintStatus, ComplaintDepartment,  ComplaintDate,  EntryType, ComplaintId, GarmentStatus, GarmentBranchName,
                #     OrderStatus,  CustomerName,  CustomerId,  GarmentName,  GarmentAmount,  OrderType """)
                # # Execute the query and fetch results
                # result = db.session.execute(query, {
                #     'back_to_mss_tags': tuple(back_to_mss_tags_list),
                #     'formatted_audit_date': formatted_audit_date, 'user_id': user_id,  'branch_code': branch_code,  'scan_id': scan_id
                # }).fetchall()
            else:
                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date = :formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss = 1 AND IsMSS=0  
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()
                # query = text("""
                #                SELECT  TagNo, EGRN, ComplaintStatus,  ComplaintDepartment,  ComplaintDate, EntryType,  ComplaintId, GarmentStatus,  GarmentBranchName,
                #                    OrderStatus,  CustomerName, CustomerId,  GarmentName,  GarmentAmount, OrderType FROM  AuditTags
                #                WHERE  Date = :formatted_audit_date
                #                    AND ScannedBy = :user_id
                #                    AND IsMSS = 0
                #                    AND BranchCode = :branch_code
                #                    AND ScanId = :scan_id
                #                    AND GarmentBranchCode = :branch_code
                #                GROUP BY  TagNo, EGRN,  ComplaintStatus, ComplaintDepartment,  ComplaintDate,  EntryType, ComplaintId, GarmentStatus, GarmentBranchName,
                #                    OrderStatus,  CustomerName,  CustomerId,  GarmentName,  GarmentAmount,  OrderType """)
                # # Execute the query and fetch results
                # result = db.session.execute(query, {
                #     'formatted_audit_date': formatted_audit_date, 'user_id': user_id, 'branch_code': branch_code,
                #     'scan_id': scan_id
                # }).fetchall()

                log_data = {
                    'route': query,
                    'DATE': formatted_audit_date,
                    'query_result': [dict(row) for row in result]
                }

                # Logging the result with proper JSON formatting
                info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

            back_to_mss_tags = SerializeSQLAResult(result).serialize()

            log_data = {
                'back_to_mss_tags11': back_to_mss_tags
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

            for mss in back_to_mss_tags:
                if mss['GarmentStatus'] == 'In Transits to CDC':
                    mss_in_transit_to_cdc.append(mss)
                elif mss['GarmentStatus'] == 'Resorted':
                    mss_resorted.append(mss)
                elif mss['GarmentStatus'] == 'Work Order Created':
                    mss_work_order_created.append(mss)
                elif mss['GarmentStatus'] == 'In Transits to mss':
                    mss_in_transit_to_mss.append(mss)
                elif mss['GarmentStatus'] == 'Pending Transfer Out From CDC':
                    mss_pending_transfer_out_from_cdc.append(mss)
                elif mss['GarmentStatus'] == 'Invoiced & Delivered':
                    mss_invoiced_and_delivered.append(mss)
                elif mss['GarmentStatus'] == 'Transfer in at CDC':
                    mss_transfer_in_at_cdc.append(mss)
                elif mss['GarmentStatus'] == 'Pending for QC Verification':
                    mss_pending_for_qc_verification.append(mss)
                elif mss['GarmentStatus'] == 'Transfer in at mss':
                    mss_transfer_in_at_mss.append(mss)
                elif mss['GarmentStatus'] == 'QC Approved':
                    mss_qc_approved.append(mss)
                elif mss['GarmentStatus'] == 'QC Rejected ':
                    mss_qc_rejected.append(mss)
                elif mss['GarmentStatus'] == 'Moved Back to Mss':
                    mss_moved_back_to_mss.append(mss)
                elif mss['GarmentStatus'] == 'Invoiced & Pending Delivery':
                    mss_invoiced_and_pending_delivery.append(mss)
                elif mss['GarmentStatus'] == 'Under clearance of Invoice settlement':
                    mss_under_clearance_of_invoice_settlement.append(mss)
                elif mss['GarmentStatus'] == 'Missing':
                    mss_missing.append(mss)
                elif mss['GarmentStatus'] == 'Damaged':
                    mss_damaged.append(mss)
                elif mss['GarmentStatus'] == 'Disputed Garment':
                    mss_disputed_garment.append(mss)
                else:
                    mss_no_stock.append(mss)
        log_data = {
            'back_to_mss_tagsmss': complaint_in_transit_to_mss
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

        if mss_other_store is not None:
            log_data = {
                'mss_tagsmss': is_mss
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

            if is_mss:
                log_data = {
                    'ScanId_is_mss:': is_mss

                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))

                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date =:formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss=0 AND IsMSS=1 
                                        AND GarmentBranchCode != :branch_code                                 
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()

                # query = text("""
                # SELECT  TagNo, EGRN, ComplaintStatus,  ComplaintDepartment,  ComplaintDate, EntryType,  ComplaintId, GarmentStatus,  GarmentBranchName,
                #     OrderStatus,  CustomerName, CustomerId,  GarmentName,  GarmentAmount, OrderType FROM  AuditTags
                # WHERE  TagNo IN :back_to_mss_tags
                #     AND Date = :formatted_audit_date
                #     AND ScannedBy = :user_id
                #     AND IsMSS = 0
                #     AND BranchCode = :branch_code
                #     AND ScanId = :scan_id
                #     AND isScannedInMss = 1
                #     AND GarmentBranchCode = :branch_code
                # GROUP BY  TagNo, EGRN,  ComplaintStatus, ComplaintDepartment,  ComplaintDate,  EntryType, ComplaintId, GarmentStatus, GarmentBranchName,
                #     OrderStatus,  CustomerName,  CustomerId,  GarmentName,  GarmentAmount,  OrderType """)
                # # Execute the query and fetch results
                # result = db.session.execute(query, {
                #     'back_to_mss_tags': tuple(back_to_mss_tags_list),
                #     'formatted_audit_date': formatted_audit_date, 'user_id': user_id,  'branch_code': branch_code,  'scan_id': scan_id
                # }).fetchall()
            else:
                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date = :formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss = 1 AND IsMSS=0  
                                        AND GarmentBranchCode != :branch_code 
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()
            log_data = {
                'route': query,
                'DATE': formatted_audit_date,
                'query_result': [dict(row) for row in result]
            }

            # Logging the result with proper JSON formatting
            info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

            mss_other_store = SerializeSQLAResult(result).serialize()

            log_data = {
                'mss_tagsmss': mss_other_store
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

            for mss_other in mss_other_store:
                # for mss_other in back_to_mss_tags:
                if mss_other['GarmentStatus'] == 'In Transits to CDC':
                    mss_other_in_transit_to_cdc.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Resorted':
                    mss_other_resorted.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Work Order Created':
                    other_work_order_created.append(mss_other)
                elif mss_other['GarmentStatus'] == 'In Transits to mss':
                    mss_other_in_transit_to_mss.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Pending Transfer Out From CDC':
                    mss_other_pending_transfer_out_from_cdc.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Invoiced & Delivered':
                    mss_other_invoiced_and_delivered.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Transfer in at CDC':
                    mss_other_transfer_in_at_cdc.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Pending for QC Verification':
                    mss_other_pending_for_qc_verification.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Transfer in at mss':
                    mss_other_transfer_in_at_mss.append(mss_other)
                elif mss_other['GarmentStatus'] == 'QC Approved':
                    mss_other_qc_approved.append(mss_other)
                elif mss_other['GarmentStatus'] == 'QC Rejected ':
                    mss_other_qc_rejected.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Moved Back to Mss':
                    mss_other_moved_back_to_mss.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Invoiced & Pending Delivery':
                    mss_other_invoiced_and_pending_delivery.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Under clearance of Invoice settlement':
                    mss_other_under_clearance_of_invoice_settlement.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Missing':
                    mss_other_missing.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Damaged':
                    mss_other_damaged.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Disputed Garment':
                    mss_other_disputed_garment.append(mss_other)
                else:
                    mss_other_no_stock.append(mss_other)

        if no_stock is not None:
            chunk_size = 1000
            no_stock_tag_details = []
            serialized_result = []
            for i in range(0, len(no_stock), chunk_size):
                chunk = no_stock[i:i + chunk_size]
                # print(chunk)
                query_result = db.session.query(AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus,
                                                AuditTags.ComplaintDepartment, AuditTags.ComplaintDate,
                                                AuditTags.ComplaintId, AuditTags.EntryType,
                                                AuditTags.GarmentStatus, AuditTags.GarmentBranchName,
                                                AuditTags.GarmentName, AuditTags.GarmentAmount,
                                                AuditTags.OrderStatus, AuditTags.OrderType,
                                                AuditTags.CustomerName, AuditTags.CustomerId).filter(
                    AuditTags.TagNo.in_(chunk), AuditTags.Date == formatted_audit_date,
                                                AuditTags.BranchCode == branch_code, AuditTags.IsMSS == 0,
                                                AuditTags.isScannedInMss == 0,
                                                AuditTags.ScanId == scan_id, AuditTags.AuditedBy == user_id,
                                                AuditTags.IsValidTag == 1,
                                                AuditTags.IsNoStock == 1).all()
                serialized_result = SerializeSQLAResult(query_result).serialize()
                # print(serialized_result)
                no_stock_tag_details.extend(serialized_result)

        final_data = generate_final_data('DATA_FOUND')
        final_data['complaint'] = [{'status': 'Pending transfer out from CDC',
                                    'count': len(complaint_pending_transfer_out_from_cdc),
                                    'details': complaint_pending_transfer_out_from_cdc
                                    },
                                   {'status': 'In Transits to MSS',
                                    'count': len(complaint_in_transit_to_mss),
                                    'details': complaint_in_transit_to_mss
                                    },
                                   {'status': 'Transfer in at MSS',
                                    'count': len(complaint_transfer_in_at_mss),
                                    'details': complaint_transfer_in_at_mss
                                    },
                                   {'status': 'Pending for QC Verification',
                                    'count': len(complaint_pending_for_qc_verification),
                                    'details': complaint_pending_for_qc_verification
                                    },
                                   {'status': 'QC Approved',
                                    'count': len(complaint_qc_approved),
                                    'details': complaint_qc_approved
                                    },
                                   {'status': 'QC Rejected',
                                    'count': len(complaint_qc_rejected),
                                    'details': complaint_qc_rejected
                                    },
                                   {'status': 'Work Order Created',
                                    'count': len(complaint_work_order_created),
                                    'details': complaint_work_order_created
                                    },
                                   {'status': 'Resorted',
                                    'count': len(complaint_resorted),
                                    'details': complaint_resorted
                                    },
                                   {'status': 'In Transits to CDC',
                                    'count': len(complaint_in_transit_to_cdc),
                                    'details': complaint_in_transit_to_cdc
                                    },
                                   {'status': 'Transfer in at CDC',
                                    'count': len(complaint_transfer_in_at_cdc),
                                    'details': complaint_transfer_in_at_cdc
                                    },
                                   {'status': 'Invoiced & Delivered',
                                    'count': len(complaint_invoiced_and_delivered),
                                    'details': complaint_invoiced_and_delivered
                                    },
                                   {'status': 'Under Clearance of Invoice settlement',
                                    'count': len(complaint_under_clearance_of_invoice_settlement),
                                    'details': complaint_under_clearance_of_invoice_settlement
                                    },
                                   {'status': 'Missing',
                                    'count': len(complaint_missing),
                                    'details': complaint_missing
                                    },
                                   {'status': 'Damaged',
                                    'count': len(complaint_damaged),
                                    'details': complaint_damaged
                                    },
                                   {'status': 'Disputed Garment',
                                    'count': len(complaint_disputed_garment),
                                    'details': complaint_disputed_garment
                                    },
                                   {'status': 'Invoiced and Pending Delivery',
                                    'count': len(complaint_invoiced_and_pending_delivery),
                                    'details': complaint_invoiced_and_pending_delivery
                                    },
                                   {'status': 'Moved Back to Mss',
                                    'count': len(complaint_moved_back_to_mss),
                                    'details': complaint_moved_back_to_mss
                                    }
                                   ]
        final_data['without_complaint'] = [{'status': 'Pending transfer out from CDC',
                                            'count': len(without_complaint_pending_transfer_out_from_cdc),
                                            'details': without_complaint_pending_transfer_out_from_cdc
                                            },
                                           {'status': 'In Transits to MSS',
                                            'count': len(without_complaint_in_transit_to_mss),
                                            'details': without_complaint_in_transit_to_mss
                                            },
                                           {'status': 'Transfer in at MSS',
                                            'count': len(without_complaint_transfer_in_at_mss),
                                            'details': without_complaint_transfer_in_at_mss
                                            },
                                           {'status': 'Pending for QC Verification',
                                            'count': len(without_complaint_pending_for_qc_verification),
                                            'details': without_complaint_pending_for_qc_verification
                                            },
                                           {'status': 'QC Approved',
                                            'count': len(without_complaint_qc_approved),
                                            'details': without_complaint_qc_approved
                                            },
                                           {'status': 'QC Rejected',
                                            'count': len(without_complaint_qc_rejected),
                                            'details': without_complaint_qc_rejected
                                            },
                                           {'status': 'Work Order Created',
                                            'count': len(without_complaint_work_order_created),
                                            'details': without_complaint_work_order_created
                                            },
                                           {'status': 'Resorted',
                                            'count': len(without_complaint_resorted),
                                            'details': without_complaint_resorted
                                            },
                                           {'status': 'In Transits to CDC',
                                            'count': len(without_complaint_in_transit_to_cdc),
                                            'details': without_complaint_in_transit_to_cdc
                                            },
                                           {'status': 'Transfer in at CDC',
                                            'count': len(without_complaint_transfer_in_at_cdc),
                                            'details': without_complaint_transfer_in_at_cdc
                                            },
                                           {'status': 'Invoiced & Delivered',
                                            'count': len(without_complaint_invoiced_and_delivered),
                                            'details': without_complaint_invoiced_and_delivered
                                            },
                                           {'status': 'Under Clearance of Invoice settlement',
                                            'count': len(without_complaint_under_clearance_of_invoice_settlement),
                                            'details': without_complaint_under_clearance_of_invoice_settlement
                                            },
                                           {'status': 'Missing',
                                            'count': len(without_complaint_missing),
                                            'details': without_complaint_missing
                                            },
                                           {'status': 'Damaged',
                                            'count': len(without_complaint_damaged),
                                            'details': without_complaint_damaged
                                            },
                                           {'status': 'Disputed Garment',
                                            'count': len(without_complaint_disputed_garment),
                                            'details': without_complaint_disputed_garment
                                            },
                                           {'status': 'Invoiced and Pending Delivery',
                                            'count': len(without_complaint_invoiced_and_pending_delivery),
                                            'details': without_complaint_invoiced_and_pending_delivery
                                            },
                                           {'status': 'Moved Back to Mss',
                                            'count': len(without_complaint_moved_back_to_mss),
                                            'details': without_complaint_moved_back_to_mss
                                            }
                                           ]
        # final_data['other_stores'] = [
        #     {
        #         'status': 'Other stores',
        #         'count': len(store_count),
        #         'details': other_store_tag_details

        #     }]

        final_data['mss_tags'] = [{'status': 'Pending transfer out from CDC',
                                   'count': len(mss_pending_transfer_out_from_cdc),
                                   'details': mss_pending_transfer_out_from_cdc
                                   },
                                  {'status': 'In Transits to MSS',
                                   'count': len(mss_in_transit_to_mss),
                                   'details': mss_in_transit_to_mss
                                   },
                                  {'status': 'Transfer in at MSS',
                                   'count': len(mss_transfer_in_at_mss),
                                   'details': mss_transfer_in_at_mss
                                   },
                                  {'status': 'Pending for QC Verification',
                                   'count': len(mss_pending_for_qc_verification),
                                   'details': mss_pending_for_qc_verification
                                   },
                                  {'status': 'QC Approved',
                                   'count': len(mss_qc_approved),
                                   'details': mss_qc_approved
                                   },
                                  {'status': 'QC Rejected ',
                                   'count': len(mss_qc_rejected),
                                   'details': mss_qc_rejected
                                   },
                                  {'status': 'Work Order Created',
                                   'count': len(mss_work_order_created),
                                   'details': mss_work_order_created
                                   },
                                  {'status': 'Resorted',
                                   'count': len(mss_resorted),
                                   'details': mss_resorted
                                   },
                                  {'status': 'In Transits to CDC',
                                   'count': len(mss_in_transit_to_cdc),
                                   'details': mss_in_transit_to_cdc
                                   },
                                  {'status': 'Transfer in at CDC',
                                   'count': len(mss_transfer_in_at_cdc),
                                   'details': mss_transfer_in_at_cdc
                                   },
                                  {'status': 'Invoiced & Delivered',
                                   'count': len(mss_invoiced_and_delivered),
                                   'details': mss_invoiced_and_delivered
                                   },
                                  {'status': 'Under Clearance of Invoice settlement',
                                   'count': len(mss_under_clearance_of_invoice_settlement),
                                   'details': mss_under_clearance_of_invoice_settlement
                                   },
                                  {'status': 'Missing',
                                   'count': len(mss_missing),
                                   'details': mss_missing
                                   },
                                  {'status': 'Damaged',
                                   'count': len(mss_damaged),
                                   'details': mss_damaged
                                   },
                                  {'status': 'Disputed Garment',
                                   'count': len(mss_disputed_garment),
                                   'details': mss_disputed_garment
                                   },
                                  {'status': 'Invoiced and Pending Delivery',
                                   'count': len(mss_invoiced_and_pending_delivery),
                                   'details': mss_invoiced_and_pending_delivery
                                   },
                                  {'status': 'Moved Back to Mss',
                                   'count': len(mss_moved_back_to_mss),
                                   'details': mss_moved_back_to_mss
                                   }
                                  ]
        final_data['mss other store'] = [{'status': 'Pending transfer out from CDC',
                                          'count': len(mss_other_pending_transfer_out_from_cdc),
                                          'details': mss_other_pending_transfer_out_from_cdc
                                          },
                                         {'status': 'In Transits to MSS',
                                          'count': len(mss_other_in_transit_to_mss),
                                          'details': mss_other_in_transit_to_mss
                                          },
                                         {'status': 'Transfer in at MSS',
                                          'count': len(mss_other_transfer_in_at_mss),
                                          'details': mss_other_transfer_in_at_mss
                                          },
                                         {'status': 'Pending for QC Verification',
                                          'count': len(mss_other_pending_for_qc_verification),
                                          'details': mss_other_pending_for_qc_verification
                                          },
                                         {'status': 'QC Approved',
                                          'count': len(mss_other_qc_approved),
                                          'details': mss_other_qc_approved
                                          },
                                         {'status': 'QC Rejected',
                                          'count': len(mss_other_qc_rejected),
                                          'details': mss_other_qc_rejected
                                          },
                                         {'status': 'Work Order Created',
                                          'count': len(mss_other_work_order_created),
                                          'details': mss_other_work_order_created
                                          },
                                         {'status': 'Resorted',
                                          'count': len(mss_other_resorted),
                                          'details': mss_other_resorted
                                          },
                                         {'status': 'In Transits to CDC',
                                          'count': len(mss_other_in_transit_to_cdc),
                                          'details': mss_other_in_transit_to_cdc
                                          },
                                         {'status': 'Transfer in at CDC',
                                          'count': len(mss_other_transfer_in_at_cdc),
                                          'details': mss_other_transfer_in_at_cdc
                                          },
                                         {'status': 'Invoiced & Delivered',
                                          'count': len(mss_other_invoiced_and_delivered),
                                          'details': mss_other_invoiced_and_delivered
                                          },
                                         {'status': 'Under Clearance of Invoice settlement',
                                          'count': len(mss_other_under_clearance_of_invoice_settlement),
                                          'details': mss_other_under_clearance_of_invoice_settlement
                                          },
                                         {'status': 'Missing',
                                          'count': len(mss_other_missing),
                                          'details': mss_other_missing
                                          },
                                         {'status': 'Damaged',
                                          'count': len(mss_other_damaged),
                                          'details': mss_other_damaged
                                          },
                                         {'status': 'Disputed Garment',
                                          'count': len(mss_other_disputed_garment),
                                          'details': mss_other_disputed_garment
                                          },
                                         {'status': 'Invoiced and Pending Delivery',
                                          'count': len(mss_other_invoiced_and_pending_delivery),
                                          'details': mss_other_invoiced_and_pending_delivery
                                          },
                                         {'status': 'Moved Back to Mss',
                                          'count': len(mss_other_moved_back_to_mss),
                                          'details': mss_other_moved_back_to_mss
                                          }
                                         ]

        # [{
        #     "status":"Other store back to mss tags",
        #     "count":len(mss_other_store),
        #     "details":mss_other_store
        # }]

        log_data = {
            'back_to_mss_tags final2': back_to_mss_tags
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

     

        log_data = {
            'back_to_mss_tags final': back_to_mss_tags
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data, default=str))

        final_data['other_stores'] = other_stores_data
        final_data['noStockTag'] = [
            {
                'status': 'No Stock',
                'count': len(no_stock_tag_details),
                'details': no_stock_tag_details
            }
        ]
        
    else:
        final_data = generate_final_data('DATA_NOT_FOUND')
    return final_data

@audit_blueprint.route('get_tag_details_garment', methods=["POST"])
@authenticate('audit')#after change in other store issue
def get_tag_details_garment():
    user_id = request.headers.get('user-id')
    tag_details_form = TagDetailsForm()
    log_data = {
        'tag_details_form': tag_details_form.data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    if tag_details_form.validate_on_submit():

        with_complaints = None if tag_details_form.with_complaints.data == '' else tag_details_form.with_complaints.data
        without_complaints = None if tag_details_form.without_complaints.data == '' else tag_details_form.without_complaints.data
        other_stores = None if tag_details_form.other_stores.data == '' else tag_details_form.other_stores.data
        no_stock = None if tag_details_form.no_stock.data == '' else tag_details_form.no_stock.data
        audit_date = None if tag_details_form.audit_date.data == '' else tag_details_form.audit_date.data
        is_mss = tag_details_form.is_mss.data
        mss_other_store = None if tag_details_form.mss_other_store.data == '' else tag_details_form.mss_other_store.data
        back_to_mss_tags_form = None if tag_details_form.mss_tags.data == '' else tag_details_form.mss_tags.data
        back_to_mss_tags_list = back_to_mss_tags_form
        # latest_scan_id = tag_details_form.latest_scan_id.data
        scan_id = tag_details_form.latest_scan_id.data
        branch_code = tag_details_form.branch_code.data
        audit_date_obj = datetime.strptime(audit_date, "%d-%m-%Y")
        # formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        # audit_date_obj = datetime.strptime(audit_date, "%d-%m-%Y")
        # formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        # formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        without_complaint_pending_transfer_out_from_cdc = []
        without_complaint_in_transit_to_mss = []
        without_complaint_pending_for_qc_verification = []
        without_complaint_transfer_in_at_mss = []
        without_complaint_qc_approved = []
        without_complaint_qc_rejected = []
        without_complaint_work_order_created = []
        without_complaint_missing = []
        without_complaint_damaged = []
        without_complaint_resorted = []
        without_complaint_in_transit_to_cdc = []
        without_complaint_transfer_in_at_cdc = []
        without_complaint_disputed_garment = []
        without_complaint_invoiced_and_delivered = []
        without_complaint_under_clearance_of_invoice_settlement = []
        without_complaint_invoiced_and_pending_delivery = []
        without_complaint_moved_back_to_mss = []
        without_complaint_no_stock = []
        other_work_order_created = []
        complaint_pending_transfer_out_from_cdc = []
        complaint_in_transit_to_mss = []
        complaint_transfer_in_at_mss = []
        complaint_pending_for_qc_verification = []
        complaint_qc_approved = []
        complaint_qc_rejected = []
        complaint_work_order_created = []
        complaint_missing = []
        complaint_damaged = []
        complaint_resorted = []
        complaint_in_transit_to_cdc = []
        complaint_transfer_in_at_cdc = []
        complaint_disputed_garment = []
        complaint_invoiced_and_delivered = []
        complaint_under_clearance_of_invoice_settlement = []
        complaint_invoiced_and_pending_delivery = []
        complaint_moved_back_to_mss = []
        complaint_no_stock = []

        serialized_result = []

        mss_pending_transfer_out_from_cdc = []
        mss_in_transit_to_mss = []
        mss_pending_for_qc_verification = []
        mss_transfer_in_at_mss = []
        mss_qc_approved = []
        mss_qc_rejected = []
        mss_work_order_created = []
        mss_missing = []
        mss_damaged = []
        mss_resorted = []
        mss_in_transit_to_cdc = []
        mss_transfer_in_at_cdc = []
        mss_disputed_garment = []
        mss_invoiced_and_delivered = []
        mss_under_clearance_of_invoice_settlement = []
        mss_invoiced_and_pending_delivery = []
        mss_moved_back_to_mss = []
        mss_no_stock = []

        mss_other_pending_transfer_out_from_cdc = []
        mss_other_in_transit_to_mss = []
        mss_other_pending_for_qc_verification = []
        mss_other_transfer_in_at_mss = []
        mss_other_qc_approved = []
        mss_other_qc_rejected = []
        mss_other_work_order_created = []
        mss_other_missing = []
        mss_other_damaged = []
        mss_other_resorted = []
        mss_other_in_transit_to_cdc = []
        mss_other_transfer_in_at_cdc = []
        mss_other_disputed_garment = []
        mss_other_invoiced_and_delivered = []
        mss_other_under_clearance_of_invoice_settlement = []
        mss_other_invoiced_and_pending_delivery = []
        mss_other_moved_back_to_mss = []
        mss_other_no_stock = []



        if with_complaints is not None:

            complaint_tag_details = db.session.query(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).filter(
                AuditTags.TagNo.in_(with_complaints),
                AuditTags.Date == formatted_audit_date,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsMSS == is_mss,
                AuditTags.BranchCode == branch_code,
                AuditTags.ScanId == scan_id,
                AuditTags.isScannedInMss == 0
            ).group_by(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount, AuditTags,
                AuditTags.OrderType
            ).all()

            complaint_tag_details = SerializeSQLAResult(complaint_tag_details).serialize()
            for complaint in complaint_tag_details:
                if complaint['GarmentStatus'] == 'In Transits to CDC':
                    complaint_in_transit_to_cdc.append(complaint)
                elif complaint['GarmentStatus'] in ['Resorted']:
                    complaint_resorted.append(complaint)
                elif complaint['GarmentStatus'] in ['Work Order Created ']:
                    complaint_work_order_created.append(complaint)
                elif complaint['GarmentStatus'] in ['In Transits to mss']:
                    complaint_in_transit_to_mss.append(complaint)
                elif complaint['GarmentStatus'] in ['Pending Transfer Out From CDC']:
                    complaint_pending_transfer_out_from_cdc.append(complaint)
                elif complaint['GarmentStatus'] in ['Invoiced & Delivered']:
                    complaint_invoiced_and_delivered.append(complaint)
                elif complaint['GarmentStatus'] in ['Transfer in at CDC']:
                    complaint_transfer_in_at_cdc.append(complaint)
                elif complaint['GarmentStatus'] in ['Pending for QC Verification']:
                    complaint_pending_for_qc_verification.append(complaint)
                elif complaint['GarmentStatus'] in ['Transfer in at mss']:
                    complaint_transfer_in_at_mss.append(complaint)
                elif complaint['GarmentStatus'] in ['QC Approved']:
                    complaint_qc_approved.append(complaint)
                elif complaint['GarmentStatus'] in ['QC Rejected ']:
                    complaint_qc_rejected.append(complaint)
                elif complaint['GarmentStatus'] in ['Moved Back to Mss']:
                    complaint_moved_back_to_mss.append(complaint)
                elif complaint['GarmentStatus'] in ['Invoiced & Pending Delivery']:
                    complaint_invoiced_and_pending_delivery.append(complaint)
                elif complaint['GarmentStatus'] in ['Under clearance of Invoice settlement']:
                    complaint_under_clearance_of_invoice_settlement.append(complaint)
                elif complaint['GarmentStatus'] in ['Missing']:
                    complaint_missing.append(complaint)
                elif complaint['GarmentStatus'] in ['Damaged']:
                    complaint_damaged.append(complaint)
                elif complaint['GarmentStatus'] in ['Disputed Garment']:
                    complaint_disputed_garment.append(complaint)
                else:
                    complaint_no_stock.append(complaint)
        if without_complaints is not None:

            # without_complaints_tag_details = db.session.query(
            #     AuditTags.TagNo,
            #     AuditTags.EGRN,
            #     AuditTags.ComplaintStatus,
            #     AuditTags.ComplaintDepartment,
            #     AuditTags.ComplaintDate,
            #     AuditTags.EntryType,
            #     AuditTags.ComplaintId,
            #     AuditTags.GarmentStatus,
            #     AuditTags.OrderStatus,
            #     AuditTags.CustomerName,
            #     AuditTags.CustomerId,
            #     AuditTags.GarmentName,
            #     AuditTags.GarmentAmount,
            #     AuditTags.OrderType
            # ).filter(
            #     AuditTags.TagNo.in_(without_complaints),
            #     AuditTags.Date == formatted_audit_date,
            #     AuditTags.ScannedBy == user_id,
            #     AuditTags.IsMSS == is_mss,
            #     AuditTags.BranchCode == branch_code, AuditTags.ScanId == scan_id,
            #     AuditTags.isScannedInMss == 0
            # ).group_by(
            #     AuditTags.TagNo,
            #     AuditTags.EGRN,
            #     AuditTags.ComplaintStatus,
            #     AuditTags.ComplaintDepartment,
            #     AuditTags.ComplaintDate,
            #     AuditTags.EntryType,
            #     AuditTags.ComplaintId,
            #     AuditTags.GarmentStatus,
            #     AuditTags.OrderStatus,
            #     AuditTags.CustomerName,
            #     AuditTags.CustomerId,
            #     AuditTags.GarmentName,
            #     AuditTags.GarmentAmount,
            #     AuditTags.OrderType
            # ).all()


            # without_complaints_tag_details = SerializeSQLAResult(without_complaints_tag_details).serialize()
            
            chunk_size = 1000
            serialized_result = []
            without_complaints_tag_details = []
            for i in range(0, len(without_complaints), chunk_size):
                chunk = without_complaints[i:i + chunk_size]
                query_result  = db.session.query(
                    AuditTags.TagNo,
                    AuditTags.EGRN,
                    AuditTags.ComplaintStatus,
                    AuditTags.ComplaintDepartment,
                    AuditTags.ComplaintDate,
                    AuditTags.EntryType,
                    AuditTags.ComplaintId,
                    AuditTags.GarmentStatus,
                    AuditTags.OrderStatus,
                    AuditTags.CustomerName,
                    AuditTags.CustomerId,
                    AuditTags.GarmentName,
                    AuditTags.GarmentAmount,
                    AuditTags.OrderType
                ).filter(
                    AuditTags.TagNo.in_(chunk),
                    AuditTags.Date == formatted_audit_date,
                    AuditTags.ScannedBy == user_id,
                    AuditTags.IsMSS == is_mss,
                    AuditTags.BranchCode == branch_code, AuditTags.ScanId == scan_id,
                    AuditTags.isScannedInMss == 0
                ).all()


                serialized_result = SerializeSQLAResult(query_result ).serialize()
                without_complaints_tag_details.extend(serialized_result)
                log_data = {
                    'without_complaints': 'without_complaints'

                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            # for without_complaint in without_complaints_tag_details:
            for without_complaint in serialized_result:
                if without_complaint['GarmentStatus'] == 'In Transits to CDC':
                    without_complaint_in_transit_to_cdc.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Resorted']:
                    without_complaint_resorted.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Work Order Created ']:
                    without_complaint_work_order_created.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['In Transits to mss']:
                    without_complaint_in_transit_to_mss.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Pending Transfer Out From CDC']:
                    without_complaint_pending_transfer_out_from_cdc.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Invoiced & Delivered']:
                    without_complaint_invoiced_and_delivered.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Transfer in at CDC']:
                    without_complaint_transfer_in_at_cdc.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Pending for QC Verification']:
                    without_complaint_pending_for_qc_verification.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Transfer in at mss']:
                    without_complaint_transfer_in_at_mss.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['QC Approved']:
                    without_complaint_qc_approved.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['QC Rejected ']:
                    without_complaint_qc_rejected.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Moved Back to Mss']:
                    without_complaint_moved_back_to_mss.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Invoiced & Pending Delivery']:
                    without_complaint_invoiced_and_pending_delivery.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Under clearance of Invoice settlement']:
                    without_complaint_under_clearance_of_invoice_settlement.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Missing']:
                    without_complaint_missing.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Damaged']:
                    without_complaint_damaged.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Disputed Garment']:
                    without_complaint_disputed_garment.append(without_complaint)
                else:
                    without_complaint_no_stock.append(without_complaint)
        if other_stores is not None:
            other_store_tag_details = db.session.query(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.GarmentBranchName,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).filter(
                AuditTags.TagNo.in_(other_stores),
                AuditTags.Date == formatted_audit_date,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsMSS == is_mss,
                AuditTags.BranchCode == branch_code,
                AuditTags.ScanId == scan_id,
                AuditTags.isScannedInMss == 0
            ).group_by(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.GarmentBranchName,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).all()

            other_store_tag_details = SerializeSQLAResult(other_store_tag_details).serialize()

            # Group tag details by branch name
            branch_tags = defaultdict(list)
            for tag_detail in other_store_tag_details:
                branch_tags[tag_detail['GarmentBranchName']].append(tag_detail)

            # Create the final data structure
            other_stores_data = []
            for branch_name, tags in branch_tags.items():
                other_stores_data.append({
                    'status': 'Other stores',
                    'count': len(tags),
                    'details': tags
                })
            if not other_stores_data:
                other_stores_data.append({
                    'status': 'Other stores',
                    'count': 0,
                    'details': []
                })
        log_data = {
            # 'back_to_mss_tags': back_to_mss_tags
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        if back_to_mss_tags_form is not None:

            log_data = {
                'ScanId': scan_id,
                'formatted_audit_date': formatted_audit_date
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            if is_mss:
                log_data = {
                    'ScanId_is_mss:': is_mss

                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))

                query_mss = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date =:formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss=0 AND IsMSS=1   
                                        AND GarmentBranchCode =:branch_code                                    
                                    """)

                result = db.session.execute(query_mss, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,
                }).fetchall()



            else:
                query_mss = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date = :formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss = 1 AND IsMSS=0  
                                        AND GarmentBranchCode =:branch_code 
                                    
                                    """)

                result = db.session.execute(query_mss, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()


            back_to_mss_tags = SerializeSQLAResult(result).serialize()


            for mss in back_to_mss_tags:
                if mss['GarmentStatus'] == 'In Transits to CDC':
                    mss_in_transit_to_cdc.append(mss)
                elif mss['GarmentStatus'] == 'Resorted':
                    mss_resorted.append(mss)
                elif mss['GarmentStatus'] == 'Work Order Created ':
                    mss_work_order_created.append(mss)
                elif mss['GarmentStatus'] == 'In Transits to mss':
                    mss_in_transit_to_mss.append(mss)
                elif mss['GarmentStatus'] == 'Pending Transfer Out From CDC':
                    mss_pending_transfer_out_from_cdc.append(mss)
                elif mss['GarmentStatus'] == 'Invoiced & Delivered':
                    mss_invoiced_and_delivered.append(mss)
                elif mss['GarmentStatus'] == 'Transfer in at CDC':
                    mss_transfer_in_at_cdc.append(mss)
                elif mss['GarmentStatus'] == 'Pending for QC Verification':
                    mss_pending_for_qc_verification.append(mss)
                elif mss['GarmentStatus'] == 'Transfer in at mss':
                    mss_transfer_in_at_mss.append(mss)
                elif mss['GarmentStatus'] == 'QC Approved':
                    mss_qc_approved.append(mss)
                elif mss['GarmentStatus'] == 'QC Rejected ':
                    mss_qc_rejected.append(mss)
                elif mss['GarmentStatus'] == 'Moved Back to Mss':
                    mss_moved_back_to_mss.append(mss)
                elif mss['GarmentStatus'] == 'Invoiced & Pending Delivery':
                    mss_invoiced_and_pending_delivery.append(mss)
                elif mss['GarmentStatus'] == 'Under clearance of Invoice settlement':
                    mss_under_clearance_of_invoice_settlement.append(mss)
                elif mss['GarmentStatus'] == 'Missing':
                    mss_missing.append(mss)
                elif mss['GarmentStatus'] == 'Damaged':
                    mss_damaged.append(mss)
                elif mss['GarmentStatus'] == 'Disputed Garment':
                    mss_disputed_garment.append(mss)
                else:
                    mss_no_stock.append(mss)


        if mss_other_store is not None:

            if is_mss:

                query = text("""
                        SELECT 
                            TagNo,
                            EGRN,
                            ComplaintStatus,
                            ComplaintDepartment,
                            ComplaintDate,
                            EntryType,
                            ComplaintId,
                            GarmentStatus,
                            GarmentBranchName,
                            OrderStatus,
                            CustomerName,
                            CustomerId,
                            GarmentName,
                            GarmentAmount,
                            OrderType
                        FROM 
                            AuditTags
                        WHERE 
                            Date =:formatted_start_date_date
                            AND ScannedBy =:ScannedBy
                            AND BranchCode = :branch_code
                            AND ScanId = :scan_id
                            AND isScannedInMss=0 AND IsMSS=1 
                            AND GarmentBranchCode != :branch_code                                 
                        """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()

            else:
                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date = :formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss = 1 AND IsMSS=0  
                                        AND GarmentBranchCode != :branch_code 
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()

            print(result)
            mss_other_store = SerializeSQLAResult(result).serialize()

            for mss_other in mss_other_store:
                # for mss_other in back_to_mss_tags:
                if mss_other['GarmentStatus'] == 'In Transits to CDC':
                    mss_other_in_transit_to_cdc.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Resorted':
                    mss_other_resorted.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Work Order Created ':
                    other_work_order_created.append(mss_other)
                elif mss_other['GarmentStatus'] == 'In Transits to mss':
                    mss_other_in_transit_to_mss.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Pending Transfer Out From CDC':
                    mss_other_pending_transfer_out_from_cdc.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Invoiced & Delivered':
                    mss_other_invoiced_and_delivered.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Transfer in at CDC':
                    mss_other_transfer_in_at_cdc.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Pending for QC Verification':
                    mss_other_pending_for_qc_verification.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Transfer in at mss':
                    mss_other_transfer_in_at_mss.append(mss_other)
                elif mss_other['GarmentStatus'] == 'QC Approved':
                    mss_other_qc_approved.append(mss_other)
                elif mss_other['GarmentStatus'] == 'QC Rejected ':
                    mss_other_qc_rejected.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Moved Back to Mss':
                    mss_other_moved_back_to_mss.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Invoiced & Pending Delivery':
                    mss_other_invoiced_and_pending_delivery.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Under clearance of Invoice settlement':
                    mss_other_under_clearance_of_invoice_settlement.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Missing':
                    mss_other_missing.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Damaged':
                    mss_other_damaged.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Disputed Garment':
                    mss_other_disputed_garment.append(mss_other)
                else:
                    mss_other_no_stock.append(mss_other)

        if no_stock is not None:
            chunk_size = 1000
            no_stock_tag_details = []
            for i in range(0, len(no_stock), chunk_size):
                chunk = no_stock[i:i + chunk_size]
                # print(chunk)
                query_result = db.session.query(AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus,
                                                AuditTags.ComplaintDepartment, AuditTags.ComplaintDate,
                                                AuditTags.ComplaintId, AuditTags.EntryType,
                                                AuditTags.GarmentStatus, AuditTags.GarmentBranchName,
                                                AuditTags.GarmentName, AuditTags.GarmentAmount,
                                                AuditTags.OrderStatus, AuditTags.OrderType,
                                                AuditTags.CustomerName, AuditTags.CustomerId).filter(
                    AuditTags.TagNo.in_(chunk), AuditTags.Date == formatted_audit_date,
                                                AuditTags.BranchCode == branch_code, AuditTags.IsMSS == 0,
                                                AuditTags.isScannedInMss == 0,
                                                AuditTags.ScanId == scan_id, AuditTags.AuditedBy == user_id,
                                                AuditTags.IsValidTag == 1,
                                                AuditTags.IsNoStock == 1).all()
                serialized_result = SerializeSQLAResult(query_result).serialize()
                # print(serialized_result)
                no_stock_tag_details.extend(serialized_result)

        final_data = generate_final_data('DATA_FOUND')
        final_data['complaint'] = [{'status': 'Pending transfer out from CDC',
                                    'count': len(complaint_pending_transfer_out_from_cdc),
                                    'details': complaint_pending_transfer_out_from_cdc
                                    },
                                   {'status': 'In Transits to MSS',
                                    'count': len(complaint_in_transit_to_mss),
                                    'details': complaint_in_transit_to_mss
                                    },
                                   {'status': 'Transfer in at MSS',
                                    'count': len(complaint_transfer_in_at_mss),
                                    'details': complaint_transfer_in_at_mss
                                    },
                                   {'status': 'Pending for QC Verification',
                                    'count': len(complaint_pending_for_qc_verification),
                                    'details': complaint_pending_for_qc_verification
                                    },
                                   {'status': 'QC Approved',
                                    'count': len(complaint_qc_approved),
                                    'details': complaint_qc_approved
                                    },
                                   {'status': 'QC Rejected',
                                    'count': len(complaint_qc_rejected),
                                    'details': complaint_qc_rejected
                                    },
                                   {'status': 'Work Order Created',
                                    'count': len(complaint_work_order_created),
                                    'details': complaint_work_order_created
                                    },
                                   {'status': 'Resorted',
                                    'count': len(complaint_resorted),
                                    'details': complaint_resorted
                                    },
                                   {'status': 'In Transits to CDC',
                                    'count': len(complaint_in_transit_to_cdc),
                                    'details': complaint_in_transit_to_cdc
                                    },
                                   {'status': 'Transfer in at CDC',
                                    'count': len(complaint_transfer_in_at_cdc),
                                    'details': complaint_transfer_in_at_cdc
                                    },
                                   {'status': 'Invoiced & Delivered',
                                    'count': len(complaint_invoiced_and_delivered),
                                    'details': complaint_invoiced_and_delivered
                                    },
                                   {'status': 'Under Clearance of Invoice settlement',
                                    'count': len(complaint_under_clearance_of_invoice_settlement),
                                    'details': complaint_under_clearance_of_invoice_settlement
                                    },
                                   {'status': 'Missing',
                                    'count': len(complaint_missing),
                                    'details': complaint_missing
                                    },
                                   {'status': 'Damaged',
                                    'count': len(complaint_damaged),
                                    'details': complaint_damaged
                                    },
                                   {'status': 'Disputed Garment',
                                    'count': len(complaint_disputed_garment),
                                    'details': complaint_disputed_garment
                                    },
                                   {'status': 'Invoiced and Pending Delivery',
                                    'count': len(complaint_invoiced_and_pending_delivery),
                                    'details': complaint_invoiced_and_pending_delivery
                                    },
                                   {'status': 'Moved Back to Mss',
                                    'count': len(complaint_moved_back_to_mss),
                                    'details': complaint_moved_back_to_mss
                                    }
                                   ]
        final_data['without_complaint'] = [{'status': 'Pending transfer out from CDC',
                                            'count': len(without_complaint_pending_transfer_out_from_cdc),
                                            'details': without_complaint_pending_transfer_out_from_cdc
                                            },
                                           {'status': 'In Transits to MSS',
                                            'count': len(without_complaint_in_transit_to_mss),
                                            'details': without_complaint_in_transit_to_mss
                                            },
                                           {'status': 'Transfer in at MSS',
                                            'count': len(without_complaint_transfer_in_at_mss),
                                            'details': without_complaint_transfer_in_at_mss
                                            },
                                           {'status': 'Pending for QC Verification',
                                            'count': len(without_complaint_pending_for_qc_verification),
                                            'details': without_complaint_pending_for_qc_verification
                                            },
                                           {'status': 'QC Approved',
                                            'count': len(without_complaint_qc_approved),
                                            'details': without_complaint_qc_approved
                                            },
                                           {'status': 'QC Rejected',
                                            'count': len(without_complaint_qc_rejected),
                                            'details': without_complaint_qc_rejected
                                            },
                                           {'status': 'Work Order Created',
                                            'count': len(without_complaint_work_order_created),
                                            'details': without_complaint_work_order_created
                                            },
                                           {'status': 'Resorted',
                                            'count': len(without_complaint_resorted),
                                            'details': without_complaint_resorted
                                            },
                                           {'status': 'In Transits to CDC',
                                            'count': len(without_complaint_in_transit_to_cdc),
                                            'details': without_complaint_in_transit_to_cdc
                                            },
                                           {'status': 'Transfer in at CDC',
                                            'count': len(without_complaint_transfer_in_at_cdc),
                                            'details': without_complaint_transfer_in_at_cdc
                                            },
                                           {'status': 'Invoiced & Delivered',
                                            'count': len(without_complaint_invoiced_and_delivered),
                                            'details': without_complaint_invoiced_and_delivered
                                            },
                                           {'status': 'Under Clearance of Invoice settlement',
                                            'count': len(without_complaint_under_clearance_of_invoice_settlement),
                                            'details': without_complaint_under_clearance_of_invoice_settlement
                                            },
                                           {'status': 'Missing',
                                            'count': len(without_complaint_missing),
                                            'details': without_complaint_missing
                                            },
                                           {'status': 'Damaged',
                                            'count': len(without_complaint_damaged),
                                            'details': without_complaint_damaged
                                            },
                                           {'status': 'Disputed Garment',
                                            'count': len(without_complaint_disputed_garment),
                                            'details': without_complaint_disputed_garment
                                            },
                                           {'status': 'Invoiced and Pending Delivery',
                                            'count': len(without_complaint_invoiced_and_pending_delivery),
                                            'details': without_complaint_invoiced_and_pending_delivery
                                            },
                                           {'status': 'Moved Back to Mss',
                                            'count': len(without_complaint_moved_back_to_mss),
                                            'details': without_complaint_moved_back_to_mss
                                            }
                                           ]


        final_data['mss_tags'] = [{'status': 'Pending transfer out from CDC',
                                   'count': len(mss_pending_transfer_out_from_cdc),
                                   'details': mss_pending_transfer_out_from_cdc
                                   },
                                  {'status': 'In Transits to MSS',
                                   'count': len(mss_in_transit_to_mss),
                                   'details': mss_in_transit_to_mss
                                   },
                                  {'status': 'Transfer in at MSS',
                                   'count': len(mss_transfer_in_at_mss),
                                   'details': mss_transfer_in_at_mss
                                   },
                                  {'status': 'Pending for QC Verification',
                                   'count': len(mss_pending_for_qc_verification),
                                   'details': mss_pending_for_qc_verification
                                   },
                                  {'status': 'QC Approved',
                                   'count': len(mss_qc_approved),
                                   'details': mss_qc_approved
                                   },
                                  {'status': 'QC Rejected',
                                   'count': len(mss_qc_rejected),
                                   'details': mss_qc_rejected
                                   },
                                  {'status': 'Work Order Created',
                                   'count': len(mss_work_order_created),
                                   'details': mss_work_order_created
                                   },
                                  {'status': 'Resorted',
                                   'count': len(mss_resorted),
                                   'details': mss_resorted
                                   },
                                  {'status': 'In Transits to CDC',
                                   'count': len(mss_in_transit_to_cdc),
                                   'details': mss_in_transit_to_cdc
                                   },
                                  {'status': 'Transfer in at CDC',
                                   'count': len(mss_transfer_in_at_cdc),
                                   'details': mss_transfer_in_at_cdc
                                   },
                                  {'status': 'Invoiced & Delivered',
                                   'count': len(mss_invoiced_and_delivered),
                                   'details': mss_invoiced_and_delivered
                                   },
                                  {'status': 'Under Clearance of Invoice settlement',
                                   'count': len(mss_under_clearance_of_invoice_settlement),
                                   'details': mss_under_clearance_of_invoice_settlement
                                   },
                                  {'status': 'Missing',
                                   'count': len(mss_missing),
                                   'details': mss_missing
                                   },
                                  {'status': 'Damaged',
                                   'count': len(mss_damaged),
                                   'details': mss_damaged
                                   },
                                  {'status': 'Disputed Garment',
                                   'count': len(mss_disputed_garment),
                                   'details': mss_disputed_garment
                                   },
                                  {'status': 'Invoiced and Pending Delivery',
                                   'count': len(mss_invoiced_and_pending_delivery),
                                   'details': mss_invoiced_and_pending_delivery
                                   },
                                  {'status': 'Moved Back to Mss',
                                   'count': len(mss_moved_back_to_mss),
                                   'details': mss_moved_back_to_mss
                                   }
                                  ]
        final_data['mss other store'] = [{'status': 'Pending transfer out from CDC',
                                          'count': len(mss_other_pending_transfer_out_from_cdc),
                                          'details': mss_other_pending_transfer_out_from_cdc
                                          },
                                         {'status': 'In Transits to MSS',
                                          'count': len(mss_other_in_transit_to_mss),
                                          'details': mss_other_in_transit_to_mss
                                          },
                                         {'status': 'Transfer in at MSS',
                                          'count': len(mss_other_transfer_in_at_mss),
                                          'details': mss_other_transfer_in_at_mss
                                          },
                                         {'status': 'Pending for QC Verification',
                                          'count': len(mss_other_pending_for_qc_verification),
                                          'details': mss_other_pending_for_qc_verification
                                          },
                                         {'status': 'QC Approved',
                                          'count': len(mss_other_qc_approved),
                                          'details': mss_other_qc_approved
                                          },
                                         {'status': 'QC Rejected',
                                          'count': len(mss_other_qc_rejected),
                                          'details': mss_other_qc_rejected
                                          },
                                         {'status': 'Work Order Created',
                                          'count': len(mss_other_work_order_created),
                                          'details': mss_other_work_order_created
                                          },
                                         {'status': 'Resorted',
                                          'count': len(mss_other_resorted),
                                          'details': mss_other_resorted
                                          },
                                         {'status': 'In Transits to CDC',
                                          'count': len(mss_other_in_transit_to_cdc),
                                          'details': mss_other_in_transit_to_cdc
                                          },
                                         {'status': 'Transfer in at CDC',
                                          'count': len(mss_other_transfer_in_at_cdc),
                                          'details': mss_other_transfer_in_at_cdc
                                          },
                                         {'status': 'Invoiced & Delivered',
                                          'count': len(mss_other_invoiced_and_delivered),
                                          'details': mss_other_invoiced_and_delivered
                                          },
                                         {'status': 'Under Clearance of Invoice settlement',
                                          'count': len(mss_other_under_clearance_of_invoice_settlement),
                                          'details': mss_other_under_clearance_of_invoice_settlement
                                          },
                                         {'status': 'Missing',
                                          'count': len(mss_other_missing),
                                          'details': mss_other_missing
                                          },
                                         {'status': 'Damaged',
                                          'count': len(mss_other_damaged),
                                          'details': mss_other_damaged
                                          },
                                         {'status': 'Disputed Garment',
                                          'count': len(mss_other_disputed_garment),
                                          'details': mss_other_disputed_garment
                                          },
                                         {'status': 'Invoiced and Pending Delivery',
                                          'count': len(mss_other_invoiced_and_pending_delivery),
                                          'details': mss_other_invoiced_and_pending_delivery
                                          },
                                         {'status': 'Moved Back to Mss',
                                          'count': len(mss_other_moved_back_to_mss),
                                          'details': mss_other_moved_back_to_mss
                                          }
                                         ]





        final_data['other_stores'] = other_stores_data
        final_data['noStockTag'] = [
            {
                'status': 'No Stock',
                'count': len(no_stock_tag_details),
                'count': len(no_stock_tag_details),
                'count': len(no_stock_tag_details),
                'details': no_stock_tag_details
            }
        ]

    else:
        final_data = generate_final_data('DATA_NOT_FOUND')
    log_data = {
        'final_data': final_data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    return final_data

@audit_blueprint.route('scanned_tag_report', methods=['POST'])
@authenticate('audit')
def scanned_tag_report():
    user_id = request.headers.get('user-id')
    scanned_report_form = ScannedTagsForm()
    if scanned_report_form.validate_on_submit():
        audit_date = None if scanned_report_form.audit_date.data == '' else scanned_report_form.audit_date.data
        is_mss = scanned_report_form.is_mss.data
        branch_name = scanned_report_form.branch_name.data
        branch_code = scanned_report_form.branch_code.data
        # in_location = scanned_report_form.in_location.data
        total_tags_scanned = scanned_report_form.total_tags_scanned.data
        is_mss = scanned_report_form.is_mss.data
        valid_tags = scanned_report_form.valid_tags.data
        mss_tags = scanned_report_form.mss_tags.data
        invalid_tags = scanned_report_form.invalid_tags.data
        fab_care_garment_count = scanned_report_form.total_garment_count.data

        auditor_name = db.session.query(DCR_Users.Name, DCR_Users.email).filter(DCR_Users.Id == user_id).one_or_none()
        from sqlalchemy import func

        # Get the latest scan id
        latest_scan_id = db.session.query(func.max(AuditTags.ScanId)).filter(
            AuditTags.AuditedBy == user_id,
            AuditTags.Date == date.today(),
            AuditTags.BranchCode == branch_code
        ).scalar()
        loc = None

        if latest_scan_id is not None:
            # Retrieve the corresponding record using the latest scan id
            in_location = db.session.query(AuditTags).filter(
                AuditTags.AuditedBy == user_id,
                AuditTags.Date == date.today(),
                AuditTags.BranchCode == branch_code,
                AuditTags.ScanId == latest_scan_id
            ).first()

            if in_location is not None:
                location = in_location.InLocation
                loc = 'Not In Location' if location == 0 else 'In Location'
            else:
                pass
        else:
            pass
        current_date = datetime.now().strftime("%d-%m-%Y %H:%M:%S %p")
        if is_mss == 1:
            audit_type = "Back to MSS"
            subject="Back to MSS-Tags saved but not submitted -" + branch_name
            data = 'scanned_tag_mss.html'
            tag_data_report = {"audit_type": audit_type,
                               "audit_date": current_date,
                               "branch_name": branch_name,
                               "in_location": loc,
                               "auditor_name": auditor_name.Name,
                               "is_mss": is_mss,
                               "total_tags_scanned": total_tags_scanned,
                               "valid_tags": valid_tags,
                               "invalid_tags": invalid_tags,

                               }
        else:
            audit_type = "Garment Audit"

            subject = "Tags saved but not submitted -" + branch_name
            data = 'Scanned_tag.html'

            tag_data_report = {"audit_type": audit_type,
                               "audit_date": current_date,
                               "branch_name": branch_name,
                               "in_location": loc,
                               "auditor_name": auditor_name.Name,
                               "is_mss": is_mss,
                               # "total_garment_count": total_garment_count,
                               "total_garment_count": fab_care_garment_count,
                               "total_tags_scanned": total_tags_scanned,
                               "valid_tags": valid_tags,
                               "invalid_tags": invalid_tags,

                               }

        report = ''
        auditor_mail = auditor_name.email
        mails = f'{auditor_mail}'
        #audit_update_mail = audit_mail.audit_mail(data, tag_data_report, subject, report, mails)
        audit_update_mail = audit_mail.audit_mail(data, tag_data_report, subject, report, mails, branch_code)
        if audit_update_mail:
            final_data = generate_final_data('SUCCESS')
        else:
            final_data = generate_final_data('DATA_NOT_FOUND')

    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(scanned_report_form.errors)
    return final_data

@audit_blueprint.route('store_audit_report', methods=['POST'])
@authenticate('audit')
def store_audit_report():
    user_id = request.headers.get('user-id')
    store_audit_report_form = StoreAuditReportForm()
    if store_audit_report_form.validate_on_submit():
        log_data = {
            'store_audit': store_audit_report_form.data
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
        start_date = None if store_audit_report_form.start_date.data == '' else store_audit_report_form.start_date.data
        end_date = None if store_audit_report_form.end_date.data == '' else store_audit_report_form.end_date.data
        branch_code = store_audit_report_form.branch_code.data
        branch_name = store_audit_report_form.branch_name.data
        is_history = store_audit_report_form.is_history.data

        auditor_name = db.session.query(DCR_Users.Name, DCR_Users.email).filter(DCR_Users.Id == user_id).one_or_none()

        if start_date is not None:
            start_date_obj = datetime.strptime(start_date, "%d-%m-%Y")
            formatted_start_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            end_date_obj = datetime.strptime(end_date, "%d-%m-%Y")
            formatted_end_date = (end_date_obj + timedelta(1)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            formatted_start_date = (datetime.today() - timedelta(10)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date = get_current_date()
        dates = db.session.query(StoreAudits.AuditDate.label('AuditDate')).filter(StoreAudits.AuditedBy == user_id,
                                                                                  StoreAudits.BranchCode == branch_code
                                                                                  , StoreAudits.AuditDate.between(
                formatted_start_date, formatted_end_date)).order_by(
            StoreAudits.AuditDate.desc()).group_by(
            StoreAudits.AuditDate).all()
        dates = SerializeSQLAResult(dates).serialize()
        complaint_history_details = []
        for date in dates:
            if date['AuditDate'] is not None:
                start_date_obj = datetime.strptime(date['AuditDate'], "%d-%m-%Y")
                audit_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")

                complaint_history = db.session.query(StoreAudits.Id, StoreAudits.Remarks, StoreAudits.IsYesNo,
                                                     StoreAudits.RecordCreatedDate.label("Date"),
                                                     Audit_Complaints.AuditQuestions,StoreAudits.InLocation
                                                     ).join(
                    Audit_Complaints, Audit_Complaints.Id == StoreAudits.ComplaintId).filter(
                    StoreAudits.BranchCode == branch_code,
                    StoreAudits.AuditedBy == user_id, StoreAudits.AuditDate == audit_date).all()
                complaint_history = SerializeSQLAResult(complaint_history).serialize(full_date_fields=['Date'])
                for complaints in complaint_history:
                    complaints["branch"] = branch_name
                for complaint in complaint_history:
                    photos = db.session.query(AuditPhotos.AuditImage).filter(
                        AuditPhotos.StoreAuditId == complaint['Id']).all()
                    images = SerializeSQLAResult(photos).serialize()
                    complaint['Images'] = images
                complaint_history_details.append(complaint_history)
        current_date = datetime.now().strftime("%d-%m-%Y %H:%M:%S %p")
        complaint_history_details_report = {"audit_type": "Store Audit",
                                            "branch_name": branch_name,
                                            "audit_date": current_date,
                                            "auditor_name": auditor_name.Name,
                                            "complaint_history_details": complaint_history_details,
                                            "start_date": start_date,
                                            "end_date": end_date

                                            }
        data = 'store-audit.html'
        subject = " Store Audit -" + branch_name
        report = ''
        query_mail = f"EXEC {OLD_DB}.dbo.GetBranchEmail @branchcode = '{branch_code}'"
        mails = CallSP(query_mail).execute().fetchall()
        to_mail = mails[0]['ToEmail']
        cc_mail = mails[0]['CCEmail']
        auditor_mail = auditor_name.email
        mails = f'{to_mail};{auditor_mail}'
        for item in complaint_history_details:
            for d in item:
                common.replace_quotes_in_dict(d)
        #audit_update_mail = audit_mail.audit_mail(data, complaint_history_details_report, subject, report, mails,cc_mail)
        #audit_update_mail = audit_mail.audit_mail(data, complaint_history_details_report, subject, report, mails, branch_code, cc_mail)
        audit_update_mail = audit_mail.audit_mail(data, complaint_history_details_report, subject, report, mails, branch_code, cc_mail,is_history)
        if audit_update_mail:
            final_data = generate_final_data('SUCCESS')
        else:
            final_data = generate_final_data('DATA_NOT_FOUND')

    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(store_audit_report_form.errors)
    log_data = {
        
        'final_data': final_data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    return final_data


@audit_blueprint.route('/get_previous_details_mss', methods=["POST"])
def get_previous_details_mss():
    user_id = request.headers.get('user-id')
    get_previous_details_form = GarmentPreviousDetailsForm()

    branch_code = get_previous_details_form.branch_code.data
    start_date = get_previous_details_form.start_date.data.strip() if get_previous_details_form.start_date.data else None
    end_date = get_previous_details_form.end_date.data.strip() if get_previous_details_form.end_date.data else None

    try:
        if start_date:
            start_date_obj = datetime.strptime(start_date, "%d-%m-%Y")
            formatted_start_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            end_date_obj = datetime.strptime(end_date, "%d-%m-%Y")
            # formatted_end_date = (end_date_obj + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date = (end_date_obj).strftime("%Y-%m-%d %H:%M:%S")
        else:
            formatted_start_date = (datetime.today() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return jsonify({
            "status": "error",
            "status_code": "INVALID_DATE_FORMAT",
            "message": "Invalid date format. Please use DD-MM-YYYY."
        }), 400

    mss_query_data = text("""
        SELECT
            AuditTags.TagNo, AuditTags.BranchCode, AuditTags.GarmentBranchCode,
            AuditTags.ComplaintId, AuditTags.Date AS 'ScanDate', DCR_Users.Name AS ScannedBy,
            AuditTags.InLocation, AuditTags.OrderStatus, AuditTags.GarmentStatus,
            MIN(AuditTags.RecordCreatedDate) AS CreatedDate, AuditTags.IsDelivered,
            AuditTags.IsNoStock, AuditTags.ScanId, AuditTags.isScannedInMss,
            AuditTags.IsMSS, AuditTags.IsScanned, AuditTags.GarmentBranchName,
            AuditTags.RecordCreatedDate
        FROM AuditTags
        LEFT JOIN DCR_Users ON DCR_Users.Id = AuditTags.ScannedBy
        WHERE
            AuditTags.ScannedBy = :user_id AND
            AuditTags.Date >= :formatted_start_date AND
            AuditTags.Date <= :formatted_end_date AND
            AuditTags.BranchCode = :branch_code AND
            AuditTags.IsValidTag = 1 AND
            AuditTags.IsMSS = 1
        GROUP BY
            AuditTags.ScanId, AuditTags.TagNo, AuditTags.BranchCode,
            AuditTags.GarmentBranchCode, AuditTags.ComplaintId, AuditTags.Date,
            DCR_Users.Name, AuditTags.InLocation, AuditTags.OrderStatus,
            AuditTags.GarmentStatus, AuditTags.isScannedInMss, AuditTags.IsDelivered,
            AuditTags.IsNoStock, AuditTags.IsMSS, AuditTags.IsScanned,
            AuditTags.GarmentBranchName, AuditTags.RecordCreatedDate
        ORDER BY MIN(AuditTags.RecordCreatedDate) DESC
    """)

    mss_query = db.session.execute(mss_query_data, {
        'user_id': user_id,
        'formatted_start_date': formatted_start_date,
        'formatted_end_date': formatted_end_date,
        'branch_code': branch_code
    }).fetchall()

    mss_query_result = SerializeSQLAResult(mss_query).serialize(full_date_fields=['RecordCreatedDate'])

    grouped_by_date = {}
    for record in mss_query_result:
        # # record_date = datetime.strptime(record['RecordCreatedDate'], "%Y-%m-%d %H:%M").strftime("%d-%m-%Y %H:%M")
        # record_date = datetime.strptime(record['RecordCreatedDate'], "%d-%m-%Y %H:%M").strftime("%d-%m-%Y %H:%M")
        try:
            record_date = datetime.strptime(record['RecordCreatedDate'], "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y")
        except ValueError:
            record_date = datetime.strptime(record['RecordCreatedDate'], "%d-%m-%Y %H:%M:%S %p").strftime("%d-%m-%Y")

        if record_date not in grouped_by_date:
            grouped_by_date[record_date] = {}

        scan_id = record['ScanId']
        if scan_id not in grouped_by_date[record_date]:
            grouped_by_date[record_date][scan_id] = {
                'scan_id': scan_id,
                'scanned_date': record['RecordCreatedDate'],
                'total_tags_scanned': 0,
                'mss_other_store_count': 0,
                'InLocation': record['InLocation'],
                'Mss_Other_Store': [],
                'mss_count': 0,
                'mssTags': [],
                'mss_tags': [],
                'mss_other_store': [],
                'scanned_by': record['ScannedBy'],
                'status_counts': {}  # Add this dictionary to track status counts
            }

        grouped_by_date[record_date][scan_id]['total_tags_scanned'] += 1
        if record['BranchCode'] == record['GarmentBranchCode']:
            grouped_by_date[record_date][scan_id]['mss_count'] += 1
            grouped_by_date[record_date][scan_id]['mss_tags'].append(record['TagNo'])
            status_group = next(
                (sg for sg in grouped_by_date[record_date][scan_id]['mssTags'] if
                 sg['status'] == record['GarmentStatus']),
                None
            )
            if status_group:
                status_group['count'] += 1
                status_group['details'].append(record)
            else:
                grouped_by_date[record_date][scan_id]['mssTags'].append({
                    'status': record['GarmentStatus'],
                    'count': 1,
                    'details': [record]
                })

            # Update the status count
            if record['GarmentStatus'] in grouped_by_date[record_date][scan_id]['status_counts']:
                grouped_by_date[record_date][scan_id]['status_counts'][record['GarmentStatus']] += 1
            else:
                grouped_by_date[record_date][scan_id]['status_counts'][record['GarmentStatus']] = 1
        else:
            grouped_by_date[record_date][scan_id]['mss_other_store_count'] += 1
            grouped_by_date[record_date][scan_id]['mss_other_store'].append(record['TagNo'])
            branch_status_group = next(
                (bsg for bsg in grouped_by_date[record_date][scan_id]['Mss_Other_Store'] if
                 bsg['branch'] == record['GarmentBranchName']),
                None
            )
            if branch_status_group:
                branch_status_group['count'] += 1  # Increment the count for this branch
                status_group = next(
                    (sg for sg in branch_status_group['details'] if sg['status'] == record['GarmentStatus']),
                    None
                )
                if status_group:
                    status_group['count'] += 1
                    status_group['details'].append(record)
                else:
                    branch_status_group['details'].append({
                        'status': record['GarmentStatus'],
                        'count': 1,
                        'details': [record]
                    })
            else:
                grouped_by_date[record_date][scan_id]['Mss_Other_Store'].append({
                    'branch': record['GarmentBranchName'],
                    'count': 1,
                    'details': [{
                        'status': record['GarmentStatus'],
                        'count': 1,
                        'details': [record]
                    }]
                })

    audit_history = []
    for date, scans in grouped_by_date.items():
        for scan in scans.values():
            audit_history.append({
                **scan,
                'status_counts': scan['status_counts']
            })

    final_data = {
        "status": "success",
        "status_code": "DATA_FOUND",
        "message": "Data retrieved successfully",
        "result": {
            "audit_history_details": audit_history
        }
    }

    return final_data

@audit_blueprint.route('get_previous_detailsLive', methods=["POST"])
# @authenticate('audit')
def get_previous_detailsLive():
    user_id = request.headers.get('user-id')
    get_previous_details_form = GarmentPreviousDetailsForm()

    log_data = {
        'start time': 'start time',
        'history-req-body': get_previous_details_form.data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    if get_previous_details_form.validate_on_submit():
        branch_code = get_previous_details_form.branch_code.data
        is_mss = get_previous_details_form.is_mss.data
        start_date = None if get_previous_details_form.start_date.data == '' else get_previous_details_form.start_date.data
        end_date = None if get_previous_details_form.end_date.data == '' else get_previous_details_form.end_date.data
        complaints = []
        without_complaints = []
        other_stores = []
        # back_to_mss_other_store1 = []
        back_to_mss2 = []
        back_to_mss_other2 = []
        # back_mss_tags = []
        normal_tags = []

        if start_date is not None:
            star_date = start_date.strip()
            start_date_obj = datetime.strptime(start_date, "%d-%m-%Y")
            formatted_start_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            end_date_obj = datetime.strptime(end_date, "%d-%m-%Y")
            # formatted_end_date = (end_date_obj + timedelta(1)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date = end_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        else:
            # formatted_start_date = (datetime.today() - timedelta(10)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_start_date = (datetime.today() - timedelta(2)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date = get_current_date()

        audit_history = []
        audit_history_details = []
        no_stock_tags = []

        user = db.session.query(DCR_Users).filter(DCR_Users.Id == user_id, DCR_Users.IsDeleted == 0).one_or_none()
        if user is not None:
            scanned_by = user.Name
        else:
            scanned_by = None

        audit_history_details = f"EXEC Mobile_JFSL.dbo.USP_Garment_History @branchcode = '{branch_code}',@AuditedBy='{user_id}',@Date='{formatted_start_date}',@endDate='{formatted_end_date}'"
        log_data = {
            'audit_history_details qry :': audit_history_details
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        audit_history_details_result = CallSP(audit_history_details).execute().fetchall()
        db.session.commit()

        for result in audit_history_details_result:
            without_complaints = result['WithoutComplaintTags'].split(',') if result.get('WithoutComplaintTags') else []
            complaints = result['WithComplaintTags'].split(',') if result.get('WithComplaintTags') else []
            other_stores = result['OtherStore'].split(',') if result.get('OtherStore') else []
            back_to_mss_other = result['OtherStoreMss'].split(',') if result.get('OtherStoreMss') else []
            back_to_mss = result['Mss'].split(',') if result.get('Mss') else []
            no_stock_tags = result['NoStock'].split(',') if result.get('NoStock') else []
            scan_id = result.get('scanId')
            date_str = result.get('Date')
            date_obj = datetime.strptime(date_str, "%d-%m-%Y")  # Adjusted format to match the date string
            formatted_string = date_obj.strftime("%d-%m-%Y")
            scanned_date = result.get('RecordCreatedDate')
            scanned_date = datetime.strptime(scanned_date, "%Y-%m-%d %I:%M:%S %p")

            # Convert the datetime object to a string in the desired format
            scanned_date = scanned_date.strftime("%d-%m-%Y %I:%M:%S %p")
            # scanned_date = datetime.strptime(scanned_date, "%d-%m-%Y %I:%M:%S %p")
            #  # scanned_date = result.get('RecordCreatedDate')
            scanned_date = str(scanned_date)
            exceptTagCnt = result.get('ExceptTagCnt')
            # log_data = {
            # 'scanned_date qry :': created_date
            # }
            # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            # created_date = datetime.strptime(scanned_date, "%d-%m-%Y %I:%M:%S %p")
             # datetime.strptime(scanned_date, "%d-%m-%Y %I:%M:%S %p")
            # created_date1 = datetime.strptime(scanned_date, "%Y-%m-%d %H:%M:%S.%f")
            # # Format the datetime to the desired string format
            # created_date = created_date1.strftime("%d-%m-%Y %I:%M:%S %p")
            # count_of_tags = len(without_complaints)
            in_location =  result.get('InLocation')
            previous_tag_details = {
                "without_complaints": without_complaints,
                "without_complaints_count": len(without_complaints),
                "complaints": complaints,
                "complaints_count": len(complaints),
                "other_stores": other_stores,
                "mss_tags": back_to_mss,
                "mss_count": len(back_to_mss),
                "mss_other_store": back_to_mss_other,
                "mss_other_store_count": len(back_to_mss_other),
                "other_stores_count": len(other_stores),
                "total_garment_count": len(without_complaints) + len(complaints) + len(no_stock_tags) - exceptTagCnt,
                "total_tags_scanned": len(without_complaints) + len(complaints) + len(back_to_mss) + len(back_to_mss_other)+ len(other_stores),
                                        # len(without_complaints) + len(complaints) + len(other_stores) + len(back_to_mss_other2) + len(back_to_mss2)
                "no_stock_count": len(no_stock_tags),
                "scanned_date_only": formatted_string,
                "scanned_date": scanned_date,
                "scanned_by": scanned_by,
                "InLocation": in_location,
                "scanned_by_id": user_id,
                "scan_id": scan_id,
                "NoStockTag": no_stock_tags}
                # "scanned_by_id": user_id,
                # "NoStockTag": no_stock_tags
            # }
            audit_history.append(previous_tag_details)

        final_data = generate_final_data('DATA_FOUND')

        # audit_history = dict(audit_history)
        final_data['result'] = {"audit_history_details": audit_history, "date_range": 5}

        # log_data = {
        #  'HIST': audit_history
        #         }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(get_previous_details_form.errors)
    return final_data

def db_result_to_dict(result):
    """
    Method for converting sql Queryset to dictionary & change date format of date values
    """
    return [
        {column: value.strftime("%d-%m-%Y") if isinstance(value, date) else value for column, value in row.items()}
        for row in result]

# @audit_blueprint.route('get_previous_details', methods=["POST"])
# # @authenticate('audit')
# def get_previous_details():
#     user_id = request.headers.get('user-id')
#     get_previous_details_form = GarmentPreviousDetailsForm()

#     log_data = {
#         'start time': 'start time',
#         'history-req-body': get_previous_details_form.data
#     }
#     info_logger(f'Route: {request.path}').info(json.dumps(log_data))
#     if get_previous_details_form.validate_on_submit():
#         branch_code = get_previous_details_form.branch_code.data
#         is_mss = get_previous_details_form.is_mss.data
#         start_date = None if get_previous_details_form.start_date.data == '' else get_previous_details_form.start_date.data
#         end_date = None if get_previous_details_form.end_date.data == '' else get_previous_details_form.end_date.data
#         complaints = []
#         without_complaints = []
#         other_stores = []
#         # back_to_mss_other_store1 = []
#         back_to_mss2 = []
#         back_to_mss_other2 = []
#         # back_mss_tags = []
#         normal_tags = []

#         if start_date is not None:
#             star_date = start_date.strip()
#             start_date_obj = datetime.strptime(start_date, "%d-%m-%Y")
#             formatted_start_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
#             end_date_obj = datetime.strptime(end_date, "%d-%m-%Y")
#             # formatted_end_date = (end_date_obj + timedelta(1)).strftime("%Y-%m-%d %H:%M:%S")
#             formatted_end_date = end_date_obj.strftime("%Y-%m-%d %H:%M:%S")
#         else:
#             # formatted_start_date = (datetime.today() - timedelta(10)).strftime("%Y-%m-%d %H:%M:%S")
#             formatted_start_date = (datetime.today() - timedelta(2)).strftime("%Y-%m-%d %H:%M:%S")
#             formatted_end_date = get_current_date()

#         audit_history = []
#         audit_history_details = []
#         no_stock_tags = []

#         user = db.session.query(DCR_Users).filter(DCR_Users.Id == user_id, DCR_Users.IsDeleted == 0).one_or_none()
#         if user is not None:
#             scanned_by = user.Name
#         else:
#             scanned_by = None

#         audit_history_details = f"EXEC Mobile_JFSL.dbo.USP_Garment_History @branchcode = '{branch_code}',@AuditedBy='{user_id}',@Date='{formatted_start_date}',@endDate='{formatted_end_date}'"
#         log_data = {
#             'audit_history_details qry :': audit_history_details
#         }
#         info_logger(f'Route: {request.path}').info(json.dumps(log_data))

#         audit_history_details_result = CallSP(audit_history_details).execute().fetchall()
#         db.session.commit()

#         for result in audit_history_details_result:
#             without_complaints = result['WithoutComplaintTags'].split(',') if result.get('WithoutComplaintTags') else []
#             complaints = result['WithComplaintTags'].split(',') if result.get('WithComplaintTags') else []
#             other_stores = result['OtherStore'].split(',') if result.get('OtherStore') else []
#             back_to_mss_other = result['OtherStoreMss'].split(',') if result.get('OtherStoreMss') else []
#             back_to_mss = result['Mss'].split(',') if result.get('Mss') else []
#             no_stock_tags = result['NoStock'].split(',') if result.get('NoStock') else []
#             scan_id = result.get('scanId')
#             date_str = result.get('Date')
#             date_obj = datetime.strptime(date_str, "%d-%m-%Y")  # Adjusted format to match the date string
#             formatted_string = date_obj.strftime("%d-%m-%Y")
#             scanned_date = result.get('RecordCreatedDate')
#             scanned_date = datetime.strptime(scanned_date, "%Y-%m-%d %I:%M:%S %p")

#             # Convert the datetime object to a string in the desired format
#             scanned_date = scanned_date.strftime("%d-%m-%Y %I:%M:%S %p")
#             # scanned_date = datetime.strptime(scanned_date, "%d-%m-%Y %I:%M:%S %p")
#             #  # scanned_date = result.get('RecordCreatedDate')
#             scanned_date = str(scanned_date)
#             exceptTagCnt = result.get('ExceptTagCnt')
#             no_stock_cnt = result.get('NoStockCnt')
#             stock_at_store_cnt = result.get('StockAtStoreCnt')
#             # log_data = {
#             # 'scanned_date qry :': created_date
#             # }
#             # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
#             # created_date = datetime.strptime(scanned_date, "%d-%m-%Y %I:%M:%S %p")
#              # datetime.strptime(scanned_date, "%d-%m-%Y %I:%M:%S %p")
#             # created_date1 = datetime.strptime(scanned_date, "%Y-%m-%d %H:%M:%S.%f")
#             # # Format the datetime to the desired string format
#             # created_date = created_date1.strftime("%d-%m-%Y %I:%M:%S %p")
#             # count_of_tags = len(without_complaints)
#             in_location =  result.get('InLocation')
#             previous_tag_details = {
#                 "without_complaints": without_complaints,
#                 "without_complaints_count": len(without_complaints),
#                 "complaints": complaints,
#                 "complaints_count": len(complaints),
#                 "other_stores": other_stores,
#                 "mss_tags": back_to_mss,
#                 "mss_count": len(back_to_mss),
#                 "mss_other_store": back_to_mss_other,
#                 "mss_other_store_count": len(back_to_mss_other),
#                 "other_stores_count": len(other_stores),
#                 # "total_garment_count": len(without_complaints) + len(complaints) + len(no_stock_tags) - exceptTagCnt,
#                 "total_garment_count": stock_at_store_cnt,
#                 "total_tags_scanned": len(without_complaints) + len(complaints) + len(back_to_mss) + len(back_to_mss_other)+ len(other_stores),
#                                         # len(without_complaints) + len(complaints) + len(other_stores) + len(back_to_mss_other2) + len(back_to_mss2)
#                 "no_stock_count": no_stock_cnt,
#                 "scanned_date_only": formatted_string,
#                 "scanned_date": scanned_date,
#                 "scanned_by": scanned_by,
#                 "InLocation": in_location,
#                 "scanned_by_id": user_id,
#                 "scan_id": scan_id,
#                 "NoStockTag": no_stock_tags}
#                 # "scanned_by_id": user_id,
#                 # "NoStockTag": no_stock_tags
#             # }
#             audit_history.append(previous_tag_details)

#         final_data = generate_final_data('DATA_FOUND')

#         # audit_history = dict(audit_history)
#         final_data['result'] = {"audit_history_details": audit_history, "date_range": 5}

#         # log_data = {
#         #  'HIST': audit_history
#         #         }
#         # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
#     else:
#         # Form validation error.
#         final_data = generate_final_data('FORM_ERROR')
#         final_data['errors'] = populate_errors(get_previous_details_form.errors)
#     log_data = {
        
#         'final_data': final_data
#     }
#     info_logger(f'Route: {request.path}').info(json.dumps(log_data))
#     return final_data

@audit_blueprint.route('get_previous_details', methods=["POST"])
# @authenticate('audit')
def get_previous_details():
    user_id = request.headers.get('user-id')
    get_previous_details_form = GarmentPreviousDetailsForm()

    log_data = {
        'start time': 'start time',
        'history-req-body': get_previous_details_form.data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    if get_previous_details_form.validate_on_submit():
        branch_code = get_previous_details_form.branch_code.data
        is_mss = get_previous_details_form.is_mss.data
        start_date = None if get_previous_details_form.start_date.data == '' else get_previous_details_form.start_date.data
        end_date = None if get_previous_details_form.end_date.data == '' else get_previous_details_form.end_date.data
        complaints = []
        without_complaints = []
        other_stores = []
        # back_to_mss_other_store1 = []
        back_to_mss2 = []
        back_to_mss_other2 = []
        # back_mss_tags = []
        normal_tags = []

        if start_date is not None:
            star_date = start_date.strip()
            start_date_obj = datetime.strptime(start_date, "%d-%m-%Y")
            formatted_start_date = start_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            end_date_obj = datetime.strptime(end_date, "%d-%m-%Y")
            # formatted_end_date = (end_date_obj + timedelta(1)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date = end_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        else:
            # formatted_start_date = (datetime.today() - timedelta(10)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_start_date = (datetime.today() - timedelta(2)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_end_date = get_current_date()

        audit_history = []
        audit_history_details = []
        no_stock_tags = []

        user = db.session.query(DCR_Users).filter(DCR_Users.Id == user_id, DCR_Users.IsDeleted == 0).one_or_none()
        if user is not None:
            scanned_by = user.Name
        else:
            scanned_by = None

        audit_history_details = f"EXEC Mobile_JFSL.dbo.USP_Garment_History @branchcode = '{branch_code}',@AuditedBy='{user_id}',@Date='{formatted_start_date}',@endDate='{formatted_end_date}'"
        log_data = {
            'audit_history_details qry :': audit_history_details
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        audit_history_details_result = CallSP(audit_history_details).execute().fetchall()
        db.session.commit()

        for result in audit_history_details_result:
            without_complaints = result['WithoutComplaintTags'].split(',') if result.get('WithoutComplaintTags') else []
            complaints = result['WithComplaintTags'].split(',') if result.get('WithComplaintTags') else []
            other_stores = result['OtherStore'].split(',') if result.get('OtherStore') else []
            back_to_mss_other = result['OtherStoreMss'].split(',') if result.get('OtherStoreMss') else []
            back_to_mss = result['Mss'].split(',') if result.get('Mss') else []
            no_stock_tags = result['NoStock'].split(',') if result.get('NoStock') else []
            scan_id = result.get('scanId')
            date_str = result.get('Date')
            date_obj = datetime.strptime(date_str, "%d-%m-%Y")  # Adjusted format to match the date string
            formatted_string = date_obj.strftime("%d-%m-%Y")
            scanned_date = result.get('RecordCreatedDate')
            try:
                # First try the expected format (YYYY-MM-DD)
                scanned_date = datetime.strptime(scanned_date, "%Y-%m-%d %I:%M:%S %p")
            except ValueError:
                try:
                    # If that fails, try DD-MM-YYYY format
                    scanned_date = datetime.strptime(scanned_date, "%d-%m-%Y %I:%M:%S %p")
                except ValueError:
                    # If both fail, use current datetime as fallback
                    scanned_date = datetime.now()

            # Convert the datetime object to a string in the desired format
            scanned_date = scanned_date.strftime("%d-%m-%Y %I:%M:%S %p")
            
            scanned_date = str(scanned_date)
            exceptTagCnt = result.get('ExceptTagCnt')
            no_stock_cnt = result.get('NoStockCnt')
            stock_at_store_cnt = result.get('StockAtStoreCnt')
           
            in_location =  result.get('InLocation')
            if in_location == "1":
                in_location = True
            elif in_location == "0":
                in_location = False
            else:
                in_location = bool(in_location)
            previous_tag_details = {
                "without_complaints": without_complaints,
                "without_complaints_count": len(without_complaints),
                "complaints": complaints,
                "complaints_count": len(complaints),
                "other_stores": other_stores,
                "mss_tags": back_to_mss,
                "mss_count": len(back_to_mss),
                "mss_other_store": back_to_mss_other,
                "mss_other_store_count": len(back_to_mss_other),
                "other_stores_count": len(other_stores),
                # "total_garment_count": len(without_complaints) + len(complaints) + len(no_stock_tags) - exceptTagCnt,
                "total_garment_count": stock_at_store_cnt,
                "total_tags_scanned": len(without_complaints) + len(complaints) + len(back_to_mss) + len(back_to_mss_other)+ len(other_stores),
                                        # len(without_complaints) + len(complaints) + len(other_stores) + len(back_to_mss_other2) + len(back_to_mss2)
                "no_stock_count": no_stock_cnt,
                "scanned_date_only": formatted_string,
                "scanned_date": scanned_date,
                "scanned_by": scanned_by,
                "InLocation": in_location,
                "scanned_by_id": user_id,
                "scan_id": scan_id,
                "NoStockTag": no_stock_tags}
                # "scanned_by_id": user_id,
                # "NoStockTag": no_stock_tags
            # }
            audit_history.append(previous_tag_details)

        final_data = generate_final_data('DATA_FOUND')

        # audit_history = dict(audit_history)
        final_data['result'] = {"audit_history_details": audit_history, "date_range": 5}

        # log_data = {
        #  'HIST': audit_history
        #         }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(get_previous_details_form.errors)
    log_data = {
        
        'final_data': final_data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    return final_data
def db_result_to_dict(result):
    """
    Method for converting sql Queryset to dictionary & change date format of date values
    """
    return [
        {column: value.strftime("%d-%m-%Y") if isinstance(value, date) else value for column, value in row.items()}
        for row in result]



@audit_blueprint.route('get_tag_details', methods=["POST"])
# @authenticate('audit')#after change in other store issue
def get_tag_details():
    user_id = request.headers.get('user-id')
    tag_details_form = TagDetailsForm()
    log_data = {
        'tag_details_ReqBdyNew': tag_details_form.data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    if tag_details_form.validate_on_submit():

        with_complaints = None if tag_details_form.with_complaints.data == '' else tag_details_form.with_complaints.data
        without_complaints = None if tag_details_form.without_complaints.data == '' else tag_details_form.without_complaints.data
        # without_complaints = None
        other_stores = None if tag_details_form.other_stores.data == '' else tag_details_form.other_stores.data
        no_stock = None if tag_details_form.no_stock.data == '' else tag_details_form.no_stock.data
        audit_date = None if tag_details_form.audit_date.data == '' else tag_details_form.audit_date.data
        is_mss = tag_details_form.is_mss.data
        mss_other_store = None if tag_details_form.mss_other_store.data == '' else tag_details_form.mss_other_store.data
        back_to_mss_tags_form = None if tag_details_form.mss_tags.data == '' else tag_details_form.mss_tags.data
        back_to_mss_tags_list = back_to_mss_tags_form
        # latest_scan_id = tag_details_form.latest_scan_id.data
        scan_id = tag_details_form.latest_scan_id.data
        branch_code = tag_details_form.branch_code.data
        audit_date_obj = datetime.strptime(audit_date, "%d-%m-%Y")
        # formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        without_complaint_pending_transfer_out_from_cdc = []
        without_complaint_in_transit_to_mss = []
        without_complaint_pending_for_qc_verification = []
        without_complaint_transfer_in_at_mss = []
        without_complaint_qc_approved = []
        without_complaint_qc_rejected = []
        without_complaint_work_order_created = []
        without_complaint_missing = []
        without_complaint_damaged = []
        without_complaint_resorted = []
        without_complaint_in_transit_to_cdc = []
        without_complaint_transfer_in_at_cdc = []
        without_complaint_disputed_garment = []
        without_complaint_invoiced_and_delivered = []
        without_complaint_under_clearance_of_invoice_settlement = []
        without_complaint_invoiced_and_pending_delivery = []
        without_complaint_moved_back_to_mss = []
        without_complaint_no_stock = []

        complaint_pending_transfer_out_from_cdc = []
        complaint_in_transit_to_mss = []
        complaint_transfer_in_at_mss = []
        complaint_pending_for_qc_verification = []
        complaint_qc_approved = []
        complaint_qc_rejected = []
        complaint_work_order_created = []
        complaint_missing = []
        complaint_damaged = []
        complaint_resorted = []
        complaint_in_transit_to_cdc = []
        complaint_transfer_in_at_cdc = []
        complaint_disputed_garment = []
        complaint_invoiced_and_delivered = []
        complaint_under_clearance_of_invoice_settlement = []
        complaint_invoiced_and_pending_delivery = []
        complaint_moved_back_to_mss = []
        complaint_no_stock = []

        mss_pending_transfer_out_from_cdc = []
        mss_in_transit_to_mss = []
        mss_pending_for_qc_verification = []
        mss_transfer_in_at_mss = []
        mss_qc_approved = []
        mss_qc_rejected = []
        mss_work_order_created = []
        mss_missing = []
        mss_damaged = []
        mss_resorted = []
        mss_in_transit_to_cdc = []
        mss_transfer_in_at_cdc = []
        mss_disputed_garment = []
        mss_invoiced_and_delivered = []
        mss_under_clearance_of_invoice_settlement = []
        mss_invoiced_and_pending_delivery = []
        mss_moved_back_to_mss = []
        mss_no_stock = []

        mss_other_pending_transfer_out_from_cdc = []
        mss_other_in_transit_to_mss = []
        mss_other_pending_for_qc_verification = []
        mss_other_transfer_in_at_mss = []
        mss_other_qc_approved = []
        mss_other_qc_rejected = []
        mss_other_work_order_created = []
        mss_other_missing = []
        mss_other_damaged = []
        mss_other_resorted = []
        mss_other_in_transit_to_cdc = []
        mss_other_transfer_in_at_cdc = []
        mss_other_disputed_garment = []
        mss_other_invoiced_and_delivered = []
        mss_other_under_clearance_of_invoice_settlement = []
        mss_other_invoiced_and_pending_delivery = []
        mss_other_moved_back_to_mss = []
        mss_other_no_stock = []

        if with_complaints is not None:

            complaint_tag_details = db.session.query(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).filter(
                AuditTags.TagNo.in_(with_complaints),
                AuditTags.Date == formatted_audit_date,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsMSS == is_mss,
                AuditTags.BranchCode == branch_code,
                AuditTags.ScanId == scan_id,
                AuditTags.isScannedInMss == 0
            ).group_by(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount, AuditTags,
                AuditTags.OrderType
            ).all()

            complaint_tag_details = SerializeSQLAResult(complaint_tag_details).serialize()
            for complaint in complaint_tag_details:
                if complaint['GarmentStatus'] == 'In Transits to CDC':
                    complaint_in_transit_to_cdc.append(complaint)
                elif complaint['GarmentStatus'] in ['Resorted']:
                    complaint_resorted.append(complaint)
                elif complaint['GarmentStatus'] in ['Work Order Created ']:
                    complaint_work_order_created.append(complaint)
                elif complaint['GarmentStatus'] in ['In Transits to mss']:
                    complaint_in_transit_to_mss.append(complaint)
                elif complaint['GarmentStatus'] in ['Pending Transfer Out From CDC']:
                    complaint_pending_transfer_out_from_cdc.append(complaint)
                elif complaint['GarmentStatus'] in ['Invoiced & Delivered']:
                    complaint_invoiced_and_delivered.append(complaint)
                elif complaint['GarmentStatus'] in ['Transfer in at CDC']:
                    complaint_transfer_in_at_cdc.append(complaint)
                elif complaint['GarmentStatus'] in ['Pending for QC Verification']:
                    complaint_pending_for_qc_verification.append(complaint)
                elif complaint['GarmentStatus'] in ['Transfer in at mss']:
                    complaint_transfer_in_at_mss.append(complaint)
                elif complaint['GarmentStatus'] in ['QC Approved']:
                    complaint_qc_approved.append(complaint)
                elif complaint['GarmentStatus'] in ['QC Rejected ']:
                    complaint_qc_rejected.append(complaint)
                elif complaint['GarmentStatus'] in ['Moved Back to Mss']:
                    complaint_moved_back_to_mss.append(complaint)
                elif complaint['GarmentStatus'] in ['Invoiced & Pending Delivery']:
                    complaint_invoiced_and_pending_delivery.append(complaint)
                elif complaint['GarmentStatus'] in ['Under clearance of Invoice settlement']:
                    complaint_under_clearance_of_invoice_settlement.append(complaint)
                elif complaint['GarmentStatus'] in ['Missing']:
                    complaint_missing.append(complaint)
                elif complaint['GarmentStatus'] in ['Damaged']:
                    complaint_damaged.append(complaint)
                elif complaint['GarmentStatus'] in ['Disputed Garment']:
                    complaint_disputed_garment.append(complaint)
                else:
                    complaint_no_stock.append(complaint)

        log_data = {
            'with_complaints':complaint_tag_details

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        if without_complaints is not None:
            # log_data = {
            #     'without_complaints 1': 'without_complaints 1'

            # }
            # info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            chunk_size = 1000
            without_complaints_tag_details = []
            serialized_result = []
            for i in range(0, len(without_complaints), chunk_size):
                chunk = without_complaints[i:i + chunk_size]
                query_result  = db.session.query(
                    AuditTags.TagNo,
                    AuditTags.EGRN,
                    AuditTags.ComplaintStatus,
                    AuditTags.ComplaintDepartment,
                    AuditTags.ComplaintDate,
                    AuditTags.EntryType,
                    AuditTags.ComplaintId,
                    AuditTags.GarmentStatus,
                    AuditTags.OrderStatus,
                    AuditTags.CustomerName,
                    AuditTags.CustomerId,
                    AuditTags.GarmentName,
                    AuditTags.GarmentAmount,
                    AuditTags.OrderType
                ).filter(
                    AuditTags.TagNo.in_(chunk),
                    AuditTags.Date == formatted_audit_date,
                    AuditTags.ScannedBy == user_id,
                    AuditTags.IsMSS == is_mss,
                    AuditTags.BranchCode == branch_code, AuditTags.ScanId == scan_id,
                    AuditTags.isScannedInMss == 0
                ).all()


                serialized_result = SerializeSQLAResult(query_result ).serialize()
                without_complaints_tag_details.extend(serialized_result)
                log_data = {
                    'without_complaints': serialized_result

                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            for without_complaint in serialized_result:
                if without_complaint['GarmentStatus'] == 'In Transits to CDC':
                    without_complaint_in_transit_to_cdc.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Resorted']:
                    without_complaint_resorted.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Work Order Created ']:
                    without_complaint_work_order_created.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['In Transits to mss']:
                    without_complaint_in_transit_to_mss.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Pending Transfer Out From CDC']:
                    without_complaint_pending_transfer_out_from_cdc.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Invoiced & Delivered']:
                    without_complaint_invoiced_and_delivered.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Transfer in at CDC']:
                    without_complaint_transfer_in_at_cdc.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Pending for QC Verification']:
                    without_complaint_pending_for_qc_verification.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Transfer in at mss']:
                    without_complaint_transfer_in_at_mss.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['QC Approved']:
                    without_complaint_qc_approved.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['QC Rejected ']:
                    without_complaint_qc_rejected.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Moved Back to Mss']:
                    without_complaint_moved_back_to_mss.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Invoiced & Pending Delivery']:
                    without_complaint_invoiced_and_pending_delivery.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Under clearance of Invoice settlement']:
                    without_complaint_under_clearance_of_invoice_settlement.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Missing']:
                    without_complaint_missing.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Damaged']:
                    without_complaint_damaged.append(without_complaint)
                elif without_complaint['GarmentStatus'] in ['Disputed Garment']:
                    without_complaint_disputed_garment.append(without_complaint)
                else:
                    without_complaint_no_stock.append(without_complaint)
        if other_stores is not None:
            other_store_tag_details = db.session.query(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.GarmentBranchName,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).filter(
                AuditTags.TagNo.in_(other_stores),
                AuditTags.Date == formatted_audit_date,
                AuditTags.ScannedBy == user_id,
                AuditTags.IsMSS == is_mss,
                AuditTags.BranchCode == branch_code,
                AuditTags.ScanId == scan_id,
                AuditTags.isScannedInMss == 0
            ).group_by(
                AuditTags.TagNo,
                AuditTags.EGRN,
                AuditTags.ComplaintStatus,
                AuditTags.ComplaintDepartment,
                AuditTags.ComplaintDate,
                AuditTags.EntryType,
                AuditTags.ComplaintId,
                AuditTags.GarmentStatus,
                AuditTags.GarmentBranchName,
                AuditTags.OrderStatus,
                AuditTags.CustomerName,
                AuditTags.CustomerId,
                AuditTags.GarmentName,
                AuditTags.GarmentAmount,
                AuditTags.OrderType
            ).all()

            other_store_tag_details = SerializeSQLAResult(other_store_tag_details).serialize()


            # Group tag details by branch name
            branch_tags = defaultdict(list)
            for tag_detail in other_store_tag_details:
                branch_tags[tag_detail['GarmentBranchName']].append(tag_detail)

            # Create the final data structure
            other_stores_data = []
            for branch_name, tags in branch_tags.items():
                other_stores_data.append({
                    'status': 'Other stores',
                    'count': len(tags),
                    'details': tags
                })
            if not other_stores_data:
                other_stores_data.append({
                    'status': 'Other stores',
                    'count': 0,
                    'details': []
                })

        if back_to_mss_tags_form is not None:

            log_data = {
                'ScanId': scan_id,
                'formatted_audit_date': formatted_audit_date
            }
            info_logger(f'Route: {request.path}').info(json.dumps(log_data))
            if is_mss:
                log_data = {
                    'ScanId_is_mss:': is_mss

                }
                info_logger(f'Route: {request.path}').info(json.dumps(log_data))

                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date =:formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss=0 AND IsMSS=1                                      
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()



            else:
                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date = :formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss = 1 AND IsMSS=0  
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()



            back_to_mss_tags = SerializeSQLAResult(result).serialize()

          

            for mss in back_to_mss_tags:
                if mss['GarmentStatus'] == 'In Transits to CDC':
                    mss_in_transit_to_cdc.append(mss)
                elif mss['GarmentStatus'] == 'Resorted':
                    mss_resorted.append(mss)
                elif mss['GarmentStatus'] == 'Work Order Created':
                    mss_work_order_created.append(mss)
                elif mss['GarmentStatus'] == 'In Transits to mss':
                    mss_in_transit_to_mss.append(mss)
                elif mss['GarmentStatus'] == 'Pending Transfer Out From CDC':
                    mss_pending_transfer_out_from_cdc.append(mss)
                elif mss['GarmentStatus'] == 'Invoiced & Delivered':
                    mss_invoiced_and_delivered.append(mss)
                elif mss['GarmentStatus'] == 'Transfer in at CDC':
                    mss_transfer_in_at_cdc.append(mss)
                elif mss['GarmentStatus'] == 'Pending for QC Verification':
                    mss_pending_for_qc_verification.append(mss)
                elif mss['GarmentStatus'] == 'Transfer in at mss':
                    mss_transfer_in_at_mss.append(mss)
                elif mss['GarmentStatus'] == 'QC Approved':
                    mss_qc_approved.append(mss)
                elif mss['GarmentStatus'] == 'QC Rejected ':
                    mss_qc_rejected.append(mss)
                elif mss['GarmentStatus'] == 'Moved Back to Mss':
                    mss_moved_back_to_mss.append(mss)
                elif mss['GarmentStatus'] == 'Invoiced & Pending Delivery':
                    mss_invoiced_and_pending_delivery.append(mss)
                elif mss['GarmentStatus'] == 'Under clearance of Invoice settlement':
                    mss_under_clearance_of_invoice_settlement.append(mss)
                elif mss['GarmentStatus'] == 'Missing':
                    mss_missing.append(mss)
                elif mss['GarmentStatus'] == 'Damaged':
                    mss_damaged.append(mss)
                elif mss['GarmentStatus'] == 'Disputed Garment':
                    mss_disputed_garment.append(mss)
                else:
                    mss_no_stock.append(mss)

        if mss_other_store is not None:
            

            if is_mss:
               

                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date =:formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss=0 AND IsMSS=1 
                                        AND GarmentBranchCode != :branch_code                                 
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()


            else:
                query = text("""
                                    SELECT 
                                        TagNo,
                                        EGRN,
                                        ComplaintStatus,
                                        ComplaintDepartment,
                                        ComplaintDate,
                                        EntryType,
                                        ComplaintId,
                                        GarmentStatus,
                                        GarmentBranchName,
                                        OrderStatus,
                                        CustomerName,
                                        CustomerId,
                                        GarmentName,
                                        GarmentAmount,
                                        OrderType
                                    FROM 
                                        AuditTags
                                    WHERE 
                                        Date = :formatted_start_date_date
                                        AND ScannedBy =:ScannedBy
                                        AND BranchCode = :branch_code
                                        AND ScanId = :scan_id
                                        AND isScannedInMss = 1 AND IsMSS=0  
                                        AND GarmentBranchCode != :branch_code 
                                    """)

                result = db.session.execute(query, {
                    'formatted_start_date_date': formatted_audit_date,
                    'branch_code': branch_code, 'scan_id': scan_id, "ScannedBy": user_id,

                }).fetchall()
    

            mss_other_store = SerializeSQLAResult(result).serialize()



            for mss_other in mss_other_store:
                # for mss_other in back_to_mss_tags:
                if mss_other['GarmentStatus'] == 'In Transits to CDC':
                    mss_other_in_transit_to_cdc.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Resorted':
                    mss_other_resorted.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Work Order Created':
                    other_work_order_created.append(mss_other)
                elif mss_other['GarmentStatus'] == 'In Transits to mss':
                    mss_other_in_transit_to_mss.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Pending Transfer Out From CDC':
                    mss_other_pending_transfer_out_from_cdc.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Invoiced & Delivered':
                    mss_other_invoiced_and_delivered.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Transfer in at CDC':
                    mss_other_transfer_in_at_cdc.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Pending for QC Verification':
                    mss_other_pending_for_qc_verification.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Transfer in at mss':
                    mss_other_transfer_in_at_mss.append(mss_other)
                elif mss_other['GarmentStatus'] == 'QC Approved':
                    mss_other_qc_approved.append(mss_other)
                elif mss_other['GarmentStatus'] == 'QC Rejected ':
                    mss_other_qc_rejected.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Moved Back to Mss':
                    mss_other_moved_back_to_mss.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Invoiced & Pending Delivery':
                    mss_other_invoiced_and_pending_delivery.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Under clearance of Invoice settlement':
                    mss_other_under_clearance_of_invoice_settlement.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Missing':
                    mss_other_missing.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Damaged':
                    mss_other_damaged.append(mss_other)
                elif mss_other['GarmentStatus'] == 'Disputed Garment':
                    mss_other_disputed_garment.append(mss_other)
                else:
                    mss_other_no_stock.append(mss_other)

        if no_stock is not None:
            chunk_size = 1000
            no_stock_tag_details = []
            for i in range(0, len(no_stock), chunk_size):
                chunk = no_stock[i:i + chunk_size]
                # print(chunk)
                query_result = db.session.query(AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus,
                                                AuditTags.ComplaintDepartment, AuditTags.ComplaintDate,
                                                AuditTags.ComplaintId, AuditTags.EntryType,
                                                AuditTags.GarmentStatus, AuditTags.GarmentBranchName,
                                                AuditTags.GarmentName, AuditTags.GarmentAmount,
                                                AuditTags.OrderStatus, AuditTags.OrderType,
                                                AuditTags.CustomerName, AuditTags.CustomerId).filter(
                    AuditTags.TagNo.in_(chunk), AuditTags.Date == formatted_audit_date,
                                                AuditTags.BranchCode == branch_code, AuditTags.IsMSS == 0,
                                                AuditTags.isScannedInMss == 0,
                                                AuditTags.ScanId == scan_id, AuditTags.AuditedBy == user_id,
                                                AuditTags.IsValidTag == 1,
                                                AuditTags.IsNoStock == 1).all()
                serialized_result = SerializeSQLAResult(query_result).serialize()
                # print(serialized_result)
                no_stock_tag_details.extend(serialized_result)

        final_data = generate_final_data('DATA_FOUND')
        final_data['complaint'] = [{'status': 'Pending transfer out from CDC',
                                    'count': len(complaint_pending_transfer_out_from_cdc),
                                    'details': complaint_pending_transfer_out_from_cdc
                                    },
                                   {'status': 'In Transits to MSS',
                                    'count': len(complaint_in_transit_to_mss),
                                    'details': complaint_in_transit_to_mss
                                    },
                                   {'status': 'Transfer in at MSS',
                                    'count': len(complaint_transfer_in_at_mss),
                                    'details': complaint_transfer_in_at_mss
                                    },
                                   {'status': 'Pending for QC Verification',
                                    'count': len(complaint_pending_for_qc_verification),
                                    'details': complaint_pending_for_qc_verification
                                    },
                                   {'status': 'QC Approved',
                                    'count': len(complaint_qc_approved),
                                    'details': complaint_qc_approved
                                    },
                                   {'status': 'QC Rejected',
                                    'count': len(complaint_qc_rejected),
                                    'details': complaint_qc_rejected
                                    },
                                   {'status': 'Work Order Created',
                                    'count': len(complaint_work_order_created),
                                    'details': complaint_work_order_created
                                    },
                                   {'status': 'Resorted',
                                    'count': len(complaint_resorted),
                                    'details': complaint_resorted
                                    },
                                   {'status': 'In Transits to CDC',
                                    'count': len(complaint_in_transit_to_cdc),
                                    'details': complaint_in_transit_to_cdc
                                    },
                                   {'status': 'Transfer in at CDC',
                                    'count': len(complaint_transfer_in_at_cdc),
                                    'details': complaint_transfer_in_at_cdc
                                    },
                                   {'status': 'Invoiced & Delivered',
                                    'count': len(complaint_invoiced_and_delivered),
                                    'details': complaint_invoiced_and_delivered
                                    },
                                   {'status': 'Under Clearance of Invoice settlement',
                                    'count': len(complaint_under_clearance_of_invoice_settlement),
                                    'details': complaint_under_clearance_of_invoice_settlement
                                    },
                                   {'status': 'Missing',
                                    'count': len(complaint_missing),
                                    'details': complaint_missing
                                    },
                                   {'status': 'Damaged',
                                    'count': len(complaint_damaged),
                                    'details': complaint_damaged
                                    },
                                   {'status': 'Disputed Garment',
                                    'count': len(complaint_disputed_garment),
                                    'details': complaint_disputed_garment
                                    },
                                   {'status': 'Invoiced and Pending Delivery',
                                    'count': len(complaint_invoiced_and_pending_delivery),
                                    'details': complaint_invoiced_and_pending_delivery
                                    },
                                   {'status': 'Moved Back to Mss',
                                    'count': len(complaint_moved_back_to_mss),
                                    'details': complaint_moved_back_to_mss
                                    }
                                   ]
        final_data['without_complaint'] = [{'status': 'Pending transfer out from CDC',
                                            'count': len(without_complaint_pending_transfer_out_from_cdc),
                                            'details': without_complaint_pending_transfer_out_from_cdc
                                            },
                                           {'status': 'In Transits to MSS',
                                            'count': len(without_complaint_in_transit_to_mss),
                                            'details': without_complaint_in_transit_to_mss
                                            },
                                           {'status': 'Transfer in at MSS',
                                            'count': len(without_complaint_transfer_in_at_mss),
                                            'details': without_complaint_transfer_in_at_mss
                                            },
                                           {'status': 'Pending for QC Verification',
                                            'count': len(without_complaint_pending_for_qc_verification),
                                            'details': without_complaint_pending_for_qc_verification
                                            },
                                           {'status': 'QC Approved',
                                            'count': len(without_complaint_qc_approved),
                                            'details': without_complaint_qc_approved
                                            },
                                           {'status': 'QC Rejected',
                                            'count': len(without_complaint_qc_rejected),
                                            'details': without_complaint_qc_rejected
                                            },
                                           {'status': 'Work Order Created',
                                            'count': len(without_complaint_work_order_created),
                                            'details': without_complaint_work_order_created
                                            },
                                           {'status': 'Resorted',
                                            'count': len(without_complaint_resorted),
                                            'details': without_complaint_resorted
                                            },
                                           {'status': 'In Transits to CDC',
                                            'count': len(without_complaint_in_transit_to_cdc),
                                            'details': without_complaint_in_transit_to_cdc
                                            },
                                           {'status': 'Transfer in at CDC',
                                            'count': len(without_complaint_transfer_in_at_cdc),
                                            'details': without_complaint_transfer_in_at_cdc
                                            },
                                           {'status': 'Invoiced & Delivered',
                                            'count': len(without_complaint_invoiced_and_delivered),
                                            'details': without_complaint_invoiced_and_delivered
                                            },
                                           {'status': 'Under Clearance of Invoice settlement',
                                            'count': len(without_complaint_under_clearance_of_invoice_settlement),
                                            'details': without_complaint_under_clearance_of_invoice_settlement
                                            },
                                           {'status': 'Missing',
                                            'count': len(without_complaint_missing),
                                            'details': without_complaint_missing
                                            },
                                           {'status': 'Damaged',
                                            'count': len(without_complaint_damaged),
                                            'details': without_complaint_damaged
                                            },
                                           {'status': 'Disputed Garment',
                                            'count': len(without_complaint_disputed_garment),
                                            'details': without_complaint_disputed_garment
                                            },
                                           {'status': 'Invoiced and Pending Delivery',
                                            'count': len(without_complaint_invoiced_and_pending_delivery),
                                            'details': without_complaint_invoiced_and_pending_delivery
                                            },
                                           {'status': 'Moved Back to Mss',
                                            'count': len(without_complaint_moved_back_to_mss),
                                            'details': without_complaint_moved_back_to_mss
                                            }
                                           ]
        # final_data['other_stores'] = [
        #     {
        #         'status': 'Other stores',
        #         'count': len(store_count),
        #         'details': other_store_tag_details

        #     }]

        final_data['mss_tags'] = [{'status': 'Pending transfer out from CDC',
                                   'count': len(mss_pending_transfer_out_from_cdc),
                                   'details': mss_pending_transfer_out_from_cdc
                                   },
                                  {'status': 'In Transits to MSS',
                                   'count': len(mss_in_transit_to_mss),
                                   'details': mss_in_transit_to_mss
                                   },
                                  {'status': 'Transfer in at MSS',
                                   'count': len(mss_transfer_in_at_mss),
                                   'details': mss_transfer_in_at_mss
                                   },
                                  {'status': 'Pending for QC Verification',
                                   'count': len(mss_pending_for_qc_verification),
                                   'details': mss_pending_for_qc_verification
                                   },
                                  {'status': 'QC Approved',
                                   'count': len(mss_qc_approved),
                                   'details': mss_qc_approved
                                   },
                                  {'status': 'QC Rejected ',
                                   'count': len(mss_qc_rejected),
                                   'details': mss_qc_rejected
                                   },
                                  {'status': 'Work Order Created',
                                   'count': len(mss_work_order_created),
                                   'details': mss_work_order_created
                                   },
                                  {'status': 'Resorted',
                                   'count': len(mss_resorted),
                                   'details': mss_resorted
                                   },
                                  {'status': 'In Transits to CDC',
                                   'count': len(mss_in_transit_to_cdc),
                                   'details': mss_in_transit_to_cdc
                                   },
                                  {'status': 'Transfer in at CDC',
                                   'count': len(mss_transfer_in_at_cdc),
                                   'details': mss_transfer_in_at_cdc
                                   },
                                  {'status': 'Invoiced & Delivered',
                                   'count': len(mss_invoiced_and_delivered),
                                   'details': mss_invoiced_and_delivered
                                   },
                                  {'status': 'Under Clearance of Invoice settlement',
                                   'count': len(mss_under_clearance_of_invoice_settlement),
                                   'details': mss_under_clearance_of_invoice_settlement
                                   },
                                  {'status': 'Missing',
                                   'count': len(mss_missing),
                                   'details': mss_missing
                                   },
                                  {'status': 'Damaged',
                                   'count': len(mss_damaged),
                                   'details': mss_damaged
                                   },
                                  {'status': 'Disputed Garment',
                                   'count': len(mss_disputed_garment),
                                   'details': mss_disputed_garment
                                   },
                                  {'status': 'Invoiced and Pending Delivery',
                                   'count': len(mss_invoiced_and_pending_delivery),
                                   'details': mss_invoiced_and_pending_delivery
                                   },
                                  {'status': 'Moved Back to Mss',
                                   'count': len(mss_moved_back_to_mss),
                                   'details': mss_moved_back_to_mss
                                   }
                                  ]
        final_data['mss other store'] = [{'status': 'Pending transfer out from CDC',
                                          'count': len(mss_other_pending_transfer_out_from_cdc),
                                          'details': mss_other_pending_transfer_out_from_cdc
                                          },
                                         {'status': 'In Transits to MSS',
                                          'count': len(mss_other_in_transit_to_mss),
                                          'details': mss_other_in_transit_to_mss
                                          },
                                         {'status': 'Transfer in at MSS',
                                          'count': len(mss_other_transfer_in_at_mss),
                                          'details': mss_other_transfer_in_at_mss
                                          },
                                         {'status': 'Pending for QC Verification',
                                          'count': len(mss_other_pending_for_qc_verification),
                                          'details': mss_other_pending_for_qc_verification
                                          },
                                         {'status': 'QC Approved',
                                          'count': len(mss_other_qc_approved),
                                          'details': mss_other_qc_approved
                                          },
                                         {'status': 'QC Rejected',
                                          'count': len(mss_other_qc_rejected),
                                          'details': mss_other_qc_rejected
                                          },
                                         {'status': 'Work Order Created',
                                          'count': len(mss_other_work_order_created),
                                          'details': mss_other_work_order_created
                                          },
                                         {'status': 'Resorted',
                                          'count': len(mss_other_resorted),
                                          'details': mss_other_resorted
                                          },
                                         {'status': 'In Transits to CDC',
                                          'count': len(mss_other_in_transit_to_cdc),
                                          'details': mss_other_in_transit_to_cdc
                                          },
                                         {'status': 'Transfer in at CDC',
                                          'count': len(mss_other_transfer_in_at_cdc),
                                          'details': mss_other_transfer_in_at_cdc
                                          },
                                         {'status': 'Invoiced & Delivered',
                                          'count': len(mss_other_invoiced_and_delivered),
                                          'details': mss_other_invoiced_and_delivered
                                          },
                                         {'status': 'Under Clearance of Invoice settlement',
                                          'count': len(mss_other_under_clearance_of_invoice_settlement),
                                          'details': mss_other_under_clearance_of_invoice_settlement
                                          },
                                         {'status': 'Missing',
                                          'count': len(mss_other_missing),
                                          'details': mss_other_missing
                                          },
                                         {'status': 'Damaged',
                                          'count': len(mss_other_damaged),
                                          'details': mss_other_damaged
                                          },
                                         {'status': 'Disputed Garment',
                                          'count': len(mss_other_disputed_garment),
                                          'details': mss_other_disputed_garment
                                          },
                                         {'status': 'Invoiced and Pending Delivery',
                                          'count': len(mss_other_invoiced_and_pending_delivery),
                                          'details': mss_other_invoiced_and_pending_delivery
                                          },
                                         {'status': 'Moved Back to Mss',
                                          'count': len(mss_other_moved_back_to_mss),
                                          'details': mss_other_moved_back_to_mss
                                          }
                                         ]

        final_data['other_stores'] = other_stores_data
        final_data['noStockTag'] = [
            {
                'status': 'No Stock',
                'count': len(no_stock_tag_details),
                'details': no_stock_tag_details
            }
        ]
        
    else:
        final_data = generate_final_data('DATA_NOT_FOUND')
    log_data = {
        'final_data': final_data
    }
    info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    return final_data

@audit_blueprint.route('garment_audit_report_date', methods=["POST"])
#@authenticate('audit') 
def garment_audit_report_date():
    user_id = request.headers.get('user-id')
    garment_audit_report_form = GarmentAuditReportForm()
    # log_data = {
    #     'Req body': garment_audit_report_form.data,
    #     "nostock_dtls_list":"nostock_dtls_list"
    # }
    # info_logger(f'Route: {request.path}').info(json.dumps(log_data))

    if garment_audit_report_form.validate_on_submit():
        audit_date = None if garment_audit_report_form.audit_date.data == '' else garment_audit_report_form.audit_date.data
        # is_mss = garment_audit_report_form.is_mss.data
        is_mss = 0
        branch_code = garment_audit_report_form.branch_code.data
        branch_name = garment_audit_report_form.branch_name.data
        in_location = garment_audit_report_form.in_location.data
        is_history = garment_audit_report_form.is_history.data
        # tags = [] if garment_audit_report_form.tags.data is None else garment_audit_report_form.tags.data
        # auditor_name = garment_audit_report_form.auditor_name.data
        audit_date_obj = datetime.strptime(audit_date, "%d-%m-%Y")
        formatted_audit_date = audit_date_obj.strftime("%Y-%m-%d %H:%M:%S")
        no_stock_tags = garment_audit_report_form.tag_list.data
        noStock_count_data = garment_audit_report_form.noStock_coun.data

        auditor_name = db.session.query(DCR_Users.Name, DCR_Users.email).filter(DCR_Users.Id == user_id).one_or_none()
        total_with_complaint_count = 0
        total_without_complaint_count = 0
        total_other_stores_count = 0
        total_no_stock_count = 0
        stock = 0
        back_to_mss_count = 0
        other_store_mss_count = 0

        garment_audit_data = [{'status': status, 'details': [], 'count': {}} for status in
                              ['In Transits to CDC', 'Resorted', 'Work Order Created ', 'In Transits to mss',
                               'Pending Transfer Out From CDC', 'Invoiced & Delivered', 'Transfer in at CDC',
                               'Pending for QC Verification', 'Transfer in at mss', 'QC Approved', 'QC Rejected ',
                               'Moved Back to Mss', 'Invoiced & Pending Delivery',
                               'Under clearance of Invoice settlement',
                               'Missing', 'Damaged', 'Disputed Garment']]
        with_complaint_count = defaultdict(int)
        without_complaint_count = defaultdict(int)
        other_stores_count = defaultdict(int)
        no_stock_count = defaultdict(int)
        back_to_mss_value = defaultdict(int)
        other_store_mss_value = defaultdict(int)
        # garment_audit_data_details = db.session.query(AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus,
        #                                               AuditTags.ComplaintDepartment, AuditTags.ComplaintDate,
        #                                               AuditTags.GarmentBranchCode, AuditTags.GarmentBranchName,
        #                                               AuditTags.OrderStatus,
        #                                               AuditTags.EntryType, AuditTags.ComplaintId,
        #                                               AuditTags.GarmentStatus,
        #                                               case([(AuditTags.IsNoStock == 1, literal('Yes'))],
        #                                                    else_=literal('No')).label('NoStock'), AuditTags.IsValidTag
        #                                               ).filter(AuditTags.ScannedBy == user_id,
        #                                                        AuditTags.Date == formatted_audit_date,
        #                                                        AuditTags.IsMSS == is_mss,
        #                                                        AuditTags.BranchCode == branch_code).all()

        latest_scan_id = db.session.query(func.max(AuditTags.ScanId)).filter(
            AuditTags.AuditedBy == user_id, AuditTags.IsMSS == 0,
            AuditTags.Date == formatted_audit_date, AuditTags.BranchCode == branch_code
        ).scalar()

        garment_audit_data_details = db.session.query(AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus,
                                                      AuditTags.ComplaintDepartment, AuditTags.ComplaintDate,
                                                      AuditTags.GarmentBranchCode, AuditTags.GarmentBranchName,
                                                      AuditTags.OrderStatus,
                                                      AuditTags.EntryType, AuditTags.ComplaintId,
                                                      AuditTags.GarmentAmount, AuditTags.GarmentName,
                                                      AuditTags.OrderType, AuditTags.CustomerName, AuditTags.CustomerId,
                                                      AuditTags.GarmentStatus, AuditTags.isScannedInMss,
                                                      AuditTags.IsMSS, AuditTags.ScanId, AuditTags.IsNoStock,
                                                      case([(AuditTags.IsNoStock == 1, literal('Yes'))],
                                                           else_=literal('No')).label('NoStock'),
                                                      AuditTags.Execptionflag.label('24hrs & Current day')
                                                      ).filter(AuditTags.ScannedBy == user_id,
                                                               AuditTags.Date == formatted_audit_date,
                                                               AuditTags.IsMSS == is_mss,
                                                               AuditTags.BranchCode == branch_code,
                                                               AuditTags.IsNoStock == 0,
                                                               AuditTags.IsDeleted == 0,
                                                               AuditTags.IsValidTag == 1,

                                                               AuditTags.ScanId == latest_scan_id).all()
        garment_audit_data_details = SerializeSQLAResult(garment_audit_data_details).serialize(
            full_date_fields=['ComplaintDate'])

        log_data = {

            "nostock_dtls_list": "nostock_dtls_list1",
            "ScanId_grmnt_rpt11": latest_scan_id,
            "Branch:": branch_code,
            "Date:": formatted_audit_date,
            "user_id:": user_id

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        for garment in garment_audit_data_details:

            if garment['IsMSS'] == 1 or garment['isScannedInMss'] == 1 and garment['GarmentBranchCode'] != branch_code:
                garment["category"] = 'Back to Mss Other Store'
            elif garment['IsMSS'] == 1 or garment['isScannedInMss'] == 1:
                garment["category"] = 'Back to Mss'

            elif garment['GarmentBranchCode'] != branch_code:
                garment["category"] = 'Others Stores'
            elif garment['ComplaintStatus'] == None:
                garment["category"] = 'Without Complaint'
            elif garment['ComplaintStatus'] != None:
                garment["category"] = 'With Complaint'
            else:
                pass

        extra_query = db.session.query(
            AuditTags.TagNo, AuditTags.EGRN, AuditTags.ComplaintStatus,
            AuditTags.ComplaintDepartment, AuditTags.ComplaintDate,
            AuditTags.GarmentBranchCode, AuditTags.GarmentBranchName,
            AuditTags.OrderStatus, AuditTags.EntryType, AuditTags.ComplaintId, AuditTags.ScanId, AuditTags.IsNoStock,
            AuditTags.GarmentAmount, AuditTags.GarmentName, AuditTags.OrderType, AuditTags.CustomerName,
            AuditTags.CustomerId,
            AuditTags.GarmentStatus, AuditTags.Execptionflag.label('24hrs & Current day')
        ).filter(
            AuditTags.Date == formatted_audit_date, AuditTags.Execptionflag == 0, AuditTags.IsDeleted == 0,
            AuditTags.IsValidTag == 1,
            AuditTags.IsMSS == 0,
            AuditTags.isScannedInMss == 0,
            # AuditTags.IsScanned == 1,
            AuditTags.BranchCode == branch_code,
            AuditTags.IsNoStock == 1, AuditTags.ScanId == latest_scan_id, AuditTags.AuditedBy == user_id,
            AuditTags.GarmentStatus.in_(
                ['In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC', 'Invoiced & Delivered'])
        ).all()
        # print(extra_query)

        # Serialize the additional data
        extra_data_details = SerializeSQLAResult(extra_query).serialize(full_date_fields=['ComplaintDate'])
        for nostock in extra_data_details:
            nostock["category"] = 'No stock'

        garment_dtls = [{key: val for key, val in d.items() if key not in ['IsValidTag']} for d in
                        garment_audit_data_details]
        # Combine the two data sets
        combined_data_details = garment_dtls + extra_data_details

        # combined_data_details = garment_audit_data_details + extra_data_details
        # print(garment_dtls)
        # print(extra_data_details)
        for datadtls in combined_data_details:
            # if datadtls['ScanId'] > 1 and datadtls['IsNoStock'] == 0 and (
            #         datadtls['IsMSS'] == 1 or datadtls['isScannedInMss'] == 1):
            #     datadtls['scan status'] = 'Already scanned'
            if datadtls['24hrs & Current day'] == 1 and datadtls['GarmentStatus'] == 'In Transits to CDC':
                datadtls['24hrs & Current day'] = 'Transferred-in within 24hrs'
            elif datadtls['24hrs & Current day'] == 1 and datadtls['GarmentStatus'] == 'Pending Transfer Out From CDC':
                datadtls['24hrs & Current day'] = 'Tag generated Today'
            else:
                datadtls['24hrs & Current day'] = ' '

        # garment_audit_data_details = [{key: val for key, val in d.items() if key not in ['IsValidTag','IsMSS','isScannedInMss']} for d in
        #                 garment_audit_data_details]
        excluded_data_details = [{key: val for key, val in d.items() if
                                  key not in ['ScanId', 'IsNoStock', 'NoStock', 'IsMSS', 'isScannedInMss']}
                                 for d in combined_data_details]

        log_data = {

            "excluded_data_details": excluded_data_details,
            'combined_data_details': combined_data_details

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        if is_mss:
            audit_type = "Back to MSS"
        else:
            audit_type = "Garment Audit"

        # report = GenerateReport(combined_data_details, audit_type).generate().get()
        report = GenerateReport(excluded_data_details, audit_type).generate().get()

        # nostock_dtls = db.session.query(func.count(AuditTags.GarmentStatus).label('Count'),
        #                                 AuditTags.GarmentStatus
        #                                 ).filter(AuditTags.Date == formatted_audit_date,
        #                                          AuditTags.IsMSS == is_mss,
        #                                          AuditTags.BranchCode == branch_code,
        #                                          AuditTags.IsNoStock == 1).group_by(AuditTags.GarmentStatus).all()

        # nostock_dtls = db.session.query(
        #     func.count(AuditTags.GarmentStatus).label('Count'),
        #     AuditTags.GarmentStatus
        # ).filter(
        #     # AuditTags.Date == formatted_audit_date,
        #     AuditTags.Date == date.today(),
        #     AuditTags.IsMSS == is_mss, AuditTags.Execptionflag == 1, AuditTags.IsDeleted == 0,
        #     AuditTags.isScannedInMss == 0,
        #     AuditTags.IsValidTag == 1,
        #     AuditTags.BranchCode == branch_code, AuditTags.GarmentBranchCode == branch_code,
        #     AuditTags.IsNoStock == 1, AuditTags.AuditedBy == user_id, AuditTags.ScanId == latest_scan_id,
        #     AuditTags.GarmentStatus.in_(
        #         ['In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC', 'Invoiced & Delivered'])
        # ).group_by(AuditTags.GarmentStatus).all()

        nostock_dtls = db.session.query(AuditTags.TagNo, AuditTags.RecordLastUpdatedDate.label('ScannedDate'),
                                        AuditTags.InLocation, AuditTags.GarmentStatus
                                        ).filter(AuditTags.BranchCode == branch_code,
                                                 AuditTags.IsNoStock == 1,
                                                 AuditTags.IsMSS == is_mss,
                                                 AuditTags.IsValidTag == 1, AuditTags.IsDeleted == 0,
                                                 AuditTags.Date == date.today(),
                                                 AuditTags.ScanId == latest_scan_id,
                                                 AuditTags.Execptionflag == 0,
                                                 AuditTags.isScannedInMss == 0,
                                                 AuditTags.AuditedBy == user_id, AuditTags.GarmentStatus.in_(
                ['In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC',
                 'Invoiced & Delivered'])).all()

        nostock_dtls_list = SerializeSQLAResult(nostock_dtls).serialize()

        log_data = {
            'nostock_dtls_list': "nostock_dtls_list",

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        for garment in garment_audit_data_details:
            # print(garment)
            found = False
            for garment_audit in garment_audit_data:
                if garment_audit['status'] == garment['GarmentStatus']:
                    if garment['GarmentBranchCode'] == branch_code and garment['GarmentStatus'] in [
                        'In Transits to CDC', 'Pending Transfer Out From CDC', 'Transfer in at CDC',
                        'Invoiced & Delivered'] and garment['24hrs & Current day'] == 0:
                        stock = stock + 1
                    else:
                        pass
                    if garment['GarmentBranchCode'] != branch_code and (
                            garment['IsMSS'] == 1 or garment['isScannedInMss'] == 1):
                        other_store_mss_value[garment_audit['status']] += 1
                        other_store_mss_count = other_store_mss_count + 1

                    elif garment['IsMSS'] == 1 or garment['isScannedInMss'] == 1:
                        garment['Back to mss'] = True
                        back_to_mss_count = back_to_mss_count + 1
                        back_to_mss_value[garment_audit['status']] += 1

                    elif garment['GarmentBranchCode'] != branch_code:
                        # print(branch_code)
                        garment['other_stores'] = True
                        total_other_stores_count = total_other_stores_count + 1
                        other_stores_count[garment_audit['status']] += 1
                    elif garment['ComplaintStatus'] is None:
                        garment['without_complaint'] = True
                        total_without_complaint_count = total_without_complaint_count + 1
                        # print(total_without_complaint_count)
                        without_complaint_count[garment_audit['status']] += 1

                    elif garment['ComplaintStatus'] != None and garment['NoStock'] in (0, 'No'):
                        garment['with_complaint'] = True
                        total_with_complaint_count = total_with_complaint_count + 1
                        with_complaint_count[garment_audit['status']] += 1

                    else:
                        pass
                        # garment['no_stock'] = True
                        # #print(garment['no_stock'])
                        # total_no_stock_count = total_no_stock_count + 1
                        # no_stock_count[garment_audit['status']] += 1

                    garment['no_stock'] = True

                    # total_no_stock_count = db.session.query(AuditGarmentCount).filter(
                    #     AuditGarmentCount.Date == formatted_audit_date,
                    #     AuditGarmentCount.BranchCode == branch_code, AuditGarmentCount.AuditedBy == user_id,
                    #     AuditGarmentCount.ScanId == latest_scan_id).one_or_none()

                    total_no_stock_count = db.session.query(func.count(AuditTags.TagNo)).filter(
                        and_(
                            AuditTags.Date == formatted_audit_date,
                            AuditTags.IsNoStock == 1,
                            AuditTags.IsMSS == is_mss,
                            AuditTags.Execptionflag == 0,
                            AuditTags.BranchCode == branch_code,
                            AuditTags.IsValidTag == 1,
                            AuditTags.AuditedBy == user_id, AuditTags.IsDeleted == 0, AuditTags.isScannedInMss == 0,
                            AuditTags.ScanId == latest_scan_id, AuditTags.GarmentBranchCode == branch_code,
                            AuditTags.GarmentStatus.in_([
                                'In Transits to CDC',
                                'Pending Transfer Out From CDC',
                                'Transfer in at CDC',
                                'Invoiced & Delivered'
                            ])
                        )
                    ).scalar()

                    if total_no_stock_count:
                        count = total_no_stock_count
                        total_no_stock_count = count - stock
                        # no_stock_count[garment_audit['status']] = total_no_stock_count
                        no_stock_count[garment_audit['status']] = count

                    else:
                        pass
                        # print("No stock count found for the specified date and branch.")
                    garment_audit['details'].append(garment)
                    found = True
                    break

            if not found:
                garment_audit_data[-1]['details'].append(garment)

            for garment_audit in garment_audit_data:
                status = garment_audit['status']
                garment_audit['count'] = {
                    'with_complaint': with_complaint_count[status],
                    'without_complaint': without_complaint_count[status],
                    'other_stores': other_stores_count[status],
                    'no_stock': 0,
                    'mss_count': back_to_mss_value[status],
                    'other_store_mss_value': other_store_mss_value[status]
                    # 'no_stock': no_stock_count[status]

                }
        if is_mss:
            audit_type = "Back to MSS"
        else:
            audit_type = "Garment Audit"
        #current_date = datetime.now().strftime("%d-%m-%Y %H:%M:%S %p")
        current_date = "11-11-2025 15:59:13 PM"

        status_items = []

        # log_data = {
        #     'status_items': status_items,
        #     'garment_audit_data': garment_audit_data
        #
        # }
        # info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        for item in garment_audit_data:
            status = item.get('status')

            if status and status not in ['In Transits to CDC', 'Invoiced & Delivered', 'Pending Transfer Out From CDC',
                                         'Transfer in at CDC']:
                count_dict = item.get('count', {})

                # if isinstance(count_dict, dict) and any(value != 0 for value in count_dict.values()):
                if any(value != 0 for value in count_dict.values()):
                    status_items.append(item)
            else:
                status_items.append(item)
        log_data = {
            'status_items': status_items,
            'garment_audit_data': garment_audit_data

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        # for item in status_items:
        #     print(item)
        # print(status_items)
        if status_items is not None:
            status_data = status_items
            # print(status_data)
        else:
            pass

        # for item in garment_audit_data:
        #     status = item.get('status')

        #     if status and status not in ['In Transits to CDC', 'Invoiced & Delivered', 'Pending Transfer Out From CDC',
        #                                  'Transfer in at CDC']:
        #         count_dict = item.get('count', {})

        #         status_items.append(item)
        #         if any(value != 0 for value in count_dict.values()):
        #             status_items.append(item)
        # else:
        #     pass
        # else:
        #     status_items.append(item)
        # for value in count_dict.values():
        #     status_items.append(item)

        # else:
        #     status_items.append(item)

        # if status_items is not None:
        #     status_data = status_items
        #     # print(status_data)
        # else:
        #     pass

        BranchName = db.session.query(DCR_User_Branches.BranchName).filter(
            DCR_User_Branches.BranchCode == branch_code).first()
        # BranchName = BranchName[0]
        # BranchName = str(BranchName)
        BranchName = str(BranchName[0]).replace("'", "")

        no_stock_tags_count = len(no_stock_tags)
        garment_audit_data_report = {"audit_type": audit_type,
                                     "audit_date": current_date,
                                     "branch_name": branch_name,
                                     "in_location": in_location,
                                     "auditor_name": auditor_name.Name,
                                     "garment_audit_data": status_data,
                                     "total_other_stores_count": total_other_stores_count,
                                     "total_with_complaint_count": total_with_complaint_count,
                                     "total_without_complaint_count": total_without_complaint_count,
                                     # "total_no_stock_count": total_no_stock_count,
                                     "total_no_stock_count1": noStock_count_data,
                                     "back_to_mss_count": back_to_mss_count,
                                     "other_store_mss_count": other_store_mss_count
                                     }
        data = 'summary-screen.html'
        if is_mss:
            subject = "Detailed garment audit report - " + BranchName
            # subject = "Detailed garment audit report - " + branch_name
        else:
            subject = "Detailed garment audit report - " + BranchName
        query_mail = f"EXEC {OLD_DB}.dbo.GetBranchEmail @branchcode = '{branch_code}'"
        mails = CallSP(query_mail).execute().fetchall()
        to_mail = mails[0]['ToEmail']

        cc_mail = mails[0]['CCEmail']
        auditor_mail = auditor_name.email
        mails = f'{to_mail};{auditor_mail}'
        # mails = f'{to_mail};{auditor_mail}'
        # for obj in garment_audit_data_report['garment_audit_data']:
        #     status = obj['status']
        #     index = next((index for (index, d) in enumerate(nostock_dtls_list) if d['GarmentStatus'] == status), None)
        #     # if index is not None:
        #     #     if isinstance(obj['count'], dict):
        #     #         obj['count']['no_stock'] += nostock_dtls_list[index]['Count']
        #     #     else:
        #     #         obj['count'] = nostock_dtls_list[index]['Count']
        #     if index is not None:
        #         if isinstance(obj['count'], dict):
        #             count_value = nostock_dtls_list[index].get('Count', 0)  # Default to 0 if 'Count' key is missing
        #             obj['count']['no_stock'] += count_value
        #         else:
        #             obj['count'] = nostock_dtls_list[index].get('Count', 0)  # Default to 0 if 'Count' key is missing

        status_counts = defaultdict(int)
        for item in nostock_dtls_list:
            status_counts[item['GarmentStatus']] += 1

        # Step 2: Update garment_audit_data_report with aggregated counts
        for obj in garment_audit_data_report['garment_audit_data']:
            status = obj['status']
            count_value = status_counts.get(status, 0)  # Get the count for the status, default to 0 if not found

            if isinstance(obj['count'], dict):
                obj['count'].setdefault('no_stock', 0)
                obj['count']['no_stock'] += count_value
            else:
                obj['count'] = count_value

        # for obj in garment_audit_data_report['garment_audit_data']:
        #     status = obj['status']
        #     index = next((index for (index, d) in enumerate(nostock_dtls_list) if d['GarmentStatus'] == status), None)
        #     if index is not None:
        #         count = nostock_dtls_list[index].get('Count', 0)
        #         if isinstance(obj['count'], dict):
        #             obj['count']['no_stock'] += count
        #         else:
        #             obj['count'] = count

        log_data = {
            'audit_mail': garment_audit_data_report,
            'Auditor_mail': mails,
            "query_mail": query_mail,
            "cc_mail": cc_mail
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        #audit_update_mail = audit_mail.audit_mail(data, garment_audit_data_report, subject, report, mails, cc_mail)
        #audit_update_mail = audit_mail.audit_mail(data, garment_audit_data_report, subject, report, mails, branch_code, cc_mail)
        #audit_update_mail = None
        audit_update_mail = audit_mail.audit_mail(data, garment_audit_data_report, subject, report, mails, branch_code, cc_mail,is_history)
        if audit_update_mail:
            final_data = generate_final_data('SUCCESS')
            final_data['result'] = garment_audit_data_report
        else:
            final_data = generate_final_data('DATA_NOT_FOUND')

    else:
        # Form validation error.
        final_data = generate_final_data('FORM_ERROR')
        final_data['errors'] = populate_errors(garment_audit_report_form.errors)
    return final_data
