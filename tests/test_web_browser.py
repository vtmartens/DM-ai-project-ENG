import os
import re
import threading
import time
from urllib.request import urlopen

import pytest
from werkzeug.serving import make_server

pytest.importorskip("selenium")

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait


def _make_driver():
    """Uses Chrome in CI, falls back to Edge locally, skips if neither exists."""
    from selenium import webdriver

    errors = []
    candidates = (
        ("chrome", webdriver.Chrome, webdriver.ChromeOptions),
        ("edge", webdriver.Edge, webdriver.EdgeOptions),
    )

    for name, driver_class, options_class in candidates:
        options = options_class()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1440,1000")
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        try:
            return driver_class(options=options)
        except Exception as exc:  # driver/browser unavailable
            errors.append(f"{name}: {exc}")

    message = "No Chromium browser available for the smoke test: " + " | ".join(errors)
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture
def live_server():
    import server as server_module

    httpd = make_server("127.0.0.1", 0, server_module.app, threaded=True)
    port = httpd.server_port
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urlopen(url, timeout=1).read()
            break
        except Exception:
            time.sleep(0.1)
    else:
        httpd.shutdown()
        pytest.fail("The Flask test server did not start")

    try:
        yield url
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_web_client_smoke(live_server):
    driver = _make_driver()
    wait = WebDriverWait(driver, 40)

    try:
        driver.get(f"{live_server}/app/")
        wait.until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "#class-select option")) >= 4
        )

        Select(driver.find_element(By.ID, "class-select")).select_by_value("fighter")
        name = driver.find_element(By.ID, "player-name")
        name.clear()
        name.send_keys("Browser Smoke")
        driver.find_element(By.ID, "start-button").click()

        wait.until(lambda d: d.find_element(By.ID, "game-screen").is_displayed())
        wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "#log .log-entry")) > 0)

        # Achievements panel: catalogue rendered, count badge populated.
        wait.until(
            lambda d: len(
                d.find_elements(By.CSS_SELECTOR, "#achievements-list .achievement")
            )
            > 0
        )
        achievements_text = driver.find_element(By.ID, "achievements-list").text
        assert "First Step" in achievements_text
        assert "Locked" in achievements_text
        assert re.fullmatch(
            r"\d+ / \d+",
            driver.find_element(By.ID, "achievements-count").text.strip(),
        )

        # Natural-language targeting: this used to open the NPC list.
        driver.find_element(By.ID, "command-input").send_keys("talk to Durnan")
        driver.find_element(By.ID, "send-button").click()
        wait.until(lambda d: d.find_element(By.ID, "dialogue-card").is_displayed())
        wait.until(
            lambda d: len(
                d.find_elements(By.CSS_SELECTOR, "#dialogue-card .dialogue-options button")
            )
            > 0
        )
        assert "Durnan" in driver.find_element(By.ID, "dialogue-card").text

        # Map modal and its generated legend.
        driver.find_element(By.ID, "show-map").click()
        wait.until(lambda d: d.find_element(By.ID, "map-modal").is_displayed())
        ascii_text = driver.find_element(By.ID, "map-ascii").text
        assert "P" in ascii_text
        assert len({len(line) for line in ascii_text.splitlines()}) == 1
        legend_text = driver.find_element(By.ID, "map-legend").text
        assert "Chair" in legend_text
        assert "(NPC)" in legend_text
        driver.find_element(By.ID, "close-map-modal").click()

        severe = [
            entry
            for entry in driver.get_log("browser")
            if entry.get("level") == "SEVERE" and "favicon.ico" not in entry.get("message", "")
        ]
        assert not severe, severe
    finally:
        driver.quit()
