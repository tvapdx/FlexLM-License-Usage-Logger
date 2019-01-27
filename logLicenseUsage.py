import os
import os.path as op
import sys
import re
import subprocess
import datetime as dt
import csv
import configparser
from collections import namedtuple

import records
import requests


# INTERNAL CONFIGS ============================================================
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
FILENAME_DATETIME_FORMAT = '%Y-%m-%d'
FEATURES_FILENAME_FORMAT = '{datetime} features.csv'
USERS_FILENAME_FORMAT = '{datetime} {feat_code} users.csv'

# main config filepath. can include env vars
CFG_GILEPATH = r'%programdata%\FlexLMLicenseUsageLoggerConfig.ini'

# DATA TYPES ==================================================================
LMUser = namedtuple('LMUser', ['feature_code', 'userid', 'host', 'display',
                               'feature_version', 'server_host', 'server_port',
                               'license_handle', 'checkout_datetime',
                               'active_time', 'overnight', 'update_time'])


LMFeature = namedtuple('LMFeature', ['timestamp', 'feature_code',
                                     'feature_version', 'vendor',
                                     'license_type', 'issued', 'used',
                                     'users'])

LMFeatureCode = namedtuple('LMFeatureCode', ['feature_name', 'feature_codes'])

# FUNCTIONS ====================================================================
def get_config():
    cfg_file = op.expandvars(CFG_GILEPATH)
    if not op.exists(cfg_file):
        raise Exception('Config file does not exit: {}'.format(cfg_file))
    
    config = configparser.ConfigParser()
    config.read(cfg_file)
    return config['DEFAULT']


def get_db(cfg):
    cnn_string = \
        '{dbms}://{dbuser}:{dbpass}@{dbhost}:{dbport}/{dbname}'.format(
            dbms=cfg['dbms'],
            dbuser=cfg['dbuser'],
            dbpass=cfg['dbpass'],
            dbhost=cfg['dbhost'],
            dbport=cfg['dbport'],
            dbname=cfg['dbname']
        )
    return records.Database(cnn_string)  


def extract_users(feature_code, feat_data, time):
    users = []
    for fdata in feat_data:
        udm = re.match(r'\s+(.+) (.+) (.+) \(v(.+)\) \((.+)/(.+) (.+)\), '
                       r'start (.+) (\d+)/(\d+) (\d*):(\d*)', fdata)
        if udm:
            co_dt = dt.datetime(year=dt.datetime.today().year,
                                month=int(udm.groups()[8]),
                                day=int(udm.groups()[9]),
                                hour=int(udm.groups()[10]),
                                minute=int(udm.groups()[11]))
            timediff = time - co_dt
            users.append(LMUser(feature_code=feature_code,
                                userid=udm.groups()[0],
                                host=udm.groups()[1],
                                display=udm.groups()[2],
                                feature_version=udm.groups()[3],
                                server_host=udm.groups()[4],
                                server_port=udm.groups()[5],
                                license_handle=udm.groups()[6],
                                checkout_datetime=\
                                    co_dt.strftime(DATETIME_FORMAT),
                                active_time=round(timediff.seconds / 3600),
                                overnight=timediff.days > 0,
                                update_time=time.strftime(DATETIME_FORMAT)))

    # process the output and extract usernames and license checkout info
    return users


def extract_feature(feat_data, time, lmversion):
    feature_data = []
    for fdata in feat_data.split('\r\n'):
        if fdata:
            feature_data.append(fdata)

    feature_license_info = feature_data[0]
    flmm = re.match(r'(.+?)?:  ' \
                    r'\(Total of (\d+?) license[s]* issued;  ' \
                    r'Total of (\d+?) license[s]* in use\)',
                    feature_license_info)
    if flmm:
        feature_code = flmm.groups()[0]
        if feature_code:
            issued = flmm.groups()[1]
            used = flmm.groups()[2]

            feature_version = vendor = license_type = None
            users = []

            if len(feature_data) > 1:
                feature_info = feature_data[1]
                fim = re.match(r'.+?v(.+?), vendor: (.+?), expiry: (.+)',
                               feature_info)
                if fim:
                    feature_version = fim.groups()[0]

                if lmversion == '2017':
                    feature_vendor = feature_data[2]
                    fvm = re.match(r'.+?vendor_string: (.+)', feature_vendor)
                    if fvm:
                        vendor = fvm.groups()[0]

                    feature_license = feature_data[3]
                    flm = re.match(r'\s+(.+?) license', feature_license)
                    if flm:
                        license_type = flm.groups()[0]

                elif lmversion == '2015':
                    feature_license = feature_data[2]
                    flm = re.match(r'\s+(.+?) license', feature_license)
                    if flm:
                        license_type = flm.groups()[0]

                if len(feature_data) > 4:
                    users = extract_users(feature_code,
                                          feature_data[4:],
                                          time=time)

            return LMFeature(timestamp=time.strftime(DATETIME_FORMAT),
                             feature_code=feature_code,
                             feature_version=feature_version or '--',
                             vendor=vendor or '--',
                             license_type=license_type or '--',
                             issued=issued or '--',
                             used=used or '--',
                             users=users)


def write_users(features, dest_path):
    for feature in features:
        user_file = op.join(
            dest_path,
            USERS_FILENAME_FORMAT.format(
                feat_code=feature.feature_code,
                datetime=dt.datetime.now().strftime(FILENAME_DATETIME_FORMAT)
                ))
        if not op.exists(user_file):
            with open(user_file, 'w') as csvfile:
                csvwriter = \
                    csv.writer(csvfile,
                            quoting=csv.QUOTE_MINIMAL, lineterminator='\n')        
                csvwriter.writerow(
                    ['feature_code', 'userid', 'host','display',
                     'feature_version',
                     'server_host', 'server_port', 'license_handle',
                     'checkout_datetime', 'update_time']
                    )

        with open(user_file, 'a') as csvfile:
            csvwriter = \
                csv.writer(csvfile,
                           quoting=csv.QUOTE_MINIMAL,
                           lineterminator='\n')        
            for u in feature.users:
                csvwriter.writerow(
                    [u.feature_code,
                     u.userid, u.host, u.display, u.feature_version,
                     u.server_host, u.server_port, u.license_handle,
                     u.checkout_datetime, u.update_time]
                                    )


def write_features(features, dest_path):
    feat_file = op.join(
            dest_path,
            FEATURES_FILENAME_FORMAT.format(
                datetime=dt.datetime.now().strftime(FILENAME_DATETIME_FORMAT)
                ))
    if not op.exists(feat_file):
        with open(feat_file, 'w') as csvfile:
            csvwriter = \
                csv.writer(csvfile,
                           quoting=csv.QUOTE_MINIMAL, lineterminator='\n')        
            csvwriter.writerow(['stamp', 'feature_code',
                                'feature_version', 'vendor', 'license_type',
                                'issued', 'used', 'users'])
    with open(feat_file, 'a') as csvfile:
        csvwriter = \
            csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')        
        for f in features:
            csvwriter.writerow([f.timestamp,
                                f.feature_code,
                                f.feature_version, f.vendor, f.license_type,
                                f.issued, f.used, len(f.users)])


def read_users(user_file):
    users = []
    with open(user_file, 'r') as csvfile:
        csvreader = \
            csv.reader(csvfile, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
        first_row = True
        for row in csvreader:
            if first_row:
                first_row = False
                continue
            elif len(row) == 10:
                users.append(
                    LMUser(
                        feature_code=row[0],
                        userid=row[1],
                        host=row[2],
                        display=row[3],
                        feature_version=row[4],
                        server_host=row[5],
                        server_port=row[6],
                        license_handle=row[7],
                        checkout_datetime=row[8],
                        active_time=None,
                        overnight=None,
                        update_time=row[9]
                        )
                )
    # use a lmfearure as wrapper for compatibility with push_users
    return LMFeature(
        timestamp=None,
        feature_code=None,
        feature_version=None,
        vendor=None,
        license_type=None,
        issued=None,
        used=None,
        users=users
        )


def read_features(feat_file):
    features = []
    with open(feat_file, 'r') as csvfile:
        csvreader = \
            csv.reader(csvfile, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')        
        first_row = True
        for row in csvreader:
            if first_row:
                first_row = False
                continue
            elif len(row) == 8:
                features.append(
                    LMFeature(
                        timestamp=row[0],
                        feature_code=row[1],
                        feature_version=row[2],
                        vendor=row[3],
                        license_type=row[4],
                        issued=row[5],
                        used=row[6],
                        users='*' * int(row[7])
                        )
                )
    return features


def read_feature_codes(featcode_file):
    featurecodes = []
    with open(featcode_file, 'r') as csvfile:
        csvreader = \
            csv.reader(csvfile, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')        
        first_row = True
        for row in csvreader:
            if first_row:
                first_row = False
                continue
            else:
                featurecodes.append(
                    LMFeatureCode(
                        feature_name=row[0],
                        feature_codes=';'.join(row[1:]))
                )
    return featurecodes


def push_users(features, db, cfg):
    insertquery = \
    "INSERT INTO {table} values ".format(table=cfg['dbflexuserstable'])
    query_values_template  = \
        "('{fcode}', '{userid}', '{host}', '{display}', " \
        "'{fver}', '{shost}', '{sport}', '{lichandle}', " \
        "'{ctime}', '{utime}')"
    data_values = []
    for f in features:
        for u in f.users:
            print('+ pushing %s users of "%s"' % (len(f.users), f.feature_code))
            data_values.append(query_values_template.format(
                fcode=u.feature_code,
                userid=u.userid,
                host=u.host,
                display=u.display,
                fver=u.feature_version,
                shost=u.server_host,
                sport=u.server_port,
                lichandle=u.license_handle,
                ctime=u.checkout_datetime,
                utime=u.update_time
            ))
    if data_values:
        insertquery += ', '.join(data_values) + ';'
        db.query(insertquery)


def push_features(features, db, cfg):
    insertquery = \
        "INSERT INTO {table} values ".format(table=cfg['dbflexfeaturestable'])
    query_values_template  = \
        "('{dtime}', '{fcode}', '{fver}', '{vendor}', " \
        "'{lictype}', '{issued}', '{used}', '{ausers}')"
    data_values = []
    for f in features:
        print('+ pushing "%s" with %s users' % (f.feature_code, len(f.users)))
        data_values.append(query_values_template.format(
            dtime=f.timestamp,
            fcode=f.feature_code,
            fver=f.feature_version,
            vendor=f.vendor,
            lictype=f.license_type,
            issued=f.issued,
            used=f.used,
            ausers=len(f.users),
        ))
    if data_values:
        insertquery += ', '.join(data_values) + ';'
        db.query(insertquery)


def push_featcodes(featcodes, db, cfg):
    insertquery = \
        "INSERT INTO {table} values ".format(
            table=cfg['dbflexfeaturecodestable']
            )
    query_values_template = "('{fname}', '{fcodes}')"
    data_values = []
    for fc in featcodes:
        data_values.append(query_values_template.format(
            fname=fc.feature_name,
            fcodes=fc.feature_codes,
        ))
    insertquery += ', '.join(data_values) + ';'
    db.query(insertquery)


def determine_lmutil_version():
    result = subprocess.run('lmutil', stdout=subprocess.PIPE)
    help_report = result.stdout.decode('utf-8')
    verm = re.match(r'.+\(c\) 1989-(\d\d\d\d) .+', help_report)
    if verm:
        return verm.groups()[0]


def get_lmstatus(configs):
    # grab lmutil license manager status output
    lic_file = configs['licfile']
    if op.exists(lic_file):
        command = 'lmutil lmstat -c "{}" -a -i'.format(lic_file)
    else:
        command = 'lmutil lmstat -a -i'
    result = subprocess.run(command, stdout=subprocess.PIPE)
    return result.stdout.decode('utf-8')


# MAIN() ======================================================================

# save timestamp so all records use the same and are not affected by io
timestamp = dt.datetime.now()
lmversion = determine_lmutil_version()

# get config
cfg = get_config()
print('configs:')
for key, value in cfg.items():
    print('{}= {}'.format(key, value))

# process cli arguments
# this is a secret feature to help push the old csv files to db server
args = sys.argv[1:]
if args:
    if args[0] == 'pushf':
        for ff in sorted(os.listdir(args[1])):
            exist_feats = read_features(op.join(args[1], ff))
            print('{} feature records read from file: {}'
                .format(len(exist_feats), ff))
            if exist_feats:
                push_features(exist_feats, get_db(cfg), cfg)

    elif args[0] == 'pushu':
        for ff in sorted(os.listdir(args[1])):
            exist_feat = read_users(op.join(args[1], ff))
            print('{} user records read from file: {}'
                .format(len(exist_feat.users), ff))
            if exist_feat.users:
                push_users([exist_feat], get_db(cfg), cfg)

    elif args[0] == 'pushfc':
        featcodes_path = op.join(op.dirname(__file__), 'Feature Codes')
        for ff in sorted(os.listdir(featcodes_path)):
            featcodes = read_feature_codes(op.join(featcodes_path, ff))
            print('{} feature codes read from file: {}'
                .format(len(featcodes), ff))
            if featcodes:
                push_featcodes(featcodes, get_db(cfg), cfg)
else:
    # othewise pull the lm status and update
    status_report = get_lmstatus(cfg)
    if status_report:
        features = []
        # extract data chunks
        features_data = status_report.split('Users of ')
        server_data = features_data[0]
        features_data.pop(0)
        features_data[-1] = features_data[-1].split('NOTE:')[0]

        # process the output and extract license usage info (issued vs used)
        for feat_data in features_data:
            lmf = extract_feature(feat_data, timestamp, lmversion)
            if lmf:
                features.append(lmf)

        # check whether to log usage
        write_users_log = cfg['logusers'].lower() == 'true'
        # write the license usage info
        if cfg['usedb']:
            db = get_db(cfg)
            push_features(features, db, cfg)
            if write_users_log:
                push_users(features, db, cfg)
        else:
            logpath = cfg['logpath']
            write_features(features, logpath)
            if write_users_log:
                write_users(features, logpath)
        
        success = True
        if cfg['ping']:
            URL = cfg['pingurl']
            if URL:
                requests.get(URL if success else URL + "/fail")