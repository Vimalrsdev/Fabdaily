from flask import Blueprint, request, current_app, send_file, redirect
import jinja2
import os
from dcr import db
from sqlalchemy import text
from dcr.generic.loggers import info_logger, error_logger
import json

#
# def audit_mail(data, test, subject, report, mails,cc_mail=None):
def audit_mail(data, test, subject, report, mails, branch_code=None, cc_mail=None,is_history=None):
    try:
        log_data = {
            'collection mail B4 Qry': 'B4 mail call'
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        root_dir = os.path.dirname(current_app.instance_path)
        template_loader = jinja2.FileSystemLoader(f'{root_dir}/static')
        template_env = jinja2.Environment(loader=template_loader)
        template = template_env.get_template(data)
        output_text = template.render(test=test)
       
        log_data = {
            'OutPut_Text': output_text,
            "root_dir":root_dir,
            'data':data,
            'test':test,
            'subject':subject,
            'report':report,

        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))

        query = f"EXEC Alert_Engine..ALERT_PROCESS @ALERT_CODE = 'Auditmails_App', @EMAIL_ID = '{mails}'," \
                f"@MOBILE_NO = null ,@SUBJECT = '{subject}',@DISPATCH_FLAG = 'OFF'," \
                f"@EMAIL_SENDER_ADD = NULL, @SMS_SENDER_ADD = NULL,@P1 = '{output_text}',@P2 = '{cc_mail}'," \
                f"@P3 = null, @P4= null, @P5= null," \
                f"@P6 = null, @P7 = '{report}', @P8 = NULL,@P9 = NULL, @P10 = NULL, @P11 = NULL, @P12 = NULL," \
                f"@P13 = NULL, @P14 = NULL,@P15= NULL,@P16 = NULL, @P17 = NULL,@P18 = NULL, @P19 = NULL , @P20 = NULL," \
                f"@REC_ID = '0'"


        user_id = request.headers.get('user-id')

        # insert_qry  = db.session.execute(text( """
        #     INSERT INTO Mobile_JFSL.dbo.FabdailyMails (MailLog, Status, UserId, BranchCode)
        #     Values (:MailLog ,:Status, :UserId, :BranchCode)
        #     """),{
        #     "MailLog":query,
        #     "Status":0,
        #     "UserId": user_id,
        #     "BranchCode": branch_code
        #     })

        insert_qry  = db.session.execute(text( """
            INSERT INTO Mobile_JFSL.dbo.FabdailyMails (MailLog, Status, Source, UserId, BranchCode, is_history)
            Values (:MailLog ,:Status,:Source ,:UserId, :BranchCode, :is_history)
            """),{
            "MailLog":query,
            "Status":0,
            "Source": 0,
            "UserId": user_id,
            "BranchCode": branch_code,
            "is_history":1 if is_history else 0
            })
        db.session.commit()
        #db.engine.execute(text(query).execution_options(autocommit=True))
        with db.engine.connect() as conn:
            conn.execution_options(autocommit=True).execute(text(query))
        
        
     
        


        
           
        log_data = {
            'audit_mail tst': query
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    except Exception as ex:
        # error_logger(f'Route: {request.path}').error(ex)
        # print("Un-able to send mail")
        log_data = {
            # 'mail Exception': query,
            'excp': str(ex)
        }
        info_logger(f'Route: {request.path}').info(json.dumps(log_data))
    return True

   