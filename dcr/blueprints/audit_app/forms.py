from wtforms import StringField, IntegerField, Field, FloatField, BooleanField, FileField
from wtforms.validators import InputRequired, Length, Optional
from flask_wtf import FlaskForm
from .validators import validate_complaint_list, validate_tag_list, \
    validate_audit_updates_list, validate_audit_summary_list, validate_audit_detailed_list,validate_garment_audit_updates_list


# class GarmentAuditReportFormMss1(FlaskForm):
#     class Meta:
#         csrf = False

#         garment_audit_updates_list = ListField('garment_audit_updates_list',
#                                                validators=[InputRequired(), validate_garment_audit_updates_list])


class ListField(Field):
    """
    A custom WTF field for accepting array of data.
    """

    def process_formdata(self, valuelist):
        self.data = valuelist

class GarmentAuditDetailsForm(FlaskForm):
    class Meta:
        csrf = False

    tag_list = ListField('tag_list', validators=[Optional()])
    branch_code = StringField('branch_code', validators=[InputRequired()])
    audit_date = StringField('audit_date', validators=[Optional()])
    is_mss = BooleanField('is_mss', validators=[Optional()], false_values=(False, 'false', 0, '0'))

class GarmentAuditReportFormMss(FlaskForm):
    class Meta:
        csrf = False

    audit_date = StringField('audit_date', validators=[Optional()])
    is_mss = BooleanField('is_mss', validators=[Optional()], false_values=(False, 'false', 0, '0'))
    branch_code = StringField('branch_code', validators=[InputRequired()])
    branch_name = StringField('branch_name', validators=[InputRequired()])
    in_location = StringField('in_location', validators=[InputRequired()])
    mss_list = ListField('tag_list', validators=[Optional()])
    other_store_list = ListField('tag_list', validators=[Optional()])
    is_history = BooleanField('is_history', validators=[Optional()], false_values=(False, 'false', 0, '0'))

class GetComplaintsForm(FlaskForm):
    class Meta:
        csrf = False

    branch_code = StringField('branch_code', validators=[InputRequired()])


class AuditComplaintsForm(FlaskForm):
    class Meta:
        csrf = False

    complaint_list = ListField('complaint_list', validators=[InputRequired(), validate_complaint_list])


class GarmentAuditForm(FlaskForm):
    class Meta:
        csrf = False

    is_mss = BooleanField('is_mss', validators=[Optional()], false_values=(False, 'false', 0, '0'))
    tag_list = ListField('tag_list', validators=[InputRequired()])
    branch_code = StringField('branch_code', validators=[InputRequired()])
    lat = FloatField('lat', validators=[Optional()])
    long = FloatField('long', validators=[Optional()])
    # entry_type = StringField('entry_type', validators=[Optional()])
    scan_id = IntegerField('scan_id', validators=[Optional()], default=None)
class GarmentAuditDetailsForm(FlaskForm):
    class Meta:
        csrf = False

    tag_list = ListField('tag_list', validators=[Optional()])
    branch_code = StringField('branch_code', validators=[InputRequired()])
    audit_date = StringField('audit_date', validators=[Optional()])
    is_mss = BooleanField('is_mss', validators=[Optional()], false_values=(False, 'false', 0, '0'))


class TagDetailsForm(FlaskForm):
    class Meta:
        csrf = False

    with_complaints = ListField('with_complaints', validators=[Optional()])
    without_complaints = ListField('without_complaints', validators=[Optional()])
    other_stores = ListField('other_stores', validators=[Optional()])
    audit_date = StringField('audit_date', validators=[Optional()])
    no_stock = ListField('no_stock', validators=[Optional()])
    is_mss = BooleanField('is_mss', validators=[Optional()], false_values=(False, 'false', 0, '0'))
    branch_code = StringField('branch_code', validators=[InputRequired()])
    latest_scan_id = IntegerField('latest_scan_id ', validators=[Optional()])
    mss_tags=ListField('mss_tags', validators=[Optional()])
    mss_other_store= ListField('mss_other_store', validators=[Optional()])


class GarmentPreviousDetailsForm(FlaskForm):
    class Meta:
        csrf = False

    branch_code = StringField('branch_code', validators=[InputRequired()])
    is_mss = BooleanField('is_mss', validators=[Optional()], false_values=(False, 'false', 0, '0'))
    start_date = StringField('start_date', validators=[Optional()])
    end_date = StringField('end_date', validators=[Optional()])


class ComplaintHistoryForm(FlaskForm):
    class Meta:
        csrf = False

    branch_code = StringField('branch_code', validators=[InputRequired()])
    complaint_date = StringField('audit_date', validators=[Optional()])
    start_date = StringField('start_date', validators=[Optional()])
    end_date = StringField('end_date', validators=[Optional()])


class AuditUpdatesForm(FlaskForm):
    class Meta:
        csrf = False

    audit_updates_list = ListField('audit_updates_list', validators=[InputRequired(), validate_audit_updates_list])


class AuditSummaryReportForm(FlaskForm):
    class Meta:
        csrf = False

    audit_summary_list = ListField('audit_summary_list', validators=[InputRequired(), validate_audit_summary_list])


class AuditDetailedReportForm(FlaskForm):
    class Meta:
        csrf = False

    audit_detailed_list = ListField('audit_detailed_list', validators=[InputRequired(), validate_audit_summary_list])


class GarmentAuditReportForm(FlaskForm):
    class Meta:
        csrf = False

    audit_date = StringField('audit_date', validators=[Optional()])
    is_mss = BooleanField('is_mss', validators=[Optional()], false_values=(False, 'false', 0, '0'))
    branch_code = StringField('branch_code', validators=[InputRequired()])
    branch_name = StringField('branch_name', validators=[InputRequired()])
    in_location = StringField('in_location', validators=[InputRequired()])
    tag = ListField('tag', validators=[Optional()])
    tag_list = ListField('tag_list', validators=[Optional()])
    noStock_coun = IntegerField("noStock_coun", validators=[Optional()])
    is_history = BooleanField('is_history', validators=[Optional()], false_values=(False, 'false', 0, '0'))


class StoreAuditReportForm(FlaskForm):
    class Meta:
        csrf = False
    branch_code = StringField('branch_code', validators=[InputRequired()])
    start_date = StringField('start_date', validators=[Optional()])
    end_date = StringField('end_date', validators=[Optional()])
    branch_name = StringField('branch_name', validators=[InputRequired()])
    is_history = BooleanField('is_history', validators=[Optional()], false_values=(False, 'false', 0, '0'))
    

class StockDetailForm(FlaskForm):
    class Meta:
        csrf = False

    is_mss = BooleanField('is_mss', validators=[Optional()], false_values=(False, 'false', 0, '0'))
    branch_code = StringField('branch_code', validators=[InputRequired()])
    

class ScannedTagsForm(FlaskForm):
    class Meta:
        csrf = False

    audit_date = StringField('audit_date', validators=[Optional()])
    is_mss = BooleanField('is_mss', validators=[Optional()], false_values=(False, 'false', 0, '0'))
    branch_code = StringField('branch_code', validators=[InputRequired()])
    branch_name = StringField('branch_name', validators=[InputRequired()])
    in_location = StringField('in_location', validators=[Optional()])
    audit_type = StringField('audit_type', validators=[InputRequired()])
    total_garment_count = IntegerField('total_garment_count', validators=[Optional()])
    total_tags_scanned = IntegerField('total_tags_scanned', validators=[InputRequired()])
    auditor_name = StringField('auditor_name', validators=[Optional()])
    valid_tags = IntegerField('valid_tags', validators=[Optional()])
    invalid_tags = IntegerField('invalid_tags', validators=[Optional()])
    mss_tags = IntegerField('mss_tags', validators=[Optional()])


class SavedTagForm(FlaskForm):
    class Meta:
        csrf = False

    is_mss = BooleanField('is_mss', validators=[Optional()], false_values=(False, 'false', 0, '0'))
    tag_list = ListField('tag_list', validators=[InputRequired(), validate_tag_list])
    branch_code = StringField('branch_code', validators=[InputRequired()])
    lat = FloatField('lat', validators=[Optional()])
    long = FloatField('long', validators=[Optional()])


class GetTagForm(FlaskForm):
    class Meta:
        csrf = False

    branch_code = StringField('branch_code', validators=[InputRequired()])
    is_mss = BooleanField('is_mss', validators=[Optional()], false_values=(False, 'false', 0, '0'))


class GetAuditReport(FlaskForm):
    """
    WTF form class for validating the get_completed_activities API request.
    """
    class Meta:
        csrf = False

    from_date = StringField('from_date', validators=[Optional()])
    to_date = StringField('to_date', validators=[Optional()])
    is_complaint=StringField('is_complaint', validators=[Optional()])
    in_location=StringField('in_location', validators=[Optional()])
    is_filters_applied=BooleanField('in_location', validators=[Optional()])
    tagno_type=StringField('tagno_type', validators=[Optional()])
    state=StringField('state', validators=[Optional()])
    city=StringField('city', validators=[Optional()])
    Branchname=StringField('branchname', validators=[Optional()])
    AuditedBy=StringField('audited_by', validators=[Optional()])
    egrn=StringField('egrn', validators=[Optional()])
    CustomerId=StringField('CustomerId', validators=[Optional()])
    EntryType=StringField('EntryType', validators=[Optional()])
    Tagno=StringField('tagno', validators=[Optional()])

class GarmentAuditReportFormMss(FlaskForm):
    class Meta:
        csrf = False

    garment_audit_updates_list = ListField('garment_audit_updates_list',
                                               validators=[InputRequired(), validate_garment_audit_updates_list])


