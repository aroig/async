=====
async
=====

async is a python script to manage synchronization across different hosts, or
backup media. Some of its features include:

- synchronization method configurable per directory. Right now directories can be synced using: unison, rsync, git, git-annex.
- can start and stop ec2 instances
- can mount encrypted partitions before the sync and umont them afterwards
- can run scripts before or after syncs, and during directory initialization


Dependencies
------------
- python2
- python2-dateutil
- python2-boto: for amazon ec2 interaction
- python2-systemd: for startup notification when running async in a systemd
  service
- openssh
- git-annex
- unison
- rsync


TODO
----
- write a man page
- write some sample configuration
- write shell completion files
