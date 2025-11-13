"""
------------------------
Project settings module
Configurations and settings for the project.
------------------------
Coded by: Athira K
© Jyothy Fabricare Services LTD.
------------------------
"""

import os

# Redis server credentials
REDIS_SERVER_HOST = "127.0.0.1"
REDIS_SERVER_PORT = 6379

# List of permissible file types that can be accessed by a client via asset API router.
ACCESSIBLE_FILE_TYPES = ["img", "icon"]

# MSG91 SMS service credentials
MSG91_SEND_OTP_API = os.getenv("MSG91_SEND_OTP_API")
MSG91_AUTH_KEY = os.getenv("MSG91_AUTH_KEY")
MSG91_TEMPLATE_ID = os.getenv("MSG91_TEMPLATE_ID")
MSG91_MESSAGE_PARAM_1 = os.getenv("MSG91_MESSAGE_PARAM_1")

# SERVER_DB, LOCAL_DB settings based on the current environment.
CURRENT_ENV = os.getenv("FLASK_ENV")

if CURRENT_ENV == 'production':
    ENV = 'api'
    SERVER_DB = 'JFSL'
    LOCAL_DB = 'CustomerApp'
    OLD_DB = 'Mobile_JFSL'
    CRM = 'CRM'
    ALERT_ENGINE_DB = 'alert_Engine'
    DB_USER = os.getenv("LIVE_DB_USER")
    DB_PASS = os.getenv("LIVE_DB_PASSWD")
else:
    ENV = 'uatapi'
    SERVER_DB = 'JFSL_UAT'
    LOCAL_DB = 'CustomerApp'
    OLD_DB = 'Mobile_JFSL_UAT'
    CRM = 'CRM_UAT'
    ALERT_ENGINE_DB = 'alert_Engine_UAT'
    DB_USER = os.getenv("UAT_DB_USER")
    DB_PASS = os.getenv("UAT_DB_PASSWD")

# Send invoice link settings
if CURRENT_ENV == 'production':
    # Url for generating invoice link
    invoice_generate_url = 'https://app.fabricspa.com/paynow/report/'
    # url for shortening invoice link
    invoice_link_shortening_url = 'https://intapps.fabricspa.com/jfsl/api_controller/generate_shorturl_from_invoiceno'
else:
    invoice_generate_url = 'https://app.fabricspa.com/UAT/paynow/report/'
    invoice_link_shortening_url = 'https://appuat.fabricspa.com/UAT/jfsl/api_controller/generate_shorturl_from_invoiceno'

# EasyRewardz settings
if CURRENT_ENV == 'production':
    # EasyRewardz live credentials.
    er_app_id = os.getenv("ER_APP_ID")
    er_dev_id = os.getenv("ER_DEV_ID")
    er_program_code = os.getenv("ER_PROGRAM_CODE")
    er_username = os.getenv("ER_USERNAME")
    er_password = os.getenv("ER_PASSWORD")
    er_api_user = os.getenv("ER_API_USER")
    er_store_code = os.getenv("ER_STORE_CODE")
    redeem_er_coupon_url = 'http://live.jfsl.in/JER/api/JER/RedeemCoupon'
    unblock_er_coupon_url = 'http://live.jfsl.in/JER/api/JER/UnblockCoupon'
else:
    # EasyRewardz test credentials.
    er_app_id = os.getenv("ER_APP_ID_TESTING")
    er_dev_id = os.getenv("ER_DEV_ID_TESTING")
    er_program_code = os.getenv("ER_PROGRAM_CODE_TESTING")
    er_username = os.getenv("ER_USERNAME_TESTING")
    er_password = os.getenv("ER_PASSWORD_TESTING")
    er_api_user = os.getenv("ER_API_USER_TESTING")
    er_store_code = os.getenv("ER_STORE_CODE_TESTING")
    redeem_er_coupon_url = 'http://live.jfsl.in/JERUAT/api/JER/RedeemCoupon'
    unblock_er_coupon_url = 'http://live.jfsl.in/JERUAT/api/JER/UnblockCoupon'

# Paytm settings
if CURRENT_ENV == 'production':
    channel_id = "FAB"
    sale_request_url = "https://securegw-edc.paytm.in/ecr/payment/request"
    sale_request_status_url = 'https://securegw-edc.paytm.in/ecr/V2/payment/status'

else:
    channel_id = "FAB"
    sale_request_url = "https://securegw-stage.paytm.in/ecr/payment/request"
    sale_request_status_url = 'https://securegw-stage.paytm.in/ecr/V2/payment/status'

# EasyRewardz configuration based on the current environment.
ER_CONFIG = {
    'ER_APP_ID': er_app_id, 'ER_DEV_ID': er_dev_id, 'ER_PROGRAM_CODE': er_program_code,
    'ER_USERNAME': er_username, 'ER_PASSWORD': er_password, 'ER_API_USER': er_api_user,
    'ER_STORE_CODE': er_store_code
}

# Ameyo configuration.
AMEYO_AUTH_TOKEN = os.getenv("AMEYO_AUTH_TOKEN")

# Payment Link API key.
PAYMENT_LINK_API_KEY = os.getenv("PAYMENT_LINK_API_KEY")

# Ice Cubes SMS service credentials
ICE_CUBES_SMS_API = os.getenv("ICE_CUBES_SMS_API")
ICE_CUBES_TRANSACTIONAL_SMS_API_KEY = os.getenv("ICE_CUBES_TRANSACTIONAL_SMS_API_KEY")
ICE_CUBES_PROMOTIONAL_SMS_API_KEY = os.getenv("ICE_CUBES_PROMOTIONAL_SMS_API_KEY")
ICE_CUBES_SENDER = os.getenv("ICE_CUBES_SENDER")
