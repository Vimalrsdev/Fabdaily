"""
------------------------
Model module
The Fabric's SQL Alchemy model classes. These model classes represent tables in DB that are used by the project.
------------------------
Coded by: Athira K
© Jyothy Fabricare Services LTD.
------------------------
"""

from dcr import db
from sqlalchemy import CHAR, DECIMAL, ForeignKey, Integer, text, Time, Date, Unicode, Float
from sqlalchemy.dialects.mssql import BIT, UNIQUEIDENTIFIER, TINYINT
from sqlalchemy.orm import relationship
from sqlalchemy import Text



class DCR_Users(db.Model):
    """
    This master table contains ranking city which are used to calculate rank of delivery user
    """
    __tablename__ = 'DCR_Users'

    Id = db.Column(Integer, primary_key=True)
    Date = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    Name = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    Phone = db.Column(db.String(20, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    Brand = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    CityCode = db.Column(db.String(200, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    Password = db.Column(db.String(200, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    Privilege = db.Column(db.String(200, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    CreatedBy = db.Column(db.String(200, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    Branches = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    BranchNames = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    CityName = db.Column(db.String(50, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    store_access_limit = db.Column(db.String(50, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    is_active = db.Column(BIT, nullable=False, server_default=text("((1))"))
    app_login = db.Column(BIT, nullable=False, server_default=text("((1))"))
    is_audit_active = db.Column(BIT, nullable=False, server_default=text("((1))"))
    screen_access = db.Column(BIT, nullable=False, server_default=text("((1))"))
    audit_store_access_limit = db.Column(db.String(50, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    garment_screen_access = db.Column(db.String(50, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    store_screen_access = db.Column(db.String(50, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    mss_screen_access = db.Column(db.String(50, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    email = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    Roles = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    IsDeleted = db.Column(Integer, nullable=False)

# class DCR_Collections(db.Model):
#     """
#     This master table contains ranking city which are used to calculate rank of delivery user
#     """
#     __tablename__ = 'DCR_Collections'

#     Id = db.Column(Integer, primary_key=True)
#     Date = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
#     StoreBranchCode = db.Column(db.String(50, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
#     StoreBranchName = db.Column(db.String(100, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
#     CollectionType = db.Column(db.String(50, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
#     DateFrom = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
#     DateTo = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
#     TotalAmount = db.Column(DECIMAL(18, 2), nullable=False)
#     CollectedAmount = db.Column(DECIMAL(18, 2), nullable=False)
#     IsDeposited = db.Column(Integer, nullable=False)
#     DepositId = db.Column(Integer, nullable=False)
#     DepositedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
#     Remarks = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
#     StoreInCharge = db.Column(Integer, nullable=False)
#     CollectedBy = db.Column(Integer, nullable=False)
#     IsDeleted = db.Column(Integer, nullable=False)

#     StoreBranchCity = db.Column(db.String(100, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
#     StoreBranchState = db.Column(db.String(100, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
#     Brand = db.Column(db.String(100, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
#     FabricareSettlementAmount = db.Column(DECIMAL(18, 2), nullable=False)
#     TotalCashTobeCollected = db.Column(DECIMAL(18, 2), nullable=False)

class DCR_Collection(db.Model):
    """
    This master table contains ranking city which are used to calculate rank of delivery user
    """
    __tablename__ = 'DCR_Collection'

    Id = db.Column(Integer, primary_key=True)
    Date = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    StoreBranchCode = db.Column(db.String(50, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    StoreBranchName = db.Column(db.String(100, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    CollectionType = db.Column(db.String(50, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    DateFrom = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    DateTo = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    TotalAmount = db.Column(DECIMAL(18, 2), nullable=False)
    CollectedAmount = db.Column(DECIMAL(18, 2), nullable=False)
    IsDeposited = db.Column(Integer, nullable=False)
    DepositId = db.Column(Integer, nullable=False)
    DepositedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    Remarks = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    StoreInCharge = db.Column(Integer, nullable=False)
    CollectedBy = db.Column(Integer, nullable=False)
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
    StoreBranchCity = db.Column(db.String(100, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    StoreBranchState = db.Column(db.String(100, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    Brand = db.Column(db.String(100, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    FabricareSettlementAmount = db.Column(DECIMAL(18, 2), nullable=False)
    TotalCashTobeCollected = db.Column(DECIMAL(18, 2), nullable=False)



class DCR_Deposits(db.Model):
    """
    This master table contains ranking city which are used to calculate rank of delivery user
    """
    __tablename__ = 'DCR_Deposits'

    Id = db.Column(Integer, primary_key=True)
    Date = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    DepositedAmount = db.Column(DECIMAL(18, 2), nullable=False)
    Image = db.Column(db.String(1000, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    DepositedBy = db.Column(Integer, nullable=False)
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))


class DCR_Deposit(db.Model):
    """
    This master table contains ranking city which are used to calculate rank of delivery user
    """
    __tablename__ = 'DCR_Deposit'

    Id = db.Column(Integer, primary_key=True)
    Date = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    DepositedAmount = db.Column(DECIMAL(18, 2), nullable=False)
    Image = db.Column(db.String(1000, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    DepositedBy = db.Column(Integer, nullable=False)
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))



class DCR_Pendings(db.Model):
    """
    This master table contains ranking city which are used to calculate rank of delivery user
    """
    __tablename__ = 'DCR_Pendings'

    Id = db.Column(Integer, primary_key=True)
    Date = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    StoreBranchCode = db.Column(db.String(1000, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    StoreBranchName = db.Column(db.String(1000, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    PendingAmount = db.Column(DECIMAL(18, 2), nullable=False)
    Image = db.Column(db.String(1000, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    DepositedBy = db.Column(Integer, nullable=False)


class DCR_PendingsLog(db.Model):
    """
    This master table contains ranking city which are used to calculate rank of delivery user
    """
    __tablename__ = 'DCR_PendingsLog'

    Id = db.Column(Integer, primary_key=True)
    Date = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    StoreBranchCode = db.Column(db.String(1000, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    StoreBranchName = db.Column(db.String(1000, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    DateFrom = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    DateTo = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    PendingAmount = db.Column(DECIMAL(18, 2), nullable=False)
    Remarks = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    StoreInCharge = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    CollectedBy = db.Column(Integer, nullable=False)


class DCR_SMSLogs(db.Model):
    """
    This table contains the SMS API service's logs.
    """
    __tablename__ = 'DCR_SMSLogs'
    # Edited By MMM
    CustomerId = db.Column(Integer)
    # Edited By MMM
    Id = db.Column(Integer, primary_key=True)
    MobileNumber = db.Column(db.String(20, 'SQL_Latin1_General_CP1_CI_AS'))
    APIRequest = db.Column(db.String(2000, 'SQL_Latin1_General_CP1_CI_AS'))
    APIResponse = db.Column(db.String(2000, 'SQL_Latin1_General_CP1_CI_AS'))
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))


class DCR_OTPs(db.Model):
    """
    This table contains all the generated OTPs and corresponding mobile number and result from the SMS vendor.
    Relationship(s):
    SMSLog is a foreign key referencing Id in SMSLogs table.
    """
    __tablename__ = 'DCR_OTPs'

    OTPId = db.Column(Integer, primary_key=True)
    OTP = db.Column(Integer, nullable=False)
    MobileNumber = db.Column(db.String(20, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    Type = db.Column(db.String(50, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    Person = db.Column(db.String(100, 'SQL_Latin1_General_CP1_CI_AS'))
    IsVerified = db.Column(BIT, nullable=False, server_default=text("((0))"))
    SMSLog = db.Column(Integer, nullable=False)
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))

    # SMSLog1 = relationship('DCR_SMSLogs')

class DcrUserLogins(db.Model):
    """
    This table contains the login information for delivery users.
    Relationship(s):
    DUserId is a foreign key referencing DUserId in DeliveryUsers table.
    """
    __tablename__ = 'DcrUserLogins'
    # Edited by MMM
    FcmToken = db.Column(db.String(255, 'SQL_Latin1_General_CP1_CI_AS'))
    AppVersion = db.Column(db.String(255, 'SQL_Latin1_General_CP1_CI_AS'))
    BuildNumber = db.Column(db.Integer())
    # Edited by MMM
    DcrUserLoginId = db.Column(Integer, primary_key=True)
    DUserId = db.Column(ForeignKey('DCR_Users.Id'), nullable=False)
    LoginTime = db.Column(db.DateTime, nullable=False)
    AuthKey = db.Column(db.String(200, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    AuthKeyExpiry = db.Column(BIT, nullable=False, server_default=text("((0))"))
    LastAccessTime = db.Column(db.DateTime, nullable=False)
    IsActive = db.Column(BIT, nullable=False, server_default=text("((1))"))
    DeviceType = db.Column(CHAR(1, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    DeviceIP = db.Column(db.String(50, 'SQL_Latin1_General_CP1_CI_AS'))
    Browser = db.Column(db.String(80, 'SQL_Latin1_General_CP1_CI_AS'))
    Platform = db.Column(db.String(80, 'SQL_Latin1_General_CP1_CI_AS'))
    Language = db.Column(db.String(80, 'SQL_Latin1_General_CP1_CI_AS'))
    UAString = db.Column(db.String(200, 'SQL_Latin1_General_CP1_CI_AS'))
    UAVersion = db.Column(db.String(30, 'SQL_Latin1_General_CP1_CI_AS'))
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordLastUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordVersion = db.Column(Integer, nullable=False, server_default=text("((0))"))
    Date = db.Column(Date, nullable=False)


    DCR_Users = relationship('DCR_Users')


class DCR_DateWiseCollections(db.Model):
    """
    This table contains all the generated OTPs and corresponding mobile number and result from the SMS vendor.
    Relationship(s):
    SMSLog is a foreign key referencing Id in SMSLogs table.
    """
    __tablename__ = 'DCR_DateWiseCollections'

    Id = db.Column(Integer, primary_key=True)
    Date = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    TotalAmount = db.Column(DECIMAL(18, 2), nullable=False)
    PendingAmount = db.Column(DECIMAL(18, 2), nullable=False)
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    BranchCode = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
    BranchName = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    # EGRN = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    # BillNo = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)


class DCR_DateWiseCollection(db.Model):
    """
    This table contains all the generated OTPs and corresponding mobile number and result from the SMS vendor.
    Relationship(s):
    SMSLog is a foreign key referencing Id in SMSLogs table.
    """
    __tablename__ = 'DCR_DateWiseCollection'

    Id = db.Column(Integer, primary_key=True)
    Date = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    TotalAmount = db.Column(DECIMAL(18, 2), nullable=False)
    PendingAmount = db.Column(DECIMAL(18, 2), nullable=False)
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    BranchCode = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
    BranchName = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    EGRN = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    BillNo = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)



class DCR_Branch_Access(db.Model):
    __tablename__ = 'DCR_Branch_Access'

    Id = db.Column(Integer, primary_key=True)
    user_id = db.Column(ForeignKey('DCR_Users.Id'))
    date = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    end_date = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    store_access = db.Column(BIT, nullable=False, server_default=text("((0))"))
    app_login = db.Column(BIT, nullable=False, server_default=text("((0))"))

    DcrUser = relationship('DCR_Users')



class Audit_Complaints(db.Model):
    """
    This table contains all the generated OTPs and corresponding mobile number and result from the SMS vendor.
    Relationship(s):
    SMSLog is a foreign key referencing Id in SMSLogs table.
    """
    __tablename__ = 'Audit_Complaints'

    Id = db.Column(Integer, primary_key=True)
    IsPhoto = db.Column(BIT, nullable=False, server_default=text("((0))"))
    IsRemarks = db.Column(BIT, nullable=False, server_default=text("((0))"))
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
    AuditQuestions = db.Column(db.String(2000, 'SQL_Latin1_General_CP1_CI_AS'))
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordLastUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    IsYesNo = db.Column(BIT, nullable=False, server_default=text("((0))"))
    IsAttachment = db.Column(BIT, nullable=False, server_default=text("((0))"))
    IsPhotoRequired = db.Column(BIT, nullable=False, server_default=text("((0))"))
    IsAttachmentRequired = db.Column(BIT, nullable=False, server_default=text("((0))"))
    IsRemarksRequired = db.Column(BIT, nullable=False, server_default=text("((0))"))
    IsYesNoRequired = db.Column(BIT, nullable=False, server_default=text("((0))"))
    IsQuestionRequired = db.Column(BIT, nullable=False, server_default=text("((0))"))
    Roles=db.Column(BIT, nullable=False, server_default=text("((0))"))



class StoreAudits(db.Model):
    """
    This table contains all the generated OTPs and corresponding mobile number and result from the SMS vendor.
    Relationship(s):
    SMSLog is a foreign key referencing Id in SMSLogs table.
    """
    __tablename__ = 'StoreAudits'

    Id = db.Column(Integer, primary_key=True)
    ComplaintId = db.Column(ForeignKey('Audit_Complaints.Id'), nullable=False)
    BranchCode = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    AuditDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
    IsActive = db.Column(BIT, nullable=False, server_default=text("((0))"))
    AuditedBy = db.Column(ForeignKey('DCR_Users.Id'))
    Remarks = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordLastUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    BranchName = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    BranchCity = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    BranchState = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    IsYesNo = db.Column(Integer, nullable=False, server_default=text("((0))"))
    lat = db.Column(DECIMAL(13, 10))
    long = db.Column(DECIMAL(13,10))
    InLocation=db.Column(Integer)

    Audit_Complaints = relationship('Audit_Complaints')
    DcrUser = relationship('DCR_Users')

class AuditPhotos(db.Model):
    """
    This table contains all the generated OTPs and corresponding mobile number and result from the SMS vendor.
    Relationship(s):
    SMSLog is a foreign key referencing Id in SMSLogs table.
    """
    __tablename__ = 'AuditPhotos'

    AuditPhotoId = db.Column(Integer, primary_key=True)
    StoreAuditId = db.Column(ForeignKey('StoreAudits.Id'), nullable=False)
    AuditImage = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordLastUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))

    DcrUser = relationship('StoreAudits')


class AuditTags(db.Model):
    __tablename__ = 'AuditTags'

    Id = db.Column(Integer, primary_key=True)
    TagNo = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    BranchCode = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
    IsActive = db.Column(BIT, nullable=False, server_default=text("((0))"))
    ScannedBy = db.Column(ForeignKey('DCR_Users.Id'))
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordLastUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    EGRN = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    GarmentStatus = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    OrderStatus = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    GarmentBranchCode = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    GarmentBranchName = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    ComplaintId = db.Column(Integer)
    isScannedInMss=db.Column(Integer)
    ComplaintStatus = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    ComplaintDepartment = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    ComplaintDate = db.Column(db.DateTime)
    #EntryType = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    CustomerId = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    BranchName = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    BranchCity = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    BranchState = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    ResolutionType = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    IsMSS = db.Column(BIT, nullable=False, server_default=text("((0))"))
    MSSName = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    EntryType = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    Date = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    InLocation = db.Column(BIT, nullable=False, server_default=text("((0))"))
    IsDelivered = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    IsValidTag = db.Column(BIT, nullable=False, server_default=text("((0))"))
    IsNoStock = db.Column(BIT, nullable=False, server_default=text("((0))"))
    CustomerName = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    GarmentName = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    GarmentAmount = db.Column(DECIMAL(18, 2))
    AuditedBy = db.Column(Integer)
    ScanId = db.Column(Integer)
    Execptionflag = db.Column(Integer, nullable=False)
    IsScanned=db.Column(BIT, nullable=False, server_default=text("((0))"))
    OrderType = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))


    DcrUser = relationship('DCR_Users')




class DCR_User_Branches(db.Model):
    __tablename__ = 'DCR_User_Branches'

    Id = db.Column(Integer, primary_key=True)
    UserId = db.Column(ForeignKey('DCR_Users.Id'))
    BranchCode = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    BranchNames = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    app_login = db.Column(BIT, nullable=False, server_default=text("((1))"))
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
    BranchName = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)


    DcrUser = relationship('DCR_Users')

# class AuditGarmentCount(db.Model):
#     __tablename__ = 'AuditGarmentCount'

#     Id = db.Column(Integer, primary_key=True)
#     Date = db.Column(Date, nullable=False)
#     GarmentCount = db.Column(Integer, nullable=False)
#     BranchCode = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
#     IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
#     RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
#     RecordUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))

class AuditGarmentCount(db.Model):
    __tablename__ = 'AuditGarmentCount'

    Id = db.Column(Integer, primary_key=True)
    Date = db.Column(Date, nullable=False)
    GarmentCount = db.Column(Integer, nullable=False)
    BranchCode = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    ScanId = db.Column(Integer, nullable=False)
    AuditedBy = db.Column(Integer, nullable=False)

class Audit_Complaints_Branches(db.Model):
    __tablename__ = 'Audit_Complaints_Branches'

    Id = db.Column(Integer, primary_key=True)
    QstnId = db.Column(ForeignKey('Audit_Complaints.Id'))
    BranchCode = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    BranchNames = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)

    Audit_Complaints = relationship('Audit_Complaints')

class AuditAttachements(db.Model):
    __tablename__ = 'AuditAttachements'

    AuditAttachementId = db.Column(Integer, primary_key=True)
    StoreAuditId = db.Column(ForeignKey('StoreAudits.Id'), nullable=False)
    AuditAttachement = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordLastUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))

    DcrUser = relationship('StoreAudits')


class FabDailyClockIn(db.Model):
    """
    This table contains the daily attendance logs of the delivery user.
    Relationship(s):
    DUserId is a foreign key referencing DUserId in DeliveryUsers table.
    """
    __tablename__ = 'FabDailyClockIn'
    Id = db.Column(Integer, primary_key=True)
    UserId = db.Column(ForeignKey('DCR_Users.Id'), nullable=False)
    Date = db.Column(Date, nullable=False)
    Apptype = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    ClockinBranch = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    ClockInTime = db.Column(Time, nullable=False)
    ClockInLat = db.Column(DECIMAL(13, 10))
    ClockInLong = db.Column(DECIMAL(13, 10))
    ClockOutTime = db.Column(Time)
    ClockOutLat = db.Column(DECIMAL(13, 10))
    ClockOutLong = db.Column(DECIMAL(13, 10))
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordLastUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    StoreAccessFrom = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)

    DcrUser = relationship('DCR_Users')


class SavedTags(db.Model):
    """ This table saves the tag details temporarily"""
    __tablename__ = 'SavedTags'
    Id = db.Column(Integer, primary_key=True)
    TagNo = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    BranchCode = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    ScannedBy = db.Column(ForeignKey('DCR_Users.Id'))
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordLastUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    EntryType = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'))
    IsMSS = db.Column(BIT, nullable=False, server_default=text("((0))"))
    DcrUser = relationship('DCR_Users')

class FabdailyMails(db.Model):
    """ This table saves the tag details temporarily"""
    __tablename__ = 'FabdailyMails'

    Id = db.Column(Integer, primary_key=True)

    MailLog = db.Column(Text(collation='SQL_Latin1_General_CP1_CI_AS'))

    Status = db.Column(BIT, nullable=False, server_default=text("((0))"))

class FabDailyMailClockIn(db.Model):
    """
    This table contains the daily attendance logs of the delivery user.
    Relationship(s):
    DUserId is a foreign key referencing DUserId in DeliveryUsers table.
    """
    __tablename__ = 'FabDailyMailClockIn'
    Id = db.Column(Integer, primary_key=True)
    UserId = db.Column(ForeignKey('DCR_Users.Id'), nullable=False)
    Date = db.Column(Date, nullable=False)
    Apptype = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    ClockinBranch = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)
    ClockInTime = db.Column(Time, nullable=False)
    ClockInLat = db.Column(DECIMAL(13, 10))
    ClockInLong = db.Column(DECIMAL(13, 10))
    ClockOutTime = db.Column(Time)
    ClockOutLat = db.Column(DECIMAL(13, 10))
    ClockOutLong = db.Column(DECIMAL(13, 10))
    IsDeleted = db.Column(BIT, nullable=False, server_default=text("((0))"))
    RecordCreatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    RecordLastUpdatedDate = db.Column(db.DateTime, nullable=False, server_default=text("(getdate())"))
    StoreAccessFrom = db.Column(db.String(500, 'SQL_Latin1_General_CP1_CI_AS'), nullable=False)

    DcrUser = relationship('DCR_Users')