import requests
import json
import time

BASE_URL = "http://localhost:8088/v2"

def deploy_models():
    print("==================================================")
    print("STEP 1: Deploying BPMN and DMN models to Camunda 8")
    print("==================================================")
    files = [
        ('resources', ('slot_decision.dmn', open(r'c:\Hospital-appointment-booking\slot_decision.dmn', 'rb'), 'application/octet-stream')),
        ('resources', ('send-notification.bpmn', open(r'c:\Hospital-appointment-booking\send-notification.bpmn', 'rb'), 'application/octet-stream')),
        ('resources', ('appointment-booking.bpmn', open(r'c:\Hospital-appointment-booking\appointment-booking.bpmn', 'rb'), 'application/octet-stream'))
    ]
    resp = requests.post(f"{BASE_URL}/deployments", files=files)
    if resp.status_code == 200:
        data = resp.json()
        print(" [+] Deployment successful! Deployment Key:", data.get("deploymentKey"))
        for d in data.get("deployments", []):
            if "processDefinition" in d:
                pd = d["processDefinition"]
                print(f"   - Process: {pd['processDefinitionId']} (v{pd['processDefinitionVersion']}, Key: {pd['processDefinitionKey']})")
            elif "decisionDefinition" in d:
                dd = d["decisionDefinition"]
                print(f"   - Decision: {dd['decisionDefinitionId']} (v{dd['version']}, Key: {dd['decisionDefinitionKey']})")
        return True
    else:
        print(f" [!] Deployment failed: {resp.status_code} {resp.text}")
        return False

def start_instance(patient_id, patient_name, department, preferred_slot, booked_count):
    payload = {
        "processDefinitionId": "appointment-booking",
        "variables": {
            "patientId": patient_id,
            "patientName": patient_name,
            "department": department,
            "preferredSlot": preferred_slot,
            "bookedCount": booked_count
        }
    }
    resp = requests.post(f"{BASE_URL}/process-instances", json=payload)
    if resp.status_code in [200, 201]:
        data = resp.json()
        key = data.get("processInstanceKey")
        print(f" [+] Started instance {key} for {patient_name} ({patient_id}) - {department}, BookedCount={booked_count}")
        return key
    else:
        print(f" [!] Failed to start instance: {resp.status_code} {resp.text}")
        return None

def publish_cancellation_message(patient_id):
    payload = {
        "name": "CancelAppointment",
        "correlationKey": patient_id,
        "timeToLive": 60000,
        "variables": {
            "cancellationReason": "Patient requested cancellation via Telegram"
        }
    }
    resp = requests.post(f"{BASE_URL}/messages/publication", json=payload)
    if resp.status_code in [200, 201, 204]:
        print(f" [+] Published CancelAppointment message for correlationKey '{patient_id}'")
        return True
    else:
        print(f" [!] Failed to publish message: {resp.status_code} {resp.text}")
        return False

def run_all_cases():
    if not deploy_models():
        return

    print("\n==================================================")
    print("STEP 2: Running Case 1 - Cardiology with bookedCount = 3 (Booking Succeeds)")
    print("==================================================")
    key1 = start_instance(
        patient_id="PAT-101",
        patient_name="John Doe",
        department="Cardiology",
        preferred_slot="10:00 AM",
        booked_count=3
    )

    print("\n==================================================")
    print("STEP 3: Running Case 2 - Cardiology with bookedCount = 12 (Slot FULL)")
    print("==================================================")
    key2 = start_instance(
        patient_id="PAT-102",
        patient_name="Jane Smith",
        department="Cardiology",
        preferred_slot="11:30 AM",
        booked_count=12
    )

    print("\n==================================================")
    print("STEP 4: Running Case 3 - Successful Booking Followed by Cancellation Message")
    print("==================================================")
    key3 = start_instance(
        patient_id="PAT-103",
        patient_name="Alice Brown",
        department="Cardiology",
        preferred_slot="02:00 PM",
        booked_count=5
    )

    print("\nWaiting 3 seconds for Case 3 to complete initial booking and reach wait state...")
    time.sleep(3)

    print("\nSending Cancellation Message for Case 3 (correlationKey: PAT-103)...")
    publish_cancellation_message("PAT-103")

    print("\n==================================================")
    print("SUMMARY OF TEST INSTANCES")
    print("==================================================")
    print(f"Case 1 (Success):     Instance Key {key1}")
    print(f"Case 2 (Slot Full):   Instance Key {key2}")
    print(f"Case 3 (Cancelled):   Instance Key {key3}")
    print("\nAccess Camunda Operate at:")
    print("http://localhost:8088/operate")
    print("Credentials: demo / demo")
    print("==================================================")

if __name__ == "__main__":
    run_all_cases()
