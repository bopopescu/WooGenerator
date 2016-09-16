# -*- coding: utf-8 -*-
from collections import OrderedDict
import os
# import shutil
from utils import SanitationUtils, TimeUtils, listUtils, debugUtils, Registrar
from utils import ProgressCounter
from csvparse_flat import CSVParse_User, UsrObjList #, ImportUser
from coldata import ColData_User
from tabulate import tabulate
from itertools import chain
# from pprint import pprint
# import sys
from copy import deepcopy
import unicodecsv
# import pickle
import dill as pickle
import requests
from bisect import insort
import re
import time
import yaml
# import MySQLdb
import paramiko
from sshtunnel import SSHTunnelForwarder, check_address
import io
# import wordpress_xmlrpc
from wordpress_json import WordpressJsonWrapper, WordpressError
import pymysql
from simplejson import JSONDecodeError
from sync_client import SyncClient_Abstract, SyncClient_WC
from woocommerce import API as WCAPI
from coldata import ColData_Woo

class ProdSyncClient_Abstract(SyncClient_Abstract):
    pass

class ProdSyncClient_WC(SyncClient_WC):
    def analyseRemote(self, parser, since=None, limit=None):
        endpoint = 'products'
        #todo: implement since
        if Registrar.DEBUG_API:
            Registrar.registerMessage('api endpoint: %s' % endpoint)
        productCount = 0
        apiIterator = self.ApiIterator(self.client, endpoint)
        progressCounter = None
        for page in apiIterator:
            if progressCounter is None:
                total_items = apiIterator.total_items
                if limit:
                    total_items = min(limit, total_items)
                progressCounter = ProgressCounter(total_items)
            progressCounter.maybePrintUpdate(productCount)

            if Registrar.DEBUG_API:
                Registrar.registerMessage('processing page: %s' % str(page))
            if 'products' in page:
                for page_product in page.get('products'):

                    parser.analyseWpApiObj(page_product)
                    productCount += 1
                    if limit and productCount > limit:
                        if Registrar.DEBUG_API:
                            Registrar.registerMessage('reached limit, exiting')
                        return

    def uploadChanges(self, pkey, updates=None):
        super(ProdSyncClient_WC, self).uploadChanges(pkey)
        endpoint = 'products/%s' % pkey
        if self.client.version is not 'wc/v1':
            updates = {'product':updates}
        if Registrar.DEBUG_API:
            Registrar.registerMessage("updating %s: %s" % (endpoint, updates))
        response = self.client.put(endpoint, updates)
        assert response.status_code not in [400], "API ERROR"
        assert response.json(), "json should exist"
        assert not isinstance(response.json(), int), "could not convert response to json: %s %s" % (str(response), str(response.json()))
        assert 'errors' not in response.json(), "response has errors: %s" % str(response.json()['errors'])
        return response
