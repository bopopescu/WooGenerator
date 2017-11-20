"""
Introduce woo api structure to shop classes.
"""
from __future__ import absolute_import, print_function

import datetime
import io
import cjson
from collections import OrderedDict
from copy import deepcopy
from pprint import pformat, pprint

from ..coldata import ColDataSubMedia, ColDataProductMeridian, ColDataWcProdCategory
from ..utils import DescriptorUtils, Registrar, SanitationUtils, SeqUtils
from .abstract import CsvParseBase
from .gen import ImportGenItem, ImportGenObject, ImportGenTaxo
from .shop import (CsvParseShopMixin, ImportShopCategoryMixin, ImportShopMixin,
                   ImportShopProductMixin, ImportShopProductSimpleMixin,
                   ImportShopProductVariableMixin,
                   ImportShopProductVariationMixin)
from .tree import CsvParseTreeMixin, ImportTreeRoot
from .woo import (CsvParseWooMixin, ImportWooImg, ImportWooMixin,
                  WooCatList, WooImgList, WooProdList)


class ApiListMixin(object):
    @staticmethod
    def json_serial(obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        raise TypeError ("Type %s not serializable" % type(obj))

    def export_api_data(self, file_path, encoding='utf-8'):
        """
        Export the items in the object list to a json file in the given file path.
        """

        assert file_path, "needs a filepath"
        assert self.objects, "meeds items"
        with open(file_path, 'wb') as out_file:
            data = []
            for item in self.objects:
                try:
                    data.append(dict(item['api_data']))
                except KeyError:
                    raise UserWarning("could not get api_data from item")
            data = SanitationUtils.encode_json(data, default=ApiListMixin.json_serial)
            data = data.encode(encoding)
            print(data, file=out_file)
        self.register_message("WROTE FILE: %s" % file_path)


class ImportApiObjectMixin(object):
    child_indexer = Registrar.get_object_index

    def process_meta(self):
        # API Objects don't process meta
        pass

    @property
    def index(self):
        return self.get(self.api_id_key)

    @property
    def identifier(self):
        # identifier = super(ImportWooApiObject, self).identifier
        identifiers = [
            'r:%s' % str(self.rowcount),
            'a:%s' % str(self.get(self.api_id_key)),
            self.title,
        ]
        if getattr(self, 'is_item'):
            identifiers[2:3] = [self.codesum]
        return "|".join(map(str, identifiers))


class ImportApiRoot(ImportTreeRoot):
    child_indexer = ImportApiObjectMixin.child_indexer

class ImportWooApiObject(ImportGenObject, ImportShopMixin, ImportWooMixin, ImportApiObjectMixin):
    child_indexer = ImportApiObjectMixin.child_indexer
    category_indexer = CsvParseWooMixin.get_title
    process_meta = ImportApiObjectMixin.process_meta
    index = ImportApiObjectMixin.index
    identifier = ImportApiObjectMixin.identifier
    to_dict = ImportShopMixin.to_dict
    api_id_key = ImportWooMixin.wpid_key
    api_id = DescriptorUtils.safe_key_property(api_id_key)
    verify_meta_keys = SeqUtils.combine_lists(
        ImportGenObject.verify_meta_keys,
        ImportWooMixin.verify_meta_keys
    )
    verify_meta_keys.remove(ImportGenObject.descsum_key)

    def __init__(self, *args, **kwargs):
        if self.DEBUG_MRO:
            self.register_message('ImportWooApiObject')
        ImportGenObject.__init__(self, *args, **kwargs)
        ImportShopMixin.__init__(self, *args, **kwargs)
        ImportWooMixin.__init__(self, *args, **kwargs)


    # def verify_meta(self):
    #     # self.descsum = self.description
    #     assert self.descsum_key in self, "descsum should be set in %s. data: %s " % (
    #         self, self.items())
    #     # self.namesum = self.title
    #     assert self.namesum_key in self, "namesum should be set in %s. data: %s " % (
    #         self, self.items())
    #     # if self.is_category:
    #     #     self.codesum = ''
    #     assert self.codesum_key in self, "codesum should be set in %s. data: %s " % (
    #         self, self.items())

class ImportWooApiItem(ImportWooApiObject, ImportGenItem):
    verify_meta_keys = SeqUtils.combine_lists(
        ImportWooApiObject.verify_meta_keys,
        ImportGenItem.verify_meta_keys
    )
    verify_meta_keys.remove(ImportGenItem.namesum_key)
    is_item = ImportGenItem.is_item

class ImportWooApiProduct(ImportWooApiItem, ImportShopProductMixin):
    is_product = ImportShopProductMixin.is_product

    verify_meta_keys = ImportWooApiObject.verify_meta_keys

    def __init__(self, *args, **kwargs):
        if self.DEBUG_MRO:
            self.register_message('ImportWooApiProduct')
        if self.product_type:
            args[0]['prod_type'] = self.product_type
        ImportWooApiObject.__init__(self, *args, **kwargs)
        ImportShopProductMixin.__init__(self, *args, **kwargs)

class WooApiProdList(WooProdList, ApiListMixin):
    supported_type = ImportWooApiProduct

ImportWooApiProduct.container = WooApiProdList

class ImportWooApiProductSimple(ImportWooApiProduct, ImportShopProductSimpleMixin):
    product_type = ImportShopProductSimpleMixin.product_type


class ImportWooApiProductVariable(
        ImportWooApiProduct, ImportShopProductVariableMixin):
    is_variable = ImportShopProductVariableMixin.is_variable
    product_type = ImportShopProductVariableMixin.product_type

    def __init__(self, *args, **kwargs):
        if self.DEBUG_MRO:
            self.register_message('ImportWooApiProductVariable')
        ImportWooApiProduct.__init__(self, *args, **kwargs)
        ImportShopProductVariableMixin.__init__(self, *args, **kwargs)


class ImportWooApiProductVariation(
        ImportWooApiProduct, ImportShopProductVariationMixin):
    is_variation = ImportShopProductVariationMixin.is_variation
    product_type = ImportShopProductVariationMixin.product_type

class ImportWooApiTaxo(ImportWooApiObject, ImportGenTaxo):
    is_taxo = ImportGenTaxo.is_taxo

    verify_meta_keys = SeqUtils.combine_lists(
        ImportWooApiObject.verify_meta_keys,
        ImportGenTaxo.verify_meta_keys
    )
    verify_meta_keys.remove(ImportGenObject.codesum_key)
    verify_meta_keys.remove(ImportGenObject.descsum_key)
    verify_meta_keys.remove(ImportGenTaxo.namesum_key)

    @classmethod
    def get_slug(cls, category_data):
        assert cls.slug_key in category_data, \
        "expected slug key (%s) in category_data" % cls.slug_key
        return category_data.get(cls.slug_key)

    @classmethod
    def get_title(cls, category_data):
        assert cls.title_key in category_data, \
        "expected title key (%s) in category_data" % cls.title_key
        return category_data.get(cls.title_key)


class ImportWooApiCategory(ImportWooApiTaxo, ImportShopCategoryMixin):
    is_category = ImportShopCategoryMixin.is_category
    identifier = ImportWooApiObject.identifier

    def __init__(self, *args, **kwargs):
        if self.DEBUG_MRO:
            self.register_message('ImportWooApiCategory')
        ImportWooApiObject.__init__(self, *args, **kwargs)
        ImportShopCategoryMixin.__init__(self, *args, **kwargs)

    @property
    def cat_name(self):
        return self.title

    @property
    def index(self):
        return self.title

class WooApiCatList(WooCatList, ApiListMixin):
    supported_type = ImportWooApiCategory
    report_cols = WooCatList.report_cols

ImportWooApiCategory.container = WooApiCatList

class ImportWooApiCategoryLegacy(ImportWooApiCategory):
    verify_meta_keys = SeqUtils.subtrace_two_lists(
        ImportWooApiCategory.verify_meta_keys,
        [
            ImportWooApiCategory.api_id_key,
            ImportWooApiCategory.slug_key
        ]
    )

ImportWooApiCategoryLegacy.container = WooApiCatList

class ImportWooApiImg(ImportWooImg):
    pass

class WooApiImgList(WooImgList, ApiListMixin):
    supported_type = ImportWooApiImg

ImportWooApiImg.container = WooApiImgList



class ApiParseMixin(object):
    root_container = ImportApiRoot
    coldata_gen_target = 'gen-api'
    def analyse_stream(self, byte_file_obj, **kwargs):

        limit, encoding, stream_name = \
            (kwargs.get('limit'), kwargs.get('encoding'), kwargs.get('stream_name'))

        if encoding is None:
            encoding = "utf8"

        if stream_name is None:
            if hasattr(byte_file_obj, 'name'):
                stream_name = byte_file_obj.name
            else:
                stream_name = 'stream'

        if self.DEBUG_PARSER:
            self.register_message(
                "Analysing stream: {}, encoding: {}, type: {}".format(
                    stream_name, encoding, type(byte_file_obj))
            )

        # I can't imagine this having any problems
        byte_sample = SanitationUtils.coerce_bytes(byte_file_obj.read(1000))
        byte_file_obj.seek(0)
        if self.DEBUG_PARSER:
            self.register_message("Byte sample: %s" % repr(byte_sample))

        decoded = SanitationUtils.decode_json(byte_file_obj.read())
        if not decoded:
            return
        if isinstance(decoded, list):
            for decoded_obj in decoded[:limit]:
                self.analyse_api_obj(decoded_obj)

    def get_kwargs(self, all_data, **kwargs):
        if 'parent' not in kwargs:
            kwargs['parent'] = self.root_data

        if 'depth' not in kwargs:
            kwargs['depth'] = kwargs['parent'].depth + 1
        return kwargs

    def analyse_api_obj(self, api_data, **kwargs):
        """
        Analyse an object from the wp api. Assume api_data has not been convert to gen data
        """

        coldata_class = kwargs.get('coldata_class', self.coldata_class)
        coldata_target = kwargs.get('coldata_target', self.coldata_target)

        core_api_data = coldata_class.translate_data_from(deepcopy(api_data), coldata_target)
        gen_api_data = coldata_class.translate_data_to(core_api_data, self.coldata_gen_target)

        row_data = deepcopy(gen_api_data)
        row_data['api_data'] = api_data
        if not 'type' in row_data:
            row_data['type'] = row_data.get('prod_type')
        kwargs['row_data'] = row_data

        object_data = self.new_object(rowcount=self.rowcount, **kwargs)
        if self.DEBUG_API:
            self.register_message("CONSTRUCTED: %s" % object_data.identifier)
        self.process_object(object_data)
        if self.DEBUG_API:
            self.register_message("PROCESSED: %s" % object_data.identifier)
        self.register_object(object_data)
        if self.DEBUG_API:
            self.register_message("REGISTERED: %s" % object_data.identifier)
        self.rowcount += 1

        return object_data

class ApiParseWoo(
    CsvParseBase, CsvParseTreeMixin, CsvParseShopMixin, CsvParseWooMixin, ApiParseMixin
):
    root_container = ApiParseMixin.root_container
    object_container = ImportWooApiObject
    product_container = ImportWooApiProduct
    simple_container = ImportWooApiProductSimple
    variable_container = ImportWooApiProductVariable
    variation_container = ImportWooApiProductVariation
    category_container = ImportWooApiCategory
    category_indexer = ImportWooApiTaxo.get_title
    item_indexer = CsvParseBase.get_object_rowcount
    taxo_indexer = ImportWooApiTaxo.get_title
    product_indexer = CsvParseShopMixin.product_indexer
    variation_indexer = CsvParseWooMixin.get_title
    image_container = ImportWooApiImg
    coldata_class = ColDataProductMeridian
    coldata_cat_class = ColDataWcProdCategory
    coldata_sub_img_class = ColDataSubMedia
    coldata_target = 'wc-wp-api'
    coldata_gen_target = ApiParseMixin.coldata_gen_target
    meta_get_key = 'meta_data'
    meta_listed = True
    analyse_stream = ApiParseMixin.analyse_stream
    get_kwargs = ApiParseMixin.get_kwargs

    def __init__(self, *args, **kwargs):
        if self.DEBUG_MRO:
            self.register_message('ApiParseWoo')
        super(ApiParseWoo, self).__init__(*args, **kwargs)
        # self.category_indexer = CsvParseGenMixin.get_name_sum
        # if hasattr(CsvParseWooMixin, '__init__'):
        #     CsvParseGenMixin.__init__(self, *args, **kwargs)

    def clear_transients(self):
        CsvParseBase.clear_transients(self)
        CsvParseTreeMixin.clear_transients(self)
        CsvParseShopMixin.clear_transients(self)
        CsvParseWooMixin.clear_transients(self)

        # super(ApiParseWoo, self).clear_transients()
        # CsvParseShopMixin.clear_transients(self)

    def register_object(self, object_data):
        # CsvParseGenTree.register_object(self, object_data)
        CsvParseBase.register_object(self, object_data)
        CsvParseTreeMixin.register_object(self, object_data)
        CsvParseShopMixin.register_object(self, object_data)
        # CsvParseWooMixin.register_object(self, object_data)

    # def process_object(self, object_data):
        # super(ApiParseWoo, self).process_object(object_data)
        # todo: this

    # def register_object(self, object_data):
    #     if self.DEBUG_MRO:
    #         self.register_message(' ')
    #     if self.DEBUG_API:
    #         self.register_message("registering object_data: %s" % str(object_data))
    #     super(ApiParseWoo, self).register_object(object_data)

    def analyse_api_image_raw(self, img_api_data, object_data=None, **kwargs):

        coldata_class = kwargs.get('codata_class', self.coldata_img_class)
        coldata_target = kwargs.get('coldata_target', self.coldata_img_target)

        img_core_data = coldata_class.translate_data_from(
            img_api_data, coldata_target
        )
        img_gen_data = coldata_class.translate_data_to(
            img_core_data, self.coldata_gen_target
        )
        img_gen_data['api_data'] = img_api_data
        self.analyse_api_image_gen(img_gen_data, object_data, **kwargs)

    def analyse_api_image_gen(self, img_gen_data, object_data=None, **kwargs):
        """ Create object for and analyse an API image object that is in gen format. """
        if not (img_gen_data.get('file_path') or img_gen_data.get('file_name')):
            warn = UserWarning(
                (
                    "could not process api img: no file path in API object\n"
                    "gen:%s\n"
                ) % (
                    pformat(img_gen_data.items()),
                )
            )
            self.register_warning(
                warn
            )
            raise warn
            return

        img_gen_data['type'] = 'image'

        super(ApiParseWoo, self).process_image(img_gen_data, object_data, **kwargs)

    def process_api_sub_image_raw(self, sub_img_api_data, object_data, **kwargs):
        coldata_class = kwargs.get('coldata_class', self.coldata_sub_img_class)
        coldata_target = kwargs.get('coldata_target', self.coldata_target)
        sub_img_core_data = coldata_class.translate_data_from(
            sub_img_api_data, coldata_target
        )
        sub_img_gen_data = coldata_class.translate_data_to(
            sub_img_core_data, self.coldata_gen_target
        )
        sub_img_gen_data['api_data'] = sub_img_api_data
        self.process_api_sub_image_gen(sub_img_gen_data, object_data, **kwargs)

    def process_api_sub_image_gen(self, sub_img_gen_data, object_data, **kwargs):
        """
        Process an api image that is a sub-entity in gen format.
        """
        if sub_img_gen_data.get('id') == 0:
            # drop the Placeholder image
            return

        sub_img_gen_data['type'] = 'sub-image'

        try:
            super(ApiParseWoo, self).process_image(sub_img_gen_data, object_data, **kwargs)
        except Exception as exc:
            warn = UserWarning("could not find api sub image, %s\nobject:\n%s" % (
                exc, object_data
            ))
            self.register_error(warn)
            if self.strict:
                self.raise_exception(warn)

    def process_api_category_raw(self, category_raw_data, object_data=None, **kwargs):
        """
        Create category if not exist of find if exist, then assign object_data to category.
        Category must be in raw format, already converted.
        """
        coldata_class = kwargs.get('coldata_class', self.coldata_cat_class)
        coldata_target = kwargs.get('coldata_target', self.coldata_target)
        category_core_data = coldata_class.translate_data_from(
            category_raw_data, coldata_target
        )
        category_gen_data = coldata_class.translate_data_to(
            category_core_data, self.coldata_gen_target
        )
        self.process_api_category_gen(category_gen_data, object_data, **kwargs)

    def process_api_category_gen(self, category_gen_data, object_data=None, **kwargs):
        """
        Create category if not exist or find if exist, then assign object_data to category
        Has to emulate CsvParseBase.new_object()
        category data must be in gen format, i.e. already converted.
        """
        if self.DEBUG_API:
            category_title = category_gen_data.get('title', '')
            if object_data:
                identifier = object_data.identifier
                self.register_message(
                    "%s member of category %s"
                    % (identifier, category_title)
                )
            else:
                self.register_message(
                    "creating category %s" % (category_title)
                )
            self.register_message("PROCESS CATEGORY: %s" %
                                  repr(category_gen_data))

        cat_data = None
        if not cat_data:
            try:
                category_index = self.category_indexer(category_gen_data)
                cat_data = self.categories.get(category_index)
            except:
                pass
        if not cat_data:
            category_search_data = {}
            category_search_data.update(**category_gen_data)

            # if 'itemsum' in category_search_data:
            #     category_search_data['taxosum'] = category_search_data['itemsum']
            #     del category_search_data['itemsum']

            if self.DEBUG_API:
                self.register_message("SEARCHING FOR CATEGORY: %s" %
                                      repr(category_search_data))

            cat_data = self.find_category(category_search_data)
        if not cat_data:
            if self.DEBUG_API:
                self.register_message("CATEGORY NOT FOUND")

            kwargs = OrderedDict()
            row_data = deepcopy(category_gen_data)
            row_data['type'] = 'category'
            kwargs['defaults'] = self.cat_defaults
            kwargs['row_data'] = row_data
            kwargs['container'] = self.category_container

            parent_category_data = None
            if self.category_container.parent_id_key in category_gen_data:
                parent_id = category_gen_data.get(self.category_container.parent_id_key)
                parent_category_search_data = {
                    self.category_container.wpid_key: parent_id
                }
                parent_category_data = self.find_category(
                    parent_category_search_data
                )
            if parent_category_data:
                kwargs['parent'] = parent_category_data
            else:
                kwargs['parent'] = self.root_data

            kwargs['coldata_class'] = self.coldata_cat_class

            cat_data = self.new_object(rowcount=self.rowcount, **kwargs)

            if self.DEBUG_API:
                self.register_message("CONSTRUCTED: %s" % cat_data.identifier)
            self.process_object(cat_data)
            if self.DEBUG_API:
                self.register_message("PROCESSED: %s" % cat_data.identifier)
            self.register_category(cat_data)
            if self.DEBUG_API:
                self.register_message("REGISTERED: %s" % cat_data.identifier)
            if 'image_object' in cat_data:
                sub_img_gen_data = cat_data['image_object']
                if sub_img_gen_data:
                    self.process_api_sub_image_gen(sub_img_gen_data, cat_data)
        else:
            if self.DEBUG_API:
                self.register_message("FOUND CATEGORY: %s" % repr(cat_data))
            # TODO: do any merging here?

        self.join_category(cat_data, object_data)

        self.rowcount += 1

    def process_api_categories_raw(self, categories):
        """ creates a queue of categories to be processed in the correct order """
        while categories:
            category = categories.pop(0)
            # self.register_message("analysing category: %s" % category)
            if category.get('parent_id'):
                parent_id = category.get('parent_id')
                # self.register_message("parent id: %s" % parent)
                queue_category_ids = [queue_category.get(
                    'id') for queue_category in categories]
                if parent_id in queue_category_ids:
                    # self.register_message('analysing later')
                    categories.append(category)
                    continue
                # self.register_message("queue categories: %s" % queue_category_ids)
                # for queue_category in categories:
                #     # If category's parent exists in queue
                #     if queue_category.get('id') == parent:
                #         # then put it at the end of the queue
                #         categories.append(category)
            self.process_api_category_raw(category)

    def process_api_attribute_gen(self, object_data, attribute_data_gen, var=False):
        # TODO: finish this
        pass

    def analyse_api_variation_gen(self, object_data, variation_data_gen):
        # TODO: finish this
        pass


    @classmethod
    def get_parser_data(cls, **kwargs):
        """
        Gets data ready for the parser, in this case from api_data which has already been
        converted to gen format
        """

        parser_data = kwargs.get('row_data', {})

        assert cls.object_container.title_key in parser_data, \
        "parser_data should have title(%s):\n%s" % (
            cls.object_container.title_key,
            pformat(parser_data.items())
        )

        if parser_data.get('type') == 'category':
            # parser_data[cls.category_container.namesum_key] = parser_data[
            #     cls.category_container.title_key]
            assert cls.category_container.slug_key in parser_data, \
            "parser_data should have slug(%s):\n%s" % (
                cls.category_container.slug_key,
                pformat(parser_data.items()),
            )
            parser_data[cls.category_container.codesum_key] = parser_data[
                cls.category_container.slug_key]
        elif parser_data.get('type') in ['sub-image', 'image']:
            assert cls.image_container.file_name_key in parser_data, \
            "parser_data should have file_name(%s):\n%s" % (
                cls.image_container.file_name_key,
                pformat(parser_data.items())
            )
        else:
            # parser_data[cls.object_container.namesum_key] = parser_data[
            #     cls.object_container.title_key]
            assert cls.object_container.codesum_key in parser_data, \
            "parser_data should have codesum(%s):\n%s" % (
                cls.object_container.codesum_key,
                parser_data
            )

        assert cls.object_container.descsum_key in parser_data, \
        "parser_data should have description(%s): \n%s" % (
            cls.object_container.descsum_key,
            pformat(parser_data.items()),
        )
        if not parser_data.get(cls.object_container.description_key):
            parser_data[cls.object_container.description_key] \
            = parser_data[cls.object_container.descsum_key]

        if Registrar.DEBUG_API:
            Registrar.register_message(
                "parser_data: {}".format(pformat(parser_data)))
        return parser_data

    def get_new_obj_container(self, all_data, **kwargs):
        # TODO: rewrite
        container = super(ApiParseWoo, self).get_new_obj_container(
            all_data, **kwargs)
        if 'type' in all_data:
            api_type = all_data['type']
            try:
                container = self.containers[api_type]
            except IndexError:
                exc = UserWarning("Unknown API product type: %s" % api_type)
                self.register_error(exc)
        return container

    def analyse_api_obj(self, api_data):
        """
        Analyse an object from the api.
        """

        object_data = ApiParseMixin.analyse_api_obj(self, api_data)

        if 'category_objects' in object_data:
            for category in object_data['category_objects']:
                self.process_api_category_gen(category, object_data)
            # pick a category as a parent
            category_depths = OrderedDict()
            for category in object_data.categories.values():
                depth = category.depth
                if depth not in category_depths:
                    category_depths[depth] = []
                category_depths[depth].append(category)
            if category_depths:
                deepest_category = list(reversed(sorted(category_depths.items())))[0][1][0]
                deepest_category.register_child(object_data)
                object_data.parent = deepest_category
                self.rowcount += 1

        if 'variations' in object_data:
            for variation_data_gen in object_data['variations']:
                self.analyse_api_variation_gen(object_data, variation_data_gen)
                self.rowcount += 1

        if 'attribute_objects' in object_data:
            for attribute_data_gen in object_data['attribute_objects']:
                self.process_api_attribute_gen(
                    object_data, attribute_data_gen, var=False
                )

        if 'image_objects' in object_data:
            sub_imgs_gen = object_data['image_objects']
            if sub_imgs_gen:
                for sub_img_gen_data in sub_imgs_gen:
                    self.process_api_sub_image_gen(
                        sub_img_gen_data, object_data
                    )

class ApiParseWooLegacy(ApiParseWoo):
    category_container = ImportWooApiCategoryLegacy
    coldata_target = 'wc-legacy-api'
    meta_get_key = 'meta'
    meta_listed = False

    def analyse_api_obj(self, api_data):
        """
        Analyse an object from the api.
        """

        object_data = ApiParseMixin.analyse_api_obj(self, api_data)

        if 'categories' in api_data:
            for category in api_data['categories']:
                self.process_api_category({'title': category}, object_data)
                # self.rowcount += 1

        if 'variations' in api_data:
            for variation in api_data['variations']:
                self.analyse_wp_api_variation(object_data, variation)
                # self.rowcount += 1

        if 'attributes' in api_data:
            self.process_api_attributes(
                object_data, api_data['attributes'], False)

    def analyse_wp_api_variation(self, object_data, variation_api_data):
        """
        Analyse a variation of an object from the wp_api.
        """
        # TODO rewrite for updated API

        if self.DEBUG_API:
            self.register_message("parent_data: %s" %
                                  pformat(object_data.items()))
            self.register_message("variation_api_data: %s" %
                                  pformat(variation_api_data))
        default_var_data = dict(
            type='variation',
            title='Variation #%s of %s' % (
                variation_api_data.get('id'), object_data.title),
            description=object_data.get('descsum'),
            parent_id=object_data.get('ID')
        )
        default_var_data.update(**variation_api_data)
        if self.DEBUG_API:
            self.register_message("default_var_data: %s" %
                                  pformat(default_var_data))

        kwargs = {
            'api_data': default_var_data,
            'parent': object_data
        }

        variation_data = self.new_object(rowcount=self.rowcount, **kwargs)

        if self.DEBUG_API:
            self.register_message(
                "CONSTRUCTED: %s" %
                variation_data.identifier)
        self.process_object(variation_data)
        if self.DEBUG_API:
            self.register_message("PROCESSED: %s" % variation_data.identifier)
        self.register_object(variation_data)
        # self.register_variation(object_data, variation_data)
        if self.DEBUG_API:
            self.register_message("REGISTERED: %s" % variation_data.identifier)

        self.rowcount += 1

        if 'attribute_objects' in variation_api_data:
            self.process_api_attributes(
                object_data, variation_api_data['attribute_objects'], True)

    def process_api_attributes(self, object_data, attributes, var=False):
        varstr = 'var ' if var else ''
        for attribute in attributes:
            if self.DEBUG_API:
                self.register_message("%s has %sattribute %s" % (
                    object_data.identifier, varstr, attribute))
            if 'name' in attribute:
                attr = attribute.get('name')
            elif 'slug' in attribute:
                attr = attribute.get('slug')
            else:
                raise UserWarning('could not determine attributte key')

            if 'option' in attribute:
                vals = [attribute['option']]
            elif 'options' in attribute:
                vals = attribute.get('options')
            else:
                raise UserWarning('could not determine attribute values')

            if vals:
                for val in vals:
                    self.register_attribute(object_data, attr, val, var)
