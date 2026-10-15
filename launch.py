#!/usr/bin/env python3
"""macOS-only launch support for the synthetic board; never closes another app."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import xml.etree.ElementTree as ET

FREECAD = Path('/Applications/FreeCAD.app/Contents/Resources/bin/freecad')

class LaunchError(Exception):
    pass


def make_plan(root):
    root = Path(root).resolve()
    runtime = root / 'local-data' / 'runtime'
    return {
        'executable': str(FREECAD),
        'root': str(root),
        'runtime': str(runtime),
        'recovery': str(runtime / 'recovery'),
        'config': str(runtime / 'user.cfg'),
        'macro': str(root / 'bridge' / 'LaunchIsolated.FCMacro'),
        'port': 8765,
        'environment': {'QT_ACCESSIBILITY': '0', 'FREECAD_USER_TEMP': str(runtime / 'recovery')},
    }


def freecad_running():
    # Fail closed if the process check is unavailable. Never terminate a process.
    result = subprocess.run(['/usr/bin/pgrep', '-x', 'freecad'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode not in (0, 1):
        raise LaunchError('Could not check existing FreeCAD sessions. Nothing was launched.')
    return result.returncode == 0


def port_available(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', port))
        return True
    except OSError:
        return False


def blockers(plan):
    problems = []
    if not os.access(plan['executable'], os.X_OK):
        problems.append('FreeCAD is missing from /Applications/FreeCAD.app.')
    if not Path(plan['macro']).is_file():
        problems.append('The isolated startup macro is missing.')
    if not (Path(plan['root'])/'node_modules/three/build/three.module.js').is_file():
        problems.append('Three.js is missing. Run npm ci in this repository first.')
    if freecad_running():
        problems.append('FreeCAD is already running. Arrange a handoff and save/close it yourself before launching this isolated prototype. No existing process was changed.')
    if not port_available(plan['port']):
        problems.append('Port 8765 is in use. The launcher will not take over or stop its owner.')
    return problems


def initialize_config(path):
    # Create a minimal, dedicated config once. Do not copy personal settings or
    # replace subsequent user changes or recovery files.
    root = ET.Element('FCParameters', {'SchemaVersion': '1'})
    group = ET.SubElement(root, 'FCParamGroup', {'Name': 'Root'})
    for name in ('BaseApp', 'Preferences', 'View'):
        group = ET.SubElement(group, 'FCParamGroup', {'Name': name})
    ET.SubElement(group, 'FCInt', {'Name': 'AnimationDuration', 'Value': '0'})
    ET.SubElement(group, 'FCBool', {'Name': 'UseSpinningAnimations', 'Value': '0'})
    ET.SubElement(group, 'FCBool', {'Name': 'UseNavigationAnimations', 'Value': '0'})
    try:
        with Path(path).open('xb') as stream:
            stream.write(ET.tostring(root, encoding='utf-8', xml_declaration=True))
    except FileExistsError:
        pass


def launch(plan):
    problems = blockers(plan)
    if problems:
        raise LaunchError('\n'.join(problems))
    runtime = Path(plan['runtime'])
    runtime.mkdir(parents=True, exist_ok=True)
    lock = (runtime/'launch.lock').open('a')
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise LaunchError('This checkout already has an isolated launcher running.')
    try:
        # Repeat the external checks while holding the checkout lock.
        problems = blockers(plan)
        if problems:
            raise LaunchError('\n'.join(problems))
        Path(plan['recovery']).mkdir(exist_ok=True)
        initialize_config(plan['config'])
        env = dict(os.environ, **plan['environment'])
        os.set_inheritable(lock.fileno(), True)
        env['FREECAD_WEB_UI_LAUNCH_FD'] = str(lock.fileno())
        argv = [plan['executable'], '--user-cfg', plan['config'], plan['macro']]
        # Direct execution deliberately avoids LaunchServices routing into an
        # existing app. No --single-instance flag is passed.
        os.execve(plan['executable'], argv, env)
    finally:
        lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Print the launch plan and blockers without creating files or starting FreeCAD')
    args = parser.parse_args()
    plan = make_plan(Path(__file__).parent)
    try:
        if args.dry_run:
            print(json.dumps(dict(plan, blockers=blockers(plan)), indent=2))
        else:
            launch(plan)
    except (LaunchError, OSError) as exc:
        print('Board Studio launcher: ' + str(exc), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
