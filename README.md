remote-lsp.nvim
===============

A Neovim plugin to run Language Servers remotely over SSH, built as an extension to [remote-sshfs.nvim](https://github.com/nosduco/remote-sshfs.nvim).

This plugin runs LSP servers on your remote machine via SSH, forwarding the LSP protocol through an SSH proxy.

Table of Contents
-----------------

<!-- toc -->

-	[What it does](#what-it-does)
-	[Requirements](#requirements)
-	[SSH Key Setup Guide](#ssh-key-setup-guide)
-	[Installation](#installation)
-	[Configuration](#configuration)
-	[Usage](#usage)
-	[Credits](#credits)

<!-- tocstop -->

What it does
------------

-	Detects the sshfs mount folder by reading `require("remote-sshfs").config.mounts.base_dir`.
-	Automatically disables the local `[lsp]` and enables the corresponding `remote-[lsp]` when editing files inside the mounted sshfs directory.
-	Runs a Python proxy script (`lsp-proxy.py`) to run LSP via SSH and translate file paths between the local sshfs mount paths and their absolute remote paths, enabling seamless LSP communication over SSH.

Requirements
------------

-	Neovim 0.11.0+  
-	[nvim-lspconfig](https://github.com/neovim/nvim-lspconfig)  
-	[remote-sshfs.nvim](https://github.com/nosduco/remote-sshfs.nvim)  
-	Python 3 on the local machine (default: `python3`)  
-	The remote machine must have the LSP servers installed that you want to use\** (e.g., `clangd`, `cmake`, etc.)  
-	SSH and SSHFS configured for remote filesystem mounting
-	SSH key-based authentication configured on the remote machine (see guide below)  

SSH Key Setup Guide
-------------------

To enable seamless SSH connections without password prompts (required for this plugin to work smoothly), set up SSH key-based authentication:

1.	**Generate SSH key pair (if you don't have one):**

	```bash
	ssh-keygen -t ed25519 -C "your_email@example.com"
	```

2.	**Copy your public key to the remote machine:**

	```bash
	ssh-copy-id user@remote_host
	```

Alternatively, manually append your `~/.ssh/id_ed25519.pub` (or corresponding `.pub` file) content to the remote `~/.ssh/authorized_keys`.

1.	**Verify that you can SSH to the remote host without a password prompt:**

	```bash
	ssh user@remote_host
	```

If this works without asking for a password, your SSH key setup is ready.

Installation
------------

Using lazy

```lua
{
    "Chayanon-Ninyawee/remote-lsp.nvim",
    dependencies = {
        "neovim/nvim-lspconfig",
        "nosduco/remote-sshfs.nvim",
    },
    opts = {
        servers = {
            -- TODO: Add more remote LSP here
        },
    },
}
```

Configuration
-------------

Configure `remote-lsp.nvim` with:

| Option       | Type   | Default     | Description                               |
|--------------|--------|-------------|-------------------------------------------|
| `python_bin` | string | `"python3"` | Python interpreter for running the proxy. |
| `servers`    | table  | `{}`        | Map of LSP servers to run remotely.       |

Example:

```lua
require("remote-lsp").setup({
    python_bin = "/usr/bin/python3",
    servers = {
        clangd = { cmd = "clangd" },
        cmake = { cmd = "cmake-language-server" },
    },
})
```

---

You can config the LSP servers in your `nvim-lspconfig` setup like this:

```lua
vim.lsp.config("clangd", {
    -- You can set root_dir or root_markers here and it will still work with remote-lsp.nvim plugin
})
```

and it will just clone your LSP config to be use in the remote version of the LSP.

or just enable it and use default config:

```lua
vim.lsp.enable("clangd")
```

Usage
-----

1.	Use [remote-sshfs.nvim](https://github.com/nosduco/remote-sshfs.nvim) to mount your remote filesystem via SSHFS. (Run `:RemoteSSHFSConnect`\)

2.	After mounting the remote filesystem via `:RemoteSSHFSConnect`, open files within the mounted directory in Neovim.

3.	The plugin will disable the local LSP client and instead enable the configured remote LSP servers, communicating over SSH through the Python proxy that handles path translation.

**Important Note:**  
Many tools and installers (like Homebrew) suggest adding environment setup commands, such as:

```bash
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
```

to your shell config files like `~/.bashrc` or `~/.zshrc`.

However, these files are usually only loaded in **interactive shells**, and are **not sourced automatically in non-interactive or remote SSH commands** (which this plugin relies on).

To ensure your environment variables and PATH are correctly set in **both interactive and non-interactive shells**, consider placing such commands in your shell’s **login configuration files** instead, for example:

-	`~/.bash_profile` or `~/.profile` for **bash**  
-	`~/.zprofile` for **zsh**  

Credits
-------

-	The `lsp-proxy.py` helper script is inspired by [inhesrom/remote-ssh.nvim](https://github.com/inhesrom/remote-ssh.nvim)  
-	[nvim-lspconfig](https://github.com/neovim/nvim-lspconfig) for LSP client integration  
-	[remote-sshfs.nvim](https://github.com/nosduco/remote-sshfs.nvim) for SSHFS mounting
