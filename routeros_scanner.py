import routeros_api
import routeros_api.exceptions
from datetime import datetime
from ipaddress import ip_address, ip_network

from scanner import AbstractScanner


class RouterOsScanner(AbstractScanner):
    def __init__(self, interval, address, username, password, ssl_context=None, subnet_filters=None):
        super().__init__(interval)

        self.api = None
        self._address = address
        self._username = username
        self._password = password
        self._ssl_context = ssl_context
        self.connect_api()

        if not subnet_filters:
            self.subnet_filters = None
        else:
            self.subnet_filters = [ip_network(sf) for sf in subnet_filters]

    def connect_api(self):
        connection = routeros_api.RouterOsApiPool(
            host=self._address,
            username=self._username,
            password=self._password,
            use_ssl=True,
            ssl_context=self._ssl_context,
            plaintext_login=True,
        )
        self.api = connection.get_api()

    def scan(self):
        if self.api is None:
            self.connect_api()

        for attempt in range(3):
            try:
                hosts = self.api.get_resource('/ip/arp').get(complete='true')
                break
            except routeros_api.exceptions.RouterOsApiConnectionError:
                self.connect_api()
        else:
            raise RuntimeError("Can't use established api connection")

        self.last_scan = timestamp = datetime.now()
        for host in hosts:
            if self.subnet_filters:
                addr = ip_address(host['address'])
                if not any(addr in subnet for subnet in self.subnet_filters):
                    continue
            self.add_scan_result(host['mac-address'], host['address'], timestamp)
