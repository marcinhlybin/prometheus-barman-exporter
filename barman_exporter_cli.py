#!/usr/bin/env python3
import sys
import argparse
import time
from sh import barman as barman_cli
from datetime import datetime
import prometheus_client
from prometheus_client import core


class Barman:

    def servers(self):
        return barman_cli('list-server', '--minimal').split()

    def server_status(self, server_name):
        status = barman_cli('status', server_name)
        status_dict = self.parse_output(status)
        return status_dict

    def server_check(self, server_name):
        check = barman_cli('check', server_name, _ok_code=[0, 1])
        check = self.parse_output(check)
        check_dict = {}
        for key, value in check.items():
            value = 1 if value.startswith("OK") else 0
            check_dict[key] = value

        return check_dict

    def list_backup(self, server_name):
        backup_list = barman_cli('list-backup', server_name)
        backups_done = []
        backups_failed = []
        for backup_line in backup_list.split("\n")[:-1]:
            backup = {}
            backup['server'] = server_name
            try:
                server_name_and_ts, date, size, wal_size = \
                    backup_line.split("-")
                backup['date'] = date.strip()
                backup['size'] = size.split(":")[1].strip()
                backup['wal_size'] = wal_size.split(":")[1].strip()
                backup['status'] = "done"
                backups_done.append(backup)
            except ValueError:
                server_name_and_ts, status = backup_line.split("-")
                backup['status'] = status.lower()
                backups_failed.append(backup)

        return backups_done, backups_failed

    @staticmethod
    def parse_output(output):
        output_dict = {}
        for line in output.split("\n")[1:-1]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower() \
                .replace(".", "") \
                .replace(" ", "_") \
                .replace("-", "_")
            output_dict[key] = value.strip()

        return output_dict


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

            if server_status['first_available_backup']:
                first_backup = datetime.strptime(
                    server_status['first_available_backup'], "%Y%m%dT%H%M%S")
                collectors['barman_first_backup'].add_metric(
                    [server_name], first_backup.strftime("%s"))

            if server_status['last_available_backup']:
                last_backup = datetime.strptime(
                    server_status['last_available_backup'], "%Y%m%dT%H%M%S")
                collectors['barman_last_backup'].add_metric(
                    [server_name], last_backup.strftime("%s"))

            backups_done, backups_failed = barman.list_backup(server_name)

            collectors['barman_backups_total'].add_metric(
                [server_name], len(backups_done) + len(backups_failed))

            collectors['barman_backups_failed'].add_metric(
                [server_name], len(backups_failed))

            for number, backup in enumerate(backups_done):
                number = str(number + 1)

                collectors['barman_backups_size'].add_metric(
                    [server_name, number],
                    self.pretty_size_to_bytes(backup['size']))

                collectors['barman_backups_wal_size'].add_metric(
                    [server_name, number],
                    self.pretty_size_to_bytes(backup['wal_size']))

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
