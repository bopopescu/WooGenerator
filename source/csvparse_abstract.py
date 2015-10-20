import csv, inspect
from collections import OrderedDict
import pprint

DEBUG = True
DEBUG_PARSER = True

class Registrar:
    messages = OrderedDict()
    errors = OrderedDict()

    def __init__(self):
        self.objectIndexer = id
        self.conflictResolver = self.passiveResolver

    def resolveConflict(self, new, old, index, registerName = ''):
        self.registerError("Object [index: %s] already exists in register %s"%(index, registerName))

    def getObjectRowcount(self, objectData):
        return objectData.getRowcount()

    def passiveResolver(*args):
        pass

    def exceptionResolver(self, new, old, index, registerName = ''):
        raise Exception("could not register %s in %s. Duplicate key" % (str(new), registerName) )

    @classmethod
    def stringAnything(self, index, thing, delimeter):
        return "%31s %s %s" % (index, delimeter, thing)

    @classmethod
    def printAnything(self, index, thing, delimeter):
        print Registrar.stringAnything(index, thing, delimeter)

    def registerAnything(self, thing, register, indexer = None, resolver = None, singular = True, registerName = ''):
        if resolver is None: resolver = self.conflictResolver
        if indexer is None: indexer = self.Indexer
        index = None
        try:
            if callable(indexer):
                index = indexer(thing)
            else: 
                index = indexer
            assert index.__hash__, "Index must be hashable"
            assert index == index, "index must support eq"
        except AssertionError as e:
            raise Exception("Indexer [%s] produced invalid index: %s | %s" % (indexer.__name__, repr(index), str(e)))
        else:
            # if not register:
            #     register = OrderedDict()
            if singular:
                if index not in register:
                    register[index] = thing
                else:
                    resolver(thing, register[index], index, registerName)
            else:
                if index not in register:
                    register[index] = []
                register[index].append(thing)
        # print "registered", thing

    def registerError(self, error, data = None):
        if data:
            try:
                index = data.getIndex()
            except:
                index = data
        else:
            index = ""
        error_string = str(error)
        if DEBUG: Registrar.printAnything(index, error, '!')
        self.registerAnything(
            error_string, 
            self.errors, 
            index, 
            singular = False,
            registerName = 'errors'
        )

    def registerMessage(self, message, source=None):
        if source is None:
            source = debugUtils.getCallerProcedure()
        if DEBUG: Registrar.printAnything(source, message, ' ')
        self.registerAnything(
            message,
            self.messages,
            source,
            singular = False,
            registerName = 'messages'
        )

class ImportObject(OrderedDict, Registrar):
    """docstring for ImportObject"""
    def __init__(self, data, rowcount, row):
        super(ImportObject, self).__init__(data)
        Registrar.__init__(self)
        self['rowcount'] = rowcount
        self.row = row
        self.initialized = False

    def getRowcount(self):
        return self['rowcount']

    def getRow(self):
        return self.row

    def getIndex(self):
        return self.getRowcount()

    def getTypeName(self):
        return type(self).__name__ 

    def getIdentifierDelimeter(self):
        return ""

    def getIdentifier(self):
        return Registrar.stringAnything( self.getIndex(), "<%s>" % self.getTypeName(), self.getIdentifierDelimeter() )

    def __str__(self):
        return "%s <%s>" % (self.getIndex(), self.getTypeName())

class listUtils:
    @staticmethod
    def combineLists(a, b):
        if not a:
            return b if b else []
        if not b: return a
        return list(set(a) | set(b))

    @staticmethod
    def combineOrderedDicts(a, b):
        if not a:
            return b if b else OrderedDict()
        if not b: return a
        c = OrderedDict(b.items())
        for key, value in a.items():
            c[key] = value
        return c

    @staticmethod
    def filterUniqueTrue(a):
        b = []
        for i in a:
            if i and i not in b:
                b.append(i)
        return b

class debugUtils:
    @staticmethod
    def getProcedure():
        return inspect.stack()[1][3]

    @staticmethod
    def getCallerProcedure():
        return inspect.stack()[2][3]

class CSVParse_Base(object, Registrar):
    """docstring for CSVParse_Base"""

    def __init__(self, cols, defaults ):
        super(CSVParse_Base, self).__init__()
        Registrar.__init__(self)

        extra_cols = []
        extra_defaults = OrderedDict()

        self.cols = listUtils.combineLists( cols, extra_cols )
        self.defaults = listUtils.combineOrderedDicts( defaults, extra_defaults )
        self.pp = pprint.PrettyPrinter(indent=2, depth=2)
        self.indexSingularity = True
        self.objectIndexer = self.getObjectRowcount
        self.objectContainer = ImportObject
        self.clearTransients()

    def clearTransients(self):
        self.indices = OrderedDict()
        self.objects = OrderedDict()

    def registerObject(self, objectData):
        self.registerAnything(
            objectData, 
            self.objects, 
            self.objectIndexer,
            singular = True,
            registerName = 'objects'
        )

    def analyseHeader(self, row):
        for col in self.cols:
            try:
                self.indices[col] = row.index(col)
                if DEBUG: print "indices [%s] = %d" % (col, row.index(col))
            except ValueError as e:
                self.registerError('Could not find index of '+str(col)+" | "+str(e) )

    def retrieveColFromRow(self, col, row):
        # if DEBUG_PARSER: print "retrieveColFromRow | col: ", col
        try:
            index = self.indices[col]
        except KeyError as e:
            self.registerError('No such column'+str(col)+' | '+str(e))
            return None
        try:
            # if DEBUG: print "row [%s] = %s" % (index, row[index])
            return row[index]
        except Exception as e:
            self.registerError('Could not retrieve '+str(col)+' from row['+str(index)+'] | '+str(e))
            return None

    def sanitizeCell(self, cell):
        return cell   
             
    def getRowData(self, row):
        rowData = OrderedDict()
        for col in self.cols:
            retrieved = self.retrieveColFromRow(col, row)
            if retrieved is not None and retrieved is not '': 
                rowData[col] = self.sanitizeCell(retrieved)
        return rowData

    def newObject(self, rowcount, row):
        self.registerMessage( '{} | {}'.format(rowcount, row) )
        defaultData = OrderedDict(self.defaults.items())
        self.registerMessage( "defaultData: {}".format(defaultData) )
        rowData = self.getRowData(row)
        self.registerMessage( "rowData: {}".format(rowData) )
        allData = listUtils.combineOrderedDicts(rowData, defaultData)
        self.registerMessage( "allData: {}".format(allData) )
        return self.objectContainer(allData, rowcount, row)

    def initializeObject(self, objectData):
        pass

    def processObject(self, objectData):
        pass

    # def processObject(self, objectData):
        # self.initializeObject(objectData)
        # objectData.initialized = True;
        # self.processObject(objectData)
        # self.registerObject(objectData)

    def analyseFile(self, fileName):
        self.registerMessage("Analysing file: {}".format(fileName))
        # self.clearTransients()

        with open(fileName) as filePointer:
            csvreader = csv.reader(filePointer, strict=True)
            objects = []
            for rowcount, row in enumerate(csvreader):
                if not self.indices :
                    self.analyseHeader(row)
                    continue
                try:
                    objectData = self.newObject( rowcount, row )
                except AssertionError as e:
                    self.registerError("could not create new object: {}".format(e), rowcount)
                    continue
                else:
                    self.registerMessage("%s CREATED" % objectData.getIdentifier() )
                try:
                    self.processObject(objectData) 
                except AssertionError as e:
                    self.registerError("could not process new object: {}".format(e), objectData)
                    continue
                try:
                    self.registerObject(objectData)
                except AssertionError as e:
                    self.registerError("could not register new object: {}".format(e), objectData)
                    continue
                            
            return objects
        return None

    def getObjects(self):
        return self.objects
