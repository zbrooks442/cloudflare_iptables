import os
import subprocess
import logging
import datetime
import requests

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")


def setup_logger(name, log_file, level=logging.INFO, stdout=False):
    """Function setup as many loggers as you want"""

    handler = logging.FileHandler(log_file)
    handler.setFormatter(logFormatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    if stdout:
        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormatter)
        logger.addHandler(consoleHandler)

    return logger


class CloudFlare(object):
    """
    CloudFlare:
    cf_file = File containing cloudflare networks from last poll
    nginx_ip = ip of front-end nginx container
    f_nets = Networks read from cf_file
    n_nets = Networks read from cloudflare API call
    """

    def __init__(self, cf_file, nginx_ip):
        self.cf_file = cf_file
        self.nginx_ip = nginx_ip
        self.f_nets = []
        self.n_nets = []
        self.ifname = None
        self.emailLogger = setup_logger('emailLogger', log_file='/var/log/cloudflare.log', stdout=True)
        self.infoLogger = setup_logger('infoLogger', log_file='/var/log/cloudflare.log')

    @staticmethod
    def missing_nets(nets1, nets2):
        """
        :param nets1:
        :param nets2:
        :return: Returns nets from nets1 that are not in nets2
        """
        nets = []
        for net in nets1:
            if net not in nets2:
                nets.append(net)
        return nets

    def call_cloudflare(self):
        """
        :return: Returns response from cloudflare containing current CDN networks
        """
        url = "https://www.cloudflare.com/ips-v4"
        response = requests.get(url)
        if response.status_code == 200:
            self.n_nets = response.text.split()
        else:
            raise RuntimeError('Recieved response code {}'.format(response.status_code))

    def open_nets(self):
        """
        Simple method to open file containing CloudFlare networks from previous poll
        """
        with open(self.cf_file, mode='rt', encoding='utf-8') as netsfile:
            self.f_nets = netsfile.read().split()

    def write_nets(self, new_nets):
        """
        Simple method to save file containing CloudFlare networks from recent poll
        :param new_nets: Networks from current cloudflare poll
        """
        with open(self.cf_file, mode='w', encoding='utf-8') as netsfile:
            netsfile.write("\n".join(new_nets))

    def get_if_name(self):
        """
        Simple method that saves the egress bridge if-name of the nginx container using in the Iptables rules
        """
        command = "ip route get {}".format(self.nginx_ip)
        self.ifname = str(subprocess.check_output(command.split())).split()[2]

    def add_rules(self, nets):
        """
        Method uses to iterate through new CloudFlare networks and add required iptables rules
        :param nets: list containing networks using in new iptables update
        """
        if nets:
            for net in nets:
                command = ("iptables -I DOCKER-USER -o {0} -p tcp -m tcp --match multiport --dports 80,443 -s "
                           "{1} -j ACCEPT").format(self.ifname, net)
                code = os.system(("iptables -I DOCKER-USER -o {0} -p tcp -m tcp --match multiport --dports 80,443 -s "
                                  "{1} -j ACCEPT").format(self.ifname, net))

                if code == 0:
                    self.emailLogger.info('iptables update completed successfully, command=\'{}\''.format(command))
                else:
                    self.emailLogger.error('iptables update failed, update = \'{}\''.format(command))
            commands = ["cp /etc/sysconfig/iptables /root/iptables_backup/iptables_{}.bak".format(str(
                datetime.datetime.now()).split()[0]), "iptables-save > /etc/sysconfig/iptables"]
            for command in commands:
                code = os.system(command)
                if code == 0:
                    self.emailLogger.info('iptables command executed, command=\'{}\''.format(command))
                else:
                    self.emailLogger.error('iptables command failed, command = \'{}\''.format(command))

    def main(self):
        """
        Method used to start
        """
        self.infoLogger.info('cloudflare.py executed')
        self.open_nets()
        self.call_cloudflare()
        self.get_if_name()
        add_nets = self.missing_nets(self.n_nets, self.f_nets)
        self.add_rules(add_nets)
        rm_nets = self.missing_nets(self.f_nets, self.n_nets)
        if rm_nets:
            self.emailLogger.warning('Cloud Flare reporting networks {} no longer part of CDN network'.format(rm_nets))
        self.write_nets(self.n_nets)
        self.infoLogger.info('cloudflare.py completed')


if __name__ == '__main__':
    CloudFlare(cf_file="cf_nets.txt", nginx_ip="172.28.0.254").main()
