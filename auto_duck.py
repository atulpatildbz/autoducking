import subprocess
import json
import numpy as np
from pydub import AudioSegment
from pydub.utils import make_chunks

def get_audio_info(filename):
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', filename
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running ffprobe: {e}")
        return None

def detect_silence(filename, silence_threshold=-30, min_silence_len=0.1):
    cmd = [
        'ffmpeg', '-i', filename, '-af',
        f'silencedetect=noise={silence_threshold}dB:d={min_silence_len}',
        '-f', 'null', '-'
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stderr  # FFmpeg outputs to stderr for this command
    except subprocess.CalledProcessError as e:
        print(f"Error running FFmpeg: {e}")
        return []
    
    silence_periods = []
    for line in output.split('\n'):
        if 'silence_start' in line:
            start = float(line.split('silence_start: ')[1])
            silence_periods.append([start, None])
        elif 'silence_end' in line:
            end = float(line.split('silence_end: ')[1].split(' ')[0])
            if silence_periods and silence_periods[-1][1] is None:
                silence_periods[-1][1] = end
    
    return silence_periods

def create_smooth_envelope(audio_length, silence_periods, transition_duration=0.3):
    envelope = np.zeros(audio_length)  # Start with all zeros (fully ducked)
    sample_rate = 1000  # 1ms resolution
    transition_samples = int(transition_duration * sample_rate)
    
    for start, end in silence_periods:
        start_idx = max(0, int(start * sample_rate) - transition_samples)
        end_idx = min(audio_length, int(end * sample_rate) + transition_samples)
        
        # Create smooth transition using a sine wave
        transition = np.sin(np.linspace(0, np.pi, end_idx - start_idx)) * 0.5 + 0.5
        envelope[start_idx:end_idx] = np.maximum(envelope[start_idx:end_idx], transition)
    
    return envelope

def apply_ducking(voiceover_file, music_file, output_file, duck_amount=-10, music_tail=5):
    # Get audio information
    voiceover_info = get_audio_info(voiceover_file)
    music_info = get_audio_info(music_file)
    
    if not voiceover_info or not music_info:
        print("Failed to get audio information. Exiting.")
        return
    
    voiceover_duration = float(voiceover_info['format']['duration'])
    
    # Detect silence in voiceover
    silence_periods = detect_silence(voiceover_file)
    
    if not silence_periods:
        print("No silence periods detected. The output may not have any ducking effect.")
    
    # Create volume envelope
    envelope = create_smooth_envelope(int(voiceover_duration * 1000), silence_periods)
    
    # Load audio files
    voiceover = AudioSegment.from_file(voiceover_file)
    music = AudioSegment.from_file(music_file)
    
    # Ensure music is as long as voiceover plus the tail
    total_duration = len(voiceover) + (music_tail * 1000)
    if len(music) < total_duration:
        music = music * (total_duration // len(music) + 1)
    music = music[:total_duration]
    
    # Extend the envelope for the music tail
    extended_envelope = np.concatenate([envelope, np.ones(music_tail * 1000)])
    
    # Convert envelope to dB scale
    db_envelope = np.where(extended_envelope > 0, 0, duck_amount)  # 0 dB for full volume, duck_amount for ducked
    
    # Apply ducking
    chunk_length = 100  # 100ms chunks for more precise ducking
    ducked_chunks = []
    for i, chunk in enumerate(make_chunks(music, chunk_length)):
        start = i * chunk_length
        end = min(start + chunk_length, len(db_envelope))
        chunk_envelope = db_envelope[start:end]
        avg_gain = float(np.mean(chunk_envelope))
        ducked_chunk = chunk.apply_gain(avg_gain)
        ducked_chunks.append(ducked_chunk)
    
    ducked_music = sum(ducked_chunks, AudioSegment.empty())
    
    # Mix voiceover and ducked music
    output = voiceover.overlay(ducked_music[:len(voiceover)])
    
    # Add the music tail
    output += ducked_music[len(voiceover):]
    
    # Export the result
    output.export(output_file, format="mp3")
    print(f"Output file created: {output_file}")

# Usage
voiceover_file = "voiceover.mp3"
music_file = "music.mp3"
output_file = "output_with_ducking.mp3"

apply_ducking(voiceover_file, music_file, output_file, duck_amount=-10, music_tail=5)
