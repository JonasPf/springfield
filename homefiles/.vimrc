"----------------
" General setings
"----------------
set nocompatible
set background=dark
syntax on
set number
set ruler
set encoding=utf-8
set wildmenu

set hlsearch
set ignorecase
set smartcase " override ignorecase if there is a upper case letter in the search text

set backspace=indent,eol,start " make backspace behave normally (https://vi.stackexchange.com/a/2163)
set mouse=a " make mouse work for everything (a == all)

"----------------
" Shortcuts
"----------------
" Use space as leader
let mapleader=" "

" Show partial command in bottom right (useful to get visual feedback when leader is pressed)
set showcmd

" Switch buffers quickly with <space><space>
nnoremap <leader><space> :buffer<space>

" Open new buffers quickly with <space>e
nnoremap <leader>e :e .<CR>

"----------------
" Tabs
"----------------
set tabstop=4
set shiftwidth=4
set softtabstop=4
set expandtab

"----------------
" Backups & Co.
"----------------
set backup
" The "//" at the end of the directory means that file names will be built from the complete path to the file.
" This will ensure file name uniqueness in the preserve directory. Use two slashes at the end of the path. This will ensure file name uniqueness in the preserve directory.
set backupdir=~/.vim/backup//
set directory=~/.vim/swp " contains unsaved changes

" Maintain undo history between sessions
set undofile
set undodir=~/.vim/undo

"----------------
" Local .vimrc
"----------------

if filereadable(".lvimrc")
    source .lvimrc
endif
