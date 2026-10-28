# Hospital Appointment Booking System (Camunda 8)

A complete end-to-end implementation of an automated Hospital Appointment Booking process orchestrated with **Camunda 8**, **BPMN 2.0**, **DMN 1.3**, **Zeebe REST Outbound Connectors**, **Call Activities**, and **Interrupting Event Subprocesses**.

---

## 1. Project Overview & Architecture

### Process Landscape
```
                    +---------------------------+
                    |    Booking requested      |
                    +-------------+-------------+
                                  |
                                  v
                    +-------------+-------------+
                    |   Check slot (DMN)        |
                    +-------------+-------------+
                                  |
                        [ Slot available? ]
                       /                   \
        (AVAILABLE)   /                     \  (FULL)
                     v                       v
        +------------+------------+     +----+--------------------+
        |       Book slot         |     | Call send-notification  |
        +------------+------------+     | ("Slot FULL" notice)    |
                     |                  +----+--------------------+
                     v                       |
        +------------+------------+          v
        | Call send-notification  |     +----+--------------------+
        | (Confirmation notice)   |     | Booking rejected (FULL) |
        +------------+------------+     +-------------------------+
                     |
                     v
        +------------+------------+
        |  Await patient check-in |
        +------------+------------+
                     |
                     v
        +------------+------------+
        | Appointment completed   |
        +-------------------------+

========================================================================
Event Subprocess: "Handle cancellation" (Interrupting Message Start Event)
========================================================================
   [ Message: CancelAppointment (=patientId) ]
                     |
                     v
        +------------+------------+
        |      Release slot       |
        +------------+------------+
                     |
                     v
        +------------+------------+
        | Call send-notification  |
        | ("Cancellation notice") |
        +------------+------------+
                     |
                     v
        +------------+------------+
        |    Booking cancelled    |
        +-------------------------+
```

---

## 2. Component Specifications

### 1. Reusable Child Process: `send-notification.bpmn`
* **Process ID**: `send-notification`
* **Start Event**: `Notification requested`
* **REST Outbound Connector Task**:
  * **Element ID**: `Task_SendTelegram`
  * **Task Type**: `io.camunda:http-json:1` (Template: `io.camunda.connectors.HttpJson.v2`)
  * **Method**: `POST`
  * **URL**: `https://api.telegram.org/bot{{secrets.TELEGRAM_BOT_TOKEN}}/sendMessage`
  * **Body**: `={"chat_id": recipientId, "text": messageText}`
  * **Headers**: `resultVariable = telegramResponse`, `errorExpression = =null`
* **End Event**: `Notification sent`

### 2. DMN Decision Table: `slot_decision.dmn`
* **Decision ID**: `slot_decision`
* **Hit Policy**: `UNIQUE` (`U`)
* **Inputs**:
  1. `department` (`string`) - Medical department (e.g., `"Cardiology"`)
  2. `bookedCount` (`number`) - Currently booked slots count
* **Outputs**:
  1. `slotStatus` (`string`) - `"AVAILABLE"` or `"FULL"`
  2. `suggestedAction` (`string`) - Recommendation message
* **Rules Matrix**:
  | Rule ID | Department | Booked Count | Slot Status | Suggested Action |
  | :--- | :--- | :--- | :--- | :--- |
  | Rule 1 | `"Cardiology"` | `< 10` | `"AVAILABLE"` | `"Proceed with Cardiology slot booking"` |
  | Rule 2 | `"Cardiology"` | `>= 10` | `"FULL"` | `"Offer waitlist or next available Cardiology day"` |
  | Rule 3 | `not("Cardiology")`| `< 15` | `"AVAILABLE"` | `"Proceed with standard department booking"` |
  | Rule 4 | `not("Cardiology")`| `>= 15` | `"FULL"` | `"Department full; suggest alternative slot"` |

### 3. Parent Process: `appointment-booking.bpmn`
* **Process ID**: `appointment-booking`
* **Business Rule Task**: `Check slot` calling `slot_decision`, output stored in `decisionResult`.
* **Gateway**:
  * Branch `AVAILABLE`: Condition `=decisionResult.slotStatus = "AVAILABLE"` -> Service task `Book slot` (`type="book-slot"`) -> Call Activity `Send confirmation` -> User Task `Await patient check-in`.
  * Branch `FULL`: Sequence flow -> Call Activity `Send slot full notice` -> End event `Booking rejected (Full)`.
* **Event Subprocess**: `Handle cancellation`
  * `triggeredByEvent="true"`
  * **Message Start Event**: Message `CancelAppointment`, correlationKey `=patientId`.
  * **Service Task**: `Release slot` (`type="release-slot"`).
  * **Call Activity**: `Send cancellation notice`.
  * **End Event**: `Booking cancelled`.

---

## 3. Task 4: Input & Output Mappings Detailed Comparison

| Criterion | Propagation ON (`propagateAllChildVariables="true"`) | Propagation OFF (`propagateAllChildVariables="false"`) |
| :--- | :--- | :--- |
| **Child Variable Return** | All child variables (`telegramResponse`, HTTP headers, connector tokens) leak back into the parent process scope. | No child variables leak. Only variables explicitly produced in parent scope persist. |
| **Encapsulation** | **Violated**. Parent process scope gets polluted with transport-level technical metadata. | **Maintained**. Clean separation between domain workflow and messaging infrastructure. |
| **Collision Risk** | **High**. If the child process is invoked multiple times (e.g. Confirmation then Cancellation), `telegramResponse` gets overwritten silently. | **Zero**. Child instances operate within isolated variable scopes. |
| **Data Privacy & Leakage** | All parent variables (`patientId`, `patientName`, `bookedCount`) are copied into the child process. | Only the mapped input variables (`recipientId`, `messageText`) are passed to the child process. |
| **Best Practice** | Discouraged for modular, reusable sub-processes. | **Recommended standard** for reusable microservice and notification tasks. |

---

## 4. How to Run the Project & Take Screenshots

### Step 1: Ensure Camunda 8 Run (c8run) is Running
Camunda 8 Run is started on port **8088**:
* **Operate URL**: [http://localhost:8088/operate](http://localhost:8088/operate)
* **Credentials**:
  * Username: `demo`
  * Password: `demo`

*(If c8run needs to be started manually, open Command Prompt, navigate to `C:\Users\hp\Downloads\camunda8-run-8.8\c8run-8.8.37` and run: `c8run.exe start -port 8088`)*

---

### Step 2: Run the Automated Demo
Open PowerShell or Command Prompt in `C:\Hospital-appointment-booking` and run:

```powershell
python run_demo.py
```

This single command automatically:
1. Deploys `appointment-booking.bpmn`, `send-notification.bpmn`, and `slot_decision.dmn`.
2. Starts the background worker for `book-slot` and `release-slot`.
3. Runs all 3 required test cases:
   * **Case 1**: Cardiology, bookedCount = 3 (Booking succeeds).
   * **Case 2**: Cardiology, bookedCount = 12 (Slot full).
   * **Case 3**: Cardiology, bookedCount = 5, followed by cancellation message.
4. Outputs the exact **Process Instance Keys** for inspection.

---

### Step 3: Taking the Required Screenshots in Operate

Open [http://localhost:8088/operate](http://localhost:8088/operate) and log in with `demo / demo`.

#### Screenshot 1: Parent Process Instance (Booking Succeeds)
1. Click **Processes** in the top navigation bar.
2. Select **Hospital Appointment Booking** from the process dropdown.
3. In the instances table at the bottom, click the instance for **Case 1 (PAT-101)**.
4. **Capture**: The process diagram showing:
   * Blue/green tokens through `Booking requested` -> `Check slot` -> `Gateway` -> `Book slot` -> `Send confirmation` -> `Await patient check-in`.

#### Screenshot 2: Child Process Linked from Call Activity
1. In the instance view of **Case 1** (or Case 2), look at the right/bottom panel under **Called Process Instances**.
2. Click the link to the child instance `Send Notification`.
3. **Capture**: The child process view showing:
   * Token path through `Notification requested` -> `Send Telegram message` -> `Notification sent`.
   * The breadcrumbs at the top showing the link back to the parent process instance.
   * In the **Variables** pane on the right, observe `recipientId` (`"PAT-101"`) and `messageText`.

#### Screenshot 3: Slot Full Path (Case 2)
1. Go back to **Processes** -> **Hospital Appointment Booking**.
2. Select the instance for **Case 2 (PAT-102)** (`bookedCount = 12`).
3. **Capture**: The diagram showing:
   * Path taken through the `FULL` gateway branch -> `Send slot full notice` -> `Booking rejected (Full)`.

#### Screenshot 4: Cancellation Event Subprocess (Case 3)
1. Go back to **Processes** -> **Hospital Appointment Booking**.
2. Select the instance for **Case 3 (PAT-103)**.
3. **Capture**:
   * The initial path at `Await patient check-in` being interrupted (cancelled).
   * Inside the event subprocess box `Handle cancellation`, the green execution path through:
     `Cancellation received` -> `Release slot` -> `Send cancellation notice` -> `Booking cancelled`.

#### Screenshot 5: DMN Decision Evaluation (Bonus / Comprehensive)
1. Click **Decisions** in the top navigation bar.
2. Select **Slot Availability** (`slot_decision`).
3. Click on the decision instance corresponding to Case 1 (`bookedCount = 3`) or Case 2 (`bookedCount = 12`).
4. **Capture**: The decision table view showing:
   * Inputs evaluated (`"Cardiology"`, `3` or `12`).
   * Rule 1 or Rule 2 highlighted in green with outputs `slotStatus` and `suggestedAction`.
