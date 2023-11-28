#!/usr/bin/env python3

from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import ElementClickInterceptedException
import dotenv
import json
from typing import Iterator
import time
import sys
import csv
import os

dotenv.load_dotenv()

def loop_until_timeout(timeout:float) -> Iterator:
    start = time.monotonic()
    while True:
        now = time.monotonic()
        if now - start > timeout:
            raise TimeoutError()
        yield


def is_loaded_main_page(driver:WebDriver) -> bool:
    try:
        elem = driver.find_element_by_id("overviewMemberInfo")
    except NoSuchElementException:
        return False
    return elem.is_displayed()

def wait_loaded_main_page(driver:WebDriver) -> None:
    for _ in loop_until_timeout(30):
        if is_loaded_main_page(driver):
            break


def is_loaded_claims_list(driver:WebDriver) -> bool:
    try:
        elem = driver.find_element_by_id("eobViewLink")
    except NoSuchElementException:
        return False
    return elem.is_displayed()

def wait_loaded_claims_list(driver:WebDriver) -> None:
    for _ in loop_until_timeout(30):
        if is_loaded_claims_list(driver):
            break


def is_loaded_eob_detail(driver:WebDriver) -> bool:
    try:
        elem = driver.find_element_by_link_text("Contact us about this EOB")
    except NoSuchElementException:
        return False
    return elem.is_displayed()

def wait_loaded_eob_detail(driver:WebDriver) -> None:
    for _ in loop_until_timeout(30):
        if is_loaded_eob_detail(driver):
            break


def login(driver: WebDriver, username:str, password:str) -> None:
    driver.get("https://pmakportal.valence.care")
    username_elem = driver.find_element_by_id("USERSXUSERNAME")
    username_elem.send_keys(username)
    password_elem = driver.find_element_by_id("USERSXPASSWORD")
    password_elem.send_keys(password)
    submit = driver.find_element_by_id("SubmitButton")
    submit.click()
    wait_loaded_main_page(driver)


def navigate_to_claims(driver:WebDriver) -> None:
    claims_menu = driver.find_element_by_id("claim_and_benefits")
    hidden_claims_list = driver.find_element_by_id("claims")

    actions = ActionChains(driver)
    #actions.scroll_to_element(claims_menu)
    actions.move_to_element(claims_menu)
    actions.click(hidden_claims_list)
    actions.perform()
    wait_loaded_claims_list(driver)


def get_claim_data_from_eob_detail(driver:WebDriver) -> dict:
    payee_block = driver.find_element_by_id("eobPayeeInformation")
    spans = payee_block.find_elements_by_css_selector("span")
    return dict((span.get_attribute("label"), span.text) for span in spans)


def iter_service_items_from_eob_detail(driver:WebDriver) -> Iterator[dict]:
    claim_data = get_claim_data_from_eob_detail(driver)
    service_line_table = driver.find_element_by_css_selector("table.service-lines")
    ths = service_line_table.find_elements_by_css_selector("th")
    headers = [th.text for th in ths]
    for tr in service_line_table.find_elements_by_css_selector("tbody>tr"):
        if not tr.is_displayed():
            continue
        tds = tr.find_elements_by_tag_name("td")
        # "Total" row uses colspan
        if any(td.get_attribute("colspan") not in ("1", None, False) for td in tds):
            continue
        values = [td.text for td in tds]
        service_item = dict(zip(headers, values))
        service_item.update(claim_data)
        yield service_item


def iter_service_items(driver:WebDriver) -> Iterator[dict]:
    navigate_to_claims(driver)
    while True:
        eob_links = driver.find_elements_by_id("eobViewLink")
        visible_eob_links = [link for link in eob_links if link.is_displayed()]
        for eob_link in visible_eob_links:
            eob_link.click()
            wait_loaded_eob_detail(driver)
            for item in iter_service_items_from_eob_detail(driver):
                yield item
            driver.back()
        next_link = driver.find_element_by_class_name("next_link")
        try:
            next_link.click()
        except ElementClickInterceptedException:
            break
        

def main() -> int:
    username = os.environ["EOB_USER"]
    password = os.environ["EOB_PASS"]

    with webdriver.Firefox() as driver:
        login(driver, username, password)
        service_items = list(iter_service_items(driver))
        fieldnames = sorted(set(k for item in service_items for k in item.keys()))
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        for item in service_items:
            writer.writerow(item)


if __name__ == "__main__":
    raise SystemExit(main())
