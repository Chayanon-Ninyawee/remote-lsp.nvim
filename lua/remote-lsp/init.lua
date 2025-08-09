local M = {}

local default_opts = {
	python_bin = "python3",
	servers = {}, -- { pyright = {...}, gopls = {...} }
}

M.setup = function(config)
	local ok_lspconfig, _ = pcall(require, "lspconfig")
	if not ok_lspconfig then
		vim.notify("[remote-lsp] Missing dependency: neovim/nvim-lspconfig", vim.log.levels.ERROR)
		return
	end

	local ok_sshfs, _ = pcall(require, "remote-sshfs")
	if not ok_sshfs then
		vim.notify("[remote-lsp] Missing dependency: nosduco/remote-sshfs.nvim", vim.log.levels.ERROR)
		return
	end

	local opts = config and vim.tbl_deep_extend("force", default_opts, config) or default_opts
	M.config = opts

	require("remote-lsp.lsp").setup(opts)
end

return M
