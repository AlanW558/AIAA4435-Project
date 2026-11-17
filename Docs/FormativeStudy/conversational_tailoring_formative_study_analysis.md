# Formative Study Analysis: Conversational Tailoring of an AI Agent

**Project:** AIAA 4435 Week 2 — Formative Study  
**Topic:** Conversational tailoring of embodied / conversational AI agents  
**Date of analysis:** 2026-09-15  
**Current valid sample:** **N = 22**

## 1. Purpose of this document

This document consolidates:

1. the current questionnaire results;
2. quality control and limitations of the collected data;
3. a cautious interpretation of the three research questions (RQs);
4. qualitative evidence from the open-ended questions;
5. triangulation with recent peer-reviewed HCI / conversational-agent / VR literature; and
6. a refined research direction suggested jointly by the survey and prior work.

The analysis is intended for a **formative study**, not a population-level survey or a confirmatory experiment. The goal is therefore to identify recurring pain points and promising design opportunities rather than to claim that the observed proportions generalize to all users.

---

# 2. Data sources and provenance

Local source files used in this analysis:

- `AdjustinganAIThroughConversation-默认报告.xlsx` — aggregated responses for Q1–Q12.
- `详细信息--第2题答案.xlsx` — raw free-text responses for Q2.
- `详细信息--第12题答案.xlsx` — raw free-text responses for Q12.
- `Immersive_Tailoring_of_Embodied_Agents_Using_Large_Language_Models.pdf` — assigned paper.
- `conversational_tailoring_questionnaire_revised.md` — questionnaire design.

## 2.1 Important note on timestamps

Some questionnaires were completed on printed paper and later entered into the online form in a batch. Therefore, the online submission timestamps do **not** represent participants' actual completion times and should **not** be used to infer response duration, fatigue, or temporal patterns.

## 2.2 Skip logic

Q1 asked whether participants had previously asked an AI to alter its future responses (e.g., tone, length, role).

- 18/22 had relevant prior experience.
- Participants answering "No" or "Not sure" were instructed to skip Q2–Q3.
- Consequently, Q3 has **n = 18**, whereas Q4–Q12 have **n = 22**.

---

# 3. High-level conclusion

The present dataset is sufficient for a **preliminary formative-study story**, but not for strong population-level claims.

The three original problem areas are supported to different degrees:

| Research area | Evidence from current survey | External literature | Overall assessment |
|---|---|---|---|
| **RQ1 — expressing / grounding user intent** | 14/18 experienced at least one request difficulty; 10/18 specifically struggled to describe the desired change; 15/22 preferred clarification when a request was ambiguous | Strong support from CHI 2023, DIS 2024, CHI 2024, CUI 2025 | **Moderate–Strong**, but wording should be refined |
| **RQ2 — latency and conversational continuity** | 16/22 reported a silent-wait tolerance below 5 s; 15/22 said losing an agreed preference would interrupt them very much or extremely | Strong support from the assigned IEEE VR paper and CUI 2025 controlled VR study | **Strong** |
| **RQ3 — execution mismatch, verification, and repair** | 19/22 preferred observable evidence rather than the AI's own confirmation; 16/22 wanted preview/approval before an approximation; 15/22 preferred local correction after an unintended side effect | Strong support from CHI 2025, UIST 2024, and CSCW 2023 | **Strongest** |

The most important cross-RQ pattern is that participants repeatedly preferred **lightweight inspection and control mechanisms** rather than a purely opaque conversational pipeline.

A more promising research direction is therefore:

> **Inspectable mixed-initiative conversational tailoring:** retain natural-language interaction as the primary input, but add lightweight mechanisms for clarification, progress feedback, preview, state visibility, and local repair.

---

# 4. Sample characteristics relevant to interpretation

## Q1. Previous use

| Previous experience | Count | Percentage |
|---|---:|---:|
| Typed messages only | 13 | 59.09% |
| Spoken requests only | 1 | 4.55% |
| Both typed and spoken | 4 | 18.18% |
| No | 3 | 13.64% |
| Not sure | 1 | 4.55% |
| **Total** | **22** | **100%** |

Thus:

- **18/22 = 81.8%** had previously used conversational tailoring in some form.
- However, only **5/22 = 22.7%** reported any spoken-request experience.

### Interpretation

The sample has strong relevance to **conversational AI customization in general**, but much weaker direct experience with **spoken VR tailoring**. Q4–Q12 were explicitly hypothetical, so they should be described as **stated preferences under scenarios**, not observed VR behavior.

This distinction should remain visible in the presentation.

---

# 5. Quantitative findings

Because the sample is small and convenience-based, the main analysis should use **counts and percentages**. Selected Wilson 95% confidence intervals are provided only to communicate uncertainty; they should not be treated as proof of population-level prevalence.

---

# 6. RQ1 — Intention expression and interpretation

## 6.1 Q3. Difficulties making the request

Among participants with prior relevant experience (**n = 18**):

| Difficulty | Count | Percentage |
|---|---:|---:|
| Describing the change in words | 10 | 55.56% |
| Knowing what the AI could change | 5 | 27.78% |
| Explaining the relevant context | 4 | 22.22% |
| Deciding what change I wanted | 2 | 11.11% |
| Nothing was difficult | 3 | 16.67% |
| Cannot recall | 1 | 5.56% |

Because participants could choose up to two items, percentages do not sum to 100%.

A useful aggregate is:

- **14/18 = 77.8%** reported at least one difficulty  
  Wilson 95% CI: approximately **54.8%–91.0%**.
- **10/18 = 55.6%** specifically reported difficulty **describing the desired change in words**  
  Wilson 95% CI: approximately **33.7%–75.4%**.

## 6.2 What this supports — and what it does not

The current data do **not** strongly support the claim:

> "Users often do not know what they want."

Only 2/18 selected "Deciding what change I wanted."

The data support a more precise statement:

> **Users may know the desired outcome but still struggle to translate that intention into a natural-language request that reliably produces the intended system behavior.**

This distinction is important. The design problem is less about users lacking goals and more about the **mapping from human intention to language to system interpretation**.

## 6.3 Q4. What users want to check before execution

For Q4 (**n = 22**), five participants preferred no check beforehand and one was unsure. Therefore:

- **16/22 = 72.7%** selected at least one piece of information they would want to check before execution  
  Wilson 95% CI: approximately **51.8%–86.8%**.

Most-selected items:

- What it plans to change: 8/22 = 36.36%
- How much it plans to change: 8/22 = 36.36%
- What it thinks I am trying to achieve: 6/22 = 27.27%
- What will stay unchanged: 4/22 = 18.18%

No single checking mechanism dominates. The underlying signal is stronger than any one item:

> Many participants want some visibility into the interpretation, but they disagree on what exactly should be surfaced.

## 6.4 Q5. Handling an ambiguous request

Scenario: "Make your feedback gentler" could mean softer wording or fewer corrections.

| Preferred first action | Count | Percentage |
|---|---:|---:|
| Offer two interpretations and let me choose | 8 | 36.36% |
| Ask an open clarification question | 7 | 31.82% |
| Try one interpretation and explain what changed | 5 | 22.73% |
| Keep current settings and explain why | 1 | 4.55% |
| Not sure | 1 | 4.55% |

Therefore:

- **15/22 = 68.2%** preferred **clarification before execution**  
  Wilson 95% CI: approximately **47.3%–83.6%**.

However, 5/22 preferred "try first, then explain." Therefore the finding is not:

> "Users always want confirmation."

A better interpretation is:

> **Users generally prefer ambiguity to be surfaced rather than silently resolved, but the preferred timing of intervention varies: some prefer pre-execution clarification, while others prefer fast execution followed by inspectable feedback.**

This tension between **accuracy/control** and **interaction cost** is a useful design problem in itself.

---

# 7. RQ1 triangulation with prior work

### [R2] Why Johnny Can't Prompt — CHI 2023

Zamfirescu-Pereira et al. studied non-AI experts using a prompt-design probe. Participants explored prompts opportunistically rather than systematically and encountered difficulties in prompt design and debugging. The work also showed that expectations transferred from human-to-human instruction could become barriers to effective prompting.

**Relation to our data:**  
This independently supports Q3's indication that converting an intention into an effective natural-language instruction is not trivial, even when natural language appears intuitive.

### [R3] How People Prompt Generative AI to Create Interactive VR Scenes — DIS 2024

A Wizard-of-Oz elicitation study with **22 participants** examined verbal prompting while users were embodied inside VR scenes. The study showed that prompts naturally depend on spatial, embodied, and contextual references.

**Relation to our data:**  
This supports the view that a spoken request can be underspecified linguistically while still being natural to the user because the user expects the system to share environmental and conversational context.

### [R4] How Beginning Programmers and Code LLMs (Mis)read Each Other — CHI 2024

A controlled study with **120 beginning programmers** found difficulties at multiple stages: describing intent, evaluating generated results, and modifying prompts after incorrect outputs, even when task difficulty was appropriate and correctness feedback was available.

**Relation to our data:**  
The domain is programming rather than VR, so the numeric results should not be pooled with ours. Mechanistically, however, it supports the broader existence of an **intention-expression-evaluation-repair gap** in LLM interaction.

### [R6] Transparent Conversational Agents — CUI 2025

A speech-based study with **56 participants** compared an agent that communicated its capabilities with one that did not. Capability communication changed user behavior (including longer utterances), but did **not** significantly improve mental-model alignment between conditions.

**Relation to our data:**  
This is an important counterpoint. Q3 shows that some users struggle to know what the AI can change, but simply displaying capabilities is unlikely to be a complete solution. Capability support should probably be combined with interaction, feedback, and iterative grounding.

---

# 8. RQ2 — Latency and conversational continuity

## 8.1 Q6. Silent waiting tolerance

Scenario: the tutor changes speaking speed and gives no progress signal.

| Longest acceptable silent wait | Count | Percentage |
|---|---:|---:|
| <1 s | 2 | 9.09% |
| 1–<3 s | 6 | 27.27% |
| 3–<5 s | 8 | 36.36% |
| 5–<8 s | 4 | 18.18% |
| ≥8 s | 1 | 4.55% |
| Not sure | 1 | 4.55% |

Key result:

- **16/22 = 72.7%** reported an acceptable silent wait of **less than 5 seconds**  
  Wilson 95% CI: approximately **51.8%–86.8%**.

This is a self-reported threshold under a hypothetical scenario, not a measured behavioral threshold.

## 8.2 Comparison with the assigned paper

The assigned IEEE VR paper reports:

- average tailoring latency: **7.3 s** (SD = 0.38);
- average non-tailoring latency: **5.2 s** (SD = 0.43);
- latency complaints during the participatory exploration, with delays described as disrupting immersion and conversational flow.

This creates a useful descriptive contrast:

> **Our survey:** 72.7% reported a silent-wait tolerance below 5 s.  
> **Original prototype:** mean tailoring latency was 7.3 s.

This should be presented as **converging evidence**, not as a direct experimental comparison, because the original study measured system latency while our survey measured hypothetical self-reported tolerance.

## 8.3 Q7. Feedback during a 5-second wait

| Preferred feedback | Count | Percentage |
|---|---:|---:|
| Small visual indicator | 9 | 40.91% |
| Spoken processing cue | 3 | 13.64% |
| Both spoken + visual | 4 | 18.18% |
| No cue | 4 | 18.18% |
| No preference | 1 | 4.55% |
| Not sure | 1 | 4.55% |

Aggregates:

- **16/22 = 72.7%** preferred some explicit feedback rather than silence.
- **13/22 = 59.1%** selected an option containing a visual cue.

The modality result should be interpreted cautiously because participants did not actually experience the alternatives.

## 8.4 Q8. Maintaining an agreed preference

Scenario: the tutor agrees to use shorter replies for the rest of the session but reverts after several turns.

| Disruption | Count | Percentage |
|---|---:|---:|
| Not at all | 0 | 0% |
| Slightly | 2 | 9.09% |
| Moderately | 4 | 18.18% |
| Very much | 10 | 45.45% |
| Extremely | 5 | 22.73% |
| Not sure | 1 | 4.55% |

Aggregates:

- **15/22 = 68.2%**: Very much or Extremely  
  Wilson 95% CI: approximately **47.3%–83.6%**.
- **19/22 = 86.4%**: at least Moderate disruption  
  Wilson 95% CI: approximately **66.7%–95.3%**.

This is one of the clearest results in the questionnaire.

### Supported claim

> **Within-session loss of an explicitly agreed tailoring preference is likely to be experienced as a substantial continuity breakdown.**

Do not generalize this finding to long-term memory across days or sessions; Q8 only tests persistence within one session.

---

# 9. RQ2 triangulation with prior work

### [R1] Assigned IEEE VR 2025 paper

The assigned paper directly identifies latency and richer contextual functionality as unresolved challenges. Its measured mean tailoring latency was 7.3 s, and its participants reported that delay reduced naturalness and immersion.

### [R5] Mitigating Response Delays in Free-Form Conversations with LLM-powered Intelligent Virtual Agents — CUI 2025

This controlled VR conversational-agent study exposed **54 participants** to different latency conditions (including 1.5 s, 4.0 s, and 6.5 s). The authors report that **latency above 4 seconds degraded quality of experience** and that natural conversational fillers could improve perceived response time, especially under higher latency.

**Relation to our Q6:**  
Our 72.7% self-reported <5 s tolerance is directionally consistent with a controlled study finding degradation beyond roughly 4 s.

**Relation to Q7:**  
Our participants most often selected a visual processing indicator, but the controlled CUI study found benefits from natural conversational fillers. This mismatch is useful rather than problematic:

> **Stated preferences about waiting feedback may differ from experienced effectiveness.**

Therefore, "add a loading indicator" should not be treated as a validated design conclusion. The better research question is which feedback strategy reduces perceived disruption without adding conversational clutter.

---

# 10. RQ3 — Execution mismatch, verification, and repair

This section contains the strongest and most coherent pattern in the current survey.

## 10.1 Q9. How users judge whether tailoring worked

| Preferred evidence | Count | Percentage |
|---|---:|---:|
| Try over several conversational turns | 6 | 27.27% |
| Before/after comparison | 5 | 22.73% |
| Hear a short example | 4 | 18.18% |
| See changed settings | 4 | 18.18% |
| Trust tutor confirmation | 2 | 9.09% |
| Not sure | 1 | 4.55% |

A useful aggregate:

- **19/22 = 86.4%** selected some form of **observable evidence** rather than the tutor's own declaration that the change was complete  
  Wilson 95% CI: approximately **66.7%–95.3%**.

### Interpretation

> **Users do not appear to treat the AI's statement "the change is complete" as sufficient evidence that tailoring actually succeeded.**

This directly motivates **preview, state visibility, or behavioral verification**.

## 10.2 Q10. Exact option unavailable

Scenario: requested voice unavailable; a similar voice exists.

| Preferred response | Count | Percentage |
|---|---:|---:|
| Play a sample and let me decide | 10 | 45.45% |
| Describe the difference and ask | 6 | 27.27% |
| Apply similar voice and explain | 4 | 18.18% |
| Keep current voice and explain limitation | 1 | 4.55% |
| Not sure | 1 | 4.55% |

Aggregate:

- **16/22 = 72.7%** preferred **preview or explicit approval before adopting the approximation**  
  Wilson 95% CI: approximately **51.8%–86.8%**.

### Interpretation

The data do not imply that users demand exact execution or failure. A more useful insight is:

> **Approximate solutions may be acceptable when the mismatch is visible and the user retains the decision to accept or reject the substitute.**

## 10.3 Q11. Unwanted side effect

Scenario: user asks for slower speech without changing the voice; system slows speech but also changes voice.

| Preferred repair | Count | Percentage |
|---|---:|---:|
| Tell it to restore only the previous voice | 8 | 36.36% |
| Use a voice selector to restore it manually | 7 | 31.82% |
| Undo the whole change and start again | 3 | 13.64% |
| Keep result | 1 | 4.55% |
| Stop trying | 1 | 4.55% |
| Not sure | 2 | 9.09% |

Aggregate:

- **15/22 = 68.2%** preferred **local correction** while retaining the successfully changed component  
  Wilson 95% CI: approximately **47.3%–83.6%**.

This is one of the most design-relevant findings.

### Interpretation

The result is stronger than "users want undo."

> **Users want selective repair: preserve the correct part of a tailoring operation and repair only the mismatched attribute.**

Also important: conversational repair (8 participants) and direct manual control (7 participants) are nearly tied.

This suggests that the best tailoring interface may **not be purely conversational**.

---

# 11. RQ3 triangulation with prior work

### [R7] Prompting an Embodied AI Agent — CHI 2025

This work designed a VR agent that used embodied and visual signals (e.g., head direction and highlighting) to communicate its understanding of situated prompts. The study reported that such signals allowed users to **prevent errors in 30% of relevant cases** and increased satisfaction and confidence.

**Relation to our data:**  
This directly supports Q4/Q9's underlying design principle: make the system's interpretation perceptible before or during execution rather than leaving the user to infer it from a final result.

### [R8] VRCopilot — UIST 2024

VRCopilot compared manual, scaffolded, and automatic generative-AI-assisted VR authoring. In its second study (**n = 15**), scaffolded creation using intermediate wireframe representations produced greater user agency than fully automatic creation; manual multimodal creation produced the highest agency and creativity.

**Relation to our data:**  
Q10/Q11 similarly suggest that users value intermediate inspectability and the ability to intervene rather than maximizing automation.

### [R9] To Err is AI — CSCW 2023

An online study with **175 participants** examined conversational-agent errors and a repair strategy that allowed users to contest incorrect agent interventions. Repair moderated some negative effects of errors, including improving perceived discussion experience under false-positive interventions.

**Relation to our data:**  
The task context differs substantially from tailoring in VR, so this is mechanistic rather than direct evidence. It nevertheless supports a general HCI principle:

> When AI errors are expected, **repairability is part of the interaction design**, not merely a backend reliability issue.

---

# 12. Open-ended responses

## 12.1 Q2 response quality

Q2 received **12 free-text responses**.

A manual relevance audit found:

- **9 responses usable for interpretation**;
- **3 responses clearly off-topic / joke responses**, excluded from thematic synthesis but retained in the raw data;
- among the 9 usable responses, **7 explicitly described a problem or mismatch**, while 2 primarily described a tailoring request without enough outcome detail to classify success/failure.

Because this coding was performed by one analyst and the sample is small, these should be treated as **illustrative themes**, not formally saturated qualitative findings.

## 12.2 Themes visible in usable Q2 responses

### Theme A — difficulty expressing a desired style

Example:

> "我想让它说得专业一点，但改了几次措辞还是不像我要的语气。"

Another:

> "I asked it to sound more casual, but I had to give an example before it got it."

This supports the RQ1 interpretation that the problem is often not absence of a goal, but difficulty translating a subjective target into a machine-actionable instruction.

### Theme B — preference/context not maintained

Example:

> "I asked for shorter replies, but they got long again after a few turns."

This closely matches the Q8 scenario and supports the importance of within-session persistence.

### Theme C — over-execution / unintended side effects

Example:

> "我说只解释代码里的错误，它却把整段代码重写了。"

This is especially valuable for RQ3 because it captures a common failure structure:

- one part of the user's request is understood;
- the system additionally changes something the user did not ask to change.

This motivates selective repair rather than complete restart.

### Theme D — latency

Example:

> "我让语音助手说慢一点，等了好久它才继续。"

This is the only directly voice-related open response and is consistent with Q6, but one anecdote cannot establish prevalence.

### Theme E — agent claims success but observable behavior does not match

Example:

> "I asked for a different accent, but it said done and sounded almost the same."

This is highly aligned with Q9. It illustrates why a system's self-confirmation should not be treated as sufficient evidence of successful tailoring.

## 12.3 Q12

Only **3 participants** answered Q12, so no frequency-based thematic claims should be made.

The three responses nevertheless reinforce three design concerns:

1. content quality remains important;
2. do not modify properties the user did not request;
3. let users hear the change and undo only the part they dislike.

Useful quote:

> "Let me hear the change and undo just the part I dislike."

This is best used as an **illustrative quote** beside the Q9–Q11 quantitative results.

---

# 13. Evidence synthesis by RQ

## RQ1 — from "true intention decoding" to conversational grounding

### Original assumption
Users' natural language may not clearly reflect their needs, and the LLM may fail to decode their real intention.

### Refined finding
The data support a narrower and more defensible formulation:

> **Users often have a target in mind but can struggle to express it in language that reliably maps to the system's capabilities and interpretation. Ambiguity should be surfaced and grounded rather than silently resolved.**

### Why this refinement matters
"True intention" is difficult to observe directly. A user may also change their mind after seeing results. The research problem is therefore better framed around **grounding, interpretation visibility, and iterative clarification** rather than mind-reading.

---

## RQ2 — from "latency is annoying" to temporal continuity

### Refined finding

> **Conversational tailoring needs temporal continuity at two levels:**
>
> 1. responsiveness — long silent processing breaks conversational flow;
> 2. state continuity — previously agreed tailoring settings should remain active for their intended scope.

This is more complete than treating latency and memory as independent engineering problems.

---

## RQ3 — from "accurate matching" to inspectable approximation and selective repair

### Original assumption
Even if the LLM understands the user's need, it may not accurately match the appropriate solution.

### Refined finding

> **Perfect matching is not the only acceptable outcome. Users appear willing to work with approximate or imperfect results when the system exposes the mismatch, lets them inspect the actual result, and supports local correction.**

This is a stronger HCI contribution than simply demanding a more accurate LLM.

---

# 14. Cross-RQ design insight

Across Q4, Q5, Q7, Q9, Q10, and Q11, participants repeatedly favored mechanisms that expose the internal interaction state:

- clarification of ambiguity;
- processing feedback;
- preview/sample;
- before/after or settings visibility;
- explicit disclosure of approximation;
- local repair;
- direct selectors as an alternative to conversational repair.

This suggests a common interaction model:

## **Speak → Ground → Process → Preview → Apply → Verify → Locally Repair**

The original architecture is roughly:

> **Speech → LLM pipeline → tailored result**

The new HCI opportunity is not necessarily to replace the LLM architecture, but to add an **interaction layer around the uncertain transitions**.

---

# 15. Proposed research direction

## Inspectable Mixed-Initiative Conversational Tailoring

### Core idea

Use natural language as the primary input but introduce lightweight non-conversational and multimodal support only when uncertainty or mismatch matters.

Possible components:

1. **Capability cues**
   - show available dimensions or examples when users appear unsure;
   - avoid a permanently cluttered menu.

2. **Ambiguity grounding**
   - when two interpretations are plausible, show/voice compact alternatives;
   - ask only when uncertainty is consequential.

3. **Progress signaling**
   - give low-disruption feedback during long processing;
   - compare visual cues with natural conversational fillers rather than assuming one is best.

4. **Preview before commitment**
   - short voice sample, behavior preview, or proposed setting summary.

5. **Persistent tailoring state**
   - lightweight representation of currently active role/style/voice/etc.;
   - scope information such as "this turn," "this session," or persistent preference.

6. **Local repair**
   - conversational command ("restore only the voice");
   - direct control for the affected attribute;
   - preserve correctly changed properties.

### Research question suggested by the combined evidence

> **How can a mixed-initiative interaction layer help users ground, inspect, and locally repair conversational tailoring while preserving conversational flow?**

A more focused version for a prototype study:

> **When should a conversational tailoring system interrupt users with clarification or visual controls, and when should it execute immediately and support post-hoc repair?**

This preserves the interesting trade-off revealed by Q5 and Q11 instead of assuming that more confirmation is always better.

---

# 16. Statistical interpretation and sample-size limitation

## 16.1 Why N = 22 is not fatal for this assignment

This study is explicitly **formative**. It is being used to identify pain points and guide a possible research direction, not to estimate precise population prevalence or establish a causal treatment effect.

The assigned paper itself used an intensive six-week participatory exploration with **five graduate students**, demonstrating that formative HCI evidence can be valuable with small samples when claims are appropriately scoped.

The correct response to N = 22 is **not** to inflate the claims or pool unrelated external samples. Instead:

1. report counts together with percentages;
2. identify the hypothetical versus experience-based questions;
3. avoid population language such as "users generally";
4. use literature for **triangulation**, not as additional participants;
5. emphasize convergence of mechanisms across independent studies.

## 16.2 Why not run significance tests

The present sample is:

- small;
- convenience-based;
- partly hypothetical;
- not designed around a preregistered null hypothesis or experimental manipulation.

P-values would create more apparent precision than the design justifies. Descriptive statistics plus uncertainty intervals are more defensible.

## 16.3 Selected Wilson intervals

| Finding | Estimate | Approx. Wilson 95% CI |
|---|---:|---:|
| Prior conversational-tailoring experience | 18/22 = 81.8% | 61.5–92.7% |
| Any difficulty among experienced participants | 14/18 = 77.8% | 54.8–91.0% |
| Difficulty describing desired change | 10/18 = 55.6% | 33.7–75.4% |
| Prefer clarification for ambiguity | 15/22 = 68.2% | 47.3–83.6% |
| Silent wait tolerance <5 s | 16/22 = 72.7% | 51.8–86.8% |
| Very/extreme disruption from lost preference | 15/22 = 68.2% | 47.3–83.6% |
| Observable evidence over AI confirmation | 19/22 = 86.4% | 66.7–95.3% |
| Preview/approval before approximation | 16/22 = 72.7% | 51.8–86.8% |
| Prefer local correction | 15/22 = 68.2% | 47.3–83.6% |

The intervals are wide, which is exactly why the study should be described as directional evidence.

---

# 17. What the current study can and cannot claim

## Defensible claims

- Most respondents had some prior experience asking AI systems to change future responses.
- Among experienced respondents, describing the desired change in words was the most frequently selected request difficulty.
- In the ambiguity scenario, clarification was preferred by a majority of the sample.
- A majority reported a silent-wait tolerance below five seconds in the presented scenario.
- Losing an explicitly agreed within-session preference was rated as substantially disruptive by most respondents.
- Most respondents wanted observable evidence to judge whether tailoring succeeded.
- Most respondents wanted preview/approval before accepting a substitute when an exact option was unavailable.
- Most respondents preferred local correction over restarting the entire tailoring operation.

## Claims to avoid

- "Users cannot express what they want."
- "Five seconds is the universal maximum acceptable latency."
- "A visual loading indicator is proven to improve immersion."
- "Our participants prove that the original system is inaccurate."
- "Users prefer multimodal interfaces in general."
- "Local repair improves performance/satisfaction."  
  The survey only shows preference; effectiveness still requires an implemented comparison.
- "These percentages generalize to VR users."  
  Most of the sample had no spoken/VR tailoring experience.

---

# 18. Presentation-ready evidence chain

A strong presentation should not show all twelve questions. The clearest chain is:

### Finding 1 — Expressing intent is non-trivial
- **14/18** experienced participants reported at least one difficulty.
- **10/18 (55.6%)** selected "describing the change in words."
- External support: CHI 2023, DIS 2024, CHI 2024.
- Refined problem: **grounding**, not "mind-reading."

### Finding 2 — Long silent waiting and lost state break flow
- **16/22 (72.7%)** reported silent-wait tolerance <5 s.
- Original system: **7.3 s mean tailoring latency**.
- Controlled CUI 2025 VR study: latency >4 s degraded experience.
- **15/22 (68.2%)** rated loss of an agreed preference as very/extremely disruptive.

### Finding 3 — Users want evidence and repair, not just an AI saying "done"
- **19/22 (86.4%)** chose observable evidence rather than agent confirmation.
- **16/22 (72.7%)** wanted preview/approval before a substitute.
- **15/22 (68.2%)** preferred local repair after an unintended side effect.
- External support: CHI 2025 multimodal grounding, UIST 2024 scaffolded control, CSCW 2023 conversational repair.

### Resulting direction
> **Inspectable mixed-initiative tailoring:** conversational input + clarification + progress feedback + preview + persistent state + local repair.

---

# 19. References

## R1 — Assigned paper

Bellucci, A., Jacucci, G., Trung, K. D., Das, P. K., Smirnov, S. V., Ahmed, I., & Lugrin, J.-L. (2025). **Immersive Tailoring of Embodied Agents Using Large Language Models.** *2025 IEEE Conference Virtual Reality and 3D User Interfaces (VR)*.  
DOI: https://doi.org/10.1109/VR59515.2025.00063

**Used for:** system architecture, 7.3 s / 5.2 s measured latency, five-participant participatory exploration, prompt/reliability/context findings.

---

## R2 — Prompt-design difficulty

Zamfirescu-Pereira, J. D., Wong, R. Y., Hartmann, B., & Yang, Q. (2023). **Why Johnny Can't Prompt: How Non-AI Experts Try (and Fail) to Design LLM Prompts.** *Proceedings of the 2023 CHI Conference on Human Factors in Computing Systems (CHI '23)*, Article 437, 1–21.  
DOI: https://doi.org/10.1145/3544548.3581388  
Open PDF: https://people.eecs.berkeley.edu/~bjoern/papers/zamfirescu-johnny-chi2023.pdf

**Used for:** difficulties in end-user prompt design, opportunistic iteration, and mismatched human mental models of LLM instruction-following.

---

## R3 — Situated / embodied prompting in VR

Aghel Manesh, S., Zhang, T., Onishi, Y., Hara, K., Bateman, S., Li, J., & Tang, A. (2024). **How People Prompt Generative AI to Create Interactive VR Scenes.** *Proceedings of the 2024 ACM Designing Interactive Systems Conference (DIS '24)*, 2319–2340.  
DOI: https://doi.org/10.1145/3643834.3661547  
Author page: https://kotarohara.com/publications/how-people-prompt-to-create-interactive-vr-scenes

**Study:** Wizard-of-Oz elicitation study, **N = 22**.

**Used for:** verbal prompts in VR depending on embodied, spatial, and contextual information rather than fully explicit language.

---

## R4 — Intent description and repair with LLMs

Nguyen, S., Babe, H. M., Zi, Y., Guha, A., Anderson, C. J., & Feldman, M. Q. (2024). **How Beginning Programmers and Code LLMs (Mis)read Each Other.** *Proceedings of the 2024 CHI Conference on Human Factors in Computing Systems (CHI '24)*, Article 651, 1–26.  
DOI: https://doi.org/10.1145/3613904.3642706  
arXiv: https://arxiv.org/abs/2401.15232

**Study:** controlled study with **N = 120**.

**Used for:** independent evidence that users can struggle with describing intent, evaluating generated results, and editing prompts after errors.

---

## R5 — Response latency in LLM-powered VR agents

Maslych, M., Katebi, M., Lee, C., Hmaiti, Y., Ghasemaghaei, A., Pumarada, C., Palmer, J., Segarra Martinez, E., Emporio, M., Snipes, W., McMahan, R. P., & LaViola, J. J., Jr. (2025). **Mitigating Response Delays in Free-Form Conversations with LLM-powered Intelligent Virtual Agents.** *Proceedings of the 7th ACM Conference on Conversational User Interfaces (CUI '25)*, Article 49, 1–15.  
DOI: https://doi.org/10.1145/3719160.3736636  
arXiv: https://arxiv.org/abs/2507.22352

**Study:** VR conversational-agent study, **N = 54**.

**Used for:** controlled evidence that latency above roughly four seconds degraded quality of experience and that natural conversational fillers can improve perceived response time under delay.

---

## R6 — Capability communication / transparency

Reimann, M. M., Kunneman, F. A., Oertel, C., & Hindriks, K. V. (2025). **Transparent Conversational Agents: The Impact of Capability Communication on User Behavior and Mental Model Alignment.** *Proceedings of the 7th ACM Conference on Conversational User Interfaces (CUI '25)*, Article 48, 1–12.  
DOI: https://doi.org/10.1145/3719160.3736629  
VU research page: https://research.vu.nl/en/publications/transparent-conversational-agents-the-impact-of-capability-commun/

**Study:** speech-based study, **N = 56**.

**Used for:** capability communication altered user behavior but did not by itself significantly improve mental-model alignment, showing that "tell users what the AI can do" is not a complete solution.

---

## R7 — Multimodal grounding for embodied AI

Zhang, T., Au Yeung, C., Aurelia, E., Onishi, Y., Chulpongsatorn, N., Li, J., & Tang, A. (2025). **Prompting an Embodied AI Agent: How Embodiment and Multimodal Signaling Affects Prompting Behaviour.** *Proceedings of the 2025 CHI Conference on Human Factors in Computing Systems (CHI '25)*, Article 60, 1–25.  
DOI: https://doi.org/10.1145/3706598.3713110  
Project page: https://ricelab.github.io/papers/zhang2025embodiedagent/

**Used for:** embodied/visual signals exposing system understanding; the study reports that users were able to prevent errors in 30% of relevant cases and were more satisfied/confident when understanding signals were available.

---

## R8 — Mixed-initiative / scaffolded control in VR

Zhang, L., Pan, J., Gettig, J., Oney, S., & Guo, A. (2024). **VRCopilot: Authoring 3D Layouts with Generative AI Models in VR.** *Proceedings of the 37th Annual ACM Symposium on User Interface Software and Technology (UIST '24)*.  
DOI: https://doi.org/10.1145/3654777.3676451  
arXiv: https://arxiv.org/abs/2408.09382

**Studies:** first study N = 14; second study comparing manual, scaffolded, and automatic creation **N = 15**.

**Used for:** intermediate representations and scaffolded creation can preserve more user agency than fully automatic generation; multimodal/manual interaction produced the highest perceived creativity and agency.

---

## R9 — Conversational repair after AI errors

Do, H. J., Kong, H.-K., Tetali, P., Lee, J., & Bailey, B. P. (2023). **To Err is AI: Imperfect Interventions and Repair in a Conversational Agent Facilitating Group Chat Discussions.** *Proceedings of the ACM on Human-Computer Interaction*, 7(CSCW1), Article 99, 1–23.  
DOI: https://doi.org/10.1145/3579532

**Study:** online study, **N = 175**.

**Used for:** conversational repair can mitigate some negative effects of erroneous agent interventions. The task is group-chat facilitation rather than tailoring, so this is supporting evidence for the interaction principle of repairability, not direct evidence about VR tailoring.

---

# 20. Recommended citation logic for the presentation

Do **not** combine external study sample sizes with the current N = 22 as if they were one larger sample.

Use the literature as **triangulation**:

> "Our formative survey suggests X. Similar mechanisms have also been observed independently in [paper / venue], using a different task and study design."

Preferred wording:

- **"consistent with"**
- **"aligns with"**
- **"provides independent evidence for the same interaction problem"**
- **"suggests a similar design implication"**

Avoid:

- **"our result is validated by"** unless the external study tests the same construct and setup;
- **"N = 22 + 54 = 76"**;
- direct comparison of percentages across different populations/tasks as though they measured the same variable.

---

# 21. Bottom line

With **N = 22**, the study should be presented as a **small formative survey with directional evidence**, not as a conclusive evaluation.

The strongest story is not that all three initial assumptions were "proved." The data refine them:

1. **Intent:** users often know what they want but may struggle to express and ground it.
2. **Flow:** latency and loss of agreed state break conversational continuity.
3. **Execution:** imperfect matching is manageable if users can inspect the result and selectively repair it.

The combined evidence points toward a coherent HCI opportunity:

> **Move from opaque speech-only tailoring toward an inspectable, mixed-initiative interaction loop that preserves the convenience of conversation while adding lightweight grounding, progress feedback, preview, state visibility, and local repair.**

That direction is supported by the current survey, the original IEEE VR system's observed limitations, and independent work from CHI, DIS, CUI, UIST, and CSCW.
