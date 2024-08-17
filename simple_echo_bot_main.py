import streamlit as st
import pyaudio
import json
from vosk import Model, KaldiRecognizer
import os
import torch
import numpy as np
from models.fastpitch import FastPitch2Wave

# Initialize variables
if 'recording' not in st.session_state:
    st.session_state.recording = False
if 'recognized_text' not in st.session_state:
    st.session_state.recognized_text = ""
if 'stream' not in st.session_state:
    st.session_state.stream = None

# Title and Instructions
st.title("Real-Time Echo Bot with Vosk and FastPitch TTS")
st.write("Click 'Start Recording' to begin and 'Stop Recording' to end.")

# Initialize Vosk Model (cached for reuse)
@st.cache_resource
def load_vosk_model():
    if not os.path.exists("ar_model"):
        st.error("Please download the model from https://alphacephei.com/vosk/models and unpack it as 'ar_model' in the current folder.")
        st.stop()
    return Model("ar_model")

# Initialize TTS model (cached for reuse)
@st.cache_resource
def load_tts_model():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = FastPitch2Wave('pretrained/fastpitch_ar_adv.pth')
    return model.to(device=device)

# TTS function that generates speech from recognized text
def tts_generate(text, model):
    wave, _ = model.tts(text,vowelizer='shakkala', return_mel=True, denoise=0.005)
    return wave

# Load models
vosk_model = load_vosk_model()
tts_model = load_tts_model()

recognizer = KaldiRecognizer(vosk_model, 16000)

# Initialize PyAudio
p = pyaudio.PyAudio()


def process_stream():
    while st.session_state.recording:
        try:
            data = st.session_state.stream.read(2000, exception_on_overflow=False)  # Reduced read size
            if len(data) == 0:
                break

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                if 'text' in result:
                    st.session_state.recognized_text += result['text'] + " "
                    text_display.text(st.session_state.recognized_text)
            else:
                partial_result = json.loads(recognizer.PartialResult())
                if 'partial' in partial_result:
                    if st.session_state.recognized_text == "":
                        st.session_state.recognized_text += partial_result['partial'] + " "
                    text_display.text(st.session_state.recognized_text + partial_result['partial'])
        except OSError as e:
            st.error(f"An error occurred: {e}")
            break

# Start and Stop buttons for recording
if st.button("Start Recording"):
    if not st.session_state.recording:
        st.session_state.recording = True
        st.session_state.stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
        st.session_state.stream.start_stream()
        st.write("Recording started...")

if st.button("Stop Recording"):
    if st.session_state.recording:
        st.session_state.recording = False
        if st.session_state.stream:
            st.session_state.stream.stop_stream()
            st.session_state.stream.close()
            st.session_state.stream = None
        st.write("Recording stopped.")
        st.write("Final recognized text:")
        st.write(st.session_state.recognized_text)

# Display the recognized text live
text_display = st.empty()

# Process the audio stream if recording
if st.session_state.recording:
    process_stream()

# TTS button to play back the recognized text
if st.button("Generate TTS"):
    if st.session_state.recognized_text:
        st.write("Generating TTS audio...")
        wave_shakkala = tts_generate(st.session_state.recognized_text, tts_model)
        # Display audio
        st.audio(np.array(wave_shakkala), format='audio/wav', sample_rate=22050)
    else:
        st.write("No text recognized yet!")

# Stop the PyAudio stream properly
if not st.session_state.recording and st.session_state.stream:
    st.session_state.stream.stop_stream()
    st.session_state.stream.close()
    p.terminate()
