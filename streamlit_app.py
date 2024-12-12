import streamlit as st
import os
from openai import OpenAI
from docx import Document
import math
from pydub import AudioSegment
import tempfile
import io

# Konfiguracja strony Streamlit
st.set_page_config(page_title="Transkrypcja Audio", page_icon="🎤")
st.title("Transkrypcja plików audio")

# Lepsza obsługa inicjalizacji OpenAI
def initialize_openai():
    try:
        # Sprawdź klucz w secrets
        openai_api_key = st.secrets.get("OPENAI_API_KEY")
        if not openai_api_key:
            # Sprawdź zmienną środowiskową jako backup
            openai_api_key = os.environ.get("OPENAI_API_KEY")
        
        if not openai_api_key:
            raise ValueError("Nie znaleziono klucza API OpenAI")
            
        # Podstawowa inicjalizacja bez dodatkowych parametrów
        return OpenAI(api_key=openai_api_key)
    except Exception as e:
        st.error(f"Błąd podczas inicjalizacji API OpenAI: {str(e)}")
        st.error("Upewnij się, że klucz API jest poprawnie skonfigurowany w secrets lub zmiennych środowiskowych.")
        # Wyświetl dostępne secrets (bez pokazywania samego klucza)
        st.write("Dostępne secrets:", list(st.secrets.keys()) if hasattr(st.secrets, 'keys') else "Brak")
        return None

# Inicjalizacja klienta OpenAI
client = initialize_openai()
if not client:
    st.stop()

def split_audio(audio_path, max_size_mb=25):
    """Dzieli plik audio na części o maksymalnym rozmiarze"""
    # Wczytanie pliku audio
    audio = AudioSegment.from_file(audio_path)
    
    # Obliczenie długości jednego fragmentu
    file_size = os.path.getsize(audio_path)
    num_chunks = math.ceil(file_size / (max_size_mb * 1024 * 1024))
    chunk_length_ms = len(audio) // num_chunks
    
    chunks = []
    for i in range(num_chunks):
        start_time = i * chunk_length_ms
        end_time = (i + 1) * chunk_length_ms if i < num_chunks - 1 else len(audio)
        chunk = audio[start_time:end_time]
        
        # Zapisanie chunka do tymczasowego pliku
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        chunk.export(temp_file.name, format="mp3")
        chunks.append(temp_file.name)
    
    return chunks

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
    
    # Zapisz do bufora
    doc_buffer = io.BytesIO()
    doc.save(doc_buffer)
    doc_buffer.seek(0)
    
    return doc_buffer

# Interface użytkownika
uploaded_file = st.file_uploader("Wybierz plik audio", type=['mp3', 'wav', 'm4a', 'ogg'])

if uploaded_file:
    with st.spinner('Przetwarzanie pliku audio...'):
        # Zapisz uploadowany plik tymczasowo
        temp_input = tempfile.NamedTemporaryFile(delete=False)
        temp_input.write(uploaded_file.getvalue())
        temp_input.close()
        
        try:
            # Podziel na części
            chunks = split_audio(temp_input.name)
            
            # Transkrybuj każdą część
            full_transcript = ""
            progress_bar = st.progress(0)
            
            for i, chunk_path in enumerate(chunks):
                transcript = transcribe_audio(client, chunk_path)
                if transcript:
                    full_transcript += transcript + "\n"
                    progress_bar.progress((i + 1) / len(chunks))
                
                # Usuń tymczasowy plik
                os.unlink(chunk_path)
            
            # Usuń oryginalny tymczasowy plik
            os.unlink(temp_input.name)
            
            if full_transcript:
                # Wyświetl transkrypcję
                st.subheader("Transkrypcja:")
                st.text_area("", full_transcript, height=300)
                
                # Przycisk do pobrania pliku Word
                if st.button("Pobierz jako dokument Word"):
                    doc_buffer = save_to_word(full_transcript)
                    st.download_button(
                        label="Pobierz transkrypcję",
                        data=doc_buffer,
                        file_name="transkrypcja.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
        except Exception as e:
            st.error(f"Wystąpił błąd podczas przetwarzania pliku: {str(e)}")
            # Upewnij się, że pliki tymczasowe zostaną usunięte
            if os.path.exists(temp_input.name):
                os.unlink(temp_input.name)