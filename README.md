
This is an experimental tree-based writing interface for GPT-3. The code is actively being developed and thus
unstable and poorly documented.

# Features

* Read mode
   * Linear story view
   * Tree nav bar
   * Edit mode


* Tree view
   * Explore tree visually with mouse
   * Expand and collapse nodes
   * Change tree topology
   * Edit nodes in place


* Navigation
   * Hotkeys
   * Bookmarks
   * Chapters
   * 'Visited' state


* Generation
   * Generate N children with GPT-3
   * Modify generation settings
   * Change hidden memory on a node-by-node basis


* File I/O
   * Open/save trees as JSON files
   * Work with trees in multiple tabs
   * Combine trees


# Demo

![](static/readme/read-view.png)
![](static/readme/read-view-light.png)
![](static/readme/tree-view.png)
![](static/readme/tree-view-light.png)
![](static/readme/metadata-light.png)

ooo what features! wow so cool

# Block multiverse mode

[Read this](https://generative.ink/meta/block-multiverse/) for a conceptual explanation of block multiverse interface and demo video

### How to use in loom

1. Click `Wavefunction` button on bottom bar. This will open the block multiverse interface in the right sidebar (drag to resize).
2. Write initial prompt in the main textbox.
3. [Optional] Write ground truth continuation in the gray entry box at the bottom of the block multiverse interface. Blocks in ground truth trajectory will be colored black.
4. Set model and [params](https://generative.ink/meta/block-multiverse/#generation-parameters) in top bar.
5. Click `Propagate` to propagate plot the block multiverse
6. Click on any of the blocks to zoom ("[renormalize](https://generative.ink/meta/block-multiverse/#renormalization)") to that block
7. Click `Propagate` again to plot future block multiverse starting from a renormalized frame
8. Click `Reset zoom` to reset zoom level to initial position
9. Click `Clear` to clear the block multiverse plot. Do this before generating a new block multiverse.

![](static/readme/block-multiverse.png)

# Hotkeys

*Alt hotkeys correspond to Command on Mac*

### File

Open: `o`, `Control-o`

Import JSON as subtree: `Control-Shift-O`

Save: `s`, `Control-s`


### Dialogs

Change chapter: `Control-y`

Preferences: `Control-p`

Generation Settings: `Control-Shift-P`

Visualization Settings: `Control-u`

Multimedia dialog: `u`

Tree Info: `Control-i`

Node Metadata: `Control+Shift+N`

Run Code: `Control+Shift+B`


### Mode / display

Toggle edit / save edits: `e`, `Control-e`

Toggle story textbox editable: `Control-Shift-e`

Toggle visualize: `j`, `Control-j`

Toggle bottom pane: `Tab`

Toggle side pane: `Alt-p`

Toggle show children: `Alt-c`

Hoist: `Alt-h`

Unhoist: `Alt-Shift-h`


### Navigate

Click to go to node: `Control-shift-click`

Next: `period`, `Return`, `Control-period`

Prev: `comma`, `Control-comma`

Go to child: `Right`, `Control-Right`

Go to next sibling: `Down`, `Control-Down`

Go to parent: `Left`, `Control-Left`

Go to previous Sibling: `Up`, `Control-Up`

Return to root: `r`, `Control-r`

Walk: `w`, `Control-w`

Go to checkpoint: `t`

Save checkpoint: `Control-t`

Go to next bookmark: `d`, `Control-d`

Go to prev bookmark: `a`, `Control-a`

Search ancestry: `Control-f`

Search tree: `Control-shift-f`

Click to split node: `Control-alt-click`

Goto node by id: `Control-shift-g`


### Organization

Toggle bookmark: `b`, `Control-b`

Toggle archive node: `!`



### Generation and memory

Generate: `g`, `Control-g`

Inline generate: `Alt-i`

Add memory: `Control-m`

View current AI memory: `Control-Shift-m`

View node memory: `Alt-m`


### Edit topology

Delete: `BackSpace`, `Control-BackSpace`

Merge with Parent: `Shift-Left`

Merge with children: `Shift-Right`

Move node up: `Shift-Up`

Move node down: `Shift-Down`

Change parent: `Shift-P`

New root child: `Control-Shift-h`

New Child: `h`, `Control-h`, `Alt-Right`

New Parent: `Alt-Left`

New Sibling: `Alt-Down`



### Edit text

Toggle edit / save edits: `Control-e`

Save edits as new sibling: `Alt-e`

Click to edit history: `Control-click`

Click to select token: `Alt-click`

Next counterfactual token: `Alt-period`

Previous counterfactual token: `Alt-comma`

Apply counterfactual changes: `Alt-return`

Enter text: `Control-bar`

Escape textbox: `Escape`

Prepend newline: `n`, `Control-n`

Prepend space: `Control-Space`



### Collapse / expand

Collapse all except subtree: `Control-colon`

Collapse node: `Control-question`

Collapse subtree: `Control-minus`

Expand children: `Control-quotedbl`

Expand subtree: `Control-plus`


### View

Center view: `l`, `Control-l`

Reset zoom: `Control-0`



# Instructions

## Linux

0. Make sure you have tkinter installed

    ```sudo apt-get install python3-tk```
1. Setup your python env (should be >= 3.9.13)

        ```python3 -m venv env```
        ```source env/bin/activate```
1. Install requirements

    ```pip install -r requirements.txt```
2. [Optional] Set environmental variables for `OPENAI_API_KEY`, `GOOSEAI_API_KEY`, `AI21_API_KEY` (you can also use the settings options)

    ```export OPENAI_API_KEY={your api key}```
3. Run main.py
4. Load a json tree
5. Read  :)

## Mac
1. `conda create -n pyloom python=3.10`
2. `conda activate pyloom`
3. `pip install -r requirements-mac.txt`
4. set the OPENAI_API_KEY env variable
5. `python main.py`

## Docker

(Only tested on Linux.)

0. [Optional] Edit the Makefile with your API keys (you can also use the settings options)
1. Run the make targets

        ```make build```
        ```make run```
2. Load a json tree
3. Read  :)

# Local Inference with llama-cpp-python
[llama.cpp](https://github.com/ggerganov/llama.cpp) lets you run models locally, and is especially useful for running models on Mac. [https://github.com/abetlen/llama-cpp-python] provides nice installation and a convenient API.

## Setup
1. `conda create -n llama-cpp-local python=3.10; conda activate llama-cpp-local`
2. Set your preferred backend before installing `llama-cpp-python`, as per [these instructions](https://github.com/abetlen/llama-cpp-python?tab=readme-ov-file#supported-backends). For instance, to infer on MPS: `CMAKE_ARGS="-DLLAMA_METAL=on"`
3. `pip install 'llama-cpp-python[server]'`
4. `pip install huggingface-hub`
5. Now you can run the server with whatever .gguf model you desire from Huggingface, i.e: `python3 -m llama_cpp.server --hf_model_repo_id NousResearch/Meta-Llama-3-8B-GGUF --model 'Meta-Llama-3-8B-Q4_5_M.gguf' --port 8009`

## Inference
1. `conda activate llama-cpp-local` and start your llama-cpp-python server.
2. In a new terminal window, activate your `pyloom` environment and run `main.py`
2. Enter configurations for your local model in Settings > Model config > Add model. By default, the llama-cpp-port-8009 model uses the following settings:
```
{
            'model': 'Meta-Llama-3-8B-Q4_5_M',
            'type': 'llama-cpp',
            'api_base': 'http://localhost:8009/v1',
},
```