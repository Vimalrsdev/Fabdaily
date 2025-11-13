from wtforms import StringField, IntegerField, Field, FloatField, BooleanField
from wtforms.validators import InputRequired, Length, Optional, NumberRange
# from .validators import validate_latitude, validate_longitude, validate_otp_types, validate_hanger_instruction_actions, \
#     validate_sorting_method, validate_gender, validate_email, validate_payment_collection, validate_complaint_list, \
#     validate_day_interval, validate_activities, validate_address_details, validate_photo_types, validate_rewash_complaint_list, validate_final_rewash_list
from flask_wtf import FlaskForm

from .validators import validate_complaint_list


class ListField(Field):
    """
    A custom WTF field for accepting array of data.
    """

    def process_formdata(self, valuelist):
        self.data = valuelist


class StoreListForm(FlaskForm):
    """
    WTF form class for validating get_rank_list
    """

    class Meta:
        csrf = False

    user_id = IntegerField('user_id', validators=[InputRequired()])

class StoreList(FlaskForm):
    """
    WTF form class for validating the StoreList API request.
    """

    class Meta:
        csrf = False

    login_type = StringField('login_type', validators=[Optional()])


class SendOTPForm(FlaskForm):
    """
    WTF form class for validating the send_otp API request.
    """

    class Meta:
        csrf = False

    mobile_number = StringField('mobile_number', validators=[InputRequired(), Length(min=10, max=10,
                                                                                     message="Minimum 10 characters are needed"), ])
    otp_type = StringField('otp_type', validators=[InputRequired()])
    # , validate_otp_types

    person = StringField('person', validators=[Optional()])


class VerifyOTPForm(FlaskForm):
    """
    WTF form class for validating the verify_otp API request.
    """

    class Meta:
        csrf = False

    mobile_number = StringField('mobile_number', validators=[InputRequired(), Length(min=10, max=10,
                                                                                     message="Minimum 10 characters are needed"), ])
    otp = IntegerField('otp', validators=[InputRequired()])


class CollectAmountForm(FlaskForm):
    """
    WTF form class for validating the get_collection_amount API request.
    """

    class Meta:
        csrf = False

    store_id = StringField('store_id', validators=[InputRequired()])
    start_date = StringField('start_date', validators=[InputRequired()])
    end_date = StringField('end_date', validators=[InputRequired()])
    branch_name = StringField('branch_name', validators=[Optional()])


class SubmitCollectAmountForm(FlaskForm):
    """
    WTF form class for validating the verify_otp API request.
    """

    class Meta:
        csrf = False

    branch_code = StringField('branch_code', validators=[InputRequired()])
    branch_name = StringField('branch_name', validators=[InputRequired()])
    start_date = StringField('collection_type', validators=[InputRequired()])
    end_date = StringField('collection_type', validators=[InputRequired()])
    total_amount = StringField('total_amount', validators=[InputRequired()])
    collected_amount = StringField('collected_amount', validators=[Optional()])  
    remarks = StringField('remarks', validators=[InputRequired()])
    store_in_charge = StringField('store_in_charge', validators=[InputRequired()])
    


class PendingDepositeForm(FlaskForm):
    """
    WTF form class for validating the PendingDepositeForm API request.
    """

    class Meta:
        csrf = False

    store_id = StringField('store_id', validators=[Optional()])
    start_date = StringField('start_date', validators=[Optional()])
    end_date = StringField('end_date', validators=[Optional()])


class SubmitDepositeForm(FlaskForm):
    """
    WTF form class for validating the SubmitDepositeForm API request.
    """

    class Meta:
        csrf = False

    collection_id = ListField('store_id', validators=[InputRequired()])
    b64_image = StringField('b64_image', validators=[InputRequired()])


class DepositHistory(FlaskForm):
    """
    WTF form class for validating the DepositHistory API request.
    """

    class Meta:
        csrf = False

    store_id = StringField('store_id', validators=[Optional()])
    start_date = StringField('start_date', validators=[Optional()])
    end_date = StringField('end_date', validators=[Optional()])

class StorePermissionForm(FlaskForm):
    """
    WTF form class for validating the StorePermission API request.
    """

    class Meta:
        csrf = False

    lat = FloatField('lat', validators=[Optional()])
    # , validate_latitude , validate_longitude
    long = FloatField('long', validators=[Optional()])
    store_id = StringField('store_id', validators=[InputRequired()])
    app_type = StringField('app_type', validators=[Optional()])


class AuditComplaintsForm(FlaskForm):
    class Meta:
        csrf = False
    complaint_list = ListField('complaint_list', validators=[InputRequired(), validate_complaint_list])


class GarmentAuditForm(FlaskForm):
    class Meta:
        csrf = False
    tag_list = ListField('tag_list', validators=[InputRequired()])
    branch_code = StringField('branch_code', validators=[InputRequired()])

class GarmentAuditDetailsForm(FlaskForm):
    class Meta:
        csrf = False

    tag_list = ListField('tag_list', validators=[InputRequired()])
    branch_code = StringField('branch_code', validators=[InputRequired()])

class ClockInForm(FlaskForm):
    """
    WTF form class for validating the clock_in API request.
    """

    class Meta:
        csrf = False

    lat = FloatField('lat', validators=[Optional()])
    long = FloatField('long', validators=[Optional()])
    branch_code = StringField('branch_code', validators=[InputRequired()])
    app_type = StringField('app_type', validators=[InputRequired()])