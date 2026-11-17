"""End-to-end synthetic STT/TTS plus one deliberately lost playback ACK."""
import io
import json
from pathlib import Path
import socket
import sys
import wave
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Experiment
from model import MockModel
from server import Server, Handler
from speech import SpeechConfig
from tutor_session import TutorSessions
from unity_audio_fixture_server import AudioFixture, AudioTransport
from unity_comparison_fixture_server import ComparisonFixture


class PlaybackHandler(Handler):
    lost = False
    def send_json(self, status, data):
        if self.command == 'POST' and self.path.endswith('/playback') and status == 200 and not type(self).lost:
            type(self).lost = True
            self.close_connection = True
            try: self.connection.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            self.connection.close(); return
        super().send_json(status, data)

    def do_GET(self):
        prefix = '/fixture/playback-state/'
        if not self.path.startswith(prefix): return super().do_GET()
        identifier = self.path[len(prefix):]
        target = self.server.comparisons.get(identifier)
        with target.audit_lock:
            path = self.server.comparisons.log_dir / (identifier + '.jsonl')
            records = [json.loads(line) for line in path.read_text().splitlines()]
        reports = [r for r in records if r['event'] == 'playback_report']
        ready = {r['audio_request_id']: r for r in records if r['event'] == 'audio_ready'}
        self.send_json(200, {
            **{state: sum(r['report']['event'] == state for r in reports) for state in ('started','stopped','completed','failed')},
            'events': len(reports), 'unique_events': len({r['report']['event_id'] for r in reports}),
            'bound_correctly': all(r['condition'] == ready[r['audio_request_id']]['condition'] and r['exchange_id'] == ready[r['audio_request_id']]['exchange_id'] for r in reports),
            'reply_conditions': sorted({r['condition'] for r in reports if r['purpose'] == 'reply' and r['report']['event'] == 'started'}),
            'feedback_count': sum(r['event'] == 'feedback_saved' for r in records),
            'submission_count': sum(r['event'] == 'task_submitted' for r in records),
            'lost_ack': type(self).lost,
        })


if __name__ == '__main__':
    folder = Path(__file__).resolve().parents[2] / 'StudyData/macos/playback-fixture'
    transport = AudioTransport(); buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000); wav.writeframes(b'\0\0' * 48000)
    transport.audio = buf.getvalue()
    speech = AudioFixture(SpeechConfig('https://fixture.cn-beijing.maas.aliyuncs.com', 'fixture-not-a-key'), transport)
    server = Server(('127.0.0.1', 8774), Experiment(MockModel(), folder), TutorSessions(ComparisonFixture(), folder), speech=speech)
    server.RequestHandlerClass = PlaybackHandler
    print('Synthetic STT / silent TTS on 127.0.0.1:8774; first playback ACK lost; no paid calls', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
