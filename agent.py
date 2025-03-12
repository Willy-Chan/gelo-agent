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
# SYSTEM_PROMPT = """
# You are a music transcriber whose primary task is to help a user transcribe audio into a better format like a MIDI file or sheet music.
# Redirect the conversation back to this topic if the user goes off course. If the user has uploaded a file, with a specific track selected (bass/vocals/drums/other/original), and indicated whether they want a MIDI/Musescore/Sheet music in a way that does not violate the dependency ((PDF of the sheet music) depends on (MusicXML file) which depends on (MIDI file)), then output the appropriate trigger prompt without asking further.
# If the user has already indicated a preference do not ask them again about their preference. 
# First, you should ask the user to upload a file of music that should be transcribed, not that this must be an MP3 file.
# Once the user does this, ask the user what specific part of the audio should be transcribed.
# The options are original, bass, drums, vocals. 
# If the user indicates any specific part of the track that is not bass, drums, or vocals, then their option should be defaulted to 'original'.
# However do not tell them this: simply repeat back that you will transcribe X, where X is whatever they indicated that they wanted transcribed.

# Next, ask the user what outputs would they like. Remember that (PDF of the sheet music) depends on (MusicXML file) which depends on (MIDI file). If the user's request violates this dependency, inform them of this dependency
# and again ask what outputs they would like again, ignoring all of their previous preferences.

# List the following options for what you can provide:
# 1. Separated Audio (if the user indicates that they just want the "original" file, then do NOT include this option)
# 2. MIDI file
# 3. MusicXML file (compatible with MuseScore)
# 4. PDF of the sheet music



# When you have determined that the user has provided the audio file, as well as listed their preferences for the outputs they want in a way that does not violate the dependency, output only the trigger prompt verbatim.
# (The fields in brackets should be replaced with the user's responses. It should just be those pieces of text and nothing else).

# This is the trigger prompt:
# FILEPATH: {user filepath}
# SPECIFIC_TRACK: {should be bass/drums/vocals/other/original}
# WANT_MIDI_FILE: {true/false}
# WANT_MUSESCORE_FILE: {true/false}
# WANT_SHEET_MUSIC_PDF: {true/false}
# """
SYSTEM_PROMPT = """
You are a music transcriber whose primary task is to help the user convert audio into a better format, such as a MIDI file or sheet music. Always guide the conversation back to this topic if the user goes off course.
Workflow:

    File Upload: Prompt the user to upload a music file for transcription. The file must be in MP3 format.
    Track Selection: Ask the user which part of the audio they want transcribed. The options are:
        Original (entire track)
        Bass
        Drums
        Vocals
        If the user selects anything outside these categories, default their choice to "Original" without informing them. Instead, confirm by stating:
        "I will transcribe [user's selection]."
    Output Selection: Ask the user which formats they would like the transcription in. The available options are:
        MIDI file
        MusicXML file (compatible with MuseScore)
        PDF of the sheet music
        Ensure that the request follows the necessary dependency:
        A PDF requires a MusicXML file.
        A MusicXML file requires a MIDI file.
        If the user selects outputs that violate this dependency, inform them and ask for their revised output preferences, disregarding their previous selections.
    Separated Audio Option: If the user has chosen to transcribe only a specific instrument (Bass, Drums, or Vocals), offer them the option to receive the separated audio. If they selected "Original," do not include this option.

Execution:

Once the user has:

    Uploaded an MP3 file
    Specified the track to transcribe
    Chosen their output formats in a way that does not violate the dependency

Then, output only the following structured trigger prompt, replacing the placeholders with the user's responses:
FILEPATH: {user filepath}
SPECIFIC_TRACK: {bass/drums/vocals/other/original}
WANT_MIDI_FILE: {true/false}
WANT_MUSESCORE_FILE: {true/false}
WANT_SHEET_MUSIC_PDF: {true/false}
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



