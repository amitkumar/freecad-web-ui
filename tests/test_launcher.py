import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('board_studio_launcher', Path(__file__).resolve().parents[1]/'launch.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

class LauncherTests(unittest.TestCase):
    def fixture(self, root):
        root = Path(root)/'checkout with spaces'
        (root/'bridge').mkdir(parents=True)
        (root/'bridge/LaunchIsolated.FCMacro').write_text('# test')
        (root/'node_modules/three/build').mkdir(parents=True)
        (root/'node_modules/three/build/three.module.js').write_text('// test')
        plan = launcher.make_plan(root)
        plan['executable'] = '/usr/bin/true'
        return plan

    def test_isolates_config_and_recovery(self):
        plan = launcher.make_plan('/tmp/example studio')
        self.assertEqual(plan['environment']['QT_ACCESSIBILITY'],'0')
        expected = str(Path('/tmp/example studio').resolve()/'local-data/runtime') + '/'
        self.assertTrue(plan['recovery'].startswith(expected))
        self.assertTrue(plan['config'].startswith(expected))

    def test_existing_freecad_blocks_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.fixture(directory)
            with patch.object(launcher,'freecad_running',return_value=True), patch.object(launcher,'port_available',return_value=True), patch.object(launcher.os,'execve') as execute:
                with self.assertRaisesRegex(launcher.LaunchError,'already running'):
                    launcher.launch(plan)
                execute.assert_not_called()
                self.assertFalse(Path(plan['runtime']).exists())

    def test_occupied_port_blocks_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.fixture(directory)
            with patch.object(launcher,'freecad_running',return_value=False), patch.object(launcher,'port_available',return_value=False), patch.object(launcher.os,'execve') as execute:
                with self.assertRaisesRegex(launcher.LaunchError,'Port 8765'):
                    launcher.launch(plan)
                execute.assert_not_called()
                self.assertFalse(Path(plan['runtime']).exists())

    def test_preserves_existing_config_and_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.fixture(directory)
            Path(plan['recovery']).mkdir(parents=True)
            sentinel = Path(plan['recovery'])/'existing-recovery-data'
            sentinel.write_text('retain')
            Path(plan['config']).write_text('retain personal edits')
            with patch.object(launcher,'freecad_running',return_value=False), patch.object(launcher,'port_available',return_value=True), patch.object(launcher.os,'execve') as execute:
                launcher.launch(plan)
                executable, argv, env = execute.call_args.args
                self.assertEqual(argv,[executable,'--user-cfg',plan['config'],plan['macro']])
                self.assertEqual(env['QT_ACCESSIBILITY'],'0')
                self.assertEqual(env['FREECAD_USER_TEMP'],plan['recovery'])
            self.assertEqual(sentinel.read_text(),'retain')
            self.assertEqual(Path(plan['config']).read_text(),'retain personal edits')

    def test_initial_config_disables_animations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'user.cfg'
            launcher.initialize_config(path)
            root = ET.parse(path).getroot()
            self.assertEqual(root.find(".//FCInt[@Name='AnimationDuration']").attrib['Value'],'0')
            self.assertEqual(root.find(".//FCBool[@Name='UseNavigationAnimations']").attrib['Value'],'0')

    def test_process_detection_fails_closed(self):
        with patch.object(launcher.subprocess,'run') as run:
            run.return_value.returncode = 2
            with self.assertRaises(launcher.LaunchError): launcher.freecad_running()
