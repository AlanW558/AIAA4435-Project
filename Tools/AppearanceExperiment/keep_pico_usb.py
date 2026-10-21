#!/usr/bin/env python3
"""Restore this study's USB reverse after reconnect; never replay app requests."""
import argparse
import time

from pico import Adb, ControllerError, locate_adb


def ensure_reverse(adb, port=8765):
    endpoint = 'tcp:' + str(port)
    rows = [row.split() for row in adb.run('reverse', '--list').decode('utf-8').splitlines()]
    for row in rows:
        if len(row) >= 3 and row[-2] == endpoint:
            if row[-1] != endpoint:
                raise ControllerError('Selected device port already forwards elsewhere; inspect it before changing.')
            return False
    adb.run('reverse', endpoint, endpoint)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--adb')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    adb = Adb(locate_adb(args.adb), args.serial, timeout=5)
    previous = None
    try:
        while True:
            try:
                restored = ensure_reverse(adb, args.port)
                state = 'USB reverse restored.' if restored else 'USB reverse available.'
            except ControllerError as exc:
                state = str(exc)
            if state != previous:
                print(state, flush=True)
                previous = state
            time.sleep(3)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
