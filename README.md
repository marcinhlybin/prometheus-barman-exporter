# Barman exporter for Prometheus

`barman_exporter.py` runs `barman` shell command with _experimental_ JSON output I added to Barman 2.9. JSON output may change in the future and break some of functionalities in the exporter.

By default barman exporter outputs metrics to stdout. If everything seems right you want to save it as textfile with `-f /var/lib/prometheus/node_exporter/barman.prom` and set up `node_exporter` to read from this path (`--collector.textfile.directory` option).

## Grafana dashboard

You can find basic grafana dashboard in `grafana-dashboard.json`. It is open for improvements.

![Grafana screenshot](grafana-screenshot.png?raw=true "Grafana screenshot")

## Usage

```
usage: barman_exporter.py [-h] [-f TEXTFILE_PATH] [-u USER] [-g GROUP]
                          [-m MODE]
                          [servers [servers ...]]

Barman exporter

positional arguments:
  servers               Space separated list of servers to check (default:
                        ['all'])

optional arguments:
  -h, --help            show this help message and exit
  -f TEXTFILE_PATH, --file TEXTFILE_PATH
                        Save output to textfile (default: None)
  -u USER, --user USER  Textfile owner (default: prometheus)
  -g GROUP, --group GROUP
                        Textfile group (default: prometheus)
  -m MODE, --mode MODE  Textfile mode (default: 0644)
```

For example:

- `$ barman_exporter postgres-01`
- `$ barman_exporter postgres-01 postgres-02`
- `$ barman_exporter all`
- `$ barman_exporter -f /var/lib/prometheus/node_exporter/barman.prom -u prometheus -g prometheus -m 0644 all`

## Requirements

You need Python3 to run it and following modules:

```
$ pip3 install prometheus_client sh

# or
$ pip3 install -r requirements.txt
```

## Installation

Copy `barman_exporter.py` file to /usr/local/sbin/barman_exporter. Set `chmod 700` and `chown root:root` permissions.

Alternatively you can use ansible playbook in `ansible/playbook.yml`.

### Cron job to run barman-exporter

Set up cron job to run every hour:

```
0 * * * * root /usr/local/bin/barman_exporter -f /var/lib/prometheus/node_exporter/barman.prom
```

## Prometheus configuration

Please note that backup listing is rather heavy IO operation and can take a while. **Definitely do not run barman exporter every minute**.

Barman exporter does not require any Prometheus configuration because it uses **node-exporter** to get metrics from a textfile. Remember to use `--collector.textfile.directory` in node-exporter to point a directory with textfiles.

## Metrics

The label `number=1` determines the newest backup.

The metrics `barman_bacukps_size` and `barman_backups_wal_size` show only successful backups. Failed backups will not be listed here.

The metric `barman_backups_total` includes failed backups. A number of failed backups is exposed in `barman_backups_failed`. `barman_last_backup_copy_time` shows how long did it take to make the latest backup.

The metric `barman_up` shows checks as in command `barman check SERVER_NAME`. Output `OK` is `1.0`, `FAILED` is `0.0`.

By using timestamps from metrics `barman_last_backup` and `barman_first_backup`, you can easily calculate how long ago backup completed:

`time() - barman_last_backup{instance="$instance", server="$server"}`

### Raw metrics

```
# HELP barman_backups_size Size of available backups
# TYPE barman_backups_size gauge
barman_backups_size{number="1",server="postgres-01"} 1.429365116108e+012
barman_backups_size{number="2",server="postgres-01"} 1.429365116108e+012
barman_backups_size{number="3",server="postgres-01"} 1.429365116108e+012
barman_backups_size{number="4",server="postgres-01"} 1.429365116108e+012
barman_backups_size{number="5",server="postgres-01"} 1.429365116108e+012
barman_backups_size{number="6",server="postgres-01"} 1.429365116108e+012
barman_backups_size{number="7",server="postgres-01"} 1.429365116108e+012
barman_backups_size{number="8",server="postgres-01"} 1.429365116108e+012

# HELP barman_backups_wal_size WAL size of available backups
# TYPE barman_backups_wal_size gauge
barman_backups_wal_size{number="1",server="postgres-01"} 1.94347270144e+011
barman_backups_wal_size{number="2",server="postgres-01"} 3.06553290752e+011
barman_backups_wal_size{number="3",server="postgres-01"} 3.05479548928e+011
barman_backups_wal_size{number="4",server="postgres-01"} 4.79318350233e+011
barman_backups_wal_size{number="5",server="postgres-01"} 2.87333312102e+011
barman_backups_wal_size{number="6",server="postgres-01"} 2.73267294208e+011
barman_backups_wal_size{number="7",server="postgres-01"} 3.65501716889e+011
barman_backups_wal_size{number="8",server="postgres-01"} 2.34075717632e+011

# HELP barman_backups_total Total number of backups
# TYPE barman_backups_total gauge
barman_backups_total{server="postgres-01"} 9.0

# HELP barman_backups_failed Number of failed backups
# TYPE barman_backups_failed gauge
barman_backups_failed{server="postgres-01"} 1.0

# HELP barman_last_backup Last successful backup timestamp
# TYPE barman_last_backup gauge
barman_last_backup{server="postgres-01"} 1.562537102e+09

# HELP barman_last_backup_copy_time Last successful backup copy time
# TYPE barman_last_backup_copy_time gauge
barman_last_backup_copy_time{server="postgres-01"} 18706.918297

# HELP barman_first_backup First successful backup timestamp
# TYPE barman_first_backup gauge
barman_first_backup{server="postgres-01"} 1.561154701e+09

# HELP barman_up Barman status checks
# TYPE barman_up gauge
barman_up{check="archiver_errors",server="postgres-01"} 1.0
barman_up{check="backup_maximum_age",server="postgres-01"} 1.0
barman_up{check="compression_settings",server="postgres-01"} 1.0
barman_up{check="directories",server="postgres-01"} 1.0
barman_up{check="failed_backups",server="postgres-01"} 1.0
barman_up{check="is_superuser",server="postgres-01"} 1.0
barman_up{check="minimum_redundancy_requirements",server="postgres-01"} 1.0
barman_up{check="pg_basebackup",server="postgres-01"} 1.0
barman_up{check="pg_basebackup_compatible",server="postgres-01"} 1.0
barman_up{check="pg_basebackup_supports_tablespaces_mapping",server="postgres-01"} 1.0
barman_up{check="pg_receivexlog",server="postgres-01"} 1.0
barman_up{check="pg_receivexlog_compatible",server="postgres-01"} 1.0
barman_up{check="postgresql",server="postgres-01"} 1.0
barman_up{check="postgresql_streaming",server="postgres-01"} 1.0
barman_up{check="receive_wal_running",server="postgres-01"} 1.0
barman_up{check="replication_slot",server="postgres-01"} 1.0
barman_up{check="retention_policy_settings",server="postgres-01"} 1.0
barman_up{check="systemid_coherence",server="postgres-01"} 1.0
barman_up{check="wal_level",server="postgres-01"} 1.0
```
