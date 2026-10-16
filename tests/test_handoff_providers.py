import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from sector_heatmap.handoff_ai import HandoffAI,review_stock_handoff
from sector_heatmap.codex_handoff import review,check_event


class ProviderTests(unittest.TestCase):
    def test_default_is_rules_and_unknown_provider_is_rejected(self):
        self.assertEqual(HandoffAI.from_payload('.',{}).provider,'RULES_ONLY')
        with self.assertRaises(ValueError):HandoffAI.from_payload('.',{'ai_provider':'unexpected'})

    def test_api_choice_is_rejected_and_rules_never_call_ai(self):
        with self.assertRaisesRegex(ValueError,'API-key analysis is disabled'):
            HandoffAI.from_payload('.',{'ai_provider':'OPENAI_API'})
        result={'cards':[{'candidate':{'symbol':'TEST'},'analysis':{'entry':100}}]}
        with patch('sector_heatmap.codex_handoff.review',side_effect=AssertionError('No AI call')):
            review_stock_handoff(result,{'ai_provider':'RULES_ONLY'},'.')
        self.assertEqual(result['ai_review']['status'],'DISABLED_BY_SELECTION')
        self.assertEqual(result['cards'][0]['analysis']['entry'],100)

    def test_stock_batches_include_only_public_indicators_and_attach_real_ai_review(self):
        captured=[]
        class AI:
            provider='CODEX_CHATGPT'
            def review(self,evidence):
                captured.append(evidence)
                return dict(summary='Observed public trends',model='fixture',recommendations=[dict(symbol=r['symbol'],decision='WAIT',confidence='LOW',rationale='Insufficient evidence',risks=[]) for r in evidence['instruments']])
        cards=[dict(candidate={'symbol':f'NSE:TEST{i}-EQ','account_id':'private-account','direction':'BULLISH','funds':12345},analysis={'entry':100,'quantity':500,'available_funds':12345,'evidence':{'daily':{'close':100,'ema20':90,'access_token':'private-token'}}}) for i in range(7)]
        result={'cards':cards}
        with patch.object(HandoffAI,'from_payload',return_value=AI()):review_stock_handoff(result,{'ai_provider':'CODEX_CHATGPT'},'.')
        self.assertEqual([len(e['instruments']) for e in captured],[6,1])
        text=json.dumps(captured)
        for secret in ('private-account','private-token','available_funds','quantity','12345'):self.assertNotIn(secret,text)
        self.assertEqual(result['ai_review']['status'],'COMPLETED');self.assertEqual(len(result['ai_review']['recommendations']),7)

    def test_codex_child_has_no_api_keys_broker_credentials_or_user_config(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);home=root/'auth';home.mkdir();(home/'auth.json').write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'fixture'}}))
            binary=root/'codex-fixture'
            binary.write_text('''#!/usr/bin/env python3
import json,os,sys
assert 'OPENAI_API_KEY' not in os.environ and 'CODEX_API_KEY' not in os.environ and 'BROKER_TOKEN' not in os.environ
assert '--ignore-user-config' in sys.argv and '--ephemeral' in sys.argv
assert 'shell_tool' in sys.argv and 'apps' in sys.argv
out=sys.argv[sys.argv.index('--output-last-message')+1]
json.dump({'summary':'Fixture','recommendations':[]},open(out,'w'))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':1}}))
''');binary.chmod(0o700)
            (root/'.private').mkdir();(root/'.private/analysis-providers.json').write_text(json.dumps({'codex_bin':str(binary),'codex_home':str(home)}))
            with patch.dict(os.environ,{'OPENAI_API_KEY':'private','CODEX_API_KEY':'private','BROKER_TOKEN':'private'}):
                value,usage=review(root,{'instruments':[]},'Public evidence only',{'type':'object'})
            self.assertEqual(value['summary'],'Fixture');self.assertEqual(usage['input_tokens'],1)

    def test_account_path_never_calls_api_sender_or_key_reader(self):
        value={'summary':'Account review','recommendations':[{'symbol':'TEST','decision':'WAIT','confidence':'LOW','rationale':'Incomplete','risks':[]}]}
        ai=HandoffAI('.',provider='CODEX_CHATGPT',key_reader=lambda:self.fail('Key read'),sender=lambda *a,**k:self.fail('API request'))
        with patch('sector_heatmap.codex_handoff.review',return_value=(value,{})):
            result=ai.review({'instruments':[{'symbol':'TEST'}]})
        self.assertEqual(result['provider'],'Codex / ChatGPT account')

    def test_codex_rejects_tool_events_and_allows_text_only(self):
        check_event({'item':{'type':'agent_message','text':'Research'}})
        with self.assertRaisesRegex(ValueError,'tool'):
            check_event({'item':{'type':'command_execution','command':'anything'}})
