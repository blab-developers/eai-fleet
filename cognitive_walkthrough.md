# Cognitive Walkthrough: Set Inference Image Deployment (Use Case 3)

- **Repository**: [eai-fleet](file:///c:/Users/bidwe/workspace/repos/eai-fleet)
- **User Persona**: Fleet Operator deploying a validated YOLOv12 model container across the Jetson fleet.
- **Task Goal**: Update the container image of the active inference workload on device `jetson-00` to `registry.endoscopeai.com/eai-nano/inference:v0.4.2` and verify the patch is applied.

---

## Step-by-Step Walkthrough

### Step 1: Open the Target Device Section
The user starts on the Fleet dashboard and must locate the target device (`jetson-00`) to access its deployment controls.

*   **Action**: Click the accordion header or details button for `jetson-00`.
*   **Cognitive Evaluation**:
    1.  *Will the user know what to do?* Yes. The device list is presented as an accordion, a standard pattern for exposing per-device detail views.
    2.  *Will the user see the control?* Yes. The accordion title `jetson-00` is prominently styled in standard Carbon typography.
    3.  *Will the user understand the feedback?* Yes. Clicking expands the accordion item downward, revealing a nested form titled "Set inference image".
    4.  *Error Recovery*: If the user expands the wrong device, they can click to collapse it or click another device header.
*   **Playwright Cross-Reference**:
    *   *Test*: [set-image.spec.ts: L9](file:///c:/Users/bidwe/workspace/repos/eai-fleet/apps/frontend/tests/e2e/set-image.spec.ts#L9): `await page.getByTestId('device-title-jetson-00').click();`
    *   *Asserts*: [set-image.spec.ts: L10](file:///c:/Users/bidwe/workspace/repos/eai-fleet/apps/frontend/tests/e2e/set-image.spec.ts#L10): Locating `device-body-jetson-00`.

---

### Step 2: Input the New Container Image Reference
The user must type or paste the valid image reference into the "Container image" input box.

*   **Action**: Focus the "Container image" text field and input `registry.endoscopeai.com/eai-nano/inference:v0.4.2`.
*   **Cognitive Evaluation**:
    1.  *Will the user know what to do?* Yes. The input label "Container image" and the placeholder showing a sample reference guide the operator.
    2.  *Will the user see the control?* Yes. The TextInput field is visible inside the expanded accordion.
    3.  *Will the user understand the feedback?* Yes. Standard browser text insertion handles the typing. If the format is invalid (e.g. spaces, missing tags), the input border turns red and displays the warning: *"Enter a valid container image reference"*.
    4.  *Error Recovery*: The operator can backspace/delete to correct the string format until the validation message disappears.
*   **Playwright Cross-Reference**:
    *   *Test*: [set-image.spec.ts: L21-23](file:///c:/Users/bidwe/workspace/repos/eai-fleet/apps/frontend/tests/e2e/set-image.spec.ts#L21-L23): Verifies the "Apply" button is disabled until the input is filled with a valid image tag.

---

### Step 3: Submit the Form and Monitor Execution
The user applies the changes to initiate the DaemonSet patch on the backend.

*   **Action**: Click the "Apply" button.
*   **Cognitive Evaluation**:
    1.  *Will the user know what to do?* Yes. The "Apply" button is adjacent to the input field, presenting a clear primary action.
    2.  *Will the user see the control?* Yes. The button is styled in high-contrast blue/black per Carbon's standard primary button theme.
    3.  *Will the user understand the feedback?* Yes. During submission, the button is disabled, preventing double-clicks. Once finished, a success notification appears stating *"Image set"*, displaying the scope (e.g., *"fleet-wide"*) and note returned by the API. The input text is cleared.
    4.  *Error Recovery*: If the backend returns an error (e.g. k8s API unreachable, 502 Bad Gateway), the form remains populated, and a red `InlineNotification` is appended below the form detailing the exact error message.
*   **Playwright Cross-Reference**:
    *   *Success Test*: [set-image.spec.ts: L26-44](file:///c:/Users/bidwe/workspace/repos/eai-fleet/apps/frontend/tests/e2e/set-image.spec.ts#L26-L44) verifies success notification, scope note, and input clearance.
    *   *Error (404) Test*: [set-image.spec.ts: L46-56](file:///c:/Users/bidwe/workspace/repos/eai-fleet/apps/frontend/tests/e2e/set-image.spec.ts#L46-L56) verifies failure banner when a device ID is missing.
    *   *Error (502) Test*: [set-image.spec.ts: L58-68](file:///c:/Users/bidwe/workspace/repos/eai-fleet/apps/frontend/tests/e2e/set-image.spec.ts#L58-L68) verifies failure banner when a Kubernetes API service is down.

---

## Usability Observations & Verification Strengths

1.  **Aesthetics and Carbon Precedence**: The UI employs high-quality typography, clear label hierarchies, and standard semantic alert colors (green for success, red for error), fitting the premium aesthetics requirement.
2.  **Clear Validation Feedback**: Input validation happens client-side using `IMAGE_TAG_PATTERN` (defined in `models.ts`), disabling the button instantly before a network hop is wasted.
3.  **Complete Error Boundaries**: The form wraps async API errors and handles them gracefully using the `getErrorMessage` utility rather than swallowing exceptions.
