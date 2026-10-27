import os
import re
import threading
import time
from urllib.request import urlopen

import pytest
from werkzeug.serving import make_server

pytest.importorskip("selenium")

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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


def _start_game(driver, wait, base_url, name="Browser Smoke"):
    driver.get(f"{base_url}/app/")
    wait.until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, "#class-select option")) >= 4
    )
    Select(driver.find_element(By.ID, "class-select")).select_by_value("fighter")
    field = driver.find_element(By.ID, "player-name")
    field.clear()
    field.send_keys(name)
    driver.find_element(By.ID, "start-button").click()
    wait.until(lambda d: d.find_element(By.ID, "game-screen").is_displayed())
    wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "#log .log-entry")) > 0)


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

        # Ask the Dungeon Master for a hint.
        driver.find_element(By.ID, "ask-hint").click()
        wait.until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "#log .log-entry.hint"))
            > 0
        )
        hint_text = driver.find_element(
            By.CSS_SELECTOR, "#log .log-entry.hint"
        ).text
        assert hint_text.strip()
        assert "hint" in hint_text.lower()

        # Locked travel reports a message and leaves the player in the tavern.
        driver.find_element(By.ID, "command-input").send_keys("go to warehouse")
        driver.find_element(By.ID, "send-button").click()
        wait.until(lambda d: "locked" in d.find_element(By.ID, "log").text.lower())

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


def test_modal_keyboard_and_skip_links(live_server):
    driver = _make_driver()
    wait = WebDriverWait(driver, 40)

    try:
        _start_game(driver, wait, live_server, name="Keyboard Smoke")

        # Skip link moves focus straight to the command input.
        driver.execute_script("document.querySelector('.game-skip').focus()")
        driver.switch_to.active_element.send_keys(Keys.ENTER)
        assert driver.execute_script("return document.activeElement.id") == "command-input"

        # The map dialog takes focus, traps Tab and restores focus on Escape.
        driver.execute_script("document.getElementById('show-map').focus()")
        driver.find_element(By.ID, "show-map").click()
        wait.until(lambda d: d.find_element(By.ID, "map-modal").is_displayed())

        assert driver.execute_script("return document.activeElement.id") == "close-map-modal"
        assert driver.execute_script(
            "return document.querySelector('main.shell').inert"
        ) is True

        for _ in range(6):
            driver.switch_to.active_element.send_keys(Keys.TAB)
            assert driver.execute_script(
                "return document.getElementById('map-modal')"
                ".contains(document.activeElement)"
            ) is True

        driver.switch_to.active_element.send_keys(Keys.ESCAPE)
        wait.until(lambda d: not d.find_element(By.ID, "map-modal").is_displayed())
        assert driver.execute_script("return document.activeElement.id") == "show-map"
        assert driver.execute_script(
            "return document.querySelector('main.shell').inert"
        ) is False
    finally:
        driver.quit()


def test_combat_status_and_conditions_ui(live_server):
    driver = _make_driver()
    wait = WebDriverWait(driver, 40)

    try:
        _start_game(driver, wait, live_server, name="Status Smoke")

        conditions = driver.find_element(By.ID, "conditions-list")
        assert "None" in conditions.text

        # Goblin initiative uses Poison Arrow, so its cooldown should appear.
        for command in ("4", "7"):
            driver.find_element(By.ID, "command-input").send_keys(command)
            driver.find_element(By.ID, "send-button").click()
            if command == "7":
                wait.until(
                    lambda d: d.find_element(By.ID, "combat-card").is_displayed()
                )
            else:
                wait.until(
                    lambda d: "How do you want to choose"
                    in d.find_element(By.ID, "log").text
                )

        driver.find_element(By.ID, "command-input").send_keys("1")
        driver.find_element(By.ID, "send-button").click()
        wait.until(
            lambda d: "Poison Arrow"
            in d.find_element(By.ID, "combat-card").text
        )

        # The conditions panel formats active effects.
        driver.execute_script(
            "renderConditions({poison: {damage: 2, turns: 3}, "
            "advantage: true})"
        )
        conditions_text = driver.find_element(By.ID, "conditions-list").text
        assert "Poisoned" in conditions_text
        assert "2/turn" in conditions_text
        assert "Advantage" in conditions_text

        # Guard and cooldown tags render in the combat card.
        driver.execute_script(
            "renderCombat({in_combat: true, round: 1, turn_of: 'player', "
            "target: 'Goblin', enemies: [{name: 'Goblin', hp: 5, "
            "max_hp: 10, guard: 4, cooldowns: [{id: 'poison_arrow', "
            "name: 'Poison Arrow', remaining: 2}]}], allies: []})"
        )
        combat_text = driver.find_element(By.ID, "combat-card").text
        assert "Guard 4" in combat_text
        assert "Poison Arrow: 2" in combat_text
    finally:
        driver.quit()


def test_mobile_layout_and_targets(live_server):
    driver = _make_driver()
    driver.set_window_size(390, 844)
    wait = WebDriverWait(driver, 40)

    try:
        _start_game(driver, wait, live_server, name="Mobile Smoke")

        dimensions = driver.execute_script(
            "return {scroll: document.documentElement.scrollWidth, "
            "inner: window.innerWidth}"
        )
        assert dimensions["scroll"] <= dimensions["inner"] + 1, dimensions

        command_box = driver.execute_script(
            "const r = document.getElementById('command-input')"
            ".getBoundingClientRect();"
            "return {bottom: r.bottom, inner: window.innerHeight};"
        )
        assert command_box["bottom"] <= command_box["inner"], command_box

        assert driver.find_element(By.ID, "send-button").size["height"] >= 44
        wait.until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "#quick-actions button")) > 0
        )
        quick = driver.find_element(By.CSS_SELECTOR, "#quick-actions button")
        assert quick.size["height"] >= 44

        toggle = driver.find_element(By.ID, "theme-toggle")
        assert toggle.get_attribute("aria-label") == "Switch to light theme"
        toggle.click()
        wait.until(
            lambda d: d.find_element(By.ID, "theme-toggle").get_attribute(
                "aria-label"
            )
            == "Switch to dark theme"
        )

        driver.find_element(By.ID, "show-map").click()
        wait.until(lambda d: d.find_element(By.ID, "map-modal").is_displayed())
        bounds = driver.execute_script(
            "const r = document.querySelector('#map-modal .modal-card')"
            ".getBoundingClientRect();"
            "return {left: r.left, right: r.right, top: r.top, bottom: r.bottom,"
            " width: window.innerWidth, height: window.innerHeight};"
        )
        assert bounds["left"] >= 0
        assert bounds["right"] <= bounds["width"] + 1
        assert bounds["top"] >= 0
        assert bounds["bottom"] <= bounds["height"] + 1
    finally:
        driver.quit()
