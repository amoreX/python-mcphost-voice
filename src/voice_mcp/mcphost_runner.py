"""MCPHost runner implementation."""

import subprocess
import sys
import time
import select
from typing import Optional, Tuple

class MCPHostRunner:
    """Handles running and interacting with MCPHost process."""

    def __init__(self, model: str, config_path: str, response_timeout: int = 30):
        """Initialize MCPHostRunner.

        Args:
            model: Model identifier to use with MCPHost
            config_path: Path to MCPHost config file
            response_timeout: Timeout in seconds for waiting for responses
        """
        self.model = model
        self.config_path = config_path
        self.response_timeout = response_timeout

    def run_mcphost(self, prompt: str) -> str:
        """Run MCPHost with the given prompt and return output.

        Args:
            prompt: The prompt to send to MCPHost

        Returns:
            str: MCPHost response or error message
        """
        # Try basic approach first (more reliable in this case)
        try:
            return self.run_mcphost_basic(prompt)
        except Exception as e:
            print(f"⚠️ Basic approach failed: {e}, trying pexpect")
            try:
                return self.run_mcphost_with_pexpect(prompt)
            except ImportError:
                return "Both approaches failed and pexpect not available"
            except Exception as e2:
                return f"Both approaches failed. Basic: {e}, Pexpect: {e2}"

    def _read_line_with_timeout(self, pipe, timeout: float) -> Optional[str]:
        """Read a line from pipe with timeout.

        Args:
            pipe: File-like object to read from
            timeout: Timeout in seconds

        Returns:
            str or None: Read line or None if timeout/error
        """
        if sys.platform == "win32":
            # Windows doesn't support select on pipes
            try:
                return pipe.readline()
            except:
                return None
        else:
            # Unix/Linux
            ready, _, _ = select.select([pipe], [], [], timeout)
            if ready:
                try:
                    return pipe.readline()
                except:
                    return None
            return None

    def run_mcphost_basic(self, prompt: str) -> str:
        """Basic approach for running MCPHost.

        Args:
            prompt: The prompt to send

        Returns:
            str: MCPHost response or error message
        """
        try:
            # Prepare the command
            cmd = [
                "mcphost",
                "-m", self.model,
                "--config", self.config_path
            ]

            print(f"🤖 Sending to MCPHost (basic): {prompt}")

            # Use Popen for interactive communication
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,  # Unbuffered
                universal_newlines=True
            )

            # Send the prompt
            process.stdin.write(prompt + "\n")
            process.stdin.flush()

            # Collect output
            all_output = ""
            stderr_output = ""
            start_time = time.time()

            while time.time() - start_time < self.response_timeout:
                try:
                    # Check if process is still running
                    if process.poll() is not None:
                        break

                    # Try to read a line with a short timeout
                    line = self._read_line_with_timeout(process.stdout, 1.0)
                    if line is not None:
                        all_output += line

                    # Also try to read stderr
                    stderr_line = self._read_line_with_timeout(process.stderr, 1.0)
                    if stderr_line is not None:
                        stderr_output += stderr_line

                except Exception as e:
                    print(f"Error reading output: {e}")
                    break

            # Clean up the process
            try:
                process.stdin.write("quit\n")
                process.stdin.flush()
                time.sleep(0.5)
            except:
                pass

            try:
                process.terminate()
                process.wait(timeout=2)
            except:
                process.kill()

            return f"STDOUT:\n{all_output}\n\nSTDERR:\n{stderr_output}"

        except Exception as e:
            error_msg = f"Error running MCPHost: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg

    def run_mcphost_with_pexpect(self, prompt: str) -> str:
        """Run MCPHost using pexpect for better interactive handling.

        Args:
            prompt: The prompt to send

        Returns:
            str: MCPHost response or error message
        """
        try:
            import pexpect

            print(f"🤖 Sending to MCPHost (pexpect): {prompt}")

            # Spawn MCPHost with proper environment
            cmd = f"mcphost -m {self.model} --config {self.config_path}"
            child = pexpect.spawn(cmd, env={'TERM': 'dumb'})
            child.timeout = 10
            child.logfile_read = sys.stdout.buffer

            # Read initial output and look for any prompt-like text
            try:
                # Look for various possible prompt patterns
                index = child.expect([
                    r"Enter your prompt.*",
                    r"prompt.*",
                    r"You:.*",
                    r"User:.*",
                    r">>.*",
                    r">.*",
                    pexpect.TIMEOUT
                ], timeout=15)

                if index == 6:  # TIMEOUT
                    print("⚠️ Timeout waiting for initial prompt, trying to send anyway...")
                else:
                    print(f"✅ Found prompt pattern {index}")

            except pexpect.TIMEOUT:
                print("⚠️ No clear prompt found, continuing anyway...")

            # Send our prompt
            child.sendline(prompt)

            # Look for assistant response
            response_text = ""

            try:
                # Wait for assistant response with multiple possible patterns
                index = child.expect([
                    r"Assistant:.*",
                    r"Response:.*",
                    r"AI:.*",
                    pexpect.TIMEOUT
                ], timeout=self.response_timeout)

                if index < 3:  # Found assistant response
                    print(f"✅ Found assistant response pattern {index}")

                    # Read until we see another prompt or timeout
                    child.timeout = 5
                    response_parts = []

                    while True:
                        try:
                            index = child.expect([
                                r"Enter your prompt.*",
                                r"prompt.*",
                                r"You:.*",
                                r">>.*",
                                pexpect.TIMEOUT,
                                pexpect.EOF
                            ], timeout=5)

                            if index < 4:  # Found next prompt
                                response_text = child.before.decode('utf-8', errors='ignore')
                                break
                            elif index == 4:  # TIMEOUT - might be end of response
                                response_text += child.before.decode('utf-8', errors='ignore')
                                break
                            else:  # EOF
                                response_text += child.before.decode('utf-8', errors='ignore')
                                break

                        except pexpect.TIMEOUT:
                            response_text += child.before.decode('utf-8', errors='ignore')
                            break

                else:
                    print("⚠️ No assistant response pattern found")

            except pexpect.TIMEOUT:
                print("⚠️ Timeout waiting for assistant response")
                response_text = child.before.decode('utf-8', errors='ignore')

            child.close()
            return response_text if response_text else "No response text captured"

        except Exception as e:
            return f"Error with pexpect approach: {str(e)}"
