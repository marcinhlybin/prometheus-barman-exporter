# Barman exporter for Prometheus

## Usage

```
usage: barman_exporter [-h] [-l HOST:PORT] [servers [servers ...]]

Barman exporter

positional arguments:
  servers               Space separated list of backed up servers to check
                        (default: ['all'])

optional arguments:
  -h, --help            show this help message and exit
  -l HOST:PORT, --web-listen-address HOST:PORT
                        Address to listen on for web interface and telemetry.
                        (default: 127.0.0.1:9780)
```

For example:

* `barman_exporter postgres-01`
* `barman_exporter postgres-01 postgres-02`
* `barman_exporter all`
* `barman_exporter -l 10.10.10.5:9780 all`

Try if it works by running:

```
# This is default IP and port.
# If you used barman_exporter with `-l` argument adjust your connection details
curl http://127.0.0.1:9780
```

Any path is supported. You can use default `/metrics` or none.


## Requirements

You need Python3 to run it and following modules:

```
$ pip3 install prometheus_client sh
```

## Prometheus configuration

Please note that backup listing is I/O heavy process and can take a while. Definitely do not run this exporter every 5s or even 15s. 15 minutes or more is reasonable with at least 120s timeout depending on how many backups and servers you have.

Sample Prometheus configuration:

```
- job_name: barman
  scrape_interval: 15m
  scrape_timeout: 2m
  static_configs:
    - targets:
      - 'barman-01:9780'
```

## Metrics

Label `number=1` is the newest backup.

Metrics `barman_bacukps_size` and `barman_backups_wal_size` shows only successful backups. Failed backups will not be listed there.

Metric `barman_backups_total` includes failed backups. Also number of failed backups is exposed in `barman_backups_failed`.


Metric `barman_up` show output of `barman check SERVER_NAME` command. Output `OK` is `1.0`, `FAILED` is `0.0`.

Using timestamps from metrics `barman_last_backup` and `barman_first_backup` you can easily calculate how long ago a backup was completed:

```time() - barman_last_backup{instance="$instance", server="$server"}```

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

# HELP barman_first_backup First successful backup timestamp
# TYPE barman_first_backup gauge
barman_first_backup{server="postgres-01"} 1.561154701e+09

# HELP barman_up Barman status checks
# TYPE barman_up gauge
barman_up{check="postgresql",server="postgres-01"} 1.0
barman_up{check="is_superuser",server="postgres-01"} 1.0
barman_up{check="postgresql_streaming",server="postgres-01"} 1.0
barman_up{check="wal_level",server="postgres-01"} 1.0
barman_up{check="replication_slot",server="postgres-01"} 1.0
barman_up{check="directories",server="postgres-01"} 1.0
barman_up{check="retention_policy_settings",server="postgres-01"} 1.0
barman_up{check="backup_maximum_age",server="postgres-01"} 1.0
barman_up{check="compression_settings",server="postgres-01"} 1.0
barman_up{check="failed_backups",server="postgres-01"} 0.0
barman_up{check="minimum_redundancy_requirements",server="postgres-01"} 1.0
barman_up{check="pg_basebackup",server="postgres-01"} 1.0
barman_up{check="pg_basebackup_compatible",server="postgres-01"} 1.0
barman_up{check="pg_basebackup_supports_tablespaces_mapping",server="postgres-01"} 1.0
barman_up{check="pg_receivexlog",server="postgres-01"} 1.0
barman_up{check="pg_receivexlog_compatible",server="postgres-01"} 1.0
barman_up{check="receive_wal_running",server="postgres-01"} 1.0
barman_up{check="archiver_errors",server="postgres-01"} 1.0
```

## Grafana dashboard

You can find a basic Grafana dashboard in `grafana-dashboard.json`.

It is definitely open for improvements. Screenshot:

![Grafana screenshot](grafana-screenshot.png?raw=true "Grafana screenshot")

## Ansible role

In `ansible-barman-exporter` directory you can find Ansible role for installing barman-exporter. Copy it to `roles/monitoring/barman-exporter` and add to you playbooks:

```
# prometheus.yml
- hosts: barman-01
  roles:
    - name: monitoring/barman-exporter
      tags: barman-exporter
```

Run with:

```
ansible-playbook playbook/prometheus.yml -t barman-exporter
```

It will install Barman Exporter to `/usr/local/bin/barman_exporter` and add `barman-exporter` service file to systemd.
