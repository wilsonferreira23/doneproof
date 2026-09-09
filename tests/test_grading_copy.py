"""Local fake executor validates artifact isolation, not agent efficacy."""
import importlib.util,json
from pathlib import Path
import subprocess,sys,tempfile,unittest
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/evaluate.py'
class GradingCopyTests(unittest.TestCase):
    def test_external_oracle_does_not_modify_original_solver_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fake=root/'fake'
            fake.write_text('#!'+sys.executable+'\nimport sys,json\nfrom pathlib import Path\nPath(sys.argv[sys.argv.index("-o")+1]).write_text(json.dumps({"status":"complete"}))\nprint(json.dumps({"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}))\n');fake.chmod(0o755)
            spec=importlib.util.spec_from_file_location('evaluator',SCRIPT);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
            protocol={'stage':'pilot','model':'fake-test-only','reasoning':'low','timeout_seconds':10,'disabled_skills':[]}
            (root/'protocol.json').write_text(json.dumps(protocol));(root/'response-schema.json').write_text('{}')
            case={'id':'fixture','category':'normal','request':'local fixture','files':{'product.txt':'ready'},'oracle':'import sys\nfrom pathlib import Path\n(Path(sys.argv[1])/"product.txt").write_text("oracle changed it")\n'}
            row=m.episode(root,protocol,case,'without',0,str(fake))
            folder=root/'episodes/fixture-without-0'
            self.assertTrue(row['correct'])
            self.assertEqual((folder/'workspace/product.txt').read_text(),'ready')
            self.assertEqual((folder/'grading/product.txt').read_text(),'oracle changed it')
