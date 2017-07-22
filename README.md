# Open Package Project

Open Package is an open-source project to develop a platform independant packaging and deployment tool.

It is similar to rpm or Debian packaging, but, not tied to any specific Operating System or development environments like npm or J2EE.

# Basic Features 

Using Open Package tool a package can be created using the following command:

```$ opkg create --pkg=myapp```

The above command will create a tarball myapp.tgz based on the meta-data defined in myapp.yml. In myapp.yml, you can specify the content of myapp.tgz, and, how myapp is installed on a target host.

A package is installed on the local system as in the following example:

```$ opkg install --pkg=/path/to/myapp.tgz```

When installing a package the following syntax can be used as well:

```$ opkg install --pkg=myapp```

In the above case, package tool will try to download myapp.tgz from a remote repository or shared drive based on the local repository configuration. We will see how a repository can be setup for maintaining opkg packages, in the latter sections.

# Advantages of Open Package

These are the general advtantages of using Open Project in place rpm or similar packaging tools:
- extremely simple packaging system that uses an open archive format, tarball.
- opkg packages are flexible enough to be installed in environments with varied configuration.
- keep track of the state of package. If an app is encapsulated as a package with its lifecycle defined, opkg can manage that easily.

# Package Manifest

The package manifest follows the YAML format as the extension of the file indicates. There is only one attribute, name of the package,  required in the manifest file. However, to use a package for anything useful, you may have to use multiple options that direct the pakaging of application code and its deployment.

There are 5 groups of options that you can specifiy in an opkg manifest that are related to: 
- package meta data, 
- package dependencies,
- packaging application code, 
- installing the code and 
- maintaining state of the application. 

An opkg package also supports template variables in manifests, bounded by "{{ }}" - a feature that can be used to install a package to multiple environments with varied configurations.  

## Sample Package Manifest

Following is a sample package manifest with all the supported options used:

```
#Sample opkg manifest file 
--- 

#Core Configs 
name: myapp
rel_num: 1.2.3
type: package #values: package,patch,wrapper
platform: generic

depends:
 - baseapp 
#- another_app 1.0.0
#- yet_another_app 1.1.1-2.3.0

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

## Package Meta-data
### name
Name of the package, required.

### rel_num
Release number of the package, optional. Default dev.

### type
Type of package. Allowed values: package,patch,wrapper, where:
- package: a full-fledged package, default.
- patch: A package name is specified next to this separated by a space. A patch package will try to make changes in the latest installation of package specified next to it.
- wrapper: A wrapper package will not have any content (specified by files option) and created mainly for "packaging" a deployment playbook that uses scripts and other package systems like rpm, and, recording a deployment on a target host.
platform: generic (default)

## Dependencies

### depends
Dependencies to other packages can be specified in the following format:
```
package_name [rel_num_info]
```
where rel_num_info is optional and it could be:
- rel_num: Any release beginning this version and above would be met as dependency requirement.
- rel_num_start - rel_num_end: The dependency will be checked for within this retricted range. 

### conflicts

As in the case of "depends" option, a conflicting package can be specified with optional release number or release range restrictions.

## Package Code

A package can contain files and variables.

### files

Both files and directories can be specified as content of the package. 
```
path/to/file/in/package: /path/to/file/on/local/system
```
The local relative paths are with respect to the location of the manifest file and in the package the relative paths are with respect to the root directory.

Examples:
```
files:
   - greeting/hi.txt: hi.txt
   - apps: src/archives
```
In the example above, 
- hi.txt which is located at the same directory as the package manifest is added to the package under the directory greeting. Note that the file name could be added with a different name too.
- the src/archives folder on the local system will be added the the package as directory apps.

If absolute paths are specified as source locations they are treated as such. Absolute paths in package will not make much sense as the top directory is always root directory of the package.

### vars

There are 2 groups of variables, system defined and externally provided. Both types of variables are meant to be used during deployment and maintenance of corresponding package.

These variables are available in the runtime environment so deployment and runtime maintenance scripts can use them. The templates used in a package will be resolved with these variables and it is a powerful tool to configure an application environment. We will see how it is done in the "templates" section.

#### System Defined Variables
The package tool makes these variables available for templates and scripts:
- OPKG_NAME: Name of package being deployed or run.
- OPKG_REL_NUM: Release number of the package being deployed or run.
- OPKG_ACTION: The action being done using package tool, like install, start etc.
- OPKG_INSTALL_STEP: Package installation process has multiple steps like pre_deploy,targets,symlinks,post_deploy etc. These options correspond to the deployment options specified in the manifest.
- OPKG_DEPLOY_DIR: This is the common location setup for a deployment session. The package is deployed under OPKG_DEPLOY_DIR/OPKG_NAME.

#### Externally Provided Variables
To make these variable available to templates and scripts, they must be defined in the manifest as in the following example:
```
vars:
   - MYAPP_ENV1: "sample env"
   - DB_NAME: {{ myapp_db }}
   - DC_NAME: "{{ dc_name }}"
```
Using --extra-vars option, values for these variables can be provided during deployment and they are resolved at that time. During runtime, like start and stop of a package, these variables will be available in the environment for the scripts to use with the values set during deployment. 

The values to these variables can be provided from the command-line using the following syntax, each hash-value pair delimited by a comma:
```
--extra-vars=myapp_db=westcoast,dc_name=us-west
```

## Deploy Code

## Maintain Runtime State

# Install Open Package Tool

# Advanced Open Package Features

# How to Contribute to Open Package Project
