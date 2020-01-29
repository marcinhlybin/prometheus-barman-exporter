#!/usr/bin/env python3
import sys
import argparse
import time
import json
from sh import barman as barman_cli
from datetime import datetime
import prometheus_client
from prometheus_client import core


class Barman:

    @staticmethod
    def cli(*args, **kwargs):
        output = barman_cli('-f', 'json', *args, **kwargs)
        output = json.loads(str(output))
        return output

    @classmethod
    def version(cls):
        version = barman_cli('-v').split()
        return version[0]

    def servers(self):
        servers = self.cli('list-server')
        return list(servers.keys())

    def server_status(self, server_name):
        status = self.cli('status', server_name)
        status = {k: v['message'] for k, v in status[server_name].items()}
        return status

    def server_check(self, server_name):
        check = self.cli('check', server_name, _ok_code=[0, 1])
        check = {k: 1 if v['status'] == "OK" else 0 for k,
                 v in check[server_name].items()}
        return check

    def list_backup(self, server_name):
        backups = self.cli('list-backup', server_name)
        backups_done = [backup for backup in backups[server_name]
                        if backup['status'] == 'DONE']
        backups_failed = [
            backup for backup in backups[server_name] if backup['status'] != 'DONE']
        return backups_done, backups_failed

    def show_backup(self, server_name, backup_id):
        backup = self.cli('show-backup', server_name, backup_id)
        return backup[server_name]


class BarmanCollector:

    def __init__(self, servers):
        self.servers = servers

    @staticmethod
    def pretty_size_to_bytes(size, suffixes="KMGTPEZY"):
        size, suffix = size.split()
        unit = 1024 if "iB" in suffix else 1000
        exponent = suffixes.find(suffix[0].upper()) + 1
        size_bytes = float(size) * (unit ** exponent)
        return int(size_bytes)

    def collect(self):
        collectors = dict(
            barman_backups_size=core.GaugeMetricFamily(
                'barman_backups_size', "Size of available backups",
                labels=['server', 'number']),
            barman_backups_wal_size=core.GaugeMetricFamily(
                'barman_backups_wal_size', "WAL size of available backups",
                labels=['server', 'number']),
            barman_backups_total=core.GaugeMetricFamily(
                "barman_backups_total", "Total number of backups",
                labels=["server"]),
            barman_backups_failed=core.GaugeMetricFamily(
                "barman_backups_failed", "Number of failed backups",
                labels=["server"]),
            barman_last_backup=core.GaugeMetricFamily(
                "barman_last_backup", "Last successful backup timestamp",
                labels=["server"]),
            barman_last_backup_copy_time=core.GaugeMetricFamily(
                "barman_last_backup_copy_time", "Last successful backup copy time",
                labels=["server"]),
            barman_first_backup=core.GaugeMetricFamily(
                "barman_first_backup", "First successful backup timestamp",
                labels=["server"]),
            barman_up=core.GaugeMetricFamily(
                "barman_up", "Barman status checks",
                labels=["server", "check"])
        )

        barman = Barman()

        if self.servers[0] == "all":
            self.servers = barman.servers()

        for server_name in self.servers:
            server_status = barman.server_status(server_name)

            if server_status['first_backup']:
                first_backup = datetime.strptime(
                    server_status['first_backup'], "%Y%m%dT%H%M%S")
                collectors['barman_first_backup'].add_metric(
                    [server_name], first_backup.strftime("%s"))

            if server_status['last_backup']:
                last_backup = datetime.strptime(
                    server_status['last_backup'], "%Y%m%dT%H%M%S")
                collectors['barman_last_backup'].add_metric(
                    [server_name], last_backup.strftime("%s"))

            backups_done, backups_failed = barman.list_backup(server_name)

            collectors['barman_backups_total'].add_metric(
                [server_name], len(backups_done) + len(backups_failed))

            collectors['barman_backups_failed'].add_metric(
                [server_name], len(backups_failed))

            if len(backups_done) > 0:
                last_backup = barman.show_backup(
                    server_name, backups_done[0]['backup_id'])
                last_backup_copy_time = last_backup['base_backup_information']['copy_time_seconds']

                collectors['barman_last_backup_copy_time'].add_metric(
                    [server_name], last_backup_copy_time)

            for number, backup in enumerate(backups_done, 1):
                collectors['barman_backups_size'].add_metric(
                    [server_name, str(number)], backup['size_bytes'])

                collectors['barman_backups_wal_size'].add_metric(
                    [server_name, str(number)], backup['wal_size_bytes'])

            server_check = barman.server_check(server_name)
            for check_name, check_value in server_check.items():
                collectors['barman_up'].add_metric(
                    [server_name, check_name], check_value)

        for collector in collectors.values():
            yield collector


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Barman exporter",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-l', '--web-listen-address',
                        metavar="HOST:PORT",
                        default="127.0.0.1:9780",
                        help="Address to listen on")
    parser.add_argument('servers', nargs="*", default=['all'],
                        help="Space separated list of "
                             "backed up servers to check")
    args = parser.parse_args()

    barman_version = tuple(int(v) for v in Barman.version().split('.'))
    if barman_version < (2, 9):
        print("ERROR: Barman version 2.9+ required")
        sys.exit(1)

    try:
        addr, port = args.web_listen_address.split(":")
    except ValueError:
        print("Incorrect '--web.listen-address' value: '{}'.".format(
              args.web_listen_address), "Use HOST:PORT.")
        sys.exit(1)

    core.REGISTRY.register(BarmanCollector(args.servers))
    prometheus_client.start_http_server(int(port), addr)
    while True:
        time.sleep(1)
