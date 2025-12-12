"""Example E2E test."""
import pytest
from playwright.sync_api import Page, expect


def test_homepage_loads(page: Page):
    """Test that the homepage loads successfully."""
    page.goto("/")
    # Customize based on your app
    # expect(page).to_have_title("Your App Title")


def test_health_endpoint(page: Page):
    """Test that health endpoint responds."""
    response = page.request.get("/health")
    assert response.ok
