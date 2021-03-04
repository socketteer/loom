
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

ooo what features! wow so cool

# Hotkeys



### File

Open: `o`, `Control-o`

Import JSON as subtree: `Control-Shift-O`

Save: `s`, `Control-s`


### Dialogues

Chapter settings: `Control-y`

Generation Settings: `Control-p`

Visualization Settings: `Control-u`

Multimedia dialogue: `u`

Show Info: `i`, `Control-i`

### Mode

Toggle edit: `e`, `Control-e`

Toggle visualize: `j`, `Control-j`

Child edit: `c`


### Navigate

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

Toggle bookmark: `b`, `Control-b`


### Edit topology

Delete: `BackSpace`, `Control-BackSpace`

Generate: `g`, `Control-g`

Merge with Parent: `Shift-Left`

Merge with children: `Shift-Right`

Change parent: `Shift-P`

New Child: `h`, `Control-h`, `Alt-Right`

New Parent: `Alt-Left`

New Sibling: `Alt-Down`


### Edit text

Enter text: `Control-bar`

Escape textbox: `Escape`

Prepend newline: `n`, `Control-n`

Prepend space: `m`, `Control-m`



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

1. Install requirements 

    ```pip install -r requirements.txt```
2. Run main.py
3. Load a json tree
4. Read  :)

