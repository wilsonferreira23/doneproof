"""A local fake executable tests cancellation, never empirical agent efficacy."""
import hashlib,json,os
from pathlib import Path
import shutil,signal,subprocess,sys,tempfile,time,unittest
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/evaluate.py'

class StopTests(unittest.TestCase):
    def test_interrupt_stops_active_executors_and_does_not_start_pending_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=root/'run';run.mkdir();pids=root/'pids'
            fake=root/'fake-agent'
            fake.write_text('#!'+sys.executable+'\nimport os,time\nfrom pathlib import Path\nwith Path('+repr(str(pids))+').open("a") as f: f.write(str(os.getpid())+"\\n")\ntime.sleep(60)\n')
            fake.chmod(0o755)
            cases=[{'id':f'task-{i}','category':'normal','request':'local fixture','files':{},'oracle':'raise SystemExit(1)'} for i in range(12)]
            (run/'corpus.json').write_text(json.dumps({'cases':cases}))
            for name in ('v22','candidate'): (run/'skills'/name).mkdir(parents=True)
            shutil.copyfile(SCRIPT,run/'controller.py')
            digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            protocol={'stage':'pilot','tasks':12,'repetitions':1,'model':'fake-test-only','reasoning':'low','timeout_seconds':60,'disabled_skills':[],
                      'controller_sha256':digest(SCRIPT),'corpus_sha256':digest(run/'corpus.json'),'skill_hashes':{'v22':{},'candidate':{}}}
            (run/'protocol.json').write_text(json.dumps(protocol));(run/'response-schema.json').write_text('{}')
            proc=subprocess.Popen([sys.executable,str(SCRIPT),'run',str(run),'--workers','2','--codex',str(fake)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                deadline=time.monotonic()+8
                while (not pids.exists() or len(pids.read_text().splitlines())<2) and time.monotonic()<deadline: time.sleep(.05)
                self.assertTrue(pids.exists(),'executors did not start')
                proc.send_signal(signal.SIGTERM)
                stdout,stderr=proc.communicate(timeout=8)
                self.assertEqual(proc.returncode,2,stdout+stderr)
                self.assertIn('interrupted',stderr)
                self.assertEqual(len(pids.read_text().splitlines()),2)
                for pid in map(int,pids.read_text().splitlines()):
                    with self.assertRaises(ProcessLookupError):os.kill(pid,0)
                rows=[json.loads(p.read_text()) for p in (run/'episodes').glob('*/result.json')]
                self.assertEqual(len(rows),2)
                self.assertTrue(all(r['interrupted'] for r in rows))
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
