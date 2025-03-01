import os
from mistralai import Mistral
import discord
import subprocess  # Import subprocess to run demucs
import librosa  # Import librosa for audio processing
import soundfile as sf  # Import soundfile to save processed audio
from scipy.io import wavfile
from scipy.signal import butter, lfilter

from music21 import converter, midi  # Import music21 for MIDI to MusicXML conversion


MISTRAL_MODEL = "mistral-large-latest"
SYSTEM_PROMPT = "You are a helpful assistant."     # PUT CONTEXT OF THE SYSTEM HERE




def bandpass_filter(audio_path, lowcut=300, highcut=3000, fs=44100, order=5):
    sr, data = wavfile.read(audio_path)

    # Design Butterworth band-pass filter
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')

    # Apply filter
    filtered_data = lfilter(b, a, data)
    wavfile.write(audio_path, sr, filtered_data.astype(data.dtype))


class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

        self.client = Mistral(api_key=MISTRAL_API_KEY)

    async def run(self, message: discord.Message):
        # The simplest form of an agent
        # Send the message's content to Mistral's API and return Mistral's response

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message.content},
        ]

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )

        return response.choices[0].message.content
    



    def validate_file_path(self, file_path: str) -> bool:
        """
        Validates the file path using Mistral API.
        """
        if os.path.isfile(file_path):
            print(f"Valid file path: {file_path}")
            return True
        else:
            print(f"Invalid file path: {file_path}")
            return False

    def separate_audio(self, file_path: str):
        """
        Separates the audio file into different stems/tracks using Demucs and prints the paths to the output files.
        """
        output_dir = os.path.join(os.path.dirname(file_path), f'separated_audio_{os.path.basename(file_path)}')
        os.makedirs(output_dir, exist_ok=True)

        # Use Demucs to separate the audio file
        command = f"demucs --out {output_dir} {file_path}"
        subprocess.run(command, shell=True, check=True)

        # Print the paths to the separated files
        for root, _, files in os.walk(output_dir):
            for file in files:
                print(os.path.join(root, file))





    def convert_to_midi(self, audio_file_path: str):
        """
        Converts a single audio file to a MIDI file using Basic Pitch.
        """
        if (os.path.basename(audio_file_path) == "vocals"):
            # Preprocess the audio file
            y, sr = librosa.load(audio_file_path, sr=None, mono=True)
            
            # Normalize the audio
            y = librosa.util.normalize(y)
            
            # Apply a high-pass filter to emphasize the melody
            y = librosa.effects.preemphasis(y)

            # Save the preprocessed audio to a temporary file
            preprocessed_audio_path = os.path.splitext(audio_file_path)[0] + ".wav"
            sf.write(preprocessed_audio_path, y, sr)

            bandpass_filter(preprocessed_audio_path)   # basically eliminate unnatural non-vocal frequencies
            
            # Convert the preprocessed audio to MIDI
            midi_output_path = os.path.splitext(preprocessed_audio_path)[0] + ".mid"
            predict_and_save(
                [preprocessed_audio_path],
                os.path.dirname(audio_file_path),
                True,   # bool to control generating and saving a MIDI file to the <output-directory>
                True,  # bool to control saving a WAV audio rendering of the MIDI file to the <output-directory>
                False,   # bool to control saving the raw model output as a NPZ file to the <output-directory>
                False,  # bool to control saving predicted note events as a CSV file <output-directory>
                basic_pitch_model
            )

            # Delete the intermediate preprocessed audio file
            # os.remove(preprocessed_audio_path)
            print(f"MIDI file saved at: {midi_output_path}")

        else:
            midi_output_path = os.path.splitext(audio_file_path)[0] + ".mid"
            predict_and_save(
                [audio_file_path],
                os.path.dirname(audio_file_path),
                True,   # bool to control generating and saving a MIDI file to the <output-directory>
                True,  # bool to control saving a WAV audio rendering of the MIDI file to the <output-directory>
                False,   # bool to control saving the raw model output as a NPZ file to the <output-directory>
                False,  # bool to control saving predicted note events as a CSV file <output-directory>
                basic_pitch_model
            )

            # Delete the intermediate preprocessed audio file
            # os.remove(preprocessed_audio_path)

            print(f"MIDI file saved at: {midi_output_path}")
        

    def convert_midi_to_musescore(self, midi_file_path: str):
        """
        Converts a MIDI file to a MusicXML file and then to a MuseScore file.
        """
        # # Convert MusicXML to MuseScore using MuseScore's command-line interface
        # musescore_output_path = os.path.splitext(midi_file_path)[0] + ".mscz"
        # command = f"musescore -o {musescore_output_path} {midi_file_path}"
        # subprocess.run(command, shell=True, check=True)
        # print(f"MuseScore file saved at: {musescore_output_path}")

        pdf_output_path = os.path.splitext(midi_file_path)[0] + ".pdf"
        command = f"musescore -o {pdf_output_path} {midi_file_path}"
        subprocess.run(command, shell=True, check=True)
        print(f"PDF file saved at: {pdf_output_path}")



from basic_pitch.inference import predict_and_save, Model
from basic_pitch import ICASSP_2022_MODEL_PATH
basic_pitch_model = Model(ICASSP_2022_MODEL_PATH)



