# bugs

* key bindings only work in most recent tab
* have to close tab before opening file
* chapter nav tree scrollbar
* num leaves calculated incorrectly
* ctrl+space sometimes clicks button
* ctrl+y hotkey (chapter dialogue) sometimes doesn't work

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


# Display
 
* show / hide navtrees
* if scroll position is regressing, add whitespace and keep instead?? (didn't work, need new approach)
* toggle gray history / context window 
* gradient color for text box history
* scroll at top of chapter by default and hotkey to go to top of chapter
* change darkmode in program
* highlight mouseover history
* implement expand/collapse functions in controller

# Tree topology

* create parent for root node
* multiple root nodes
* add ghostchildren/ghostparents (using hotkey)


# import / export 
* export subtree as json


# versioning
* save version each time node is edited
* save creation information (prompt, logprobs, merge or branch)


# Features

* search (global or by subtree or in ancestry)
* search chapter titles
* undo
* right sidebar for (everything else)
* "floating" notes
    * global or associated with subtree
* bookmark-like tags define subsets of tree (and option to only display/navigate tag)
* save open status (not visible status) in tree dict 
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

* clickable links in active text

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

- save multiple memory entries for each node
- should memory use pointers like chapter?
- memory dialogue lets you import
    - memories from ancestry
    - by search (multiverse or ancestry)
    - by keying (top n matches) (multiverse or ancestry)
- memory in context: when importing memory, option to navigate surrounding tree
- semantic search for short-term memory?
- when changing memory, option to create new entry vs edit existing one

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
* stochastic walk 
    * mode which doesn't count visited nodes
    * depth limit
    * display probabilities
    * canonical only
    
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
