import routeros_api
from datetime import datetime
from ipaddress import ip_address, ip_network

from scanner import AbstractScanner


class RouterOsScanner(AbstractScanner):
    def __init__(self, interval, address, username, password, ssl_context=None, subnet_filters=None):
        super().__init__(interval)

        connection = routeros_api.RouterOsApiPool(
            address, username=username, password=password, use_ssl=True, ssl_context=ssl_context, plaintext_login=True
        )
        self.api = connection.get_api()

        if not subnet_filters:
            self.subnet_filters = None
        else:
            self.subnet_filters = [ip_network(sf) for sf in subnet_filters]

    def scan(self):
        hosts = self.api.get_resource('/ip/arp').get(complete='true')
        self.last_scan = timestamp = datetime.now()
        for host in hosts:
            if self.subnet_filters:
                addr = ip_address(host['address'])
                if not any(addr in subnet for subnet in self.subnet_filters):
                    print('skipping %s' % host['address'])
                    continue
            print(host)
            self.add_scan_result(host['mac-address'], host['address'], timestamp)
