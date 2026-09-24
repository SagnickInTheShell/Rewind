# REWIND — 3-Minute Live Presentation Demo Script

This script guides the live walkthrough of the **REWIND** system during a hackathon or jury evaluation.

---

### [0:00 – 0:20] Introduction & Ingest
- **Action**: Open the REWIND dashboard at `http://localhost:5175/` (or click **"Demo"** in the top navigation).
- **Spoken**:
  > *"When crowd incidents occur, post-event reports take months to compile, and we rarely answer the most important question: could simple operational interventions have changed the outcome?
  >
  > Welcome to REWIND. REWIND turns CCTV footage and a venue floor plan into an interactive digital twin that reconstructs what happened, explains why it escalated, and simulates what could have happened differently."*

---

### [0:20 – 0:50] The Scene & Perception Overlay
- **Action**: Look at the main CCTV Concourse view. Scrub playhead to `12:34` then `12:38`.
- **Spoken**:
  > *"Here is the footage from CCTV_Stadium_01. In sparse areas near Gate C, our hybrid perception engine tracks individual trajectories with ByteTrack. But as crowd density builds above 1.5 people per square metre near Gate B, REWIND seamlessly transitions to continuous density estimation and Farneback optical flow.
  >
  > Notice the dynamic heatmap overlay across the concourse floor: blue and green in normal flow, transitioning into a severe red congestion zone at Gate B."*

---

### [0:50 – 1:15] Incident Reconstruction & Explanation
- **Action**: Point to the **Incident Timeline** and click milestone `12:38` (Flow becomes unstable). Show the **Incident Summary** and **Key Factors** on the right.
- **Spoken**:
  > *"Our causal chain reconstructs the exact sequence of events. At 12:31, initial entry surge occurred. At 12:36, a bottleneck developed at Gate B as outflow was choked. By 12:38, turbulent flow instability surged to 72% with crowd pressure reaching critical levels.
  >
  > REWIND doesn't use black-box guesses. Under Key Factors, we see the exact physical drivers: high density at 92%, bottleneck pressure at 78%, and opposing movement at 65%."*

---

### [1:15 – 1:45] The "REWIND" Moment
- **Action**: Click the **"Rewind"** tab in the sidebar (or navigate to `/rewind`). Click the big animated **"REWIND TO t₀"** button. The scrubber smoothly animates backwards to `12:35` (prior to the bottleneck).
- **Spoken**:
  > *"Now for the core innovation: REWIND. What if the control room had acted earlier?
  >
  > We press REWIND to jump back to 12:35—before the turbulence became critical. In our Intervention Builder, we can test alternative policies: what if we opened Gate C, which was closed during the event?"*

---

### [1:45 – 2:20] Digital Twin Side-by-Side Simulation
- **Action**: Select `Open Gate C at 12:35` and press **"Run Simulation"**. In the **TwinDualView**, press Play to watch the side-by-side twin replay.
- **Spoken**:
  > *"On the left, we see the Baseline replay—what actually happened, leading to critical density and a 25-second red state.
  >
  > On the right, the digital twin simulates opening Gate C. The crowd redistributes into the side corridor. Modelled peak density plummets from 3.47 to 0.91 people per square metre, and the risk state remains completely LOW throughout."*

---

### [2:20 – 2:40] Scenario Comparison & Prevention Plan
- **Action**: Scroll to the **Scenario Comparison Table** and **Prevention Plan Card**.
- **Spoken**:
  > *"Our engine evaluates multiple interventions across seeds. In the comparison table, Opening Gate C plus restricting entry achieves the best outcome. 
  >
  > The automated Prevention Plan ranks recommendations with quantified deltas: 42% of crowd flow diverted, bottleneck pressure relieved in under 45 seconds."*

---

### [2:40 – 3:00] Out-of-Sample Validation & Closing
- **Action**: Point to the **Validation Card** ("Do-Nothing Replay vs Real Footage", Verdict: GOOD).
- **Spoken**:
  > *"To ensure trust, our simulator is calibrated on the first half of footage and validated against the unseen second half. With an overall density RMSE of 0.127 and 92% risk state agreement, the verdict is GOOD.
  >
  > REWIND doesn't just analyze the past. It gives event organizers the foresight to simulate the alternative and keep crowds safe. Thank you."*
