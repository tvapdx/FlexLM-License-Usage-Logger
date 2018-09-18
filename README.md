# FlexLM License Usage Logger

python utility script to parse the `lmutil lmstat` results on a FlexLM server and log the license usage for each product and active users. Clone this repo on license server machine and create a cron job to call this method at intervals.

## Config

The script expects minimum configuration below, at config file:
`%PROGRAMDATA%/FlexLMLicenseUsageLoggerConfig.ini`

``` ini
[DEFAULT]
logusers = True or False
logpath = \\shareddrive\flexlm\Logs
usedb = True or False
dbms = postgres
dbhost = 192.168.000.000
dbport = 5432
dbuser = username
dbpass = password
dbname = database name
# see below for table creation SQL
# revise the table names as necessary
dbflexfeaturestable = flexlmfeatures or anything else
dbflexuserstable = flexlmusers or anything else
```

## Logging to a Database

Logs could be pushed to a database server. This script uses the `records` python module to talk to the database server and builds a connection string based on the configurations provided in the config file.

### Feature logs

Feature logs are written to the database and table specified in the config file.

##### Table Schema

``` sql
-- modify table name as needed
CREATE TABLE flexlmfeatures (
    dtime timestamp,
    fcode varchar(255),
    fver varchar(255),
    vendor varchar(255),
    lictype varchar(255),
    issued integer,
    used integer,
    ausers integer
);
```

Example Entry:

``` csv
2018-09-05 16:32:15,67647324PRM_2018_0F,1.000,--,--,125,12,11
```

### User logs

User logs are written to the database and table specified in the config file.

##### Table Schema

``` sql
-- modify table name as needed
CREATE TABLE flexlmusers (
    fcode varchar(255),
    userid varchar(255),
    host varchar(255),
    display varchar(255),
    fver varchar(255),
    shost varchar(255),
    sport integer,
    lichandle integer,
    ctime timestamp,
    utime timestamp
);
```

Example Entry:

``` csv
67647324PRM_2018_0F,ehsan.irannejad,ein1,ein1,1.0,flexlmserver,8888,121,2018-09-05 10:41:00,2018-09-05 16:32:15
```
## Logging to a Directory

Log could be saved as CSV files. By default one csv file will be created for each day of logging. In current implementation, there are two types of logs for each day:

### Feature logs

There is a single feature log file for each day. Feature log files are good for tracking the overall license usage.

Filename format: `YYYY-MM-DD features.csv`
    
Example: e.g. `2018-09-05 features.csv`

##### Schema

``` csv
stamp,feature_code,feature_version,vendor,license_type,issued,used,users
```

Example Entry:

``` csv
2018-09-05 16:32:15,67647324PRM_2018_0F,1.000,--,--,125,12,12
```


### User logs

There is one user log file per each license feature. User logs are good for tracking license usage by specific users.

Filename format: `YYYY-MM-DD <feature_code> users.csv`

Example: e.g. `2018-09-05 67647324PRM_2018_0F users.csv`

##### Schema

``` csv
feature_code,userid,host,display,feature_version,server_host,server_port,license_handle,checkout_datetime,update_time
```

Example Entry:

``` csv
67647324PRM_2018_0F,ehsan.irannejad,ein1,ein1,1.0,flexlmserver,8888,121,2018-09-05 10:41:00,2018-09-05 16:32:15
```

## Feature Code Lookups

A set of CSV files are inside `Feature Codes` directory. They have been gathered from [ADN Feature Codes](https://knowledge.autodesk.com/customer-service/network-license-administration/managing-network-licenses/interpreting-your-license-file/feature-codes)

## Dependencies

- FlexLM Utility: `lmutil.exe` is shipped inside the FlexLM installation directory. Make sure to add the path to the `%PATH%` env var. `lmutil` can be used from local machines that see the license server as well. You can download and install [Autodesk Network License Manager](https://knowledge.autodesk.com/search-result/caas/downloads/content/autodesk-network-license-manager-for-windows.html) on your machine to use the `lmutil` utility.
- python 3.7: Install python on server machine.

### Installing python modules

This script uses `pipenv` for package management. If you don't have pipenv installed, simply:

``` bash
# use pip3 if you have python 2 and 3 installed
pip install pipenv
```

Then `cd` to the repo directory and:

``` bash
# pipenv will install all python dependencies
pipenv install
```