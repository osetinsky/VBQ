# Video Beat Quantizer (VBQ)
## Sync videos to songs
VBQ is an experimental tool that aligns scene change onsets of an input video to the detected beat of an input song.

NOTE: it has imperfections that need to be addressed, but this repo provides a framework for syncing audio/video without cropping.

![vbq](https://github.com/po-studio/vbq/assets/1250151/48b1131d-57d8-476e-8f44-2e6dc3c7b45a)

## Quickstart

You'll need Docker running to build and run the application. After running, you should find your output generated within the container on your host machine at:
`/analysis/<timestamped_directory>/outputs/final_output.mp4`

### Demo
`make build`
`make run-default` (uses an example video and audio file)

### Personal usage
`make build`
`make run VIDEO=<my_video.mp4> AUDIO=<my_audio.wav>`

## How It Works
### Video Analysis (ffmpeg)
* Detect scenes with a given sensitivity threshold for what constitutes a scene change. Higher difference threshold value means fewer scenes.
* Extract scenes into video segments for later manipulation based on the audio analysis.

### Audio Analysis (librosa)
* Detect the most salient beat of an input audio file
* Based on the detected beat, calculate timestamps on which the beat falls
* The calculated timestamps will serve as targets with which to align the end times of video segments

### Video Segment Manipulation
For each video segment
* Dtermine the beat timestamp closest to the end-time of that video segment
* Calculate a video playback speed multiplier that will either slightly speed up or slow down the segment in a way that makes its end time fall on the closest beat timestamp

### Concatenation
* Once all extracted segments have had their playback speeds modified, concatenate them
* Apply the audio to the video

## Issues
* Input video and audio that differ greatly in duration should be rejected
* Sometimes segments are overly altered (sped up or slowed down too much). What's missing is a cap on the playback speed multiplier, and a fallback method for how to deal with segments that require too high a level of playback speed manipulation in order to fall on a beat
* Example outputs should include a debugging video that compares the original video to the output video while playing both to the input audio and displaying analysis metrics
* Some scene changes in the output still fall _slightly_ before or after the beat. Find where we need to improve precision
* Move logic for the (a) video extraction and (b) playback speed adjustment out of sync_video_to_beat 
* Ensure / add support for various video and audio file formats
* Optimization: even with concurrency, the execution is too slow. How can we improve perfomance?
* Autoplay output video after execution completes
* Add tests
