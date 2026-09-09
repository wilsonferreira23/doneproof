"""Synthetic records verify the evaluator only; these are not agent episodes."""
import hashlib,json
from pathlib import Path
import shutil,subprocess,sys,tempfile,unittest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/evaluate.py'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

class FinalReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.write('corpus.json',{'cases':[{'id':f'fixture-{i}','category':['normal','integration','strict','plan','operational'][i%5],'requirement_ids':['R1','R2']} for i in range(60)]})
        for name in ('v22','candidate'): (self.root/'skills'/name).mkdir(parents=True)
        shutil.copyfile(SCRIPT,self.root/'controller.py')
        self.write('protocol.json',{'stage':'final','tasks':60,'repetitions':2,'controller_sha256':sha(SCRIPT),'corpus_sha256':sha(self.root/'corpus.json'),'skill_hashes':{'v22':{},'candidate':{}}})
        for i in range(60):
            for cond in ('without','v22','candidate'):
                for rep in range(2):
                    folder=f'episodes/fixture-{i}-{cond}-{rep}'
                    usage={'input_tokens':100,'output_tokens':10}
                    self.write(folder+'/events.jsonl',{'type':'turn.completed','usage':usage})
                    self.write(folder+'/answer.json',{'status':'complete'})
                    self.write(folder+'/compliance.json',{'valid':True})
                    self.write(folder+'/oracle-result.json',{'exit':0,'stdout':json.dumps({'requirements':{'R1':True,'R2':True}})})
                    self.write(folder+'/result.json',{'task':f'fixture-{i}','category':['normal','integration','strict','plan','operational'][i%5],'condition':cond,'repetition':rep,'correct':True,'declared_complete':True,'false_success':False,'false_block':False,'correct_completion':True,'duration_seconds':1,'usage':usage,'commands':1,'infrastructure_error':False,'timed_out':False,'requirements':{'R1':True,'R2':True},'compliance':{'valid':True},'protocol_sha256':sha(self.root/'protocol.json')})

    def write(self,path,value):
        p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))

    def report(self):
        return subprocess.run([sys.executable,str(SCRIPT),'report','--require-pass',str(self.root)],capture_output=True,text=True)

    def test_complete_synthetic_final_exercises_arithmetic_only(self):
        result=self.report();self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout);self.assertEqual(report['episodes'],360)
        self.assertEqual(report['by_category']['strict']['candidate']['episodes'],24)

    def test_exit_zero_cannot_hide_missing_outcome(self):
        folder='episodes/fixture-0-candidate-0'
        self.write(folder+'/oracle-result.json',{'exit':0,'stdout':json.dumps({'requirements':{'R1':True}})})
        self.assertNotEqual(self.report().returncode,0)

    def test_empty_oracle_output_cannot_count_as_correct(self):
        self.write('episodes/fixture-0-candidate-0/oracle-result.json',{'exit':0,'stdout':''})
        self.assertNotEqual(self.report().returncode,0)

    def test_interrupted_run_cannot_pass(self):
        p=self.root/'episodes/fixture-0-candidate-0/result.json';r=json.loads(p.read_text());r['interrupted']=True;p.write_text(json.dumps(r))
        result=self.report();self.assertNotEqual(result.returncode,0)
        self.assertIn('interrupted episodes',result.stdout)
