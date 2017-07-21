# Open Package Project

Open Package is an open-source project to develop a platform independant packaging and deployment tool.

It is similar to rpm or Debian packaging, but, not tied to any specific Operating System or development environments like npm or J2EE.

## Basic Features 

Using Open Package tool a package can be created using the following command:

```$ opkg create --pkg=myapp```

The above command will create a tarball myapp.tgz based on the meta-data defined in myapp.yml. In myapp.yml, you can specify the content of myapp.tgz, and, how myapp is installed on a target host.

A package is installed on the local system as in the following example:

```$ opkg install --pkg=/path/to/myapp.tgz```

When installing a package the following syntax can be used as well:

```$ opkg install --pkg=myapp```

In the above case, package tool will try to download myapp.tgz from a remote repository or shared drive based on the local repository configuration. We will see how a repository can be setup for maintaining opkg packages, in the latter sections.

## Advantages of Open Package

These are the general advtantages of using Open Project in place rpm or similar packaging tools:
- extremely simple packaging system that uses an open archive format, tarball.
- opkg packages are flexible enough to be installed in environments with varied configuration.
- keep track of the state of package. If an app is encapsulated as a package with its lifecycle defined, opkg can manage that easily.

## Package Manifest

Following is a sample package manifest with all the supported options used:

```
#Sample opkg manifest file 
--- 

#Core Configs 
name: myapp
rel_num: 1.2.3

depends:
 - baseapp 
#- coreapp LATEST
#- another_app 1.0.0

conflicts:
 - badapp 

#Package Content
files:
   - greeting/hi.txt: hi.txt
   - apps: src/archives

#OPKG defined vars: OPKG_NAME, OPKG_REL_NUM, OPKG_ACTION
vars:
   - MYAPP_ENV1: "sample env"
   - DB_NAME: myapp_db
   - DC_NAME: "{{ DC_NAME }}"

#Deployment Playbook
pre_deploy:
 - echo Going to deploy {{ OPKG_NAME }} v{{ OPKG_REL_NUM }}
 - mkdir -p /etc/myapp

#target_path: source_path
#target path is relative to OPKG_DEPLOY_DIR
#source paths is relative to OPKG_STAGE_DIR
targets:
   - apps: apps
   - greeting: greeting

#The target paths are relative to OPKG_DEPLOY_DIR unless absolute path is specified.
templates:
   - greeting/hi.txt

#The target paths are relative to OPKG_DEPLOY_DIR unless absolute path is specified.
replaces:
   apps/conf/server.conf:
      - HTTP_PORT=80: HTTP_PORT=9090

#The target paths are relative to OPKG_DEPLOY_DIR unless absolute path is specified.
symlinks:
   - /etc/myapp/apps: apps

#The target paths are relative to OPKG_DEPLOY_DIR unless absolute path is specified.
#Format: PATH: chown_input chmod_input
permissions:
   - apps: root:root 0444

#Paths have to be fully qualified with OPKG_INSTALL_ROOT, OPKG_DEPLOY_DIR etc, if needed.
post_deploy:
   - cat {{ OPKG_DEPLOY_DIR }}/greeting/hi.txt

rollback:

#Run-time
#Scripts or bash commands can be specified as a steps for following runtime
#actions, start, stop  and rollback. restart will run both stop and start in succession.
#Fully qualify scripts with OPKG_INSTALL_ROOT, OPKG_DEPLOY_DIR etc if needed.
start:
stop:
reload:
```

The package manifest follows the YAML format as the extension of the file indicates. There is only one attribute, name of the package,  required in the manifest file. However, to use a package for anything useful, you may have to use multiple options that direct the pakaging of application code and its deployment.

There are 3 groups of options that you can specifiy in an opkg manifest that are related to: packaging application code, installing the code and maintaining state of the application. 

An opkg package also supports template variables in manifests, bounded by "{{ }}" - a feature that can be used to install a package to multiple environments with varied configurations. 

