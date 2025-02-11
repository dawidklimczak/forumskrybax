import streamlit as st
import os
import librosa
import soundfile as sf
import numpy as np
from openai import OpenAI
from docx import Document
import math
import tempfile
import io

# Konfiguracja strony Streamlit
st.set_page_config(page_title="Transkrypcja Audio", page_icon="🎤")
st.title("Transkrypcja plików audio")

# Inicjalizacja stanu sesji dla transkrypcji
if 'transcription_done' not in st.session_state:
    st.session_state.transcription_done = False
if 'full_transcript' not in st.session_state:
    st.session_state.full_transcript = ""

# Lepsza obsługa inicjalizacji OpenAI
def initialize_openai():
    try:
        openai_api_key = st.secrets.get("OPENAI_API_KEY")
        if not openai_api_key:
            openai_api_key = os.environ.get("OPENAI_API_KEY")
        
        if not openai_api_key:
            raise ValueError("Nie znaleziono klucza API OpenAI")
            
        return OpenAI(api_key=openai_api_key)
    except Exception as e:
        st.error(f"Błąd podczas inicjalizacji API OpenAI: {str(e)}")
        return None

# Inicjalizacja klienta OpenAI
client = initialize_openai()
if not client:
    st.stop()

def split_audio(audio_path, max_size_mb=25):
    """Dzieli plik audio na części o maksymalnym rozmiarze"""
    try:
        # Wczytanie pliku audio używając librosa
        y, sr = librosa.load(audio_path)
        
        # Obliczenie rozmiaru jednej sekundy audio
        bytes_per_second = sr * y.itemsize
        
        # Obliczenie maksymalnej długości fragmentu w sekundach
        max_seconds = (max_size_mb * 1024 * 1024) / bytes_per_second
        
        # Obliczenie liczby fragmentów
        total_seconds = len(y) / sr
        num_chunks = math.ceil(total_seconds / max_seconds)
        
        chunks = []
        for i in range(num_chunks):
            start_sample = int(i * max_seconds * sr)
            end_sample = int(min((i + 1) * max_seconds * sr, len(y)))
            chunk = y[start_sample:end_sample]
            
            # Zapisanie chunka do tymczasowego pliku
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            sf.write(temp_file.name, chunk, sr)
            chunks.append(temp_file.name)
        
        return chunks
    except Exception as e:
        st.error(f"Błąd podczas dzielenia pliku audio: {str(e)}")
        raise

def transcribe_audio(client, audio_path):
    """Transkrybuje pojedynczy plik audio"""
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                response_format="text"
            )
        return transcript
    except Exception as e:
        st.error(f"Błąd podczas transkrypcji: {str(e)}")
        return None

def save_to_word(text, filename="transkrypcja.docx"):
    """Zapisuje tekst do pliku Word"""
    doc = Document()
    doc.add_paragraph(text)
    
    doc_buffer = io.BytesIO()
    doc.save(doc_buffer)
    doc_buffer.seek(0)
    
    return doc_buffer

# Interface użytkownika
uploaded_file = st.file_uploader("Wybierz plik audio", type=['mp3', 'wav', 'm4a', 'ogg'])

if uploaded_file:
    # Przycisk do rozpoczęcia transkrypcji
    if st.button("Rozpocznij transkrypcję"):
        with st.spinner('Przetwarzanie pliku audio...'):
            # Zapisz uploadowany plik tymczasowo
            temp_input = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_input.write(uploaded_file.getvalue())
            temp_input.close()
            
            try:
                # Podziel na części
                chunks = split_audio(temp_input.name)
                
                # Transkrybuj każdą część
                st.session_state.full_transcript = ""
                progress_bar = st.progress(0)
                
                for i, chunk_path in enumerate(chunks):
                    transcript = transcribe_audio(client, chunk_path)
                    if transcript:
                        st.session_state.full_transcript += transcript + "\n"
                        progress_bar.progress((i + 1) / len(chunks))
                    
                    # Usuń tymczasowy plik
                    if os.path.exists(chunk_path):
                        os.unlink(chunk_path)
                
                # Usuń oryginalny tymczasowy plik
                if os.path.exists(temp_input.name):
                    os.unlink(temp_input.name)
                
                st.session_state.transcription_done = True
                
            except Exception as e:
                st.error(f"Wystąpił błąd podczas przetwarzania pliku: {str(e)}")
                # Upewnij się, że pliki tymczasowe zostaną usunięte
                if os.path.exists(temp_input.name):
                    os.unlink(temp_input.name)

    # Wyświetl transkrypcję i przycisk do pobrania tylko jeśli transkrypcja została wykonana
    if st.session_state.transcription_done and st.session_state.full_transcript:
        st.subheader("Transkrypcja:")
        st.text_area("", st.session_state.full_transcript, height=300)
        
        # Przycisk do pobrania pliku Word
        doc_buffer = save_to_word(st.session_state.full_transcript)
        st.download_button(
            label="Pobierz jako dokument Word",
            data=doc_buffer,
            file_name="transkrypcja.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )