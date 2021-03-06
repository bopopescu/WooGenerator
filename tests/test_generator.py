from __future__ import print_function

import os
import shutil
import tempfile
import unittest
from collections import OrderedDict
from datetime import datetime
from pprint import pformat, pprint

import mock
import pytest
import pytz
from tabulate import tabulate

from context import TESTS_DATA_DIR, woogenerator
from six import text_type
from test_sync_manager import AbstractSyncManagerTestCase
from utils import MockUtils
from woogenerator.coldata import (ColDataAttachment, ColDataProductMeridian,
                                  ColDataProductVariationMeridian,
                                  ColDataWcProdCategory)
from woogenerator.generator import (do_match_categories, do_match_images,
                                    do_match_prod, do_match_var,
                                    do_merge_categories, do_merge_images,
                                    do_merge_prod, do_merge_var, do_report,
                                    do_report_categories, do_report_images,
                                    do_updates_categories_master,
                                    do_updates_categories_slave,
                                    do_updates_images_master,
                                    do_updates_images_slave,
                                    do_updates_prod_master,
                                    do_updates_prod_slave,
                                    do_updates_var_master,
                                    do_updates_var_slave, export_master_parser,
                                    populate_master_parsers,
                                    populate_slave_parsers)
from woogenerator.images import process_images
from woogenerator.matching import ProductMatcher
from woogenerator.namespace.core import MatchNamespace, UpdateNamespace
from woogenerator.namespace.prod import SettingsNamespaceProd
from woogenerator.parsing.api import ApiParseWoo
from woogenerator.parsing.special import CsvParseSpecial, SpecialGruopList
from woogenerator.parsing.tree import ItemList
from woogenerator.parsing.woo import CsvParseWoo, WooProdList
from woogenerator.parsing.xero import ApiParseXero
from woogenerator.utils import FileUtils, Registrar, SanitationUtils, TimeUtils
from woogenerator.utils.reporter import ReporterNamespace

from .abstract import AbstractWooGeneratorTestCase


class AbstractParserSyncManagerTestCase(AbstractSyncManagerTestCase):
    """
    Common superclass of TestGeneratorDummySpecials and TestGeneratorSuperDummy.

    House common utility functions.
    """
    def populate_master_parsers(self):
        if self.parsers.master:
            return
        if self.debug:
            print("regenerating master")
        populate_master_parsers(self.parsers, self.settings)

    def populate_slave_parsers(self):
        if self.parsers.slave:
            return
        if self.debug:
            print("regenerating slave")
        populate_slave_parsers(self.parsers, self.settings)

class TestGeneratorDummySpecials(AbstractParserSyncManagerTestCase):
    settings_namespace_class = SettingsNamespaceProd
    config_file = "generator_config_test.yaml"

    def setUp(self):
        super(TestGeneratorDummySpecials, self).setUp()
        self.settings.master_dialect_suggestion = "SublimeCsvTable"
        self.settings.download_master = False
        self.settings.download_slave = False
        self.settings.master_file = os.path.join(
            TESTS_DATA_DIR, "generator_master_dummy.csv"
        )
        self.settings.specials_file = os.path.join(
            TESTS_DATA_DIR, "generator_specials_dummy.csv"
        )
        self.settings.do_specials = True
        self.settings.specials_mode = 'all_future'
        # self.settings.specials_mode = 'auto_next'
        self.settings.wp_srv_offset = 7200
        self.settings.skip_special_categories = False
        self.settings.do_sync = True
        self.settings.do_categories = True
        self.settings.do_images = True
        self.settings.report_matching = True
        self.settings.auto_create_new = True
        self.settings.update_slave = False
        self.settings.do_problematic = True
        self.settings.do_report = True
        self.settings.do_remeta_images = False
        self.settings.do_resize_images = True
        self.settings.do_delete_images = False
        self.settings.schema = "CA"
        self.settings.ask_before_update = False
        self.settings.skip_unattached_images = True
        if self.settings.wc_api_is_legacy:
            self.settings.slave_file = os.path.join(
                TESTS_DATA_DIR, "prod_slave_woo_api_dummy_legacy.json"
            )
            self.settings.slave_cat_file = os.path.join(
                TESTS_DATA_DIR, "prod_slave_categories_woo_api_dummy_legacy.json"
            )
        else:
            self.settings.slave_file = os.path.join(
                TESTS_DATA_DIR, "prod_slave_woo_api_dummy_wp-json.json"
            )
            self.settings.slave_cat_file = os.path.join(
                TESTS_DATA_DIR, "prod_slave_cat_woo_api_dummy_wp-json.json"
            )
            self.settings.slave_img_file = os.path.join(
                TESTS_DATA_DIR, "prod_slave_img_woo_api_dummy_wp-json.json"
            )
        self.settings.img_raw_dir = os.path.join(
            TESTS_DATA_DIR, 'imgs_raw'
        )
        self.settings.init_settings(self.override_args)

        # TODO: this
        if self.debug:
            # Registrar.strict = True
            # Registrar.DEBUG_ABSTRACT = True
            # Registrar.DEBUG_PARSER = True
            # Registrar.DEBUG_TREE = True
            # Registrar.DEBUG_GEN = True
            # Registrar.DEBUG_SHOP = True
            # Registrar.DEBUG_WOO = True
            # Registrar.DEBUG_TRACE = True
            # Registrar.DEBUG_UPDATE = True
            Registrar.DEBUG_ERROR = True
            Registrar.DEBUG_WARN = True
            Registrar.DEBUG_MESSAGE = True
            Registrar.DEBUG_TRACE = True
            Registrar.DEBUG_CATS = True
            # Registrar.DEBUG_IMG = True
            # Registrar.DEBUG_SPECIAL = True
            # Registrar.strict = True
            ApiParseWoo.product_resolver = Registrar.exception_resolver
            CsvParseWoo.product_resolver = Registrar.exception_resolver
        else:
            Registrar.strict = False

    @pytest.mark.first
    def test_dummy_init_settings(self):
        self.assertTrue(self.settings.do_specials)
        self.assertTrue(self.settings.do_sync)
        self.assertTrue(self.settings.do_categories)
        self.assertTrue(self.settings.do_images)
        self.assertTrue(self.settings.do_resize_images)
        self.assertFalse(self.settings.do_remeta_images)
        self.assertTrue(self.settings.skip_unattached_images)
        self.assertTrue(self.settings.do_problematic)
        self.assertFalse(self.settings.download_master)
        self.assertFalse(self.settings.download_slave)
        self.assertEqual(self.settings.master_name, "gdrive-test")
        self.assertEqual(self.settings.slave_name, "woocommerce-test")
        self.assertEqual(self.settings.merge_mode, "sync")
        self.assertEqual(self.settings.specials_mode, "all_future")
        self.assertEqual(self.settings.schema, "CA")
        self.assertEqual(self.settings.download_master, False)
        self.assertEqual(
            self.settings.master_download_client_args["dialect_suggestion"],
            "SublimeCsvTable")
        self.assertEqual(self.settings.spec_gid, None)

    @pytest.mark.first
    def test_dummy_settings_namespace(self):
        sync_handles_cat = self.settings.sync_handles_cat
        for handle in [
            'rowcount'
        ]:
            self.assertNotIn(
                handle,
                sync_handles_cat
            )

        self.settings.do_categories = False
        self.settings.do_images = True
        self.settings.do_specials = True
        self.settings.do_dyns = True
        exclude_handles = self.settings.exclude_handles

        for handle in [
            'product_categories',
            'product_category_list'
        ]:
            self.assertIn(
                handle,
                exclude_handles
            )

        self.settings.do_categories = True
        self.settings.do_images = False
        self.settings.do_specials = True
        self.settings.do_dyns = True
        exclude_handles = self.settings.exclude_handles

        for handle in ['attachment_objects']:
            self.assertIn(
                handle,
                exclude_handles
            )
        self.settings.do_categories = True
        self.settings.do_images = True
        self.settings.do_specials = False
        self.settings.do_dyns = True
        exclude_handles = self.settings.exclude_handles

        for handle in [
            'lc_dp_sale_price', 'lc_rn_sale_price_dates_to', 'lc_dn_sale_price_dates_to', 'lc_wp_sale_price_dates_from',
            'lc_wn_sale_price_dates_from', 'sale_price_dates_to_gmt', 'lc_rn_sale_price', 'sale_price_dates_from_gmt',
            'specials_schedule', 'lc_rp_sale_price_dates_from', 'sale_price_dates_from', 'lc_rp_sale_price', 'lc_wn_sale_price',
            'lc_dn_sale_price_dates_from', 'lc_rn_sale_price_dates_from', 'sale_price_dates_to', 'lc_wp_sale_price',
            'lc_wp_sale_price_dates_to', 'lc_dp_sale_price_dates_to', 'lc_dp_sale_price_dates_from', 'sale_price',
            'lc_wn_sale_price_dates_to', 'lc_rp_sale_price_dates_to', 'lc_dn_sale_price'
        ]:
            self.assertIn(
                handle,
                exclude_handles
            )

        self.settings.do_categories = True
        self.settings.do_images = True
        self.settings.do_specials = True
        self.settings.do_dyns = False
        exclude_handles = self.settings.exclude_handles

        for handle in [
            'dynamic_category_rulesets',
            'dynamic_product_rulesets'
        ]:
            self.assertIn(
                handle,
                exclude_handles
            )

    @pytest.mark.first
    def test_dummy_populate_master_parsers(self):
        self.populate_master_parsers()

        #number of objects:
        self.assertEqual(len(self.parsers.master.objects.values()), 165)
        self.assertEqual(len(self.parsers.master.items.values()), 144)

        self.assertIn('modified_gmt', self.parsers.master.defaults)
        self.assertEqual(
            type(self.parsers.master.defaults['modified_gmt']),
            datetime
        )

        prod_container = self.parsers.master.product_container.container
        prod_list = prod_container(self.parsers.master.products.values())
        if self.debug:
            print("%d products:" % len(prod_list))
            print(SanitationUtils.coerce_bytes(prod_list.tabulate(tablefmt='simple')))
        self.assertEqual(len(prod_list), 48)
        first_prod = prod_list[0]

        if self.debug:
            print("pformat@first_prod:\n%s" % pformat(first_prod.to_dict()))
            print("first_prod.categories: %s" % pformat(first_prod.categories))
            print("first_prod.to_dict().get('attachment_objects'): %s" % pformat(first_prod.to_dict().get('attachment_objects')))
        self.assertEqual(first_prod.codesum, "ACARA-CAL")
        self.assertEqual(first_prod.parent.codesum, "ACARA-CA")
        first_prod_specials = first_prod.specials
        self.assertEqual(first_prod_specials,
                         ['SP2016-08-12-ACA', 'EOFY2016-ACA'])
        self.assertEqual(
            set([attachment.file_name for attachment in first_prod.to_dict().get('attachment_objects')]),
            set(["ACARA-CAL.png"])
        )
        self.assertEqual(first_prod.depth, 4)
        self.assertTrue(first_prod.is_item)
        self.assertTrue(first_prod.is_product)
        self.assertFalse(first_prod.is_category)
        self.assertFalse(first_prod.is_root)
        self.assertFalse(first_prod.is_taxo)
        self.assertFalse(first_prod.is_variable)
        self.assertFalse(first_prod.is_variation)
        test_dict = {
            'DNR': u'59.97',
            'DPR': u'57.47',
            'RNR': u'',
            'RPR': u'',
            'WNR': u'99.95',
            'WPR': u'84.96',
            'height': u'235',
            'length': u'85',
            'weight': u'1.08',
            'width': u'85',
            'rowcount': 10,
            'title': u'Range A - Style 1 - 1Litre',
            'HTML Description': u'',
            'Images': u'ACARA-CAL.png',
            'CA': u'S',
            'Updated': u'',

            # TODO: the rest of the meta keys
        }
        if self.settings.do_specials:
            timezone = TimeUtils._gdrive_tz
            test_dict.update({
                'WNS': u'74.9625',
                'WNF': timezone.localize(datetime(2016, 8, 12, 0)),
                'WNT': timezone.localize(datetime(3000, 9, 1, 0, 0)),
            })
        for key, value in test_dict.items():
            self.assertEqual(text_type(first_prod[key]), text_type(value))

        for key in ['modified_gmt', 'modified_local']:
            self.assertIn(key, first_prod)
            self.assertEqual(type(first_prod[key]), datetime)

        if self.debug:
            print("pformat@to_dict@first_prod:\n%s" % pformat(first_prod.to_dict()))
            print("dir@first_prod:\n%s" % dir(first_prod))
            print("vars@first_prod:\n%s" % vars(first_prod))
            for attr in ["depth"]:
                print("first_prod.%s: %s" % (attr, pformat(getattr(first_prod, attr))))

        third_prod = prod_list[2]
        if self.debug:
            print("pformat@third_prod:\n%s" % pformat(third_prod.to_dict()))
            print("third_prod.to_dict().get('attachment_objects'): %s" % pformat(third_prod.to_dict().get('attachment_objects')))
        self.assertEqual(
            set([attachment.file_name for attachment in third_prod.to_dict().get('attachment_objects')]),
            set(["ACARA-S.png"])
        )

        sixth_prod = prod_list[5]
        if self.debug:
            print("pformat@sixth_prod:\n%s" % pformat(sixth_prod.to_dict()))
            print("sixth_prod.to_dict().get('attachment_objects'): %s" % pformat(sixth_prod.to_dict().get('attachment_objects')))

        self.assertEqual(
            set([attachment.file_name for attachment in sixth_prod.to_dict().get('attachment_objects')]),
            set(["ACARA-S.png"])
        )

        # Test the products which have the same attachment use different attachment objects
        self.assertNotEqual(
            set([id(attachment) for attachment in third_prod.to_dict().get('attachment_objects')]),
            set([id(attachment) for attachment in sixth_prod.to_dict().get('attachment_objects')])
        )


        expected_categories = set([
            u'Product A',
            u'Company A Product A',
            u'Range A',
            u'1 Litre Company A Product A Items',
        ])
        if self.settings.add_special_categories:
            expected_categories.update([
                u'Specials',
                u'Product A Specials',
            ])

        self.assertEquals(
            set([
                cat.title for cat in first_prod.categories.values()
            ]),
            expected_categories
        )

        if self.debug:
            print("parser tree:\n%s" % self.parsers.master.to_str_tree())

        cat_container = self.parsers.master.category_container.container
        cat_list = cat_container(self.parsers.master.categories.values())

        if self.debug:
            print(SanitationUtils.coerce_bytes(
                cat_list.tabulate(tablefmt='simple')
            ))
        if self.settings.add_special_categories:
            self.assertEqual(len(cat_list), 11)
        else:
            self.assertEqual(len(cat_list), 9)
        first_cat = cat_list[0]
        if self.debug:
            print("pformat@first_cat:\n%s" % pformat(first_cat.to_dict()))
            print("first_cat.to_dict().get('attachment_object'): %s" % pformat(first_cat.to_dict().get('attachment_object')))

        self.assertEqual(first_cat.codesum, 'A')
        self.assertEqual(first_cat.title, 'Product A')
        self.assertEqual(first_cat.depth, 0)
        self.assertEqual(
            first_cat.to_dict().get('attachment_object'),
            None
        )

        second_cat = cat_list[1]
        if self.debug:
            print("pformat@second_cat:\n%s" % pformat(second_cat.to_dict()))
            print("second_cat.to_dict().get('attachment_object'): %s" % pformat(second_cat.to_dict().get('attachment_object')))

        self.assertEqual(second_cat.codesum, 'ACA')
        self.assertEqual(second_cat.depth, 1)
        self.assertEqual(second_cat.parent.codesum, 'A')
        self.assertEqual(
            second_cat.to_dict().get('attachment_object').file_name,
            "ACA.jpg"
        )
        second_cat_attachment_id = id(second_cat.to_dict().get('attachment_object'))

        last_cat = cat_list[-1]
        if self.debug:
            print("pformat@last_cat:\n%s" % pformat(last_cat.to_dict()))
            print("last_cat.to_dict().get('attachment_object'): %s" % pformat(last_cat.to_dict().get('attachment_object')))

        self.assertEqual(last_cat.codesum, 'SPA')
        self.assertEqual(last_cat.depth, 1)
        self.assertEqual(last_cat.parent.codesum, 'SP')
        self.assertEqual(
            last_cat.to_dict().get('attachment_object').get('file_name'),
            "ACA.jpg"
        )
        last_cat_attachment_id = id(last_cat.to_dict().get('attachment_object'))

        # This tests that categories which have the same attachment use the same attachment object

        self.assertEqual(
            second_cat_attachment_id,
            last_cat_attachment_id
        )

        prod_a_spec_cat = self.parsers.master.find_category({
            self.parsers.master.category_container.title_key: 'Product A Specials'
        })
        self.assertEqual(
            prod_a_spec_cat[self.parsers.master.category_container.codesum_key],
            'SPA'
        )

        spec_list = SpecialGruopList(self.parsers.special.rule_groups.values())
        if self.debug:
            print(SanitationUtils.coerce_bytes(
                    spec_list.tabulate(tablefmt='simple')
            ))
        first_group = spec_list[0]
        if self.debug:
            print(
                "first group:\n%s\npformat@dict:\n%s\npformat@dir:\n%s\n" %
                (
                    SanitationUtils.coerce_bytes(
                        tabulate(first_group.children, tablefmt='simple')
                    ),
                    pformat(dict(first_group)),
                    pformat(dir(first_group))
                )
            )

    def test_dummy_export_master_parsers(self):
        self.populate_master_parsers()
        export_master_parser(self.settings, self.parsers)

    @pytest.mark.first
    def test_dummy_populate_slave_parsers(self):
        # self.populate_master_parsers()
        self.populate_slave_parsers()
        if self.debug:
            print("slave objects: %s" % len(self.parsers.slave.objects.values()))
            print("slave items: %s" % len(self.parsers.slave.items.values()))
            print("slave products: %s" % len(self.parsers.slave.products.values()))
            print("slave categories: %s" % len(self.parsers.slave.categories.values()))

        if self.debug:
            print("parser tree:\n%s" % self.parsers.slave.to_str_tree())

        self.assertEqual(len(self.parsers.slave.products), 48)
        prod_container = self.parsers.slave.product_container.container
        prod_list = prod_container(self.parsers.slave.products.values())
        first_prod = prod_list[0]
        if self.debug:
            print("first_prod.dict %s" % pformat(dict(first_prod)))
            print("first_prod.categories: %s" % pformat(first_prod.categories))
            print("first_prod.to_dict().get('attachment_objects'): %s" % pformat(first_prod.to_dict().get('attachment_objects')))

        self.assertEqual(first_prod.codesum, "ACARF-CRS")
        # self.assertEqual(first_prod.parent.codesum, "ACARF-CR")

        self.assertEqual(first_prod.product_type, "simple")
        self.assertTrue(first_prod.is_item)
        self.assertTrue(first_prod.is_product)
        self.assertFalse(first_prod.is_category)
        self.assertFalse(first_prod.is_root)
        self.assertFalse(first_prod.is_taxo)
        self.assertFalse(first_prod.is_variable)
        self.assertFalse(first_prod.is_variation)
        test_dict = {
                'height': u'120',
                'length': u'40',
                'weight': u'0.12',
                'width': u'40',
                'DNR': u'8.45',
                'DPR': u'7.75',
                'WNR': u'12.95',
                'WPR': u'11.00',
        }
        if self.settings.do_specials:
            timezone = TimeUtils._wp_srv_tz
            test_dict.update({
                # Note: the slave data was generated in the wrong timezone
                'WNF': "2016-06-14 01:00:00",
                'WNT': "3000-07-01 07:00:00",
                # 'WNF': u'1465837200',
                # 'WNT': u'32519314800',
                'WNS': u'10.36',
            })
        for key, value in test_dict.items():
            self.assertEqual(text_type(first_prod[key]), text_type(value))

        # Remember the test data is deliberately modified to remove one of the categories

        self.assertEquals(
            set([
                category.title \
                for category in first_prod.categories.values()
            ]),
            set([
                '100ml Company A Product A Samples',
                'Company A Product A',
                'Product A'
            ])
        )

        self.assertEquals(
            set([
                image.file_name \
                for image in first_prod.to_dict().get('attachment_objects')
            ]),
            set([
                'ACARF-CRS.png'
            ])
        )

        cat_container = self.parsers.slave.category_container.container
        cat_list = cat_container(self.parsers.slave.categories.values())
        if self.debug:
            print(SanitationUtils.coerce_bytes(
                cat_list.tabulate(tablefmt='simple')
            ))
        self.assertEqual(len(cat_list), 9)
        first_cat = cat_list[0]
        if self.debug:
            print("pformat@first_cat:\n%s" % pformat(first_cat.to_dict()))
            print("first_cat.to_dict().get('attachment_object'): %s" % pformat(first_cat.to_dict().get('attachment_object')))

        self.assertEqual(first_cat.slug, 'product-a')
        self.assertEqual(first_cat.title, 'Product A')
        self.assertEqual(first_cat.api_id, 315)
        self.assertEqual(
            first_cat.to_dict().get('attachment_object').file_name,
            "ACA.jpg"
        )
        self.assertEqual(first_cat.menu_order, 1)

        second_cat = cat_list[1]
        if self.debug:
            print("pformat@second_cat:\n%s" % pformat(second_cat.to_dict()))
            print("second_cat.to_dict().get('attachment_object'): %s" % pformat(second_cat.to_dict().get('attachment_object')))

        self.assertEqual(second_cat.slug, 'product-a-company-a-product-a')
        self.assertEqual(second_cat.title, 'Company A Product A')
        self.assertEqual(second_cat.api_id, 316)
        self.assertEqual(
            second_cat.to_dict().get('attachment_object').file_name,
            "ACA.jpg"
        )
        self.assertEqual(second_cat.menu_order, 0)

        img_container = self.parsers.slave.attachment_container.container
        img_list = img_container(self.parsers.slave.attachments.values())
        if self.debug:
            print(SanitationUtils.coerce_bytes(
                img_list.tabulate(tablefmt='simple')
            ))

        # first_img = img_list[0]
        first_img = img_list.get_by_index('ACARF.jpg')

        if self.debug:
            print(SanitationUtils.coerce_bytes(
                pformat(first_img.items())
            ))

        self.assertEqual(first_img.file_name, 'ACARF.jpg')
        self.assertEqual(first_img.wpid, 24885)
        self.assertEqual(
            first_img['caption'],
            ('With the choice of four, stunning golden brown shades that '
             'develop over 6-8 hours, TechnoTan Classic Tan is the ultimate '
             'Spray on Tan.')
        )
        self.assertEqual(
            first_img['title'],
            'Solution > TechnoTan Solution > Classic Tan (6hr)'
        )

        # last_img = img_list[-1]
        last_img = img_list.get_by_index('ACARA-CAL.png')

        if self.debug:
            print(SanitationUtils.coerce_bytes(
                pformat(last_img.items())
            ))

        self.assertEqual(last_img.file_name, 'ACARA-CAL.png')
        self.assertEqual(last_img.wpid, 24772)
        self.assertEqual(last_img['title'], 'Range A - Style 1 - 1Litre 1')
        self.assertEqual(last_img['slug'], 'range-a-style-1-1litre-1')
        self.assertEqual(last_img['width'], 1200)
        self.assertEqual(last_img['height'], 1200)

    def print_images_summary(self, attachments):
        img_cols = ColDataAttachment.get_col_data_native('report')
        img_table = [img_cols.keys()] + [
            [img_data.get(key) for key in img_cols.keys()]
            for img_data in attachments
        ]
        print(tabulate(img_table))

    def setup_temp_img_dir(self):
        self.settings.thumbsize_x = 1024
        self.settings.thumbsize_y = 768
        suffix='generator_dummy_process_images'
        temp_img_dir = tempfile.mkdtemp(suffix + '_img')
        if self.debug:
            print("working dir: %s" % temp_img_dir)
        self.settings.img_raw_dir = os.path.join(
            temp_img_dir, "imgs_raw"
        )
        shutil.copytree(
            os.path.join(
                TESTS_DATA_DIR, 'imgs_raw'
            ),
            self.settings.img_raw_dir
        )

        self.settings.img_cmp_dir = os.path.join(
            temp_img_dir, "imgs_cmp"
        )

    # @unittest.skip("takes too long")
    @pytest.mark.slow
    def test_dummy_process_images_master(self):
        self.setup_temp_img_dir()
        self.populate_master_parsers()
        if self.settings.do_images:
            process_images(self.settings, self.parsers)
        self.populate_slave_parsers()

        if self.debug:
            self.print_images_summary(self.parsers.master.attachments.values())

        # test resizing
        prod_container = self.parsers.master.product_container.container
        prod_list = prod_container(self.parsers.master.products.values())
        resized_images = 0
        for prod in prod_list:
            for img_data in prod.to_dict().get('attachment_objects'):
                if self.settings.img_cmp_dir in img_data.get('file_path', ''):
                    resized_images += 1
                    self.assertTrue(img_data['width'] <= self.settings.thumbsize_x)
                    self.assertTrue(img_data['height'] <= self.settings.thumbsize_y)

        self.assertTrue(resized_images)

    @pytest.mark.slow
    def test_dummy_images_slave(self):
        self.settings.do_remeta_images = False
        self.settings.do_resize_images = False
        self.populate_master_parsers()
        self.populate_slave_parsers()

        if self.debug:
            self.print_images_summary(self.parsers.slave.attachments.values())
            for img_data in self.parsers.slave.attachments.values():
                print(
                    img_data.file_name,
                    [attach.index for attach in img_data.attaches.objects]
                )

    @pytest.mark.slow
    def test_dummy_do_match_images(self):
        self.populate_master_parsers()
        self.populate_slave_parsers()
        if self.settings.do_images:
            self.setup_temp_img_dir()
            process_images(self.settings, self.parsers)
            if self.debug:
                Registrar.DEBUG_IMG = True
            do_match_images(
                self.parsers, self.matches, self.settings
            )

        if self.debug:
            # self.matches.image.globals.tabulate()
            self.print_matches_summary(self.matches.image)

        self.assertEqual(len(self.matches.image.valid), 51)
        first_match = self.matches.image.valid[0]
        first_master = first_match.m_object
        first_slave = first_match.s_object
        if self.debug:
            print('pformat@first_master:\n%s' % pformat(first_master.to_dict()))
            print('pformat@first_slave:\n%s' % pformat(first_slave.to_dict()))
            master_keys = set(dict(first_master).keys())
            slave_keys = set(dict(first_slave).keys())
            intersect_keys = master_keys.intersection(slave_keys)
            print("intersect_keys:\n")
            for key in intersect_keys:
                out = ("%20s | %50s | %50s" % (
                    SanitationUtils.coerce_ascii(key),
                    SanitationUtils.coerce_ascii(first_master[key])[:50],
                    SanitationUtils.coerce_ascii(first_slave[key])[:50]
                ))
                print(SanitationUtils.coerce_ascii(out))

        for attr, value in {
            'file_name': 'ACA.jpg',
            'title': 'Product A > Company A Product A',
        }.items():
            self.assertEqual(getattr(first_master, attr), value)
        for attr, value in {
            'file_name': 'ACA.jpg',
            'title': 'Solution > TechnoTan Solution',
            'slug': 'solution-technotan-solution',
            'api_id': 24879
        }.items():
            self.assertEqual(getattr(first_slave, attr), value)

        # last_match = self.matches.image.valid[-1]
        # last_master = last_match.m_object
        # last_slave = last_match.s_object
        # if self.debug:
        #     print('pformat@last_master:\n%s' % pformat(last_master.to_dict()))
        #     print('pformat@last_slave:\n%s' % pformat(last_slave.to_dict()))
        #     master_keys = set(dict(last_master).keys())
        #     slave_keys = set(dict(last_slave).keys())
        #     intersect_keys = master_keys.intersection(slave_keys)
        #     print("intersect_keys:\n")
        #     for key in intersect_keys:
        #         out = ("%20s | %50s | %50s" % (
        #             SanitationUtils.coerce_ascii(key),
        #             SanitationUtils.coerce_ascii(last_master[key])[:50],
        #             SanitationUtils.coerce_ascii(last_slave[key])[:50]
        #         ))
        #         print(SanitationUtils.coerce_ascii(out))
        #
        # for match in self.matches.image.valid:
        #     self.assertEqual(
        #         match.m_object.normalized_filename,
        #         match.s_object.normalized_filename
        #     )
        #
        # for attr, value in {
        #     'file_name': 'ACARB-S.jpg',
        #     'title': 'Range B - Extra Dark - 100ml Sample',
        # }.items():
        #     self.assertEqual(getattr(last_master, attr), value)
        # for attr, value in {
        #     'file_name': 'ACARB-S.jpg',
        #     'title': 'Range B - Extra Dark - 100ml Sample 1',
        #     'slug': 'range-b-extra-dark-100ml-sample-1',
        #     'api_id': 24817
        # }.items():
        #     self.assertEqual(getattr(last_slave, attr), value)

    def test_do_match_cat_name(self):
        """
        Test category matching with bad name match:

        there were some urgent errors that need to be reviewed before continuing
        woogenerator/generator.py:2063.main>woogenerator/generator.py:959.do_match_categories | You may want to fix up the following categories before syncing:


        (1) [                              CV|r:305|w:|Pre Tan <ImportWooCategory>                               ] | (0) [                                                                                                    ]
        (0) [                                                                                                    ] | (1) [                           r:15|a:55|VuTan Pre Tan <ImportWooApiCategory>                           ]

        """
        self.settings.schema = "VT"
        self.settings.woo_schemas = ["VT"]
        self.parsers.master = self.settings.master_parser_class(
            **self.settings.master_parser_args
        )

        # Manually insert only relevant items
        self.parsers.master.indices = OrderedDict([
            ('post_status', 54), ('height', 48), ('width', 47),
            ('stock_status', 50), ('weight', 45), ('Images', 51),
            ('length', 46), ('Xero Description', 53), ('CVC', 44),
            ('HTML Description', 52), ('VA', 21), ('PA', 20),
            ('is_sold', 56), ('SCHEDULE', 26), ('is_purchased', 57),
            ('DYNCAT', 23), ('Updated', 22), ('D', 17), ('VISIBILITY', 25),
            ('DYNPROD', 24), ('E', 18), ('RNR', 30), ('RPR', 31), ('WNR', 32),
            ('WPR', 33), ('DNR', 34), ('DPR', 35), ('RNRC', 37), ('RPRC', 38),
            ('WNRC', 39), ('WPRC', 40), ('DNRC', 41), ('DPRC', 42),
            ('stock', 49), ('VT', 12)
        ])

        self.parsers.master.analyse_rows([
            [
                u'Tan Care', u'', u'', u'', u'', u'C', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u''
            ],
            [
                u'', u'VuTan Pre Tan', u'', u'', u'', u'', u'V', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'{"pa_brand":"VuTan"}', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'CV-PT.jpg', u'',
                u'', u'', u'', u'', u''
            ],
            [
                u'', u'', u'Exfoliating Facial Gel', u'', u'', u'', u'', u'EXG',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u''
            ],
            [
                u'', u'', u'', u'Exfoliating Facial Gel - Lavender & Rosemary',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'{"fragrance":"Lavender & Rosemary"}', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', text_type('The VuTan Exfoliating Gel is specially '
                'designed to gently polish away dead skin cells whilst '
                'nourishing the skin. The formula is completely sodium lauryl '
                'sulphate free and contains Aloe Vera, Lavender, Rosemary, Tea '
                'Tree and Geranium Oils. Not to mention the wonderful exfoliating '
                'properties of English Walnut Shell.'), u'', u'', u'', u'', u''
            ],
            [
                u'', u'', u'', u'', u'250ml (jar)', u'', u'', u'', u'', u'250',
                u'Y', u'', u'S', u'', u'', u'', u'', u'', u'E', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'VTCARE1', u'$19.95',
                u'$17.95', u'$11.95', u'$10.16', u'$7.17', u'$6.87', u'',
                u'$20.91', u'$17.78', u'$11.95', u'$10.16', u'$7.17', u'$6.87',
                u'$9.56', u'1.00', u'0.32', u'94', u'94', u'55', u'', u'',
                u'CVEXG-250.png', u'', u'', u'trash', u'', u'', u''
            ]
        ])

        self.assertTrue(len(self.parsers.master.categories) > 0)

        self.parsers.slave = self.settings.slave_parser_class(
            **self.settings.slave_parser_args
        )

        self.parsers.slave.process_api_categories_gen([
            OrderedDict([
                ('display', u'default'), ('HTML Description', u'Tan Care'),
                ('slug', u'tan-care'), ('title', 'Tan Care'), ('ID', 54),
                ('rowcount', 14), ('descsum', u'Tan Care'), ('parent_id', 0),
                ('attachment_object', []), ('type', 'category'),
                ('codesum', u'tan-care'), ('source', 'woocommerce-vt-test'),
                ('_row', []), ('cat_name', 'Tan Care')
            ]),
            OrderedDict([
                ('display', u'default'), ('HTML Description', u'VuTan Pre Tan'),
                ('slug', u'tan-care-pre-tan'), ('title', 'VuTan Pre Tan'),
                ('ID', 55), ('rowcount', 15), ('descsum', u'VuTan Pre Tan'),
                ('parent_id', 54), ('attachment_object', []),
                ('type', 'category'), ('codesum', u'tan-care-pre-tan'),
                ('source', 'woocommerce-vt-test'), ('_row', []), ('cat_name', 'VuTan Pre Tan')
            ])
        ])

        self.assertTrue(len(self.parsers.slave.categories) > 0)

        do_match_categories(
            self.parsers, self.matches, self.settings
        )

        self.assertTrue(len(self.matches.category.valid) > 1)
        for index in ['Tan Care', 'Pre Tan']:
            self.assertTrue(index in self.matches.category.globals.m_indices)

        self.parsers.slave.clear_transients()

        self.parsers.slave.process_api_categories_gen([
            OrderedDict([
                ('display', u'default'), ('HTML Description', u'Tan Care'),
                ('slug', u'tan-care'), ('cat_name', 'Tan Care'), ('ID', 54),
                ('rowcount', 15), ('descsum', u'Tan Care'), ('parent_id', 0),
                ('attachment_object', []), ('type', 'category'), ('title', 'Tan Care'),
                ('codesum', u'tan-care'), ('source', 'woocommerce-vt-test'),
                ('_row', []),
            ]),
            OrderedDict([
                ('display', u'default'), ('HTML Description', u'VuTan Pre Tan'),
                ('cat_name', 'Pre Tan'), ('parent_id', 54),
                ('slug', u'tan-care-pre-tan'), ('rowcount', 16),
                ('descsum', u'VuTan Pre Tan'), ('attachment_object', []),
                ('ID', 55), ('type', 'category'),
                ('codesum', u'tan-care-pre-tan'),
                ('source', 'woocommerce-vt-test'),
                ('_row', []), ('title', 'Pre Tan')
            ])
        ])

        self.assertTrue(len(self.matches.category.valid) > 1)
        for index in ['Tan Care', 'Pre Tan']:
            self.assertTrue(index in self.matches.category.globals.m_indices)


    def test_do_match_cat_ambiguous_title(self):
        self.settings.schema = "VT"
        self.settings.woo_schemas = ["VT"]
        self.parsers.master = self.settings.master_parser_class(
            **self.settings.master_parser_args
        )

        # Manually insert only relevant items
        self.parsers.master.indices = OrderedDict([
            ('post_status', 54), ('height', 48), ('width', 47),
            ('stock_status', 50), ('weight', 45), ('Images', 51),
            ('length', 46), ('Xero Description', 53), ('CVC', 44),
            ('HTML Description', 52), ('VA', 21), ('PA', 20),
            ('is_sold', 56), ('SCHEDULE', 26), ('is_purchased', 57),
            ('DYNCAT', 23), ('Updated', 22), ('D', 17), ('VISIBILITY', 25),
            ('DYNPROD', 24), ('E', 18), ('RNR', 30), ('RPR', 31), ('WNR', 32),
            ('WPR', 33), ('DNR', 34), ('DPR', 35), ('RNRC', 37), ('RPRC', 38),
            ('WNRC', 39), ('WPRC', 40), ('DNRC', 41), ('DPRC', 42),
            ('stock', 49), ('VT', 12)
        ])

        self.parsers.master.analyse_rows([
            # rowcount = 3
            [
                u'Solution', u'', u'', u'', u'', u'S', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'wholesale | local', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u''
            ],
            # rowcount = 99
            [
                u'', u'VuTan Solution', u'', u'', u'', u'', u'V', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'{"pa_brand":"VuTan"}', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', (u"VuTan have "
                u"developed a range of unique blends in a number of shades to "
                u"suit all skin types. All VuTan's tanning solutions are create"
                u"d using the finest naturally derived botanical and certified "
                u"organic ingredients."), u'', u'', u'', u'', u''
            ],
            # rowcount = 104
            [
                u'', u'', u'', u'Vu2Tan (2hr) - Caramel', u'', u'', u'', u'',
                u'CA', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'{"pa_colour":"Light"}', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'',
                (u'Vu2Tan is perfect for tanners looking for an authentic '
                 u'Australian glow, without compromising on quality. Available '
                 u'in five rich, ash-brown shades to suit all skin tones. Vu2Tan'
                 u' is ready to wash off in just 2 hours, yet it continues to '
                 u'develop for a further 12-24 hours. Specially formulated with'
                 u' Erythrulose, Eco Certified DHA, and natural ingredients suc'
                 u'h as Aloe Vera, Kakadu Plum and a unique selection of Certif'
                 u'ied Organic herbal extracts. Caramel is recommended for fair'
                 u' skin tones.'), u'', u'', u'', u'', u''
            ],
            # rowcount = 105
            [
                u'', u'', u'', u'', u'1Litre', u'', u'', u'', u'', u'L', u'Y',
                u'', u'S', u'', u'', u'', u'', u'', u'E', u'', u'', u'', u'',
                u'', u'', u'', u'', u'', u'', u'VTSOL1', u'-', u'-', u'$99.95',
                u'$84.96', u'$59.97', u'$57.47', u'', u'', u'', u'$99.95',
                u'$84.96', u'$59.97', u'$57.47', u'$79.96', u'1.00', u'1.08',
                u'85', u'85', u'235', u'', u'', u'SVV2-CAL.png', u'', u'', u'',
                u'', u'', u''
            ],
        ])

        self.assertTrue(len(self.parsers.master.categories) > 0)

        self.parsers.slave = self.settings.slave_parser_class(
            **self.settings.slave_parser_args
        )

        self.parsers.slave.process_api_categories_gen([
            OrderedDict([
                ('display', u'default'), ('HTML Description', u'Solution'),
                ('cat_name', 'Solution'), ('slug', u'solution'),
                ('parent_id', 0), ('descsum', u'Solution'),
                ('attachment_object', []), ('menu_order', 99),
                ('type', 'category'), ('ID', 29), ('codesum', u'solution'),
                ('source', 'woocommerce-vt-test'), ('rowcount', 5),
                ('_row', []), ('title', 'Solution')]),
        ])

        do_match_categories(
            self.parsers, self.matches, self.settings
        )

        self.assertEqual(len(self.matches.category.valid), 1)
        self.assertEqual(self.matches.category.valid[0].m_object.codesum , 'SV')


    @pytest.mark.slow
    def test_dummy_do_match_cat_img(self):
        self.setup_temp_img_dir()
        self.populate_master_parsers()
        self.populate_slave_parsers()

        if self.settings.do_images:
            process_images(self.settings, self.parsers)
            do_match_images(
                self.parsers, self.matches, self.settings
            )
            do_merge_images(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_updates_images_master(
                self.updates, self.parsers, self.results, self.settings
            )
            self.do_updates_images_slave_mocked()

        if self.settings.do_categories:
            do_match_categories(
                self.parsers, self.matches, self.settings
            )

        if self.debug:
            self.matches.category.globals.tabulate()
            self.print_matches_summary(self.matches.category)

        self.assertEqual(len(self.matches.category.globals), 9)
        first_match = self.matches.category.valid[2]
        first_master = first_match.m_object
        first_slave = first_match.s_object
        if self.debug:
            print('pformat@first_master:\n%s' % pformat(first_master.to_dict()))
            print('pformat@first_slave:\n%s' % pformat(first_slave.to_dict()))
            master_keys = set(dict(first_master).keys())
            slave_keys = set(dict(first_slave).keys())
            intersect_keys = master_keys.intersection(slave_keys)
            print("intersect_keys:\n")
            for key in intersect_keys:
                print("%20s | %50s | %50s" % (
                    str(key), str(first_master[key])[:50], str(first_slave[key])[:50]
                ))

        for match in self.matches.category.globals:
            self.assertEqual(match.m_object.title, match.s_object.title)

        last_slaveless_match = self.matches.category.slaveless[-1]
        last_slaveless_master = last_slaveless_match.m_object
        if self.debug:
            print(
                'pformat@last_slaveless_master.to_dict:\n%s' % \
                pformat(last_slaveless_master.to_dict())
            )
        # This ensures that specials categories correctly match with existing
        self.assertTrue(
            last_slaveless_master.row
        )
        self.assertEqual(
            last_slaveless_master.to_dict().get('attachment_object').file_name,
            'ACA.jpg'
        )




    @pytest.mark.slow
    def test_dummy_do_merge_images_only(self):
        """
        Assume image files are newer than example json image mod times
        """
        self.settings.do_resize_images = True
        self.settings.do_remeta_images = False
        self.setup_temp_img_dir()
        self.populate_master_parsers()
        self.populate_slave_parsers()

        if self.settings.do_images:
            process_images(self.settings, self.parsers)
            do_match_images(
                self.parsers, self.matches, self.settings
            )
            do_merge_images(
                self.matches, self.parsers, self.updates, self.settings
            )

        if self.debug:
            print("img sync handles: %s" % self.settings.sync_handles_img)
            self.print_updates_summary(self.updates.image)
            for update in self.updates.image.slave:
                print(update.tabulate())
        self.assertEqual(len(self.updates.image.slave), 51)
        self.assertEqual(len(self.updates.image.problematic), 0)
        if self.debug:
            print("slave updates:")
            for sync_update in self.updates.image.slave:
                print(sync_update.tabulate())
        # sync_update = self.updates.image.problematic[0]
        # try:
        #     if self.debug:
        #         self.print_update(sync_update)
        #     # TODO: test this?
        # except AssertionError as exc:
        #     self.fail_syncupdate_assertion(exc, sync_update)

        sync_update = self.updates.image.slave.get_by_ids("-1|ACA.jpg", 24879)
        try:
            if self.debug:
                self.print_update(sync_update)
            master_desc = (
                "Company A have developed a range of unique blends in 16 "
                "shades to suit all use cases. All Company A's products "
                "are created using the finest naturally derived botanical "
                "and certified organic ingredients."
            )
            slave_desc = (
                "TechnoTan have developed a range of unique blends in 16 "
                "shades to suit all skin types. All TechnoTan's tanning solutions "
                "are created using the finest naturally derived botanical "
                "and certified organic ingredients."
            )
            master_title = 'Product A > Company A Product A'
            slave_title = 'Solution > TechnoTan Solution'

            self.assertEqual(
                sync_update.old_m_object_core['title'],
                master_title
            )
            self.assertEqual(
                sync_update.old_s_object_core['title'],
                slave_title
            )
            self.assertEqual(
                sync_update.new_s_object_core['title'],
                master_title
            )
            self.assertEqual(
                sync_update.old_m_object_core['post_excerpt'],
                master_desc
            )
            self.assertEqual(
                SanitationUtils.normalize_unicode(sync_update.old_s_object_core['post_excerpt']),
                slave_desc
            )
            self.assertEqual(
                sync_update.new_s_object_core['post_excerpt'],
                master_desc
            )
            self.assertFalse(sync_update.old_s_object_core['alt_text'])
            self.assertEqual(
                sync_update.new_s_object_core['alt_text'],
                master_title
            )
            self.assertFalse(sync_update.old_s_object_core['post_content'])
            self.assertEqual(
                sync_update.new_s_object_core['post_content'],
                master_desc
            )
            self.assertTrue(
                sync_update.m_time
            )
            self.assertTrue(
                sync_update.s_time
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)
        self.assertEqual(len(self.updates.image.master), 51)
        if self.debug:
            print("master updates:")
            for sync_update in self.updates.image.master:
                print(sync_update.tabulate())
        # sync_update = self.updates.image.master[0]
        sync_update = self.updates.image.master.get_by_ids("-1|ACA.jpg", 24879)
        try:
            if self.debug:
                self.print_update(sync_update)
            master_slug = ''
            slave_slug = 'solution-technotan-solution'
            self.assertEqual(
                sync_update.old_m_object_core['slug'],
                master_slug
            )
            self.assertEqual(
                sync_update.old_s_object_core['slug'],
                slave_slug
            )
            self.assertEqual(
                sync_update.new_m_object_core['slug'],
                slave_slug
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

        if self.debug:
            print("slaveless objects")
            for update in self.updates.image.slaveless:
                slave_gen_object = update.old_m_object_gen
                print(slave_gen_object)

        self.assertEqual(len(self.updates.image.slaveless), 2)
        # sync_update = self.updates.image.slaveless[0]
        sync_update = self.updates.image.slaveless.get_by_ids("14|ACARA-CCL.png", "")
        try:
            if self.debug:
                self.print_update(sync_update)
            slave_gen_object = sync_update.old_m_object_gen
            title = 'Range A - Style 2 - 1Litre'
            content = (
                "Company A have developed a range of unique blends in 16 shades to "
                "suit all use cases. All Company A's products are created using the "
                "finest naturally derived botanical and certified organic ingredients."
            )
            self.assertEqual(
                self.parsers.master.attachment_container.get_title(slave_gen_object),
                title
            )
            self.assertEqual(
                self.parsers.master.attachment_container.get_alt_text(slave_gen_object),
                title
            )
            self.assertEqual(
                self.parsers.master.attachment_container.get_description(slave_gen_object),
                content
            )
            self.assertEqual(
                self.parsers.master.attachment_container.get_caption(slave_gen_object),
                content
            )
            self.assertEqual(
                FileUtils.get_path_basename(
                    self.parsers.master.attachment_container.get_file_path(slave_gen_object),
                ),
                "ACARA-CCL.png"
            )
            self.assertTrue(
                sync_update.m_time
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

    def do_updates_images_slave_mocked(self):
        with mock.patch(
            MockUtils.get_mock_name(
                self.settings.__class__,
                'slave_img_sync_client_class'
            ),
            new_callable=mock.PropertyMock,
            return_value=self.settings.null_client_class
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'coldata_class'
            ),
            new_callable=mock.PropertyMock,
            return_value=ColDataAttachment
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'coldata_target'
            ),
            new_callable=mock.PropertyMock,
            return_value=self.settings.coldata_img_target
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'coldata_target_write'
            ),
            new_callable=mock.PropertyMock,
            return_value=self.settings.coldata_img_target_write
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'endpoint_plural'
            ),
            new_callable=mock.PropertyMock,
            return_value='media'
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'endpoint_singular'
            ),
            new_callable=mock.PropertyMock,
            return_value='media'
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'file_path_handle'
            ),
            new_callable=mock.PropertyMock,
            return_value='file_path'
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'source_url_handle'
            ),
            new_callable=mock.PropertyMock,
            return_value='source_url'
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'primary_key_handle'
            ),
            new_callable=mock.PropertyMock,
            return_value='id'
        ):
            self.settings.update_slave = True
            do_updates_images_slave(
                self.updates, self.parsers, self.results, self.settings
            )
            self.settings.update_slave = False

    @pytest.mark.slow
    def test_dummy_do_updates_images_slave(self):
        self.setup_temp_img_dir()
        self.populate_master_parsers()
        self.populate_slave_parsers()

        if self.settings.do_images:
            process_images(self.settings, self.parsers)
            do_match_images(
                self.parsers, self.matches, self.settings
            )
            do_merge_images(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_updates_images_master(
                self.updates, self.parsers, self.results, self.settings
            )
            self.do_updates_images_slave_mocked()

        if self.debug:
            print('image update results: %s' % self.results.image)

        self.assertEqual(len(self.results.image.new.successes), 2)

        sync_update = self.results.image.new.successes[0]
        # sync_update = self.results.image.new.successes.get_by_ids("14|ACARA-CCL.png", 100000)
        try:
            if self.debug:
                self.print_update(sync_update)
            self.assertEqual(
                sync_update.new_s_object_core['id'],
                100000
            )
            self.assertEqual(
                sync_update.old_m_object_gen['ID'],
                100000
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)
        sync_update = self.results.image.new.successes[-1]
        # sync_update = self.results.image.new.successes.get_by_ids("48|ACARC-CL.jpg", 100001)
        try:
            if self.debug:
                self.print_update(sync_update)
            self.assertEqual(
                sync_update.new_s_object_core['id'],
                100001
            )
            self.assertEqual(
                sync_update.old_m_object_gen['ID'],
                100001
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

        self.assertEqual(
            len(self.results.image.successes),
            51
        )
        sync_update = self.results.image.successes[0]
        # sync_update = self.results.image.successes.get_by_ids("-1|ACA.jpg", 100002)
        try:
            if self.debug:
                self.print_update(sync_update)
            self.assertEqual(
                sync_update.new_s_object_core['id'],
                100002
            )
            self.assertEqual(
                sync_update.old_m_object_gen['ID'],
                100002
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

        sync_update = self.results.image.successes[-1]
        # sync_update = self.results.image.successes.get_by_ids("41|ACARB-S.jpg", 100052)
        try:
            if self.debug:
                self.print_update(sync_update)
            self.assertEqual(
                sync_update.new_s_object_core['id'],
                100052
            )
            self.assertEqual(
                sync_update.old_m_object_gen['ID'],
                100052
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

    @pytest.mark.first
    def test_dummy_do_merge_categories_only(self):
        self.settings.do_images = False
        self.populate_master_parsers()
        self.populate_slave_parsers()
        if self.settings.do_categories:
            do_match_categories(
                self.parsers, self.matches, self.settings
            )
            do_merge_categories(
                self.matches, self.parsers, self.updates, self.settings
            )

        if self.debug:
            self.print_updates_summary(self.updates.category)
        self.assertEqual(len(self.updates.category.master), 9)
        # sync_update = self.updates.category.master[1]
        sync_update = self.updates.category.master.get_by_ids(4, 316)
        try:
            if self.debug:
                self.print_update(sync_update)

            updates_native = sync_update.get_slave_updates_native()

            master_desc = (
                "Company A have developed a range of unique blends in 16 "
                "shades to suit all use cases. All Company A's products "
                "are created using the finest naturally derived botanical "
                "and certified organic ingredients."
            )
            slave_desc = "Company A have developed stuff"
            self.assertEqual(
                sync_update.old_m_object['descsum'],
                master_desc
            )
            self.assertEqual(
                sync_update.old_s_object['descsum'],
                slave_desc
            )
            self.assertEqual(
                sync_update.new_s_object['descsum'],
                master_desc
            )
            self.assertIn(
                ('description', master_desc),
                updates_native.items()
            )

            master_title = "Company A Product A"
            self.assertEqual(
                sync_update.old_m_object['title'],
                master_title
            )
            self.assertEqual(
                sync_update.old_s_object['title'],
                master_title
            )
            self.assertNotIn(
                'name',
                updates_native
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

        if self.debug:
            print("slaveless objects")
            for update in self.updates.category.slaveless:
                slave_gen_object = update.old_m_object_gen
                print(slave_gen_object)

        self.assertEqual(
            set([
                self.parsers.slave.category_container.get_title(gen_data.old_m_object_gen)
                for gen_data in self.updates.category.slaveless
            ]),
            set(['Specials', 'Product A Specials'])
        )

        # sync_update = self.updates.category.slaveless[-1]
        sync_update = self.updates.category.slaveless.get_by_ids(167, '')
        try:
            if self.debug:
                self.print_update(sync_update)
            master_title = "Product A Specials"
            master_desc = master_title
            self.assertEqual(
                sync_update.old_m_object_core['title'],
                master_title
            )
            self.assertEqual(
                sync_update.new_s_object_core['title'],
                master_title
            )
            self.assertEqual(
                sync_update.old_m_object_core['description'],
                master_desc
            )
            self.assertEqual(
                sync_update.new_s_object_core['description'],
                master_desc
            )
            self.assertEqual(
                bool(self.settings.do_images),
                'image' in sync_update.new_s_object_core,
                "images should be excluded from new slave objects if do_images disabled, contrapositive is true"
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

    def do_updates_categories_slave_mocked(self):
        with mock.patch(
            MockUtils.get_mock_name(
                self.settings.__class__,
                'slave_cat_sync_client_class'
            ),
            new_callable=mock.PropertyMock,
            return_value=self.settings.null_client_class
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'coldata_class'
            ),
            new_callable=mock.PropertyMock,
            return_value=ColDataWcProdCategory
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'coldata_target'
            ),
            new_callable=mock.PropertyMock,
            return_value=self.settings.coldata_cat_target
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'coldata_target_write'
            ),
            new_callable=mock.PropertyMock,
            return_value=self.settings.coldata_cat_target_write
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'endpoint_plural'
            ),
            new_callable=mock.PropertyMock,
            return_value='categories'
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'endpoint_singular'
            ),
            new_callable=mock.PropertyMock,
            return_value='category'
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'primary_key_handle'
            ),
            new_callable=mock.PropertyMock,
            return_value='term_id'
        ):
            self.settings.update_slave = True
            do_updates_categories_slave(
                self.updates, self.parsers, self.results, self.settings
            )
            self.settings.update_slave = False

    @pytest.mark.last
    def test_dummy_do_updates_categories_slave_only(self):
        self.settings.do_images = False
        self.populate_master_parsers()
        self.populate_slave_parsers()
        if self.settings.do_categories:
            do_match_categories(
                self.parsers, self.matches, self.settings
            )
            do_merge_categories(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_updates_categories_master(
                self.updates, self.parsers, self.results, self.settings
            )
            self.do_updates_categories_slave_mocked()

        if self.debug:
            print('category update results: %s' % self.results.category)

        self.assertEqual(
            len(self.results.category.successes),
            9
        )

        self.assertEqual(
            len(self.results.category.new.successes),
            2
        )
        index_fn = self.parsers.master.category_indexer
        sync_update = self.results.category.new.successes.pop(0)
        # sync_update = self.results.category.new.successes.get_by_ids(166, 100000)
        try:
            if self.debug:
                self.print_update(sync_update)
            new_s_object_gen = sync_update.new_s_object
            if self.debug:
                pprint(new_s_object_gen.to_dict())
            self.assertEqual(
                new_s_object_gen.title,
                'Specials',
            )
            self.assertEqual(
                new_s_object_gen.wpid,
                100000
            )
            master_index = index_fn(sync_update.old_m_object)
            original_master = self.parsers.master.categories[master_index]
            self.assertEqual(
                original_master.wpid,
                100000
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

        sync_update = self.results.category.new.successes.pop(0)
        # sync_update = self.results.category.new.successes.get_by_ids(167, 100001)
        try:
            if self.debug:
                self.print_update(sync_update)
            new_s_object_gen = sync_update.new_s_object
            if self.debug:
                pprint(new_s_object_gen.items())
            self.assertEqual(
                new_s_object_gen.title,
                'Product A Specials',
            )
            self.assertEqual(
                new_s_object_gen.wpid,
                100001
            )
            master_index = index_fn(sync_update.old_m_object)
            original_master = self.parsers.master.categories[master_index]
            self.assertEqual(
                original_master.wpid,
                100001
            )
            self.assertEqual(
                original_master.parent.wpid,
                100000
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

    @pytest.mark.slow
    def test_dummy_do_merge_cat_img(self):
        self.setup_temp_img_dir()
        self.populate_master_parsers()
        self.populate_slave_parsers()

        if self.settings.do_images:
            process_images(self.settings, self.parsers)
            do_match_images(
                self.parsers, self.matches, self.settings
            )
            do_merge_images(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_updates_images_master(
                self.updates, self.parsers, self.results, self.settings
            )
            self.do_updates_images_slave_mocked()

        if self.settings.do_categories:
            do_match_categories(
                self.parsers, self.matches, self.settings
            )
            do_merge_categories(
                self.matches, self.parsers, self.updates, self.settings
            )

        if self.debug:
            self.print_updates_summary(self.updates.category)

        expected_sub_img_handles = ['source_url', 'title', 'id']
        unexpected_sub_img_handles = ['modified_gmt', 'created_gmt']
        expected_sub_img_cols = ['src', 'title', 'id']
        def sync_update_cat_rudiments_test(sync_update):
            if getattr(sync_update, 'new_s_object_core') \
            and sync_update.new_s_object_core.get('image'):
                new_s_core_img = sync_update.new_s_object_core['image']
                for key in expected_sub_img_handles:
                    self.assertIn(
                        key,
                        new_s_core_img
                    )
                for key in unexpected_sub_img_handles:
                    self.assertNotIn(
                        key,
                        new_s_core_img
                    )
            if sync_update.get_slave_updates().get('image'):
                slave_updates_core_img = sync_update.get_slave_updates().get('image')
                for key in expected_sub_img_handles:
                    self.assertIn(
                        key,
                        slave_updates_core_img
                    )
                for key in unexpected_sub_img_handles:
                    self.assertNotIn(
                        key,
                        slave_updates_core_img
                    )
                slave_updates_native_img = sync_update.get_slave_updates_native().get('image')
                for key in expected_sub_img_cols:
                    self.assertIn(
                        key,
                        slave_updates_native_img
                    )

        self.assertEqual(len(self.updates.category.master), 9)

        for sync_update in self.updates.category.master:
            try:
                sync_update_cat_rudiments_test(sync_update)
            except AssertionError as exc:
                self.fail_syncupdate_assertion(exc, sync_update)

        """
update <       4 |     316 ><class 'woogenerator.syncupdate.SyncUpdateCatWoo'>
---
M:ACA|r:4|w:|Company A Product A <ImportWooCategory>
{'CA': u'',
 'CVC': u'',
 'D': u'',
 'DNR': u'',
 'DPR': u'',
 'DYNCAT': u'',
 'DYNPROD': u'',
 'E': u'',
 'HTML Description': u"Company A have developed a range of unique blends in 16 shades to suit all use cases. All Company A's products are created using the finest naturally derived botanical and certified organic ingredients.",
 'ID': '',
 'Images': u'ACA.jpg',
 'PA': u'{"pa_brand":"Company A"}',
 'RNR': u'',
 'RPR': u'',
 'SCHEDULE': u'EOFY2016-ACA',
 'Updated': u'',
 'VA': u'',
 'VISIBILITY': u'local',
 'WNR': u'',
 'WPR': u'',
 'Xero Description': u'',
 '_row': [],
 'attachment_object': -1|ACA.jpg <ImportWooImg>,
 'attachment_objects': OrderedDict([(u'-1|ACA.jpg', -1|ACA.jpg <ImportWooImg>)]),
 'backorders': 'no',
 'catalog_visibility': 'visible',
 'code': u'CA',
 'codesum': u'ACA',
 'descsum': u"Company A have developed a range of unique blends in 16 shades to suit all use cases. All Company A's products are created using the finest naturally derived botanical and certified organic ingredients.",
 'download_expiry': -1,
 'download_limit': -1,
 'featured': 'no',
 'fullname': u'Company A Product A',
 'fullnamesum': u'Product A > Company A Product A',
 'height': u'',
 'imgsum': u'ACA.jpg',
 'is_purchased': u'',
 'is_sold': u'',
 'itemsum': '',
 'length': u'',
 'modified_gmt': datetime.datetime(2017, 12, 5, 16, 56, 30, tzinfo=<UTC>),
 'modified_local': datetime.datetime(2017, 12, 6, 2, 36, 30),
 'name': u'Company A Product A',
 'post_status': u'',
 'prod_type': 'simple',
 'rowcount': 4,
 'slug': '',
 'stock': u'',
 'stock_status': u'',
 'tax_status': 'taxable',
 'taxosum': u'Product A > Company A Product A',
 'title': u'Company A Product A',
 'weight': u'',
 'width': u''}
S:r:2|a:316|Company A Product A <ImportWooApiCategory>
{'HTML Description': u'Company A have developed stuff',
 'ID': 316,
 '_row': [],
 'api_data': {u'_links': {u'collection': [{u'href': u'http://localhost:18080/wptest/wp-json/wc/v2/products/categories'}],
                          u'self': [{u'href': u'http://localhost:18080/wptest/wp-json/wc/v2/products/categories/316'}],
                          u'up': [{u'href': u'http://localhost:18080/wptest/wp-json/wc/v2/products/categories/315'}]},
              u'count': 48,
              u'description': u'Company A have developed stuff',
              u'display': u'default',
              u'id': 316,
              u'image': {u'alt': u'',
                         u'date_created': u'2017-11-08T20:55:43',
                         u'date_created_gmt': u'2017-11-08T20:55:43',
                         u'date_modified': u'2017-11-08T20:55:43',
                         u'date_modified_gmt': u'2017-11-08T20:55:43',
                         u'id': 24879,
                         u'src': u'http://localhost:18080/wptest/wp-content/uploads/2017/11/ACA.jpg',
                         u'title': u'Solution &gt; TechnoTan Solution'},
              u'menu_order': 0,
              u'name': u'Company A Product A',
              u'parent': 315,
              u'slug': u'product-a-company-a-product-a',
              u'type': u'category'},
 'attachment_object': 100002|ACA.jpg <ImportWooApiImg>,
 'attachment_objects': OrderedDict([(24879, 100002|ACA.jpg <ImportWooApiImg>)]),
 'codesum': u'product-a-company-a-product-a',
 'descsum': u'Company A have developed stuff',
 'display': u'default',
 'parent_id': 315,
 'rowcount': 2,
 'slug': u'product-a-company-a-product-a',
 'source': 'woocommerce-test',
 'title': 'Company A Product A',
 'type': 'category'}
warnings:
-
Column       Reason    Subject           Old                                                 New                                                   M TIME    S TIME  EXTRA
-----------  --------  ----------------  --------------------------------------------------  --------------------------------------------------  --------  --------  -------
description  updating  woocommerce-test  Company A have developed stuff                      Company A have developed a range of unique blends          0         0
menu_order   updating  woocommerce-test  2                                                   4                                                          0         0
image        updating  woocommerce-test  OrderedDict([('modified_gmt', datetime.datetime(20  OrderedDict([('modified_gmt', datetime.datetime(20         0         0
-
Column          Reason        Subject      Old    New                              M TIME    S TIME  EXTRA
--------------  ------------  -----------  -----  -----------------------------  --------  --------  -------
term_parent_id  merging-read  gdrive-test         315                                   0         0
term_id         merging       gdrive-test         316                                   0         0
slug            merging       gdrive-test         product-a-company-a-product-a         0         0
display         merging       gdrive-test         default                               0         0
passes:
-
Column    Reason     Master               Slave                  M TIME    S TIME  EXTRA
--------  ---------  -------------------  -------------------  --------  --------  -------
title     identical  Company A Product A  Company A Product A         0         0
probbos:

        """
        sync_update = self.updates.category.master.get_by_ids(4, 316)

        try:
            if self.debug:
                self.print_update(sync_update)
            m_attachment = sync_update.old_m_object_gen.to_dict()['attachment_object']
            self.assertEqual(
                m_attachment.get('file_name'),
                'ACA.jpg'
            )
            self.assertEqual(
                m_attachment.get('ID'),
                100002
            )
            s_attachment = sync_update.old_s_object_gen.to_dict()['attachment_object']
            self.assertEqual(
                s_attachment.get('file_name'),
                'ACA.jpg'
            )
            self.assertEqual(
                s_attachment.get('ID'),
                24879
            )
            self.assertEqual(
                sync_update.old_m_object_core['image']['id'],
                100002
            )
            self.assertEqual(
                sync_update.old_s_object_core['image']['id'],
                24879
            )
            self.assertEqual(
                sync_update.new_s_object_core['image']['id'],
                100002
            )
            if self.debug:
                print(
                    "sync warnings core img:\n%s" % \
                    pformat(sync_update.sync_warnings_core.items())
                )
                print(
                    "slave img updates native: \n%s" % \
                    pformat(sync_update.get_slave_updates_native())
                )
            self.assertTrue(
                sync_update.sync_warnings_core.get('image')
            )
            self.assertTrue(
                sync_update.get_slave_updates_native().get('image')
            )
            self.assertTrue(
                sync_update.get_slave_updates_native().get('image').get('id'),
                100002
            )

        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

        # TODO: this
        if self.debug:
            import pudb; pudb.set_trace()
        self.assertEqual(len(self.updates.category.slave), 9)
        for sync_update in self.updates.category.slave:
            try:
                sync_update_cat_rudiments_test(sync_update)
            except AssertionError as exc:
                self.fail_syncupdate_assertion(exc, sync_update)
        """
update <       8 |     317 >OLD
taxos                 descsum                                            title    parent_id    ID    slug
--------------------  -------------------------------------------------  -------  -----------  ----  -------------------------------------
ACARA|r:8|w:|Range A  Company A have developed a range of unique blends  Range A
r:3|a:317|Range A                                                        Range A  316          317   product-a-company-a-product-a-range-a
CHANGES (6!1)
-
Column       Reason     Subject           Old                                                 New                                                   M TIME    S TIME  EXTRA
-----------  ---------  ----------------  --------------------------------------------------  --------------------------------------------------  --------  --------  -------
description  inserting  woocommerce-test                                                      Company A have developed a range of unique blends          0         0
image        updating   woocommerce-test  {'source_url': u'http://localhost:18080/wptest/wp-  {'source_url': u'/var/folders/sx/43gc_nmj43dcwbw15         0         0
-
Column          Reason        Subject      Old    New                                      M TIME    S TIME  EXTRA
--------------  ------------  -----------  -----  -------------------------------------  --------  --------  -------
term_parent_id  merging-read  gdrive-test         316                                           0         0
term_id         merging       gdrive-test         317                                           0         0
slug            merging       gdrive-test         product-a-company-a-product-a-range-a         0         0
display         merging       gdrive-test         default                                       0         0
gdrive-test CHANGES
  ID    term_parent_id    term_id  slug                                   display
----  ----------------  ---------  -------------------------------------  ---------
   8               316        317  product-a-company-a-product-a-range-a  default
woocommerce-test CHANGES
  ID  description                                                                                                                                                                                                 image
----  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 317  Company A have developed a range of unique blends in 16 shades to suit all use cases. All Company A's products are created using the finest naturally derived botanical and certified organic ingredients.  OrderedDict([('src', u'/var/folders/sx/43gc_nmj43dcwbw15n3pwm440000gn/T/tmpGiIcYKgenerator_dummy_process_images_img/imgs_cmp/images-CA/ACARA.jpg'), ('id', 100003), ('title', u'Product A > Company A Product A > Range A')])
PASSES (1)
-
Column    Reason     Master    Slave      M TIME    S TIME  EXTRA
--------  ---------  --------  -------  --------  --------  -------
title     identical  Range A   Range A         0         0

NEW
taxos                              descsum                                            title      parent_id    ID  slug
---------------------------------  -------------------------------------------------  -------  -----------  ----  -------------------------------------
ACA|r:8|w:317|Company A Product A  Company A have developed a range of unique blends  Range A          316   317  product-a-company-a-product-a-range-a
r:3|a:317|Range A                  Company A have developed a range of unique blends  Range A          316   317  product-a-company-a-product-a-range-a
        """
        sync_update = self.updates.category.slave.get_by_ids(8,317)
        try:
            if self.debug:
                self.print_update(sync_update)

            m_attachment = sync_update.old_m_object_gen.to_dict()['attachment_object']
            self.assertEqual(
                m_attachment.get('file_name'),
                'ACARA.jpg'
            )
            self.assertEqual(
                m_attachment.get('ID'),
                100003
            )
            s_attachment = sync_update.old_s_object_gen.to_dict()['attachment_object']
            self.assertEqual(
                s_attachment.get('file_name'),
                'ACARA.jpg'
            )
            self.assertEqual(
                s_attachment.get('ID'),
                24880
            )

            self.assertTrue(
                sync_update.sync_warnings_core.get('image')
            )
            self.assertTrue(
                sync_update.get_slave_updates_native().get('image')
            )
            self.assertTrue(
                sync_update.get_slave_updates_native().get('image').get('id'),
                100003
            )

        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

        self.assertEqual(len(self.updates.category.slaveless), 2)

        for sync_update in self.updates.category.slaveless:
            try:
                sync_update_cat_rudiments_test(sync_update)
            except AssertionError as exc:
                self.fail_syncupdate_assertion(exc, sync_update)


        """
update <     167 |         ><class 'woogenerator.syncupdate.SyncUpdateCatWoo'>
---
M:SPA|r:167|w:|Product A Specials <ImportWooCategory>
{'CA': u'',
 'CVC': u'',
 'D': u'',
 'DNR': u'',
 'DPR': u'',
 'DYNCAT': u'',
 'DYNPROD': u'',
 'E': u'',
 'HTML Description': u'',
 'ID': '',
 'Images': u'ACA.jpg',
 'PA': u'',
 'RNR': u'',
 'RPR': u'',
 'SCHEDULE': u'',
 'Updated': u'',
 'VA': u'',
 'VISIBILITY': u'wholesale | local',
 'WNR': u'',
 'WPR': u'',
 'Xero Description': u'',
 '_row': [],
 'attachment_object': -1|ACA.jpg <ImportWooImg>,
 'backorders': 'no',
 'catalog_visibility': 'visible',
 'code': u'A',
 'codesum': u'SPA',
 'descsum': u'Product A Specials',
 'download_expiry': -1,
 'download_limit': -1,
 'featured': 'no',
 'fullname': u'Product A Specials',
 'fullnamesum': u'Specials > Product A Specials',
 'height': u'',
 'imgsum': u'ACA.jpg',
 'is_purchased': u'',
 'is_sold': u'',
 'itemsum': '',
 'length': u'',
 'modified_gmt': datetime.datetime(2017, 12, 5, 16, 56, 30, tzinfo=<UTC>),
 'modified_local': datetime.datetime(2017, 12, 6, 2, 36, 30),
 'name': u'Product A Specials',
 'post_status': u'',
 'prod_type': 'simple',
 'rowcount': 167,
 'slug': '',
 'stock': u'',
 'stock_status': u'',
 'tax_status': 'taxable',
 'taxosum': u'Specials > Product A Specials',
 'title': u'Product A Specials',
 'weight': u'',
 'width': u''}
S:{}
EMPTY
warnings:
-
Column       Reason     Subject           Old    New                                                   M TIME    S TIME  EXTRA
-----------  ---------  ----------------  -----  --------------------------------------------------  --------  --------  -------
description  inserting  woocommerce-test         Product A Specials                                         0         0
title        inserting  woocommerce-test         Product A Specials                                         0         0
menu_order   inserting  woocommerce-test         167                                                        0         0
image        inserting  woocommerce-test         OrderedDict([('modified_gmt', datetime.datetime(20         0         0
passes:
-
Column          Reason     Master    Slave      M TIME    S TIME  EXTRA
--------------  ---------  --------  -------  --------  --------  -------
term_parent_id  identical                            0         0
term_id         identical                            0         0
slug            identical                            0         0
display         identical                            0         0
probbos:

        """
        sync_update = self.updates.category.slaveless.get_by_ids(167, '')

        try:
            if self.debug:
                self.print_update(sync_update)
            m_attachment = sync_update.old_m_object_gen.to_dict()['attachment_object']
            self.assertEqual(
                m_attachment.get('file_name'),
                'ACA.jpg'
            )
            self.assertEqual(
                m_attachment.get('ID'),
                100002
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

# equivalent to:
    """
python -m woogenerator.generator \
      --schema=CA --local-work-dir 'tests/sample_data' --local-test-config 'generator_config_test.yaml' \
      --skip-download-master --master-file "tests/sample_data/generator_master_dummy.csv" \
      --master-dialect-suggestion "SublimeCsvTable" \
      --download-slave --schema "CA" \
      --do-specials --specials-file 'tests/sample_data/generator_specials_dummy.csv' \
      --do-sync --update-slave --do-problematic --auto-create-new \
      --do-categories --skip-variations --skip-attributes \
      --do-images --do-resize-images --skip-delete-images --skip-remeta-images --img-raw-dir "tests/sample_data/imgs_raw" \
      --wp-srv-offset 36000 \
      -vvv --debug-trace --force-update
    """

    @pytest.mark.slow
    def test_dummy_do_match_prod_cat_img(self):
        self.setup_temp_img_dir()
        self.populate_master_parsers()
        self.populate_slave_parsers()

        if self.settings.do_images:
            process_images(self.settings, self.parsers)
            do_match_images(
                self.parsers, self.matches, self.settings
            )
            do_merge_images(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_updates_images_master(
                self.updates, self.parsers, self.results, self.settings
            )
            self.do_updates_images_slave_mocked()

        if self.settings.do_categories:
            do_match_categories(
                self.parsers, self.matches, self.settings
            )
            do_merge_categories(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_updates_categories_master(
                self.updates, self.parsers, self.results, self.settings
            )
            self.do_updates_categories_slave_mocked()
        do_match_prod(self.parsers, self.matches, self.settings)

        if self.debug:
            self.matches.globals.tabulate()
            self.print_matches_summary(self.matches)

        self.assertEqual(len(self.matches.globals), 48)
        if self.debug:
            for index, matches in self.matches.sub_category.items():
                print("prod_matches: %s" % index)
                self.print_matches_summary(matches)

        # TODO: more tests

    @pytest.mark.slow
    def test_dummy_do_merge_prod_cat_img(self):
        self.setup_temp_img_dir()
        self.populate_master_parsers()
        self.populate_slave_parsers()

        if self.settings.do_images:
            process_images(self.settings, self.parsers)
            do_match_images(
                self.parsers, self.matches, self.settings
            )
            do_merge_images(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_updates_images_master(
                self.updates, self.parsers, self.results, self.settings
            )
            self.do_updates_images_slave_mocked()

        if self.settings.do_categories:
            do_match_categories(self.parsers, self.matches, self.settings)

            do_merge_categories(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_updates_categories_master(
                self.updates, self.parsers, self.results, self.settings
            )
            self.do_updates_categories_slave_mocked()

        if self.debug:
            report_cols = ColDataProductMeridian.get_col_values_native('path', target='gen-api')
            # report_cols['WNR'] = 'WNR'
            # report_cols['WNF'] = 'WNF'
            # report_cols['WNT'] = 'WNT'
            # report_cols['WNS'] = 'WNS'
            # report_cols['category_objects'] = 'category_objects'
            master_container = self.parsers.master.product_container.container
            master_products = master_container(self.parsers.master.products.values())
            slave_container = self.parsers.slave.product_container.container
            slave_products = slave_container(self.parsers.slave.products.values())
            print("matser_products:\n", master_products.tabulate(cols=report_cols))
            print("slave_products:\n", slave_products.tabulate(cols=report_cols))

        do_match_prod(self.parsers, self.matches, self.settings)
        do_merge_prod(self.matches, self.parsers, self.updates, self.settings)


        expected_sub_img_handles = ['source_url', 'title', 'id', 'position']
        unexpected_sub_img_handles = ['modified_gmt', 'created_gmt']
        expected_sub_img_cols = ['src', 'name', 'id', 'position']
        def sync_update_prod_rudiments_test(sync_update):
            if getattr(sync_update, 'new_s_object_core') \
            and sync_update.new_s_object_core.get('attachment_objects'):
                new_s_core_imgs = sync_update.new_s_object_core['attachment_objects']
                for new_s_core_img in new_s_core_imgs:
                    for key in expected_sub_img_handles:
                        self.assertIn(
                            key,
                            new_s_core_img
                        )
                    for key in unexpected_sub_img_handles:
                        self.assertNotIn(
                            key,
                            new_s_core_img
                        )
            if sync_update.get_slave_updates().get('attachment_objects'):
                slave_updates_core_imgs = sync_update.get_slave_updates().get('attachment_objects')
                for slave_updates_core_img in slave_updates_core_imgs:
                    for key in expected_sub_img_handles:
                        self.assertIn(
                            key,
                            slave_updates_core_img
                        )
                    for key in unexpected_sub_img_handles:
                        self.assertNotIn(
                            key,
                            slave_updates_core_img
                        )
                slave_updates_native_imgs = sync_update.get_slave_updates_native().get('images')
                for slave_updates_native_img in slave_updates_native_imgs:
                    for key in expected_sub_img_cols:
                        self.assertIn(
                            key,
                            slave_updates_native_img
                        )


        if self.debug:
            self.print_updates_summary(self.updates)
        self.assertTrue(self.updates.slave)
        self.assertEqual(len(self.updates.slave), 48)

        for sync_update in self.updates.slave:
            try:
                sync_update_prod_rudiments_test(sync_update)
            except AssertionError as exc:
                self.fail_syncupdate_assertion(exc, sync_update)

        # sync_update = self.updates.slave.get_by_ids(10, 24863)
        # Something must have changed in product matching??
        sync_update = self.updates.slave.get_by_ids(93, 24863)

        try:
            if self.debug:
                self.print_update(sync_update)
            expected_sku = "ACARF-CRS"

            self.assertEquals(
                sync_update.old_m_object_core['sku'],
                expected_sku
            )
            self.assertEquals(
                sync_update.old_s_object_core['sku'],
                expected_sku
            )
            self.assertEquals(
                sync_update.new_s_object_core['sku'],
                expected_sku
            )

            if self.settings.do_categories:
                expected_master_categories = set([320, 323, 315, 316])
                if not self.settings.skip_special_categories:
                    expected_master_categories.update([100000, 100001])
                expected_slave_categories = set([320, 315, 316])

                old_m_core_cat_ids = [
                    cat.get('term_id') for cat in \
                    sync_update.old_m_object_core['product_categories']
                ]
                self.assertEquals(
                    set(old_m_core_cat_ids),
                    expected_master_categories
                )
                old_s_core_cat_ids = [
                    cat.get('term_id') for cat in \
                    sync_update.old_s_object_core['product_categories']
                ]
                self.assertEquals(
                    set(old_s_core_cat_ids),
                    expected_slave_categories
                )
                new_s_core_cat_ids = [
                    cat.get('term_id') for cat in \
                    sync_update.new_s_object_core['product_categories']
                ]
                self.assertEquals(
                    set(new_s_core_cat_ids),
                    expected_master_categories
                )

            if self.settings.do_images:
                expected_master_images = set([100044])
                expected_slave_images = set([24864])

                old_m_core_img_ids = [
                    img.get('id') for img in \
                    sync_update.old_m_object_core['attachment_objects']
                ]
                self.assertEqual(
                    set(old_m_core_img_ids),
                    expected_master_images
                )
                old_s_core_img_ids = [
                    img.get('id') for img in \
                    sync_update.old_s_object_core['attachment_objects']
                ]
                self.assertEqual(
                    set(old_s_core_img_ids),
                    expected_slave_images
                )
                new_s_core_img_ids = [
                    img.get('id') for img in \
                    sync_update.new_s_object_core['attachment_objects']
                ]
                self.assertEqual(
                    set(new_s_core_img_ids),
                    expected_master_images
                )

            # TODO: test exact contents of get_slave_updates_native()
            # Specifically make sure that sale_price_dates_(to|from) are not datetime

            slave_updates_core = sync_update.get_slave_updates()
            slave_updates_native = sync_update.get_slave_updates_native()
            if self.debug:
                print("slave_updates_native:\n%s" % pformat(slave_updates_native.items()))
                print("slave_updates_core:\n%s" % pformat(slave_updates_core.items()))

            expected_dict = {
                # 'lc_wn_sale_price_dates_from': datetime(
                #     2016, 6, 13, 7, 0, 0, tzinfo=pytz.utc
                # ),
                'lc_wn_sale_price_dates_to': TimeUtils._gdrive_tz.localize(datetime(
                    3000, 7, 1, 0, 0, 0
                ))
            }
            for key, value in expected_dict.items():
                expected_value = value
                actual_value = slave_updates_core[key]
                if isinstance(actual_value, dict):
                    actual_value = set(actual_value.items())
                    expected_value = set(expected_value.items())
                elif isinstance(actual_value, list):
                    actual_value = set([
                        text_type(item) for item in actual_value
                    ])
                    expected_value = set([
                        text_type(item) for item in expected_value
                    ])
                else:
                    actual_value = text_type(actual_value)
                    expected_value = text_type(expected_value)

                self.assertEquals(
                    actual_value,
                    expected_value
                )
            expected_categories = set([315, 316, 323, 320, 100000, 100001])
            actual_categories = set([
                cat.get('term_id') for cat in slave_updates_core['product_categories']
            ])
            self.assertEqual(
                expected_categories,
                actual_categories
            )
            expected_attachments = set([100044])
            actual_attachments = set([
                img.get('id') for img in slave_updates_core['attachment_objects']
            ])
            self.assertEqual(
                expected_attachments,
                actual_attachments
            )

            for meta_object in slave_updates_native['meta_data']:
                if meta_object['key'] == 'lc_wn_sale_price_dates_to':
                    self.assertEqual(
                        meta_object['value'],
                        32519289600
                    )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

    @pytest.mark.slow
    def test_reporting_imgs_only(self):
        self.setup_temp_img_dir()
        self.populate_master_parsers()
        self.populate_slave_parsers()

        if self.settings.do_images:
            process_images(self.settings, self.parsers)
            do_match_images(
                self.parsers, self.matches, self.settings
            )
            do_merge_images(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_report_images(
                self.reporters, self.matches, self.updates, self.parsers, self.settings
            )

        self.assertTrue(
            self.reporters.img
        )

        if self.debug:
            print(
                "img pre-sync summary: \n%s" % \
                self.reporters.img.get_summary_text()
            )

    def test_reporting_cat_only(self):
        self.settings.do_images = False
        self.populate_master_parsers()
        self.populate_slave_parsers()
        if self.settings.do_categories:
            do_match_categories(
                self.parsers, self.matches, self.settings
            )
            do_merge_categories(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_report_categories(
                self.reporters, self.matches, self.updates, self.parsers, self.settings
            )

        self.assertTrue(
            self.reporters.cat
        )

        if self.debug:
            print(
                "cat pre-sync summary: \n%s" % \
                self.reporters.cat.get_summary_text()
            )

    @pytest.mark.slow
    def test_reporting_cat_img(self):
        self.setup_temp_img_dir()
        self.populate_master_parsers()
        self.populate_slave_parsers()

        if self.settings.do_images:
            process_images(self.settings, self.parsers)
            do_match_images(
                self.parsers, self.matches, self.settings
            )
            do_merge_images(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_updates_images_master(
                self.updates, self.parsers, self.results, self.settings
            )
            self.do_updates_images_slave_mocked()

        if self.settings.do_categories:
            do_match_categories(
                self.parsers, self.matches, self.settings
            )
            do_merge_categories(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_report_categories(
                self.reporters, self.matches, self.updates, self.parsers, self.settings
            )

        self.assertTrue(
            self.reporters.cat
        )

        if self.debug:
            print(
                "cat pre-sync summary: \n%s" % \
                self.reporters.cat.get_summary_text()
            )

    def test_dummy_do_merge_prod_cat_only(self):
        self.settings.do_variations = False
        self.settings.do_categories = True
        self.settings.do_attributes = False
        self.settings.do_images = False
        self.settings.do_specials = False

        self.populate_master_parsers()
        self.populate_slave_parsers()

        if self.settings.do_categories:
            do_match_categories(self.parsers, self.matches, self.settings)

            do_merge_categories(
                self.matches, self.parsers, self.updates, self.settings
            )
            do_updates_categories_master(
                self.updates, self.parsers, self.results, self.settings
            )
            self.do_updates_categories_slave_mocked()


        do_match_prod(self.parsers, self.matches, self.settings)
        # if self.debug:
        #     Registrar.DEBUG_UPDATE = True

        do_merge_prod(self.matches, self.parsers, self.updates, self.settings)

        sync_update = self.updates.slave.get_by_ids(93, 24863)

        self.assertNotIn('meta', sync_update.get_master_updates().keys())

    def test_dummy_do_updates_prod_master_only(self):
        self.settings.do_variations = False
        self.settings.do_categories = False
        self.settings.do_attributes = False
        self.settings.do_images = False
        self.settings.do_specials = False

        self.populate_master_parsers()
        self.populate_slave_parsers()

        do_match_prod(self.parsers, self.matches, self.settings)
        do_merge_prod(self.matches, self.parsers, self.updates, self.settings)

        do_updates_prod_master(
            self.updates, self.parsers, self.results, self.settings
        )

        self.assertEqual(
            self.parsers.master.products['ACARA-CAL']['ID'],
            24771
        )

    # TODO:
    # def test_dummy_do_updates_prod_slave_only(self):
    #     self.settings.do_variations = False
    #     self.settings.do_categories = False
    #     self.settings.do_attributes = False
    #     self.settings.do_images = False
    #     self.settings.do_specials = False
    #
    #     self.populate_master_parsers()
    #     self.populate_slave_parsers()
    #
    #     do_match_prod(self.parsers, self.matches, self.settings)
    #     do_merge_prod(self.matches, self.parsers, self.updates, self.settings)
    #
    #     do_updates_prod_slave()



class TestGeneratorSuperDummy(AbstractParserSyncManagerTestCase):
    """
    Stuff missing from original dummy which this tests:
     - variations
     - trashed products
     - attributes
     - collapsable categories (e.g. Product A > Company A Product A => Company A Product A)

    Generate slave input files:
    ```
    python -m woogenerator.generator --testmode --schema "CA" \
      --local-work-dir "/Users/derwent/Documents/woogenerator/" \
      --local-test-config "/Users/derwent/GitHub/WooGenerator/tests/sample_data/generator_config_test.yaml" \
      --master-file "/Users/derwent/GitHub/WooGenerator/tests/sample_data/generator_master_super_dummy.csv" \
      --master-dialect-suggestion "SublimeCsvTable" --do-categories --skip-specials --do-images --skip-attributes --do-variations \
      --download-slave --save-api-data \
      -vvv --debug-trace
    ```

    TODO / test:
        - parent of variable product can change from simple to variable (prod type syncs correctly)

    """
    settings_namespace_class = SettingsNamespaceProd
    config_file = "generator_config_test.yaml"

    def setUp(self):
        super(TestGeneratorSuperDummy, self).setUp()
        self.settings.master_dialect_suggestion = "SublimeCsvTable"
        self.settings.download_master = False
        self.settings.master_file = os.path.join(
            TESTS_DATA_DIR, "generator_master_super_dummy.csv"
        )
        self.settings.slave_file = os.path.join(
            TESTS_DATA_DIR, "prod_slave_super_dummy.json"
        )
        self.settings.slave_cat_file = os.path.join(
            TESTS_DATA_DIR, "prod_slave_cat_super_dummy.json"
        )
        self.settings.slave_img_file = os.path.join(
            TESTS_DATA_DIR, "prod_slave_img_super_dummy.json"
        )
        self.settings.slave_var_file_27063 = os.path.join(
            TESTS_DATA_DIR, "prod_slave_var_27063_super_dummy.json"
        )
        self.settings.master_and_quit = False
        self.settings.do_specials = False
        self.settings.do_categories = True
        self.settings.do_images = True
        self.settings.do_variations = True
        self.settings.do_sync = True
        self.settings.auto_create_new = True
        self.settings.update_slave = False
        self.settings.do_problematic = True
        self.settings.do_report = True
        self.settings.report_matching = True
        self.settings.do_remeta_images = False
        self.settings.do_resize_images = True
        self.settings.do_delete_images = False
        self.settings.schema = "CA"
        self.settings.skip_unattached_images = True
        self.settings.init_settings(self.override_args)

    @pytest.mark.first
    def test_super_dummy_init_settings(self):
        self.assertIn('image', self.settings.sync_handles_var)
        self.settings.do_images = False
        self.assertNotIn('image', self.settings.sync_handles_var)


    @pytest.mark.first
    def test_super_dummy_populate_master_parsers(self):

        self.populate_master_parsers()

        prod_container = self.parsers.master.product_container.container
        prod_list = prod_container(self.parsers.master.products.values())
        if self.debug:
            print(
                (
                    "%d objects\n"
                    "%d items\n"
                    "%d products:\n"
                ) % (
                    len(self.parsers.master.objects.values()),
                    len(self.parsers.master.items.values()),
                    len(prod_list)
                )
            )
            print(SanitationUtils.coerce_bytes(prod_list.tabulate(tablefmt='simple')))

        self.assertEqual(len(self.parsers.master.objects.values()), 9)
        self.assertEqual(len(self.parsers.master.items.values()), 6)
        self.assertEqual(len(prod_list), 1)

        first_prod = prod_list[0]
        if self.debug:
            print("pformat@first_prod:\n%s" % pformat(first_prod.to_dict()))
            print("first_prod.categories: %s" % pformat(first_prod.categories))
            print("first_prod.to_dict().get('attachment_objects'): %s" % pformat(first_prod.to_dict().get('attachment_objects')))
        self.assertEqual(first_prod.codesum, "AGL-CP5")
        self.assertEqual(first_prod.parent.codesum, "AGL")
        self.assertEqual(
            set([attachment.file_name for attachment in first_prod.to_dict().get('attachment_objects')]),
            set(["AGL-CP5.png"])
        )
        self.assertEqual(first_prod.depth, 3)
        self.assertTrue(first_prod.is_item)
        self.assertTrue(first_prod.is_product)
        self.assertFalse(first_prod.is_category)
        self.assertFalse(first_prod.is_root)
        self.assertFalse(first_prod.is_taxo)
        self.assertTrue(first_prod.is_variable)
        self.assertFalse(first_prod.is_variation)

        test_dict = {
            'attribute:pa_material': 'Cotton',
            'attribute:quantity': '5',
            'attribute:size': 'XSmall|Small|Medium|Large|XLarge',
            'attribute_data:pa_material': '0|1|0',
            'attribute_data:quantity': '0|1|0',
            'attribute_data:size': '0|1|1',
            'attribute_default:size': u'XSmall',
            'title': u'Cotton Glove Pack x5 Pairs',
            'CA': u'V',
        }

        first_prod_dict = first_prod.to_dict()

        for key, value in test_dict.items():
            self.assertEqual(text_type(first_prod_dict[key]), text_type(value))

        # Keys not allowed in variable products
        disallowed_keys = [
            'stock_status'
        ]

        for key in disallowed_keys:
            self.assertNotIn(key, first_prod_dict.keys())

        self.assertEqual(
            set([variation.codesum for variation in first_prod.variations.values()]),
            set([
                "AGL-CP5XS",
                "AGL-CP5S",
                "AGL-CP5M",
                "AGL-CP5L",
                "AGL-CP5XL",
            ])
        )

        first_variation = first_prod.variations.get('AGL-CP5S')

        test_dict = {
            'DNR': u'3.85',
            'DPR': u'3.85',
            'RNR': u'',
            'RPR': u'',
            'WNR': u'5.40',
            'WPR': u'4.95',
            'height': u'25',
            'length': u'100',
            'width': u'250',
            'weight': u'0.10',
            'stock_status': 'instock',
            'attribute:pa_material': 'Cotton',
            'attribute:quantity': '5',
            'attribute:size': 'Small',
            'meta:attribute_size': 'Small',
            'CA': u'I',
        }

        first_variation_dict = first_variation.to_dict()

        for key, value in test_dict.items():
            self.assertEqual(
                text_type(first_variation_dict[key]), text_type(value))

        trashed_variation = first_prod.variations.get('AGL-CP5XL')

        test_dict = {
            'post_status': 'trash'
        }

        for key, value in test_dict.items():
            self.assertEqual(text_type(trashed_variation[key]), text_type(value))

    def test_super_dummy_populate_slave_parsers(self):

        self.populate_slave_parsers()
        if self.debug:
            print("slave objects: %s" % len(self.parsers.slave.objects.values()))
            print("slave items: %s" % len(self.parsers.slave.items.values()))
            print("slave products: %s" % len(self.parsers.slave.products.values()))
            print("slave categories: %s" % len(self.parsers.slave.categories.values()))

        if self.debug:
            print("parser tree:\n%s" % self.parsers.slave.to_str_tree())

        self.assertEqual(len(self.parsers.slave.products), 1)
        prod_container = self.parsers.slave.product_container.container
        prod_list = prod_container(self.parsers.slave.products.values())
        first_prod = prod_list[0]
        if self.debug:
            print("first_prod.dict %s" % pformat(first_prod.to_dict()))
            print("first_prod.categories: %s" % pformat(first_prod.categories))
            print("first_prod.to_dict().get('attachment_objects'): %s" % pformat(first_prod.to_dict().get('attachment_objects')))

        test_dict = {
            'codesum': u'AGL-CP5',
            'title': u'Cotton Glove Pack x5 Pairs',
            'post_status': u'publish',
            'descsum': (
                'The materials used to manufacture these products has been '
                'developed to optimise exfoliation and massage without being '
                'too harsh to the skin.'
            ),
            'slug': u'cotton-glove-pack-x5-pairs',
            # TODO: test attributes somewhere
        }

        first_prod_dict = first_prod.to_dict()

        for key, value in test_dict.items():
            self.assertEqual(text_type(first_prod_dict[key]), text_type(value))

        # Keys not allowed in variable products
        disallowed_keys = [
            'stock_status'
        ]

        for key in disallowed_keys:
            self.assertNotIn(key, first_prod_dict.keys())

        #TODO: test only variation_id first, then test codesum
        var_ids = [var.api_id for var in first_prod.variations.values()]
        for var_id in [27065, 27066, 27067, 27068]:
            self.assertIn(var_id, var_ids)

        self.assertEqual(
            set([variation.codesum for variation in first_prod.variations.values()]),
            set([
                "AGL-CP5S",
                "AGL-CP5M",
                "AGL-CP5L",
                "AGL-CP5XL",
            ])
        )

        first_variation = first_prod.variations.get(27065)

        test_dict = {
            'DNR': u'3.85',
            'DPR': u'3.85',
            'RNR': u'',
            'RPR': u'',
            'WNR': u'5.50',
            'WPR': u'4.95',
            'height': u'25',
            'length': u'100',
            'width': u'250',
            'weight': u'0.10',
            # TODO: test these somewhere else
            # 'attribute:pa_material': 'Cotton',
            # 'attribute:quantity': '5',
            # 'attribute:size': 'Small',
            # 'meta:attribute_size': 'Small',
            # 'CA': u'I',
        }

        for key, value in test_dict.items():
            self.assertEqual(text_type(first_variation[key]), text_type(value))

    def test_super_dummy_to_target_type(self):
        """
        test the to_target_type functionality of master objects.
        """

        self.populate_master_parsers()

        prod_container = self.parsers.master.product_container.container
        prod_list = prod_container(self.parsers.master.products.values())

        first_prod = prod_list[0]
        first_variation = first_prod.variations.get('AGL-CP5S')
        coldata_target = 'wc-csv'
        coldata_class = ColDataProductMeridian

        extra_colnames = self.settings.coldata_class.get_attribute_colnames_native(
            self.parsers.master.attributes, self.parsers.master.vattributes
        )

        first_prod_csv = first_prod.to_target_type(
            coldata_class=coldata_class,
            coldata_target=coldata_target,
            extra_colnames=extra_colnames
        )

        test_dict = {
            'attribute:pa_material': 'Cotton',
            'attribute:quantity': '5',
            'attribute:size': 'XSmall|Small|Medium|Large|XLarge',
            'attribute_data:pa_material': '0|1|0',
            'attribute_data:quantity': '0|1|0',
            'attribute_data:size': '0|1|1',
            'attribute_default:size': u'XSmall',
            'post_title': u'Cotton Glove Pack x5 Pairs',
        }

        for key, value in test_dict.items():
            self.assertEqual(text_type(first_prod_csv[key]), text_type(value))

        extra_variation_col_names = self.settings.coldata_class_var.get_attribute_meta_colnames_native(
            self.parsers.master.vattributes
        )

        first_variation_csv = first_variation.to_target_type(
            coldata_class=coldata_class,
            coldata_target=coldata_target,
            extra_colnames=extra_variation_col_names
        )

        test_dict = {
            'meta:lc_dn_regular_price': u'3.85',
            'meta:lc_dp_regular_price': u'3.85',
            'meta:lc_rn_regular_price': u'',
            'meta:lc_rp_regular_price': u'',
            'meta:lc_wn_regular_price': u'5.40',
            'meta:lc_wp_regular_price': u'4.95',
            'height': u'25',
            'length': u'100',
            'width': u'250',
            'weight': u'0.10',
            'meta:attribute_size': 'Small',
        }

        for key, value in test_dict.items():
            self.assertEqual(text_type(first_variation_csv[key]), text_type(value))

    def test_super_dummy_match_var_only(self):
        self.settings.do_images = False
        self.populate_master_parsers()
        self.populate_slave_parsers()

        do_match_var(self.parsers, self.matches, self.settings)

        self.assertEqual(len(self.matches.variation.globals), 4)
        self.assertEqual(len(self.matches.variation.masterless), 0)
        self.assertEqual(len(self.matches.variation.slaveless), 1)

        # For any two given variations, master should be newer than slave,
        # since master comes from a file that should have recently been touched
        first_match = self.matches.variation.globals[0]
        self.assertGreater(
            first_match.m_objects[0].get('modified_gmt'),
            first_match.s_objects[0].get('modified_gmt')
        )


    def test_super_dummy_merge_var_only(self):
        self.settings.do_images = False
        self.settings.do_categories = False
        self.settings.do_attributes = False
        self.populate_master_parsers()
        self.populate_slave_parsers()

        do_match_var(self.parsers, self.matches, self.settings)
        if self.debug:
            Registrar.DEBUG_VARS = True

        do_merge_var(self.matches, self.parsers, self.updates, self.settings)

        try:
            self.assertEqual(len(self.updates.variation.delta_master), 0)
            self.assertEqual(len(self.updates.variation.delta_slave), 1)
            self.assertEqual(len(self.updates.variation.master), 3)
            self.assertEqual(len(self.updates.variation.slave), 2)
            self.assertEqual(len(self.updates.variation.slaveless), 1)
            self.assertEqual(len(self.updates.variation.masterless), 1)
            self.assertEqual(len(self.updates.variation.nonstatic_slave), 0)
            self.assertEqual(len(self.updates.variation.nonstatic_master), 0)
            self.assertEqual(len(self.updates.variation.problematic), 1)
        except BaseException as exc:
            self.fail_update_namespace_assertion(exc, self.updates.variation)

        sync_update = self.updates.variation.problematic.get_by_ids('AGL-CP5S', 27065)

        try:
            master_updates = sync_update.get_master_updates()
            self.assertNotIn('meta', master_updates.keys())
            self.assertNotIn('regular_price', master_updates.keys())
            self.assertIn('id', master_updates.keys())

            slave_updates = sync_update.get_slave_updates()
            self.assertIn('lc_wn_regular_price', slave_updates.keys())

        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

    def do_updates_var_slave_mocked(self):
        with mock.patch(
            MockUtils.get_mock_name(
                self.settings.__class__,
                'slave_var_sync_client_class'
            ),
            new_callable=mock.PropertyMock,
            return_value=self.settings.null_client_class
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'coldata_class'
            ),
            new_callable=mock.PropertyMock,
            return_value=ColDataProductVariationMeridian
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'coldata_target'
            ),
            new_callable=mock.PropertyMock,
            return_value=self.settings.coldata_var_target
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'coldata_target_write'
            ),
            new_callable=mock.PropertyMock,
            return_value=self.settings.coldata_var_target_write
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'endpoint_plural'
            ),
            new_callable=mock.PropertyMock,
            return_value='variations'
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'endpoint_singular'
            ),
            new_callable=mock.PropertyMock,
            return_value='variation'
        ), \
        mock.patch(
            MockUtils.get_mock_name(
                self.settings.null_client_class,
                'primary_key_handle'
            ),
            new_callable=mock.PropertyMock,
            return_value='id'
        ):
            self.settings.update_slave = True
            do_updates_var_slave(
                self.updates, self.parsers, self.results, self.settings
            )
            self.settings.update_slave = False

    def test_super_dummy_updates_var_master_only(self):
        self.settings.do_images = False
        self.settings.do_categories = False
        self.settings.do_attributes = False
        self.settings.ask_before_update = False
        self.populate_master_parsers()
        self.populate_slave_parsers()

        do_match_var(self.parsers, self.matches, self.settings)
        do_merge_var(self.matches, self.parsers, self.updates, self.settings)
        do_updates_var_master(
            self.updates, self.parsers, self.results, self.settings
        )

        self.assertEqual(
            self.parsers.master.variations['AGL-CP5S']['ID'], 27065
        )

    def test_super_dummy_updates_create_var_slave_only(self):
        self.settings.do_images = False
        self.settings.do_categories = False
        self.settings.do_attributes = False
        self.settings.ask_before_update = False
        self.settings.auto_create_new = True
        self.populate_master_parsers()
        self.populate_slave_parsers()

        do_match_var(self.parsers, self.matches, self.settings)
        do_merge_var(self.matches, self.parsers, self.updates, self.settings)
        do_match_prod(self.parsers, self.matches, self.settings)
        do_merge_prod(self.matches, self.parsers, self.updates, self.settings)
        do_updates_var_master(
            self.updates, self.parsers, self.results, self.settings
        )
        do_updates_prod_master(
            self.updates, self.parsers, self.results, self.settings
        )
        self.do_updates_var_slave_mocked()


    def test_super_dummy_updates_changes_var_slave_only(self):
        self.settings.do_images = False
        self.settings.do_categories = False
        self.settings.do_attributes = False
        self.settings.ask_before_update = False
        self.settings.auto_create_new = False
        self.populate_master_parsers()
        self.populate_slave_parsers()

        do_match_var(self.parsers, self.matches, self.settings)
        do_merge_var(self.matches, self.parsers, self.updates, self.settings)

        do_updates_var_master(
            self.updates, self.parsers, self.results, self.settings
        )

        self.do_updates_var_slave_mocked()


    # def test_super_dummy_attributes(self):
    #     self.populate_master_parsers()
    #
    #     attributes = self.parsers.master.attributes
    #     vattributes = self.parsers.master.vattributes

class TestGeneratorXeroDummy(AbstractSyncManagerTestCase):
    settings_namespace_class = SettingsNamespaceProd
    config_file = "generator_config_test.yaml"

    # debug = True

    def setUp(self):
        super(TestGeneratorXeroDummy, self).setUp()
        self.settings.download_master = False
        self.settings.do_categories = False
        self.settings.do_specials = False
        if self.debug:
            # self.settings.debug_shop = True
            # self.settings.debug_parser = True
            # self.settings.debug_abstract = True
            # self.settings.debug_gen = True
            # self.settings.debug_tree = True
            # self.settings.debug_update = True
            self.settings.verbosity = 3
            self.settings.quiet = False
        self.settings.init_settings(self.override_args)
        self.settings.schema = "XERO"
        self.settings.slave_name = "Xero"
        self.settings.do_sync = True
        self.settings.master_file = os.path.join(
            TESTS_DATA_DIR, "generator_master_dummy_xero.csv"
        )
        self.settings.master_dialect_suggestion = "SublimeCsvTable"
        self.settings.slave_file = os.path.join(
            TESTS_DATA_DIR, "xero_demo_data.json"
        )
        self.settings.report_matching = True
        self.matches = MatchNamespace(
            index_fn=ProductMatcher.product_index_fn
        )
        if self.debug:
            # Registrar.DEBUG_WARN = True
            # Registrar.DEBUG_MESSAGE = True
            # Registrar.DEBUG_ERROR = True
            # Registrar.DEBUG_SHOP = True
            # Registrar.DEBUG_PARSER = True
            # Registrar.DEBUG_ABSTRACT = True
            # Registrar.DEBUG_GEN = True
            # Registrar.DEBUG_TREE = True
            # Registrar.DEBUG_TRACE = True
            # ApiParseXero.DEBUG_API = True
            # Registrar.strict = True
            ApiParseXero.product_resolver = Registrar.exception_resolver
        else:
            Registrar.strict = False

    def test_xero_init_settings(self):
        self.assertFalse(self.settings.download_master)
        self.assertFalse(self.settings.do_specials)
        self.assertTrue(self.settings.do_sync)
        self.assertFalse(self.settings.do_categories)
        self.assertFalse(self.settings.do_delete_images)
        self.assertFalse(self.settings.do_dyns)
        self.assertFalse(self.settings.do_images)
        self.assertFalse(self.settings.do_mail)
        self.assertFalse(self.settings.do_post)
        self.assertFalse(self.settings.do_problematic)
        self.assertFalse(self.settings.do_remeta_images)
        self.assertFalse(self.settings.do_resize_images)
        self.assertFalse(self.settings.do_variations)
        self.assertFalse(self.settings.do_specials)
        self.assertTrue(self.settings.do_report)

    def test_xero_populate_master_parsers(self):
        if self.debug:
            # print(pformat(vars(self.settings)))
            registrar_vars = dict(vars(Registrar).items())
            print(pformat(registrar_vars.items()))
            del(registrar_vars['messages'])
            print(pformat(registrar_vars.items()))
        populate_master_parsers(self.parsers, self.settings)
        if self.debug:
            print("master objects: %s" % len(self.parsers.master.objects.values()))
            print("master items: %s" % len(self.parsers.master.items.values()))
            print("master products: %s" % len(self.parsers.master.products.values()))

        self.assertEqual(len(self.parsers.master.objects.values()), 29)
        self.assertEqual(len(self.parsers.master.items.values()), 20)

        prod_container = self.parsers.master.product_container.container
        prod_list = prod_container(self.parsers.master.products.values())
        if self.debug:
            print("prod list:\n%s" % prod_list.tabulate())
            item_list = ItemList(self.parsers.master.items.values())
            print("item list:\n%s" % item_list.tabulate())
            print("prod_keys: %s" % self.parsers.master.products.keys())

        self.assertEqual(len(prod_list), 15)
        first_prod = prod_list[0]
        self.assertEqual(first_prod.codesum, "GB1-White")
        self.assertEqual(first_prod.parent.codesum, "GB")
        self.assertTrue(first_prod.is_product)
        self.assertFalse(first_prod.is_category)
        self.assertFalse(first_prod.is_root)
        self.assertFalse(first_prod.is_taxo)
        self.assertFalse(first_prod.is_variable)
        self.assertFalse(first_prod.is_variation)
        for key, value in {
                'WNR': u'5.60',
        }.items():
            self.assertEqual(first_prod[key], value)

    def test_xero_populate_slave_parsers(self):
        # self.parsers = populate_master_parsers(self.parsers, self.settings)
        populate_slave_parsers(self.parsers, self.settings)

        if self.debug:
            print("slave objects: %s" % len(self.parsers.slave.objects.values()))
            print("slave items: %s" % len(self.parsers.slave.items.values()))
            print("slave products: %s" % len(self.parsers.slave.products.values()))

        self.assertEqual(len(self.parsers.slave.objects.values()), 10)
        self.assertEqual(len(self.parsers.slave.items.values()), 10)

        prod_container = self.parsers.slave.product_container.container
        prod_list = prod_container(self.parsers.slave.products.values())
        if self.debug:
            print("prod list:\n%s" % prod_list.tabulate())
            item_list = ItemList(self.parsers.slave.items.values())
            print("item list:\n%s" % item_list.tabulate())
            print("prod_keys: %s" % self.parsers.slave.products.keys())

        self.assertEqual(len(prod_list), 10)
        first_prod = prod_list[0]
        self.assertEqual(first_prod.codesum, "DevD")
        self.assertTrue(first_prod.is_product)
        self.assertFalse(first_prod.is_category)
        self.assertFalse(first_prod.is_root)
        self.assertFalse(first_prod.is_taxo)
        self.assertFalse(first_prod.is_variable)
        self.assertFalse(first_prod.is_variation)

    @pytest.mark.last
    def test_xero_do_match(self):
        populate_master_parsers(self.parsers, self.settings)
        populate_slave_parsers(self.parsers, self.settings)
        do_match_prod(self.parsers, self.matches, self.settings)

        if self.debug:
            print('match summary')
            self.print_matches_summary(self.matches)

        self.assertEqual(len(self.matches.globals), 10)
        self.assertEqual(len(self.matches.masterless), 0)
        self.assertEqual(len(self.matches.slaveless), 5)

    @pytest.mark.last
    def test_xero_do_merge(self):
        populate_master_parsers(self.parsers, self.settings)
        populate_slave_parsers(self.parsers, self.settings)
        do_match_prod(self.parsers, self.matches, self.settings)
        do_merge_prod(self.matches, self.parsers, self.updates, self.settings)

        if self.debug:
            self.print_updates_summary(self.updates)

        if self.debug:
            for sync_update in self.updates.slave:
                self.print_update(sync_update)

        self.assertEqual(len(self.updates.delta_master), 0)
        self.assertEqual(len(self.updates.delta_slave), 1)
        self.assertEqual(len(self.updates.master), 10)
        self.assertEqual(len(self.updates.slave), 1)
        self.assertEqual(len(self.updates.slaveless), 5)
        self.assertEqual(len(self.updates.masterless), 0)
        self.assertEqual(len(self.updates.nonstatic_slave), 0)
        self.assertEqual(len(self.updates.nonstatic_master), 0)
        self.assertEqual(len(self.updates.problematic), 0)

        # sync_update = self.updates.delta_slave[0]
        self.assertTrue(
            self.updates.delta_slave[0].new_m_object.rowcount
        )
        sync_update = self.updates.delta_slave.get_by_ids(19, 'c27221d7-8290-4204-9f3d-0cfb7c5a3d6f')
        try:
            if self.debug:
                self.print_update(sync_update)
            self.assertEqual(sync_update.old_m_object.codesum, 'DevD')
            self.assertEqual(
                float(sync_update.old_m_object['WNR']),
                610.0
            )
            self.assertEqual(
                sync_update.slave_id,
                u'c27221d7-8290-4204-9f3d-0cfb7c5a3d6f'
            )
            self.assertEqual(sync_update.old_s_object.codesum, 'DevD')
            self.assertEqual(
                float(sync_update.old_s_object['WNR']),
                650.0
            )
            self.assertEqual(
                float(sync_update.new_s_object['WNR']),
                610.0
            )
        except AssertionError as exc:
            self.fail_syncupdate_assertion(exc, sync_update)

    @pytest.mark.last
    def test_xero_do_report(self):
        suffix='geenrator_xero_do_report'
        temp_working_dir = tempfile.mkdtemp(suffix + '_working')
        if self.debug:
            print("working dir: %s" % temp_working_dir)
        self.settings.local_work_dir = temp_working_dir
        self.settings.init_dirs()
        populate_master_parsers(self.parsers, self.settings)
        populate_slave_parsers(self.parsers, self.settings)
        do_match_prod(self.parsers, self.matches, self.settings)
        self.updates = UpdateNamespace()
        do_merge_prod(self.matches, self.parsers, self.updates, self.settings)
        self.reporters = ReporterNamespace()
        do_report(
            self.reporters, self.matches, self.updates, self.parsers, self.settings
        )


if __name__ == '__main__':
    unittest.main()
