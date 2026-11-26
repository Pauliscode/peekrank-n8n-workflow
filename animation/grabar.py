"""Graba anim.html fotograma a fotograma con Chrome (protocolo DevTools, sin librerías externas) y lo pasa a ffmpeg."""
import base64, json, os, socket, struct, subprocess, sys, time, urllib.request

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
aqui = os.path.dirname(os.path.abspath(__file__))
html, salida, dur, fps = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
PORT = 9339

perfil = os.path.join(aqui, "perfil-chrome")
proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={perfil}",
                         "--hide-scrollbars", "--window-size=1920,1080", "--force-device-scale-factor=1",
                         "file:///" + html.replace("\\", "/")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
            pg = [p for p in pages if p.get("type") == "page"][0]
            break
        except Exception:
            time.sleep(.3)
    ws_url = pg["webSocketDebuggerUrl"]
    host, path = ws_url[len("ws://"):].split("/", 1)
    h, p = host.split(":")
    s = socket.create_connection((h, int(p)))
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET /{path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += s.recv(4096)
    resto = buf.split(b"\r\n\r\n", 1)[1]

    def recv_exact(n):
        global resto
        while len(resto) < n:
            resto += s.recv(1 << 20)
        out, resto = resto[:n], resto[n:]
        return out

    def recv_msg():
        datos = b""
        while True:
            b1, b2 = recv_exact(2)
            fin, op = b1 & 0x80, b1 & 0x0F
            ln = b2 & 0x7F
            if ln == 126: ln = struct.unpack(">H", recv_exact(2))[0]
            elif ln == 127: ln = struct.unpack(">Q", recv_exact(8))[0]
            datos += recv_exact(ln)
            if fin: return datos.decode()

    def send(obj):
        d = json.dumps(obj).encode(); m = os.urandom(4)
        hdr = bytes([0x81]) + (bytes([0x80 | len(d)]) if len(d) < 126 else
               bytes([0x80 | 126]) + struct.pack(">H", len(d)) if len(d) < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", len(d)))
        s.sendall(hdr + m + bytes(b ^ m[i % 4] for i, b in enumerate(d)))

    nid = [0]
    def call(method, **params):
        nid[0] += 1; send({"id": nid[0], "method": method, "params": params})
        while True:
            r = json.loads(recv_msg())
            if r.get("id") == nid[0]:
                if "error" in r: raise RuntimeError(r["error"])
                return r.get("result", {})

    call("Emulation.setDeviceMetricsOverride", width=1920, height=1080, deviceScaleFactor=1, mobile=False)
    call("Runtime.evaluate", expression="document.fonts.ready.then(()=>1)", awaitPromise=True)
    time.sleep(1.0)
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
                           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-crf", "17", "-preset", "medium", salida],
                          stdin=subprocess.PIPE)
    n = int(round(dur * fps))
    for i in range(n):
        call("Runtime.evaluate", expression=f"render({i / fps})")
        img = call("Page.captureScreenshot", format="jpeg", quality=93)["data"]
        ff.stdin.write(base64.b64decode(img))
        if i % 150 == 0: print(f"{i}/{n}", flush=True)
    ff.stdin.close(); ff.wait()
    print("ok", n)
finally:
    proc.kill()
