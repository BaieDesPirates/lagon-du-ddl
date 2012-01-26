# -*- coding: utf-8 -*-

#########################################################################
## This scaffolding model makes your app work on Google App Engine too
## File is released under public domain and you can use without limitations
#########################################################################
import re
from applications.ddlagoon import pathutils

if False:
    from gluon.dal import Field, DAL
    from gluon.contrib.pysimplesoap.server import request
    from gluon.contrib.pysimplesoap.client import response

if not request.env.web2py_runtime_gae:     
    ## if NOT running on Google App Engine use SQLite or other DB
    #db = DAL('sqlite://storage.sqlite')
    if request.env.http_host == '127.0.0.1:8000' or request.env.http_host == '127.0.0.1:8080':
        db = DAL('sqlite://storage.sqlite')
    else:
        db = DAL('mysql://ddlagoon:YWQ20u77@ddlagoon.mysql.fluxflex.com/ddlagoon', migrate_enabled=False)
else:
    ## connect to Google BigTable (optional 'google:datastore://namespace')
    db = DAL('google:datastore') 
    ## store sessions and tickets there
    session.connect(request, response, db = db) 
    ## or store session in Memcache, Redis, etc.
    ## from gluon.contrib.memdb import MEMDB
    ## from google.appengine.api.memcache import Client
    ## session.connect(request, response, db = MEMDB(Client()))

## by default give a view/generic.extension to all actions from localhost
## none otherwise. a pattern can be 'controller/function.extension'
response.generic_patterns = ['*'] if request.is_local else []

#########################################################################
## Here is sample code if you need for
## - email capabilities
## - authentication (registration, login, logout, ... )
## - authorization (role based authorization)
## - services (xml, csv, json, xmlrpc, jsonrpc, amf, rss)
## - old style crud actions
## (more options discussed in gluon/tools.py)
#########################################################################

from gluon.tools import Auth, Crud, Service, PluginManager, prettydate
auth = Auth(db, hmac_key=Auth.get_or_create_key())
crud, service, plugins = Crud(db), Service(), PluginManager()

def generateNickname():
    import random
    return 'DDLagoonFan%d' % random.randint(1,1e10)

def generateUploaderKey():
    #from Crypto.Random import random
    import random
    from datetime import datetime
    from hashlib import sha256, md5
    return md5(sha256(str(random.getrandbits(256))).digest()+str(datetime.now().isoformat())).hexdigest()

def getCurrentTime():
    from datetime import datetime
    return datetime.now()

## create all tables needed by auth if not custom tables
auth.settings.extra_fields['auth_user']= [
    Field('nickname', 'string', length=128, unique=True, default=generateNickname()),
    Field('allow_porn', 'boolean', writable=False, readable=False, default=False),
    Field('uploader_key', 'string', writable=False, default=generateUploaderKey()),
    Field('is_uploader', 'boolean', writable=False, readable=False, default=False)
    #Field('birthday', 'date', default=date.today()),
    #Field('of_age', 'boolean', compute=lambda r: ((date.today()-r.birthday) > timedelta(hours=18)))
]

auth.settings.register_onvalidation = generateNickname
auth.settings.create_user_groups = False
auth.define_tables()
db.auth_user.email.writable = False
db.auth_user.email.required = False
db.auth_user.first_name.writable = False
db.auth_user.last_name.writable = False
db.auth_user.last_name.required = False
db.auth_user.email.readable = False
db.auth_user.first_name.readable = False
db.auth_user.last_name.readable = False

# The categories
db.define_table('category',
    Field('category_title', notnull=True),
    Field('category_description', 'text'),
    Field('category_parent', 'reference category', default=None),
    format='%(category_title)s (%(category_parent)s) (%(id)s)'
)

# The DDLz
db.define_table('ddl',
    Field('filename', required=True, notnull=True),
    Field('author'),
    Field('description'),
    Field('web_description', 'text'),
    Field('size', 'integer', required=True, notnull=True),
    Field('hash', required=True, notnull=True),
    Field('parts', 'integer', required=True, notnull=True),
    Field('service', required=True, notnull=True),
    Field('links', "text", required=True, notnull=True),
    Field('version', 'double', required=True, notnull=True),
    Field('date_created', 'datetime', required=False),
    Field('uploader', 'reference auth_user', required=True, notnull=True),
    Field('date_added', 'datetime', default=getCurrentTime()),
    Field('category', 'reference category'),
    Field('last_time_downloaded', 'datetime'),
    Field('times_downloaded', 'integer', default=0),
    Field('times_error', 'integer', default=0),
    Field('karma_pos', 'integer', default=0),
    Field('karma_neg', 'integer', default=0),
    Field('reported', 'integer', default=0),
    Field('size_readable', compute=lambda r: pathutils.formatbytes(r['size'])),
    Field('filename_url', compute=lambda r: re.sub('[^A-Za-z0-9_ .-]+', '', r['filename']).replace(" ","_"))
)

# Record the downloads
db.define_table('ddl_downloaded',
    Field('ddl', 'reference ddl', required=True, notnull=True),
    Field('downloader', 'reference auth_user', required=True, notnull=True),
    Field('download_time', 'datetime', required=True, notnull=True)
)

db.define_table('downloads_log',
    Field('ddl', 'reference ddl', required=True, notnull=True),
    Field('downloader_ip', required=True, notnull=True),
    Field('download_time', 'datetime', required=True, notnull=True),
    Field('message')
)

## configure email
mail=auth.settings.mailer
mail.settings.server = 'logging' or 'smtp.gmail.com:587'
mail.settings.sender = 'you@gmail.com'
mail.settings.login = 'username:password'

## configure auth policy
auth.settings.registration_requires_verification = False
auth.settings.registration_requires_approval = False
auth.settings.reset_password_requires_verification = True

## if you need to use OpenID, Facebook, MySpace, Twitter, Linkedin, etc.
## register with janrain.com, write your domain:api_key in private/janrain.key
from gluon.contrib.login_methods.rpx_account import use_janrain
use_janrain(auth,filename='private/janrain.key', )

#########################################################################
## Define your tables below (or better in another model file) for example
##
## >>> db.define_table('mytable',Field('myfield','string'))
##
## Fields can be 'string','text','password','integer','double','boolean'
##       'date','time','datetime','blob','upload', 'reference TABLENAME'
## There is an implicit 'id integer autoincrement' field
## Consult manual for more options, validators, etc.
##
## More API examples for controllers:
##
## >>> db.mytable.insert(myfield='value')
## >>> rows=db(db.mytable.myfield=='value').select(db.mytable.ALL)
## >>> for row in rows: print row.id, row.myfield
#########################################################################
