# p.osetinsky@gmail.com
# revised by LLMs

from concurrent.futures import ThreadPoolExecutor, as_completed
import ffmpeg
import librosa
import numpy as np
import json
import argparse
import subprocess
import os
import math
import sys
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from tqdm import tqdm

def detect_scenes(video_path, threshold=0.4):
    """
    Detects scene changes in the given video file.

    Args:
    - video_path: Path to the video file.
    - threshold: Sensitivity threshold for scene change detection. Higher values result in fewer scenes.

    Returns:
    - A list of tuples, where each tuple contains the start and end time (in seconds) of a scene.
    """
    # Construct the ffmpeg command to detect scene changes
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-filter:v', f'select=\'gt(scene,{threshold})\',showinfo',
        '-f', 'null',
        '-',
    ]

    # Execute the ffmpeg command and capture the output
    result = subprocess.run(cmd, capture_output=True, text=True)
    scenes = []
    current_scene_start = None
    last_time = 0  # Keep track of the last time for the final scene

    # Parse the ffmpeg output to find scene change information
    for line in result.stderr.split('\n'):
        if 'showinfo' in line and 'pts_time:' in line:
            parts = line.split('pts_time:')
            if len(parts) > 1:
                time_str = parts[1].split(' ')[0]
                time = float(time_str)  # float conversion preserves milliseconds for precision
                if current_scene_start is None:
                    current_scene_start = time
                else:
                    scenes.append((current_scene_start, time))
                    current_scene_start = time
                last_time = time  # Update the last time


    # Add the last scene if the video doesn't end with a detected scene change
    if current_scene_start is not None and last_time > current_scene_start:
        scenes.append((current_scene_start, last_time))

    return scenes

def extract_scene_segment(video_path, start_time, end_time, output_path):
    """
    Extracts a segment from a video based on start and end times, saving to a specified output path.

    Args:
    - video_path: Path to the video file.
    - start_time: The start time of the segment (in seconds).
    - end_time: The end time of the segment (in seconds).
    - output_path: The output path for the extracted segment.
    """
    # Calculate the duration of the segment
    duration = end_time - start_time

    # Command to extract the segment using ffmpeg
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output files without asking
        '-i', video_path,  # Input file
        '-ss', f"{start_time:.3f}",  # Start of the segment, with milliseconds
        '-t', f"{duration:.3f}",  # Duration of the segment, with milliseconds
        output_path  # Output file
    ]

    # Execute the ffmpeg command
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Failed to extract segment: {e.stderr.decode()}")

        
def adjust_scene_to_beat(scene_start, scene_end, beat_times):
    # Find the nearest beat after the scene's end
    nearest_beat = min(beat_times, key=lambda x:abs(x-scene_end) if x > scene_end else float('inf'))
    
    # Calculate the new duration based on this beat
    new_duration = nearest_beat - scene_start
    original_duration = scene_end - scene_start
    
    # Calculate the required playback speed adjustment
    playback_speed = original_duration / new_duration if new_duration > 0 else 1
    
    return playback_speed, nearest_beat

def adjust_video_segment_speed(segment_path, playback_speed, adjusted_segment_path):
    """
    Adjusts the playback speed of a video segment, removing original audio.

    Args:
    - segment_path: Path to the original segment file.
    - playback_speed: The desired playback speed (e.g., 0.8 for slower, 1.2 for faster).
    - adjusted_segment_path: Path to save the adjusted segment file.
    """
    # Video filter to adjust speed
    vf = f"setpts={1/playback_speed}*PTS"
    
    cmd = [
        'ffmpeg',
        '-i', str(segment_path),
        '-filter:v', vf,  # Apply the video filter
        '-an',  # Drop the audio
        str(adjusted_segment_path),
        '-y'  # Overwrite output files without asking
    ]

    # Execute the ffmpeg command
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Failed to adjust segment speed: {e.stderr.decode()}")


def concatenate_segments(segment_paths, output_path):
    """
    Concatenates video segments into a single video file.

    Args:
    - segment_paths: List of paths to the video segments.
    - output_path: Path for the concatenated video file.
    """
    with open("concat_list.txt", "w") as f:
        for segment_path in segment_paths:
            f.write(f"file '{segment_path}'\n")
    
    concat_cmd = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', 'concat_list.txt',
        '-c', 'copy',
        '-an',  # Ensure no audio is included in the output
        output_path,
        '-y'
    ]
    subprocess.run(concat_cmd, check=True)
    os.remove("concat_list.txt")  # Clean up the temporary file


def overlay_audio(video_path, audio_path, output_path):
    """
    Overlays an audio track onto a video file, replacing any existing audio.

    Args:
    - video_path: Path to the video file.
    - audio_path: Path to the audio file to overlay.
    - output_path: Path to save the video file with the overlaid audio.
    """
    overlay_cmd = [
        'ffmpeg',
        '-i', video_path,
        '-i', audio_path,
        '-c:v', 'copy',  # Copy the video stream as is
        '-map', '0:v:0',  # Use video from the first input
        '-map', '1:a:0',  # Use audio from the second input
        '-shortest',  # End the output based on the shortest input stream
        output_path,
        '-y'
    ]
    subprocess.run(overlay_cmd, check=True)

def play_video(video_path):
    try:
        if sys.platform.startswith('darwin'):
            subprocess.run(['open', video_path], check=True)
        elif sys.platform.startswith('win32') or sys.platform.startswith('cygwin'):
            subprocess.run(['start', video_path], shell=True, check=True)
        elif sys.platform.startswith('linux'):
            subprocess.run(['xdg-open', video_path], check=True)
        else:
            raise ValueError(f"Unsupported operating system: {sys.platform}")
        print(f"Playing video: {video_path}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to play video {video_path}: {e}")

def create_analysis_dir_structure(base_dir="analysis"):
    """Create directory structure for analysis including timestamped subdirectories."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_path = Path(base_dir) / timestamp
    raw_segments_path = base_path / "raw_segments"
    adjusted_segments_path = base_path / "adjusted_segments"
    outputs_path = base_path / "outputs"
    
    # Create the directory structure
    for path in [raw_segments_path, adjusted_segments_path, outputs_path]:
        path.mkdir(parents=True, exist_ok=True)
    
    return base_path, raw_segments_path, adjusted_segments_path, outputs_path

def sync_video_to_beat(video_path, audio_path, threshold=0.4):
    logging.info("Beat detection started.")
    try:
        y, sr = librosa.load(audio_path)
        _, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        logging.info("Beat detection completed.")
    except Exception as e:
        logging.error(f"Beat detection failed: {e}")
        raise

    logging.info("Scene detection started.")
    try:
        scenes = detect_scenes(video_path, threshold)
        logging.info(f"Scene detection completed. {len(scenes)} scenes detected.")
    except Exception as e:
        logging.error(f"Scene detection failed: {e}")
        raise

    base_path, raw_segments_path, adjusted_segments_path, outputs_path = create_analysis_dir_structure("analysis")

    # Extract video segments
    logging.info("Scene extraction started.")
    with ThreadPoolExecutor(max_workers=int(os.getenv('MAX_WORKERS', '8'))) as executor:
        futures = [executor.submit(extract_scene_segment, video_path, scene_start, scene_end, str(raw_segments_path / f"segment_{index}.mp4")) for index, (scene_start, scene_end) in enumerate(scenes)]
        
        for future in tqdm(as_completed(futures), total=len(futures), desc="Extracting Scenes"):
            try:
                future.result()
                logging.info(f"Scene extracted successfully.")
            except Exception as exc:
                logging.error(f"Failed to extract scene: {exc}")
                raise Exception("Scene extraction failed.")

    logging.info("Scene extraction completed.")

    # Adjust playback speed of extracted segments
    logging.info("Scene adjustment started.")
    adjusted_segment_paths = []
    with ThreadPoolExecutor(max_workers=int(os.getenv('MAX_WORKERS', '8'))) as executor:
        futures = []
        for index, (scene_start, scene_end) in enumerate(scenes):
            raw_segment_path = raw_segments_path / f"segment_{index}.mp4"
            adjusted_segment_path = adjusted_segments_path / f"segment_{index}_adjusted.mp4"
            playback_speed, _ = adjust_scene_to_beat(scene_start, scene_end, beat_times)
            futures.append(executor.submit(adjust_video_segment_speed, str(raw_segment_path), playback_speed, str(adjusted_segment_path)))
            adjusted_segment_paths.append(adjusted_segment_path)
        
        for future in tqdm(as_completed(futures), total=len(futures), desc="Adjusting Scenes"):
            try:
                future.result()
                logging.info(f"Scene adjusted successfully.")
            except Exception as exc:
                logging.error(f"Failed to adjust scene: {exc}")
                raise Exception("Scene adjustment failed.")

    logging.info("Scene adjustment completed.")

    # Concatenate adjusted video segments
    concatenated_video_path = outputs_path / "concatenated_video.mp4"
    logging.info("Concatenation started.")
    try:
        concatenate_segments([str(path) for path in adjusted_segment_paths], str(concatenated_video_path))
        logging.info("Concatenation completed successfully.")
    except Exception as e:
        logging.error(f"Concatenation failed: {e}")
        raise

    # Overlay audio on the concatenated video
    final_output_path = outputs_path / "final_output.mp4"
    logging.info("Audio overlay started.")
    try:
        overlay_audio(str(concatenated_video_path), audio_path, str(final_output_path))
        logging.info("Audio overlay completed successfully.")
    except Exception as e:
        logging.error(f"Audio overlay failed: {e}")
        raise

    logging.info("Video analysis completed. Final video is ready.")

    # Play the final video
    # play_video(str(final_output_path))


def main():
    parser = argparse.ArgumentParser(description='Sync video scenes to music beats.')
    parser.add_argument('--video', required=True, help='Path to the video file')
    parser.add_argument('--audio', required=True, help='Path to the audio file')
    parser.add_argument('--threshold', type=float, default=0.4, help='Scene change detection threshold')

    args = parser.parse_args()

    sync_video_to_beat(args.video, args.audio, args.threshold)

if __name__ == '__main__':
    main()