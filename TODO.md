## Priority

- node can "conceal" ancestry (to reader and/or language model) 

- masking
    - mask subtree
        - option to automatically mask new chapters
        - test if this makes splitting faster on huge tree
        - should all *collapsed* nodes be masked by default?
            - but I want "open" state to be property of session, not tree?
            - should all masking belong to a *session mask*?
    - function to check if a node is masked
    
- tags
    - tag config
        - nav tree foreground / background
        - reset
        - change order
    - convert to tags
        - visited
        - AI / prompt
        - edited
        - fix deprecated tags function
    - search tags
    - redistribute tags when merging nodes
    - transform one tag into another
    - clear tags
    - delete all with tag 
    - *new* tags of zipped node (or same rules as split)
        - should these tags be assigned at tagging time?
    - no deleting program tags (archive, pin, notes, visited, AI/prompt, edited)
- fix everything that uses old data format
    - wavefunction
    - autocomplete
    - diff / optimization logging
- repair autocomplete


- test click goto commands
    - alter for read mode

- vis expanded state out of sync with nav tree expanded state

- substitute (node)

- adopt grandparent hotkey
- make top level sibling hotkey
- move to chapter head hotkey

- export visible tree / prune hidden nodes

- edit textbox directly causes branch from nearest unmodified ancestor?
    - compare verbatim text
    - ask whether to create new branch or overwrite old

- bring selected node out of Model
    - should be with Display?
    - multiple selected nodes

- fix reverse
    - also reverse nav direction when nav tree is reversed
    - changing reverse in preferences doesn't cause update to nav tree

- summaries 
    - with context
    - suggest summaries in summary dialog
    - prompt to partition long text into summaries

- icons showing up for ancestry scope?

- scroll to beginning of node text when navigating?

- refactor generate edit stack
    - when nodes fail to generate somehow, this sometimes messes up future generations

- test suite

- fix super deprecated search

- create child doesn't open edit mode if focus on nav

- change node order should move node behind / in front of next *visible* sibling

- memory
    - refactor to use dicts like tags
    - enable / disable
    - memory preview box
        - editable?
    - memories of hoisted / compound nodes aren't accessible


- separate nav update events from other events
    - fix hacky solutions for child edit and notes
    
    
- archiving/deleting children textboxes sometimes causes crash with bad text index "tk::anchor1" or anchor3
    
- make everything a module
    - story textbox
    - nav and chapter trees
    - other dialogs
        
- windows
    - hide buttons preference
    - no show hidden option preference
    - bind edit hotkey


- generations data options
    - save in tree file
    - don't save
    - save in backup file
    - handle trying to access nonexistent entry

- save as duplicate button
    - distinct:
        - duplicate subtree
        - duplicate only edited node(without children)
        - save old version as duplicate (new one inherits children)
            - ghostparent connection
            
- preference for whether to navigate to next node or parent

- floating notes should survive when their parent is deleted - move to grandparent?
    - ok if parent is archived though
    
- implement reactive updating for all components and refactor tree_updated callback
    - vis
    - nav tree

- eval
    - run should use exec instead of eval?
    - interpreter

- make add and remove tag methods in controller
        
- text highlighting
    - keyboard
    - mouse
- insertion cursor
    - emacs-like commands

- tabs for suggested modules and dropdown for all

- visible nodes tree object
    - locality / pruning
    - hoisting
    - masks
    - source of truth for nav, visible (not quite - nav is still source of truth)

- code to be executed upon navigating to node

- don't change selection when unhoisting from root node

- tagging a node which was just split results in tagging multiple nodes (revealed or done only when navigating to node - why?)


- inline generation in story textbox
    - hotkey to split node after generation


- ghostchildren and portals
    - ghostchildren have hysteresis: navigating to ghostchild keeps current ancestry
        - how to prevent cycles / duplicates?
            - not a problem if nav render distance is limited?
    - portals just teleport you to another part of the tree

- walk - option to loop to start if no children

- children
    - "hidden children" should include blacklisted windows

- panes
    - pane with no modules should automatically close
    - buttons to open panes
    - top and left pane

- modules
    - modules / workspace menu
    - notes 
        - expand / contract note scope
        - click icon to toggle pin
            - show empty square icon when no tag
    - playground
        - toggle multiple choice or inline (end)
        - integrate with tree
    - minimap 
        - detect size of frame
        - right click
            - edit (in preview textbox)
            - color node / subtree
            - expand / collapse
            - hoist
            - tag...
        - node/subtree color / tag display
            - color according to tag
        - reactive updating
        - selected node highlighted by default; show preview text in textbox
        - export image of minimap
        - auto color by curation metrics
    - paint
        - all layers should be canvases
            - transparent bg
            - merge lines into img when layer changes - "imagify" canvas
                - make canvas lines into transparent png
                - merge drawing png & background png (if background not blank)
        - right click 
            - merge up
            - delete
            - hide
            - change transparency?
    - modules come in two types, ones which can be duplicated (and should have their own settings) and ones which shouldnt
        - ok instances
            - text editor
            - edit
            - playground
            - run
        - not ok
            - notes
            - paint
            - media
            - input
            - children
            - prompt
            - debug
        - ?
            - minimap

- fullscreen / minimize

- zip chain (but not zip all) broken

- override even meta hotkeys in modules

- hotkey to shift words to parent / children

- export
    - export subtree function
    - global objects and frames

- import 
    - throw out immutable root? or convert to normal node

- custom focus out binding for text attribute class

- node events
    - onSelect
    - onExit
    - onEdit
    - global and local
    - tags can be configured to toggle on events

- frames
    - script to delete / reassign old settings
        - chapters, memories, and tags get moved to root frame
    - merging and splitting frames
    - zipping / unzipping frames
    - frame tree
    - edit frame template
    - edit user frame dialog
    - save frame preset
    - frames should be able to reference preset names
        - requires saving frames as strings instead of dicts?


- enable / disable realtime updates for textattributes

- splices
    - links and windows
    - should markup live in text?

- LoomTerminals
    - editable main textbox
        - handle compound nodes
        - ask, branch, forbid modes
    - color by token probability

- interface presets
    - separate "write" into "generate" and "gamify" interfaces
    - "gamify"
        - "edit"
        - frames tree
        - view: reader
    - "generate"/write
        - children
        - notes
        - view: writer (sees everything that reader and AI sees, tagged. sees splices markup?)
    - prompt programming preset
        - transformers
        - playground

- fix vis

- store permanent alternative texts
    - as ghostparents?

- demo
    - tutorial
    - read examples
    - write examples
    - multiverse comics

- NL functions database

- "path" bar

- pretext
    - subsume memories under pretext type
    - memory module
        - enable / disable
        - change automatic inheritability conditions
    - memory collection
    - world info

- num descendents in children preview

- centralized way to synch node and nav tree open states
- tagging nodes causes newly opened nodes to close

- don't open minimap settings 

- version control 
    - option to turn versions into explicit branches (and vice versa?)
    - start a new "branch" and merge
    
- generation settings text attributes f strings?

- update text index stuff to work with templates

- adjust textattribute textbox heights based on content

- decode openAI alt token bytes

- generation preset with preset attribute is terrible

- inline generations in textbox sometimes inserted in wrong indices (after distributing changes?)

- read coloring bug - when text is long?

- edit module pin doesn't work right

- empty nodes with auto walk
    - as a way to group options

## Other TODO

### bugs

* crashes with this error sometimes: `_tkinter.TclError: bad text index "tk::anchor1"`
* key bindings only work in most recent tab
* num leaves calculated incorrectly
* ctrl+space sometimes clicks button
* ctrl+y hotkey (chapter dialog) sometimes doesn't work
* clicking textbox sometimes causes index error
* display history bug - seen with astronomer -> spirals (try disabling context window highlighting)
* reinserting into nav tree causes change in node ordering
* various bugs splitting, merging (seems to have been caused by partial nav updating?)
* memory (what?) causes freeze?
* mark as prompt doesn't always work? or display doesnt update
* generating when trying to calculate optimization bits??
* merge with children is broken?
* change chapter dialog doesn't show up when hotkey pressed depending on focus
* after the first counterfactual substitution via select node, other selections will be misaligned
* visited state sometimes doesn't update
* split node sometimes causes string/int index comparison error?

### problems
* saving and inserting into nav tree is slow for massive trees
* rebuild view children frame is slow (enough to be annoying)
    - textboxes are being rebuilt multiple times when tree updated

### Deprecated
- OpenAI logprob format. Use loom-specific format now for everything
    - node-specific meta.generation dictionary

#### To deprecate
- node-specific "visited" status (move to session file?)

### Model response data
- option to not save model response data
- option to clear model response data (and save backup)
    - handle key error


### Tokenization
- change gpt2 tokenizer import so loom doesn't require internet connection to run
    - use ada to tokenize instead? will this cause lag?
    - GPT2 tokenizer local files?


### Models 
- model-agnostic interface
- integrate other models
    - GPT-J 
    - GPT-2

### Masking / zipping
- auto-collapse chains in read mode
- transform compound node into regular node
- root
    - when attempt to edit hoisted root, ask to unhoist (instead of unzip)
- interactions with canonical, chapters


### Usability 
- all hotkeys dialog

### Tree manipulation
- swap node function
- split node and merge second part with children 
    - hotkey

### Display
- global "read" mode (separate from coloring)
- show multimedia inline
- if node has only one (visible) child, display as a single node
    - enabled by default in read mode


### "Floating" nodes
- floating subtree associated with root node and accessible in subtree(or path, node)



### Navigation
- multiple checkpoints - hotkey returns to nearest checkpoint in ancestry
- return to chapter root hotkey (r) (shift-r goes to root)
    - if no chapter, return to root
- jump to unvisited nodes



### Interface
- open new tab/window on same working copy of tree
- minibuffer for commands


### Preventing data loss
- log gpt-3 output files
- ask before quitting if unsaved changes



### Attributes and filtering

- filter by arbitrary attributes (canonical, created_after, etc)
    - create an attribute
        - scope types: node (bookmark, archived), node+ancestry (canonical), node+subtree (chapter), node+ancestry+subtree
            - let's call it path and subtree
    - has_attribute() function
    - handle navigating to / creating a hidden node
    - hide chapters without root (?) or nodes
    

### archived
- visually indicate archived nodes in nav tree when hide_archived=False (~ or different color?)
     

### session files: separate session from underlying tree?
- visited
- active node
- expanded state
- settings... 

### Generation
- generation 
    - multiverse generation options (depth, branching factor, branching interval/conditions)
  
- gpt modes     
    - account for additional prompt length (abstract)
    - save generation mode metadata
    - stop at newline generation mode

- chat
    - don't show restart text
 
- presets
    - toggle whether context appears in textbox
    - toggle whether context remains in prompt
    - antisummary is different - its a program, not just generation mode. remove for now





### Metadata
- diff
    - splitting / merging
    - display in node info or diff dialog
    
- optimization logging
    - selection
    - manual editing
    - autocomplete


### Memory
- memory
    - enable/disable memory entries
    - goto root 


### Autocomplete
* sometimes freezes
* replace sentence/highlighted section functionality
    * generates sentence by sentence / line by line
* edit mode and vis
* longer range suggestions mode?
* save counterfactuals?

### Hoist
* REFACTOR hoist to use a mask?
    * pros: able to save hoist state; more elegant
    * cons: unhoist all more difficult?
* handle navigating to node outside subtree (expand to common ancestor of current and new node?) (see handle navigating to masked node)
* option to automatically hoist when new chapter
* pack hoist/unhoist/unhoist all buttons more compactly
* re-center view if in vis


### Edit mode
- preview text
    - show in read multi mode in space of node text
- preview and active textboxes hidden by default unless there is preview / active text
    - buttons(?) to show textboxes


### Multi mode
- build and populate in single function (allows custom height)
- update when tree updated
    - remove any children that have been deleted
- frame height when nodes are unevenly sized
- adjustable frame height
- remove child edit mode code
- hide button in visualize and wavefunction modes
- button to show archived / hidden options (indicate #)
- enable undo
- show canonical first
- test
    - test for bugs switching to vis mode etc
- "Read" multi mode 
    - option to override preview text
- move multi display code to new object
- change order of children in multi mode
- remove new child button - make normal new child button behave different if children shown?



### Block multiverse

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
* generating multiverse also adds branches to loom tree (but labeled different so they don't clutter everything up?)
* choose continuation by autocomplete / hotkeys
* commands to go to parent, go to sibling, walk
* fix precision errors



### Tree vis

#### Bugs
* tree vis settings won't change on newly opened file
* tree vis duplication when zooming
* collapse all sometimes causes duplication?
* text width when zooming: save defaults
* zooming causes misalignment
* fix vertical mode
* icons sometimes do not zoom
* different icon colors for light mode
* vis expanded state out of sync with nav tree expanded state

#### Features

* mark as visited in tree mode
* save vis settings
* increase offsets when text is too long OR scrollbar OR pages
* collapsed nodes don't need their own column / variable offsets
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

* show history in nodes option
* move at finite speed (animation)


# Windows

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


# versioning
* save version each time node is edited
* save origin information (prompt, logprobs, merge or branch)
* undo


# Search
* enter to search
* search chapter titles
* search tags
* regex
* integrated (inline) search
* key filter -> semantic search among matches

# Features

* "floating" notes
    * global or associated with subtree
* save open status (not visible status) in tree dict 
* named bookmarks
* bookmarks (unique) vs tags (category) 
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

### chapter

- chapter hierarchy
- collapse all but chapter subtree

### floating notes

- floating trees
    - access scopes. single note, subtree, global, subtree and ancestry
- attach and detach subtree
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