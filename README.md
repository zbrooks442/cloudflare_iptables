# cloudflare_script

cloudflare.py is a simple script to update iptables to allow new cloudflare CDN edge networks or remove edge networks. This script is executed on standalone public facing docker host that leverages iptables for firewalling.

The script is executed as root on the docker vm. It is executed on a scheduled basis using cron. The cloudflare.cron file is the output from the /var/spool/cron/root file that is editted by crontab -e.