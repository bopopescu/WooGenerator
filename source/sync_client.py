# -*- coding: utf-8 -*-
from collections import OrderedDict, Iterable
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

from requests import request
from json import dumps as jsonencode

try:
    from urllib.parse import urlencode, quote, unquote, parse_qs, parse_qsl, urlparse, urlunparse
    from urllib.parse import ParseResult as URLParseResult
except ImportError:
    from urllib import urlencode, quote, unquote
    from urlparse import parse_qs, parse_qsl, urlparse, urlunparse
    from urlparse import ParseResult as URLParseResult

import httplib2

from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools

# from woocommerce import API
from wordpress import API
from wordpress.helpers import UrlUtils
from simplejson.scanner import JSONDecodeError

class AbstractServiceInterface(object):
    """Defines the interface to an abstract service"""
    def close(self): pass
    def connect(self, connectParams): raise NotImplementedError()
    def files(self): raise NotImplementedError()
    def put(self, *args, **kwargs): raise NotImplementedError()
    @property
    def version(self): raise NotImplementedError()
    # @property
    # def wp_api(self): raise NotImplementedError()

class WPAPI_Service(API, AbstractServiceInterface):
    """ A child of the wordpress API that implements the Service interface """
    pass
    # def __init__(self, *args, **kwargs):
        # if not args:
            # args = [kwargs['api_key'], kwargs['api_secret']]
        # super(WPAPI_Service, self).__init__(*args, **kwargs)
    # pass
    # def __init__(self, *args, **kwargs):
    #     # print "hello from __init__"
    #     super(WPAPI_Service, self).__init__(*args, **kwargs)

    # def _API__get_url(self, endpoint):
    #     # print "hello from _API__get_url"
    #     url = super(WPAPI_Service, self)._API__get_url(endpoint)
    #     #
    #     # if Registrar.DEBUG_API:
    #     #     Registrar.registerMessage("API got endpoint url: %s" % url)
    #     return url
    #
    # def _API__request(self, method, endpoint, data):
    #     """ Do requests """
    #     url = self._API__get_url(endpoint)
    #     auth = None
    #     headers = {
    #         "user-agent": "WooCommerce API Client-Python/%s" % 1.2,
    #         "content-type": "application/json;charset=utf-8",
    #         "accept": "application/json"
    #     }
    #
    #     if self.is_ssl is True:
    #         auth = (self.consumer_key, self.consumer_secret)
    #     else:
    #         url = self._API__get_oauth_url(url, method)
    #
    #     if data is not None:
    #         data = jsonencode(data, ensure_ascii=False).encode('utf-8')
    #
    #     request_params = {}
    #     request_params.update(
    #         method=method,
    #         url=url,
    #         verify=self.verify_ssl,
    #         auth=auth,
    #         data=data,
    #         timeout=self.timeout,
    #         headers=headers
    #     )
    #
    #     if Registrar.DEBUG_API:
    #         Registrar.registerMessage("WCAPI, request params: %s" % str(request_params))
    #
    #     return request(
    #         **request_params
    #     )

class SyncClient_Abstract(Registrar):
    """docstring for UsrSyncClient_Abstract"""
    service_builder = AbstractServiceInterface

    def __init__(self, connectParams):
        self.connectParams = connectParams
        self.attemptConnect()

    def __enter__(self):
        return self

    def __exit__(self, exit_type, value, traceback):
        if hasattr(self.service, 'close'):
            self.service.close()

    @property
    def connectionReady(self):
        return self.service

    def assertConnect(self):
        if not self.connectionReady:
            self.attemptConnect()
        assert self.connectionReady, "connection must be ready"

    def attemptConnect(self):
        positional_args = self.connectParams.pop('positional', [])
        service_name = 'UNKN'
        if hasattr(self.service_builder, '__name__'):
            service_name = getattr(self.service_builder, '__name__')
        if self.DEBUG_API: self.registerMessage("building service (%s) with positional: %s and keyword: %s" %
            (
                str(service_name),
                str(positional_args),
                str(self.connectParams)
            )
        )
        self.service = self.service_builder(*positional_args, **self.connectParams )

    # def __exit__(self, exit_type, value, traceback):
    #     raise NotImplementedError()
    #
    # @property
    # def connectionReady(self):
    #     raise NotImplementedError()

    def analyseRemote(self, parser, *args, **kwargs):
        raise NotImplementedError()

    def uploadChanges(self, pkey, updates=None):
        if updates:
            assert pkey, "must have a valid primary key"
            assert self.connectionReady, "connection should be ready"

class SyncClient_GDrive(SyncClient_Abstract):
    skip_download = None
    service_builder = discovery.build

    def __init__(self, gdriveParams):
        for key in ['credentials_dir', 'credentials_file', 'client_secret_file',
                    'scopes', 'app_name']:
            assert key in gdriveParams, "key %s should be specified" % key
        self.gdriveParams = gdriveParams
        credentials = self.get_credentials()
        auth_http = credentials.authorize(httplib2.Http())

        superConnectParams = {
            'positional': ['drive', 'v2'],
            'http':auth_http
        }
        super(SyncClient_GDrive, self).__init__(superConnectParams)
        # self.service = self.service_builder('drive', 'v2', http=auth_http)
        self.service = discovery.build(
            *superConnectParams.pop('positional',[]),
            **superConnectParams
        )
        # self.service = self.service_builder(    #todo: figure out why this doesn't work but the others do
        #     *superConnectParams.pop('positional',[]),
        #     **superConnectParams
        # )
        # self.service = discovery.build('drive', 'v2', http=auth_http)

        self.drive_file = self.service.files().get(fileId=self.gdriveParams['genFID']).execute()

    def __exit__(self, exit_type, value, traceback):
        pass

    def attemptConnect(self):
        pass

    def assertConnect(self):
        assert self.connectionReady, "connection must be ready"

    def get_credentials(self):
        credential_dir = os.path.expanduser(self.gdriveParams['credentials_dir'])
        if not os.path.exists(credential_dir):
            os.makedirs(credential_dir)
        credential_path = os.path.join(credential_dir, self.gdriveParams['credentials_file'])
        store = oauth2client.file.Storage(credential_path)
        credentials = store.get()
        if not credentials or credentials.invalid:
            flow = client.flow_from_clientsecrets(self.gdriveParams['client_secret_file'],
                                                  self.gdriveParams['scopes'])
            flow.user_agent = self.gdriveParams['app_name']
            # if flags:
            #     credentials = tools.run_flow(flow, store, flags)
            # else: # Needed only for compatibility with Python 2.6
            #     credentials = tools.run(flow, store)
            credentials = tools.run(flow, store)
            self.registerMessage('Storing credentials to ' + credential_path)
        return credentials

    def download_file_content_csv(self, gid=None):
        """Download current file's content as csv.

        Args:
          gid: GID of file to download

        Returns:
          File's content if successful, None otherwise.
        """
        # print( type(drive_file) )
        # print( drive_file)
        download_url = self.drive_file['exportLinks']['text/csv']
        if gid:
            download_url += "&gid=" + str(gid )
        self.registerMessage( "Downloading: %s" % download_url )
        if download_url:
            resp, content = self.service._http.request(download_url)
            if resp.status == 200:
                self.registerMessage('Status: %s' % resp)
                return content
            else:
                self.registerError('An error occurred: %s' % resp)
                return None
        else:
            return None
            # The file doesn't have any content stored on Drive.

    def get_gm_modtime(self, gid=None):
        if gid: pass #gets rid of annoying warnings
        modifiedDate = self.drive_file['modifiedDate']

        return time.strptime(modifiedDate, '%Y-%m-%dT%H:%M:%S.%fZ')

    def analyseRemote(self, parser, gid=None, outPath=None, limit=None):
        if not outPath:
            outPath = '/tmp/' + gid + '.csv'
        if not self.skip_download:
            # try:
            #     assert os.path.isfile(outPath)
            #     local_timestamp = os.path.getmtime(outPath)
            # except:
            #     local_timestamp = 0
            # local_gmtime = time.gmtime(local_timestamp)
            #
            # remote_gmtime = get_gm_modtime(gid)
            #
            # print "local / remote gmtime", local_gmtime, remote_gmtime

            # if local_gmtime < remote_gmtime:
            content = self.download_file_content_csv(gid)
            if content:
                with open(outPath, 'w') as outFile:
                    outFile.write(content)
                    print "downloaded ", outFile
        parser.analyseFile(outPath, limit=limit)

class SyncClient_Rest(SyncClient_Abstract):
    class ApiIterator(Iterable):
        def __init__(self, service, endpoint):
            assert isinstance(service, WPAPI_Service)
            self.service = service
            self.next_endpoint = endpoint
            self.prev_response = None
            self.next_page = None
            # self.progressCounter = None
            self.total_pages = None
            self.total_items = None
            # self.stopNextIteration = False

        def get_page_param(self, url):
            params = SanitationUtils.findall_url_params(url)
            if 'page' in params:
                pages = params['page']
                assert len(pages) == 1
                return int(pages[0])
            else:
                return None

        def processHeaders(self, response):
            headers = response.headers
            if Registrar.DEBUG_API:
                Registrar.registerMessage("headers: %s" % str(headers))

            if self.service.namespace == 'wp-api':
                total_pages_key = 'X-WP-TotalPages'
                total_items_key = 'X-WP-Total'
                links_finder = SanitationUtils.findall_wp_links
            else:
                total_pages_key = 'x-wc-totalpages'
                total_items_key = 'x-wc-total'
                links_finder = SanitationUtils.findall_wc_links

            if self.total_pages is None and total_items_key in headers:
                self.total_pages = int(headers.get(total_pages_key,''))
            if self.total_items is None and total_pages_key in headers:
                self.total_items = int(headers.get(total_items_key,''))
            # if self.progressCounter is None:
            #     self.progressCounter = ProgressCounter(total=self.total_pages)
            # self.stopNextIteration = True
            # self.next_page = self.total_pages
            prev_endpoint = self.next_endpoint
            self.next_endpoint = None

            for rel, link in response.links.items():
                if rel == 'next' and link.get('url'):
                    next_response_url = link['url']
                    # if Registrar.DEBUG_API:
                    #     Registrar.registerMessage('next_response_url: %s' % str(next_response_url))
                    self.next_page = parse_qs(urlparse(next_response_url).query).get('page',[None])[0]
                    self.next_page = int(self.next_page)
                    if not self.next_page:
                        return
                    assert \
                        self.next_page <= self.total_pages, \
                        "next page (%s) should be lte total pages (%s)" \
                        % (str(self.next_page), str(self.total_pages))
                    next_endpoint_queries = parse_qs(urlparse(next_response_url).query)
                    next_endpoint_queries.update(page=self.next_page)
                    self.next_endpoint = UrlUtils.substitute_query(prev_endpoint, urlencode(next_endpoint_queries))
                    # self.next_endpoint = self.__get_endpoint(next_response_url)
                    # if Registrar.DEBUG_API:
                    #     Registrar.registerMessage('next_endpoint: %s' % str(self.next_endpoint))

            # links_str = headers.get('link', '')
            # if Registrar.DEBUG_API:
            #     Registrar.registerMessage("links str: {}".format(links_str))
            # links = links_finder(links_str)
            # if Registrar.DEBUG_API:
            #     Registrar.registerMessage("wc_links: %s" % str(links))
            # for link in links:
            #     if link.get('rel') == 'next' and link.get('url'):
            #         next_response_url = link['url']
            #         self.next_page = self.get_page_param(next_response_url)
            #         if self.next_page == 2:
            #             next_response_url = re.sub(r'page=\d', 'page=8', next_response_url)
            #         # self.stopNextIteration = False
            #         if Registrar.DEBUG_API:
            #             Registrar.registerMessage('next_response_url: %s' % str(next_response_url))
            #         self.next_endpoint = self.__get_endpoint(next_response_url)
            #         if Registrar.DEBUG_API:
            #             Registrar.registerMessage('next_endpoint: %s' % str(self.next_endpoint))
            #         break

            # self.progressCounter.maybePrintUpdate(self.next_page)

        # def __get_endpoint(self, url):
        #     url_path = SanitationUtils.stripURLHost(url)
        #     response = url_path
        #     print "url_path", url_path
        #     service_url_path = UrlUtils.join_components([
        #         SanitationUtils.stripURLHost(self.service.url),
        #         self.service.namespace,
        #         self.service.version
        #     ])
        #     print "service_url_path", service_url_path
        #     if url_path.startswith(service_url_path):
        #         response = response.replace(service_url_path, '')
        #     print "reponse", response
        #     return response

        def __iter__(self):
            return self

        def next(self):
            if Registrar.DEBUG_API:
                Registrar.registerMessage('start')

            if self.next_endpoint is None:
                if Registrar.DEBUG_API:
                    Registrar.registerMessage('stopping due to no next endpoint')
                raise StopIteration()

            # get API response
            self.prev_response = self.service.get(self.next_endpoint)

            # handle API errors
            if self.prev_response.status_code in range(400, 500):
                raise UserWarning('api call failed: %dd with %s' %( self.prev_response.status_code, self.prev_response.text))

            # can still 200 and fail
            try:
                prev_response_json = self.prev_response.json()
            except JSONDecodeError:
                prev_response_json = {}
                e = UserWarning('api call to %s failed: %s' % (self.next_endpoint, self.prev_response.text))
                Registrar.registerError(e)

            if Registrar.DEBUG_API:
                Registrar.registerMessage('first api response: %s' % str(prev_response_json))
            if 'errors' in prev_response_json:
                raise UserWarning('first api call returned errors: %s' % (prev_response_json['errors']))

            # process API headers
            self.processHeaders(self.prev_response)

            return prev_response_json

    service_builder = WPAPI_Service
    version = None
    endpoint_singular = ''
    mandatory_params = ['api_key', 'api_secret', 'url']
    default_version='wp/v2'
    default_namespace='wp-json'

    @property
    def endpoint_plural(self):
        return "%ss" % self.endpoint_singular

    def __init__(self, connectParams):

        key_translation = {
            'api_key': 'consumer_key',
            'api_secret': 'consumer_secret'
        }
        for param in self.mandatory_params:
            assert param in connectParams and connectParams[param], \
                "missing mandatory param (%s) from connect parameters: %s" \
                % (param, str(connectParams))

        #
        superConnectParams = {}

        for key, value in connectParams.items():
            super_key = key
            if key in key_translation:
                super_key = key_translation[key]
            superConnectParams[super_key] = value

        if 'api' not in superConnectParams:
            superConnectParams['api'] = self.default_namespace
        if 'version' not in superConnectParams:
            superConnectParams['version'] = self.default_version
        if superConnectParams['api'] == 'wp-json':
            superConnectParams['oauth1a_3leg'] = True


        superConnectParams.update(
            timeout=60
        )

        super(SyncClient_Rest, self).__init__(superConnectParams)
        #
        # self.service = WCAPI(
        #     url=connectParams['url'],
        #     consumer_key=connectParams['api_key'],
        #     consumer_secret=connectParams['api_secret'],
        #     timeout=60,
        #     # wp_api=True, # Enable the WP REST API integration
        #     # version="v3", # WooCommerce WP REST API version
        #     # version="wc/v1"
        # )

    #
    def analyseRemote(self, parser, since=None, limit=None):
        if since: pass #todo: implement since
        resultCount = 0
        apiIterator = self.ApiIterator(self.service, self.endpoint_plural)
        progressCounter = None
        for page in apiIterator:
            if progressCounter is None:
                total_items = apiIterator.total_items
                if limit:
                    total_items = min(limit, total_items)
                progressCounter = ProgressCounter(total_items)
            progressCounter.maybePrintUpdate(resultCount)

            if Registrar.DEBUG_API:
                Registrar.registerMessage('processing page: %s' % str(page))
            if self.endpoint_plural in page:
                for page_item in page.get(self.endpoint_plural):

                    parser.analyseWpApiObj(page_item)
                    resultCount += 1
                    if limit and resultCount > limit:
                        if Registrar.DEBUG_API:
                            Registrar.registerMessage('reached limit, exiting')
                        return

    def uploadChanges(self, pkey, updates=None):
        super(SyncClient_Rest, self).uploadChanges(pkey)
        service_endpoint = '%s/%d' % (self.endpoint_plural,pkey)
        if self.service.version is not 'wc/v1':
            updates = {'product':updates}
        if Registrar.DEBUG_API:
            Registrar.registerMessage("updating %s: %s" % (service_endpoint, updates))
        response = self.service.put(service_endpoint, updates)
        assert response.status_code not in [400,401], "API ERROR"
        assert response.json(), "json should exist"
        assert not isinstance(response.json(), int), "could not convert response to json: %s %s" % (str(response), str(response.json()))
        assert 'errors' not in response.json(), "response has errors: %s" % str(response.json()['errors'])
        return response

    def getIterator(self, endpoint=None):
        if not endpoint:
            endpoint = self.endpoint_plural
        return self.ApiIterator(self.service, endpoint)

    # def __exit__(self, exit_type, value, traceback):
    #     pass

class SyncClient_WC(SyncClient_Rest):
    default_version='v3'
    default_namespace='wc-api'

class SyncClient_WP(SyncClient_Rest):
    mandatory_params = ['api_key', 'api_secret', 'url', 'wp_user', 'wp_pass', 'callback']
