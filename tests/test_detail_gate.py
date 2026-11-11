import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from bonus.tools import BonusTools
from status_tools import StatusTools
from test_lab import FakeProvider, tool_call, final

VERCEL_BUILDS = ('get_vercel_status', '{"component": "Builds"}')
VERCEL_DETAIL = ('get_incident_details', '{"provider": "vercel", "incident_id": "w661l7k3kf4p"}')


def events(result, name):
    return [x for x in result['trace'] if x['event'] == name]


class IncidentDetailGateTests(unittest.TestCase):
    def test_component_search_without_details_gets_reminder(self):
        tools = BonusTools(scenario='noisy')
        url = tools.get_incident_details('vercel', 'w661l7k3kf4p')['url']
        fake = FakeProvider([tool_call('1', *VERCEL_BUILDS),
                             final('Vercel Builds resolved.'),      # trả lời mà chưa đọc chi tiết
                             tool_call('2', *VERCEL_DETAIL),
                             final('Vercel Builds resolved. ' + url)])
        result = run_agent('Kiểm tra Vercel Builds', fake, tools, max_steps=6)
        self.assertEqual(result['status'], 'completed')
        gate = events(result, 'validation_unread_incident_details')
        self.assertEqual(len(gate), 1)
        self.assertEqual(gate[0]['unread'], ['w661l7k3kf4p'])
        self.assertEqual(len(events(result, 'final')), 1)

    def test_status_without_component_has_no_reminder(self):
        fake = FakeProvider([tool_call('1', 'get_vercel_status', '{}'), final('Vercel operational.')])
        result = run_agent('x', fake, BonusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(events(result, 'validation_unread_incident_details'), [])

    def test_gate_disabled_for_main_lab(self):
        fake = FakeProvider([tool_call('1', 'get_status', '{"provider":"github","component":"Actions"}'),
                             final('Actions operational.')])
        result = run_agent('x', fake, StatusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(events(result, 'validation_unread_incident_details'), [])


if __name__ == '__main__':
    unittest.main()
