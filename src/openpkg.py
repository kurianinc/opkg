#!/usr/bin/python

import yaml
import re
import os
import subprocess
import ConfigParser
import time
import hashlib
import sys

'''Default config file. This can be overridden by opkg CLI option --conf-file'''
OPKG_CONF_FILE='/etc/opkg/conf/opkg.env'

META_FILE_PREVIOUS='Previous.meta'
META_FILE_LATEST='Latest.meta'
EXTRA_PARAM_DELIM=','
EXTRA_PARAM_KEY_VAL_SEP='='

''' Classes '''

'''Tracks local env configuration'''
class EnvConfig():
    def __init__(self):
        self.config_file=OPKG_CONF_FILE
        self.conf=None

    def setConfigFile(self,config_file):
        self.config_file=config_file

    def loadConfigFile(self):
        self.conf = ConfigParser.ConfigParser()
        if os.path.isfile(self.config_file) and os.access(self.config_file, os.R_OK):
            self.conf.read(self.config_file)

    def updateConfigItem(self,section,key,val):
        try:
            self.conf.set(section,key,val)
        except:
            print "Warning: Cannot locate config item "+key+" in "+self.config_file
            return False

        return True

    def getConfigItem(self,section,item):
        return self.conf.get(section,item)

'''Class to read opkg manifest '''
class Manifest():

    def __init__(self, manifest_path):
        self.manifest_file=manifest_path
        self.manifest_dict=None
        self.rel_num=None

        with open(self.manifest_file, 'r') as stream:
            try:
                self.manifest_dict=yaml.load(stream)
            except yaml.YAMLError as exc:
                print "Error: Problem loading manifest file "+self.manifest_file
                print(exc)
                return

        if 'rel_num' not in self.manifest_dict:
            print "rel_num not found in "+self.manifest_file
            self.manifest_dict=None
            return

        self.rel_num=self.manifest_dict['rel_num']

    def getConfig(self):
        return self.manifest_dict

    '''The action lines are available as dictionaries and converting those to a list is easier to deal with down the road.
    It could be a mixed-bag, plain list item or a dict element.
    '''
    def getSectionItems(self, section):
        if section not in self.manifest_dict: return None
        lines = list()
        for item in self.manifest_dict[section]:
            if type(item) is str:
                lines.append(item)
            elif type(item) is dict:
                for key in item:
                    val = item[key]
                    lines.append(key + ':' + val)
                    break
            else:
                print "Error: Unknown format in "+self.manifest_file+", section: "+section
                return None

        return lines

'''Class for core Open Pkg'''
class Pkg():
    def __init__(self,name):
        if re.search("\W", name) is not None:
            print "Error: Illegal character in package name (" + name + ")"
            return
        self.name=name
        self.rel_num=None
        self.rel_ts=None
        self.is_release=False
        self.manifest_file = name + '.yml'
        self.tarball_name = name + '.tgz'
        self.md5=None #md5 of package being installed.
        self.manifest=None
        self.build_root = os.getcwd()
        self.manifest_path=self.build_root+'/'+self.manifest_file

        '''stage_dir - where files to create a tarball are staged and
        files from a tarball are extracted for deployment.
        By default, the stage_dir is set for action create pkg.
        '''
        self.stage_dir = self.build_root + '/.pkg/' + name
        self.deploy_dir=self.stage_dir+'/.deploy'

        self.env_conf=None
        self.install_meta=None #meta data of existing installation
        self.install_md5=None #md5 of currently installed version

    @staticmethod
    def parseName(pkg_label):
        '''pkg can be specified in following ways:
        - /path/to/mypkg.tgz -- tarball available on locally
        - /path/to/mypkg-rel_num.tgz -- tarball available on locally
        - mypkg
        - mypkg-rel_num
        '''
        pkg_name_rel_num = os.path.basename(pkg_label)
        pkg_name_rel_num = pkg_name_rel_num.replace('.tgz', '')
        tarball_name = pkg_name_rel_num + '.tgz'
        pkg_name = re.split('-', pkg_name_rel_num)[0]

        return pkg_name,pkg_name_rel_num,tarball_name

    @staticmethod
    def parseTarballName(tarball_name):
        rel_num, rel_ts = 'dev', None
        '''The dev version will not have any rel_num or rel_ts
        The parsing is based on the assumption that the tarball names can have only 2 formats:
         name.tgz - dev
         name-rel_num-rel_ts.tgz - release
        '''
        m = re.search('.+?-(.+?)-(.+).tgz', tarball_name)
        if m:
            rel_num = m.group(1)
            rel_ts = m.group(2)

        return rel_num,rel_ts

    def setManifest(self,f):
        self.manifest_path=f
    def loadManifest(self):
        self.manifest = Manifest(self.manifest_path)

    def setRelNum(self,rel_num):
        self.rel_num=rel_num
    def setRelTs(self,rel_ts):
        self.rel_ts=rel_ts

    '''Meta file has this syntax: pkg_name,rel_num,rel_ts,pkg_md5,deploy_ts'''
    def loadMeta(self):
        self.install_meta=dict()
        meta_dir=self.env_conf['basic']['opkg_dir'] + '/meta/' + self.name
        meta_path = meta_dir + "/" + META_FILE_LATEST
        self.install_meta['latest_install']=self.loadMetaFile(meta_path)
        if not self.install_meta['latest_install']:
            print "Info: No active installation of "+self.name+" found."
        meta_path = meta_dir + "/" + META_FILE_PREVIOUS
        self.install_meta['previous_install'] = self.loadMetaFile(meta_path)
        if not self.install_meta['previous_install']:
            print "Info: No previous installation of "+self.name+" found."
        if self.install_meta['latest_install']:
            self.install_md5 = self.install_meta['latest_install']['pkg_md5']

    def getMeta(self):
        return self.install_meta

    '''Load .meta files that keep track of deployments and verifies the data in those.
    The meta data on package deployment is a single line with attrs delimited by , in the following order:
    pkg_name,pkg_rel_num,pkg_ts,pkg_md5,deploy_ts
    '''
    def loadMetaFile(self,file_path):
        if not os.path.isfile(file_path): return None
        str = loadFile(file_path)
        install_info = str.strip().split(',')
        if len(install_info) < 5: return None
        meta=dict()
        meta['pkg_name']=install_info[0]
        meta['pkg_rel_num'] = install_info[1]
        meta['pkg_ts'] = install_info[2]
        meta['pkg_md5'] = install_info[3]
        meta['deploy_ts'] = install_info[4]

        return meta

    '''Reset install meta files upon successful installation of a package.'''
    def registerInstall(self,deploy_inst):
        meta_dir=deploy_inst.opkg_dir + "/meta/" + self.name
        meta_file_previous = meta_dir + "/" + META_FILE_PREVIOUS
        meta_file_latest = meta_dir + "/" + META_FILE_LATEST
        runCmd("mkdir -p "+meta_dir)

        if os.path.exists(meta_file_latest):
            if not execOSCommand("mv -f " + meta_file_latest + " " + meta_file_previous):
                print "Problem moving " + meta_file_latest + " as " + meta_file_previous
                return False

        '''Meta file has this syntax: pkg_name,rel_num,rel_ts,pkg_md5,deploy_dir'''
        rel_num=''
        if self.rel_num: rel_num=self.rel_num
        rel_ts=0
        if self.rel_ts: rel_ts=self.rel_ts
        strx = self.name+','+rel_num+','+str(rel_ts)+','+self.pkg_md5+','+deploy_inst.deploy_ts
        cmd = "echo " + strx + ">" + meta_file_latest
        if not execOSCommand(cmd):
            print "Error: Couldn't record the package installation."
            return False
        self.loadMeta()

        return True

    def setRelease(self,is_release=True):
        self.is_release=is_release

    def setEnvConfig(self,env_conf):
        self.env_conf=env_conf

    def create(self):
        self.loadManifest() #the default manifest points to that in build dir

        runCmd("mkdir -p " + self.stage_dir)
        os.chdir(self.stage_dir)
        runCmd("rm -rf *")

        '''Copy manifest to the deploy folder in archive'''
        runCmd('mkdir -p ' + self.deploy_dir)
        if not execOSCommand('cp ' + self.manifest_path + ' ' + self.deploy_dir + '/'):
            print "Error: Problem copying package manifest."
            return False

        '''Stage files content for archiving'''
        content_lines=self.manifest.getSectionItems('files')
        if content_lines:
            for content_line in content_lines:
                tgt,src=re.split(':',content_line)
                if not self.stageContent(self.build_root+'/'+src,tgt):
                    print "Error: Cannot copy content at "+src+" for archiving."
                    return False

        '''Make tarball and clean up the staging area'''
        if self.is_release:
            rel_num=self.manifest['rel_num']
            self.tarball_name = self.name + '-' + rel_num + '.tgz'
        os.chdir(self.stage_dir)
        rc = runCmd("tar czf " + self.tarball_name + ' * .deploy')
        if rc != 0:
            print "Error: Couldn't create package " + self.tarball_name
            return False
        os.chdir(self.build_root)
        rc = runCmd('mv ' + self.stage_dir + '/' + self.tarball_name + ' ./')
        if rc == 0:
            runCmd("rm -rf " + self.stage_dir)
            print "Package " + self.tarball_name + " has been created."
        else:
            print "Error: Package " + self.tarball_name + " couldn't be created."
            return False

    def stageContent(self,src,tgt):
        os.chdir(self.stage_dir)
        if os.path.isdir(src):
            '''skip build folder silently, but individual files can still be added.'''
            if runCmd("mkdir -p " + tgt) != 0: return False
            if runCmd("cp -r " + src + '/. ' + tgt + '/') != 0: return False
        else:
            tgt_dir = os.path.dirname(tgt)
            if tgt_dir != '':
                if runCmd("mkdir -p " + tgt_dir) != 0: return False
            if runCmd("cp " + src + ' ' + tgt) != 0: return False

        return True

    '''Execute the deploy playbook for a package specified in the manifest'''
    def install(self,tarball_path,deploy_inst):
        deploy_inst.logHistory("Installing package "+self.name+" using "+tarball_path)

        ''' Track the md5 of package being installed '''
        self.pkg_md5=getFileMD5(tarball_path)

        '''Extract the tarball in stage_dir, to prepare for deploy playbook to  execute steps'''
        stage_dir=deploy_inst.opkg_dir+'/pkgs/'+self.name+'/'+deploy_inst.deploy_ts
        if not execOSCommand('mkdir -p ' + stage_dir):
                return
        os.chdir(stage_dir)

        if not execOSCommand('tar xzf ' + tarball_path):
            print "Error: Problem extracting " + tarball_path + " in " + stage_dir
            return False

        '''Setup install location for the new deployment of pkg'''
        deploy_dir = deploy_inst.deploy_root + '/' + self.name
        deploy_inst.extra_vars['OPKG_DEPLOY_DIR'] = deploy_dir
        if not execOSCommand('mkdir -p ' + deploy_dir):
            return False

        '''Resolve manifest, and files defined under templates and replaces with actual values 
        defined for this specific deployment.'''
        os.chdir('.deploy')
        manifest_path=os.getcwd()+'/'+self.manifest_file
        tmpl_inst=Tmpl(manifest_path)
        if not tmpl_inst.resolveVars(deploy_inst.getVars()):
            print "Error: Problem resolving "+self.manifest_file
            return False
        pkg_manifest=Manifest(manifest_path)

        '''Run pre-deploy steps. 
        These are run immediately after the tarball is extracted in stage_dir
        '''
        steps = pkg_manifest.getSectionItems('pre_deploy')
        if steps:
            for step in steps:
                if not execOSCommand(step):
                    print "Error: Problem executing the following step in pre_deploy phase: "+step
                    return False

        '''copy targets entries to install_root'''
        targets=pkg_manifest.getSectionItems('targets')
        if targets:
            for target in targets:
                tgt,src=re.split(':',target)
                source_path,target_path = src,tgt
                if not re.match("^\/", src): source_path = stage_dir + "/" + src
                if not re.match("^\/", tgt): target_path = deploy_dir + "/" + tgt

                if not createTargetPath(source_path, target_path):
                    print "Error: Base dir of " + target_path + " cannot be created."
                    return False
                cmd='cp '+source_path+' '+target_path #if a file
                if os.path.isdir(source_path): cmd='cp -r '+source_path+'/* '+target_path+'/'
                if not execOSCommand(cmd):
                    print "Error: Problem copying from " + stage_dir + ". command: " + cmd
                    return False

        '''Generate deployed template files with actual values, variables are marked as {{ var }} '''
        templates = pkg_manifest.getSectionItems('templates')
        if templates:
            for tmpl in templates:
                tmpl_path=tmpl
                if not re.match("^\/", tmpl): tmpl_path = deploy_dir + "/" + tmpl
                tmpl_inst=Tmpl(tmpl_path)
                if not tmpl_inst.resolveVars(deploy_inst.getVars()):
                    print "Error: Couldn't install resolved files for those marked as templates, with real values."
                    return False

        '''Replaces tokens in files flagged for that, tokens are unmarked like PORT=80 etc'''
        if 'replaces' in pkg_manifest.getConfig():
            for replaces_file in pkg_manifest.getConfig()['replaces']:
                '''Each entry for replacement in the replaces_file is a dict as replacement entries are delimited with :'''
                replaces_list=list()
                for token_dict in pkg_manifest.getConfig()['replaces'][replaces_file]:
                    for key in token_dict:
                        replaces_list.append(key+Tmpl.TMPL_KEY_VAL_DELIM+token_dict[key])
                        break
                replaces_path=replaces_file
                if not re.match("^\/", replaces_file): replaces_path = deploy_dir + "/" + replaces_file
                tmpl_inst=Tmpl(replaces_path)
                if not tmpl_inst.replaceTokens(replaces_list):
                    print "Error: Couldn't install resolved files for those marked with having tokens in the 'replaces' section, with real values."
                    return False

        '''Symlinks'''
        symlinks = pkg_manifest.getSectionItems('symlinks')
        if symlinks:
            for symlink in symlinks:
                tgt_path,src_path=re.split(':',symlink)
                if not re.match("^\/", tgt_path): tgt_path = deploy_dir + "/" + tgt_path
                if not re.match("^\/", src_path): src_path = deploy_dir + "/" + src_path
                cmd = "ln -sfn " + src_path + " " + tgt_path
                if not execOSCommand(cmd):
                    print "Error: Problem creating symlink " + cmd
                    return False

        '''Permissions
        The list items will be returned in the format, dir:owner:group mod; eg: 'apps:root:root 0444'
        Parse each line accordingly.
        '''
        perms = pkg_manifest.getSectionItems('permissions')
        if perms:
            for perm in perms:
                fpath, owner,group,chmod_opt = re.split('[ :]', perm)
                if not re.match("^\/", fpath): fpath = deploy_dir + "/" + fpath
                chown_opt=owner+':'+group
                cmd="chown -R "+chown_opt+" "+fpath+';chmod -R '+chmod_opt+' '+fpath
                if not execOSCommand(cmd):
                    print "Error: Problem setting permissions on " + fpath+'. Command: '+cmd
                    return False

        '''Post-deploy steps'''
        steps = pkg_manifest.getSectionItems('post_deploy')
        if steps:
            for step in steps:
                if not execOSCommand(step):
                    print "Error: Problem executing the following step in post_deploy phase: " + step
                    return False
        
        ''' Register the installation '''
        self.registerInstall(deploy_inst)

        '''delete the stage_dir upon successful installation of the package'''
        os.chdir("/tmp")  # a workaround to avoid system warning when curr dir stage_dir is deleted.
        if not execOSCommand('rm -r ' + stage_dir):
            print "Warning: Couldn't delete " + stage_dir

        return True

    def isInstalled(self,tarball_path):
        if not self.getMeta()['latest_install']:
            return False
        md5_local = self.install_meta['latest_install']['pkg_md5']

        return (getFileMD5(tarball_path) == md5_local)

'''Class to process the main opkg actions'''
class opkg():
    ACTIONS=['create','ls','rls','get','put','deploy','clean','start','stop','restart','rollback']

    '''action specific required configs'''
    ACTION_CONFIGS={
        'deploy': ['install_root'],
        'ls':['install_root'],
        'put':['repo_type','repo_path'],
        'get': ['repo_type', 'repo_path']
    }

    OPKG_LABEL='opkg'
    OPKG_VERSION='0.1.0'

    def __init__(self,params):
        self.arg_dict=dict()
        self.arg_dict['opkg_cmd']=params[0]
        self.action=None #This will be available in the env as OPKG_ACTION
        self.extra_vars=dict()
        self.conf_file=None
        self.configs=dict()
        self.pkgs=None
        self.opkg_dir=None

        if len(params) < 2:
            self.printHelp()
            Exit(0)

        '''action is positional'''
        self.action=params[1]

        '''The args can be in these formats: argx,--opt_x,--opt_y=opt_val'''
        for argx in params[1:]:
            if re.match("^--", argx) is not None:
                m = re.split('--', argx)
                n = re.match("^(.+?)=(.+)", m[1])
                if n is not None:
                    self.arg_dict[n.group(1)] = n.group(2)
                else:
                    self.arg_dict[m[1]] = ''
            else:
                self.arg_dict[argx] = ''

        '''Set extra-vars dict'''
        if 'extra-vars' in self.arg_dict:
            extra_vars = re.split(EXTRA_PARAM_DELIM,self.arg_dict['extra-vars'])
            for extra_var in extra_vars:
                k, v = re.split(EXTRA_PARAM_KEY_VAL_SEP,extra_var)
                self.extra_vars[k] = v

        if self.arg_dict.has_key('help'):
            self.printHelp()
            Exit(0)
        elif self.arg_dict.has_key('version'):
            self.printVersion()
            Exit(0)

        '''Check if config file is specified, if it exists load and initialize configs from it.
        Note, the config items are grouped under sections in config file, but, 
        from command-line there is no option to qualify an item with section and so it should be unique across sections.
        '''
        opkg_conf_file=OPKG_CONF_FILE
        if 'opkg_dir' in self.arg_dict: opkg_conf_file=self.arg_dict['opkg_dir']+'/conf/opkg.env'
        self.conf_file=opkg_conf_file
        self.loadConfigFile()
        self.opkg_dir=self.configs['basic']['opkg_dir']

        '''Override config items specified in config file with those from command-line'''
        for section in self.configs:
            for item in self.configs[section]:
                if item in self.arg_dict: self.configs[section][item]=self.arg_dict[item]

        '''Parse out common options such as pkg'''
        if 'pkg' in self.arg_dict:
            self.pkgs=re.split(',',self.arg_dict['pkg'])

        return

    '''Loads configs from opkg.env as a dictionary'''
    def loadConfigFile(self):
        Config = ConfigParser.ConfigParser()
        Config.read(self.conf_file)
        sections=Config.sections()
        for section in sections:
            self.configs[section]=dict()
            for item in Config.options(section):
                self.configs[section][item]=Config.get(section,item)
        return

    def printVersion(self):
        print opkg.OPKG_LABEL + " v" + opkg.OPKG_VERSION

        return True

    def printHelp(self):
        self.printVersion()

        script = os.path.basename(self.arg_dict['opkg_cmd'])
        print "Usages:"
        print script + " --version"
        print script + " --help"
        print script + " ls [--pkg=pkg1,pkg2,...]"
        print script + " rls [--pkg=pkg1,pkg2,...]"
        print script + " create --pkg=pkg1,pkg2,... [--release]"
        print script + " put --file=/tarball/with/full/path"
        print script + " get --pkg=pkg1,pkg2,... [--release=REL_NUM|dev] [--path=/download/path]" 
        print script + " deploy --pkg=pkg1,pkg2[-REL_NUM|dev],... [--install_root=/path/to/install]"
        print script + " start|stop|restart|reload --pkg=pkg1,pkg2,... [--install_root=/path/to/install]"
        print script + " rollback --pkg=pkg1,pkg2,... [--install_root=/path/to/install]"
        print script + " clean [--pkg=pkg1,pkg2,...] [--count=COUNT] [--install_root=/path/to/install]"

        return True

    '''Execute the action'''
    def main(self):

        if self.action=='create':
            self.extra_vars['ACTION'] = 'create'
            for pkg in self.pkgs:
                pkg_inst=Pkg(pkg)
                pkg_inst.create()

        elif self.action=='ls':
            self.extra_vars['ACTION'] = 'ls'
            for pkg in self.pkgs:
                pkg_name, pkg_name_rel_num, tarball_name = Pkg.parseName(pkg)
                pkg_inst=Pkg(pkg_name)
                pkg_inst.setEnvConfig(self.configs)
                pkg_inst.loadMeta()
                pkg_meta=pkg_inst.getMeta()
                if not pkg_meta: continue
                print pkg_name+'-'+pkg_meta['latest_install']['pkg_rel_num']

        elif self.action=='deploy':
            self.extra_vars['ACTION'] = 'deploy'
            deploy_inst=Deploy(self.configs,self.arg_dict,self.extra_vars)
            for pkg in self.pkgs:
                pkg_name,pkg_name_rel_num,tarball_name=Pkg.parseName(pkg)
                is_local=False
                if re.match('^.+?\.tgz',pkg): is_local=True
                download_dir=self.opkg_dir+'/pkgs/'+pkg_name
                execOSCommand("mkdir -p "+download_dir)
                if is_local:
                    if not execOSCommand("cp "+pkg+" "+download_dir+"/"):
                        print "Error: Cannot copy tarball "+tarball_name+" to staging location "+download_dir
                        Exit(1)
                else:
                    '''The tarball has to be downloaded in this case from a repo.
                    The possible values of pkg would be mypkg or mypkg-rel_num.
                    '''
                    print "Error: tarball cannot be downloaded for package specified: "+pkg
                    Exit(1)

                '''Start installation of the package once the tarball is copied to staging location.'''
                deploy_inst.installPackage(pkg_name,tarball_name)
        else:
            print "Unsupported action: "+self.action

'''Class for deployment specific methods'''
class Deploy():
    def __init__(self,env_conf,deploy_options,extra_vars=None):
        self.deploy_ts=str(int(time.time()))
        self.env_conf=env_conf
        self.install_root=self.env_conf['basic']['install_root']
        self.deploy_root=self.install_root+'/installs/'+self.deploy_ts
        self.opkg_dir=self.env_conf['basic']['opkg_dir']
        self.download_root=self.opkg_dir + '/pkgs'
        self.history_dir=self.opkg_dir + '/history'
        self.extra_vars=extra_vars

        self.deploy_force=False
        if 'force' in deploy_options: self.deploy_force=True

        if not self.extra_vars: self.extra_vars=dict()
        self.extra_vars['OPKG_NAME'] = None
        self.extra_vars['OPKG_REL_NUM'] = None
        self.extra_vars['OPKG_TS'] = None
        self.extra_vars['OPKG_ACTION'] = None

        if not execOSCommand('mkdir -p ' + self.download_root): return
        if not execOSCommand('mkdir -p ' + self.history_dir): return

    '''Returns the extra-vars specified from commandline and the OPKG_ vars'''
    def getVars(self):
        return self.extra_vars

    def logHistory(self,log_entry):
        history_log=self.deploy_ts+": "+log_entry
        history_file=self.env_conf['basic']['deploy_history_file']
        with open(self.history_dir + '/' + history_file, "a") as hf: hf.write(history_log+"\n")

        return True

    '''The tarball is downloaded/copied to download_dir'''
    def installPackage(self,pkg_name,tarball_name):
        rel_num,rel_ts=Pkg.parseTarballName(tarball_name)

        self.extra_vars['OPKG_NAME'] = pkg_name
        self.extra_vars['OPKG_REL_NUM'] = rel_num
        self.extra_vars['OPKG_TS'] = rel_ts

        pkg=Pkg(pkg_name)
        pkg.setRelNum(rel_num)
        pkg.setRelTs(rel_ts)
        pkg.setEnvConfig(self.env_conf)
        pkg.loadMeta()
        tarball_path=self.download_root+'/'+pkg_name+'/'+tarball_name
        if not pkg.isInstalled(tarball_path) or self.deploy_force:
            pkg.install(tarball_path,self)
        else:
            print "Info: This revision of package "+pkg_name+" is already installed at "+self.install_root+'/installs/'+pkg.getMeta()['latest_install']['deploy_ts']+'/'+pkg_name

        return True

'''Utility classes '''

'''Utility class to do template related tasks'''
class Tmpl():
    TMPL_KEY_VAL_DELIM=':'

    def __init__(self,tmpl_path):
        self.tmpl_path=tmpl_path
        self.is_dir=False
        if not os.path.exists(tmpl_path):
            print "Error: " + tmpl_path + " doesn't exist."
            return
        if os.path.isdir(tmpl_path): self.is_dir = True

    '''Recreates files under tmpl_path with values from vars_dict
    The template vars are searched for using pattern {{ var }}
    tmpl_path could be single file or a directory, 
    in the latter case all files in the dir will be checked for recursively.
    '''
    def resolveVars(self,vars_dict,backup=False):
        if self.is_dir:
            files=os.listdir(self.tmpl_path)
            for f in files:
                ftmpl=Tmpl(self.tmpl_path+'/'+f)
                ftmpl.resolveVars(vars_dict,backup)
        else:
            if not self.resolveVarsFile(self.tmpl_path,vars_dict,backup):
                print "Error: Failed to resolve template "+self.tmpl_path
                return False

        return True

    '''Recreates files under tmpl_path with values from vars_list
    vars_list contains a search/replace pair SEARCH-STR:REPLACE-STR, the file is updated by replacing all SEARCH-STR with REPLACE-STR
    tmpl_path could be single file or a directory, 
    in the latter case all files in the dir will be checked for recursively.
    '''
    def replaceTokens (self,tokens_list,backup=False):
        if self.is_dir:
            files = os.listdir(self.tmpl_path)
            for f in files:
                fpath = self.tmpl_path + '/' + f
                ftmpl = Tmpl(fpath)
                ftmpl.replaceTokens(tokens_list,backup)
        else:
            if not self.replaceTokensFile(self.tmpl_path,tokens_list, backup):
                print "Error: Failed to resolve template " + self.tmpl_path
                return False

        return True

    def resolveVarsFile(self,file_path, vars_dict, backup=False):
        str = loadFile(file_path)
        for var in vars_dict:
            if var not in vars_dict or not vars_dict[var]: continue
            str = re.sub('{{ ' + var + ' }}', vars_dict[var], str)
        if backup:
            if not execOSCommand("mv " + file_path + " " + file_path + '.' + str(int(time.time()))):
                print "Error: Couldn't backup " + file_path
                return False
        try:
            with open(file_path, "w") as f:
                f.write(str)
        except EnvironmentError:
            print "Error: Cannot save updated " + file_path
            return False

        return True

    def replaceTokensFile(self,file_path, tokens_list, backup=False):
        str = loadFile(file_path)
        for token in tokens_list:
            pattern, replace = re.split(Tmpl.TMPL_KEY_VAL_DELIM,token)
            str = re.sub(pattern, replace, str)
        if backup:
            if not execOSCommand("mv " + file_path + " " + file_path + '.' + str(int(time.time()))):
                print "Error: Couldn't backup " + file_path
                return False
        try:
            with open(file_path, "w") as f:
                f.write(str)
        except EnvironmentError:
            print "Error: Cannot save updated " + file_path
            return False

        return True

''' Utility Functions '''

'''returns the status code after executing cmd in the shell'''
def runCmd(cmd):
    return subprocess.call(cmd,shell=True)

'''process return status from a command execution '''
def execOSCommand(cmd):
   rc=runCmd(cmd)
   if rc!=0:
       print "Error executing "+cmd
       return False

   return True

'''Returns output of a command run in the shell'''
def getCmdOutput(cmd):
    output=subprocess.check_output(cmd, shell=True)

    return output.strip()

'''Execute a command locally: on Mac or Linux, so this must be platform independent'''
def execCmdLocal(cmd):
    global verbose

    out=None
    try:
        out=subprocess.check_output(cmd,shell=True)
    except Exception as e:
        if verbose: print (e)

    return out

'''returns the file content as a string.'''
def loadFile(file_path):
    s = open(file_path)
    str = s.read()
    s.close()

    return str

'''Create a target location depending on what is to be copied from source'''
def createTargetPath(source_path,target_path):
    d=target_path
    if os.path.isfile(source_path): d=os.path.dirname(target_path)
    base_dir=d.split()[0]
    if not os.path.exists(base_dir):
        cmd="mkdir -p "+base_dir
        if not execOSCommand(cmd):
            print "Error: Couldn't create "+base_dir
            return False

    return True

def Exit(rc):
    sys.exit(rc)

def getFileMD5(file_path):
    return hashlib.md5(open(file_path, 'rb').read()).hexdigest()

''' main '''

opkg_cmd=opkg(sys.argv)
opkg_cmd.main()
