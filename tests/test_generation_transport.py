"""Contrat HTTP Ollama avec serveur LOCAL factice : aucune vraie inférence LLM."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading
from unittest.mock import patch
from urllib.error import URLError

import pytest
from partie2_rag.generation import OllamaClient


def test_ollama_native_http_contract():
    observed = {}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            observed.update(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            assert self.path == '/api/chat'
            content = json.dumps({'model': 'fixture-only', 'done': True, 'message': {'role': 'assistant', 'content': 'Réponse factice réservée au test.'}, 'eval_count': 7}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = OllamaClient('fixture-only', f'http://127.0.0.1:{server.server_port}', 2).generate([{'role': 'user', 'content': 'Test du transport seulement.'}])
        assert observed['stream'] is False
        assert observed['options']['temperature'] == 0
        assert observed['options']['num_ctx'] == 8192
        assert result['answer'] == 'Réponse factice réservée au test.'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_service_error_is_not_an_abstention():
    with patch('partie2_rag.generation.urlopen', side_effect=URLError('fixture unreachable')):
        with pytest.raises(RuntimeError, match='Ollama impossible'):
            OllamaClient(timeout=1).generate([])


def test_url_protocol_rejected():
    with pytest.raises(ValueError):
        OllamaClient(base_url='file:///tmp/not-http')


def test_length_truncated_generation_is_rejected():
    import io
    payload = {'done': True, 'done_reason': 'length', 'model': 'fixture-only',
               'message': {'content': 'Phrase interrompue avant ses conditions'}}
    with patch('partie2_rag.generation.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
        with pytest.raises(RuntimeError, match='tronqu'):
            OllamaClient().generate([])
