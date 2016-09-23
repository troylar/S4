# -*- coding: utf-8 -*-

import os


def create_parent_directories(path):
    path = '/'.join(path.split('/')[:-1])
    if not os.path.exists(path):
        os.makedirs(path)


def traverse(path):
    for item in os.listdir(path):
        full_path = os.path.join(path, item)
        if os.path.isdir(full_path):
            for result in traverse(full_path):
                yield os.path.join(item, result)
        elif not item.startswith('.'):
            yield item


class LocalSyncClient(object):
    def __init__(self, local_dir):
        self.local_dir = local_dir

    def get_object_timestamp(self, key):
        object_path = os.path.join(self.local_dir, key)
        if os.path.exists(object_path):
            return os.stat(object_path).st_mtime
        else:
            return None

    def update_sync_index(self):
        pass

    def keys(self):
        return list(traverse(self.local_dir))

    def put_object(self, key, fp, timestamp):
        object_path = os.path.join(self.local_dir, key)

        if not os.path.exists(object_path):
            create_parent_directories(object_path)

        with open(object_path, 'wb') as fp2:
            fp2.write(fp.read())

        object_stat = os.stat(object_path)
        os.utime(object_path, (object_stat.st_atime, timestamp))

    def get_object(self, key):
        return open(os.path.join(self.local_dir, key), 'rb')