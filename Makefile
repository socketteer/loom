IMAGE := loom

SHELL = /bin/sh

CURRENT_UID := $(shell id -u)
CURRENT_GID := $(shell id -g)

export CURRENT_UID
export CURRENT_GID

include .env
export

install: reqs
	echo "Make sure you are using python version 3.9.13 or over"
	sudo apt install python-tk
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt

build: reqs
	docker build -t $(IMAGE) .
	rm requirements.txt

run:
	docker run -it --rm \
		-v $(PWD)/_data:/app/_data \
		-v /tmp/.X11-unix:/tmp/.X11-unix:rw \
		-e DISPLAY=$(DISPLAY) \
		-e OPENAI_API_KEY=$(OPENAI_API_KEY) \
		-e GOOSEAI_API_KEY=$(GOOSEAI_API_KEY) \
		-e AI21_API_KEY=$(AI21_API_KEY) \
		-u=$(CURRENT_UID):$(CURRENT_GID) \
		$(IMAGE)

reqs:
	pip install poetry
	poetry export -f requirements.txt --without-hashes > requirements.txt
