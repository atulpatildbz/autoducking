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

def create_volume_envelope(audio_length, silence_periods, fade_duration=0.1):
    envelope = np.zeros(audio_length)  # Start with all zeros (fully ducked)
    sample_rate = 1000  # 1ms resolution
    
    for start, end in silence_periods:
        start_idx = int(start * sample_rate)
        end_idx = min(int(end * sample_rate), audio_length)
        fade_samples = int(fade_duration * sample_rate)
        
        # Ensure fade doesn't exceed silence period
        fade_samples = min(fade_samples, (end_idx - start_idx) // 2)
        
        # Create fade in (from ducked to full volume)
        fade_in = np.linspace(0, 1, fade_samples)
        envelope[start_idx:start_idx+fade_samples] = fade_in[:len(envelope[start_idx:start_idx+fade_samples])]
        
        # Set silence period to 1 (full volume)
        envelope[start_idx+fade_samples:end_idx-fade_samples] = 1
        
        # Create fade out (from full volume to ducked)
        fade_out = np.linspace(1, 0, fade_samples)
        envelope[end_idx-fade_samples:end_idx] = fade_out[:len(envelope[end_idx-fade_samples:end_idx])]
    
    return envelope

def apply_ducking(voiceover_file, music_file, output_file, duck_amount=-10):
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
    envelope = create_volume_envelope(int(voiceover_duration * 1000), silence_periods)
    
    # Load audio files
    voiceover = AudioSegment.from_file(voiceover_file)
    music = AudioSegment.from_file(music_file)
    
    # Ensure music is as long as voiceover
    if len(music) < len(voiceover):
        music = music * (len(voiceover) // len(music) + 1)
    music = music[:len(voiceover)]
    
    # Convert envelope to dB scale
    db_envelope = np.where(envelope > 0, 0, duck_amount)  # 0 dB for full volume, duck_amount for ducked
    
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
    output = voiceover.overlay(ducked_music)
    
    # Export the result
    output.export(output_file, format="mp3")
    print(f"Output file created: {output_file}")

# Usage
voiceover_file = "voiceover.mp3"
music_file = "music.mp3"
output_file = "output_with_ducking.mp3"

apply_ducking(voiceover_file, music_file, output_file)
