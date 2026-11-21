"""Tiny offline cache fixtures. Never loads actual broker masters or credentials."""
import csv
import importlib.util
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

candidate=Path('.private/chart-order-rollouts/fyers-master-memory-20261119/broker.candidate.py')
spec=importlib.util.spec_from_file_location('strategies.ema_crossover.shared_master_candidate',candidate)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class MasterCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        module._shared_master_rows.clear()

    def broker(self,folder=None):
        return module.FyersBroker(folder or self.root,lambda *a:None,lambda *a:None)

    def write(self,folder=None,name='NSE_FO',value='A'):
        folder=folder or self.root;folder.mkdir(parents=True,exist_ok=True)
        path=folder/(name+'.csv');path.write_text(value+',description,1\n')
        return path

    def test_multiple_adapters_share_one_immutable_parse(self):
        self.write()
        brokers=[self.broker() for _ in range(13)]
        with patch.object(module.csv,'reader',wraps=csv.reader) as reader:
            rows=[b.rows('NSE_FO') for b in brokers]
        self.assertEqual(reader.call_count,1)
        self.assertTrue(all(r is rows[0] for r in rows))
        with self.assertRaises(TypeError):rows[0][0][0]='changed'
        self.assertTrue(all(not hasattr(b,'_master_rows_cache') for b in brokers))

    def test_atomic_file_replacement_invalidates_current_version(self):
        path=self.write(value='OLD');a=self.broker();b=self.broker()
        old=a.rows('NSE_FO')
        replacement=path.with_suffix('.replacement');replacement.write_text('NEW,description,1\n');replacement.replace(path)
        current=b.rows('NSE_FO')
        self.assertEqual(current[0][0],'NEW');self.assertEqual(old[0][0],'OLD')
        self.assertIs(a.rows('NSE_FO'),current)
        self.assertEqual(len(module._shared_master_rows),1)

    def test_stale_missing_or_changed_masters_never_use_old_cached_rows(self):
        path=self.write();b=self.broker();b.rows('NSE_FO')
        os.utime(path,(time.time()-90000,time.time()-90000))
        with self.assertRaisesRegex(ValueError,'Current FYERS master'):b.rows('NSE_FO')
        path.unlink()
        with self.assertRaisesRegex(ValueError,'Current FYERS master'):b.rows('NSE_FO')

    def test_different_owner_paths_cannot_alias_same_segment(self):
        left=self.root/'left';right=self.root/'right'
        self.write(left,value='LEFT');self.write(right,value='RIGHT')
        a=self.broker(left).rows('NSE_FO');b=self.broker(right).rows('NSE_FO')
        self.assertIsNot(a,b);self.assertEqual(a[0][0],'LEFT');self.assertEqual(b[0][0],'RIGHT')

    def test_bounded_cache_evicts_paths_without_mutating_existing_readers(self):
        first=None
        for i in range(20):
            folder=self.root/str(i);self.write(folder,value=str(i))
            rows=self.broker(folder).rows('NSE_FO')
            if first is None:first=rows
        self.assertEqual(len(module._shared_master_rows),16)
        self.assertEqual(first[0][0],'0')

    def test_replacement_during_parse_fails_closed_and_does_not_cache_mixed_rows(self):
        path=self.write(value='OLD');original_reader=csv.reader
        def changing(stream):
            for row in original_reader(stream):
                replacement=path.with_suffix('.replacement')
                replacement.write_text('NEW,description,1\\n');replacement.replace(path)
                yield row
        with patch.object(module.csv,'reader',side_effect=changing):
            with self.assertRaisesRegex(ValueError,'changed during read'):
                self.broker().rows('NSE_FO')
        self.assertEqual(len(module._shared_master_rows),0)
        self.assertEqual(self.broker().rows('NSE_FO')[0][0],'NEW')

    def test_parallel_adapters_parse_only_once(self):
        self.write();barrier=threading.Barrier(5);results=[];errors=[]
        def read():
            try:
                barrier.wait();results.append(self.broker().rows('NSE_FO'))
            except Exception as error:errors.append(error)
        with patch.object(module.csv,'reader',wraps=csv.reader) as reader:
            threads=[threading.Thread(target=read) for _ in range(5)]
            for t in threads:t.start()
            for t in threads:t.join(timeout=5)
        self.assertFalse(errors);self.assertEqual(len(results),5);self.assertEqual(reader.call_count,1)
        self.assertTrue(all(r is results[0] for r in results))


if __name__=='__main__':
    unittest.main()
