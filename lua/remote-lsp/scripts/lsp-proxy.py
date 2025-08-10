#!/usr/bin/env python3

import datetime
import json
import logging
import os
import subprocess
import sys
import threading

# Set up logging
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_dir = os.path.expanduser("~/.cache/nvim/remote_lsp_logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"proxy_log_{timestamp}.log")

# Create logger with file handler for all messages
logger = logging.getLogger("proxy")
logger.setLevel(logging.DEBUG)

# File handler for all messages
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Stderr handler only for errors and warnings (to avoid polluting LSP communication)
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.WARNING)
logger.addHandler(stderr_handler)

shutdown_requested = False
ssh_process = None  # Global reference to SSH process


def parse_args(argv):
    if len(argv) < 5:
        logger.error(
            "[lsp-proxy.py Error]: Usage: lsp-proxy.py <user@remote> <sshfs_prefix> <remote_prefix> [--root-dir <dir>] <lsp_command> [args...]"
        )
        sys.exit(1)

    user_remote = argv[1]
    sshfs_prefix = argv[2]
    remote_prefix = argv[3]

    root_dir = None
    lsp_command_start = 4
    if len(argv) > 5 and argv[4] == "--root-dir":
        root_dir = argv[5]
        lsp_command_start = 6
        logger.info(f"Root directory specified: {root_dir}")

    lsp_command = argv[lsp_command_start:]

    return user_remote, sshfs_prefix, remote_prefix, root_dir, lsp_command


def build_ssh_command(user_remote, root_dir, lsp_command):
    import shlex

    try:
        cd_command = f"cd {shlex.quote(root_dir)} && " if root_dir else ""
    except Exception as e:
        logger.error(f"[lsp-proxy.py Error]: Error creating cd_command: {e}")
        sys.exit(1)

    env_setup = (
        "source ~/.bashrc 2>/dev/null || true; "
        "source ~/.profile 2>/dev/null || true; "
        "source ~/.zshrc 2>/dev/null || true; "
        "export PATH=$HOME/.cargo/bin:$HOME/.local/bin:$HOME/.npm-global/bin:/usr/local/bin:/opt/homebrew/bin:$PATH; "
        "export CARGO_HOME=$HOME/.cargo 2>/dev/null || true; "
        "export RUSTUP_HOME=$HOME/.rustup 2>/dev/null || true; "
    )

    lsp_command_str = " ".join(lsp_command)
    full_command = f"{env_setup} {cd_command}{lsp_command_str}"

    ssh_cmd = [
        "ssh",
        "-q",
        "-o",
        "ServerAliveInterval=10",
        "-o",
        "ServerAliveCountMax=6",
        "-o",
        "TCPKeepAlive=yes",
        "-o",
        "ControlMaster=no",
        "-o",
        "ControlPath=none",
        user_remote,
        full_command,
    ]

    logger.info(f"Using environment setup for LSP server: {cd_command}{lsp_command_str}")
    logger.info(f"Executing: {' '.join(ssh_cmd)}")

    return ssh_cmd


def start_stderr_monitoring(ssh_process):
    def monitor_stderr():
        while not shutdown_requested:
            try:
                line = ssh_process.stderr.readline()
                if not line:
                    break
                error_msg = line.decode("utf-8", errors="replace").strip()
                if error_msg:
                    logger.error(error_msg)
                import time

                # Throttle logging to prevent combining lines
                time.sleep(0.010)
            except Exception:
                break

    try:
        stderr_thread = threading.Thread(target=monitor_stderr)
        stderr_thread.daemon = True
        stderr_thread.start()
    except Exception as e:
        logger.error(f"[lsp-proxy.py Error]: Failed to start stderr monitoring thread: {e}")
        sys.exit(1)


def replace_paths(obj, sshfs_prefix, remote_prefix):
    if isinstance(obj, str):
        result = obj

        if result.startswith(sshfs_prefix):
            result = remote_prefix + obj[len(sshfs_prefix) :]
            logger.debug(f"Path translation (sshfs->remote): {obj} -> {result}")
            return result
        if result.startswith("file://" + sshfs_prefix):
            result = "file://" + remote_prefix + obj[len("file://" + sshfs_prefix) :]
            logger.debug(f"Path translation (sshfs->remote): {obj} -> {result}")
            return result

        if result.startswith(remote_prefix):
            result = sshfs_prefix + obj[len(remote_prefix) :]
            logger.debug(f"Path translation (remote->sshfs): {obj} -> {result}")
            return result
        if result.startswith("file://" + remote_prefix):
            result = "file://" + sshfs_prefix + obj[len("file://" + remote_prefix) :]
            logger.debug(f"Path translation (remote->sshfs): {obj} -> {result}")
            return result

        return result
    elif isinstance(obj, dict):
        return {
            replace_paths(k, sshfs_prefix, remote_prefix): replace_paths(v, sshfs_prefix, remote_prefix)
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [replace_paths(item, sshfs_prefix, remote_prefix) for item in obj]

    return obj


def handle_stream(stream_name, input_stream, output_stream, sshfs_prefix, remote_prefix):
    global shutdown_requested, ssh_process

    logger.info(f"Starting {stream_name} handler")

    while not shutdown_requested:
        # Read Content-Length header with proper EOF handling
        header = b""
        while not shutdown_requested:
            try:
                byte = input_stream.read(1)
            except Exception as e:
                logger.error(f"[lsp-proxy.py Error]: {stream_name} - Error reading header byte: {e}")
                return

            if byte:
                header += byte
                if header.endswith(b"\r\n\r\n"):
                    break

            # Check if this is a real EOF or just no data available
            # For stdin/stdout pipes, empty read usually means EOF
            # But we should verify the process is still alive
            if hasattr(input_stream, "closed") and input_stream.closed:
                logger.info(f"{stream_name} - Input stream is closed")
                return
            # For process pipes, check if the process is still running
            if stream_name == "ssh_to_neovim" and ssh_process is not None:
                if ssh_process.poll() is not None:
                    logger.info(f"{stream_name} - SSH process has terminated (exit code: {ssh_process.returncode})")
                    return

            # If we can't determine the state, treat as potential temporary condition
            # Try a small delay and check again
            import time

            time.sleep(0.01)  # 10ms delay

        # Parse Content-Length
        content_length = None
        for line in header.split(b"\r\n"):
            if line.startswith(b"Content-Length:"):
                try:
                    content_length = int(line.split(b":")[1].strip())
                    break
                except (ValueError, IndexError) as e:
                    logger.error(f"[lsp-proxy.py Error]: {stream_name} - Failed to parse Content-Length: {e}")

        if content_length is None:
            continue

        # Read content with proper error handling
        content = b""
        while len(content) < content_length and not shutdown_requested:
            remaining = content_length - len(content)

            try:
                chunk = input_stream.read(remaining)
            except Exception as e:
                logger.error(f"[lsp-proxy.py Error]: {stream_name} - Error reading content chunk: {e}")
                return

            if chunk:
                content += chunk
                continue

            # Similar EOF checking as above
            if hasattr(input_stream, "closed") and input_stream.closed:
                logger.info(f"{stream_name} - Input stream closed during content read")
                return
            if stream_name == "ssh_to_neovim" and ssh_process is not None:
                if ssh_process.poll() is not None:
                    logger.info(
                        f"{stream_name} - SSH process terminated during content read (exit code: {ssh_process.returncode})"
                    )
                    return

            # Brief delay for potential temporary condition
            import time

            time.sleep(0.01)

        try:
            content_str = content.decode("utf-8")
            message = json.loads(content_str)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.error(f"[lsp-proxy.py Error]: {stream_name} - JSON decode error: {e}")
            continue
        except Exception as e:
            logger.error(f"[lsp-proxy.py Error]: {stream_name} - Error processing message: {e}")
            continue

        logger.debug(f"{stream_name} - Original message: {json.dumps(message, indent=2)}")

        # Check for exit messages
        if message.get("method") == "exit":
            logger.info("Exit message detected")
            shutdown_requested = True

        # Replace URIs
        try:
            translated_message = replace_paths(message, sshfs_prefix, remote_prefix)
        except Exception as e:
            logger.error(f"[lsp-proxy.py Error]: {stream_name} - Error in replace_paths: {e}")
            continue

        logger.debug(f"{stream_name} - Translated message: {json.dumps(translated_message, indent=2)}")

        # Send translated message
        new_content = json.dumps(translated_message)
        header = f"Content-Length: {len(new_content)}\r\n\r\n"

        try:
            output_stream.write(header.encode("utf-8"))
            output_stream.write(new_content.encode("utf-8"))
            output_stream.flush()
        except Exception as e:
            logger.error(f"[lsp-proxy.py Error]: {stream_name} - Error writing to output stream: {e}")
            continue

    logger.info(f"{stream_name} - Handler exiting")


def main():
    global shutdown_requested, ssh_process

    user_remote, sshfs_prefix, remote_prefix, root_dir, lsp_command = parse_args(sys.argv)

    ssh_cmd = build_ssh_command(user_remote, root_dir, lsp_command)

    try:
        ssh_process = subprocess.Popen(
            ssh_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        logger.info(f"SSH process started with PID: {ssh_process.pid}")
    except Exception as e:
        logger.error(f"[lsp-proxy.py Error]: Failed to start SSH process: {e}")
        sys.exit(1)

    start_stderr_monitoring(ssh_process)

    t1 = threading.Thread(
        target=handle_stream,
        args=(
            "neovim_to_ssh",
            sys.stdin.buffer,
            ssh_process.stdin,
            sshfs_prefix,
            remote_prefix,
        ),
    )
    t2 = threading.Thread(
        target=handle_stream,
        args=(
            "ssh_to_neovim",
            ssh_process.stdout,
            sys.stdout.buffer,
            sshfs_prefix,
            remote_prefix,
        ),
    )
    t1.start()
    t2.start()

    try:
        ssh_process.wait()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        shutdown_requested = True
        if ssh_process.poll() is None:
            ssh_process.terminate()
        t1.join(timeout=2)
        t2.join(timeout=2)
        logger.info("Proxy terminated")


if __name__ == "__main__":
    main()
