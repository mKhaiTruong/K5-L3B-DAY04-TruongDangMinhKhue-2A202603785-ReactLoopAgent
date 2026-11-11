import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from status_tools import StatusTools
from test_lab import FakeProvider, tool_call, final

PARENT = '{"provider":"github","incident_id":"h02n9572mx9y"}'   # update dẫn link tới xr3myzj7ms51
LINKED = '{"provider":"github","incident_id":"xr3myzj7ms51"}'
NO_LINK = '{"provider":"cloudflare","incident_id":"wp49bp8bqo6c"}'


def url_of(provider, incident_id):
    return StatusTools().get_incident_details(provider, incident_id)['url']


def events(result, name):
    return [x for x in result['trace'] if x['event'] == name]


class LinkedIncidentGateTests(unittest.TestCase):
    def test_unread_linked_incident_gets_reminder_then_read(self):
        url = url_of('github', 'h02n9572mx9y')
        fake = FakeProvider([tool_call('1', 'get_incident_details', PARENT),
                             final('Đã xử lý. ' + url),           # trả lời sớm, chưa đọc incident được dẫn link
                             tool_call('2', 'get_incident_details', LINKED),
                             final('Đã xử lý, xem tóm tắt gộp. ' + url)])
        result = run_agent('Điều tra h02n9572mx9y', fake, StatusTools(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        gate = events(result, 'validation_unread_linked_incident')
        self.assertEqual(len(gate), 1)
        self.assertEqual(gate[0]['unread'], ['xr3myzj7ms51'])
        read = [x['arguments'] for x in events(result, 'tool')]
        self.assertEqual(read, [PARENT, LINKED])
        self.assertEqual(len(events(result, 'final')), 1)
    
    def test_reminder_is_sent_only_once(self):
        url = url_of('github', 'h02n9572mx9y')
        fake = FakeProvider([tool_call('1', 'get_incident_details', PARENT),
                             final('Đã xử lý. ' + url),
                             final('Vẫn không đọc tiếp. ' + url)])   # model bỏ qua lời nhắc
        result = run_agent('x', fake, StatusTools(), max_steps=4)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(events(result, 'validation_unread_linked_incident')), 1)
    
    def test_incident_without_link_has_no_reminder(self):
        url = url_of('cloudflare', 'wp49bp8bqo6c')
        fake = FakeProvider([tool_call('1', 'get_incident_details', NO_LINK), final('Xong. ' + url)])
        result = run_agent('x', fake, StatusTools(), max_steps=3)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(events(result, 'validation_unread_linked_incident'), [])
        
if __name__ == '__main__': unittest.main()