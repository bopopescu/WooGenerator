"""
CSVParse Abstract
Abstract base classes originally intended to be used for parsing and storing CSV data in a
convenient accessible dictionary structure, but modified to parse data in other formats.
Parse classes store Import objects in their internal structure and output ObjList instances
for easy analyis.
Here be dragons. Some of the design decisions are pretty bizarre, so please have a full read
through before changing anything. Sorry about that.
"""

from collections import OrderedDict
from tabulate import tabulate
import unicodecsv
from copy import deepcopy, copy
from pprint import pformat
import re

from woogenerator.utils import listUtils, SanitationUtils, Registrar, ProgressCounter
from woogenerator.utils import UnicodeCsvDialectUtils

BLANK_CELL = ''

class ObjList(list, Registrar):
    # supports_tablefmt = True
    objList_type = 'objects'
    supported_type = object

    def __init__(self, objects=None, indexer=None):
        super(ObjList, self).__init__()
        Registrar.__init__(self)
        if self.DEBUG_MRO:
            self.registerMessage('ObjList')
        self.indexer = indexer if indexer else (lambda x: x.index)
        self.supported_type = ImportObject
        # self._objList_type = 'objects'
        # self._objects = []
        self.indices = []
        if objects:
            self.extend(objects)

    @property
    def objects(self):
        return self[:]

    # @property
    # def objList_type(self):
    #     return self._objList_type

    # @property
    # def indices(self):
    #     return self._indices


    # def __len__(self):
    #     return len(self.objects)

    def append(self, objectData):
        #re-implemeny by overriding .append()?
        try:
            assert issubclass(objectData.__class__, self.supported_type), \
                "object must be subclass of %s not %s" % \
                    (str(self.supported_type.__name__), str(objectData.__class__))
        except Exception as e:
            self.registerError(e)
            return
        index = self.indexer(objectData)
        if(index not in self.indices):
            super(ObjList, self).append(objectData)
            self.indices.append(index)

    def extend(self, objects):
        #re-implemeny by overriding .extend()?
        for obj in objects:
            self.append(obj)

    def getKey(self, key):
        values = listUtils.filterUniqueTrue([
            obj.get(key) for obj in self.objects
        ])

        if values:
            return values[0]

    def getSanitizer(self, tablefmt=None):
        if tablefmt == 'html':
            return SanitationUtils.sanitizeForXml
        else:
            return SanitationUtils.sanitizeForTable

    def tabulate(self, cols=None, tablefmt=None, highlight_rules=None):
        objs = self.objects
        sanitizer = self.getSanitizer(tablefmt)
        # sanitizer = (lambda x: str(x)) if tablefmt == 'html' else SanitationUtils.makeSafeOutput
        if objs:
            if not cols: cols = self.reportCols
            assert isinstance(cols, dict), \
                "cols should be a dict, found %s instead: %s" % (type(cols), repr(cols))
            header = [self.objList_type]
            for col in cols.keys():
                header += [col]
            table = []
            for obj in objs:
                row = [obj.identifier]

                # process highlighting rules
                if highlight_rules:
                    classes = []
                    for highlight_class, rule in highlight_rules:
                        if rule(obj):
                            classes.append(highlight_class)
                    row = [" ".join(classes)] + row

                for col in cols.keys():
                    # if col == 'Address':
                    #     print repr(str(obj.get(col))), repr(sanitizer(obj.get(col)))
                    row += [ sanitizer(obj.get(col) )or ""]
                    try:
                        SanitationUtils.coerceUnicode(row[-1])
                    except:
                        Registrar.registerWarning("can't turn row into unicode: %s" % SanitationUtils.coerceUnicode(row))

                table += [row]
                # table += [[obj.index] + [ sanitizer(obj.get(col) )or "" for col in cols.keys()]]
            # print "table", table
            # SanitationUtils.safePrint(table)
            # return SanitationUtils.coerceUnicode(tabulate(table, headers=header, tablefmt=tablefmt))
            table_str = (tabulate(table, headers=header, tablefmt=tablefmt))
            if highlight_rules and tablefmt=='html':
                # print "table pre:", (table_str.encode('utf8'))
                table_str = re.sub(r'<tr><td>([^<]*)</td>',r'<tr class="\1">',table_str)
                # also delete first row
                table_str = re.sub(r'<tr><th>\s*</th>', r'<tr>', table_str)
                # print "table post:", (table_str.encode('utf8'))

            return table_str
            # return table.encode('utf8')
        else:
            Registrar.registerWarning("cannot tabulate Objlist: there are no objects")
            return ""

    def exportItems(self, filePath, colNames, dialect = None, encoding="utf8"):
        assert filePath, "needs a filepath"
        assert colNames, "needs colNames"
        assert self.objects, "meeds items"
        with open(filePath, 'w+') as outFile:
            if dialect is None:
                csvdialect = UnicodeCsvDialectUtils.act_out
            else:
                csvdialect = UnicodeCsvDialectUtils.get_dialect_from_suggestion(dialect)
            # unicodecsv.register_dialect('act_out', delimiter=',', quoting=unicodecsv.QUOTE_ALL, doublequote=False, strict=True, quotechar="\"", escapechar="`")
            if self.DEBUG_ABSTRACT:
                self.registerMessage(UnicodeCsvDialectUtils.dialect_to_str(csvdialect))
            dictwriter = unicodecsv.DictWriter(
                outFile,
                dialect=csvdialect,
                fieldnames=colNames.keys(),
                encoding=encoding,
                extrasaction='ignore',
            )
            dictwriter.writerow(colNames)
            dictwriter.writerows(self.objects)
        self.registerMessage("WROTE FILE: %s" % filePath)

    reportCols = OrderedDict([
        ('_row',{'label':'Row'}),
        ('index',{})
    ])

    def getReportCols(self):
        e = DeprecationWarning("use .reportCols instead of .getReportCols()")
        self.registerError(e)
        return self.reportCols

    @classmethod
    def getBasicCols(cls):
        return cls.reportCols


class ImportObject(OrderedDict, Registrar):
    container = ObjList
    rowcountKey = 'rowcount'
    rowKey = '_row'

    def __init__(self, *args, **kwargs):
        if self.DEBUG_MRO:
            self.registerMessage('ImportObject')
        data = args[0]
        # Registrar.__init__(self)
        if self.DEBUG_PARSER:
            self.registerMessage('About to register child,\n -> DATA: %s\n -> KWARGS: %s' \
                % (pformat(data), pformat(kwargs)) )

        rowcount = kwargs.pop(self.rowcountKey, None)
        if rowcount is not None:
            data[self.rowcountKey] = rowcount
        OrderedDict.__init__(self, **data)
        row = kwargs.pop('row', None)

        # if not self.get('rowcount'): self['rowcount'] = 0
        # assert isinstance(self['rowcount'], int), "must specify integer rowcount not %s" % (self['rowcount'])
        if row is not None:
            self._row = row
        else:
            if not '_row' in self.keys():
                self['_row'] = []
        super(ImportObject, self).__init__(*args, **kwargs)

    def __hash__(self):
        return hash(self.index)

    @property
    def row(self): return self._row

    @property
    def rowcount(self): return self.get(self.rowcountKey, 0)

    @property
    def index(self): return self.rowcount

    @property
    def identifierDelimeter(self): return ""

    # @classmethod
    # def getNewObjContainer(cls):
    #     e = DeprecationWarning("user .container instead of .getNewObjContainer()")
    #     self.registerError(e)
    #     return cls.container
    #     # return ObjList

    @property
    def typeName(self):
        return type(self).__name__

    def getTypeName(self):
        e = DeprecationWarning("use .typeName instead of .getTypeName()")
        self.registerError(e)
        return self.typeName

    def getIdentifierDelimeter(self):
        e = DeprecationWarning("use .identifierDelimeter instead of .getIdentifierDelimeter()")
        self.registerError(e)
        return self.identifierDelimeter

    @property
    def identifier(self):
        index =  self.index
        if self.DEBUG_ABSTRACT:
            self.registerMessage("index: %s" % repr(index))
        typeName = self.typeName
        if self.DEBUG_ABSTRACT:
            self.registerMessage("typeName %s" % repr(typeName))
        identifierDelimeter = self.identifierDelimeter
        if self.DEBUG_ABSTRACT:
            self.registerMessage("identifierDelimeter %s" % repr(identifierDelimeter))
        return self.stringAnything( index, "<%s>" % typeName, identifierDelimeter )

    def getIdentifier(self):
        e = DeprecationWarning("use .identifier instead of .getIdentifier()")
        self.registerError(e)
        return self.identifier
        # return Registrar.stringAnything( self.index, "<%s>" % self.getTypeName(), self.getIdentifierDelimeter() )

    def getCopyArgs(self):
        return {
            'rowcount': self.rowcount,
            'row':self.row[:]
        }

    def containerize(self):
        """ put self in a container by itself """
        return self.container([self])

    def __getstate__(self): return self.__dict__
    def __setstate__(self, d): self.__dict__.update(d)
    def __copy__(self):
        items = copy(self.items())
        print "doing a copy on %s \nwith items %s \nand copyargs %s" % (
            repr(self.__class__),
            pformat(items),
            self.getCopyArgs(),
        )
        return self.__class__(
            copy(OrderedDict(self.items())),
            **self.getCopyArgs()
        )
    def __deepcopy__(self, memodict=None):
        if not hasattr(Registrar, 'deepcopyprefix'):
            Registrar.deepcopyprefix = '>'
        Registrar.deepcopyprefix = '=' + Registrar.deepcopyprefix
        items = deepcopy(self.items())
        # print Registrar.deepcopyprefix, "doing a deepcopy on %s \nwith items %s \nand copyargs %s, \nmemodict: %s" % (
        #     repr(self.__class__),
        #     pformat(items),
        #     self.getCopyArgs(),
        #     pformat(memodict)
        # )
        Registrar.deepcopyprefix = Registrar.deepcopyprefix[1:]
        return self.__class__(
            deepcopy(OrderedDict(items)),
            **self.getCopyArgs()
        )

    def __str__(self):
        return "%10s <%s>" % (self.identifier, self.typeName)

    def __repr__(self):
        return self.__str__()

    def __cmp__(self, other):
        if other == None:
            return -1
        if not isinstance(other, ImportObject):
            return -1
        return cmp(self.rowcount, other.rowcount)

class CSVParse_Base(Registrar):
    objectContainer = ImportObject

    def __init__(self, cols, defaults, **kwargs):
        # super(CSVParse_Base, self).__init__()
        # Registrar.__init__(self)
        if self.DEBUG_MRO:
            self.registerMessage('CSVParse_Base')

        extra_cols = []
        extra_defaults = OrderedDict()

        self.limit = kwargs.pop('limit', None)
        self.cols = listUtils.combineLists( cols, extra_cols )
        self.defaults = listUtils.combineOrderedDicts( defaults, extra_defaults )
        self.objectIndexer = self.getObjectRowcount
        self.clearTransients()
        self.source = kwargs.get('source')

    def __getstate__(self): return self.__dict__
    def __setstate__(self, d): self.__dict__.update(d)

    def clearTransients(self):
        if self.DEBUG_MRO:
            self.registerMessage(' ')
        self.indices = OrderedDict()
        self.objects = OrderedDict()
        self.rowcount = 1

    def registerObject(self, objectData):
        if self.DEBUG_MRO:
            self.registerMessage(' ')
        self.registerAnything(
            objectData,
            self.objects,
            self.objectIndexer,
            singular = True,
            registerName = 'objects'
        )

    def analyseHeader(self, row):
        # if self.DEBUG_PARSER: self.registerMessage( 'row: %s' % unicode(row) )
        sanitizedRow = [self.sanitizeCell(cell) for cell in row]
        for col in self.cols:
            sanitizedCol = self.sanitizeCell(col)
            if sanitizedCol in sanitizedRow:
                self.indices[col] = sanitizedRow.index(sanitizedCol)
                continue
            if self.indices[col]:
                if self.DEBUG_ABSTRACT:
                    self.registerMessage( "indices [%s] = %s" % (col, self.indices.get(col)))
            else:
                self.registerError('Could not find index of %s -> %s in %s' % (repr(col), repr(sanitizedCol), repr(sanitizedRow)) )
        if not self.indices:
            raise UserWarning("could not find any indices")

    def retrieveColFromRow(self, col, row):
        # if self.DEBUG_PARSER: print "retrieveColFromRow | col: ", col
        try:
            index = self.indices[col]
        except KeyError as e:
            if col in self.defaults:
                return self.defaults[col]
            self.registerError('No default for column '+str(col)+' | '+str(e) + ' ' + unicode(self.defaults))
            return None
        try:
            if self.DEBUG_ABSTRACT: self.registerMessage(u"row [%3d] = %s" % (index, repr(row[index])))
            #this may break shit
            return row[index]
        except Exception as e:
            self.registerWarning('Could not retrieve '+str(col)+' from row['+str(index)+'] | '+\
                                 str(e) +' | '+repr(row))
            return None

    def sanitizeCell(self, cell):
        return cell

    def getParserData(self, **kwargs):
        """
        gets data for the parser (in this case from row, specified in kwargs)
        generalized from getRowData
        """
        if self.DEBUG_MRO:
            self.registerMessage(' ')
        row = kwargs.get('row', [])
        rowData = OrderedDict()
        for col in self.cols:
            retrieved = self.retrieveColFromRow(col, row)
            if retrieved is not None and unicode(retrieved) is not u"":
                rowData[col] = self.sanitizeCell(retrieved)
        return rowData

    def getMandatoryData(self, **kwargs):
        mandatoryData = OrderedDict()
        if self.source:
            mandatoryData['source'] = self.source
        return mandatoryData

    def getNewObjContainer(self, allData, **kwargs):
        if kwargs:
            pass # gets rid of unused argument error
        if self.DEBUG_MRO:
            self.registerMessage(' ')
        return self.objectContainer

    def getKwargs(self, allData, container, **kwargs):
        return kwargs

    def newObject(self, rowcount, **kwargs):
        """
        An import object is created with two pieces of information:
         - data: a dict containing the raw data in the importObject as a dictionary
         - kwargs: extra arguments passed to subclass __init__s to initialize the object
        Subclasses of CSVParse_Base override the getKwargs and getParserData methods
        so that they can supply their own arguments to an object's initialization
        """
        if self.DEBUG_PARSER: self.registerMessage( 'rowcount: {} | kwargs {}'.format(rowcount, kwargs) )
        kwargs['row'] = kwargs.get('row', [])
        kwargs['rowcount'] = rowcount
        defaultData = OrderedDict(self.defaults.items())
        if self.DEBUG_PARSER: self.registerMessage( "defaultData: {}".format(defaultData) )
        parserData = self.getParserData(**kwargs)
        if self.DEBUG_PARSER: self.registerMessage( "parserData: {}".format(parserData) )
        # allData = listUtils.combineOrderedDicts(parserData, defaultData)
        allData = listUtils.combineOrderedDicts(defaultData, parserData)
        mandatoryData = self.getMandatoryData(**kwargs)
        allData = listUtils.combineOrderedDicts(allData, mandatoryData)
        if self.DEBUG_PARSER: self.registerMessage( "allData: {}".format(allData) )
        container = self.getNewObjContainer(allData, **kwargs)
        if self.DEBUG_PARSER: self.registerMessage("container: {}".format(container.__name__))
        kwargs = self.getKwargs(allData, container, **kwargs)
        if self.DEBUG_PARSER: self.registerMessage("kwargs: {}".format(kwargs))
        objectData = container(allData, **kwargs)
        return objectData

    # def initializeObject(self, objectData):
    #     pass

    def processObject(self, objectData):
        pass

    # def processObject(self, objectData):
        # self.initializeObject(objectData)
        # objectData.initialized = True;
        # self.processObject(objectData)
        # self.registerObject(objectData)

    def analyseRows(self, unicode_rows, fileName="rows", limit=None):
        if limit and isinstance(limit, int):
            unicode_rows = list(unicode_rows)[:limit]
        if self.DEBUG_PROGRESS:

            # last_print = time()
            rows = []
            try:
                for row in unicode_rows:
                    rows.append(row)
            except Exception, e:
                raise Exception("could not append row %d, %s: \n\t%s" % (len(rows), str(e), repr(rows[-1:])))
            rowlen = len(rows)
            self.progressCounter = ProgressCounter(rowlen)
            unicode_rows = rows

        for unicode_row in (unicode_rows):
            self.rowcount += 1

            if limit and self.rowcount > limit:
                break
            if self.DEBUG_PROGRESS:
                self.progressCounter.maybePrintUpdate(self.rowcount)
                # now = time()
                # if now - last_print > 1:
                #     last_print = now
                #     print "%d of %d rows processed" % (self.rowcount, rowlen)

            if unicode_row:
                non_unicode = filter(
                    lambda unicode_cell: not isinstance(unicode_cell, unicode) if unicode_cell else False,
                    unicode_row
                )
                assert not non_unicode, "non-empty cells must be unicode objects, {}".format(repr(non_unicode))

            if not any(unicode_row):
                continue

            if not self.indices :
                self.analyseHeader(unicode_row)
                continue
            try:
                objectData = self.newObject( self.rowcount, row=unicode_row )
            except UserWarning as e:
                self.registerWarning("could not create new object: {}".format(e), "%s:%d" % (fileName, self.rowcount))
                continue
            else:
                if self.DEBUG_PARSER:
                    self.registerMessage("%s CREATED" % objectData.identifier )
            try:
                self.processObject(objectData)
                if self.DEBUG_PARSER:
                    self.registerMessage("%s PROCESSED" % objectData.identifier )
            except UserWarning as e:
                self.registerError("could not process new object: {}".format(e), objectData)
                continue
            try:
                self.registerObject(objectData)
                if self.DEBUG_PARSER:
                    self.registerMessage("%s REGISTERED" % objectData.identifier )
                    self.registerMessage("%s" % objectData.__repr__())

            except UserWarning as e:
                self.registerWarning("could not register new object: {}".format(e), objectData)
                continue
        if self.DEBUG_PARSER:
            self.registerMessage("Completed analysis")

    def analyseStream(self, byte_file_obj, streamName=None, encoding=None, dialect_suggestion=None, limit=None):
        """ may want to revert back to this commit if things break:
        https://github.com/derwentx/WooGenerator/commit/c4fabf83d5b4d1e0a4d3ff755cd8eadf1433d253 """

        if hasattr(self, 'rowcount') and self.rowcount > 1:
            raise UserWarning('rowcount should be 0. Make sure clearTransients is being called on ancestors')
        if encoding is None:
            encoding = "utf8"

        if streamName is None:
            if hasattr(byte_file_obj, 'name'):
                streamName = byte_file_obj.name
            else:
                streamName = 'stream'

        if self.DEBUG_PARSER:
            self.registerMessage("Analysing stream: {0}, encoding: {1}".format(streamName, encoding))

        # I can't imagine this having any problems
        byte_sample = SanitationUtils.coerceBytes(byte_file_obj.read(1000))
        byte_file_obj.seek(0)

        if dialect_suggestion:
            csvdialect = UnicodeCsvDialectUtils.get_dialect_from_suggestion(dialect_suggestion)
        else:
            csvdialect = unicodecsv.Sniffer().sniff(byte_sample)
            assert \
                csvdialect.delimiter == ',' and isinstance(csvdialect.delimiter, str)
            # try:
            #     csvdialect = unicodecsv.Sniffer().sniff(byte_sample)
            #     assert csvdialect.delimiter ==',', "sanity test"
            #     assert isinstance(csvdialect.delimiter, str)
            # except AssertionError:
            #     csvdialect = UnicodeCsvDialectUtils.default_dialect

        if self.DEBUG_PARSER:
            self.registerMessage(UnicodeCsvDialectUtils.dialect_to_str(csvdialect))

        unicodecsvreader = unicodecsv.reader(
            byte_file_obj,
            dialect=csvdialect,
            encoding=encoding,
            strict=True
        )
        return self.analyseRows(unicodecsvreader, fileName=streamName, limit=limit)

    def analyseFile(self, fileName, encoding=None, dialect_suggestion=None, limit=None):
        with open(fileName, 'rbU') as byte_file_obj:
            return self.analyseStream(
                byte_file_obj,
                streamName=fileName,
                encoding=encoding,
                dialect_suggestion=dialect_suggestion,
                limit=limit
            )
        return None

    @classmethod
    def translateKeys(cls, objectData, key_translation):
        translated = OrderedDict()
        for col, translation in key_translation.items():
            if col in objectData:
                translated[translation] = objectData[col]
        return translated

    def analyseWpApiObj(self, apiData):
        raise NotImplementedError()

    def getObjects(self):
        e = DeprecationWarning("Use .objects instead of .getObjects()")
        self.registerError(e)
        return self.objects

    def getObjList(self):
        listClass = self.objectContainer.container
        # listClass = self.objectContainer.getNewObjContainer()
        objlist = listClass(self.objects.values())
        return objlist

    def tabulate(self, cols=None, tablefmt=None):
        objlist = self.getObjList()
        return SanitationUtils.coerceBytes(objlist.tabulate(cols, tablefmt))


    @classmethod
    def printBasicColumns(cls, objects):
        obj_list = cls.objectContainer.container()
        for _object in objects:
            obj_list.append(_object)

        cols = cls.objectContainer.container.getBasicCols()

        SanitationUtils.safePrint( obj_list.tabulate(
            cols,
            tablefmt = 'simple'
        ))
#
# if __name__ == '__main__':
#     inFolder = "../input/"
#     # actPath = os.path.join(inFolder, 'partial act records.csv')
#     actPath = os.path.join(inFolder, "500-act-records.csv")
#     outFolder = "../output/"
#     usrPath = os.path.join(outFolder, 'users.csv')
#
#     usrData = ColData_User()
#
#     # print "import cols", usrData.getImportCols()
#     # print "defaults", usrData.getDefaults()
#
#     usrParser = CSVParse_Base(
#         cols = usrData.getImportCols(),
#         defaults = usrData.getDefaults()
#     )
#
#     usrParser.analyseFile(actPath)
#
#     SanitationUtils.safePrint( usrParser.tabulate(cols = usrData.getReportCols()))
#     print ( usrParser.tabulate(cols = usrData.getReportCols()))
#
#     for usr in usrParser.objects.values()[:3]:
#         pprint(OrderedDict(usr))