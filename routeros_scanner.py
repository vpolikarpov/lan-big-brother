import routeros_api
from datetime import datetime

from scanner import AbstractScanner


class RouterOsScanner(AbstractScanner):
    def __init__(self, interval, address, username, password, ssl_context=None):
        super().__init__(interval)

        connection = routeros_api.RouterOsApiPool(
            address, username=username, password=password, use_ssl=True, ssl_context=ssl_context, plaintext_login=True
        )
        self.api = connection.get_api()

    def scan(self):
        leases = self.api.get_resource('/ip/arp').get()
        self.last_scan = timestamp = datetime.now()
        for lease in leases:
            self.add_scan_result(lease['mac-address'], lease['address'], timestamp)
