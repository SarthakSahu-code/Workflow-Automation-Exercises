import os
import sys
import time
import threading
import requests
import webbrowser

BASE_URL = "http://localhost:8088/v2"
OPERATE_URL = "http://localhost:8088/operate"

def check_camunda_alive():
    try:
        r = requests.get(f"{BASE_URL}/topology", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

def deploy_all():
    print("[1/4] Deploying process models and DMN decision...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    files = [
        ('resources', ('slot_decision.dmn', open(os.path.join(base_dir, 'slot_decision.dmn'), 'rb'), 'application/octet-stream')),
        ('resources', ('send-notification.bpmn', open(os.path.join(base_dir, 'send-notification.bpmn'), 'rb'), 'application/octet-stream')),
        ('resources', ('appointment-booking.bpmn', open(os.path.join(base_dir, 'appointment-booking.bpmn'), 'rb'), 'application/octet-stream'))
    ]
    resp = requests.post(f"{BASE_URL}/deployments", files=files)
    if resp.status_code == 200:
        data = resp.json()
        print(f"       Models successfully deployed (DeploymentKey: {data.get('deploymentKey')})")
        return True
    else:
        print(f"      [!] Deployment failed: {resp.status_code} {resp.text}")
        return False

def activate_and_complete_jobs(job_type, worker_name="demo-runner"):
    payload = {
        "type": job_type,
        "worker": worker_name,
        "timeout": 30000,
        "maxJobsToActivate": 10,
        "requestTimeout": 1000
    }
    try:
        resp = requests.post(f"{BASE_URL}/jobs/activation", json=payload, timeout=5)
        if resp.status_code == 200:
            jobs = resp.json().get("jobs", [])
            for job in jobs:
                key = job.get("jobKey")
                vars_dict = job.get("variables", {})
                pid = vars_dict.get("patientId", "Unknown")
                res = {"slotBooked": True, "bookingRef": f"BK-{pid}"} if job_type == "book-slot" else {"slotReleased": True}
                requests.post(f"{BASE_URL}/jobs/{key}/completion", json={"variables": res}, timeout=5)
                print(f"      [Worker] Handled '{job_type}' for patient {pid}")
    except Exception:
        pass

def worker_bg_loop(stop_event):
    while not stop_event.is_set():
        activate_and_complete_jobs("book-slot")
        activate_and_complete_jobs("release-slot")
        time.sleep(1)

def run():
    print("=" * 65)
    print("  HOSPITAL APPOINTMENT BOOKING PROCESS - DEMO RUNNER")
    print("=" * 65)
    
    if not check_camunda_alive():
        print(f"❌ Camunda 8 is not responding at {BASE_URL}.")
        print("   Please start c8run on port 8088: c8run.exe start -port 8088")
        return

    if not deploy_all():
        return

    stop_worker = threading.Event()
    worker_thread = threading.Thread(target=worker_bg_loop, args=(stop_worker,), daemon=True)
    worker_thread.start()
    print("[2/4] Started embedded service worker for 'book-slot' and 'release-slot'...")

    print("[3/4] Triggering Test Cases...")
    # Case 1: Cardiology with bookedCount = 3
    print("   -> Case 1: Starting Cardiology booking with bookedCount = 3 (Booking Succeeds)...")
    r1 = requests.post(f"{BASE_URL}/process-instances", json={
        "processDefinitionId": "appointment-booking",
        "variables": {
            "patientId": "PAT-101",
            "patientName": "John Doe",
            "department": "Cardiology",
            "preferredSlot": "10:00 AM",
            "bookedCount": 3
        }
    }).json()
    k1 = r1.get("processInstanceKey")
    print(f"      Instance Key: {k1}")

    # Case 2: Cardiology with bookedCount = 12
    print("   -> Case 2: Starting Cardiology booking with bookedCount = 12 (Slot FULL)...")
    r2 = requests.post(f"{BASE_URL}/process-instances", json={
        "processDefinitionId": "appointment-booking",
        "variables": {
            "patientId": "PAT-102",
            "patientName": "Jane Smith",
            "department": "Cardiology",
            "preferredSlot": "11:30 AM",
            "bookedCount": 12
        }
    }).json()
    k2 = r2.get("processInstanceKey")
    print(f"      Instance Key: {k2}")

    # Case 3: Cardiology with bookedCount = 5 + Cancellation
    print("   -> Case 3: Starting booking for Alice Brown (PAT-103), then triggering cancellation...")
    r3 = requests.post(f"{BASE_URL}/process-instances", json={
        "processDefinitionId": "appointment-booking",
        "variables": {
            "patientId": "PAT-103",
            "patientName": "Alice Brown",
            "department": "Cardiology",
            "preferredSlot": "02:00 PM",
            "bookedCount": 5
        }
    }).json()
    k3 = r3.get("processInstanceKey")
    print(f"      Instance Key: {k3}")

    print("      Waiting 3 seconds for initial booking flow to reach wait state...")
    time.sleep(3)

    print("      Publishing 'CancelAppointment' message with correlationKey 'PAT-103'...")
    requests.post(f"{BASE_URL}/messages/publication", json={
        "name": "CancelAppointment",
        "correlationKey": "PAT-103",
        "timeToLive": 60000,
        "variables": {"reason": "Patient requested cancellation"}
    })
    print("      [+] Cancellation message published!")

    print("\n[4/4] Summary of Process Instances for Operate Inspection:")
    print("-" * 65)
    print(f"  * Case 1 (Booking Succeeds): Instance Key {k1}")
    print(f"  * Case 2 (Slot Full):       Instance Key {k2}")
    print(f"  * Case 3 (Cancelled):       Instance Key {k3}")
    print("-" * 65)
    print(f"[*] Camunda Operate URL: {OPERATE_URL}")
    print("   Username: demo")
    print("   Password: demo")
    print("=" * 65)

if __name__ == "__main__":
    run()
