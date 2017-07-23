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
- OPKG_ROOT_DIR: The directory where package tool specific files and meta data are maintained. Default: /etc/opkg
- OPKG_NAME: Name of package being deployed or run.
- OPKG_REL_NUM: Release number of the package being deployed or run.
- OPKG_ACTION: The action being done using package tool, like install, start etc.
- OPKG_INSTALL_STEP: Package installation process has multiple steps like pre_deploy,targets,symlinks,post_deploy etc. These options correspond to the deployment options specified in the manifest.
- OPKG_STAGE_DIR: The location where a package is extracted prior to starting the deployment steps, and, it will be available begining the step "targets".
- OPKG_INSTALL_ROOT: The root directory under which package installations are done on the target system.
- OPKG_DEPLOY_TS: A timestamp used to track a deployment session across packages.
- OPKG_DEPLOY_DIR: The package is deployed under this directory and it is OPKG_INSTALL_ROOT/OPKG_DEPLOY_TS/pkg_name.
- OPKG_META_LATEST: Content of existing Latest.meta for the package.
- OPKG_META_PREVIOUS: Content of existing Previous.meta for the package.

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

Multiple packages can be specified in a deployment session as below:

```
$ opkg deploy --pkg=pkg1-latest,pkg2-latest,pkg3-1.2.3
```
In this case, latest versions of pk1 and pkg2 and pkg3-1.2.3 will be deployed. 

All the packages deployed during the same session will be installed under a common root directory OPKG_INSTALL_ROOT/OPKG_DEPLOY_TS. The OPKG_DEPLOY_DIR will be OPKG_INSTALL_ROOT/OPKG_DEPLOY_TS/pkg_name, under which, a package is installed.

Installation of a package is done in multiple steps and those steps are described in the following sections in the same order they are executed as tasks in a playbook.

A host can end up having multiple installations of the same package from multiple deployments. The package installation data are stored under OPKG_DIR/meta/pkg_name, and, to keep track of installations, 2 meta files, Latest.meta and Previous.meta, are maintained under OPKG_DIR/meta/pkg_name for each package.

Multiple installations on a host can be pruned to 2, the latest and the previous, using following command:

```
$ opkg clean [--count=COUNT]
```
The count option can be specified to remove only the specified number of installations. Useful only if you like to keep more than 2 installations around. The best practice is only to maintain only 2 installations.

The deployment history on a host can be checked using the command:

```
$ opkg history [--count=COUNT]
```
The count option can be used to list only the specified number of latest entries from the history log.

### pre_deploy
Multiple steps can be specified pre-installation steps as below:

```
pre_deploy:
 - echo Going to deploy {{ OPKG_NAME }} v{{ OPKG_REL_NUM }}
 - mkdir -p /etc/myapp
 ```
 The package is extracted and the variables specified in the manifest are resolved at this stage. But rest of the installation process is not started so a pre-deploy step should not rely on scripts the package with template variables and tokens.
 
### targets
Using this option, files and directories in the package can be copied anywhere on the target system.

```
targets:
   - apps: apps
   - greeting: greeting
```
The key in this specification is the target location and the value is the corresponding source in the package. Normally, a relative path is specified for target and that will translate to OPKG_DEPLOY_DIR/target_path.

### templates

This is a powerful option to make environment specific changes to the generic application configuration files maintained source code control system, as in the following example:
```
templates:
   - greeting/hi.txt
   - apps/conf
```
The paths are relative to OPKG_DEPLOY_DIR unless an absolute path is specified. If a file is specified, opkg will look at that file for template variables specified in the format {{ var_name }}. If found, {{ var_name }} is replaced with related hash value. If the hash value is not available, package tool will throw error.

If a directory is specified, all the files in that directory will be checked for template variables. This is not recursive and so sub-directories have to be specified, if needed.

As a best practice, configuration files with template variables must be limited to few directories and files for simpler handling and minimizing deployment errors.

### replaces

This is another available to configure applications for a specific environment. While "templates" option rely on template variables that are enclosed with "{{ }}" in a file and such instrumentations will be possible only in your own applications. If some change has to be done in a third-party application, for example Tomcat Server that runs your application war file, then you have to use this search and replace option.

```
replaces:
   apps/conf/server.conf:
      - HTTP_PORT=80: HTTP_PORT=9090
```
Using this option, multiple files or directories can be specified in which tokens have to be replaced with values provided from the manifest. In the example, in OPKG_DEPLOY_DIR/apps/conf/server.conf, every occurance of "HTTP_PORT=80" will be replaced with "HTTP_PORT=9090".

### symlinks

This option is used mainly to mark the latest deployment as the currently one. However, any number of symlinks can be defined on the target host using this option. 
```
symlinks:
   - /etc/myapp/apps: apps
```
The hash key in this specification is the symlink and the hash value is the source. The package tool doesn't make any validation checks on these paths and it's up to the designer of the package to specify appropriate paths. The package tool will try to create those as part of this installation step.

### permissions

The permission settings that can be implemented using chown and chmod commands can be set using this option.

```
permissions:
   - apps: root:root 0444
```
In the example above, the changes will be same as that done by the following commands:
```
$ chown -R root:root OPKG_DEPLOY_DIR/apps
$ chmod -R 0444 OPKG_DEPLOY_DIR/apps
```
### post_deploy
Multiple post-deployment steps can be specified under this section. The relative paths are not supported in this step and all the paths should be fully qualified as in the following example.

```
post_deploy:
   - cat {{ OPKG_DEPLOY_DIR }}/greeting/hi.txt
```
Keywords START,STOP and RESTART can also be specified. The package tool will try to execute the related runtime steps as the action.

### rollback

This step is not part of a deployment step but it can be used to rollback a deployment to its previous version if a previous deployment exists.

The package designer is fully responsible for the steps that would reliably rollback a deployment. The package tool simply executed the commands listed under this section.

A rollback action cannot be rolled back. When rollback is executed successfully, package tool renames existing Previous.meta file to Latest.meta. To make the actual rollback, steps have to be provided under this section and they can use the info available in OPKG_META_PREVIOUS and OPKG_META_LATEST.

Unless there is a compelling case for rollback, this option should not be used as part of settig up your production environment. The older versions of deployments are kept for debugging purposes. In an ideal scenario the deployment should be part of building an immutable runtime environment, and, instead of rolling back you should rebuild the application environment using versions of package that is known to have been working.

## Maintain Runtime State

Following are the actions that you can use from package tool to maintain running state of a package:
- start
- stop
- restart
- reload

```
$ opkg [start|stop|restart|reload] --pkg=myapp
```
When these actions are called, the variables specified under "vars" and the applicable system variables are loaded and made available to the scripts and commands specified under the corresponding section in the package manifest.

Though these actions are modelled after the Linux service actions, no attempt is made to keep track of which runtime action is last called and succeeded. For example, everytime "start" is called, all the scripts and commands specified under this section will be executed. So, it is up to the package designer to build robust scripts to start and stop applications, if these package options are for application maintenance.

# Installation

## Manual Steps

Until more automated methods are available, use these steps to install package tool on your system:

- Save openpkg.py from GitHub to /etc/opkg/bin/ on your local system.
- Install the command using these steps:
```
$ chmod +x /etc/opkg/bin/openpkg.py
$ ln -s /etc/opkg/bin/openpkg.py /usr/local/bin/opkg 
```
- The hashbang to python interpreter points to /usr/bin/python (usually a valid path on Mac platforms) in the GitHub version of opkg.py. If needed, update that to a valid path depending on where Python is installed on your system. Python 2.7 or higher is needed to run package tool.

- In /etc/opkg/conf/opkg.env, add the following config items and save:
```
[basic]
opkg_dir=/etc/opkg
deploy_history_file=deploy_history.log
install_root=/opt/apps
```

- To test the installation, check the version and you will see an output similar to the following:
```
$ opkg --version
opkg v0.1.0
```

# Advanced Features

# Use Cases

# How to Contribute
