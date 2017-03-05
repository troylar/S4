#! /usr/bin/env python

import argparse
import datetime
import getpass
import os
import json
import logging

import boto3

from tabulate import tabulate

from s3backup import sync
from s3backup.clients import local, s3


CONFIG_FILE_PATH = os.path.expanduser('~/.config/s3backup/sync.conf')


def get_s3_client(target, aws_access_key_id, aws_secret_access_key, region_name):
    s3_uri = s3.parse_s3_uri(target)
    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
    )
    return s3.S3SyncClient(s3_client, s3_uri.bucket, s3_uri.key)


def get_local_client(target):
    return local.LocalSyncClient(target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    parser.add_argument('--conflicts', default=None, choices=['1', '2', 'ignore'])

    subparsers = parser.add_subparsers(dest='command')
    sync_parser = subparsers.add_parser('sync')
    sync_parser.add_argument('targets', nargs='*')

    subparsers.add_parser('targets')
    subparsers.add_parser('add')
    edit_parser = subparsers.add_parser('edit')
    edit_parser.add_argument('name')

    ls_parser = subparsers.add_parser('ls')
    ls_parser.add_argument('target')

    args = parser.parse_args()

    if args.log_level == 'DEBUG':
        log_format = '%(levelname)s:%(module)s:%(lineno)s %(message)s'
    else:
        log_format = '%(message)s'

    logging.basicConfig(format=log_format, level=args.log_level)

    # shut boto up
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    logging.getLogger('botocore').setLevel(logging.CRITICAL)
    logging.getLogger('nose').setLevel(logging.CRITICAL)
    logging.getLogger('s3transfer').setLevel(logging.CRITICAL)

    logger = logging.getLogger(__name__)
    logger.setLevel(args.log_level)

    config = get_config()

    if args.command == 'sync':
        sync_command(args, config, logger)
    elif args.command == 'targets':
        targets_command(args, config, logger)
    elif args.command == 'add':
        add_command(args, config, logger)
    elif args.command == 'edit':
        edit_command(args, config, logger)
    elif args.command == 'ls':
        ls_command(args, config, logger)
    else:
        parser.print_help()


def get_config():
    if not os.path.exists(CONFIG_FILE_PATH):
        return {}

    with open(CONFIG_FILE_PATH, 'r') as fp:
        config = json.load(fp)
    return config


def set_config(config):
    with open(CONFIG_FILE_PATH, 'w') as fp:
        json.dump(config, fp, indent=4)


def get_clients(entry):
    target_1 = entry['local_folder']
    target_2 = entry['s3_uri']
    aws_access_key_id = entry['aws_access_key_id']
    aws_secret_access_key = entry['aws_secret_access_key']
    region_name = entry['region_name']

    # append trailing slashes to prevent incorrect prefix matching on s3
    if not target_1.endswith('/'):
        target_1 += '/'
    if not target_2.endswith('/'):
        target_2 += '/'

    client_1 = get_local_client(target_1)
    client_2 = get_s3_client(target_2, aws_access_key_id, aws_secret_access_key, region_name)
    return client_1, client_2


def sync_command(args, config, logger):
    all_targets = list(config['targets'].keys())
    if not args.targets:
        targets = all_targets
    else:
        targets = args.targets

    try:
        for name in targets:
            if name not in config['targets']:
                logger.info('"%s" is an unknown target. Choices are: %s', name, all_targets)
                continue

            entry = config['targets'][name]
            client_1, client_2 = get_clients(entry)

            logger.info('Syncing %s [%s <=> %s]', name, client_1.get_uri(), client_2.get_uri())
            sync.sync(client_1, client_2, conflict_choice=args.conflicts)
    except KeyboardInterrupt:
        logger.warning('Quitting due to Keyboard Interrupt...')


def targets_command(args, config, logger):
    if 'targets' not in config:
        return

    for name in sorted(config['targets']):
        entry = config['targets'][name]
        logger.info('%s: [%s <=> %s]', name, entry['local_folder'], entry['s3_uri'])


def add_command(args, config, logger):
    entry = {}

    entry['local_folder'] = input('local folder: ')
    entry['s3_uri'] = input('s3 uri: ')
    entry['aws_access_key_id'] = input('AWS Access Key ID: ')
    entry['aws_secret_access_key'] = getpass.getpass('AWS Secret Access Key: ')
    entry['region_name'] = input('region name: ')

    default_name = os.path.basename(entry['s3_uri'])
    name = input('Provide a name for this entry [{}]: '.format(default_name))

    if not name:
        name = default_name

    if 'targets' not in config:
        config['targets'] = {}

    config['targets'][name] = entry

    set_config(config)


def edit_command(args, config, logger):
    if 'targets' not in config or args.name not in config['targets']:
        logger.info('Target "%s" not found', args.name)
        logger.info('Use the "add" command to add a new target')
        return

    entry = config['targets'][args.name]

    local_folder = entry.get('local_folder', '')
    s3_uri = entry.get('s3_uri', '')
    aws_access_key_id = entry.get('aws_access_key_id')
    aws_secret_access_key = entry.get('aws_secret_access_key')
    region_name = entry.get('region_name')

    new_local_folder = input('local folder [{}]: '.format(local_folder))
    new_s3_uri = input('s3 uri [{}]: '.format(s3_uri))
    new_aws_access_key_id = input('AWS Access Key ID [{}]: '.format(aws_access_key_id))
    new_aws_secret_access_key = getpass.getpass('AWS Secret Access Key [{}]: '.format(aws_secret_access_key))
    new_region_name = input('region name [{}]: '.format(region_name))

    if new_local_folder:
        entry['local_folder'] = new_local_folder
    if new_s3_uri:
        entry['s3_uri'] = new_s3_uri
    if new_aws_access_key_id:
        entry['aws_access_key_id'] = new_aws_access_key_id
    if new_aws_secret_access_key:
        entry['aws_secret_access_key'] = new_aws_secret_access_key
    if new_region_name:
        entry['region_name'] = new_region_name

    config['targets'][args.name] = entry

    set_config(config)


def ls_command(args, config, logger):
    if 'targets' not in config:
        logger.info('You have not added any targets yet')
        logger.info('Use the "add" command to do this')
        return
    if args.target not in config['targets']:
        all_targets = sorted(list(config['targets'].keys()))
        logger.info('"%s" is an unknown target', args.target)
        logger.info('Choices are: %s', all_targets)
        return

    target = config['targets'][args.target]
    client_1, client_2 = get_clients(target)

    keys = set(client_1.index) | set(client_2.index)

    data = []
    for key in sorted(keys):
        entry_1 = client_1.index.get(key, {})
        entry_2 = client_2.index.get(key, {})

        ts_1 = entry_1.get('local_timestamp')
        ts_2 = entry_2.get('local_timestamp')

        if ts_1 is not None:
            data.append((
                key,
                datetime.datetime.utcfromtimestamp(int(ts_1)) if ts_1 is not None else '<deleted>',
                datetime.datetime.utcfromtimestamp(int(ts_2)) if ts_2 is not None else None,
            ))

    logger.info(tabulate(data, headers=['Key', client_1.get_client_name(), client_2.get_client_name()]))


if __name__ == '__main__':
    main()