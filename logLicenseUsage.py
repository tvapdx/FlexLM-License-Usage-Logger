import os
import os.path as op
import re
import subprocess
import datetime as dt
import csv
import configparser
from collections import namedtuple


# INTERNAL CONFIGS ============================================================
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
FILENAME_DATETIME_FORMAT = '%Y-%m-%d'
FEATURES_FILENAME_FORMAT = '{datetime} features.csv'
USERS_FILENAME_FORMAT = '{datetime} {feat_name} {feat_code} users.csv'


# DATA TYPES ==================================================================
LMUser = namedtuple('LMUser', ['userid', 'host', 'display', 'feature_version',
                               'server_host', 'server_port', 'license_handle',
                               'checkout_datetime', 'active_time',
                               'overnight', 'update_time'])


LMFeature = namedtuple('LMFeature', ['feature_name', 'feature_code',
                                     'feature_version', 'vendor',
                                     'license_type', 'issued', 'used',
                                     'users'])


# FUNCTIONS ====================================================================
def get_config():
    cfg_file = op.expandvars(r'%programdata%\logLicenseUsage.ini')
    if not op.exists(cfg_file):
        raise Exception('Config file does not exit: {}'.format(cfg_file))
    
    config = configparser.ConfigParser()
    config.read(cfg_file)
    return config['DEFAULT']
    

def extract_users(feat_data, time):
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
            timediff = dt.datetime.now() - co_dt
            users.append(LMUser(userid=udm.groups()[0],
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
                                update_time=time\
                                    
                                ))

    # process the output and extract usernames and license checkout info
    return users


def extract_feature(feat_data, time, lmversion):
    feature_data = []
    for fdata in feat_data.split('\r\n'):
        if fdata:
            feature_data.append(fdata)

    feature_license_info = feature_data[0]
    flmm = re.match(r'(.+?)_(.+?)?F:  ' \
                    r'\(Total of (\d+?) license[s]* issued;  ' \
                    r'Total of (\d+?) license[s]* in use\)',
                    feature_license_info)
    if flmm:
        revit_version = flmm.groups()[1]
        if revit_version:
            feature_name = flmm.groups()[0]
            issued = flmm.groups()[2]
            used = flmm.groups()[3]

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
                    users = extract_users(feature_data[4:], time=time)

            return LMFeature(feature_name=feature_name,
                             feature_code=revit_version,
                             feature_version=feature_version or '--',
                             vendor=vendor or '--',
                             license_type=license_type or '--',
                             issued=issued or '--',
                             used=used or '--',
                             users=users)


def write_users(feature, dest_path):
    user_file = op.join(
            dest_path,
            USERS_FILENAME_FORMAT.format(
                feat_name=feature.feature_name,
                feat_code=feature.feature_code,
                datetime=dt.datetime.now().strftime(FILENAME_DATETIME_FORMAT)
                ))
    if not op.exists(user_file):
        with open(user_file, 'w') as csvfile:
            csvwriter = \
                csv.writer(csvfile,
                           quoting=csv.QUOTE_MINIMAL, lineterminator='\n')        
            csvwriter.writerow(['feature_name', 'userid', 'host', 'display',
                                'feature_version',
                                'server_host', 'server_port', 'license_handle',
                                'checkout_datetime', 'update_time'])

    with open(user_file, 'a') as csvfile:
        csvwriter = \
            csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')        
        for u in feature.users:
            csvwriter.writerow([feature.feature_name,
                                u.userid, u.host, u.display, u.feature_version,
                                u.server_host, u.server_port, u.license_handle,
                                u.checkout_datetime, u.update_time])


def write_features(features, dest_path):
    write_users_log = get_config()['logusers'].lower() == 'true'
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
            csvwriter.writerow(['stamp', 'feature_name', 'feature_code',
                                'feature_version', 'vendor', 'license_type',
                                'issued', 'used', 'users'])
    with open(feat_file, 'a') as csvfile:
        csvwriter = \
            csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')        
        for f in features:
            csvwriter.writerow([dt.datetime.now().strftime(DATETIME_FORMAT),
                                f.feature_name, f.feature_code,
                                f.feature_version, f.vendor, f.license_type,
                                f.issued, f.used, len(f.users)])
            if write_users_log:
                write_users(f, dest_path)


def determine_lmutil_version():
    result = subprocess.run('lmutil', stdout=subprocess.PIPE)
    help_report = result.stdout.decode('utf-8')
    verm = re.match(r'.+\(c\) 1989-(\d\d\d\d) .+', help_report)
    if verm:
        return verm.groups()[0]


def get_lmstatus():
    # grab lmutil license manager status output
    lic_file = 'C:/Autodesk/Network License Manager/2018 License File.lic'
    if op.exists(lic_file):
        command = 'lmutil lmstat -c "{}" -a -i'.format(lic_file)
    else:
        command = 'lmutil lmstat -a -i'
    result  = subprocess.run(command, stdout=subprocess.PIPE)
    return result.stdout.decode('utf-8')


# MAIN() ======================================================================

lmversion = determine_lmutil_version()

status_report = get_lmstatus()
if status_report:
    features = []
    # extract data chunks
    features_data = status_report.split('Users of ')
    server_data = features_data[0]
    features_data.pop(0)
    features_data[-1] = features_data[-1].split('NOTE:')[0]

    # process the output and extract license usage info (issued vs used)
    for feat_data in features_data:
        lmf = extract_feature(feat_data,
                              dt.datetime.now().strftime(DATETIME_FORMAT),
                              lmversion)
        if lmf:
            features.append(lmf)

    # write the license usage info
    write_features(features, get_config()['dbpath'])