#!/usr/bin/env python

import argparse
import agavepy.agave as a
import logging
import time

from os import makedirs, listdir, environ
from os.path import abspath, exists, expanduser, isfile, isdir, join, basename, dirname, getmtime
from json import load, loads, dumps
from requests import get, post, put
from datetime import datetime

# global variables
global logger
global HERE

HERE = dirname(abspath(__file__))

cache = '~/.agave/current'
agave_prefix = 'agave://'
url_prefix = 'http'

# file types; set here to avoid repeated string use
agave = 'agave'
url = 'url'
local = 'local'


def get_logger(name):
    """
    Returns a properly configured logger.
         name (str) should be the module name.
    """
    FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
    DATEFORMAT = "%Y-%m-%dT%H:%M:%SZ"
    logging.Formatter.converter = time.gmtime

    logger = logging.getLogger(name)
    level = environ.get('LOGLEVEL', 'INFO')
    logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(FORMAT, datefmt=DATEFORMAT))
    logger.addHandler(handler)
    logger.debug(
        "Returning a logger set to level: {} for module: {}".format(
            level, name))
    return logger


def credentials():
    '''
    Load credentials for testing session

    Order: user credential store, test file, env
    '''
    credentials = {}
    # credential store
    ag_cred_store = expanduser('~/.agave/current')
    if exists(ag_cred_store):
        logger.debug('Reading ~/.agave/current')
        tempcred = load(open(ag_cred_store, 'r'))
        credentials['apiserver'] = tempcred.get('baseurl', None)
        credentials['username'] = tempcred.get('username', None)
        credentials['password'] = tempcred.get('password', None)
        credentials['apikey'] = tempcred.get('apikey', None)
        credentials['apisecret'] = tempcred.get('apisecret', None)
        credentials['token'] = tempcred.get('access_token', None)
        credentials['refresh_token'] = tempcred.get('refresh_token', None)
        credentials['verify_certs'] = tempcred.get('verify', None)
        credentials['client_name'] = tempcred.get('client_name', None)
        credentials['tenantid'] = tempcred.get('tenantid', None)

    # test file
    credentials_file = environ.get('creds', 'test_credentials.json')
    if exists(credentials_file):
        logger.debug(("Reading credentials file: {}".format(
            credentials_file)))
        credentials = load(open(
            join(HERE, credentials_file), 'r'))
    # environment
    for env in ('apikey', 'apisecret', 'username', 'password',
                'apiserver', 'verify_certs', 'refresh_token',
                'token', 'client_name'):
        varname = '_AGAVE_' + env.upper()
        if environ.get(varname, None) is not None:
            credentials[env] = environ.get(varname)
            logger.debug("Loaded {} from environment".format(env))

    return credentials


def agave(credentials):
    '''Returns an authenticated Agave client'''
    aga = a.Agave(username=credentials.get('username'),
                  password=credentials.get('password'),
                  api_server=credentials.get('apiserver'),
                  api_key=credentials.get('apikey'),
                  api_secret=credentials.get('apisecret'),
                  token=credentials.get('token'),
                  refresh_token=credentials.get('refresh_token'),
                  verify=credentials.get('verify_certs', True))
    return aga

# basic helper functions
def get_path_type(path):
    '''Determines if path is of local, agave, or url types.'''
    path_type=''
    if path[:len(agave_prefix)] == agave_prefix:
        path_type = agave
    elif path[:len(url_prefix)] == url_prefix:
        path_type = url
    else:
        assert isfile(path) or isdir(path), 'Invalid local path: {}'.format(path)
        path_type = local
    return path_type

def agave_path_builder(base, path, recursive=False):
    '''Generates a ready-to-use agave url with the cached base and user-provided path'''
    assert get_path_type(path) == agave, 'Path is type {}, must be type agave'.format(get_path_type(path))
    # strip agave prefix
    path = path[len(agave_prefix): ]
    # return full path
    path = '{}/files/v2/media/system/{}'.format(base, path)
    return path

def agave_path_setlisting(path, base, listings=True):
    '''Sets path prefix to /files/v2/listings/ when listings=True (default) and /files/v2/media/ when listings=False'''
    if listings:
        path = path.replace('{}/files/v2/media'.format(base), '{}/files/v2/listings'.format(base))
    else:
        path = path.replace('{}/files/v2/listings'.format(base), '{}/files/v2/media'.format(base))
    return path

def sametype(local_filepath, agave_description):
    '''Checks if local and agave files are both directories or files. Returns boolean.'''
    return (isfile(local_filepath) and agave_description['type'] == 'file') or (isdir(local_filepath) and agave_description['type'] == 'dir')

def update_import_destfiles_dict(new_dest, headers, dest_type=url, url_base=None):
    '''Helper function to update dictionary of destination file information'''
    # get list url if agave
    if dest_type == agave:
        assert url_base is not None, 'Must pass baseurl when using agave url'
        new_dest = agave_path_setlisting(new_dest, url_base)
    fdict = { i['name']: {'lastModified':i['lastModified'], 'type':i['type'], 'path':i['path']}
               for i in list_agave_dir_files(new_dest, headers) }
    return fdict
# end basic helper functions

# request wrappers
def list_agave_dir_files(url, headers):
    '''Performs files-list on remote agave directory and returns list of file JSON descriptions'''
    r = get(url, headers=headers)
    assert r.status_code == 200, 'Unable to list files at {}; status code {}'.format(url, r.status_code)
    l = loads(r.content)
    assert l.get('result') is not None, 'Unable to read file info from key "result" in JSON \n{}'.format(dumps(l, indent=2))
    return l['result']

def files_download(url, headers, path='.', name=None):
    '''Downloads and saves file at url. Defaults to saving in the current directory without changing name, but these options are available.'''
    r = get(url, headers=headers)
    assert r.status_code == 200, 'files-download failed with code {}'.format(r.status_code)
    # set up path
    if name is None:
        name = basename(url)
    path += '/'+name
    with open(expanduser(path), 'wb') as f:
        f.write(r.content)
    return

# touch a local, empty-length file instead of downloading it
def files_touch(url, path='.', name=None):
    if name is None:
        name = basename(url)
    path += '/' + name
    with open(expanduser(path), 'wb') as f:
        f.write("")
    return

def files_upload(localfile, url, headers, new_name=None):
    '''Uploads file at localfile path to url. Name at location can be specified with new_name; defaults to current name.'''
    assert isfile(localfile), 'Local file {} does not exists or is directory'.format(localfile)
    # set new_name to current name if not given
    if new_name is None:
        new_name = basename(localfile)
    # format file data and run command
    files = {'fileToUpload': (new_name, open(expanduser(localfile), 'rb'))}
    r = post(url, headers=headers, files=files)
    assert r.status_code == 202, 'Command status code is {}, not 202'.format(r.status_code)
    return

def files_mkdir(dirname, url, headers):
    '''Makes a directory at the agave url path.'''
    data = {'action': 'mkdir', 'path':dirname}
    r = put(url+'/', data=data, headers=headers)
    assert r.status_code == 201
    return

def files_import(source, destination, headers, new_name=None):
    '''Import file from remote source to remote destination. New name defaults to current name.'''
    if new_name is None:
        new_name = basename(source)
    data = {'urlToIngest': source, 'fileName': new_name}
    r = post(destination, headers=headers, data=data)
    assert r.status_code == 202, 'Command status code is {}, not 202'.format(r.status_code)
    return
# end request wrappers

# modification time helper functions
def get_localfile_modtime(localfile):
    '''Given path to file, returns datetime of last modification on that file.'''
    assert isfile(localfile) or isdir(localfile), 'Local file {} does not exist'.format(localfile)
    return datetime.fromtimestamp(getmtime(localfile))

def get_agavefile_size(agavedescription):
    '''Given Agave file JSON file description, returns size in bytes'''
    assert 'length' in agavedescription, 'size key not in Agave description keys: {}'.format(agavedescription.keys())
    # strip '.000-0X:00' off modtime (unknown meaning)
    filesize = agavedescription['length']
    return filesize

def get_agavefile_modtime(agavedescription):
    '''Given Agave file JSON file description (only lastModified key required), returns datetime of last modification on that file.'''
    assert 'lastModified' in agavedescription, 'lastModified key not in Agave description keys: {}'.format(agavedescription.keys())
    # strip '.000-0X:00' off modtime (unknown meaning)
    modstring = agavedescription['lastModified'][:-10] 
    strptime_format = '%Y-%m-%dT%H:%M:%S'
    return datetime.strptime(modstring, strptime_format)

def newer_agavefile(localfile, agavedescription):
    '''Given local filepath and Agave file JSON description (only lastModified key required), return TRUE if Agave file is more recently modified.'''
    assert isfile(localfile) or isdir(localfile), 'Local file {} does not exist'.format(localfile)
    assert 'lastModified' in agavedescription, 'lastModified key not in Agave description keys: {}'.format(agavedescription.keys())
    local_modtime = get_localfile_modtime(localfile)
    agave_modtime = get_agavefile_modtime(agavedescription)
    return (agave_modtime > local_modtime)

def newer_importfile(import_description, dest_description):
    '''Given import and destination Agave file JSON descriptions (only lastModified key required), return TRUE if import file is more recently modified.'''
    assert 'lastModified' in import_description, 'lastModified key not in import description keys: {}'.format(import_description.keys())
    assert 'lastModified' in dest_description, 'lastModified key not in destination description keys: {}'.format(dest_description.keys())
    import_modtime = get_agavefile_modtime(import_description)
    dest_modtime = get_agavefile_modtime(dest_description)
    return(import_modtime > dest_modtime)
# end modification time helper functions

# recursive files functions
def recursive_get(url, headers, destination='.', url_type=url, url_base=None, tab=''):
    '''Performs recursive files-get from remote to local location (ONLY AGAVE CURRENTLY SUPPORTED)'''
    assert url_type == agave, 'Only agave currently supported for recursive files-get; source was type {}'.format(url_type)
    # get listable url and file-list
    list_url = agave_path_setlisting(url, url_base)
    list_json = list_agave_dir_files(list_url, headers)

    for i in list_json:
        filename = i['name']

        # if is directory and '.': mkdir if necessary, otherwise skip
        if i['type'] == 'dir' and filename == '.':
            directoryname = basename(i['path'])
            destination += '/{}'.format(directoryname) # add dirname to local path
            if not isdir(destination):
                logger.debug('mkdir {}'.format(destination))
                makedirs(destination)
            else:
                logger.debug('skipping {} ({})'.format(directoryname, 'exists'))
            tab += '  '

        # elif is not '.' but still directory, recurse
        elif i['type'] == 'dir':
            recursion_url = '{}/{}'.format(url,filename)
            recursive_get(recursion_url, headers, destination=destination, url_type=url_type, url_base=url_base, tab=tab)

        # must be file; download if not in local dir (new) or agave timestamp is newer (modified), otherwise skip
        else:
            # build file url by adding filename
            file_url = '{}/{}'.format(url, filename)
            filename_fullpath = '{}/{}'.format(destination, filename)
            file_size = get_agavefile_size(i)
            if filename not in listdir(destination):
                logger.debug('downloading {} ({})'.format(filename, 'new'))
                if file_size > 0:
                    files_download(file_url, headers, path=destination)
                else:
                    files_touch(file_url, destination)
            elif newer_agavefile(filename_fullpath, i):
                logger.debug('downloading {} ({})'.format(filename, 'modified'))
                if file_size > 0:
                    files_download(file_url, headers, path=destination)
                else:
                    files_touch(file_url, destination)
            else:
                logger.debug('skipping {} ({})'.format(filename, 'exists'))
    return

def recursive_upload(url, headers, source='.', url_type=url, url_base=None, tab=''):
    '''Recursively upload files from a local directory to an agave directory'''

    # if agave url, make listable
    if url_type == agave:
        list_url = agave_path_setlisting(url, url_base, listings=True)
    else:
        logger.warning('WARNING: recursive upload not tested for non-agave remote directories')

    # check url EXISTS and is type DIR
    # make dir of urlfiles info { name:{modified, type}}
    urlfiles = list_agave_dir_files(list_url, headers)
    urlinfo = {i['name']:{'lastModified':i['lastModified'],'type':i['type']} for i in urlfiles}
    assert '.' in urlinfo, 'Url {} is not valid directory'.format(url)

    for filename in listdir(expanduser(source)):
        fullpath = '{}/{}'.format(expanduser(source), filename)
        # if present at dest: skip if dir or agavefile is newer, else upload file
        if filename in urlinfo and sametype(fullpath, urlinfo[filename]):
            if isdir(fullpath) or newer_agavefile(fullpath, urlinfo[filename]):
                logger.debug('skipping {} ({})'.format(filename, 'exists'))
            else:
                logger.debug('uploading {} ({})'.format(filename, 'modified'))
                files_upload(fullpath, url, headers)
        # else, not present at dest, so either upload file or make dir
        elif isfile(fullpath):
            logger.debug('uploading {} ({})'.format(filename, 'new'))
            files_upload(fullpath, url, headers)
        else:
            logger.debug('mkdir {}'.format(filename))
            files_mkdir(filename, url, headers)

        # if is directory (newly made or old), recurse
        if isdir(fullpath):
            recursion_url = '{}/{}'.format(url,filename)
            recursive_upload(recursion_url, headers, source=fullpath, url_type=url_type, url_base=url_base, tab=tab+'  ')
    return

def recursive_import(source, destination, headers, stype=url, dtype=url, url_base=None, tab=''):
    '''Performs recursive files-import between remote locations (ONLY AGAVE CURRENTLY SUPPORTED).'''
    assert stype == agave, 'Only agave currently supported for recursive files-get; source was type {}'.format(stype)
    assert dtype == agave, 'Only agave currently supported for recursive files-get; destination was type {}'.format(dtype)

    # get source list url and dict
    slisturl = agave_path_setlisting(source, url_base)

    # get dict of destination files
    dfiles = update_import_destfiles_dict(destination, headers, dest_type=dtype, url_base=url_base)

    for finfo in list_agave_dir_files(slisturl, headers):
        fname = finfo['name']

        # if dir and '.': mkdir if necessary; otherwise skip
        if finfo['type'] == 'dir' and fname == '.':
            directoryname = basename(finfo['path'])
            if directoryname not in dfiles:
                logger.debug('mkdir {}'.format(directoryname))
                files_mkdir(directoryname, destination, headers)
            else:
                logger.debug('skipping {} ({})'.format(directoryname, 'exists'))
            destination += '/{}'.format(directoryname)
            dfiles = update_import_destfiles_dict(destination, headers, dest_type=dtype, url_base=url_base)
            tab += '  '

        # elif is not '.' but still directory, recurse
        elif finfo['type'] == 'dir':
            recursion_source = '{}/{}'.format(source,fname)
            recursive_import(recursion_source, destination, headers, stype=stype, dtype=stype, url_base=url_base, tab=tab)

        # must be file; import if not in dest dir (new) or source timestamp is newer (modified), otherwise skip
        else:
            fpath = '{}/{}'.format(source, fname)
            if fname not in dfiles:
                logger.debug('importing {} ({})'.format(fname, 'new'))
                files_import(fpath, destination, headers)
            elif newer_importfile(finfo, dfiles[fname]):
                logger.debug('importing {} ({})'.format(fname, 'modified'))
                files_import(fpath, destination, headers)
            else:
                logger.debug('skipping {} ({})'.format(fname, 'exists'))
    return
# end recursive files functions

if __name__ == '__main__':

    logger = get_logger('agave-files-sync')

    # arguments
    parser = argparse.ArgumentParser(description='Script to combine file-upload, files-get, and files-import. When recursion (-r) specified, a trailing slash on source path syncs contents of source and destination; no trailing slash nests source under destination.')
    parser.add_argument('-n', '--name', dest='name', help='new file name')
    parser.add_argument('-r', '--recursive', dest='recursive', action='store_true', help='sync recursively')
    parser.add_argument('source', help='source path (local, agave, or url)')
    parser.add_argument('destination', default='.', nargs='?', help='destination path (local or agave; default $PWD)')
    args = parser.parse_args()

    # if recursive run, ignore name flag
    if args.recursive and args.name is not None:
        logger.warning('Ignoring name flag due to recursion.')

    # Adapt the code we use in CI testing to bootstrap credentials
    ag = agave(credentials())
    try:
        access_token = ag.token.token_info['access_token']
        baseurl = ag.token.api_server
    except Exception as e:
        exit('Error initializing api client: {}'.format(e))

    # we will eventually need to replace the direct calls to requests with agavepy
    h = { 'Authorization': 'Bearer {}'.format(access_token) }

    # check for trailing slash on source, then strip slashes
    # if recursing: trailing slash means no nesting
    # else: ERROR because unsure what to do
    source_slash = (args.source[-1] == '/')
    if source_slash and not args.recursive:
        exit('Please provide either a path to a file or specify a recursive response.')
    else:
        args.source = (args.source[:-1] if args.source[-1] == '/' else args.source)
    args.destination = (args.destination[:-1] if args.destination[-1] == '/' else args.destination)

    # determine path types
    source_type = get_path_type(args.source)
    dest_type = get_path_type(args.destination)

    # reformat agave urls
    if source_type == agave:
        args.source = agave_path_builder(baseurl, args.source, recursive=args.recursive)
    if dest_type == agave:
        args.destination = agave_path_builder(baseurl, args.destination)

    # source=agave/url and dest=local --> get
    if source_type != local and dest_type == local:
        if args.recursive:
            logger.debug('Beginnning recursive download...')
            recursive_get(args.source, h, destination=args.destination, url_type=source_type, url_base=baseurl)
        else:
            #logger.debug('Downloading', basename(args.source), 'to', args.destination)
            files_download(args.source, h, path=args.destination, name=args.name)
    
    # source=local and dest=agave --> upload
    elif source_type == local and dest_type == agave:
        if args.recursive:
            logger.debug('Beginning recursive upload...')
            recursive_upload(args.destination, h, source=args.source, url_type=dest_type, url_base=baseurl)
        else:
            logger.debug('Uploading', basename(args.source), 'to', args.destination)
            files_upload(expanduser(args.source), args.destination, h, new_name=args.name)

    # source=agave/url and dest=agave --> import
    elif source_type != local and dest_type == agave:
        if source_type == url:
            logger.warning('WARNING: generic urls not yet tested')

        if args.recursive:
            logger.debug('Beginning recursive import...')
            recursive_import(args.source, args.destination, h, stype=source_type, dtype=dest_type, url_base=baseurl)
        else:
            logger.debug('Importing', basename(args.source), 'to', args.destination)
            files_import(args.source, args.destination, h, new_name=args.name)

    # other combos --> error 
    else:
        exit('Cannot have source type', source_type, 'and destination type', dest_type)
