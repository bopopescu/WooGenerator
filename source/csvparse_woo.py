from csvparse_gen import CSVParse_Gen, importGenProduct, ImportGenTaxo
from collections import OrderedDict
import re
import time
import datetime
import json

def findAllImages(imgString):
    assert type(imgString) == str, "param must be a string not %s"% type(imgString)
    return re.findall(r'\s*([^.|]*\.[^.|\s]*)(?:\s*|\s*)',imgString)

def findAllTokens(tokenString, delim = "|"):
    assert type(tokenString) == str, "param must be a string not %s"% type(tokenString)
    return re.findall(r'\s*(\b[^\s.|]+\b)\s*', tokenString )

def findallDollars(instring):
    assert type(instring) == str, "param must be a string not %s"% type(instring)
    return re.findall("\s*\$([\d,]+\.?\d*)", instring)

def findallPercent(instring):
    assert type(instring) == str, "param must be a string not %s"% type(instring)
    return re.findall("\s*(\d+\.?\d*)%", instring)

def datetotimestamp(datestring):
    assert type(datestring) == str, "param must be a string not %s"% type(datestring)
    return int(time.mktime(datetime.datetime.strptime(datestring, "%d/%m/%Y").timetuple()))

DEBUG_WOO = True

class ImportWooMixin:
    """docstring for ImportWooMixin"""
    attributes = OrderedDict()
    imglistKey = 'imglist'
    # attributesKey = 'attributes'

    def registerImage(self, image):
        assert type(image) == str
        thisImages = self.getImages()
        if image not in thisImages:
            thisImages.append(image)
            parent = self.getParent()
            parentImages = parent.getImages()
            if not parentImages:
                parent.registerImage(image)

    def getImages(self):
        return self.get(self.imglistKey, [])

    def registerAttribute(self, attr, val):
        var = self.isItem() and self.isVariation()
        attrs = self.getAttributes()
        if attr not in attrs:
            attrs[attr] = {
                'values':[val],
                'visible':1,
                'variation':0
            }
            if var:
                attrs[attr]['default'] = val
        elif val not in attrs[attr]['values'] :
            attrs[attr]['values'].append(val)
        if var:
            if not attrs[attr]['default']:
                attrs[attr]['default'] = val
            attrs[attr]['variation'] = 1

    def getAttributes(self):
        try:
            return self.attributes
        except:
            return OrderedDict()

class ImportWooProduct(importGenProduct):
    """docstring for ImportWooProduct"""

    def __init__(self, *args):
        super(ImportWooProduct, self).__init__(*args)
        self[self.catlistKey] = OrderedDict()
        self[self.attributesKey] = OrderedDict()

    def isFirstOrder(): return False;
    def isVariable(): return False;
    def isVariation(): return False;

    def registerCategory(self, catData):
        self.registerAnything(
            catData,
            self.categories,
            # indexer = self.getSum,
            indexer = catData.getRowcount,
            singular = True,
            resolver = self.passiveResolver,
            registerName = 'product categories'
        )

    def joinCategory(self, catData):
        self.registerCategory(catData)
        catData.registerMember(self)

    def getCategories(self):
        return self.categories

    def getAttributes(self):
        return self.get('attributes', OrderedDict())

    def getNameDelimeter(self):
        return ' \xe2\x80\x94 '

class ImportWooSimpleProduct(ImportWooProduct):
    """docstring for ImportWooSimpleProduct"""
    def __init__(self, *args):
        super(ImportWooSimpleProduct, self).__init__(*args)
        self['prod_type'] = 'simple'

    def isFirstOrder(): return True; 

class ImportWooVariableProduct(ImportWooProduct):
    """docstring for ImportWooVariableProduct"""

    def __init__(self, *args):
        super(ImportWooVariableProduct, self).__init__(*args)
        self['prod_type'] = 'variable'
        self[self.variationsKey] = OrderedDict()

    def registerVariation(self, varData):
        self.registerAnything(
            varData,
            self.variations,
            indexer = varData.getCodesum,
            singular = True,
            registerName = "product variations"
        )

    def getVariations(self):
        return self.variations

    def isFirstOrder(): return True; 
    def isVariable(): return True; 

class ImportWooVariation(ImportWooProduct):
    """docstring for ImportWooVariation"""
    def __init__(self, *args):
        super(ImportWooVariation, self).__init__(*args)
        self['prod_type'] = 'variable-instance'

    def registerParentProduct(self, parentData):
        self.parentProduct = parentData
        self['parent_SKU'] = parentData.getCodesum()

    def joinVariable(self, parentData):
        self.registerProduct(parentData)
        parentData.registerVariation(self)

    def getParentProduct(self):
        return self.parentProduct

    def isVariation(): return True;        

class ImportWooCompositeProduct(ImportWooProduct):
    """docstring for ImportWooVariableProduct"""
    def __init__(self, *args):
        super(ImportWooSimpleProduct, self).__init__(*args)
        self['prod_type'] = 'composite'

    def isFirstOrder(): return True; 

class ImportWooGroupedProduct(ImportWooProduct):
    """docstring for ImportWooGroupedProduct"""
    def __init__(self, *args):
        super(ImportWooGroupedProduct, self).__init__(*args)
        self['prod_type'] = 'grouped'

    def isFirstOrder(): return True; 

class ImportWooBundledProduct(ImportWooProduct):
    """docstring for ImportWooBundledProduct"""
    def __init__(self, *args):
        super(ImportWooBundledProduct, self).__init__(*args)
        self['prod_type'] = 'bundle'

    def isFirstOrder(): return True; 

class ImportWooCategory(ImportGenTaxo):
    """docstring for ImportWooCategory"""
    productsKey = 'products'

    def __init__(self, *args):
        super(ImportWooCategory, self).__init__(*args) 
        self[self.productsKey] = OrderedDict()
        self[self.attributesKey] = OrderedDict()

    def registerMember(self, itemData):
        self.registerAnything(
            itemData,
            self.members,
            # indexer = self.getSum,
            indexer = itemData.getRowcount,
            singular = True,
            resolver = self.passiveResolver,
            registerName = 'product categories'
        )

    def getMembers(self, itemData):
        return self.members

class CSVParse_Woo(CSVParse_Gen):
    """docstring for CSVParse_Woo"""

    prod_containers = {
        'S': ImportWooSimpleProduct,
        'V': ImportWooVariableProduct,
        'I': ImportWooVariation,
        'C': ImportWooCompositeProduct,
        'G': ImportWooGroupedProduct,
        'B': ImportWooBundledProduct,
    }

    # prod_types = {
    #     'S': 'simple',
    #     'V': 'variable',
    #     'I': 'variable-instance',
    #     'C': 'composite',
    #     'G': 'grouped',
    #     'B': 'bundle',
    # }

    def __init__(self, cols, defaults, schema="", importName="", \
                taxoSubs={}, itemSubs={}, taxoDepth=2, itemDepth=2, metaWidth=2,\
                dprcRules={}, dprpRules={}, specials={}):
        extra_cols = [ 'PA', 'VA', 'weight', 'length', 'width', 'height', 
                    'stock', 'stock_status', 'Images', 'HTML Description',
                    'post_status']

        extra_defaults =  OrderedDict([
            ('post_status', 'publish'),
            # ('last_import', importName),
        ])

        extra_taxoSubs = OrderedDict([
            ('Generic Literature', 'Marketing > Literature'),
            ('Generic Signage', 'Marketing > Signage'),
            ('Generic ', ''),
            ('Shimmerz for Hair', 'Shimmerz for Hair'),
            ('Sqiffy Accessories', 'Sqiffy'),
            ('Sticky Soul Accessories', 'Sticky Soul'),
            ('Tanning Advantage ', ''),   
            ('Assorted ', ''),
            ('My Tan Apparel', 'My Tan Dress'),
            # ('Shimmerz for Hair', 'Tanning Accessories > Shimmerz for Hair'),
            # ('Sqiffy Accessories', 'Tanning Accessories > Sqiffy'),
            # ('EzeBreathe', 'Tanning Accessories > EzeBreathe'),
            # ('My Tan', 'Tanning Accessories > My Tan'),
            # ('Tan Sleeper', 'Tanning Accessories > Tan Sleeper'),
            # ('Tanning Advantage Application Equipment', 'Equipment > Application Equipment'),   
            # ('Generic Application Equipment', 'Equipment > Application Equipment'),
            # ('Generic Tanning Booths', 'Equipment > Tanning Booths'),
        ])

        extra_itemSubs = OrderedDict()

        if not importName: importName = time.strftime("%Y-%m-%d %H:%M:%S")
        cols = self.combineLists( cols, extra_cols )
        defaults = self.combineOrderedDicts( defaults, extra_defaults )
        taxoSubs = self.combineOrderedDicts( taxoSubs, extra_taxoSubs )
        itemSubs = self.combineOrderedDicts( itemSubs, extra_itemSubs ) 
        if not schema: schema = "TT"
        super(CSVParse_Woo, self).__init__( cols, defaults, schema, \
                taxoSubs, itemSubs, taxoDepth, itemDepth, metaWidth)
        self.dprcRules = dprcRules
        self.dprpRules = dprpRules
        self.specials = specials
        self.productContainer = ImportWooProduct
        self.categoryContainer = ImportWooCategory
        if DEBUG_WOO:
            print "WOO initializing: "
            print "-> taxoDepth: ", self.taxoDepth
            print "-> itemDepth: ", self.itemDepth
            print "-> maxDepth: ", self.maxDepth
            print "-> metaWidth: ", self.metaWidth

    def clearTransients(self):
        super(CSVParse_Woo, self).clearTransients()
        self.categories = OrderedDict()
        self.attributes = OrderedDict()
        self.variations = OrderedDict()
        self.images     = OrderedDict()        

    def registerImage(self, image, objectData):
        assert isinstance(image,str) 
        assert image is not "" 
        self.registerAnything(
            objectData,
            self.images,
            image,
            singular = False,
            registerName = 'images'
        )
        objectData.registerImage(image)

    def registerCategory(self, catData, itemData):

        self.registerAnything(
            catData, 
            self.categories, 
            # indexer = self.getSum,
            indexer = self.getObjectRowcount,
            resolver = self.passiveResolver,
            singular = True,
            registerName = 'categories'
        )
        itemData.joinCategory(catData)

    def registerAttribute(self, objectData, attr, val):
        # if DEBUG_WOO: print 'registering attribute: ',attr, ': ', val 
        try:
            attr = str(attr)
            assert isinstance(attr, str), 'Attribute must be a string not '+str(type(attr))
            assert attr is not '', 'Attribute must not be empty'
        except AssertionError as e:
            self.registerError(e)
            # raise e
        else:
            objectData.registerAttribute(attr, val)

            if attr not in self.attributes.keys():
                self.attributes[attr] = [] 
            if val not in self.attributes[attr]:
                self.attributes[attr].append(val)

    def registerVariation(self, parentData, varData):
        assert parentData.isVariable()
        assert varData.isVariation()
        self.registerAnything( 
            varData, 
            self.variations, 
            registerName = 'variations' 
        )
        # if not parentData.get('variations'): parentData['variations'] = OrderedDict()
        varData.joinVariable(parentData)

    def processImages(self, objectData):
        # if DEBUG_WOO: print "called processImages"

        imglist = filter(None, findAllImages(objectData.get('Images','')))
        for image in imglist:
            self.registerImage(image, objectData)
            objectData.registerImage(image)

        # todo: share images with nearest parent

        # for image in objectData['imglist']:
        #     self.registerImage(image, objectData)
            
        # if self.taxoDepth > 1 and objectData.getDepth() > self.taxoDepth :
        #     parentData = self.stack.getTopParent()
        #     if not objectData['imglist'] and parentData['imglist']:
        #         objectData['imglist'] = parentData['imglist']
        #     elif objectData['imglist'] and not parentData['imglist']:
        #         parentData['imglist'] = objectData['imglist'][:]

    def processCategories(self, objectData):
        if objectData.isItem():
            for ancestor in objectData.getTaxoAncestors():
                self.registerCategory(ancestor, objectData)

        #todo: this "extra item" crap

        # if objectData.get('E'):
        #     if objectData.isItem():
        #         extraStack = self.stack.getLeftSlice(self.taxoDepth-1)
        #         extraLayer = self.newObject(objectData.getRowcount(), objectData.getRow(), objectData.getDepth() + 1, extraStack)
        #         # extraStack.append(extraLayer)
        #         extraCodesum = extraLayer.getSum()

        # if objectData.get('E'):
        #     if self.isItem(objectData):
        #         # print "pricessing extra item categories"
        #         extraStack = self.stack[:self.taxoDepth-1]
        #         extraLayer = self.fakeLayer(
        #             objectData['rowcount'], 
        #             len(extraStack)
        #             [
        #                 objectData['name'] + ' Items',
        #                 objectData['code']
        #             ]
        #         )

        #         extraStack.append(extraLayer)
        #         self.initializeData(extraLayer, extraStack)

        #         extraCodes = extraStack.retrieveKey('code')
        #         extraCodesum = self.joinCodes(extraCodes)

        #         # print "looking for ", extraCodesum
        #         # extraStack.getTopParent()
        #         parentData = extraStack.getTopParent()
        #         if parentData.get('children'):
        #             for child in parentData.get('children').values():
        #                 if child['codesum'] == extraCodesum:
        #                     # print "found child ", extraCodesum
        #                     extraLayer = child
        #                     break

        #         self.registerCategory(extraLayer, objectData)
        #     else:
        #         pass


    def decodeAttributes(self, string):
        try:
            attrs = json.loads(string)
            assert isinstance(string, str)
        except (ValueError, AssertionError) as e:
            self.registerError(e)
            attrs = {}
        return attrs

    def processProductAttributes(self, itemData, attrs):
        for attr, val in attrs.items():
            self.registerAttribute(itemData, attr, val)

    def processVariableAttributes(self, parentData, itemData, attrs):
        for attr, val in attrs.items():
            self.registerAttribute(parentData, attr, val, True)   
            self.registerAttribute(itemData, attr, val, True)     

    def processSpecials(self, itemData):
        schedule = itemData.get('SCHEDULE')
        if schedule:
            print "special for ", self.getIndex(itemData)
            splist = filter(None, findAllTokens(schedule))
        else:
            splist = []
        itemData['splist'] = splist

    def processItemtype(self, itemData):
        if DEBUG_WOO:
            print "WOO.processItemtype before isItem: ", itemData.getSum()
        if self.isItem(itemData) and itemData['itemtype'] in self.prod_types.keys():
            itemData['prod_type'] = self.prod_types[itemData['itemtype']]
            if DEBUG_WOO:
                print "WOO.processItemtype before isProduct: ", itemData.getSum()
            if itemData.isProduct():
                for layer in self.stack:
                    self.processCategories(layer)
                cats = itemData.getCategories().values()

                if DEBUG_WOO:
                    print "WOO.processItemtype before cats: ", itemData.getSum()

                palist = filter(None, map(
                    lambda cat: cat.get('PA'),
                    cats
                ))
                # for attrs in map(self.decodeAttributes, filter(None, self.stack.retrieveKey('PA'))):
                for attrs in map(self.decodeAttributes, palist):
                    self.processProductAttributes(itemData, attrs)

                # if not self.isVariable(itemData):
                    # self.processSpecials(itemData)

                self.registerProduct(itemData)

            elif self.isVariation(itemData):
                parentData = self.stack.getTopParent()
                assert(self.isProduct(parentData)), 'parent of variable instance should be a product'
                itemData['parent'] = parentData
                itemData['parent_SKU'] = parentData['codesum']
                # self.processSpecials(itemData)
                self.processVariableAttributes( parentData, itemData, self.decodeAttributes(itemData['VA']))
                self.registerVariation(parentData, itemData)

    def processObject(self, row, objectData):
        super(CSVParse_Woo, self).processObject(row, objectData)
        self.processImages(objectData)
        self.processSpecials(objectData)

    def addDynRules(self, itemData, dynType, ruleIDs):
        rules = {
            'dprc':self.dprcRules, 
            'dprp':self.dprpRules
        }[dynType]
        dynListIndex = dynType+'list'
        dynIDListIndex = dynType+'IDlist'
        if not itemData.get(dynListIndex):
            itemData[dynListIndex]=[]
        if not itemData.get(dynIDListIndex):
            itemData[dynIDListIndex]=[]
        for ruleID in ruleIDs:
            if ruleID not in itemData[dynIDListIndex]:
                itemData[dynIDListIndex] = ruleID
            # print "adding %s to %s" % (ruleID, itemData['codesum'])
            rule = rules.get(ruleID)
            if rule: 
                if rule not in itemData[dynListIndex]:
                    itemData[dynListIndex].append(rule)
            else:
                self.registerError('rule should exist: %s'%ruleID, itemData)

    def postProcessDyns(self, itemData):
        print "postProcessDyns", itemData.getCodesum(), itemData.getSum()
        #postProcess DPRCs
        # if self.isProduct(itemData):
        categories = filter(
            None,
            itemData.get('catlist', {}).values()
        )
        for cat in categories + [itemData]:
            # print "%16s is a member of %s" % (itemData['codesum'], cat['taxosum'])
            dprcString = cat.get('DYNCAT')
            if dprcString:
                # print " -> DPRC", dprcString
                dprclist = dprcString.split('|')
                self.addDynRules(itemData, 'dprc', dprclist)
            dprpString = cat.get('DYNPROD')
            if dprpString:
                # print " -> DPRP", dprpString
                dprplist = dprpString.split('|')
                self.addDynRules(itemData, 'dprp', dprplist)

        itemData['dprcsum'] = '<br/>'.join(
            filter( 
                None,
                map(
                    lambda x: x.toHTML(),
                    itemData.get( 'dprclist','')
                )
            )
        )
        itemData['dprpsum'] = '<br/>'.join(
            filter( 
                None,
                map(
                    lambda x: x.toHTML(),
                    itemData.get('dprplist','')
                )
            )
        )
        # else:
        #     pass
            #todo maybe add stuff for categories

    def postProcessCategories(self, itemData):
        if self.isProduct(itemData):
            categories = filter(
                None,
                itemData.get('catlist', {}).values()
            )

            itemData['catsum'] = '|'.join(filter(
                None,
                map(
                    lambda x: x.get('taxosum', ''),
                    categories
                )
            ))

    def postProcessImages(self, itemData):
        itemData['imgsum'] = '|'.join(filter(
            None, 
            itemData.get('imglist', [])
        ))

        if self.isProduct(itemData) :
            try:
                assert itemData['imgsum'], "All Products should have images"
            except Exception as e:
                self.registerError(e, itemData)

    def postProcessAttributes(self, itemData):
        # print 'analysing attributes', itemData.get('codesum')

        for attr, data in itemData.get('attributes',{}).items():
            if not data: continue
            values = '|'.join(map(str,data.get('values',[])))
            visible = data.get('visible', 1)
            variation = data.get('variation',0)
            position = data.get('position',0)
            default = data.get('default', '')

            # self.pp.pprint({
            #     'attr':attr,
            #     'values':values,
            #     'visible':visible,
            #     'variation':variation,
            #     'default':default
            # })

            if self.isProduct(itemData):
                itemData['attribute:'+attr] = values
                itemData['attribute_data:'+attr] = '|'.join(map(str,[
                    position,
                    visible,
                    variation
                ]))
                itemData['attribute_default:'+attr] = default

            if self.isVariation(itemData):
                try:
                    assert variation == 1, "variations should have 'variation' set" 
                except Exception as e:
                    self.registerError(e, itemData)

                itemData['meta:attribute_'+attr] = values

    def postProcessSpecials(self, itemData):
        # print 'analysing specials', itemData.get('codesum')

        if self.isProduct(itemData) or self.isVariation(itemData):
            if self.isProduct(itemData): 
                print '-> is a product'
            if self.isVariation(itemData):
                print '-> is a variation'

            splist = itemData.get('splist', [])
            if not splist: 
                splist = []

            cats = itemData.get('catlist', {}).values()

            for cat in cats:
                csplist = cat.get('splist', [])
                if csplist:
                    print "cat splist: ", csplist
                    splist.extend(cat.get('splist', []))

            if itemData.get('parents') and itemData['parents'].values():
                print "has parents"
                for parent in itemData['parents'].values():
                    psplist = parent.get('splist', [])
                    if psplist:
                        print "parent splist: ", psplist
                        splist.extend(psplist)

            print '-> splist', splist

            # if self.isVariation(itemData):
            #     parent = itemData.get('parent', None)
            #     if parent:
            #         psplist = parent.get('splist', [])
            #         if psplist:
            #             # print "parent splist: ", psplist
            #             splist.extend(psplist)



            itemData['splist'] = splist
            itemData['spsum'] = '|'.join(splist)

            for special in splist:
                print "--> analysing special", special
                # print "--> all specials: ", self.specials.keys()
                if special in self.specials.keys():
                    print "special exists!", special

                    specialparams = self.specials[special]

                    specialfrom = datetotimestamp( specialparams["FROM"])
                    specialto = datetotimestamp(specialparams["TO"])
                    if( specialto < time.time() ):
                        print "special is over"
                        continue

                    print "--> specialfrom", specialparams["FROM"], " | ", specialfrom
                    print "--> specialto", specialparams["TO"], " | ", specialto

                    for tier in ["RNS", "RPS", "WNS", "WPS", "DNS", "DPS"]:
                        discount = specialparams.get(tier)
                        if discount:
                            # print "discount is ", discount
                            special_price = None

                            percentages = findallPercent(discount)
                            # print "percentages are", percentages
                            if percentages:
                                coefficient = float(percentages[0]) / 100
                                regular_price_string = itemData.get(tier[:-1]+"R")
                                # print "regular_price_string", regular_price_string
                                if regular_price_string:
                                    regular_price = float(regular_price_string)
                                    special_price = regular_price * coefficient  
                            else:    
                                dollars = findallDollars(discount)
                                if dollars:
                                    dollar = float(self.sanitizeCell( dollars[0]) )
                                    if dollar:
                                        special_price = dollar

                            if special_price:
                                print "special price is", special_price
                                tier_key = tier
                                tier_from_key = tier[:-1]+"F"
                                tier_to_key = tier[:-1]+"T"
                                for key, value in {
                                    tier_key: special_price,
                                    tier_from_key: specialfrom,
                                    tier_to_key: specialto
                                }.items():
                                    print "setting itemData["+key+"] to "+str(value)
                                    itemData[key] = value
                                # itemData[tier_key] = special_price
                                # itemData[tier_from_key] = specialfrom
                                # itemData[tier_to_key] = specialto

                else:
                    print "special does not exist"
                    self.registerError(Exception("special does not exist %s" % special, itemData)) 

            print "setting", itemData.getCodesum(), "price to", itemData.get('RNR')
            itemData['price'] = itemData.get('RNR')
            itemData['sale_price'] = itemData.get('RNS')
            itemData['sale_price_dates_from'] = itemData.get('RNF')
            itemData['sale_price_dates_to'] = itemData.get('RNT')


    def analyseFile(self, fileName):
        objects = super(CSVParse_Woo, self).analyseFile(fileName)  
        #post processing
        for itemData in self.taxos.values() + self.items.values():
            print 'POST analysing product', itemData.getCodesum(), itemData.getSum()
            self.postProcessDyns(itemData)
            self.postProcessCategories(itemData)
            self.postProcessImages(itemData)
            self.postProcessAttributes(itemData)
            self.postProcessSpecials(itemData)

        return objects

    def getCategories(self):
        return self.categories
        # return self.flatten(self.categories.values())

    def getAttributes(self):
        return self.attributes
        # return self.flatten(self.attributes.values())

    def getVariations(self):
        return self.variations


class CSVParse_TT(CSVParse_Woo):
    """docstring for CSVParse_TT"""

    def __init__(self, cols={}, defaults ={}, importName="", \
                taxoSubs={}, itemSubs={}, taxoDepth=2, itemDepth=2, metaWidth=2,\
                dprcRules={}, dprpRules={}, specials={}):

        schema = "TT"

        extra_cols = [ 'RNRC', 'RPRC', 'WNRC', 'WPRC', 'DNRC', 'DPRC']
        extra_defaults    = OrderedDict([])
        extra_taxoSubs = OrderedDict([
            # ('TechnoTan After Care', 'Tan Care > After Care'),
            # ('TechnoTan Pre Tan', 'Tan Care > Pre Tan'),
            # ('TechnoTan Tan Enhancement', 'Tan Care > Tan Enhancement'),
            # ('TechnoTan Hair Care', 'Tan Care > Hair Care'),
            # ('TechnoTan Application Equipment', 'Equipment > Application Equipment'),
            # ('TechnoTan Tanning Booths', 'Equipment > Tanning Booths'),
            ('TechnoTan Literature', 'Marketing > Literature'),
            ('TechnoTan Signage', 'Marketing > Signage'),
            ('TechnoTan Spray Tanning Packages', 'Packages'),  
            # ('TechnoTan Solution', 'Solution'),
            # ('TechnoTan After Care', 'After Care'),
            # ('TechnoTan Pre Tan', 'Pre Tan'),
            # ('TechnoTan Tan Enhancement', 'Tan Enhancement'),
            # ('TechnoTan Hair Care', 'Hair Care'),
            # ('TechnoTan Tanning Accessories', 'Tanning Accessories'),
            # ('TechnoTan Technician Accessories', 'Technician Accessories'),
            # ('TechnoTan Application Equipment', 'Application Equipment'),
            # ('TechnoTan Tanning Booths', 'Tanning Booths'),
            # ('TechnoTan Apparel', 'Apparel'),
            ('TechnoTan ', ''),
        ])
        extra_itemSubs = OrderedDict()

        cols = self.combineLists( cols, extra_cols )
        defaults = self.combineOrderedDicts( defaults, extra_defaults )
        taxoSubs = self.combineOrderedDicts( taxoSubs, extra_taxoSubs )
        itemSubs = self.combineOrderedDicts( itemSubs, extra_itemSubs ) 
        super(CSVParse_TT, self).__init__( cols, defaults, schema, importName,\
                taxoSubs, itemSubs, taxoDepth, itemDepth, metaWidth, \
                dprcRules, dprpRules, specials) 
        if DEBUG_WOO:
            print "WOO initializing: "
            print "-> taxoDepth: ", self.taxoDepth
            print "-> itemDepth: ", self.itemDepth
            print "-> maxDepth: ", self.maxDepth
            print "-> metaWidth: ", self.metaWidth

class CSVParse_VT(CSVParse_Woo):
    """docstring for CSVParse_VT"""

    def __init__(self, cols={}, defaults ={}, importName="", \
                taxoSubs={}, itemSubs={}, taxoDepth=2, itemDepth=2, metaWidth=2,\
                dprcRules={}, dprpRules={}, specials={}):

        schema = "VT"

        extra_cols = [ 'RNRC', 'RPRC', 'WNRC', 'WPRC', 'DNRC', 'DPRC']
        extra_defaults    = OrderedDict([])
        extra_taxoSubs = OrderedDict([
            # ('VuTan After Care', 'Tan Care > After Care'),
            # ('VuTan Pre Tan', 'Tan Care > Pre Tan'),
            # ('VuTan Tan Enhancement', 'Tan Care > Tan Enhancement'),
            # ('VuTan Hair Care', 'Tan Care > Hair Care'),
            # ('VuTan Application Equipment', 'Equipment > Application Equipment'),
            # ('VuTan Tanning Booths', 'Equipment > Tanning Booths'),
            ('VuTan Literature', 'Marketing > Literature'),
            ('VuTan Signage', 'Marketing > Signage'),
            ('VuTan Spray Tanning Packages', 'Packages'),  
            # ('VuTan Solution', 'Solution'),
            # ('VuTan After Care', 'After Care'),
            # ('VuTan Pre Tan', 'Pre Tan'),
            # ('VuTan Tan Enhancement', 'Tan Enhancement'),
            # ('VuTan Hair Care', 'Hair Care'),
            # ('VuTan Tanning Accessories', 'Tanning Accessories'),
            # ('VuTan Technician Accessories', 'Technician Accessories'),
            # ('VuTan Application Equipment', 'Application Equipment'),
            # ('VuTan Tanning Booths', 'Tanning Booths'),
            # ('VuTan Apparel', 'Apparel'),
            ('VuTan ', ''),
        ])
        extra_itemSubs = OrderedDict()

        cols = self.combineLists( cols, extra_cols )
        defaults = self.combineOrderedDicts( defaults, extra_defaults )
        taxoSubs = self.combineOrderedDicts( taxoSubs, extra_taxoSubs )
        itemSubs = self.combineOrderedDicts( itemSubs, extra_itemSubs ) 
        super(CSVParse_VT, self).__init__( cols, defaults, schema, importName,\
                taxoSubs, itemSubs, taxoDepth, itemDepth, metaWidth, \
                dprcRules, dprpRules, specials) 
        if DEBUG_WOO:
            print "WOO initializing: "
            print "-> taxoDepth: ", self.taxoDepth
            print "-> itemDepth: ", self.itemDepth
            print "-> maxDepth: ", self.maxDepth
            print "-> metaWidth: ", self.metaWidth


if __name__ == '__main__':
    from coldata import ColData_Woo
    colData = ColData_Woo()

    print "Testing script..."
    inFolder = "../input/"
    genPath = inFolder + "generator.csv"

    outFolder = "../output/"
    prodPath = outFolder + 'products.csv'

    importName = time.strftime("%Y-%m-%d %H:%M:%S")

    # WooParser = CSVParse_TT(
    #     cols = colData.getImportCols(),
    #     defaults = colData.getDefaults(),
    #     importName = importName,
    #     taxoDepth = 3,
    # )
    # WooParser.analyseFile(genPath)

    # with open(prodPath, 'w+') as outFile:
    #     cols = ['rowcount', 'codesum', 'itemsum', 'descsum', 'attributes']
    #     dictwriter = csv.DictWriter(outFile, fieldnames=cols, extrasaction='ignore' )
    #     dictwriter.writeheader()
    #     dictwriter.writerows(WooParser.products.values())

    # sort_keys = lambda (ka, va), (kb, vb): cmp(ka, kb)

    # print "Categories:"
    # for key, category in sorted(WooParser.categories.items(), sort_keys):
    #     print "%15s | %s" % (category.get('codesum', ''), category.get('taxosum', ''))

    # print "Products:"
    # for product in WooParser.getProducts():
    #     print "%15s | %s" % (product.get('codesum', ''), product.get('itemsum', '')), product.get('dprplist')

    # print "Variations:"
    # for sku, variation in WooParser.variations.items():
    #     print "%15s | %s" % (sku, variation.get('itemsum', ''))

    # print "Attributes"
    # for attr, vals in WooParser.attributes.items():
    #     print "%15s | %s" % (attr[:15], "|".join(map(str,vals)))

    # for img, items in WooParser.images.items():
    #         print "%s " % img
    #         for item in items:
    #             print " -> (%4d) %15s " % (item['rowcount'], item['codesum'])




