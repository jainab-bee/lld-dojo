from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app, repository


@pytest.fixture
def client():
    return TestClient(app)


def test_home_page_lists_problems(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Practice Problems" in response.text
    assert "Parking Lot System" in response.text
    assert "Vending Machine" in response.text
    assert "Elevator System" in response.text


def test_problem_detail_page_renders_form(client):
    response = client.get("/problems/parking-lot")
    assert response.status_code == 200
    assert "Parking Lot System" in response.text
    assert "Assumptions" in response.text
    assert "Classes &amp; Responsibilities" in response.text or "Classes & Responsibilities" in response.text
    assert "Relationships" in response.text
    assert "Key Execution Flow" in response.text
    assert "Tradeoffs" in response.text


def test_submit_empty_or_too_short_design_rejected_with_clear_message(client):
    # Empty submission
    response = client.post(
        "/problems/parking-lot/submit",
        data={
            "assumptions": "",
            "classes_and_responsibilities": "",
            "relationships": "",
            "key_flow": "",
            "tradeoffs": "",
            "idempotency_key": "test-empty-key",
        },
    )
    assert response.status_code == 400
    assert "Assumptions" in response.text and "section is empty" in response.text

    # Too short section
    response2 = client.post(
        "/problems/parking-lot/submit",
        data={
            "assumptions": "Short assumptions",
            "classes_and_responsibilities": "Short classes",
            "relationships": "Short rels",
            "key_flow": "Short flow",
            "tradeoffs": "Short",  # < 15 chars
            "idempotency_key": "test-short-key",
        },
    )
    assert response2.status_code == 400
    assert "too brief" in response2.text or "too short overall" in response2.text


def test_valid_submission_flow_and_idempotency(client):
    data = {
        "assumptions": "Multi-floor parking lot with motorcycle and car spaces. Gate handles concurrency.",
        "classes_and_responsibilities": (
            "class ParkingLot manages floors and tickets. "
            "class ParkingSpot tracks availability. "
            "class Ticket records vehicle entry time. "
            "class FeeCalculator computes fees."
        ),
        "relationships": (
            "ParkingLot has-a list of ParkingFloors. "
            "ParkingFloor has-a list of ParkingSpots. "
            "Car is-a Vehicle."
        ),
        "key_flow": (
            "1. Vehicle arrives. 2. ParkingLot finds nearest spot. "
            "3. Ticket issued. 4. Spot occupied. 5. On exit, fee calculated."
        ),
        "tradeoffs": (
            "Used Strategy pattern instead of conditionals for spot allocation. "
            "Tradeoff: more classes vs high extensibility."
        ),
        "idempotency_key": "unique-route-test-key-101",
    }

    # First submit -> redirects to /submissions/{id}
    res1 = client.post("/problems/parking-lot/submit", data=data, follow_redirects=False)
    assert res1.status_code == 303
    redirect_url = res1.headers["location"]
    submission_id = redirect_url.split("/")[-1]

    # Second submit with the exact same idempotency key -> redirects to the exact same submission
    res2 = client.post("/problems/parking-lot/submit", data=data, follow_redirects=False)
    assert res2.status_code == 303
    assert res2.headers["location"] == redirect_url

    # Check submission status page
    sub_page = client.get(f"/submissions/{submission_id}")
    assert sub_page.status_code == 200
    assert "Parking Lot System" in sub_page.text


def test_history_page_loads(client):
    response = client.get("/history")
    assert response.status_code == 200
    assert "Attempt History" in response.text
    assert "Parking Lot System" in response.text


def test_compare_route_shows_comparison(client):
    # Submit first attempt
    data1 = {
        "assumptions": "Vending machine has standard coin denominations and inventory checks.",
        "classes_and_responsibilities": (
            "class VendingMachine handles state transitions. "
            "class Inventory manages stock of items. "
            "class CoinDispenser returns change."
        ),
        "relationships": (
            "VendingMachine has-a Inventory. "
            "VendingMachine has-a CoinDispenser."
        ),
        "key_flow": "1. Insert money. 2. Select item. 3. Dispense item. 4. Return change.",
        "tradeoffs": "Used State pattern instead of multiple boolean flags for machine state.",
        "idempotency_key": "vending-att-1-key",
    }
    res1 = client.post("/problems/vending-machine/submit", data=data1, follow_redirects=False)
    sub1_id = res1.headers["location"].split("/")[-1]
    sub1 = repository.get_submission(sub1_id)

    # Submit second attempt (revision)
    data2 = {
        "assumptions": "Vending machine supports cash, coins, and handles insufficient change error.",
        "classes_and_responsibilities": (
            "class VendingMachine handles state transitions. "
            "class Inventory manages stock of items. "
            "class PaymentProcessor handles cash and digital wallet payments. "
            "class CoinDispenser returns change."
        ),
        "relationships": (
            "VendingMachine has-a Inventory. "
            "VendingMachine has-a PaymentProcessor. "
            "PaymentProcessor implements PaymentStrategy."
        ),
        "key_flow": "1. Select item. 2. Choose payment method. 3. Dispense item. 4. Return change.",
        "tradeoffs": "Used Strategy pattern for payments to easily support digital wallets (change request).",
        "idempotency_key": "vending-att-2-key",
    }
    res2 = client.post("/problems/vending-machine/submit", data=data2, follow_redirects=False)
    sub2_id = res2.headers["location"].split("/")[-1]
    sub2 = repository.get_submission(sub2_id)

    # Now request /compare?a={sub1.attempt_id}&b={sub2.attempt_id}
    compare_res = client.get(f"/compare?a={sub1.attempt_id}&b={sub2.attempt_id}")
    assert compare_res.status_code == 200
    assert "Attempt Comparison" in compare_res.text
    assert "Rubric Score Deltas" in compare_res.text
    assert "Concern Evolution" in compare_res.text
