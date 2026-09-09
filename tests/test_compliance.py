import hashlib,importlib.util
from pathlib import Path
import shutil,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class ComplianceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);skill=self.root/'skill/scripts';skill.mkdir(parents=True)
        self.pod=skill/'pod.py';shutil.copyfile(ROOT/'scripts/pod.py',self.pod)
        self.protocol={'skill_hashes':{'candidate':{'scripts/pod.py':hashlib.sha256(self.pod.read_bytes()).hexdigest()}}}
        spec=importlib.util.spec_from_file_location('evaluator',ROOT/'scripts/evaluate.py');self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.case={'category':'normal','request':'Return one'}
        (self.root/'app.py').write_text('VALUE=1\n');(self.root/'acceptance.py').write_text('from app import VALUE\nassert VALUE==1\n')
        self.contract=self.root/'.proof-of-done/task/contract.json'

    def cli(self,*args):
        p=subprocess.run([sys.executable,str(self.pod),*map(str,args)],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def finish(self):
        self.cli('init',self.contract,'--input','app.py','--criterion','acceptance.py','--run',sys.executable,'acceptance.py')
        self.cli('verify',self.contract,'--gate','final');self.cli('finalize',self.contract)

    def test_requires_real_current_completion(self):
        self.assertFalse(self.module.verify_completion(self.root,self.case,self.protocol)['valid'])
        self.finish();self.assertTrue(self.module.verify_completion(self.root,self.case,self.protocol)['valid'])
        (self.root/'app.py').write_text('VALUE=2\n')
        self.assertFalse(self.module.verify_completion(self.root,self.case,self.protocol)['valid'])

    def test_modified_engine_is_not_accepted(self):
        self.finish();self.pod.write_text('print("VERIFIED_SUCCESS")\n')
        self.assertFalse(self.module.verify_completion(self.root,self.case,self.protocol)['valid'])

    def test_light_task_cannot_substitute_for_strict_or_plan_workflow(self):
        self.finish()
        for category in ('strict','plan','integration'):
            self.assertFalse(self.module.verify_completion(self.root,dict(self.case,category=category),self.protocol)['valid'])
