# bugs

* key bindings only work in most recent tab
* have to close tab before opening file
* chapter nav tree scrollbar
* num leaves calculated incorrectly

### Tree vis
* first time switching to vis mode centering bug
* tree vis settings won't change on newly opened file
* tree vis duplication when zooming
* collapse all sometimes causes duplication?
* text width when zooming: save defaults
* zooming causes misalignment
* vertical mode
* view doesn't center when navigating to newly expanded node
* creating new parent in vis mode causes subtree collapse ??
* icons sometimes do not zoom
* edit text box position wrong after zooming (and?)

# Tree visualization


- don't calc tree structure when refreshing
* mark as visited in tree mode
* save vis settings

* increase offsets when text is too long OR scrollbar OR pages
* collapsed nodes don't need their own column
* save pointer to offset when drawing tree...
 
* more space after collapsed node
* dynamic icon position
* use callbacks in tree vis
* display collapsed ghostchild position
* ghostchild hysteresis

- add expand/collapse functions to menu bar

- editing: 
global edit mode, where all nodes turn into textboxes, but no zooming?


# Display
 
* show / hide navtrees
* if scroll position is regressing, add whitespace and keep instead?? (didn't work, need new approach)
* toggle gray history
* highlight context window (toggle)
* gradient color for text box history
* rename node for nav tree
* sidebar adjustable
* display hotkeys window
* scroll at top of chapter by default and hotkey to go to top of chapter
* change darkmode in program

# Modifications


# Tree topology

* create parent for root node
* multiple root nodes
* add ghostchildren/ghostparents (using hotkey)
* visual indication that change parent mode has been toggled

* change order of children


# import / export 
* export subtree as json
* export plaintext of single history


# Features

* search (global or by subtree or in ancestry)
* search chapter titles
* undo
* right sidebar for (everything else)
* "floating" notes
    * global or associated with subtree
* bookmark-like tags define subsets of tree (and option to only display/navigate tag)
* save open status (not visible status) in tree dict 
* click on textbox to edit history
* named bookmarks
* separate bookmarks (unique) and tags (category) 
* open non-root node of json as root node
* make arbitrary node act as root node
    * deal with navigating to node outside subtree (expand to common 
    ancestor of current and new node?)
* ctrl+c copies node text in read/vis modes
* copy ancestry
* split node by clicking/highlighting? is this possible?
* developer console
* mark node (and ancestry) as canonical
* visited sessions

## multimedia

* multimedia dialogue
    * change caption
* indicate presence of multimedia in vis, textbox
* display multimedia in sidebar

### GPT-3

* display logprobs
* view alternative tokens 
    * replace with alternative tokens
* define pre and post prompt
* active side prompts like "Who is the main character in this story?"
* playground-like interface
* load gpt-3 program
* save metadata from gpt-3 calls
* min cutoff length for adaptive branching

### AI memory

**world info**
- import world info json 
- make new entries
- display top n world info entries, which can be individually toggled to be included in AI input    

**memory system**

- semantic search for short-term memory?
- all entries are (automatically) indexed in memory
- memory access modes: multiverse vs single world history
- memory suggestions for easy importing or (toggle) automatic
- memory in context: when importing memory, option to navigate surrounding tree
- save (multiple) memory entries for each node
    - each node automatically inherits parent memory entries (can be edited or deleted)


### Story navigation

* "play" mode
* stochastic walk 
    * mode which doesn't count visited nodes
    * optional depth limit
    * display probabilities
    
    

## "inheritable" attributes (chapter, memory, notes)


### chapter

- different chapter levels
- chapter nav tree
- option to view ancestry as linear chapters
- function to collapse all but chapter subtree

### memory

- each memory entry is a unique object stored in the tree; nodes point to memory
- inheritable or not inheritable
- if you modify memory for subtree, acts like changing chapter. Or you can modify
the memory instantiation itself, which modifies memory for all nodes pointing to 
it and doesn't create a new object
- you can have multiple memory entries for one node
- you can create assign a node an existing memory object without creating a new memory object
bool for whether memory is activated
- layer variable for order of entries
- memories are inheritable by default, but you can create a non-inheritable memory
deleting a memory entry - either for entire subtree or just for one node
- reverse time influence: option to propagate memory pointers backward

#### interface

- optional custom title
- tags
- keys
    - automatically generated keys
- view memory entries of a node
- change enabled status of memory
- create a new memory entry (for node or subtree) (global) (inheritable?)
- import an existing memory entry (for node or subtree)
    - database of memories (tree? keywords? search?)
    - automatic importing
- delete a memory entry (for node or subtree)
- edit (or delete) memory object 
- edit inheritable status of a memory
- propagate back in time (with optional max depth)

### floating notes

- title and tags
- same as memory, except by default the object is edited and a new instant isn't created
    - default deleting only removes pointers
    - option to duplicate note (create new instance from template)
- show up as text boxes on the side which are always editable
- like memory, pointers can be inheritable or not and global or not
    - global notes are accessible from any node
- option to minimize without deleting
- like memory, can import existing notes
- reverse time propagation
