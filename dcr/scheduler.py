from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
load_dotenv()
import openpyxl
import requests
import os
import random
from flask import current_app
from sqlalchemy import text
from datetime import datetime, timedelta
import atexit
import json
from dcr.generic.loggers import info_logger



db = SQLAlchemy()

def send_mail(app: Flask):
    try:
        with app.app_context():
            info_logger("Route: /scheduler/send_mail").info("Send mail job triggered")

            all_rows = []

            sp_query = "Exec Mobile_JFSL.[dbo].[SPGetAuditorVisitedBranchesToday]"
            result = db.session.execute(text(sp_query))
            rows = result.fetchall()

            log_data = {"query": sp_query, "result": len(rows) if rows else 0}
            info_logger("Route: /scheduler/send_mail").info(json.dumps(log_data))

            if not rows:
                info_logger("Route: /scheduler/send_mail").warning("No records found from SP.")
                return

            # Exclude fields
            exclude_fields = {"UserId", "State", "ClockinBranch","LastMailLogTime"}

            # Desired order (using DB column names)
            desired_order = [
                "Date",
                "AuditorName",
                "StoreName",
                "City",
                "StoreAccessFrom",
                "Roles",
                "ClockInTime",
                "VisitDurationMins",
            ]

            # Header rename mapping
            rename_map = {
                "AuditorName":"Auditor Name",
                "StoreName":"Store Name",
                "City": "Location",
                "StoreAccessFrom":"Store access from",
                "Roles": "Role",
                "ClockInTime": "Visit Time (Clock-in",
                "VisitDurationMins": "Visit Duration (hours",
            }

            # Convert rows to dicts
            columns = result.keys()
            for row in rows:
                all_rows.append(dict(zip(columns, row)))

            workbook = openpyxl.Workbook()
            worksheet = workbook.active

            # Pick final headers
            available_fields = set(all_rows[0].keys()) - exclude_fields
            headers = [h for h in desired_order if h in available_fields]
            headers += [h for h in available_fields if h not in headers]

            # Apply renaming for Excel header row
            display_headers = [rename_map.get(h, h) for h in headers]

            # Write headers
            worksheet.append(display_headers)

            # Write rows
            for r in all_rows:
                worksheet.append([
                    str(r.get(key, "")) if r.get(key) is not None else ""
                    for key in headers
                ])

            # Save Excel file
            folder_path = r"C:\jfsl_cloud\prod\fabdaily_mail_report"
            os.makedirs(folder_path, exist_ok=True)
            file_name = "report.xlsx"
            file_path = os.path.join(folder_path, file_name)
            workbook.save(file_path)

            info_logger("Route: /scheduler/send_mail").info(f"Report saved at {file_path}")
            from datetime import datetime, timedelta

            yesterday = (datetime.now() - timedelta(days=1)).strftime("%d-%m-%Y")  # or "%Y-%m-%d"

            # Send email via SP
            # email_query = f"""
            #     EXEC JFSL.[dbo].[SendCommanEmailFabDaily] 
            #         @FilePath='{file_name}', 
            #         @EmailTo='syari.ms@mmminfosolutions.com;jfsl.mdm@jyothy.com', 
            #         @EmailCC='aiswarya.sajeev@mmminfosolutions.com;aswani@mmminfosolutions.com;vimal@mmminfosolutions.com;suvin@mmminfosolutions.com', 
            #         @Subject='Store Audited On {yesterday}', 
            #         @Body='Hello Team,                                                                                                                                                                                                                 

            #         Attached is the summary of all the stores audited yesterday'
            # """
           
            body_text = "Hello Team,<br><br>Attached is the summary of all the stores audited yesterday"

            email_query = f"""
                EXEC JFSL.[dbo].[SendCommanEmailFabDaily] 
            @FilePath='{file_name}', 
            @EmailTo='sukanta.kishor@jyothy.com', 
            @EmailCC='jfsl.mdm@jyothy.com', 
            @Subject='Store Audited On {yesterday}', 
            @Body='{body_text}'
                    """


            info_logger("Route: /scheduler/send_mail").info(json.dumps({"query": email_query}))

            db.engine.execute(text(email_query).execution_options(autocommit=True))
            info_logger("Route: /scheduler/send_mail").info("Email sent successfully.")

    except Exception as e:
        info_logger("Route: /scheduler/send_mail").error(f"send_mail failed: {str(e)}")


def sendmailnotauditedstores(app: Flask):
    # send mail those  stores are not audited  both garment and store audit
    
    with app.app_context():
        info_logger("Route: /scheduler/sendmailnotauditedstores").info("Send mail job triggered")

        all_rows = []

        try:
            sp_query = "EXEC Mobile_JFSL.dbo.SPGetBranchesNotAudited"
            info_logger("Route: /scheduler/sendmailnotauditedstores").info(f"STEP 1: Before executing SP: {sp_query}")

            result = db.session.execute(text(sp_query))
            info_logger("Route: /scheduler/sendmailnotauditedstores").info("STEP 2: After executing SP")

            rows = result.fetchall()
            info_logger("Route: /scheduler/sendmailnotauditedstores").info(f"STEP 3: Rows fetched: {rows if rows else 0}")

        except Exception as e:
            info_logger("Route: /scheduler/sendmailnotauditedstores").error(f"ERROR at SP execution: {e}")
            return

        # If no rows, stop here
        if not rows:
            info_logger("Route: /scheduler/sendmailnotauditedstores").warning("No records found from SP. Exiting function.")
            return

        try:
            exclude_fields = {"Id", "LastAuditedDate"}

            desired_order = [
                "Auditor Name",
                "Contact #",
                "Store access from",
                "Role",
                "Screen Access",
                "State",
                "City",
                "Branches",
                "Last Audited Date"
                
            ]

            info_logger("Route: /scheduler/sendmailnotauditedstores").info("STEP 4: Processing rows into dictionaries")

            columns = result.keys()
            for row in rows:
                all_rows.append(dict(zip(columns, row)))

            worksheet = None
            workbook = openpyxl.Workbook()
            worksheet = workbook.active

            available_fields = set(all_rows[0].keys()) - exclude_fields
            headers = [h for h in desired_order if h in available_fields]
            headers += [h for h in available_fields if h not in headers]

            # Fix renaming mistake: desired_order is a list, not a dict
            display_headers = headers  # keep headers as-is

            info_logger("Route: /scheduler/sendmailnotauditedstores").info(f"STEP 5: Headers ready: {display_headers}")

            worksheet.append(display_headers)

            for r in all_rows:
                worksheet.append([
                    str(r.get(key, "")) if r.get(key) is not None else ""
                    for key in headers
                ])

            info_logger("Route: /scheduler/sendmailnotauditedstores").info("STEP 6: Rows written to Excel")

            folder_path = r"C:\jfsl_cloud\prod\fabdaily_mail_report"
            os.makedirs(folder_path, exist_ok=True)
            file_name = "sendmailnotauditedstores.xlsx"
            file_path = os.path.join(folder_path, file_name)
            workbook.save(file_path)

            info_logger("Route: /scheduler/sendmailnotauditedstores").info(f"STEP 7: Excel saved at: {file_path}")

        except Exception as e:
            info_logger("Route: /scheduler/sendmailnotauditedstores").error(f"ERROR while writing Excel: {e}")
            return
        body_text = "Hello Team,<br><br>Attached is the summary of all the stores not audited last month"

        try:
            email_query = f"""
                EXEC JFSL.[dbo].[SendCommanEmailFabDaily] 
                    @FilePath='{file_name}', 
                    @EmailTo='sukanta.kishor@jyothy.com', 
                    @EmailCC='jfsl.mdm@jyothy.com', 
                    @Subject='Fabdaily Not Audited Store Report', 
                    @Body='{body_text}'
            """

            info_logger("Route: /scheduler/sendmailnotauditedstores").info(f"STEP 8: Before sending email: {email_query}")

            db.engine.execute(text(email_query).execution_options(autocommit=True))

            info_logger("Route: /scheduler/sendmailnotauditedstores").info("STEP 9: Email sent successfully")

        except Exception as e:
            info_logger("Route: /scheduler/sendmailnotauditedstores").error(f"ERROR while sending email: {e}")
            return





from sqlalchemy import and_, func


def auto_logout_inactive_users1(app: Flask):
    """
    Auto logout users if no activity for 30 minutes within a 2-hour audit session.
    Only considers users clocked in today.
    """
    from datetime import datetime, timedelta
    from sqlalchemy import text

    with app.app_context():
        try:
            now = datetime.now().replace(microsecond=0)
            today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
            two_hours_ago = now - timedelta(hours=2)
            thirty_mins_ago = now - timedelta(minutes=30)

            info_logger("Scheduler").info("Starting auto logout job")
            info_logger("Scheduler").info(
                f"today_start: {today_start}, two_hours_ago: {two_hours_ago}, "
                f"thirty_mins_ago: {thirty_mins_ago}"
            )

            # 1️⃣ Get latest clock-in per user per branch today
            clocked_in_query = text("""
                SELECT c.UserId, MAX(c.RecordCreatedDate) AS ClockInTime, c.ClockinBranch
                FROM Mobile_JFSL.dbo.FabDailyMailClockIn c
                WHERE c.RecordCreatedDate >= :today_start
                GROUP BY c.UserId, c.ClockinBranch
            """)
            clocked_in_users = db.session.execute(clocked_in_query, {"today_start": today_start}).fetchall()
            info_logger("Scheduler").info(f"Clocked in users to check: {len(clocked_in_users)}")

            for user_id, clock_in_time, clockin_branch in clocked_in_users:
                info_logger("Scheduler").info(f"Checking user {user_id}, ClockInTime: {clock_in_time}, Branch: {clockin_branch}")

                # Check if user has been at branch for >= 2 hours
                if now - clock_in_time >= timedelta(hours=2):
                    # 2️⃣ Get last activity (mail) after clock-in for that branch
                    last_activity_query = text("""
                        SELECT TOP 1 RecordCreatedDate
                        FROM Mobile_JFSL.dbo.FabdailyMails
                        WHERE UserId = :user_id
                          AND BranchCode = :clockin_branch
                          AND RecordCreatedDate >= :clock_in_time
                        ORDER BY RecordCreatedDate DESC
                    """)
                    result = db.session.execute(last_activity_query, {
                        "user_id": user_id,
                        "clockin_branch": clockin_branch,
                        "clock_in_time": clock_in_time
                    }).fetchone()

                    last_activity = result[0] if result else None
                    info_logger("Scheduler").info(f"Last activity for user {user_id}: {last_activity}")

                    # 3️⃣ Auto logout if no activity or last activity > 30 mins ago
                    if not last_activity or last_activity < thirty_mins_ago:
                    #if last_activity < thirty_mins_ago:
                        info_logger("Scheduler").info(f"Last activity  {user_id}: {last_activity}")
                        info_logger("Scheduler").info(f"User {user_id} inactive for 30+ mins, auto-logging out")

                        update_query = text("""
                            UPDATE Mobile_JFSL.dbo.DcrUserLogins
                            SET IsActive = 0, AuthKeyExpiry = 1
                            WHERE DUserId = :user_id
                        """)
                        db.session.execute(update_query, {"user_id": user_id})
                        info_logger("Scheduler").info("Auto logout job completed successfully")

            # Commit once after all updates
            db.session.commit()
            info_logger("Scheduler").info("Auto ")
            

        except Exception as e:
            import traceback
            error_logger("Scheduler").error(f"Auto logout job failed: {e}\n{traceback.format_exc()}")

def auto_logout_inactive_users(app: Flask):
    """
    Auto logout users if no activity for 30 minutes within a 2-hour audit session.
    Only considers users clocked in today.
    """
    from datetime import datetime, timedelta
    from sqlalchemy import text

    with app.app_context():
        try:
            now = datetime.now().replace(microsecond=0)
            today_start = datetime(now.year, now.month, now.day, 0, 0, 0)

            
            # after 2 hours from clock-in, check if no activity in last 30 minutes (now - 30 min)
            two_hours_ago = now - timedelta(hours=2)
            thirty_mins_ago = now - timedelta(minutes=30)

            info_logger("Scheduler").info("Starting auto logout job")
            info_logger("Scheduler").info(
                f"today_start: {today_start}, two_hours_ago: {two_hours_ago}, "
                f"thirty_mins_ago: {thirty_mins_ago}"
            )

            # 1️⃣ Get latest clock-in per user per branch today
            # clocked_in_query = text("""
            #     SELECT c.UserId, MAX(c.RecordCreatedDate) AS ClockInTime, c.ClockinBranch
            #     FROM Mobile_JFSL.dbo.FabDailyMailClockIn c
            #     WHERE c.RecordCreatedDate >= :today_start
            #         AND c.Apptype = 'audit' 
            #     GROUP BY c.UserId, c.ClockinBranch
            # """)
            clocked_in_query = text("""
                ;WITH RankedClockIns AS (
                    SELECT 
                        c.UserId,
                        c.RecordCreatedDate AS ClockInTime,
                        c.ClockinBranch,
                        ROW_NUMBER() OVER (PARTITION BY c.UserId ORDER BY c.RecordCreatedDate DESC) AS rn
                    FROM Mobile_JFSL.dbo.FabDailyMailClockIn c
                    WHERE c.RecordCreatedDate >= :today_start
                      AND c.Apptype = 'audit'
                )
                SELECT UserId, ClockInTime, ClockinBranch
                FROM RankedClockIns
                WHERE rn = 1
            """)
                        
            clocked_in_users = db.session.execute(
                clocked_in_query, {"today_start": today_start}
            ).fetchall()

            info_logger("Scheduler").info(f"Clocked in users to check: {len(clocked_in_users)}")

            for user_id, clock_in_time, clockin_branch in clocked_in_users:
                info_logger("Scheduler").info(
                    f"Checking user {user_id}, ClockInTime: {clock_in_time}, Branch: {clockin_branch}"
                )

                # 2️⃣ Check if user has been at branch for >= 2 hours
                if now - clock_in_time >= timedelta(hours=2):

                    # 3️⃣ Get last activity (mail) after clock-in for that branch
                    last_activity_query = text("""
                        SELECT TOP 1 RecordCreatedDate
                        FROM Mobile_JFSL.dbo.FabdailyMails
                        WHERE UserId = :user_id
                          AND BranchCode = :clockin_branch
                          AND RecordCreatedDate >= :clock_in_time
                        ORDER BY RecordCreatedDate DESC
                    """)
                    result = db.session.execute(
                        last_activity_query,
                        {
                            "user_id": user_id,
                            "clockin_branch": clockin_branch,
                            "clock_in_time": clock_in_time
                        }
                    ).fetchone()

                    last_activity = result[0] if result else None
                    info_logger("Scheduler").info(
                        f"User {user_id} last activity: {last_activity}"
                    )

                    # 4️⃣ Auto logout if no activity in last 30 minutes
                    if not last_activity or last_activity < thirty_mins_ago:
                        info_logger("Scheduler").info(
                            f"User {user_id} inactive since {last_activity}, auto-logging out..."
                        )

                        update_query = text("""
                            UPDATE Mobile_JFSL.dbo.DcrUserLogins
                            SET IsActive = 0, AuthKeyExpiry = 1
                            WHERE DUserId = :user_id
                        """)
                        db.session.execute(update_query, {"user_id": user_id})

            # 5️⃣ Commit all updates together
            db.session.commit()
            info_logger("Scheduler").info("Auto logout job completed successfully")

        except Exception as e:
            import traceback
            error_logger("Scheduler").error(
                f" Auto logout job failed: {e}\n{traceback.format_exc()}"
            )







def init_scheduler(app: Flask):
    """
    Initialize APScheduler to run background tasks.
    """
    scheduler = BackgroundScheduler()

    # Add background job to run every 15 minutes
    #scheduler.add_job(func=triggermail, trigger='interval', minutes=1, args=[app])
    
    

    scheduler.add_job(
        func=send_mail,
        trigger='cron',
        hour=10,       # 24-hour format: 13 = 1 PM
        minute=2,     # 15 minutes past the hour
        args=[app],
        id='daily_send_mail_job',
        replace_existing=True
    )
    # scheduler.add_job(
    #     func=sendmailnotauditedstores,
    #     trigger='cron',
    #     hour=22,       # 24-hour format: 13 = 1 PM
    #     minute=57,     # 15 minutes past the hour
    #     args=[app],
    #     id='daily_send_mail',
    #     replace_existing=True
    # )

    scheduler.add_job(
        func=sendmailnotauditedstores,
        trigger='cron',
        day='1',
        hour=10,
        minute=1,
        args=[app],
        id='monthly_send_mail',
        replace_existing=True
    )

    scheduler.add_job(
        func=auto_logout_inactive_users,
        trigger='interval',
        minutes=5,
        args=[app],
        id='auto_logout_inactive_users',
        replace_existing=True
    )

    scheduler.start()

    # Ensure scheduler shuts down when Python exits
    atexit.register(lambda: scheduler.shutdown())

    # Log scheduler startup safely
    with app.app_context():
        info_logger("Route: /scheduler/init_scheduler").info(
            json.dumps({"scheduler": "APScheduler started"})
        )

















