import json
from pathlib import Path
import subprocess,sys,tempfile,unittest
POD=Path(__file__).resolve().parents[1]/'scripts/pod.py'
class InitRecoveryTests(unittest.TestCase):
    def test_existing_state_without_contract_is_not_a_new_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'proof';folder.mkdir()
            (root/'app.py').write_text('VALUE=1\n');(root/'check.py').write_text('assert True\n')
            argv=[sys.executable,str(POD),'init',str(folder/'contract.json'),'--input','app.py','--criterion','check.py','--run',sys.executable,'check.py']
            first=subprocess.run(argv,cwd=root,capture_output=True,text=True);self.assertEqual(first.returncode,0,first.stdout)
            before=(folder/'state.json').read_bytes();(folder/'contract.json').unlink()
            again=subprocess.run(argv,cwd=root,capture_output=True,text=True)
            self.assertNotEqual(again.returncode,0)
            self.assertEqual((folder/'state.json').read_bytes(),before)
            self.assertFalse((folder/'contract.json').exists())

    def test_invalid_external_destination_has_no_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);project=root/'project';project.mkdir();outside=root/'outside'
            result=subprocess.run([sys.executable,str(POD),'init',str(outside/'contract.json'),'--input','app.py','--criterion','check.py','--run',sys.executable,'check.py'],cwd=project,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(outside.exists())
