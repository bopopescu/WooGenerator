# pylint: disable=too-many-lines
"""Module for updating woocommerce and ACT databases from ACT import file."""

# TODO: Fix too-many-lines

import io
import os
import re
import time
import traceback
import zipfile
from bisect import insort
from collections import OrderedDict
from pprint import pprint, pformat

import unicodecsv
from sshtunnel import check_address
from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout
from httplib2 import ServerNotFoundError

import __init__
from woogenerator.coldata import ColDataUser
from woogenerator.contact_objects import FieldGroup
from woogenerator.duplicates import Duplicates
from woogenerator.matching import (CardMatcher, ConflictingMatchList,
                                   EmailMatcher, Match, MatchList,
                                   NocardEmailMatcher, UsernameMatcher)
from woogenerator.parsing.user import CsvParseUser, UsrObjList
from woogenerator.sync_client_user import (UsrSyncClientSqlWP,
                                           UsrSyncClientSshAct,
                                           UsrSyncClientWP)
from woogenerator.syncupdate import SyncUpdate, SyncUpdateUsrApi
from woogenerator.utils import (HtmlReporter, ProgressCounter, Registrar,
                                SanitationUtils, TimeUtils, DebugUtils)
from woogenerator.config import (ArgumentParserUser, ArgumentParserProtoUser,
                                 SettingsNamespaceUser)


def timediff(settings):
    """
    Return the difference in time since the start time according to settings.
    """
    return time.time() - settings.start_time


def main(override_args=None, settings=None):  # pylint: disable=too-many-branches,too-many-locals
    """
    Use settings object to load config file and detect changes in wordpress.
    """
    # TODO: fix too-many-branches,too-many-locals
    # DONE: implement override_args

    if not settings:
        settings = SettingsNamespaceUser()

    proto_argparser = ArgumentParserProtoUser()

    print "proto_parser: \n%s" % pformat(proto_argparser.get_actions())

    parser_override = {'namespace':settings}
    if override_args:
        parser_override['args'] = override_args.split()

    settings, _ = proto_argparser.parse_known_args(**parser_override)

    print "proto settings: \n%s" % pformat(vars(settings))

    argparser = ArgumentParserUser()

    for conf in settings.second_stage_configs:
        print "adding conf: %s" % conf
        argparser.add_default_config_file(conf)

    print "parser: %s " % pformat(argparser.get_actions())

    settings = argparser.parse_args(**parser_override)

    print "Raw settings: %s" % pformat(vars(settings))


    # DONE: change default-last-sync to just last-sync
    # DONE: Remove references to yaml_path
    # DONE: move in, out, log folders to full

    if settings.verbosity > 0:
        Registrar.DEBUG_PROGRESS = True
        Registrar.DEBUG_ERROR = True
    if settings.verbosity > 1:
        Registrar.DEBUG_MESSAGE = True
    if settings.quiet:
        Registrar.DEBUG_PROGRESS = False
        Registrar.DEBUG_ERROR = False
        Registrar.DEBUG_MESSAGE = False

    Registrar.DEBUG_ABSTRACT = settings.debug_abstract
    Registrar.DEBUG_PARSER = settings.debug_parser
    Registrar.DEBUG_UPDATE = settings.debug_update
    Registrar.DEBUG_FLAT = settings.debug_flat
    Registrar.DEBUG_NAME = settings.debug_name
    Registrar.DEBUG_ADDRESS = settings.debug_address
    Registrar.DEBUG_CLIENT = settings.debug_client
    Registrar.DEBUG_UTILS = settings.debug_utils
    Registrar.DEBUG_CONTACT = settings.debug_contact
    Registrar.DEBUG_DUPLICATES = settings.debug_duplicates

    ### DISPLAY CONFIG ###
    if Registrar.DEBUG_MESSAGE:
        if settings.testmode:
            print "testmode enabled"
        else:
            print "testmode disabled"
        if not settings['download_slave']:
            print "no download_slave"
        if not settings['download_master']:
            print "no download_master"
        if not settings['update_master']:
            print "not updating maseter"
        if not settings['update_slave']:
            print "not updating slave"
        if not settings['do_filter']:
            print "not doing filter"
        if not settings['do_sync']:
            print "not doing sync"
        if not settings.do_post:
            print "not doing post"

    ### PROCESS CLASS PARAMS ###

    FieldGroup.do_post = settings.do_post
    SyncUpdate.set_globals(settings.master_name, settings.slave_name,
                           settings.merge_mode, settings.last_sync)
    TimeUtils.set_wp_srv_offset(settings.wp_srv_offset)

    ### SET UP DIRECTORIES ###

    for path in (settings.in_folder_full, settings.out_folder_full):
        if not os.path.exists(path):
            os.mkdir(path)

    if settings['download_master']:
        ma_path = os.path.join(settings.in_folder_full, settings.m_x_name)
        ma_encoding = "utf-8"
    else:
        assert settings['master_file'], "master file must be provided if not download_master"
        ma_path = os.path.join(settings.in_folder_full, settings['master_file'])
        ma_encoding = "utf8"
    if settings['download_slave']:
        sa_path = os.path.join(settings.in_folder_full, settings.s_x_name)
        sa_encoding = "utf8"
    else:
        assert settings['slave_file'], "slave file must be provided if not download_slave"
        sa_path = os.path.join(settings.in_folder_full, settings['slave_file'])
        sa_encoding = "utf8"

    settings.repd_path = os.path.join(
        settings.out_folder_full,
        "%ssync_report_duplicate%s.html" % (settings.file_prefix, settings.file_suffix))
    settings.w_pres_csv_path = os.path.join(
        settings.out_folder_full,
        "%ssync_report_%s%s.csv" % \
            (settings.file_prefix, settings.slave_name, settings.file_suffix))
    settings.master_res_csv_path = os.path.join(
        settings.out_folder_full,
        "%ssync_report_%s%s.csv" % \
            (settings.file_prefix, settings.master_name, settings.file_suffix))
    settings.master_delta_csv_path = os.path.join(
        settings.out_folder_full,
        "%sdelta_report_%s%s.csv" % \
            (settings.file_prefix, settings.master_name, settings.file_suffix))
    settings.slave_delta_csv_path = os.path.join(
        settings.out_folder_full,
        "%sdelta_report_%s%s.csv" % \
            (settings.file_prefix, settings.slave_name, settings.file_suffix))

    ### PROCESS OTHER CONFIG ###

    assert settings.store_url, "store url must not be blank"

    settings.act_fields = ";".join(ColDataUser.get_act_import_cols())

    wp_api_params = {
        'api_key': settings.wp_api_key,
        'api_secret': settings.wp_api_secret,
        'url': settings.store_url,
        'wp_user': settings.wp_user,
        'wp_pass': settings.wp_pass,
        'callback': settings.wp_callback
    }

    act_connect_params = {
        'hostname': settings.m_ssh_host,
        'port': settings.m_ssh_port,
        'username': settings.m_ssh_user,
        'password': settings.m_ssh_pass,
    }

    act_db_params = {
        'db_x_exe': settings.m_x_cmd,
        'db_i_exe': settings.m_i_cmd,
        'db_name': settings.m_db_name,
        'db_host': settings.m_db_host,
        'db_user': settings.m_db_user,
        'db_pass': settings.m_db_pass,
        'fields': settings.act_fields,
    }
    if 'since_m' in settings:
        act_db_params['since'] = settings['since_m']

    fs_params = {
        'import_name': settings.import_name,
        'remote_export_folder': settings.remote_export_folder,
        'in_folder': settings.in_folder_full,
        'out_folder': settings.out_folder_full
    }

    #########################################
    # Prepare Filter Data
    #########################################

    print DebugUtils.hashify("PREPARE FILTER DATA"), timediff(settings)

    if settings['do_filter']:
        filter_files = {
            'users': settings['user_file'],
            'emails': settings['email_file'],
            'cards': settings['card_file'],
        }
        filter_items = {}
        for key, filter_file in filter_files.items():
            if filter_file:
                try:
                    with open(os.path.join(settings.in_folder_full,
                                           filter_file)) as filter_file_obj:
                        filter_items[key] = [
                            re.sub(r'\s*([^\s].*[^\s])\s*(?:\n)', r'\1', line)
                            for line in filter_file_obj
                        ]
                except IOError as exc:
                    SanitationUtils.safe_print(
                        "could not open %s file [%s] from %s" % (
                            key, filter_file, unicode(os.getcwd())))
                    raise exc
        if 'since_m' in settings:
            filter_items['sinceM'] = TimeUtils.wp_strp_mktime(settings['since_m'])
        if 'since_s' in settings:
            filter_items['sinceS'] = TimeUtils.wp_strp_mktime(settings['since_s'])
    else:
        filter_items = None

    print filter_items

    #########################################
    # Download / Generate Slave Parser Object
    #########################################

    print DebugUtils.hashify(
        "Download / Generate Slave Parser Object"), timediff(settings)

    sa_parser = CsvParseUser(
        cols=ColDataUser.get_wp_import_cols(),
        defaults=ColDataUser.get_defaults(),
        filter_items=filter_items,
        limit=settings['download_limit'],
        source=settings.slave_name)
    if settings['download_slave']:
        settings.ssh_tunnel_forwarder_address = (settings['ssh_host'],
                                                 settings['ssh_port'])
        settings.ssh_tunnel_forwarder_b_address = (settings['remote_bind_host'],
                                                   settings['remote_bind_port'])
        for host in [
                'ssh_tunnel_forwarder_address',
                'ssh_tunnel_forwarder_bind_address'
        ]:
            try:
                check_address(getattr(settings, host))
            except AttributeError:
                Registrar.register_error("host not specified in settings: %s" %
                                         host)
            except Exception as exc:
                raise UserWarning("Host must be valid: %s [%s = %s]" % (
                    str(exc), host, repr(getattr(settings, host))))
        ssh_tunnel_forwarder_params = {
            'ssh_address_or_host': settings.ssh_tunnel_forwarder_address,
            'ssh_password': settings['ssh_pass'],
            'ssh_username': settings['ssh_user'],
            'remote_bind_address': settings.ssh_tunnel_forwarder_b_address,
        }
        py_my_sql_connect_params = {
            'host': settings['db_host'],
            'user': settings['db_user'],
            'password': settings['db_pass'],
            'db': settings['db_name'],
            'charset': settings['db_charset'],
            'use_unicode': True,
            'tbl_prefix': settings['tbl_prefix'],
        }

        print "SSHTunnelForwarderParams", ssh_tunnel_forwarder_params
        print "PyMySqlconnect_params", py_my_sql_connect_params

        with UsrSyncClientSqlWP(ssh_tunnel_forwarder_params,
                                py_my_sql_connect_params) as client:
            client.analyse_remote(
                sa_parser, limit=settings['download_limit'], filter_items=filter_items)

            sa_parser.get_obj_list().export_items(
                os.path.join(settings.in_folder_full, settings.s_x_name),
                ColDataUser.get_wp_import_col_names())

    else:
        sa_parser.analyse_file(sa_path, sa_encoding)

    # CsvParseUser.print_basic_columns( list(chain( *saParser.emails.values() )) )

    #########################################
    # Generate and Analyse ACT CSV files using shell
    #########################################

    ma_parser = CsvParseUser(
        cols=ColDataUser.get_act_import_cols(),
        defaults=ColDataUser.get_defaults(),
        contact_schema='act',
        filter_items=filter_items,
        limit=settings['download_limit'],
        source=settings.master_name)

    print DebugUtils.hashify("Generate and Analyse ACT data"), timediff(
        settings)

    if settings['download_master']:
        for thing in [
                'm_x_cmd', 'm_i_cmd', 'remote_export_folder', 'act_fields'
        ]:
            assert getattr(settings, thing), "settings must specify %s" % thing

        with UsrSyncClientSshAct(act_connect_params, act_db_params,
                                 fs_params) as master_client:
            master_client.analyse_remote(ma_parser, limit=settings['download_limit'])
    else:
        ma_parser.analyse_file(
            ma_path, dialect_suggestion='ActOut', encoding=ma_encoding)

    # CsvParseUser.print_basic_columns(  saParser.roles['WP'] )
    #
    # exit()
    # quit()

    # print "first maParser source:"
    # print maParser.objects.values()[0]['source']
    # print "first saParse source:"
    # print saParser.objects.values()[0]['source']

    # quit()

    # get matches

    global_matches = MatchList()
    anomalous_match_lists = {}
    new_masters = MatchList()
    new_slaves = MatchList()
    duplicate_matchlists = OrderedDict()
    anomalous_parselists = {}
    # nonstatic_updates = []
    nonstatic_s_updates = []
    nonstatic_m_updates = []
    static_updates = []
    # staticSUpdates = []
    # staticMUpdates = []
    problematic_updates = []
    master_updates = []
    slave_updates = []
    m_delta_updates = []
    s_delta_updates = []
    email_conflict_matches = ConflictingMatchList(
        index_fn=EmailMatcher.email_index_fn)

    def deny_anomalous_match_list(match_list_type, anomalous_match_list):
        """Add the matchlist to the list of anomalous match lists if it is not empty."""
        try:
            assert not anomalous_match_list
        except AssertionError:
            # print "could not deny anomalous match list", match_list_type,
            # exc
            anomalous_match_lists[match_list_type] = anomalous_match_list

    def deny_anomalous_parselist(parselist_type, anomalous_parselist):
        """Add the parselist to the list of anomalous parse lists if it is not empty."""
        try:
            assert not anomalous_parselist
        except AssertionError:
            # print "could not deny anomalous parse list", parselist_type, exc
            anomalous_parselists[parselist_type] = anomalous_parselist

    if settings['do_sync']:  # pylint: disable=too-many-nested-blocks
        # for every username in slave, check that it exists in master
        # TODO: fix too-many-nested-blocks

        print DebugUtils.hashify("processing usernames")
        print timediff(settings)

        deny_anomalous_parselist('saParser.nousernames', sa_parser.nousernames)

        username_matcher = UsernameMatcher()
        username_matcher.process_registers(sa_parser.usernames,
                                           ma_parser.usernames)

        deny_anomalous_match_list('usernameMatcher.slaveless_matches',
                                  username_matcher.slaveless_matches)
        deny_anomalous_match_list('usernameMatcher.duplicate_matches',
                                  username_matcher.duplicate_matches)

        duplicate_matchlists['username'] = username_matcher.duplicate_matches

        global_matches.add_matches(username_matcher.pure_matches)

        if Registrar.DEBUG_MESSAGE:
            print "username matches (%d pure)" % len(
                username_matcher.pure_matches)
            # print repr(usernameMatcher)

        if Registrar.DEBUG_DUPLICATES and username_matcher.duplicate_matches:
            print("username duplicates: %s" %
                  len(username_matcher.duplicate_matches))

        print DebugUtils.hashify("processing cards")
        print timediff(settings)

        # for every card in slave not already matched, check that it exists in
        # master

        deny_anomalous_parselist('maParser.nocards', ma_parser.nocards)

        card_matcher = CardMatcher(global_matches.s_indices,
                                   global_matches.m_indices)
        card_matcher.process_registers(sa_parser.cards, ma_parser.cards)

        deny_anomalous_match_list('cardMatcher.duplicate_matches',
                                  card_matcher.duplicate_matches)
        deny_anomalous_match_list('cardMatcher.masterless_matches',
                                  card_matcher.masterless_matches)

        duplicate_matchlists['card'] = card_matcher.duplicate_matches

        global_matches.add_matches(card_matcher.pure_matches)

        if Registrar.DEBUG_MESSAGE:
            print "card matches (%d pure)" % len(card_matcher.pure_matches)
            # print repr(cardMatcher)

        if Registrar.DEBUG_DUPLICATES and card_matcher.duplicate_matches:
            print "card duplicates: %s" % len(card_matcher.duplicate_matches)

        # #for every email in slave, check that it exists in master

        print DebugUtils.hashify("processing emails")
        print timediff(settings)

        deny_anomalous_parselist("saParser.noemails", sa_parser.noemails)

        email_matcher = NocardEmailMatcher(global_matches.s_indices,
                                           global_matches.m_indices)

        email_matcher.process_registers(sa_parser.nocards, ma_parser.emails)

        new_masters.add_matches(email_matcher.masterless_matches)
        new_slaves.add_matches(email_matcher.slaveless_matches)
        global_matches.add_matches(email_matcher.pure_matches)
        duplicate_matchlists['email'] = email_matcher.duplicate_matches

        if Registrar.DEBUG_MESSAGE:
            print "email matches (%d pure)" % (len(email_matcher.pure_matches))
            # print repr(emailMatcher)

        if Registrar.DEBUG_DUPLICATES and email_matcher.duplicate_matches:
            print "email duplicates: %s" % len(email_matcher.duplicate_matches)

        # TODO: further sort emailMatcher

        print DebugUtils.hashify("BEGINNING MERGE (%d)" % len(global_matches))
        print timediff(settings)

        sync_cols = ColDataUser.get_sync_cols()

        if Registrar.DEBUG_PROGRESS:
            sync_progress_counter = ProgressCounter(len(global_matches))

        for count, match in enumerate(global_matches):
            if Registrar.DEBUG_PROGRESS:
                sync_progress_counter.maybe_print_update(count)
                # print "examining globalMatch %d" % count
                # # print SanitationUtils.safe_print( match.tabulate(tablefmt = 'simple'))
                # print repr(match)

            m_object = match.m_objects[0]
            s_object = match.s_objects[0]

            sync_update = SyncUpdateUsrApi(m_object, s_object)
            sync_update.update(sync_cols)

            # if(Registrar.DEBUG_MESSAGE):
            #     print "examining SyncUpdate"
            #     SanitationUtils.safe_print( syncUpdate.tabulate(tablefmt = 'simple'))

            if sync_update.m_updated and sync_update.m_deltas:
                insort(m_delta_updates, sync_update)

            if sync_update.s_updated and sync_update.s_deltas:
                insort(s_delta_updates, sync_update)

            if not sync_update:
                continue

            if sync_update.s_updated:
                sync_slave_updates = sync_update.get_slave_updates()
                if 'E-mail' in sync_slave_updates:
                    new_email = sync_slave_updates['E-mail']
                    if new_email in sa_parser.emails:
                        m_objects = [m_object]
                        s_objects = [s_object] + sa_parser.emails[new_email]
                        SanitationUtils.safe_print("duplicate emails",
                                                   m_objects, s_objects)
                        try:
                            email_conflict_matches.add_match(
                                Match(m_objects, s_objects))
                        except Exception as exc:
                            SanitationUtils.safe_print(
                                ("something happened adding an email "
                                 "conflict, new_email: %s ; exception: %s") %
                                (new_email, exc))
                        continue

            if not sync_update.important_static:
                if sync_update.m_updated and sync_update.s_updated:
                    if sync_update.s_mod:
                        insort(problematic_updates, sync_update)
                        continue
                elif sync_update.m_updated and not sync_update.s_updated:
                    insort(nonstatic_m_updates, sync_update)
                    if sync_update.s_mod:
                        insort(problematic_updates, sync_update)
                        continue
                elif sync_update.s_updated and not sync_update.m_updated:
                    insort(nonstatic_s_updates, sync_update)
                    if sync_update.s_mod:
                        insort(problematic_updates, sync_update)
                        continue

            if sync_update.s_updated or sync_update.m_updated:
                insort(static_updates, sync_update)
                if sync_update.m_updated and sync_update.s_updated:
                    insort(master_updates, sync_update)
                    insort(slave_updates, sync_update)
                if sync_update.m_updated and not sync_update.s_updated:
                    insort(master_updates, sync_update)
                if sync_update.s_updated and not sync_update.m_updated:
                    insort(slave_updates, sync_update)

        print DebugUtils.hashify("COMPLETED MERGE")
        print timediff(settings)

        # TODO: process duplicates here

    #########################################
    # Write Report
    #########################################

    print DebugUtils.hashify("Write Report")
    print timediff(settings)

    with io.open(settings.rep_path_full, 'w+', encoding='utf8') as res_file:

        repd_file = None
        if settings['process_duplicates']:
            repd_file = io.open(settings['repd_path'], 'w+', encoding='utf8')

        css = ""
        reporter = HtmlReporter(css=css)

        basic_cols = ColDataUser.get_basic_cols()
        address_cols = OrderedDict(basic_cols.items() + [
            ('address_reason', {}),
            ('Edited Address', {}),
            ('Edited Alt Address', {}),
        ])
        name_cols = OrderedDict(basic_cols.items() + [
            ('name_reason', {}),
            ('Edited Name', {}),
        ])
        csv_colnames = ColDataUser.get_col_names(
            OrderedDict(basic_cols.items() + ColDataUser.name_cols([
                'address_reason',
                'name_reason',
                'Edited Name',
                'Edited Address',
                'Edited Alt Address',
            ]).items()))

        sanitizing_group = HtmlReporter.Group('sanitizing',
                                              'Sanitizing Results')

        if sa_parser.bad_address:
            sanitizing_group.add_section(
                HtmlReporter.Section(
                    's_bad_addresses_list',
                    title='Bad %s Address List' % settings.slave_name.title(),
                    description='%s records that have badly formatted addresses'
                    % settings.slave_name,
                    data=UsrObjList(sa_parser.bad_address.values()).tabulate(
                        cols=address_cols,
                        tablefmt='html', ),
                    length=len(sa_parser.bad_address)))

        if sa_parser.bad_name:
            sanitizing_group.add_section(
                HtmlReporter.Section(
                    's_bad_names_list',
                    title='Bad %s Names List' % settings.slave_name.title(),
                    description='%s records that have badly formatted names' %
                    settings.slave_name,
                    data=UsrObjList(sa_parser.bad_name.values()).tabulate(
                        cols=name_cols,
                        tablefmt='html', ),
                    length=len(sa_parser.bad_name)))
        if sa_parser.bad_name or sa_parser.bad_address:
            UsrObjList(sa_parser.bad_name.values() + ma_parser.bad_address.
                       values()).export_items(settings['w_pres_csv_path'], csv_colnames)

        if ma_parser.bad_address:
            sanitizing_group.add_section(
                HtmlReporter.Section(
                    'm_bad_addresses_list',
                    title='Bad %s Address List' % settings.master_name.title(),
                    description='%s records that have badly formatted addresses'
                    % settings.master_name,
                    data=UsrObjList(ma_parser.bad_address.values()).tabulate(
                        cols=address_cols,
                        tablefmt='html', ),
                    length=len(ma_parser.bad_address)))

        if ma_parser.bad_name:
            sanitizing_group.add_section(
                HtmlReporter.Section(
                    'm_bad_names_list',
                    title='Bad %s Names List' % settings.master_name.title(),
                    description='%s records that have badly formatted names' %
                    settings.master_name,
                    data=UsrObjList(ma_parser.bad_name.values()).tabulate(
                        cols=name_cols,
                        tablefmt='html', ),
                    length=len(ma_parser.bad_name)))

        if ma_parser.bad_name or ma_parser.bad_address:
            UsrObjList(ma_parser.bad_name.values() + ma_parser.bad_address.values())\
                .export_items(settings['master_res_csv_path'], csv_colnames)

        reporter.add_group(sanitizing_group)

        if settings['do_sync'] and (m_delta_updates + s_delta_updates):

            delta_group = HtmlReporter.Group('deltas', 'Field Changes')

            m_delta_list = UsrObjList(
                filter(None, [update.new_m_object
                              for update in m_delta_updates]))

            s_delta_list = UsrObjList(
                filter(None, [update.new_s_object
                              for update in s_delta_updates]))

            delta_cols = ColDataUser.get_delta_cols()

            all_delta_cols = OrderedDict(
                ColDataUser.get_basic_cols().items() + ColDataUser.name_cols(
                    delta_cols.keys() + delta_cols.values()).items())

            if m_delta_list:
                delta_group.add_section(
                    HtmlReporter.Section(
                        'm_deltas',
                        title='%s Changes List' % settings.master_name.title(),
                        description='%s records that have changed important fields'
                        % settings.master_name,
                        data=m_delta_list.tabulate(
                            cols=all_delta_cols, tablefmt='html'),
                        length=len(m_delta_list)))

            if s_delta_list:
                delta_group.add_section(
                    HtmlReporter.Section(
                        's_deltas',
                        title='%s Changes List' % settings.slave_name.title(),
                        description='%s records that have changed important fields'
                        % settings.slave_name,
                        data=s_delta_list.tabulate(
                            cols=all_delta_cols, tablefmt='html'),
                        length=len(s_delta_list)))

            reporter.add_group(delta_group)
            if m_delta_list:
                m_delta_list.export_items(
                    settings['master_delta_csv_path'],
                    ColDataUser.get_col_names(all_delta_cols))
            if s_delta_list:
                s_delta_list.export_items(
                    settings['slave_delta_csv_path'],
                    ColDataUser.get_col_names(all_delta_cols))

        report_matching = settings['do_sync']
        if report_matching:

            matching_group = HtmlReporter.Group('matching', 'Matching Results')
            matching_group.add_section(
                HtmlReporter.Section(
                    'perfect_matches',
                    **{
                        'title':
                        'Perfect Matches',
                        'description':
                        "%s records match well with %s" % (
                            settings.slave_name, settings.master_name),
                        'data':
                        global_matches.tabulate(tablefmt="html"),
                        'length':
                        len(global_matches)
                    }))

            match_list_instructions = {
                'cardMatcher.masterless_matches':
                '%s records do not have a corresponding CARD ID in %s (deleted?)'
                % (settings.slave_name, settings.master_name),
                'usernameMatcher.slaveless_matches':
                '%s records have no USERNAMEs in %s' %
                (settings.master_name, settings.slave_name),
            }

            for matchlist_type, match_list in anomalous_match_lists.items():
                if not match_list:
                    continue
                description = match_list_instructions.get(matchlist_type,
                                                          matchlist_type)
                if ('masterless' in matchlist_type or
                        'slaveless' in matchlist_type):
                    data = match_list.merge().tabulate(tablefmt="html")
                else:
                    data = match_list.tabulate(tablefmt="html")
                matching_group.add_section(
                    HtmlReporter.Section(
                        matchlist_type,
                        **{
                            # 'title': matchlist_type.title(),
                            'description': description,
                            'data': data,
                            'length': len(match_list)
                        }))

            # print DebugUtils.hashify("anomalous ParseLists: ")

            parse_list_instructions = {
                "saParser.noemails":
                "%s records have invalid emails" % settings.slave_name,
                "maParser.noemails":
                "%s records have invalid emails" % settings.master_name,
                "maParser.nocards":
                "%s records have no cards" % settings.master_name,
                "saParser.nousernames":
                "%s records have no username" % settings.slave_name
            }

            for parselist_type, parse_list in anomalous_parselists.items():
                description = parse_list_instructions.get(parselist_type,
                                                          parselist_type)
                usr_list = UsrObjList()
                for obj in parse_list.values():
                    usr_list.append(obj)

                data = usr_list.tabulate(tablefmt="html")

                matching_group.add_section(
                    HtmlReporter.Section(
                        parselist_type,
                        **{
                            # 'title': matchlist_type.title(),
                            'description': description,
                            'data': data,
                            'length': len(parse_list)
                        }))

            reporter.add_group(matching_group)

        report_sync = settings['do_sync']
        if report_sync:
            syncing_group = HtmlReporter.Group('sync', 'Syncing Results')

            syncing_group.add_section(
                HtmlReporter.Section(
                    (settings.master_name + "_updates"),
                    description=settings.master_name +
                    " items will be updated",
                    data='<hr>'.join([
                        update.tabulate(tablefmt="html")
                        for update in master_updates
                    ]),
                    length=len(master_updates)))

            syncing_group.add_section(
                HtmlReporter.Section(
                    (settings.slave_name + "_updates"),
                    description=settings.slave_name + " items will be updated",
                    data='<hr>'.join([
                        update.tabulate(tablefmt="html")
                        for update in slave_updates
                    ]),
                    length=len(slave_updates)))

            syncing_group.add_section(
                HtmlReporter.Section(
                    "problematic_updates",
                    description="items can't be merged because they are too dissimilar",
                    data='<hr>'.join([
                        update.tabulate(tablefmt="html")
                        for update in problematic_updates
                    ]),
                    length=len(problematic_updates)))

            reporter.add_group(syncing_group)

        report_duplicates = settings['process_duplicates']
        if report_duplicates:

            dup_css = """
.highlight_old {color: red !important; }
.highlight_old {color: orange;}
.highlight_master {background: lightblue !important;}
.highlight_slave {background: lightpink !important;}
            """
            dup_reporter = HtmlReporter(css=dup_css)
            duplicate_group = HtmlReporter.Group('dup', 'Duplicate Results')

            basic_cols = ColDataUser.get_basic_cols()
            dup_cols = OrderedDict(basic_cols.items() + [
                # ('Create Date', {}),
                # ('Last Sale', {})
            ])

            # What we're doing here is analysing the duplicates we've seen so far, and
            # creating a list of all the potential objects to delete and WHY
            # they should be deleted.

            def fn_obj_source_is(target_source):
                """Return function that checks if object source equals target source."""

                def obj_source_is(object_data):
                    """Check if the object source equals target source."""

                    obj_source = object_data.get('source')
                    if obj_source and target_source == obj_source:
                        return True

                return obj_source_is

            def fn_user_older_than_wp(wp_time):
                """Return function ot check user is older than wp_time."""
                wp_time_obj = TimeUtils.wp_strp_mktime(wp_time)
                assert wp_time_obj, "should be valid time struct: %s" % wp_time

                def user_older_than(user_data):
                    """Determine if user is older than wp_time."""
                    if fn_obj_source_is(settings.master_name)(user_data):
                        assert hasattr(user_data, 'act_last_transaction'), \
                            "%s user should have act_last_transaction attr: %s, %s, source: %s" % (
                                settings.master_name,
                                type(user_data),
                                SanitationUtils.coerce_ascii(user_data),
                                user_data.get('source'))
                        user_time_obj = user_data.act_last_transaction
                    else:
                        user_time_obj = user_data.last_modtime
                    return user_time_obj < wp_time_obj

                return user_older_than

            duplicates = Duplicates()

            for duplicate_type, duplicate_matchlist in duplicate_matchlists.items(
            ):
                print "checking duplicates of type %s" % duplicate_type
                print "len(duplicate_matchlist) %s" % len(duplicate_matchlist)
                for match in duplicate_matchlist:
                    if match.m_len <= 1:
                        continue
                        # only care about master duplicates at the moment
                    duplicate_objects = list(match.m_objects)
                    duplicates.add_conflictors(duplicate_objects,
                                               duplicate_type)

            address_duplicates = {}
            for address, objects in ma_parser.addresses.items():
                # print "analysing address %s " % address
                # for object_data in objects:
                # print " -> associated object: %s" % object_data
                if len(objects) > 1:
                    # if there are more than one objects associated with an address,
                    # add to the duplicate addresses report
                    address_duplicates[address] = objects
                    duplicates.add_conflictors(
                        objects, "address", weighting=0.1)

            for object_data in ma_parser.objects.values():
                if fn_user_older_than_wp(settings['old_threshold'])(object_data):
                    details = TimeUtils.wp_time_to_string(
                        object_data.act_last_transaction)
                    duplicates.add_conflictor(
                        object_data, "last_transaction_old", 0.5, details)
                elif fn_user_older_than_wp(settings['oldish_threshold'])(object_data):
                    details = TimeUtils.wp_time_to_string(
                        object_data.act_last_transaction)
                    duplicates.add_conflictor(
                        object_data, "last_transaction_oldish", 0.2, details)

            highlight_rules_master_slave = [
                ('highlight_master', fn_obj_source_is(settings.master_name)),
                ('highlight_slave', fn_obj_source_is(settings.slave_name))
            ]

            highlight_rules_old = [
                ('highlight_oldish', fn_user_older_than_wp(settings['oldish_threshold'])),
                ('highlight_old', fn_user_older_than_wp(settings['old_threshold']))
            ]

            highlight_rules_all = highlight_rules_master_slave + highlight_rules_old

            # if Registrar.DEBUG_DUPLICATES:
            # print duplicates.tabulate({}, tablefmt='plain')
            if duplicates:
                duplicate_group.add_section(
                    HtmlReporter.Section('all duplicates', **{
                        'title':
                        'All Duplicates',
                        'description':
                        "%s records are involved in duplicates" %
                        settings.master_name,
                        'data':
                        duplicates.tabulate(
                            dup_cols,
                            tablefmt='html',
                            highlight_rules=highlight_rules_all),
                        'length':
                        len(duplicates)
                    }))

            email_conflict_data = email_conflict_matches.tabulate(
                cols=dup_cols,
                tablefmt="html",
                highlight_rules=highlight_rules_all)
            duplicate_group.add_section(
                HtmlReporter.Section(
                    "email conflicts",
                    **{
                        # 'title': matchlist_type.title(),
                        'description': "email conflicts",
                        'data': email_conflict_data,
                        'length': len(email_conflict_matches)
                    }))

            email_duplicate_data = email_matcher.duplicate_matches.tabulate(
                tablefmt="html", highlight_rules=highlight_rules_all)
            if email_matcher.duplicate_matches:
                duplicate_group.add_section(
                    HtmlReporter.Section('email_duplicates', **{
                        'title':
                        'Email Duplicates',
                        'description':
                        "%s records match with multiple records in %s on email"
                        % (settings.slave_name, settings.master_name),
                        'data':
                        email_duplicate_data,
                        'length':
                        len(email_matcher.duplicate_matches)
                    }))

            match_list_instructions = {
                'cardMatcher.duplicate_matches':
                '%s records have multiple CARD IDs in %s' %
                (settings.slave_name, settings.master_name),
                'usernameMatcher.duplicate_matches':
                '%s records have multiple USERNAMEs in %s' %
                (settings.slave_name, settings.master_name)
            }

            for matchlist_type, match_list in anomalous_match_lists.items():
                if not match_list:
                    continue
                description = match_list_instructions.get(matchlist_type,
                                                          matchlist_type)
                if ('masterless' in matchlist_type or
                        'slaveless' in matchlist_type):
                    data = match_list.merge().tabulate(tablefmt="html")
                else:
                    data = match_list.tabulate(
                        tablefmt="html", highlight_rules=highlight_rules_all)
                matching_group.add_section(
                    HtmlReporter.Section(
                        matchlist_type,
                        **{
                            # 'title': matchlist_type.title(),
                            'description': description,
                            'data': data,
                            'length': len(match_list)
                        }))

            if address_duplicates:

                print "there are address duplicates"
                duplicate_group.add_section(
                    HtmlReporter.Section(
                        'address_duplicates',
                        title='Duplicate %s Addresses' %
                        settings.master_name.title(),
                        description='%s addresses that appear in multiple records'
                        % settings.master_name,
                        data="<br/>".join([
                            "<h4>%s</h4><p>%s</p>" % (address, UsrObjList(
                                objects).tabulate(
                                    cols=dup_cols,
                                    tablefmt='html',
                                    highlight_rules=highlight_rules_old))
                            for address, objects in address_duplicates.items()
                        ]),
                        length=len(address_duplicates)))
            dup_reporter.add_group(duplicate_group)
            repd_file.write(dup_reporter.get_document_unicode())

        res_file.write(reporter.get_document_unicode())

    #########################################
    # Update databases
    #########################################

    all_updates = static_updates
    if settings.do_problematic:
        all_updates += problematic_updates

    print DebugUtils.hashify("Update databases (%d)" % len(all_updates))
    print timediff(settings)

    master_failures = []
    slave_failures = []

    if all_updates:
        Registrar.register_progress("UPDATING %d RECORDS" % len(all_updates))

        if settings['ask_before_update']:
            try:
                input(
                    "Please read reports and press Enter to continue or ctrl-c to stop..."
                )
            except SyntaxError:
                pass

        if Registrar.DEBUG_PROGRESS:
            update_progress_counter = ProgressCounter(len(all_updates))

        with \
                UsrSyncClientSshAct(act_connect_params, act_db_params, fs_params) \
                    as master_client, \
                UsrSyncClientWP(wp_api_params) as slave_client:
            # UsrSyncClient_JSON(jsonconnect_params) as slave_client:

            for count, update in enumerate(all_updates):
                if Registrar.DEBUG_PROGRESS:
                    update_progress_counter.maybe_print_update(count)
                # if update.wpid == '1':
                #     print repr(update.wpid)
                #     continue
                if settings['update_master'] and update.m_updated:
                    try:
                        update.update_master(master_client)
                    except Exception as exc:
                        master_failures.append({
                            'update':
                            update,
                            'master':
                            SanitationUtils.coerce_unicode(
                                update.new_m_object),
                            'slave':
                            SanitationUtils.coerce_unicode(
                                update.new_s_object),
                            'mchanges':
                            SanitationUtils.coerce_unicode(
                                update.get_master_updates()),
                            'schanges':
                            SanitationUtils.coerce_unicode(
                                update.get_slave_updates()),
                            'exception':
                            repr(exc)
                        })
                        Registrar.register_error(
                            "ERROR UPDATING MASTER (%s): %s\n%s" %
                            (update.master_id, repr(exc),
                             traceback.format_exc()))

                        # continue
                if settings['update_slave'] and update.s_updated:
                    try:
                        update.update_slave(slave_client)
                    except Exception as exc:
                        slave_failures.append({
                            'update':
                            update,
                            'master':
                            SanitationUtils.coerce_unicode(
                                update.new_m_object),
                            'slave':
                            SanitationUtils.coerce_unicode(
                                update.new_s_object),
                            'mchanges':
                            SanitationUtils.coerce_unicode(
                                update.get_master_updates()),
                            'schanges':
                            SanitationUtils.coerce_unicode(
                                update.get_slave_updates()),
                            'exception':
                            repr(exc)
                        })
                        Registrar.register_error(
                            "ERROR UPDATING SLAVE (%s): %s\n%s" %
                            (update.slave_id, repr(exc),
                             traceback.format_exc()))

    def output_failures(failures, file_path):
        """
        Output a list of lists of failures as a csv file to the path specified.
        """
        with open(file_path, 'w+') as out_file:
            for failure in failures:
                Registrar.register_error(failure)
            dictwriter = unicodecsv.DictWriter(
                out_file,
                fieldnames=[
                    'update', 'master', 'slave', 'mchanges', 'schanges',
                    'exception'
                ],
                extrasaction='ignore', )
            dictwriter.writerows(failures)
            print "WROTE FILE: ", file_path

    output_failures(master_failures, settings.m_fail_path_full)
    output_failures(slave_failures, settings.s_fail_path_full)

    # Registrar.register_error('testing errors')


def catch_main(override_args=None):
    """
    Run the main function within a try statement and attempt to analyse failure.
    """

    settings = SettingsNamespaceUser()

    status = 0

    try:
        main(settings=settings, override_args=override_args)
    except SystemExit:
        exit()
    except (ReadTimeout, ConnectionError, ConnectTimeout, ServerNotFoundError):
        status = 69  # service unavailable
        Registrar.register_error(traceback.format_exc())
    except IOError:
        status = 74
        print "cwd: %s" % os.getcwd()
        Registrar.register_error(traceback.format_exc())
    except UserWarning:
        status = 65
        Registrar.register_error(traceback.format_exc())
    except:
        status = 1
        Registrar.register_error(traceback.format_exc())

    with io.open(settings.log_path_full, 'w+', encoding='utf8') as log_file:
        for source, messages in Registrar.get_message_items(1).items():
            print source
            log_file.writelines([SanitationUtils.coerce_unicode(source)])
            log_file.writelines([
                SanitationUtils.coerce_unicode(message) for message in messages
            ])
            for message in messages:
                pprint(message, indent=4, width=80, depth=2)

    #########################################
    # email reports
    #########################################

    files_to_zip = [
        settings.m_fail_path_full, settings.s_fail_path_full, settings.rep_path_full
    ]

    with zipfile.ZipFile(settings.zip_path_full, 'w') as zip_file:
        for file_to_zip in files_to_zip:
            try:
                os.stat(file_to_zip)
                zip_file.write(file_to_zip)
            except Exception as exc:
                if exc:
                    pass
        Registrar.register_message('wrote file %s' % settings.zip_path_full)


if __name__ == '__main__':
    catch_main()
