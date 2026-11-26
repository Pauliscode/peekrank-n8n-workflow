"""Música sintetizada (sin derechos de terceros), estilo pop electrónico alegre: 118 BPM, Do-Sol-Lam-Fa.
Bombo, palmas, hi-hat, bajo con 'pump', pad y melodía pulsada."""
import sys, wave
import numpy as np

SR = 48000
DUR = float(sys.argv[2])
BPM = 100
beat = 60 / BPM
N = int(SR * DUR)
t = np.arange(N) / SR
L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(21)

def hz(m):  # m = nota MIDI
    return 440 * 2 ** ((m - 69) / 12)

def add(a0, sig, gl=1.0, gr=1.0):
    i0 = int(a0 * SR)
    if i0 >= N: return
    n = min(len(sig), N - i0)
    L[i0:i0+n] += sig[:n] * gl; R[i0:i0+n] += sig[:n] * gr

compas = 4 * beat
acordes = [[57, 60, 64, 67], [53, 57, 60, 64], [48, 52, 55, 59], [55, 59, 62, 65]]   # Am7, Fmaj7, Cmaj7, G7
raices = [33, 41, 36, 43]
n_beats = int(DUR / beat) + 1
intro = 2 * compas            # los dos primeros compases sin batería, para entrar suave

# sidechain: volumen que baja en cada tiempo (efecto "pump")
pump = np.ones(N)
for b in range(n_beats):
    a0 = b * beat
    if a0 < intro: continue
    i0 = int(a0 * SR); n = min(int(beat * SR), N - i0)
    if n <= 0: break
    x = np.arange(n) / SR
    pump[i0:i0+n] = 1 - .55 * np.exp(-x / .09)

# pad (ondas de sierra suavizadas)
pad = np.zeros(N)
for c in range(int(DUR / compas) + 1):
    a0 = c * compas; ac = acordes[c % 4]
    i0 = int(a0 * SR); n = min(int((compas + .3) * SR), N - i0)
    if n <= 0: break
    x = np.arange(n) / SR
    env = np.minimum(1, x / .15) * np.minimum(1, np.maximum(0, (compas + .3 - x)) / .3)
    for m in ac:
        for det in (-.15, .15):
            f = hz(m + 12) + det
            sig = sum(np.sin(2 * np.pi * k * f * x) / k for k in range(1, 6))
            pad[i0:i0+n] += .018 * env * sig
L += pad * pump * .9; R += pad * pump

# bajo: corcheas en la raíz
for b8 in range(int(DUR / (beat / 2)) + 1):
    a0 = b8 * beat / 2
    if a0 < compas: continue
    c = int(a0 // compas); m = raices[c % 4] + (12 if b8 % 2 else 0) * 0
    x = np.arange(int(.22 * SR)) / SR
    f = hz(m)
    sig = (np.sin(2*np.pi*f*x) + .35*np.sin(2*np.pi*2*f*x)) * np.exp(-x/.12) * np.minimum(1, x/.004)
    add(a0, .22 * sig)

# melodía pulsada (pentatónica de Do), patrón de 2 compases
mel = [76, None, None, 72, None, 74, None, 76, 79, None, 76, None, 74, None, 72, None]
for i in range(int(DUR / (beat / 2)) + 1):
    a0 = i * beat / 2
    if a0 < compas: continue
    m = mel[i % 16]
    if m is None: continue
    c = int(a0 // compas)
    if c % 4 == 3 and m in (79, 81): m -= 2
    x = np.arange(int(.35 * SR)) / SR
    f = hz(m)
    sig = (np.sign(np.sin(2*np.pi*f*x)) * .25 + np.sin(2*np.pi*f*x)) * np.exp(-x/.11) * np.minimum(1, x/.003)
    add(a0, .07 * sig, .8, 1.0)
    add(a0 + beat * .75, .025 * sig, 1.0, .6)   # eco

# batería
for b in range(n_beats):
    a0 = b * beat
    if a0 < intro: continue
    x = np.arange(int(.3 * SR)) / SR
    fk = 52 + 110 * np.exp(-x / .035)
    kick = np.sin(2 * np.pi * np.cumsum(fk) / SR) * np.exp(-x / .14)
    add(a0, .55 * kick)
    if b % 4 == 2:   # golpe solo en el 3, más relajado
        x = np.arange(int(.18 * SR)) / SR
        nz = rng.standard_normal(len(x)); nz = nz - np.convolve(nz, np.ones(4)/4, 'same')
        clap = nz * (np.exp(-x/.03) + .5*np.exp(-np.maximum(0, x-.012)/.03)*(x>.012))
        add(a0, .12 * clap, .9, 1.0)
for h in range(int(DUR / (beat / 2)) + 1):
    a0 = h * beat / 2
    if a0 < intro: continue
    x = np.arange(int(.05 * SR)) / SR
    nz = rng.standard_normal(len(x)); nz = np.diff(np.concatenate([[0], nz]))
    add(a0 + (beat / 4 if h % 2 else 0) * 0, (.035 if h % 2 else .02) * nz * np.exp(-x / .012), .7, 1.0)

st = np.stack([L, R], axis=1)
fi, fo = int(SR * .5), int(SR * 2.2)
st[:fi] *= np.linspace(0, 1, fi)[:, None]; st[-fo:] *= np.linspace(1, 0, fo)[:, None]
st = np.tanh(st * 1.2) ; st = st / np.max(np.abs(st)) * .85
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes())
print("ok", DUR)
