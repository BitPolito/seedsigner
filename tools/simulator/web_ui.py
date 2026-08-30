"""Local browser UI for environments where Tk/X11 is unavailable."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from queue import Empty
import json

from tools.simulator.adapters import image_from_payload, SimulatorButtonPins


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BitPolito SeedSigner Simulator</title>
<style>
:root { color-scheme: light; font-family: system-ui, sans-serif; }
body { margin: 0; min-height: 100vh; display: grid; place-items: center;
       background: #f3f5ff; color: #001ce0; }
main { padding: 20px; text-align: center; }
#screen { display: block; margin: auto; width: min(72vw, 480px); height: auto;
          image-rendering: pixelated; background: #000; border: 4px solid #001ce0;
          border-radius: 8px; box-shadow: 0 12px 32px #001ce033; }
#status { min-height: 1.5em; margin: 12px 0; color: #005fcc; }
.controls { display: flex; justify-content: center; align-items: center; gap: 28px; }
.dpad { display: grid; grid-template-columns: repeat(3, 58px); gap: 5px; }
.side { display: grid; gap: 8px; }
button { min-width: 58px; min-height: 48px; border: 2px solid #6666ff;
         border-radius: 8px; background: #fff; color: #001ce0;
         font-size: 20px; font-weight: 700; cursor: pointer; touch-action: none; }
button:active, button.active { background: #001ce0; color: #fff; }
.empty { visibility: hidden; }
.hint { margin-top: 14px; color: #667085; font-size: 14px; }
</style>
</head>
<body>
<main>
  <img id="screen" alt="SeedSigner display">
  <div id="status">Starting real SeedSigner application…</div>
  <div class="controls">
    <div class="dpad">
      <span class="empty"></span><button data-pin="31">↑</button><span class="empty"></span>
      <button data-pin="29">←</button><button data-pin="33">●</button><button data-pin="37">→</button>
      <span class="empty"></span><button data-pin="35">↓</button><span class="empty"></span>
    </div>
    <div class="side">
      <button data-pin="40">1</button><button data-pin="38">2</button><button data-pin="36">3</button>
    </div>
  </div>
  <div class="hint">Arrow keys · Enter · 1 / 2 / 3</div>
</main>
<script>
const screen = document.querySelector('#screen');
const statusBox = document.querySelector('#status');
const keys = {ArrowUp:31, ArrowDown:35, ArrowLeft:29, ArrowRight:37,
              Enter:33, '1':40, '2':38, '3':36};
const active = new Set();
async function send(pin, value) {
  await fetch('/input', {method:'POST', headers:{'Content-Type':'application/json'},
                         body:JSON.stringify({pin:Number(pin), value})});
}
function press(pin, button) {
  pin = Number(pin); if (active.has(pin)) return;
  active.add(pin); if (button) button.classList.add('active'); send(pin, 0);
}
function release(pin, button) {
  pin = Number(pin); if (!active.has(pin)) return;
  active.delete(pin); if (button) button.classList.remove('active'); send(pin, 1);
}
document.querySelectorAll('button[data-pin]').forEach(button => {
  const pin = button.dataset.pin;
  button.addEventListener('pointerdown', e => { e.preventDefault(); press(pin, button); });
  for (const event of ['pointerup', 'pointercancel', 'pointerleave'])
    button.addEventListener(event, () => release(pin, button));
});
document.addEventListener('keydown', event => {
  if (keys[event.key] !== undefined) { event.preventDefault(); press(keys[event.key]); }
});
document.addEventListener('keyup', event => {
  if (keys[event.key] !== undefined) { event.preventDefault(); release(keys[event.key]); }
});
setInterval(() => { screen.src = '/frame.png?t=' + Date.now(); }, 50);
setInterval(async () => {
  try {
    const state = await (await fetch('/status')).json();
    statusBox.textContent = state.error || (state.alive ? `Live · ${state.frames} frames` : 'Application stopped');
    statusBox.style.color = state.error || !state.alive ? '#b42318' : '#005fcc';
  } catch (_) { statusBox.textContent = 'Simulator server unavailable'; }
}, 500);
</script>
</body>
</html>
"""


class SimulatorWebServer:
    def __init__(
        self,
        frame_queue,
        input_queue,
        error_queue,
        app_process,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
    ):
        self.frame_queue = frame_queue
        self.input_queue = input_queue
        self.error_queue = error_queue
        self.app_process = app_process
        self.host = host
        self.port = int(port)
        self.latest_payload = None
        self.error = None
        self.frames = 0

    def _drain_frames(self):
        while True:
            try:
                self.latest_payload = self.frame_queue.get_nowait()
                self.frames += 1
            except Empty:
                return

    def _drain_errors(self):
        while True:
            try:
                self.error = self.error_queue.get_nowait()
            except Empty:
                return

    def _handler(self):
        simulator = self
        allowed_pins = {
            SimulatorButtonPins.KEY_UP,
            SimulatorButtonPins.KEY_DOWN,
            SimulatorButtonPins.KEY_LEFT,
            SimulatorButtonPins.KEY_RIGHT,
            SimulatorButtonPins.KEY_PRESS,
            SimulatorButtonPins.KEY1,
            SimulatorButtonPins.KEY2,
            SimulatorButtonPins.KEY3,
        }

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def _send(self, status, content_type, body):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/" or self.path.startswith("/?"):
                    self._send(200, "text/html; charset=utf-8", HTML.encode())
                    return
                if self.path.startswith("/frame.png"):
                    simulator._drain_frames()
                    if simulator.latest_payload is None:
                        self._send(204, "image/png", b"")
                        return
                    image = image_from_payload(simulator.latest_payload)
                    output = BytesIO()
                    image.save(output, format="PNG")
                    self._send(200, "image/png", output.getvalue())
                    return
                if self.path == "/status":
                    simulator._drain_errors()
                    payload = json.dumps(
                        {
                            "alive": simulator.app_process.is_alive(),
                            "frames": simulator.frames,
                            "error": simulator.error,
                        }
                    ).encode()
                    self._send(200, "application/json", payload)
                    return
                self._send(404, "text/plain", b"Not found")

            def do_POST(self):
                if self.path != "/input":
                    self._send(404, "text/plain", b"Not found")
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    data = json.loads(self.rfile.read(length))
                    pin = int(data["pin"])
                    value = int(data["value"])
                    if pin not in allowed_pins or value not in (0, 1):
                        raise ValueError("invalid GPIO event")
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    self._send(400, "text/plain", b"Invalid input")
                    return
                simulator.input_queue.put((pin, value))
                self._send(204, "text/plain", b"")

        return Handler

    def create_server(self):
        return ThreadingHTTPServer((self.host, self.port), self._handler())

    def run(self):
        try:
            server = self.create_server()
        except OSError as exc:
            raise SystemExit(
                f"Cannot start browser UI on {self.host}:{self.port}: {exc}"
            ) from exc
        print(f"BitPolito simulator: http://{self.host}:{server.server_port}")
        print("Press Ctrl+C in this terminal to stop it.")
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            print("\nStopping BitPolito simulator.")
        finally:
            server.server_close()
