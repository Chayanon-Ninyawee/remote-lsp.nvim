# remote-lsp.nvim

Run Language Servers remotely over SSH while leveraging [remote-sshfs.nvim](https://github.com/nosduco/remote-sshfs.nvim) for mounting remote filesystems.

This plugin runs LSP servers on your remote machine via SSH, forwarding the LSP protocol through an SSH proxy, and uses the remote-sshfs.nvim plugin to mount the remote filesystem locally via SSHFS.

---

## Features

- Runs LSP servers remotely over SSH using a Python proxy helper  
- Utilizes remote-sshfs.nvim to mount remote filesystem via SSHFS  
- Supports configuring multiple LSP servers to run remotely  

---

## Requirements

- Neovim 0.11.0+  
- [nvim-lspconfig](https://github.com/neovim/nvim-lspconfig)  
- [remote-sshfs.nvim](https://github.com/nosduco/remote-sshfs.nvim)  
- Python 3 on the local machine (default: `python3`)  
- The remote machine must have the LSP servers installed that you want to use** (e.g., `clangd`, `cmake`, etc.)  
- SSH and SSHFS configured for remote filesystem mounting  
- **SSH key-based authentication configured on the remote machine** (see guide below)  

---

## SSH Key Setup Guide

To enable seamless SSH connections without password prompts (required for this plugin to work smoothly), set up SSH key-based authentication:

1. **Generate SSH key pair (if you don't have one):**

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

2. **Copy your public key to the remote machine:**

```bash
ssh-copy-id user@remote_host
```

Alternatively, manually append your `~/.ssh/id_ed25519.pub` (or corresponding `.pub` file) content to the remote `~/.ssh/authorized_keys`.

3. **Verify that you can SSH to the remote host without a password prompt:**

```bash
ssh user@remote_host
```

If this works without asking for a password, your SSH key setup is ready.

---

## Installation

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
            clangd = { cmd = "clangd" },
            cmake = { cmd = "cmake-language-server" },
        },
    },
}
```

---

## Configuration

Configure `remote-lsp.nvim` with:

| Option       | Type    | Default                 | Description                              |
|--------------|---------|-------------------------|------------------------------------------|
| `python_bin` | string  | `"python3"`             | Python interpreter for running the proxy. |
| `servers`    | table   | `{}`                    | Map of LSP servers to run remotely.        |

Example:

```lua
require("remote-lsp").setup({
  python_bin = "/usr/bin/python3",
  servers = {
    clangd = { cmd = "clangd" },
    cmake = { cmd = "cmake-language-server" },
    -- Add more remote LSP here
  },
})
```

---

## Usage

1. Use [remote-sshfs.nvim](https://github.com/nosduco/remote-sshfs.nvim) to mount your remote filesystem via SSHFS.

### remote-sshfs.nvim Commands

- `:RemoteSSHFSConnect [host]`  
  Connect to a remote host and mount its filesystem.  
  If `[host]` is omitted, a picker will show available hosts from your SSH config.

- `:RemoteSSHFSDisconnect [host]`  
  Unmount the remote filesystem for the given host.

- `:RemoteSSHFSReload`  
  Reload all SSHFS mounts and connections.

- `:RemoteSSHFSEdit`  
  Edit your SSHFS connections.

- `:RemoteSSHFSFindFiles`  
  Use Telescope to find files on the mounted remote filesystem.

- `:RemoteSSHFSLiveGrep`  
  Use Telescope live grep on the remote filesystem.

2. After mounting the remote filesystem via `:RemoteSSHFSConnect`, open files within the mounted directory in Neovim.

3. This plugin will run your configured LSP servers remotely over SSH for those files, providing seamless LSP support.

---

## How it works

- The plugin spawns an SSH process that runs the remote LSP server on your remote host.  
- Communication is proxied over SSH using a Python helper script bundled with the plugin (`lsp-proxy.py`).  
- The plugin and proxy script translate file paths between the local SSHFS mount and the remote filesystem paths.  
- This allows the LSP to correctly understand file locations and provide accurate diagnostics and code actions.

---

## Credits

- The `lsp-proxy.py` helper script is inspired by [inhesrom/remote-ssh.nvim](https://github.com/inhesrom/remote-ssh.nvim)  
- [nvim-lspconfig](https://github.com/neovim/nvim-lspconfig) for LSP client integration  
- [remote-sshfs.nvim](https://github.com/nosduco/remote-sshfs.nvim) for SSHFS mounting  

---
