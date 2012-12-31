#!/usr/bin/python2
# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, Abdó Roig-Maranges <abdo.roig@upc.edu>'
__docformat__ = 'restructuredtext en'

from optparse import OptionParser
import re
import os
import time
import subprocess
import sys
import paramiko
import glob
import shutil

from miscelania import execute           # Personal lib

import cali.calibredb as calibredb
import classifier

hypathia_host="hypathia"
hypathia_ssh_user="root"
hypathia_local_dir=os.path.expanduser("~/Devices/hypathia")
hypathia_local_sdcard=os.path.join(hypathia_local_dir, "sdcard")
hypathia_boox_subdir="zzz-Boox"


hypathia_ssh_args = ' '.join(['-o UserKnownHostsFile=/dev/null',
                              '-o StrictHostKeyChecking=no'])

hypathia_local_sd_mountpoint = '/media/hypathia'
hypathia_device_sd_mountpoint = "/media/sd"

hypathia_query = 'tag:"=boox"'

# This is hackish. I need a better way to do this ...
#def get_calibre_files():
#  """Gets the list of files to sync with hypathia."""
#  raw_formats = execute(['calibredb', 'list', '-w', '5000', '-f', 'formats', '-s', calibre_search])
#  raw_boox = execute(['calibredb', 'list', '-w', '5000', '-f', '*boox_folder', '-s', calibre_search])
#  print(raw_formats)



def hypathia_status():
  """Pings hypathia to check if on-line."""
  # TODO
  pass



def cmd_ssh(cmd = None):

  # TODO: Check status of hypathia
  if True:               # if on-line
    if cmd == None:
      subprocess.call('ssh %s %s@%s' % (hypathia_ssh_args, hypathia_ssh_user,  hypathia_host),
                      shell=True)
    else:
      # TODO: Execute a command via paramiko
      pass


def cmd_sshmount():
  """Mounts skynet's data as sshfs"""

  # TODO: Check if hypathia is on-line

  subprocess.call('sshfs %s@%s:%s %s %s -o idmap=user' %
                  (hypathia_ssh_user, hypathia_host, hypathia_device_sd_mountpoint,
                  hypathia_local_sd_mountpoint, hypathia_ssh_args), shell=True)


def cmd_sshumount():
  """Umounts the sshfs"""
  subprocess.call("fusermount -u %s" % local_ssh_mountpoint, shell=True)
  


def cmd_status():
  """Prints the status of hypathia"""
  pass



def hypathia_sanitize_filename(title):
  title = title.replace(':', '')
  title = title.replace(';', '')
  title = title.replace('?', '')
  title = title.replace('!', '')
  return title


def hypathia_author(authors):
  if len(authors) > 0:
    auth = authors[0]
    auth = auth.replace('.', '')    
    return auth
  else:
    return "unknown"


def ensure_trailing_bar(path):
  if path[-1] != "/":
    return path + "/"
  else:
    return path
  

def cmd_sync(mode="sdcard"):
  """Syncs hypathia books mode can be sdcard or ssh"""

  # Clean the sdcard directory  
  for f in glob.glob(os.path.join(hypathia_local_sdcard, "*")):
    if os.path.isdir(f) and not os.path.islink(f): shutil.rmtree(f)
    else:                                          os.remove(f)

  # Link the zzz-Boox
  os.symlink(os.path.join(hypathia_local_dir, hypathia_boox_subdir),
             os.path.join(hypathia_local_sdcard, hypathia_boox_subdir))

  doclist = calibredb.query(hypathia_query)
  print("Going to sync %d documents to hypathia" % len(doclist))

  # Link documents
  for doc in doclist:
    fmt, srcpath = calibredb.get_docfile(doc)

    cl = classifier.subject(doc['tags'])

    tgtdir = os.path.join(hypathia_local_sdcard,
                          classifier.hypathia_dir(cl, doc['tags']),
                          hypathia_author(doc['authors']))

    fname = hypathia_sanitize_filename(os.path.basename(srcpath))

    if not os.path.isdir(tgtdir): os.makedirs(tgtdir)
    os.symlink(srcpath, os.path.join(tgtdir, fname))

  if mode == "sdcard":
    if os.path.isdir(os.path.join(hypathia_local_sd_mountpoint, hypathia_boox_subdir)):
      subprocess.call(["rsync", "-avz", "-L", "--delete",
                       ensure_trailing_bar(hypathia_local_sdcard),
                       ensure_trailing_bar(hypathia_local_sd_mountpoint)])
    else:
      raise Exception("Target medium not mounted.")
  else:
    print("TODO: sync over ssh not implemented")
    # TODO: mount and sync.
  
  




def main():
  usage = """usage: %prog [options] <cmd> <args>

Commands:

  sshmount:     Mount hypathia's SD card as sshfs.

  sshumount:    Umount the sshfs.

  status:       print the status of hypathia.

  sync:         Syncs the contents of the SD card with calibre (NOT IMPLEMENTED).

  ssh:          Opens a ssh connection with hypathia.
"""

  parser = OptionParser(usage=usage)

  parser.add_option("-b", "--batch", action="store_true", default=False, dest="batch", 
    help="Syncs non-conflicting differences and skips conflicts. Asks no questions.")


  (options, args) = parser.parse_args()

  if len(args) == 0:
    print("Need a command.")
    sys.exit()

  cmd = args[0]

  if cmd == "status":
    if len(args) == 1:
      cmd_status()
    else:
      print("Too many arguments for command status.")
    sys.exit()

  elif cmd == "sync":
    if len(args) == 1:
      cmd_sync()
    else:
      print("Too many arguments for sync.")
    sys.exit()

  elif cmd == "ssh":
    if len(args) == 1:
      cmd_ssh()
    elif len(args) == 2:
      cmd_ssh(args[1])
    else:
      print("Too many arguments for ssh.")
    sys.exit()

  elif cmd == "sshmount":
    if len(args) == 1:
      cmd_sshmount()
    else:
      print("Too many arguments for command sshmount.")
    sys.exit()

  elif cmd == "sshumount":
    if len(args) == 1:
      cmd_sshumount()
    else:
      print("Too many arguments for command sshumount.")
    sys.exit()   

  else:
    print("Unknown command %s" % cmd)
    sys.exit()


if __name__ == "__main__":
  main()

