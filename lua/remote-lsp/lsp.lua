local M = {}

local function get_proxy_path()
	local source = debug.getinfo(1, "S").source
	local script_path = source:sub(2)
	local plugin_dir = script_path:match("(.*/)")
	return plugin_dir .. "scripts/lsp-proxy.py"
end

local function setup_lsp_with_remote(lsp, root_dir)
	local remote_sshfs_root = require("remote-sshfs").config.mounts.base_dir

	vim.lsp.config(lsp, {
		root_dir = function(bufnr, on_dir)
			local fullpath = vim.fn.fnamemodify(vim.fn.bufname(bufnr), ":p")
			if not (remote_sshfs_root and fullpath:sub(1, #remote_sshfs_root) == remote_sshfs_root) then
				on_dir(root_dir(bufnr))
			end
		end,
	})

	local remote_lsp = "remote-" .. lsp
	vim.lsp.config[remote_lsp] = vim.fn.deepcopy(vim.lsp.config[lsp])
	vim.lsp.config(remote_lsp, {
		root_dir = function(bufnr, on_dir)
			local fullpath = vim.fn.fnamemodify(vim.fn.bufname(bufnr), ":p")
			if remote_sshfs_root and fullpath:sub(1, #remote_sshfs_root) == remote_sshfs_root then
				on_dir(root_dir(bufnr))
			end
		end,
	})

	vim.lsp.enable(remote_lsp)
end

M.setup = function(opts)
	for lsp, _ in pairs(opts.servers) do
		setup_lsp_with_remote(lsp, function(bufnr)
			return require("lspconfig.configs." .. lsp).default_config.root_dir(vim.fn.bufname(bufnr))
		end)
	end

	require("remote-sshfs").callback.on_connect_success:add(function(host, mount_dir)
		local lsp_proxy_path = get_proxy_path()

		local sshfs_prefix = mount_dir
		local remote_prefix = host["Path"] or ("/home/" .. host["User"])

		local function get_remote_cmd(cmd)
			local remote_cmd = {
				opts.python_bin,
				"-u",
				lsp_proxy_path,
				host["User"] .. "@" .. (host["HostName"] or host["Name"]),
				sshfs_prefix,
				remote_prefix,
			}

			if type(cmd) == "table" then
				for _, part in ipairs(cmd) do
					table.insert(remote_cmd, part)
				end
			elseif type(cmd) == "string" then
				table.insert(remote_cmd, cmd)
			else
				error("Unsupported cmd type for LSP: expected table or string, got " .. type(cmd))
			end

			return remote_cmd
		end

		for lsp, server_conf in pairs(opts.servers) do
			vim.lsp.config("remote-" .. lsp, {
				cmd = get_remote_cmd(server_conf.cmd or lsp),
			})
		end
	end)
end

return M
