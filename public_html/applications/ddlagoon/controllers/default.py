# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## This is a samples controller
## - index is the default action of any application
## - user is required for authentication and authorization
## - download is for downloading files uploaded in the db (does streaming)
## - call exposes all registered services (none by default)
#########################################################################
from datetime import datetime
#from applications.ddlagoon import pathutils

__version__ = 1.9

from Crypto.PublicKey import RSA
#from Crypto.Random import random
import random
import base64, hashlib
import gluon.contrib.simplejson as json
import tempfile
from time import mktime

def sha512(n):
    return hashlib.sha512(str(n)).digest()
def sha256(n):
    return hashlib.sha256(str(n)).digest()
def compute(n):
    return 61*long(n)**3-54*long(n)**2+8942*long(n)*3
def chunks(s, n):
    """Produce `n`-character chunks from `s`."""
    for start in range(0, len(s), n):
        yield s[start:start+n]

if False:
    from gluon.contrib import *
    from re import T
    from applications.ddlagoon.models.db import db, service, auth
    from gluon.contrib.pysimplesoap.server import request
    from gluon.html import FORM

def pluralize(number, text):
    output = str(number) + " " + text
    if number>1:
        output += "s"
    return output

def getTimeDelta(weeks, days, hours, minutes, seconds):
    output=""
    if weeks>0:
        return pluralize(weeks, "week")
    elif days>0:
        return pluralize(days, "day")
    elif hours>0:
        return pluralize(hours, "hour")
    elif minutes>0:
        return pluralize(minutes, "minute")
    elif seconds>0:
        return pluralize(seconds, "second")


def search():
    return ""

def like_query(term, field):
    """Receives term and field to query, then returns the query to be performed
       """
    queryStart = term.decode('utf-8')
    queryEnd = queryStart+"\xEF\xBF\xBD".decode('utf-8')
    query =((field>=queryStart) & (field<=queryEnd))
    return query

def index():
    """
    example action using the internationalization operator T and flash
    rendered by views/default/index.html or views/generic.html
    """
    form=FORM(T('Search:'),
              INPUT( _name='filesearch', requires=IS_LENGTH(minsize=3)),
              INPUT(_type='submit'))

    filesearch=None
    if form.accepts(request,session):
        filesearch=request.vars['filesearch']
        if not request.env.web2py_runtime_gae:
            rows= db(db.ddl.filename.contains(filesearch.replace("%", "_").replace(" ","%"))).select(orderby=db.ddl.filename, limitby=(0,100))
        else:
#            query = like_query(filesearch.replace(" ","%"), db.ddl.filename)
#            rows = db(query).select()
            from google.appengine.ext.db import GqlQuery
            query = filesearch
            queryEnd = query+"\xEF\xBF\xBD".decode('utf-8')
            rows = GqlQuery("SELECT * FROM ddl WHERE filename>=:1 AND filename<=:2 ORDER BY filename DESC", query, queryEnd)
    else:
        rows= db(db.ddl.id>0).select(orderby=~db.ddl.date_added, limitby=(0,20))
    ddlz=[]

    for row in rows:
        if not request.env.web2py_runtime_gae:
            date_added=row['date_added']
        else:
            date_added=row.date_added
        difference = datetime.now()-date_added
        weeks, days = divmod(difference.days, 7)
        minutes, seconds = divmod(difference.seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if not request.env.web2py_runtime_gae:
            row['timedelta']= getTimeDelta(weeks, days, hours, minutes, seconds)
            row['nickname']= row['uploader']['nickname']
        else:
            row.timedelta= getTimeDelta(weeks, days, hours, minutes, seconds)
            if type(row.uploader) is long:
                row.nickname = row.uploader
                row.id = 0
            else:
                row.nickname= row.uploader.nickname
                
        ddlz.append(row)

    loggedIn = True if auth.is_logged_in() else False

    return dict(message=T('Hello World'),ddlz=ddlz, form=form, filesearch=filesearch, loggedIn=loggedIn)

def user():
    """
    exposes:
    http://..../[app]/default/user/login
    http://..../[app]/default/user/logout
    http://..../[app]/default/user/register
    http://..../[app]/default/user/profile
    http://..../[app]/default/user/retrieve_password
    http://..../[app]/default/user/change_password
    use @auth.requires_login()
        @auth.requires_membership('group name')
        @auth.requires_permission('read','table name',record_id)
    to decorate functions that need access control
    """
    return dict(form=auth())

@auth.requires_login()
def profile():
    return dict(nickname=auth.user.nickname,
                uploader_key=auth.user.uploader_key,
                is_uploader=auth.user.is_uploader)

def download():
    """
    allows downloading of uploaded files
    http://..../[app]/default/download/[filename]
    """
    return response.download(request,db)

@auth.requires_login()
def uploadDDL():
    return service()

def call():
    """
    exposes services. for example:
    http://..../[app]/default/call/jsonrpc
    decorate with @services.jsonrpc the functions to expose
    supports xml, json, xmlrpc, jsonrpc, amfrpc, rss, csv
    """
    return service()

@service.xmlrpc
@service.json
@service.xml
def downloaded(encryptedText):
    # Requires:
    # id
    # filename
    # uploader
    # returnCode
    # message
    returnCode= -1
    message= "Unknown Error"
    try:
        decryptedMsg= decryptFromClient(encryptedText)
    except:
        returnCode=-1
        message= "Error decrypting the message"
    else:
        try:
            dataFromClient = json.loads(decryptedMsg)
        except :
            returnCode= -1
            message= "Error reading the message"
        else:
            if 'id' in dataFromClient:
                now= datetime.now()
                # update ddl
                ddl= db(db.ddl.id==dataFromClient['id']).select().first()
                if 'returnCode' in dataFromClient and dataFromClient['returnCode']==-1:
                    ddl.times_error      += 1
                else:
                    ddl.times_downloaded += 1
                ddl.last_time_downloaded = now
                ddl.update_record()
                # update log
                db.downloads_log.insert(
                    ddl=dataFromClient['id'],
                    downloader_ip= request.env["remote_addr"],
                    download_time= now,
                    message=dataFromClient['message']
                )
                returnCode= 0
                message="Download done!"
            else:
                returnCode= -1
                message= "Which file did you download?"
    dataToSend = {
        'returnCode' : returnCode,
        'message' : message
    }
    return json.dumps(dataToSend, sort_keys=True, indent=4)
@service.xmlrpc
@service.json
@service.xml
def receiveDDL(encryptedText):
    returnCode=-1
    message="Unknown Error"
    try:
        decryptedMsg= decryptFromClient(encryptedText)
    except:
        returnCode=-1
        message= "Error decrypting the DDL"
    else:
        try:
            dataFromClient = json.loads(decryptedMsg)
        except :
            returnCode= -1
            message="Error reading the DDL"
        else:
            # prepare a DDL from the received information
            if 'uploaderID' in dataFromClient:
                uploader= db(db.auth_user.id==dataFromClient['uploaderID']).select().first()
            else:
                uploader= db(db.auth_user.nickname==dataFromClient['nickname']).select().first()
            ddl = dataFromClient['ddl']
            # remove previous DDL, if present
            #db((db.ddl.filename==ddl['filename']) & (db.ddl.uploader==uploader.id)).delete()
            db.ddl.update_or_insert(
                (db.ddl.filename==ddl['filename']) & (db.ddl.uploader==uploader.id)
                ,  author=ddl['author']
                , uploader=uploader.id
                , filename=ddl['filename']
                , description=ddl['description'],
                size=ddl['size'],
                hash=ddl['hash'],
                parts=ddl['parts'],
                service=ddl['service'],
                links="|".join(ddl['links']),
                version=ddl['version'],
                date_added=datetime.now()
                #, date_created=datetime.fromtimestamp(ddl['time'])
            )
            returnCode= 0
            message="Upload done!"
    dataToSend = {
        'returnCode' : returnCode,
        'message' : message
    }
    return json.dumps(dataToSend, sort_keys=True, indent=4)

@service.json
@service.xmlrpc
@service.xml
def concat(a,b):
    return dict(test=a+b)

def loginTest(nickname, uploaderKey):
    returnCode = -1
    message = ""
    uploaderID = -1
    try:
        record = db(db.auth_user.nickname==nickname).select().first()
    except:
        pass
    else:
        if not record:
            returnCode= -1
            message= "Who is %s?" % nickname
        else:
            if not record.uploader_key==uploaderKey:
                returnCode= -1
                message= "Wrong API Key"
            else:
                if record.is_uploader:
                    # login the user
                    #session.nickname= nickname
                    uploaderID = record.id
                    returnCode=0
                else:
                    returnCode= -1
                    message= "You are not allowed to upload"
    return returnCode, message, uploaderID


def decryptFromClient(encryptedMsg):
    decryptedMsg = ""
    private_json = {
        "d": 23787079891404684333685400978249298094378954863672776929346845102263722750088918762338764266712467553502811192479791825128333774826784684125489823193368527161074577530140077392439136510635896140296132025922882984837588521257841050129145633510814630843053674301016823808612405445927946023993959147765325630609,
        "e": 65537,
        "n": 113857278326248086267655574343523535583648376051747208707172377115619164320229146138430878888952306898474564499090572366596232150220784972504544737264372878940265396864770701575284749329394957815581364039447123399430603091303935702146927576939090729428557897918935408150236788311903915427199939052963176280397,
        "p": 9580774579539128121039431812737453710839471771236942870475012323041145011884745445780348665996631786895791139388698030648995797187661607074610865997962403,
        "q": 11883932492202009053507786643172605523535663521769572031030078443728388902717320133755150294842235771246601522313496536316374989301635407931585896758667599,
        "u": 1517576679209673870508661373022611765046783829884979500337395070156130858916802958093981514472423096659658057726899513257360280724233068450029128365828499
    }
    private_key = RSA.construct((long(private_json['n']), long(private_json['e']),
                             long(private_json['d']), long(private_json['p']),
                             long(private_json['q']), long(private_json['u'])))
    try:
        for p in encryptedMsg.split("@"):
            decryptedMsg += private_key.decrypt(base64.b16decode(p))
    except:
        pass
    
    return decryptedMsg

def encryptForClient(n, e, clearMsg):
    client_pub_key = RSA.construct((long(n), long(e)))
    encryptedMsg = list()
    randomK = long(random.getrandbits(random.randint(128, 256)))
    for part in chunks(clearMsg,127):
        encryptedData = client_pub_key.encrypt(part, randomK)
        coded = base64.b16encode(encryptedData[0])
        encryptedMsg.append(coded)
    data = "@".join(encryptedMsg)
    return data

@service.json
@service.xmlrpc
@service.xml
def checkLogin(encryptedMsg):
    # decrypt the message with the private key
    returnCode = -1
    message = ''
    computedNb = 0
    uploaderID = -1
    decryptedMsg = decryptFromClient(encryptedMsg)
    dataFromClient = ()
    if not len(decryptedMsg)>0:
        returnCode = -1
        message = 'Server Decrypt Error'
    else:
        # try to load into a json
        try:
            dataFromClient = json.loads(decryptedMsg)
        except:
            returnCode = -1
            message = 'Server Load Error'
        else:
            toFind = ['nickname','version','uploaderKey','n','e','randomNb']
            error = False
            for e in toFind:
                if e not in dataFromClient:
                    error = True
                    returnCode = -1
                    message = 'Server Elements Missing'
            if not error:
                # check if the client is using the last version
                if float(dataFromClient['version'])>=__version__:
                    returnCode, message, uploaderID = loginTest(dataFromClient['nickname'],dataFromClient['uploaderKey'])
                    computedNb = base64.b16encode(sha512(sha256(str(compute(dataFromClient['randomNb'])))))
                else:
                    returnCode=1
                    message="A new version of Bobpic is available.\nYou need to upgrade."

    # prepare a json
    dataToSend = {
        'returnCode' : returnCode,
        'message' : message,
        'computedNb' : computedNb,
        'uploaderID' : uploaderID
    }
    # encrypt the json with the dynamic public key of the client
    try:
        dataToSendStr = str(json.dumps(dataToSend, sort_keys=True, indent=4))
        data= encryptForClient(dataFromClient['n'], dataFromClient['e'], dataToSendStr)
    except :
        dataToSend = {
            'returnCode' : -2,
            'message' : message
        }
        return json.dumps(dataToSend, sort_keys=True, indent=4)
    else:
        return data

#def checkLogin(username, key):
#    users = db.auth_user
#    q = users.nickname==username
#    s = db(q)
#    if s.select():
#        return dict(test=username+key)
#    else:
#        return "get out"

@auth.requires_signature()
def data():
    """
    http://..../[app]/default/data/tables
    http://..../[app]/default/data/create/[table]
    http://..../[app]/default/data/read/[table]/[id]
    http://..../[app]/default/data/update/[table]/[id]
    http://..../[app]/default/data/delete/[table]/[id]
    http://..../[app]/default/data/select/[table]
    http://..../[app]/default/data/search/[table]
    but URLs bust be signed, i.e. linked with
      A('table',_href=URL('data/tables',user_signature=True))
    or with the signed load operator
      LOAD('default','data.load',args='tables',ajax=True,user_signature=True)
    """
    return dict(form=crud())


def get():
    return service()

@service.xml
def ddl(id="", filename=""):
    # find the record
    ddl= db((db.ddl.filename_url==filename) & (db.ddl.id==id)).select().first()
    if not ddl:
        return "404 - File not found."
    else:
        # prepare the file
        ddlJ = {
            'id':ddl.id,
            'author':ddl.author,
            'filename':ddl.filename,
            'description':ddl.description,
            'uploader':ddl.uploader,
            'size':ddl.size,
            'hash':ddl.hash,
            'parts':ddl.parts,
            'service':ddl.service,
            'links':ddl.links.split("|"),
            'version':ddl.version,
            'time':int(mktime(ddl.date_added.timetuple()))
        }
        ddlJson = json.dumps(ddlJ, sort_keys=True, indent=4)
        public_ddl = {
            "e": 65537,
            "n": 138699374543223257537557103176001704226735255147448649583225017098287197630734176291676474096655313606555548753275002732095146725547697816211326459323755204828036245647843790985208692060549009977103102474302073609652750671753426409739287485014860128030833183117757223967930924686377060843991855851119927153483
        }
        encryptedMsg = encryptForClient(public_ddl['n'],public_ddl['e'],ddlJson)
        #response.headers['Content-Type'] = 'application/ddl'
        #response.headers['Content-Disposition'] = 'attachment; filename=test.ddl'
        #return response.stream(ddlFile, request=request)
#        request.args[0] = ddlFile.name
#        return response.download(request, ddlFile)
        response.headers['Content-Type'] = "application/octet-stream"
        response.headers['Content-Disposition'] = 'attachment; filename=%s.ddl' % ddl.filename
        return encryptedMsg

def howto():
    win32= "http://www.mediafire.com/?dd8w1my51qwrs70"
    win64= "http://www.mediafire.com/?gtvi14dx713e849"
    amd64= "http://www.mediafire.com/?p4mzpscyd93uur8"
    loggedIn = True if auth.is_logged_in() else False
    return dict(win32=win32, win64=win64, amd64=amd64, version=__version__, loggedIn=loggedIn)

@auth.requires_login()
def how_to_upload():
    allowed= False
    tuto=dict()
    if auth.user.is_uploader:
        tuto = dict()
        tuto['start']= T("Start DDLagoon Uploader.")
        tuto['login']= T("Login with your username and password.")
        tuto['go_to_profile_pre']= T('Go to your')
        tuto['profile']= T('profile')
        tuto['go_to_profile_suf']= T('to get your API key.')
        tuto['go_to_settings']= T('Go to the settings tab.')
        allowed=True
    loggedIn = True if auth.is_logged_in() else False
    return dict(tuto=tuto, allowed=allowed, loggedIn=loggedIn)

def help():
    issuesUrl= "https://bitbucket.org/DDLagoon/ddlagoon/issues"
    wikiUrl=   "https://bitbucket.org/DDLagoon/ddlagoon/wiki"
    loggedIn = True if auth.is_logged_in() else False
    return dict(issuesUrl=issuesUrl, wikiUrl=wikiUrl, loggedIn=loggedIn)