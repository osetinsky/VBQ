DEFAULT_VIDEO=video_sample.mp4
DEFAULT_AUDIO=audio_sample.wav
ANALYSIS_DIR=./analysis

prep-analysis-dir:
	mkdir -p $(ANALYSIS_DIR)

build:
	docker-compose build

run-default: prep-analysis-dir build
	docker-compose run --rm vbq --video /app/data/$(DEFAULT_VIDEO) --audio /app/data/$(DEFAULT_AUDIO)

run: prep-analysis-dir build check-args
	docker-compose run --rm vbq --video /app/data/$(VIDEO) --audio /app/data/$(AUDIO)

check-args:
ifndef VIDEO
	$(error VIDEO is undefined. Use make run VIDEO=your_video.mp4 AUDIO=your_audio.mp3)
endif
ifndef AUDIO
	$(error AUDIO is undefined. Use make run VIDEO=your_video.mp4 AUDIO=your_audio.mp3)
endif