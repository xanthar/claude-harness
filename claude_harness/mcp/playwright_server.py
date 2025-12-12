#!/usr/bin/env python3
"""MCP Server for Playwright Browser Automation.

This MCP server provides tools for browser automation testing,
allowing Claude Code to interact with web applications like a real user.

Usage:
    python -m claude_harness.mcp.playwright_server

Or add to claude_desktop_config.json:
    {
        "mcpServers": {
            "playwright": {
                "command": "python",
                "args": ["-m", "claude_harness.mcp.playwright_server"]
            }
        }
    }
"""

import asyncio
import base64
import json
import sys
from typing import Any, Optional
from contextlib import asynccontextmanager

# MCP protocol implementation
# Uses JSON-RPC 2.0 over stdio


class PlaywrightMCPServer:
    """MCP Server providing Playwright browser automation tools."""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self._initialized = False

    async def initialize(self):
        """Initialize Playwright."""
        if self._initialized:
            return

        try:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()
            self._initialized = True
        except ImportError:
            raise RuntimeError(
                "Playwright not installed. Run: pip install playwright && playwright install"
            )

    async def cleanup(self):
        """Cleanup browser resources."""
        if self.page:
            await self.page.close()
            self.page = None
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        self._initialized = False

    # --- Tool Implementations ---

    async def tool_launch_browser(
        self,
        browser_type: str = "chromium",
        headless: bool = True,
        slow_mo: int = 0,
        viewport_width: int = 1280,
        viewport_height: int = 720,
    ) -> dict:
        """Launch a browser instance.

        Args:
            browser_type: Browser to use (chromium, firefox, webkit)
            headless: Run in headless mode
            slow_mo: Slow down operations by ms
            viewport_width: Browser viewport width
            viewport_height: Browser viewport height

        Returns:
            Status of browser launch
        """
        await self.initialize()

        # Close existing browser if any
        if self.browser:
            await self.browser.close()

        # Launch browser
        browser_launcher = getattr(self.playwright, browser_type, None)
        if not browser_launcher:
            return {"error": f"Unknown browser type: {browser_type}"}

        self.browser = await browser_launcher.launch(
            headless=headless,
            slow_mo=slow_mo,
        )

        self.context = await self.browser.new_context(
            viewport={"width": viewport_width, "height": viewport_height}
        )

        self.page = await self.context.new_page()

        return {
            "status": "success",
            "browser": browser_type,
            "headless": headless,
            "viewport": f"{viewport_width}x{viewport_height}",
        }

    async def tool_navigate(self, url: str, wait_until: str = "load") -> dict:
        """Navigate to a URL.

        Args:
            url: URL to navigate to
            wait_until: Wait condition (load, domcontentloaded, networkidle)

        Returns:
            Navigation result with page title
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            response = await self.page.goto(url, wait_until=wait_until)
            title = await self.page.title()

            return {
                "status": "success",
                "url": self.page.url,
                "title": title,
                "response_status": response.status if response else None,
            }
        except Exception as e:
            return {"error": str(e)}

    async def tool_click(
        self,
        selector: str,
        button: str = "left",
        click_count: int = 1,
        timeout: int = 30000,
    ) -> dict:
        """Click an element.

        Args:
            selector: CSS selector or text selector
            button: Mouse button (left, right, middle)
            click_count: Number of clicks
            timeout: Timeout in ms

        Returns:
            Click result
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            await self.page.click(
                selector,
                button=button,
                click_count=click_count,
                timeout=timeout,
            )
            return {"status": "success", "selector": selector}
        except Exception as e:
            return {"error": str(e), "selector": selector}

    async def tool_fill(
        self,
        selector: str,
        value: str,
        timeout: int = 30000,
    ) -> dict:
        """Fill an input field.

        Args:
            selector: CSS selector for the input
            value: Value to fill
            timeout: Timeout in ms

        Returns:
            Fill result
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            await self.page.fill(selector, value, timeout=timeout)
            return {"status": "success", "selector": selector, "value_length": len(value)}
        except Exception as e:
            return {"error": str(e), "selector": selector}

    async def tool_type(
        self,
        selector: str,
        text: str,
        delay: int = 50,
        timeout: int = 30000,
    ) -> dict:
        """Type text into an element (simulates real typing).

        Args:
            selector: CSS selector for the element
            text: Text to type
            delay: Delay between keystrokes in ms
            timeout: Timeout in ms

        Returns:
            Type result
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            await self.page.type(selector, text, delay=delay, timeout=timeout)
            return {"status": "success", "selector": selector, "text_length": len(text)}
        except Exception as e:
            return {"error": str(e), "selector": selector}

    async def tool_screenshot(
        self,
        path: Optional[str] = None,
        full_page: bool = False,
        selector: Optional[str] = None,
    ) -> dict:
        """Take a screenshot.

        Args:
            path: Path to save screenshot (optional, returns base64 if not provided)
            full_page: Capture full scrollable page
            selector: Capture specific element

        Returns:
            Screenshot result (with base64 data if no path)
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            if selector:
                element = await self.page.query_selector(selector)
                if not element:
                    return {"error": f"Element not found: {selector}"}
                screenshot_bytes = await element.screenshot()
            else:
                screenshot_bytes = await self.page.screenshot(full_page=full_page)

            if path:
                with open(path, "wb") as f:
                    f.write(screenshot_bytes)
                return {"status": "success", "path": path}
            else:
                return {
                    "status": "success",
                    "base64": base64.b64encode(screenshot_bytes).decode("utf-8"),
                    "size": len(screenshot_bytes),
                }
        except Exception as e:
            return {"error": str(e)}

    async def tool_get_text(self, selector: str, timeout: int = 30000) -> dict:
        """Get text content of an element.

        Args:
            selector: CSS selector
            timeout: Timeout in ms

        Returns:
            Text content
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if not element:
                return {"error": f"Element not found: {selector}"}

            text = await element.text_content()
            return {"status": "success", "selector": selector, "text": text}
        except Exception as e:
            return {"error": str(e), "selector": selector}

    async def tool_get_attribute(
        self,
        selector: str,
        attribute: str,
        timeout: int = 30000,
    ) -> dict:
        """Get attribute value of an element.

        Args:
            selector: CSS selector
            attribute: Attribute name
            timeout: Timeout in ms

        Returns:
            Attribute value
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if not element:
                return {"error": f"Element not found: {selector}"}

            value = await element.get_attribute(attribute)
            return {
                "status": "success",
                "selector": selector,
                "attribute": attribute,
                "value": value,
            }
        except Exception as e:
            return {"error": str(e), "selector": selector}

    async def tool_wait_for_selector(
        self,
        selector: str,
        state: str = "visible",
        timeout: int = 30000,
    ) -> dict:
        """Wait for an element to reach a state.

        Args:
            selector: CSS selector
            state: State to wait for (attached, detached, visible, hidden)
            timeout: Timeout in ms

        Returns:
            Wait result
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            await self.page.wait_for_selector(selector, state=state, timeout=timeout)
            return {"status": "success", "selector": selector, "state": state}
        except Exception as e:
            return {"error": str(e), "selector": selector}

    async def tool_evaluate(self, expression: str) -> dict:
        """Evaluate JavaScript in the page context.

        Args:
            expression: JavaScript expression to evaluate

        Returns:
            Evaluation result
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            result = await self.page.evaluate(expression)
            return {"status": "success", "result": result}
        except Exception as e:
            return {"error": str(e)}

    async def tool_get_url(self) -> dict:
        """Get the current page URL.

        Returns:
            Current URL and title
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            title = await self.page.title()
            return {
                "status": "success",
                "url": self.page.url,
                "title": title,
            }
        except Exception as e:
            return {"error": str(e)}

    async def tool_select_option(
        self,
        selector: str,
        value: Optional[str] = None,
        label: Optional[str] = None,
        index: Optional[int] = None,
        timeout: int = 30000,
    ) -> dict:
        """Select an option from a dropdown.

        Args:
            selector: CSS selector for select element
            value: Option value to select
            label: Option label to select
            index: Option index to select
            timeout: Timeout in ms

        Returns:
            Selection result
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            if value:
                await self.page.select_option(selector, value=value, timeout=timeout)
            elif label:
                await self.page.select_option(selector, label=label, timeout=timeout)
            elif index is not None:
                await self.page.select_option(selector, index=index, timeout=timeout)
            else:
                return {"error": "Must provide value, label, or index"}

            return {"status": "success", "selector": selector}
        except Exception as e:
            return {"error": str(e), "selector": selector}

    async def tool_check(self, selector: str, timeout: int = 30000) -> dict:
        """Check a checkbox or radio button.

        Args:
            selector: CSS selector
            timeout: Timeout in ms

        Returns:
            Check result
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            await self.page.check(selector, timeout=timeout)
            return {"status": "success", "selector": selector}
        except Exception as e:
            return {"error": str(e), "selector": selector}

    async def tool_uncheck(self, selector: str, timeout: int = 30000) -> dict:
        """Uncheck a checkbox.

        Args:
            selector: CSS selector
            timeout: Timeout in ms

        Returns:
            Uncheck result
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            await self.page.uncheck(selector, timeout=timeout)
            return {"status": "success", "selector": selector}
        except Exception as e:
            return {"error": str(e), "selector": selector}

    async def tool_press(self, key: str, selector: Optional[str] = None) -> dict:
        """Press a keyboard key.

        Args:
            key: Key to press (Enter, Tab, Escape, etc.)
            selector: Optional element to focus first

        Returns:
            Press result
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            if selector:
                await self.page.press(selector, key)
            else:
                await self.page.keyboard.press(key)
            return {"status": "success", "key": key}
        except Exception as e:
            return {"error": str(e)}

    async def tool_close_browser(self) -> dict:
        """Close the browser.

        Returns:
            Close result
        """
        try:
            await self.cleanup()
            return {"status": "success", "message": "Browser closed"}
        except Exception as e:
            return {"error": str(e)}

    async def tool_get_page_content(self) -> dict:
        """Get the full HTML content of the page.

        Returns:
            Page HTML content
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            content = await self.page.content()
            return {
                "status": "success",
                "content_length": len(content),
                "content": content[:50000],  # Limit to 50k chars
            }
        except Exception as e:
            return {"error": str(e)}

    async def tool_query_selector_all(
        self,
        selector: str,
        attribute: Optional[str] = None,
    ) -> dict:
        """Get all elements matching a selector.

        Args:
            selector: CSS selector
            attribute: Optional attribute to extract from each element

        Returns:
            List of matching elements
        """
        if not self.page:
            return {"error": "Browser not launched. Call launch_browser first."}

        try:
            elements = await self.page.query_selector_all(selector)
            results = []

            for i, el in enumerate(elements[:50]):  # Limit to 50 elements
                if attribute:
                    value = await el.get_attribute(attribute)
                    results.append({"index": i, attribute: value})
                else:
                    text = await el.text_content()
                    tag = await el.evaluate("el => el.tagName.toLowerCase()")
                    results.append({"index": i, "tag": tag, "text": text[:200] if text else None})

            return {
                "status": "success",
                "selector": selector,
                "count": len(elements),
                "results": results,
            }
        except Exception as e:
            return {"error": str(e), "selector": selector}

    # --- MCP Protocol Implementation ---

    def get_tools_schema(self) -> list:
        """Get MCP tools schema."""
        return [
            {
                "name": "browser_launch",
                "description": "Launch a browser instance for E2E testing",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "browser_type": {
                            "type": "string",
                            "enum": ["chromium", "firefox", "webkit"],
                            "default": "chromium",
                            "description": "Browser type to launch",
                        },
                        "headless": {
                            "type": "boolean",
                            "default": True,
                            "description": "Run in headless mode",
                        },
                        "slow_mo": {
                            "type": "integer",
                            "default": 0,
                            "description": "Slow down operations by ms",
                        },
                        "viewport_width": {
                            "type": "integer",
                            "default": 1280,
                            "description": "Viewport width",
                        },
                        "viewport_height": {
                            "type": "integer",
                            "default": 720,
                            "description": "Viewport height",
                        },
                    },
                },
            },
            {
                "name": "browser_navigate",
                "description": "Navigate to a URL",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to navigate to"},
                        "wait_until": {
                            "type": "string",
                            "enum": ["load", "domcontentloaded", "networkidle"],
                            "default": "load",
                        },
                    },
                    "required": ["url"],
                },
            },
            {
                "name": "browser_click",
                "description": "Click an element on the page",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector"},
                        "button": {
                            "type": "string",
                            "enum": ["left", "right", "middle"],
                            "default": "left",
                        },
                        "click_count": {"type": "integer", "default": 1},
                        "timeout": {"type": "integer", "default": 30000},
                    },
                    "required": ["selector"],
                },
            },
            {
                "name": "browser_fill",
                "description": "Fill an input field with a value",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector"},
                        "value": {"type": "string", "description": "Value to fill"},
                        "timeout": {"type": "integer", "default": 30000},
                    },
                    "required": ["selector", "value"],
                },
            },
            {
                "name": "browser_type",
                "description": "Type text with realistic keystroke simulation",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector"},
                        "text": {"type": "string", "description": "Text to type"},
                        "delay": {"type": "integer", "default": 50, "description": "Delay between keys in ms"},
                        "timeout": {"type": "integer", "default": 30000},
                    },
                    "required": ["selector", "text"],
                },
            },
            {
                "name": "browser_screenshot",
                "description": "Take a screenshot of the page or element",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to save (optional)"},
                        "full_page": {"type": "boolean", "default": False},
                        "selector": {"type": "string", "description": "Element selector (optional)"},
                    },
                },
            },
            {
                "name": "browser_get_text",
                "description": "Get text content of an element",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector"},
                        "timeout": {"type": "integer", "default": 30000},
                    },
                    "required": ["selector"],
                },
            },
            {
                "name": "browser_wait",
                "description": "Wait for an element to reach a specific state",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector"},
                        "state": {
                            "type": "string",
                            "enum": ["attached", "detached", "visible", "hidden"],
                            "default": "visible",
                        },
                        "timeout": {"type": "integer", "default": 30000},
                    },
                    "required": ["selector"],
                },
            },
            {
                "name": "browser_evaluate",
                "description": "Evaluate JavaScript in the page context",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "JavaScript expression"},
                    },
                    "required": ["expression"],
                },
            },
            {
                "name": "browser_get_url",
                "description": "Get the current page URL and title",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "browser_select",
                "description": "Select an option from a dropdown",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector"},
                        "value": {"type": "string", "description": "Option value"},
                        "label": {"type": "string", "description": "Option label"},
                        "index": {"type": "integer", "description": "Option index"},
                        "timeout": {"type": "integer", "default": 30000},
                    },
                    "required": ["selector"],
                },
            },
            {
                "name": "browser_check",
                "description": "Check a checkbox or radio button",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector"},
                        "timeout": {"type": "integer", "default": 30000},
                    },
                    "required": ["selector"],
                },
            },
            {
                "name": "browser_press",
                "description": "Press a keyboard key (Enter, Tab, Escape, etc.)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Key to press"},
                        "selector": {"type": "string", "description": "Element to focus first (optional)"},
                    },
                    "required": ["key"],
                },
            },
            {
                "name": "browser_close",
                "description": "Close the browser",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "browser_content",
                "description": "Get the HTML content of the page",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "browser_query_all",
                "description": "Query all elements matching a selector",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector"},
                        "attribute": {"type": "string", "description": "Attribute to extract (optional)"},
                    },
                    "required": ["selector"],
                },
            },
        ]

    async def handle_tool_call(self, name: str, arguments: dict) -> Any:
        """Handle a tool call."""
        tool_map = {
            "browser_launch": self.tool_launch_browser,
            "browser_navigate": self.tool_navigate,
            "browser_click": self.tool_click,
            "browser_fill": self.tool_fill,
            "browser_type": self.tool_type,
            "browser_screenshot": self.tool_screenshot,
            "browser_get_text": self.tool_get_text,
            "browser_wait": self.tool_wait_for_selector,
            "browser_evaluate": self.tool_evaluate,
            "browser_get_url": self.tool_get_url,
            "browser_select": self.tool_select_option,
            "browser_check": self.tool_check,
            "browser_press": self.tool_press,
            "browser_close": self.tool_close_browser,
            "browser_content": self.tool_get_page_content,
            "browser_query_all": self.tool_query_selector_all,
        }

        handler = tool_map.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}"}

        return await handler(**arguments)


async def run_mcp_server():
    """Run the MCP server over stdio."""
    server = PlaywrightMCPServer()

    async def read_message():
        """Read a JSON-RPC message from stdin."""
        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        if not line:
            return None
        return json.loads(line)

    def write_message(message: dict):
        """Write a JSON-RPC message to stdout."""
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()

    try:
        while True:
            message = await read_message()
            if message is None:
                break

            method = message.get("method")
            params = message.get("params", {})
            msg_id = message.get("id")

            response = {"jsonrpc": "2.0", "id": msg_id}

            try:
                if method == "initialize":
                    response["result"] = {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "claude-harness-playwright",
                            "version": "1.0.0",
                        },
                    }

                elif method == "tools/list":
                    response["result"] = {"tools": server.get_tools_schema()}

                elif method == "tools/call":
                    tool_name = params.get("name")
                    tool_args = params.get("arguments", {})
                    result = await server.handle_tool_call(tool_name, tool_args)
                    response["result"] = {
                        "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                    }

                elif method == "notifications/initialized":
                    # Client acknowledges initialization
                    continue

                else:
                    response["error"] = {
                        "code": -32601,
                        "message": f"Method not found: {method}",
                    }

            except Exception as e:
                response["error"] = {"code": -32603, "message": str(e)}

            if msg_id is not None:
                write_message(response)

    finally:
        await server.cleanup()


def main():
    """Entry point for MCP server."""
    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    main()
