from utils import descriptorUtils, listUtils, SanitationUtils, TimeUtils
from csvparse_abstract import CSVParse_Base, ImportObject, ObjList
from collections import OrderedDict
from coldata import ColData_User
from contact_objects import ContactAddress
import os
import csv
import time
from pprint import pprint
import operator
import re

usrs_per_file = 1000

DEBUG_FLAT = False

class ImportFlat(ImportObject):
    pass

class CSVParse_Flat(CSVParse_Base):

    objectContainer = ImportFlat
    # def __init__(self, cols, defaults):
    #     super(CSVParse_Flat, self).__init__(cols, defaults)

class ImportSpecial(ImportFlat):

    ID = descriptorUtils.safeKeyProperty('ID')
    start_time = descriptorUtils.safeKeyProperty('start_time')
    end_time = descriptorUtils.safeKeyProperty('end_time')

    # @property
    # def start_time_iso(self): return TimeUtils.isoTimeToString(self.start_time)

    # @property
    # def end_time_iso(self): return TimeUtils.isoTimeToString(self.end_time)

    def __init__(self,  data, rowcount, row):
        super(ImportSpecial, self).__init__(data, rowcount, row)
        try:
            self.ID
        except:
            raise UserWarning('ID exist for Special to be valid')

        self['start_time'] = TimeUtils.gDriveStrpTime(self['FROM'])
        self['end_time'] = TimeUtils.gDriveStrpTime(self['TO'])

    def getIndex(self):
        return self.ID

class CSVParse_Special(CSVParse_Flat):

    objectContainer = ImportSpecial

    def __init__(self, cols=[], defaults={}):
        extra_cols = [
            "ID", 
            "FROM",
            "TO",
            "RNS",
            "RPS",
            "WNS",
            "WPS",
            "XRNS",
            "XRPS",
            "XWNS",
            "XWPS"
        ]
        cols = listUtils.combineLists(cols, extra_cols)

        super(CSVParse_Special, self).__init__(cols, defaults)
        self.objectIndexer = self.getObjectID

    def getObjectID(self, objectData):
        return objectData.ID     

class ImportUser(ImportFlat):

    email = descriptorUtils.safeKeyProperty('E-mail')
    MYOBID = descriptorUtils.safeKeyProperty('MYOB Card ID')
    username = descriptorUtils.safeKeyProperty('Wordpress Username')
    role = descriptorUtils.safeKeyProperty('Role')
    contact_schema = descriptorUtils.safeKeyProperty('contact_schema')
    billing_address = descriptorUtils.safeKeyProperty('Address')
    shipping_address = descriptorUtils.safeKeyProperty('Home Address')

    def __init__(self, data, rowcount=None, row=None, **kwargs):
        super(ImportUser, self).__init__(data, rowcount, row)
        for key in ['E-mail', 'MYOB Card ID', 'Wordpress Username', 'Role', 'contact_schema']:
            val = kwargs.get(key, "")
            if(val):
                self[key] = val
            elif(not self.get(key)):
                self[key] = ""

        self['Address'] = ContactAddress(
            self.contact_schema,  
            line1       = self.get('Address 1', ''),
            line2       = self.get('Address 2', ''),
            city        = self.get('City', ''),
            postcode    = self.get('Postcode', ''),
            state       = self.get('State', ''),
            country     = self.get('Country'),
        )

        self['Home Address'] = ContactAddress(
            self.contact_schema,  
            line1       = self.get('Home Address 1', ''),
            line2       = self.get('Home Address 2', ''),
            city        = self.get('Home City', ''),
            postcode    = self.get('Home Postcode', ''),
            state       = self.get('Home State', ''),
            country     = self.get('Home Country', '')
        )

    @staticmethod
    def getContainer():
        return UsrObjList

    def addressesActLike(self):
        actLike = True
        for address in filter(None, map(lambda key: self.get(key), ['Address', 'Home Address'])):
            if address.schema and address.schema != 'act':
                actLike = False
        return actLike

    def usernameActLike(self):
        return self.username == self.MYOBID

    def __repr__(self):
        return "<%s> %s | %s | %s | %s " % (self.index, self.email, self.MYOBID, self.role, self.username)

class UsrObjList(ObjList):
    def __init__(self, objects=None, indexer=None):
        super(UsrObjList, self).__init__(objects, indexer=None)
        self._objList_type = 'User'

    def getReportCols(self):
        usrData = ColData_User()
        report_cols = usrData.getReportCols()
        # for exclude_col in ['E-mail','MYOB Card ID','Wordpress Username','Role']:
        #     if exclude_col in report_cols:
        #         del report_cols[exclude_col]

        return report_cols



class CSVParse_User(CSVParse_Flat):

    objectContainer = ImportUser

    def __init__(self, cols=[], defaults = {}, contact_schema = None):
        extra_cols = [  
            # 'ABN', 'Added to mailing list', 'Address 1', 'Address 2', 'Agent', 'Birth Date', 
            # 'book_spray_tan', 'Book-a-Tan Expiry', 'Business Type', 'Canvasser', ''
            # 'post_status'
        ]
        extra_defaults =  OrderedDict([
            # ('post_status', 'publish'),
            # ('last_import', importName),
        ])
        cols = listUtils.combineLists( cols, extra_cols )
        defaults = listUtils.combineOrderedDicts( defaults, extra_defaults )
        super(CSVParse_User, self).__init__(cols, defaults)
        self.contact_schema = contact_schema
        # self.itemIndexer = self.getUsername

    # def getKwargs(self, allData, container, **kwargs):
    #     kwargs = super(CSVParse_User, self).getKwargs(allData, container, **kwargs)
    #     for key in ['E-mail', 'MYOB Card ID', 'username', 'Role']:
    #         assert kwargs[key] is not None
    #     return kwargs

    # def newObject(self, rowcount, row, **kwargs):
    #     for key in ['E-mail', 'MYOB Card ID', 'username', 'Role']:
    #         try:
    #             assert kwargs[key]
    #         except:
    #             kwargs[key] = self.retrieveColFromRow

    def clearTransients(self):
        super(CSVParse_User, self).clearTransients()
        self.roles = OrderedDict()
        self.noroles = OrderedDict()
        self.emails = OrderedDict()
        self.noemails = OrderedDict()
        self.cards = OrderedDict()
        self.nocards = OrderedDict()
        self.usernames = OrderedDict()
        self.nousernames = OrderedDict()

    def sanitizeCell(self, cell):
        return SanitationUtils.sanitizeCell(cell)

    def registerEmail(self, objectData, email):
        self.registerAnything(
            objectData,
            self.emails,
            email,
            singular = False,
            registerName = 'emails'
        )

    def registerNoEmail(self, objectData):
        self.registerAnything(
            objectData,
            self.noemails,
            objectData.index,
            singular = True,
            registerName = 'noemails'
        )

    def registerRole(self, objectData, role):
        self.registerAnything(
            objectData,
            self.roles,
            role,
            singular = False,
            registerName = 'roles'
        )

    def registerNoRole(self, objectData):
        self.registerAnything(
            objectData,
            self.noroles,
            objectData.index,
            singular = True,
            registerName = 'noroles'
        )

    def registerCard(self, objectData, card):
        self.registerAnything(
            objectData,
            self.cards,
            card,
            singular = False,
            registerName = 'cards'
        )

    def registerNoCard(self, objectData):
        self.registerAnything(
            objectData,
            self.nocards,
            objectData.index,
            singular = True,
            registerName = 'nocards'
        )

    def registerUsername(self, objectData, username):
        self.registerAnything(
            objectData,
            self.usernames,
            username,
            singular = False,
            registerName = 'usernames'
        )

    def registerNoUsername(self, objectData):
        self.registerAnything(
            objectData,
            self.nousernames,
            objectData.index,
            singular = True,
            registerName = 'nousernames'
        )

    def registerObject(self, objectData):
        email = objectData.email
        if email and SanitationUtils.stringIsEmail(email) :
            self.registerEmail(objectData, email)
        else:
            if(DEBUG_FLAT): self.registerWarning("invalid email address: %s"%email)
            self.registerNoEmail(objectData)
        
        role = objectData.role
        if role:
            self.registerRole(objectData, role)
        else:
            # self.registerWarning("invalid role: %s"%role)
            self.registerNoRole(objectData)

        card = objectData.MYOBID
        if card and SanitationUtils.stringIsMYOBID(card):
            self.registerCard(objectData, card)
        else:
            self.registerNoCard(objectData)

        username = objectData.username
        if username:
            self.registerUsername(objectData, username)
        else:
            if(DEBUG_FLAT): self.registerWarning("invalid username: %s"%username)
            self.registerNoUsername(objectData)

        super(CSVParse_User, self).registerObject(objectData)

    def getKwargs(self, allData, container, **kwargs):
        kwargs = super(CSVParse_User, self).getKwargs(allData, container, **kwargs)
        if not 'contact_schema' in kwargs.keys():
            kwargs['contact_schema'] = self.contact_schema
        return kwargs

    # def processRoles(self, objectData):
    #     role = objectData.role
    #     if not self.roles.get(role): self.roles[role] = OrderedDict()
    #     self.registerAnything(
    #         objectData,
    #         self.roles[role],
    #         self.getUsername,
    #         singular = True,
    #         registerName = 'roles'
    #     )

    # def processObject(self, objectData):
    #     # objectData.username = self.getMYOBID(objectData)
    #     super(CSVParse_Flat, self).processObject(objectData)
    #     self.processRoles(objectData) 

    # def analyzeRow(self, row, objectData):
    #     objectData = super(CSVParse_Flat, self).analyseRow(row, objectData)
    #     return objectData

if __name__ == '__main__':
    inFolder = "../input/"
    # actPath = os.path.join(inFolder, 'partial act records.csv')
    actPath = os.path.join(inFolder, "200-act-records.csv")
    outFolder = "../output/"
    usrPath = os.path.join(outFolder, 'users.csv')

    usrData = ColData_User()

    # print "import cols", usrData.getImportCols()
    # print "defaults", usrData.getDefaults()

    usrParser = CSVParse_User(
        cols = usrData.getImportCols(),
        defaults = usrData.getDefaults()
    )

    usrParser.analyseFile(actPath)

    usrList = UsrObjList()

    from copy import deepcopy

    for usr in usrParser.objects.values()[:3]:    
        usrList.addObject(usr)
        clone = deepcopy(usr)
        usr['Wordpress Username'] = 'jonno'
        usrList.addObject(clone)
        card_id = usr.MYOBID
        edit_date = usr.get('Edit Date')
        act_date = usr.get('Edited in Act')

    print usrList.tabulate()

    # usrCols = usrData.getUserCols()

    # exportItems(
    #     usrPath,
    #     usrData.getColNames(usrCols),
    #     usrParser.objects.values()
    # )

    # for role, usrs in usrParser.roles.items():
    #     for i, u in enumerate(range(0, len(usrs), usrs_per_file)):
    #         rolPath = os.path.join(outFolder, 'users_%s_%d.csv'%(role,i))

    #         exportItems(
    #             rolPath,
    #             usrData.getColNames(usrCols),
    #             usrs.values()[u:u+usrs_per_file]
    #         )
        
