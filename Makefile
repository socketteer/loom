OPENAI_API_KEY := <your key here>
GOOSEAI_API_KEY := <your key here (you only need one of these)>
AI21_API_KEY := <your key here>


IMAGE := loom

SHELL = /bin/sh

CURRENT_UID := $(shell id -u)
CURRENT_GID := $(shell id -g)

export CURRENT_UID
export CURRENT_GID

install:
	echo "Make sure you are using python version 3.9.13 or over"
	sudo apt install python-tk

build:
	docker build -t $(IMAGE) .

run:
	docker run -it --rm \
		-v $(PWD)/data:/app/data \
		-v $(PWD)/examples:/app/examples \
		-v /tmp/.X11-unix:/tmp/.X11-unix:rw \
		-e DISPLAY=$(DISPLAY) \
		-u=$(CURRENT_UID):$(CURRENT_GID) \
		$(IMAGE)
