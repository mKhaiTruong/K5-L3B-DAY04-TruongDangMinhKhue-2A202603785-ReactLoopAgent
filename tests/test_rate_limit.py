import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent, SYSTEM_PROMPT
from bonus.tools import BonusTools
from status_tools import StatusTools
from test_lab import FakeProvider, tool_call, final

VERCEL = ('get_vercel_status', '{}')


def events(result, name):
    return [x for x in result['trace'] if x['event'] == name]


def tool_calls(result, name):
    return [x for x in events(result, 'tool') if x['name'] == name]


class RateLimitGateTests(unittest.TestCase):
    def test_unretried_429_gets_one_reminder_then_retry(self):
        fake = FakeProvider([tool_call('1', *VERCEL),          # 429 giả lập
                             final('Vercel bị lỗi.'),           # trả lời mà chưa retry
                             tool_call('2', *VERCEL),           # retry -> thành công
                             final('Vercel operational sau 1 lần retry.')])
        result = run_agent('Kiểm tra Vercel', fake, BonusTools(scenario='rate_limit_once'), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        gate = events(result, 'validation_unretried_rate_limit')
        self.assertEqual(len(gate), 1)
        self.assertEqual(gate[0]['pending'], ['get_vercel_status'])
        self.assertEqual(len(tool_calls(result, 'get_vercel_status')), 2)
        self.assertEqual(len(events(result, 'final')), 1)

    def test_persistent_429_is_capped(self):
        fake = FakeProvider([tool_call('1', *VERCEL), tool_call('2', *VERCEL),
                             final('Vẫn 429.'),                 # 2 lần < 3 -> nhắc 1 lần
                             tool_call('3', *VERCEL),           # lần 3 vẫn 429
                             final('Không kiểm tra được Vercel do 429.')])
        result = run_agent('x', fake, BonusTools(scenario='rate_limit_always'), max_steps=8)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(events(result, 'validation_unretried_rate_limit')), 1)
        self.assertEqual(len(tool_calls(result, 'get_vercel_status')), 3)

    def test_main_lab_prompt_and_timeout_unchanged(self):
        fake = FakeProvider([tool_call('1', 'get_status', '{"provider":"github"}'),
                             final('Không lấy được dữ liệu do timeout.')])
        result = run_agent('x', fake, StatusTools(fail=True))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(fake.histories[0][0]['content'], SYSTEM_PROMPT)
        self.assertEqual(events(result, 'validation_unretried_rate_limit'), [])


if __name__ == '__main__':
    unittest.main()