import time
import requests
import json
import sys

BASE_URL = "http://localhost:8088/v2"

def activate_and_complete_jobs(job_type, worker_name="hospital-worker"):
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
            data = resp.json()
            jobs = data.get("jobs", [])
            for job in jobs:
                job_key = job.get("jobKey")
                variables = job.get("variables", {})
                patient_id = variables.get("patientId", "Unknown")
                dept = variables.get("department", "Unknown")
                slot = variables.get("preferredSlot", "Unknown")
                print(f"[Worker] Activated job {job_key} of type '{job_type}' for patient {patient_id} ({dept} @ {slot})")

                # Process job logic
                result_vars = {}
                if job_type == "book-slot":
                    result_vars = {"slotBooked": True, "bookingRef": f"BK-{patient_id}"}
                    print(f"[Worker] -> Slot BOOKED successfully for {patient_id}. Reference: BK-{patient_id}")
                elif job_type == "release-slot":
                    result_vars = {"slotReleased": True}
                    print(f"[Worker] -> Slot RELEASED for {patient_id}.")

                # Complete the job
                comp_resp = requests.post(f"{BASE_URL}/jobs/{job_key}/completion", json={"variables": result_vars}, timeout=5)
                if comp_resp.status_code == 204 or comp_resp.status_code == 200:
                    print(f"[Worker] -> Job {job_key} completed successfully.")
                else:
                    print(f"[Worker] -> Failed to complete job {job_key}: {comp_resp.status_code} {comp_resp.text}")
    except Exception as e:
        # Ignore connection errors during polling
        pass

def run_worker_loop():
    print("[Worker] Hospital Appointment Service Worker started.")
    print("[Worker] Polling for 'book-slot' and 'release-slot' jobs...")
    while True:
        activate_and_complete_jobs("book-slot")
        activate_and_complete_jobs("release-slot")
        time.sleep(1)

if __name__ == "__main__":
    run_worker_loop()
