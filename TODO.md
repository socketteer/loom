# priority 

replace sentence/highlighted section functionality
    - generates sentence by sentence / line by line

block multiverse svg

autocomplete bug - sometimes freezes

stop at newline generation mode

log gpt-3 output files

add global memory option

ask before quitting if unsaved changes

jump to unvisited nodes

hide display text by default (but button to show?)

minibuffer for commands

- archived
    - navigation which navigates only any (conditional?) subset of tree
        - implemented for node offset (next)
        - nav to child
        - nav to sibling
    - when in hide archived mode, navigation should only go to unarchived nodes
        - deal with case when you navigate to a hidden node anyway (for example using goto)?

- session files: separate session from underlying tree?
    - visited
    - active node
    - expanded state
    - settings... 

- open subtrees only...?

- archiving
    - shortcut to archive nodes

- autocomplete mode
    - edit mode and vis
    - longer range suggestions mode?
    - more than one token for first (worth latency)?
    - save counterfactuals?
    - filter by character input

- generation 
    - logit bias
    - multiverse generation options (depth, branching factor, branching interval/conditions)
  
- gpt modes     
    - account for additional prompt length (abstract)
    - save generation mode metadata
 
- dialogue
    - optimize prompt / multiple modes 
 
- presets
    - save preset
    - toggle whether context appears in textbox
    - toggle whether context remains in prompt

- optimization logging
    - selection
    - manual editing
    - autocomplete

- diff
    - splitting / merging
    - display in node info or diff dialog

- memory system
    - enable/disable memory entries
    - goto root 
 
 
# bugs

* key bindings only work in most recent tab
* num leaves calculated incorrectly
* ctrl+space sometimes clicks button
* ctrl+y hotkey (chapter dialog) sometimes doesn't work
* importing tree causes file to be renamed to name of imported file
* clicking textbox sometimes causes index error
* display history bug - seen with astronomer -> spirals (try disabling context window highlighting)
* saving is slow for massive trees
* reinserting into nav tree causes change in node ordering
* various bugs splitting, merging (seems to have been caused by partial nav updating?)
* memory causes freeze?
* mark as prompt doesn't always work? or display doesnt update
* generating when trying to calculate optimization bits??


### Nav tree

- goto selected node button/command
- hide siblings option
- remove clear chapters button

### Multi mode

- fix story textbox scroll 
- update when tree updated
    - remove any children that have been deleted
- change frame height when editing or adding  
- archive node
- remove child edit mode code
- hide button in visualize and wavefunction modes
- don't show archived nodes (if show_archived disabled)
- test
- enable undo

### Block multiverse

* show more of prompt in past box
* clear multiverse
    * automatically clear multiverse if different root node
* render multiverse in real time (draw after API calls) (IMPOSSIBLE)
* panning
    * track x/y movements
* Fix text zoom / hide too small
* color by differences betweent two multiverses
* top k and top p 
* draw existing loom trajectories as ground truth paths
* cache computed multiverses
* command/button to add wavefunction path to loom tree
* remove invisible widgets (may be necessary if multiverses get too big?)
* generatinng multiverse also adds branches to loom tree (but labeled different so they don't clutter everything up?)
* choose continuation by autocomplete / hotkeys
* commands to go to parent, go to sibling, walk



### Tree vis
* first time switching to vis mode centering bug
* tree vis settings won't change on newly opened file
* tree vis duplication when zooming
* collapse all sometimes causes duplication?
* text width when zooming: save defaults
* zooming causes misalignment
* fix vertical mode
* icons sometimes do not zoom
* different icon colors for light mode
* vis expanded state out of synch with nav tree expanded state

# Tree visualization

* mark as visited in tree mode
* save vis settings
* increase offsets when text is too long OR scrollbar OR pages
* collapsed nodes don't need their own column
* save pointer to offset when drawing tree...
 
* more space after collapsed node
* dynamic icon position
* display collapsed ghostchild position
* ghostchild hysteresis
* chapter colors

* padding

* buttons for chapter and multimedia

- editing: 
global edit mode, where all nodes turn into textboxes, but no zooming?

- collapse nodes when too many are expanded


# Windows

* debugger
* gpt3 stuff
* minimap
* floating notes

# Display
 
* show / hide navtrees
* if scroll position is regressing, add whitespace and keep instead?? (didn't work, need new approach)
* toggle gray history / context window 
* gradient color for text box history
* scroll to top of node by default and hotkey to go to top of node
* change darkmode in program
* highlight when mouseover history
* implement expand/collapse functions in controller
* right sidebar for (everything else)
* toggle highlighting gpt-3 vs user contributions

# Tree topology

* always have secret root node
* create parent for root node
* multiple root nodes (from single empty root?)
    * hotkey to create new root
* add ghostchildren/ghostparents (using hotkey)
* split node
    * deal with metadata
    * option to not nav to split node / otherwise indicate split position
    * in vis and edit mode


# import / export 
* export subtree as json


# versioning
* save version each time node is edited
* save origin information (prompt, logprobs, merge or branch)
* undo


# Search
* enter to search
* search chapters
* regex
* case (in)sensitive
* search ancestry
* integrated search
* key filter -> semantic search among matches

# Features

* "floating" notes
    * global or associated with subtree
* save open status (not visible status) in tree dict 
* named bookmarks
* bookmarks (unique) vs tags (category) 
* make arbitrary node act as root node
    * deal with navigating to node outside subtree (expand to common 
    ancestor of current and new node?)
* developer console
* visited sessions
* preferences dialog

* clickable links in active text

* node edit function in controller which saves version, updates metadata etc

## multimedia

* multimedia dialog
    * change caption
* indicate presence of multimedia in vis, textbox
* display multimedia in sidebar

### GPT-3

* define pre and post prompt
* active side prompts like "Who is the main character in this story?"
* playground-like interface
* load gpt-3 program
* min cutoff length for adaptive branching

### AI memory

**world info**
- import world info json 
- make new entries
- display top n world info entries, which can be individually toggled to be included in AI input    

**memory system**

- importing
    - memories from ancestry
    - by search (multiverse or ancestry)
    - by keying (top n matches) (multiverse or ancestry)
- memory in context: when importing memory, option to navigate surrounding tree
- semantic search
    - search ancestry
        - including context window
        - search only manually saved entries
- when changing memory, option to create new entry vs edit existing one
- create memory entry by highlighting

**saving memory entries**

- toggle automatic memory construction
- all entries are (automatically) indexed in memory
- optional title
- tags
- keys
    - automatically generated keys
- reverse time influence: propagate memory backward


### Story navigation

* "play" mode
    * read only 
* stochastic walk 
    * mode which doesn't count visited nodes
    * depth limit
    * display probabilities
* option to display clickable preview text for children
    * preview text can be overridden
    * children can be flagged as hidden
    
### chapter

- chapter hierarchy
- function to collapse all but chapter subtree

### floating notes

- title and tags
- global or subtree access like memory, except by default the object is edited and a new instance isn't created (maybe memory should be this way too)
    - default deleting only removes pointers
    - option to duplicate note (create new instance from template)
- notes sidebar: boxes on the side which are always editable
- option to minimize/hide without deleting
- reverse time propagation

## non-floating notes 

- notes for a specific node
- can be linked from multiple nodes