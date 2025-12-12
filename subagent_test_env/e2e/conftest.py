"""E2E test configuration for Playwright."""
import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context."""
    return {
        **browser_context_args,
        "base_url": "http://localhost:8000",
        "viewport": {"width": 1280, "height": 720},
    }


@pytest.fixture
def authenticated_page(page: Page):
    """Fixture for authenticated page (customize login flow)."""
    # TODO: Implement your login flow
    # page.goto("/login")
    # page.fill("[name=email]", "test@example.com")
    # page.fill("[name=password]", "password")
    # page.click("button[type=submit]")
    # expect(page).to_have_url("/dashboard")
    return page
