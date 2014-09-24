TODO
====

* Fix race condition with openssh socket Right now there is a race, since
  async's openssh does not know about the control socket when it is configured
  in `~/.ssh/config` This means that alive() can't check for this socket to make
  sure next ssh calls will use it. I don't know how to fix it, yet.
  - We need a reliable way to check whether the ssh connection is alive!
  - Alternatively, a way to guess the connection socket when establishing the connection
