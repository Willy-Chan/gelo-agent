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
SYSTEM_PROMPT = """You are a music transcriber whose primary task is to help a user convert some given audio into sheet music. 
First, you should determine the exact file of the music that needs to be transcribed, and try to redirect the conversation back to this topic if the user goes off course.
If you finally get what looks to be a valid, non-joking file to the audio file, then try to also determine whether or not the user specifically wants the
bass or drums or vocals or other of the song transcribed. Or if the user indicates that they don't care/it's not relevant or the piece is really simple, just default to the original audio file without any separation.

Next, try to understand whether or not they want the MIDI file, the Musescore file, and the sheet music PDF.  
Remember that it is NOT possible to produce the sheet music PDF if the user does not want the musescore file, since producing the sheet music PDF requires creating the musescore file.
Try to get these attributes one at a time: do not ask for all of them at once.


When you are sufficiently satisfied, just output the following text verbatim:


FILEPATH: {user filepath}
SPECIFIC_TRACK: {should be bass/drums/vocals/other/original}
WANT_MIDI_FILE: {true/false}
WANT_MUSESCORE_FILE: {true/false}
WANT_SHEET_MUSIC_PDF: {true/false}


The fields in brackets should be replaced with the user's responses. It should just be those pieces of text and nothing else.
"""


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


    async def indicate_loading(self, loading_message):
        messages = [
            {"role": "system", "content": f"Give me some loading text indicating that the system is currently doing the following: {loading_message}"},
        ]
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )
        return response.choices[0].message.content
    

    async def ask_whether_splitting_necessary(self, ask_msg):
        messages = [
            {"role": "system", "content": ask_msg},
        ]
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )
        return response.choices[0].message.content
    

    async def run_with_history(self, message: discord.Message, history: list):
        """
        Process the message with the history of previous messages.
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in history:
            messages.append({"role": "user", "content": msg})

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )

        msg_content = response.choices[0].message.content

        # Check if the response contains a valid file path
        if msg_content.startswith("GREAT!"):
            # Extract the file path from the response
            file_path = msg_content.split(" ")[-1].strip()
            print(f"Valid file path confirmed: {file_path}")
            return f"Valid file path confirmed: {file_path}"
        else:
            return msg_content



            ##### NOTE: NEED TO HANDLE EVERYTHING IN THIS HISTORY PROMPT. BASICALLY SHOULD TRY TO UNDERSTAND A BUNCH OF USER REQUIREMENTS FIRST, AND THEN RUN ALL OF THE COMMANDS AT ONCE ONE AFTER ANOTHER!




    

    def separate_audio(self, file_path: str):
        """
        Separates the audio file into different stems/tracks using Demucs and returns the paths to the output files.
        """
        output_dir = os.path.join(os.path.dirname(file_path), f'separated_audio_{os.path.basename(file_path)}')
        os.makedirs(output_dir, exist_ok=True)

        # Use Demucs to separate the audio file
        command = f"demucs --out {output_dir} {file_path}"
        subprocess.run(command, shell=True, check=True)

        # Collect the paths to the separated files
        separated_files = {}
        for root, _, files in os.walk(output_dir):
            for file in files:
                track_name = os.path.splitext(file)[0]
                separated_files[track_name] = os.path.join(root, file)

        return separated_files





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
            midi_output_path = os.path.splitext(preprocessed_audio_path)[0] + "_basic_pitch.mid"
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
            return midi_output_path

        else:
            midi_output_path = os.path.splitext(audio_file_path)[0] + "_basic_pitch.mid"
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
            return midi_output_path
        

    def convert_midi_to_musescore(self, midi_file_path: str):
        """
        Converts a MIDI file to a MusicXML file and then to a MuseScore file.
        """
        # Convert MIDI to MusicXML
        midi_score = converter.parse(midi_file_path)
        musicxml_output_path = os.path.splitext(midi_file_path)[0] + ".musicxml"
        midi_score.write('musicxml', fp=musicxml_output_path)
        print(f"MusicXML file saved at: {musicxml_output_path}")

        # Convert MusicXML to PDF using MuseScore's command-line interface
        pdf_output_path = os.path.splitext(midi_file_path)[0] + ".pdf"
        command = f"musescore -o {pdf_output_path} {midi_file_path}"
        subprocess.run(command, shell=True, check=True)
        print(f"PDF file saved at: {pdf_output_path}")

        return musicxml_output_path, pdf_output_path



from basic_pitch.inference import predict_and_save, Model
from basic_pitch import ICASSP_2022_MODEL_PATH
basic_pitch_model = Model(ICASSP_2022_MODEL_PATH)



