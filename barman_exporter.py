#!/usr/bin/env python3
import sys
import time
import logging
import argparse
import prometheus_client
from prometheus_client import core
from barman import cli
from barman import output
from barman.infofile import BackupInfo
from barman.server import CheckOutputStrategy


class PythonOutputWriter(output.ConsoleOutputWriter):

    def close(self):
        if hasattr(self, 'results'):
            return self.results

    def init_list_backup(self, server_name, minimal=False):
        self.results = dict(
            status_done=[],
            status_failed=[]
        )

    def result_list_backup(self, backup_info, backup_size, wal_size,
                           retention_status):
        if backup_info.status in BackupInfo.STATUS_COPY_DONE:
            self.results['status_done'].append(dict(
                server_name=backup_info.server_name,
                backup_id=backup_info.backup_id,
                end_time=backup_info.end_time.timestamp(),
                size=backup_size,
                wal_size=wal_size))
        else:
            self.results['status_failed'].append(dict(
                server_name=backup_info.server_name,
                backup_id=backup_info.backup_id))

    def init_check(self, server_name, active=True):
        self.results = {}

    def result_check(self, server_name, check, status, hint=None):
        check = check.lower() \
            .replace(' ', '_') \
            .replace('-', '_') \
            .replace('.', '')

        self.results[check] = 1 if status else 0


class BarmanCollector(object):

    def __init__(self, args):
        cli.global_config(args)

        # Remove logging handlers to avoid opening
        # barman.log over and over again
        logging.disable(logging.CRITICAL)
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        self.servers = cli.get_server_list(args)
        self.server_names = self.servers.keys()

    def list_backup(self, server_name):
        output.init('list_backup', server_name)

        server = self.servers[server_name]
        server.list_backups()
        server.close()

        results = output._writer.close()
        return results

    def check(self, server_name, check_strategy=CheckOutputStrategy()):
        output.init('check', server_name)

        server = self.servers[server_name]
        server.check_archive(check_strategy)

        if not server.passive_node:
            server.check_postgres(check_strategy)

        server.check_directories(check_strategy)
        server.check_retention_policy_settings(check_strategy)
        server.check_backup_validity(check_strategy)
        server.backup_manager.check(check_strategy)
        server.check_configuration(check_strategy)

        for archiver in server.archivers:
            archiver.check(check_strategy)

        server.check_archiver_errors(check_strategy)
        server.close()

        results = output._writer.close()
        return results

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

        for server_name in self.server_names:
            backups = self.list_backup(server_name)

            collectors['barman_backups_total'].add_metric(
                [server_name],
                len(backups['status_done']) + len(backups['status_failed']))

            collectors['barman_backups_failed'].add_metric(
                [server_name], len(backups['status_failed']))

            if backups['status_done']:
                collectors['barman_last_backup'].add_metric(
                    [server_name], backups['status_done'][0]['end_time'])

                collectors['barman_first_backup'].add_metric(
                        [server_name], backups['status_done'][-1]['end_time'])

            for number, backup in enumerate(backups['status_done'], 1):
                collectors['barman_backups_size'].add_metric(
                    [server_name, str(number)], backup['size'])

                collectors['barman_backups_wal_size'].add_metric(
                    [server_name, str(number)], backup['wal_size'])

            check = self.check(server_name)
            for check_name, check_value in check.items():
                collectors['barman_up'].add_metric(
                    [server_name, check_name], check_value)

        for collector in collectors.values():
            yield collector


class BarmanArgs():

    def __init__(self, servers):
        output.set_output_writer(PythonOutputWriter())
        self.quiet = output._writer
        self.debug = output._writer
        self.format = output._writer
        self.color = 'auto'
        self.minimal = False
        self.server_name = servers


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

    barman_args = BarmanArgs(args.servers)
    collector = BarmanCollector(barman_args)

    core.REGISTRY.register(collector)
    prometheus_client.start_http_server(int(port), addr)

    while True:
        time.sleep(1)
