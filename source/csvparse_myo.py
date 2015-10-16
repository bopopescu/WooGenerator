from csvparse_gen import CSVParse_Gen, ImportGenProduct
from collections import OrderedDict
from coldata import ColData_MYO
import time
import os

DEBUG_MYO = True

class CSVParse_MYO(CSVParse_Gen):
    """docstring for CSVParse_MYO"""

    def __init__(self, cols={}, defaults={}, schema='MY', importName="", \
            taxoSubs={}, itemSubs={}, taxoDepth=3, itemDepth=2, metaWidth=2):

        product_types = {
            'Y': ImportGenProduct
        }

        extra_cols = [ 'WNRC', 'RNRC', 'HTML Description' ]

        extra_defaults =  OrderedDict([
            ('Sell', 'S'),
            ('Tax Code When Sold', 'GST'),
            ('Sell Price Inclusive', 'X'),
            ('Income Acct', '41000'),
            ('Use Desc. On Sale', ''),
            ('Inactive Item', 'N'),
        ])

        extra_taxoSubs = OrderedDict([
            ('', ''),
        ])

        extra_itemSubs = OrderedDict([
            ('Body Butter with Shimmer', 'Body Butter w/ Shimmer'),
            ('Tan Saver Body Wash', 'Body Wash'),
            ('Full Body Moisturizer', 'Moisturizer'),
            ('Moisturizing Body Milk', 'Body Milk'),
            ('Hair Brush', 'Brush'),
            ('Training Session', 'Session'),
            ('Skin Trial Pack', "Pack"),
            ('Trial Pack', "Pack"),
            ('Starter Package', 'Pack'),
            ('Sample Pack', "Pack"),
            ('Evaluation Package', 'Pack'),
            ('Spare Pot & Hose', 'Pot, Hose'),
            ('Spare Pots & Hose', 'Pots, Hose'),
            ('spare pot + Hose', 'pot, hose'),
            ('spare pots + Hose', 'pots, hose'),
            ('extraction fans', 'xfan'),
            ('Low Voltage', 'LV'),
            ('Double Sided', '2Sided'),

            ('TechnoTan', 'TT'),
            ('VuTan', 'VT'),
            ('EzeBreathe', 'EZB'), 
            ('Sticky Soul', 'SS'),
            ('My Tan', 'MT'),
            ('TanSense', 'TS'),
            ('Tanning Advantage', 'TA'),
            ('Tanbience', 'TB'),
            ('Mosaic Minerals', 'MM'),

            ('Removal', 'Rem.'),
            ('Application', 'App.'),
            ('Peach & Vanilla', 'P&V'),
            ('Tamarillo & Papaya', 'T&P'),
            ('Tamarillo', 'TAM'),
            ('Lavander & Rosmary', 'L&R'),
            ('Coconut & Lime', 'C&L'),
            ('Melon & Cucumber', 'M&C'),
            ('Coconut Cream', 'CC'),
            ('Black & Silver', 'B&S'),
            ('Black & Gold', 'B&G'),
            ('Hot Pink', 'PNK'),
            ('Hot Lips (Red)', 'RED'),
            ('Hot Lips Red', 'RED'),
            ('Hot Lips', 'RED'),
            ('Silken Chocolate (Bronze)', 'BRZ'),
            ('Silken Chocolate', 'BRZ'),
            ('Moon Marvel (Silver)', 'SLV'),
            ('Dusty Gold', 'GLD'),

            ('Black', 'BLK'),
            ('Light Blue', 'LBLU'),
            ('Dark Blue', 'DBLU'),
            ('Blue', 'BLU'),
            ('Green', 'GRN'),
            ('Pink', 'PNK'),
            ('White', 'WHI'),
            ('Grey', 'GRY'),
            ('Peach', 'PEA'),
            ('Bronze', 'BRZ'),
            ('Silver', 'SLV'),
            ('Gold', 'GLD'),
            ('Red', 'RED'),

            ('Cyclone', 'CYC'),
            ('Classic', 'CLA'),
            ('Premier', 'PRE'),
            ('Deluxe', 'DEL'),
            ('ProMist Cube', 'CUBE'),
            ('ProMist', 'PRO'),
            ('Mini Mist', 'MIN'),

            ('Choc Fudge', 'CFdg.'),
            ('Choc Mousse', 'Cmou'),
            ('Ebony', 'Ebny.'),
            ('Creme Caramel', 'CCarm.'),
            ('Caramel', 'Carm.'),
            ('Cappuccino', 'Capp.'),
            ('Evaluation', 'Eval.'),
            ('Package', 'Pack'),
            ('Sample', 'Samp.'),
            ('sample', 'Samp.'),
            ('Tan Care', 'TCare'),
            ('After Care', "ACare"),
            ('A-Frame', 'AFrm'),
            ('X-Frame', 'XFrm'),
            ('Tear Drop Banner', 'TDBnr'),
            ('Roll Up Banner', 'RUBnr'),
            ('Hose Fitting', 'Fit.'),
            ('Magnetic', 'Mag.'),
            ('Option ', 'Opt.'),
            ('Style ', 'Sty.'),
            ('Insert and Frame', 'ins. frm.'),
            ('Insert Only', 'ins.'),
            ('Insert', 'ins.'),
            ('insert', 'ins.'),
            ('Frame', 'frm.'),
            ('Foundation', 'Found.'),
            ('Economy', 'Econ.'),

            ('Medium-Dark', 'MDark'),
            ('Medium Dark', 'MDark'),
            ('Medium', 'Med.'),
            ('medium', 'med.'),
            ('Extra Dark', 'XDark'),
            ('Extra-Dark', 'XDark'),
            ('Dark', 'Dark'),
            ('Tanning', 'Tan.'),
            ('Extra Small', 'XSml.'),
            ('Small', 'Sml.'),
            ('Extra Large', 'XLge.'),
            ('Large', 'Lge.'),
            ('Ladies', 'Ld.'),
            ('Mens', 'Mn.'),
            ('Non Personalized', 'Std.'),
            ('Personalized', 'Per.'),
            ('personalized', 'per.'),
            ('Personalised', 'Per.'),
            ('personalised', 'per.'),
            ('Custom Designed', 'Cust.'),
            ('Refurbished', 'Refurb.'),
            ('Compressor', 'Cmpr.'),
            ('Spray Gun', 'Gun'),
            ('Permanent', 'Perm.'),
            ('Shimmering', 'Shim.'),
            ('Screen Printed', 'SP'),
            ('Embroidered', 'Embr.'),
            ('Athletic', 'Athl.'),
            ('Singlet', 'Sing.'),
            ('Solution', 'Soln.'),
            ('Flash Tan', 'FTan'),
            ('Original', 'Orig.'),
            ('Exfoliating', 'Exfo.'),
            ('Disposable', 'Disp.'),
            ('Retractable', 'Ret.'),
            ('Synthetic', 'SYN'),
            ('Natural', 'NAT'),
            ('Bayonet', 'BAY'),
            ('Hexagonal', 'Hex.'),

            ('one', '1'),
            ('One', '1'),
            ('two', '2'),
            ('Two', '2'),
            ('three', '3'),
            ('Three', '3'),
            ('four', '4'),
            ('Four', '4'),
            # ('for', '4'),
            ('five', '5'),
            ('Five', '5'),
            ('six', '6'),
            ('Six', '6'),
            ('seven', '7'),
            ('seven', '7'),
            ('eight', '8'),
            ('Eight', '8'),
            ('nine', '9'),
            ('Nine', '9'),

            (' Plus', '+'),
            (' - ', ' '),
            (' Pack / ', ' x '),
            ('with', 'w/'),
            ('With', 'w/'),
            ('Box of', 'Box/'),
            (' Fitting for ', ' Fit '),
            (' Fits ', ' Fit '),

            # (' (2hr)', ''),
            (' (sachet)', ''),
            (' (pump bottle)', ''),
            (' Bottle with Flip Cap', ''),
            (' (jar)', ''),
            (' (tube)', ''),
            (' (spray)', ''), 
    
            (' \xe2\x80\x94 ', ' '),

        ])

        cols = list(set(cols) | set(extra_cols)) if cols else extra_cols
        defaults = OrderedDict(extra_defaults.items() + defaults.items() + ('last_import', importName))\
            if defaults else extra_defaults
        if not importName: importName = time.strftime("%Y-%m-%d %H:%M:%S")
        taxoSubs = OrderedDict(extra_taxoSubs.items() + taxoSubs.items())
        itemSubs = OrderedDict(extra_itemSubs.items() + itemSubs.items())
        super(CSVParse_MYO, self).__init__( cols, defaults, schema, \
                taxoSubs, itemSubs, taxoDepth, itemDepth, metaWidth)
        if DEBUG_MYO: print "csvparse initialized with cols:",str(extra_cols)

    # def joinDescs(self, descs, fullnames):
    #     return self.changeFullname(self.joinItems(fullnames[self.taxoDepth:]))

    # def processItemtype(self, itemData):
    #     if itemData['itemtype'] == 'Y':
    #         itemData['item_name'] = itemData['itemsum'][:32]
    #         # itemData['description'] = itemData['descsum'][:]
    #         self.registerProduct(itemData)        

if __name__ == '__main__':
    print "Testing MYO script..."
    inFolder = "../input/"
    genPath = os.path.join(inFolder, 'generator.csv')


    colData = ColData_MYO()
    productParser = CSVParse_MYO(
        cols = colData.getImportCols(),
        defaults = colData.getDefaults(),
    )
    productParser.analyseFile(genPath)
    products = productParser.getProducts()

    print "products:"
    for product in products:
        print "%15s | %32s | %s" % (product.get('codesum', ''), product.get('item_name',''), product.get('descsum', ''))
        # print "\t%128s\n" % product.get('descsum', '')          