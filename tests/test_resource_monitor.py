import unittest
from sector_heatmap.resource_monitor import parse_sar, cpu_delta
from sector_heatmap.section_permissions import allowed

class ResourceMonitorTests(unittest.TestCase):
    def test_wait_and_steal_are_not_cpu_work(self):
        result=cpu_delta([0]*8,[20,0,10,50,5,2,3,10])
        self.assertEqual(result['cpu'],35)
        self.assertEqual(result['non_idle'],50)
        self.assertEqual(result['steal'],10)
    def test_sar_columns_and_timestamp(self):
        text='Linux x (host) 10/14/26 _x86_64_ (4 CPU)\n00:00:01 CPU %user %nice %system %iowait %steal %idle\n04:20:01 all 43.78 0.01 4.56 0.35 6.77 44.54\nAverage: all 1 0 1 0 0 98'
        row=parse_sar(text,'cpu')[0]
        self.assertEqual(row['cpu'],48.35)
        self.assertEqual(row['non_idle'],55.46)
        self.assertEqual(row['time'],'2026-10-14T04:20:01+00:00')
        memory='Linux x (host) 10/14/26 _x86_64_ (4 CPU)\n00:00:01 kbmemfree kbavail kbmemused %memused\n04:20:01 20 40 60 51.71'
        self.assertEqual(parse_sar(memory,'memory')[0]['memory'],51.71)
    def test_permission_is_explicit(self):
        self.assertFalse(allowed({'features':['broker']},'/api/resources'))
        self.assertTrue(allowed({'features':['resources']},'/api/resources'))
        self.assertTrue(allowed({'admin':True},'/api/resources'))
