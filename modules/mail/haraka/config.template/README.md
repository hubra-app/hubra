# Haraka Config

This folder is copied into the Haraka image at `/etc/haraka/config` during build.

Included starter files:

- `me`: primary server hostname
- `host_list`: accepted local recipient domains for `rcpt_to.in_host_list`
- `plugins`: minimal plugin chain for inbound handling
- `smtp_forward.ini`: forwards accepted mail to `mailserver:25`
- `tls.ini`: reads certs from the Let's Encrypt volume mount

Adjust these files as needed for anti-spam plugins and policy checks.
