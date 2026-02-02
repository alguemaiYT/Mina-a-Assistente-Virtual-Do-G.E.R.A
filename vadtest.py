import sounddevice as sd
import numpy as np
import onnxruntime as ort
import time

# ================== CONFIG ==================
MODEL_PATH = "silero_vad.onnx"
SAMPLE_RATE = 16000
FRAME_SIZE = 512
CHANNELS = 1

SPEECH_THRESHOLD = 0.5   # score mínimo (strict) para considerar fala
SPEECH_TIMEOUT = 2.0      # segundos
# ============================================


# -------- ONNX --------
sess = ort.InferenceSession(
    MODEL_PATH,
    providers=["CPUExecutionProvider"]
)

inp = sess.get_inputs()[0].name
state_name = sess.get_inputs()[1].name
sr_name = sess.get_inputs()[2].name

state = np.zeros((2, 1, 128), dtype=np.float32)
sr = np.array(SAMPLE_RATE, dtype=np.int64)

# -------- Estado --------
speech_active = False
speech_timer = 0.0
last_time = time.time()


def process_frame(audio):
    global state, speech_active, speech_timer, last_time

    now = time.time()
    dt = now - last_time
    last_time = now

    audio = audio.reshape(1, -1).astype(np.float32)

    out, state = sess.run(
        None,
        {
            inp: audio,
            state_name: state,
            sr_name: sr
        }
    )

    score = float(out[0][0])

    # Reset the 3s 'imaginary' timer only when score is strictly above threshold
    if score > SPEECH_THRESHOLD:
        # fala detectada → ativa ou mantém o timer
        speech_timer = SPEECH_TIMEOUT
        if not speech_active:
            speech_active = True
            print(">>> FALA INICIOU")
    else:
        # silêncio → timer diminui
        if speech_timer > 0:
            speech_timer -= dt
        if speech_active and speech_timer <= 0:
            speech_active = False
            print("<<< FALA TERMINOU")

    # Debug simples
    print(f"score={score:.3f} timer={speech_timer:.2f}s", end="\r")


# -------- Microfone --------
def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    process_frame(indata[:, 0])


print("[INFO] VAD rodando — Ctrl+C para sair")

with sd.InputStream(
    channels=CHANNELS,
    samplerate=SAMPLE_RATE,
    blocksize=FRAME_SIZE,
    dtype="float32",
    callback=audio_callback
):
    while True:
        pass
