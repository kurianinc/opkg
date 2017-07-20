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

## Package Manifest

Following is a sample package manifest with all the supported options used:



