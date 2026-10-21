# Nightjar: Personal Sleep Experiment Companion

Status: free hosted-session mode is implemented. All 151 tests passed, plus five checks from the clean deployment package. Browser isolation and Linux dependency resolution were checked. GitHub sign-in, publication and the live Linux deployment remain pending. The README records verification details.

## Product purpose

**Find a sleep routine worth keeping.**

Nightjar helps an adult who already owns an EEG recorder answer one question: "Which small change is worth keeping in my routine?" It turns compatible recordings into estimated sleep measurements, pairs them with how the person felt, and guides them through a comparison of their usual routine and one chosen change.

The problem is the gap between tracking and deciding. A consumer can see a shorter night or a different stage chart without knowing whether to change anything. Nightjar gives them a manageable next action, a history that saves automatically, and an understandable review of several nights. It does not ask them to interpret EEG or optimise every stage.

| Consumer need | Product response |
|---|---|
| Understand the value before doing setup | An interactive, clearly labelled example available from the welcome screen. |
| Know what to do today | One primary action based on the current experiment and unfinished nights. |
| Try something manageable | Four habit cards, one selected goal and one change at a time. |
| Avoid judging a habit from one unusual night | Period averages, night-to-night variation and a visible check of unusual circumstances. |
| Understand a mismatch between numbers and feelings | Estimated sleep and morning restfulness presented separately, with agreement or disagreement explained. |
| Make a practical decision | Keep trying, keep the routine or try a different routine, with the comparison and decision retained. |
| Return without managing files | Automatic local saving; portable backups are optional. |

The app describes observed differences. It supplies no diagnosis, treatment, causal proof, guaranteed improvement or invented sleep-quality score. More estimated sleep is interpreted relative to the user's chosen goal, not as an instruction to maximise sleep duration indefinitely.

## Commercial proposition and differentiation

The proposed route to market is a consumer service distributed through an EEG hardware partner, potentially as a premium feature with subscription revenue sharing. A pilot should test whether the guided comparison helps people make decisions, complete experiments and return to their device. Demand, willingness to pay, revenue terms and retention benefits remain hypotheses.

Habit experiments are not a new category. [Oura Experiments](https://support.ouraring.com/hc/en-us/articles/19663280975379-Oura-Experiments) already guides one-habit comparisons, and [WHOOP Journal](https://support.whoop.com/s/article/WHOOP-Journal-Overview?language=en_US) connects logged behaviour with physiological measurements. [RISE](https://www.risescience.com/) frames its value around useful daily actions. Nightjar's proposed distinction is a focused decision process for EEG owners: one goal, one manageable change, understandable recording estimates, a check of the comparison's limitations, and a record of what the person chose to keep. This combination needs user testing; it is not a claim of market uniqueness or superior accuracy.

### Prospective partners

| Organisation | Published basis for considering it | Proposed collaboration |
|---|---|---|
| Muse / Interaxon | Its [developer programme](https://choosemuse.com/pages/developers) provides an SDK and a commercial licensing route. | Explore compatible feature extraction and a partner-distributed experiment companion. |
| Earable Neuroscience / FRENZ Brainband | Its [partnership programme](https://frenzband.com/pages/earable-neuroscience-research-partnership-services) describes data access, licensing and co-branded services. | Explore a companion combining compatible recordings with routine comparisons. |

These are prospective partners, not supported integrations or existing relationships. Selecting a recorder in setup records the user's source; it does not connect a device. Commercial use would require suitable data access, feature extraction and validation on that hardware, with retraining if needed. Assignment-data performance does not establish consumer-headband performance or superiority to another tracker.

| SWOT | Assessment |
|---|---|
| Strength | A working CRF connected to a focused experiment and decision workflow. |
| Weakness | Specialised feature input, imperfect predictions and a local prototype without production accounts. |
| Opportunity | Give existing EEG owners a reason to return to their recordings and hardware. |
| Threat | Existing apps or hardware partners could reproduce the workflow; integration cost and terms may limit viability. |

## Scope and navigation

Use the saved Part I MLP-CRF in a local Streamlit application. No Bayesian network, logistic baseline, training, raw EEG processing, live monitoring, payments or chatbot is included.

The two main destinations are **Today** and **Night log**. Today is the daily dashboard: one next action, the current routine and the latest night. **Routine progress** opens from the dashboard, and **Comparison details** opens from that routine. **Routine history** is a child destination for past choices and results. **Settings** is tertiary, for profile, routine options and data controls. Each child screen has a visible route back to its parent. New screens open at the top; editing a field on the current screen retains its scroll position.

Every new browser session opens on Welcome, including when a personal space is saved. Welcome shows the introduction and demo choice without the main navigation. A new visitor uses **Create my space**; a returning visitor uses **Continue to my space** to reach Today without repeating setup. Exiting the demo returns to Welcome. **Settings → About → Back to welcome** reopens the introduction without clearing data. Welcome and the generated demo do not require the model artifacts; verify the saved model when the person enters their personal app.

If model files are missing or unreadable, `model_recovery.py` provides retry, return to Welcome, a routine backup and confirmed deletion of all local spaces. Results and inference remain blocked. Recovery must not require loading the model or exposing ordinary Settings tabs that render prediction exports.

### First use

1. Show Welcome with **Explore the demo** and **Create my space**, or **Continue to my space** when progress is already saved.
2. Use two short setup steps: an optional nickname and recording source, then the person's main goal. Update a visible preview as the goal changes, explaining which measure will lead the dashboard and routine comparison. The choice does not change model predictions. Do not request a date of birth: the current model cannot use it to personalise its estimates.
3. Explain automatic local saving once, where the profile is created. The person can inspect or delete their local data later.
4. Return to Today, where **Choose a routine** offers four routine cards. Choosing a goal determines the primary outcome before comparisons are reviewed. **Save plan and go to Today** starts with normal nights; Today later offers **Start my change tonight**.
5. Teach through ten grouped practice steps, from meeting Alex and choosing a change to saving a choice. Each short explanation precedes **Show me**, which restores the page and highlights the real control or result. Normal application actions advance the practice. Detours preserve the step; the person can resume, skip, exit or replay.

### Daily journey

- **Today:** place one useful next action above a dated **Inside your latest night** preview of deep sleep, REM and first-deep timing. Mark these as one-recording estimates, give a direct **View sleep details** link, and return from that child screen to Today. With no analysed night, explain what will appear without inventing values. Follow this preview with calculated period averages, a trend, consistency, morning ratings and relevant context. Show partial measurements when a full comparison is unavailable, without inventing results or changing the goal. **Open routine progress** and **Open latest night** lead to detail; **View night log** opens history.
- **Routine progress:** explain the comparison as **Before the change** and **With the change**. Show the result and pattern, then offer direct **Keep logging nights** and **Keep this routine** actions. **View comparison details** opens the supporting measures, context check and earlier choices. Avoid an unexplained phase diagram or a decision questionnaire.
- **After keeping a routine:** offer **Keep tracking**, **Try another change** and **View routine history**. Save an immutable comparison snapshot with the choice. Later nights and edits update the current result and reopen the decision while retaining its earlier snapshot. Ten nights is not a stopping limit.
- **Routine history:** browse saved and current results without switching the active routine. Resuming an earlier routine requires **Make this my current routine**. A new routine retains the old records and begins a fresh starting period without automatically reusing nights.
- **Night log:** show clickable dated nights, with undated uploads first. Open a night directly rather than choosing a recording ID from a dropdown.
- **Night detail:** show understandable estimates and a short check-in containing the date and optional morning restfulness. Display how the night will count before saving. **Edit night details** holds routine membership, adherence, context, notes and removal; **Sleep stages** opens the optional timeline.
- **Settings:** use Profile, Routine & history, Data & privacy and About sections. Keep goals, an early change start, a different routine, past routines, exports and deletion here rather than among daily actions.

Starting the change records that date. New nights use a visible routine suggestion based on that start date, or the current phase when no start date exists. Explicitly saved membership is retained. The person can correct the suggestion in Edit night details. Night dates still come from the person; recording IDs never become calendar dates. Context tags are Travel, Unwell, Alcohol, Unusual stress and Schedule change. Missing ratings or adherence remain unknown.

Five usual-routine nights followed by five changed-routine nights is a starting guide for using the product, not a validated sample-size rule or proof of effectiveness. Shorter comparisons remain descriptive and clearly early. The progress target must not be presented as a statistical confidence threshold. Incomplete check-ins remain reminders; they must not hide the next action when sufficient eligible nights already support starting or reviewing.

### Demo

Generate fictional stage sequences and diary entries at runtime. The banner states that no EEG was analysed. Practice uses no uploads or model calls, but uses the same routine chooser, plan screen, plan creation, check-in, comparison and decision logic as personal use. Guidance highlights Alex's choice without replacing the actual screens. Other cards can be explored; saving another choice during guided practice asks the visitor to return to Alex's prepared routine. Personal use and free exploration allow all four routines.

The ten grouped steps introduce Alex's busy evenings and goal of less wake during sleep, ask the visitor to choose **A calmer last hour** through the normal four-card chooser, review and save the normal plan, return to Today and choose Log a night, prepare an example recording and select its participant, save a real check-in, point to optional night corrections, build five starting nights and begin the change, add five changed nights, read the dashboard, open the latest night's sleep details and timeline, and save a choice. **Edit night details** is highlighted after the first check-in; the visitor can try a correction or continue. The first night supplies its fictional date and leaves the rating optional. Explicit time-jump buttons add four further starting nights and five changed nights; guidance explains that real recordings arrive on separate mornings. Repeating a jump cannot duplicate nights.

A solid, bordered guide explains one step while the rest of the page is dimmed and keyboard-inert. **Show me** restores interaction and highlights the actual action or result, with a concise action prompt. **Read this step again** restores the explanation without resetting progress. Completion explains continued tracking, another change and history. The guide remains visible on desktop; on phones it stays in normal flow so the focused control has room. Skip is a clear secondary button. Skipping, exiting, replaying or losing the guide removes any restrictions; reduced-motion preferences are respected.

The invented example makes the comparison easy to see: mean wake during sleep changes from 45 to 18 minutes, four of five changed nights improve on the starting median, and one unusual night stays in the main comparison. Default ratings average 2.0 and 4.2. The periods have the same mean recording length. Normal summary functions calculate these values from generated stages and diary entries; they are neither model predictions nor a promised effect of the routine.

**Skip intro and see Alex's status** opens a complete ten-night example. **Replay practice** restarts only fictional data. Free navigation preserves progress and offers **Resume practice**. No demo data enters local storage, exports as a personal result, overwrites a saved space or mixes with uploads. Real uploads still call the model.

After the comparison, **Keep tracking → Add another example night** adds at most one fictional follow-up and opens the normal check-in. It reuses the last example's generated stages and supplies no rating or adherence answer. Later uses show **Open the example follow-up**. The live decision reopens while its saved comparison stays in history, demonstrating continued use beyond ten nights.

## Routine library and evidence

| Habit | Action | Rationale |
|---|---|---|
| A calmer last hour | Set aside the hour before bed for quiet activities and softer light. | A repeatable quiet period puts general pre-bed guidance into practice. |
| A steadier wake-up | Choose a realistic wake-up time while leaving enough opportunity for sleep. | Regular sleep and wake times support a consistent routine. |
| An earlier last coffee | Choose an earlier cutoff for caffeinated drinks. | Caffeine can affect sleep for up to eight hours; the app does not infer an individual cutoff from EEG. |
| A quieter, darker room | Change one practical source of light or noise. | A quiet, dark bedroom is part of healthy sleep guidance. |

These options follow [NIH/NHLBI healthy sleep habits](https://www.nhlbi.nih.gov/health/sleep-deprivation/healthy-sleep-habits). They are general wellness suggestions to explore, not treatments or promises about an individual's response. Do not offer medication, supplement changes or sleep restriction. Do not infer a physiological explanation for a night's result from a context tag.

## Inputs and validation

- Required columns are `Subject_ID`, `Recording_ID`, `Epoch_ID` and the original feature columns saved in the fitted preprocessor.
- Each row represents 30 seconds. A recording is identified by `(Subject_ID, Recording_ID)` and has consecutive integer `Epoch_ID` values starting at 1.
- Accept shuffled rows and restore their temporal order. Reject missing identifiers, duplicate columns, duplicate epoch keys and gaps before decoding.
- Preserve a unique supplied `Row_ID`, or generate an explicit upload-row identifier. Identifiers are not predictors.
- Exclude extra columns, supplied labels and calibration metadata from inference. Never use uploaded labels to generate or evaluate test predictions.
- Reuse existing cleaning, power reconstruction and imputation. A recording with no usable original measurements is rejected instead of being predicted entirely from training medians.
- Night dates, adherence, ratings and context come from the person, never from IDs. A new night's suggested routine membership comes from the chosen start date or phase, is shown before saving, and can be corrected. Do not invent feelings or assume adherence from membership.
- Each workspace and experiment belong to one selected participant. Always show the participant selector after validating an upload. Selecting a different participant offers an explicit separate saved space, preserving the current person's nights; people must never be pooled.
- Identical reuploads cannot inflate a comparison. Conflicting reuploads require an explicit replacement choice and invalidate affected predictions.
- Updated diary entries must immediately change derived comparisons; replaced measurements require fresh inference.

## Model behaviour

Load the trusted fitted preprocessor and CRF from the submitted `output/` artifacts. Apply their existing cleaning, feature engineering, imputation and scaling unchanged. Never estimate parameters from an upload or substitute stored submission predictions.

The model uses following epochs and centred feature windows, so it analyses complete recordings offline. Every feature window and CRF sequence stays within one subject-recording pair. Preserve prediction-to-row alignment and exclude padding from every result.

Predict `W`, `N1`, `N2`, `N3` and `REM`. Identical inputs and artifacts must produce predictions matching the existing inference path. Keep a model fingerprint with computed results; results from different model versions must not silently form one comparison.

## Measurements and insight rules

Each eligible night has equal weight. A longer recording does not receive greater weight because it contains more epochs.

| Measurement | Definition |
|---|---|
| Estimated sleep | Number of non-W epochs multiplied by 0.5 minutes. |
| Estimated wake during sleep | W epochs between the first and last non-W epochs, multiplied by 0.5 minutes. |
| Morning restfulness | Optional user rating from 1, not at all rested, to 5, very rested. |
| Stage duration | Number of epochs in each predicted stage multiplied by 0.5 minutes. |
| Deep sleep and REM | N3 and REM durations, shown on Today, night detail and Sleep stages. |
| First deep sleep | Elapsed time from the first non-W epoch to the first N3 epoch, including intervening wake. Unavailable if the recording starts asleep, contains no N3 or contains no sleep. |
| Stage timeline | Predicted stages against elapsed recording time, with plain-language labels. |

The stage timeline stays secondary to the chosen goal, while the three stage measures are visible on Today without opening another screen. First deep sleep is not the time taken to fall asleep after going to bed, since bedtime is not measured. Do not supply invented stage targets or imply that more deep sleep or earlier deep sleep is always better. The [NIH sleep-stage explanation](https://www.nhlbi.nih.gov/health/sleep/stages-of-sleep), checked 21 October 2026, supports distinguishing N3 and REM; it does not validate this model's estimates.

If all epochs are W, estimated sleep is zero and wake during sleep is unavailable. Recording duration is not a measured time-in-bed window, so do not invent sleep efficiency from it. The model can miss brief stage changes; avoid presenting a count of predicted awakenings as a clinical measure of fragmentation.

Only dated, assigned nights enter period comparisons. Exclude missing outcomes separately and show the valid counts. Compare unrounded values, then round for presentation.

Saving a changed-routine night advances the guide to trying the change, even if the user did not press the explicit phase button. Navigating to the next unfinished night must update both the recording selector and the check-in form.

The insight layer provides:

1. **Primary comparison:** each period's count, mean and sample standard deviation, and changed minus usual difference. Standard deviation is unavailable for a single observation.
2. **Consistency:** count how many changed-routine nights lie on the goal-aligned side of the usual-routine median. This is descriptive, not a probability of benefit.
3. **Variation:** show night-to-night spread so an average is not mistaken for every night's experience.
4. **Feelings alongside recordings:** explain whether changes in estimated sleep measures and morning restfulness agree or differ. Neither invalidates the other.
5. **Sensitivity check:** repeat the comparison without tagged unusual nights or changed-routine nights marked as not following the plan. Keep the all-night comparison primary and visible. Explain if the direction changes; never silently remove inconvenient results. Show average recording length alongside this check, because differing recording windows can complicate the interpretation. Recorded length is not time in bed.
6. **Individual-night context:** compare a selected night with earlier usual-routine nights only. Do not include that night in its own reference.
7. **Next action:** use incomplete data, early comparisons, mixed patterns or a completed starting guide to suggest a practical action. The rule is visible product guidance, not a diagnosis or a calibrated confidence model.

Compare feelings with recordings only on nights where both measures are available. Report those matching counts and distinguish early or unavailable coverage; independently available averages can otherwise give a misleading agreement signal. Keep all eligible nights in the main outcome summaries.

Do not report statistical significance, causal effects or a "proven" habit. Avoid arbitrary clinical thresholds, universal stage targets and pressure to achieve perfect sleep. A retrospective before/after comparison is not a randomised N-of-1 trial. Changing the main outcome after review must be recorded rather than silently rewriting the experiment's purpose.

## Persistence, privacy and portability

The user has authorised automatic saving. Use SQLite at `app/.local/nightjar.sqlite3`, or the directory selected by `NIGHTJAR_DATA_DIR`, for one active workspace and separately saved participant spaces. Save profile, experiments, diary entries, required measurements and trusted computed results after successful changes.

- Browsers on this installation share the active space and can access other saved spaces. Participant separation protects comparison integrity; it is not authentication or privacy between users.
- Creating or switching spaces atomically preserves the previous space. A new participant can inherit the plan but never another person's nights or conclusions. **Settings → Profile → Other saved spaces → Open selected space** restores an earlier space.
- Use a global revision check so stale tabs cannot overwrite changes or switch the active space against a newer save. Explain conflicts and offer an explicit discard-and-reload route for participant switches as well as ordinary saves.
- A failed save must not be described as successful. Give a recoverable error without deleting the active session. A successful retry completes the originally requested navigation.
- Separate generated demo state from personal state; never persist it.
- Store a small comparison snapshot when a routine is kept: save date, chosen outcome, headline, period counts and statistics, and model identifiers. Later edits must not rewrite the snapshot. Archive it with the earlier decision when the live comparison changes.
- **Delete all local spaces** explicitly removes all active and saved local spaces, with a confirmation naming all profiles, recordings, experiments and decisions. Portable backups remain optional; routine backups contain one experiment, not every participant or profile.
- Validate versioned imported backups as data. Preserve measurements, check-ins and choices, but discard predictions and numerical snapshots at both the current-comparison and decision-history levels. Recompute a new comparison through the model; never present imported historical statistics as trusted results.
- Optional CSV and readable report exports distinguish estimates from self-report and identify the model. Escape text in HTML and protect free-text CSV cells against formula injection.
- Do not log private measurements, send recordings to external services, commit the database or include it in the submission ZIP.

The local database is not encrypted by the app. Its access follows the computer's filesystem permissions. The public demonstration uses isolated, temporary browser sessions instead of this local database. Durable online accounts would require a separate authentication and retention design.

## Design principles and research

The dashboard is the starting point for daily use. Top-level navigation represents distinct destinations, not steps in a form. Routine progress and comparisons sit below the dashboard; a night opens from the night log. Every detail screen has an explicit route back to its parent. Settings, exports and history are secondary to the daily task.

Use calm, readable layouts and one clear primary action. Present the useful result before its calculation. Offer one route to supporting detail rather than a stack of collapsed technical sections. Avoid a stage diagram that assumes people already understand the process, a decision questionnaire followed by a save button, large forms, mandatory free text and repeated introductory banners.

Practice separates a short explanation from doing the action. **Show me** reveals and highlights the target; normal check-in and decision handlers perform the work. Explain fictional time jumps distinctly from day-to-day recording. Combine CSV guidance in one File requirements control above the uploader: hover for help, or open it with keyboard or touch to read the guide and download the column-name template. Use clear hover, pressed and keyboard-focus states; brief route transitions honour reduced-motion preferences.

Keep navigation available while scrolling. Open a new screen at its heading without moving the page during same-screen edits. Preserve setup choices when going back, and recover practice after detours or removal of its first night. Browsing alternative routines keeps the current routine active until a new plan is saved. Once five starting nights are present, both Today and routine progress should offer starting the change as the next action. Chart periods use different marker shapes and line styles as well as colour.

Use shared grids for information and metric cards. Siblings have equal widths and heights set by their content, with consistent padding and aligned notes. Stack cards on phones and allow text to wrap; avoid fixed card heights.

Test the assumptions behind the flow: can a first-time visitor identify the next action, understand which night they are editing, find the routine comparison and return to the dashboard without coaching? Check those tasks at desktop and phone widths, including a fresh return visit. Automated checks establish behaviour; an observed walkthrough and user feedback are still needed to assess whether the flow makes sense.

Research informing the design:

| Source | Design consequence |
|---|---|
| [Apple onboarding guidance](https://developer.apple.com/design/human-interface-guidelines/onboarding) | Offer an optional interactive example, brief setup and contextual tips. |
| [Apple tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) and [layout guidance](https://developer.apple.com/design/human-interface-guidelines/layout) | Reserve top-level navigation for distinct destinations, preserve context and put the most useful daily content first. |
| [NN/g recognition rather than recall](https://www.nngroup.com/articles/recognition-and-recall/) and [progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/) | Use visible habit choices and defer detail until needed. |
| [Messman et al., 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9649840/) | Healthy sleepers vary from night to night; show repeated nights and variation rather than judge one night. |
| [AHRQ guidance on personal trials](https://effectivehealthcare.ahrq.gov/products/n-1-trials/research-2014-1) | Choose an outcome in advance and account visibly for context; do not claim simple before/after differences establish cause. |
| [Baron et al., 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5263088/) | Avoid perfect-sleep targets and alarming stage judgements; the reported cases raise a design concern about tracking-related anxiety. |

Sources checked on 20 October 2026. They support design choices and general guidance, not validation of Nightjar's effectiveness. In particular, no source establishes five nights per period as sufficient proof.

## Acceptance criteria

| ID | Check |
|---|---|
| A1 | Documented launch works without a notebook kernel, training run or paid external service. |
| A2 | Welcome and practice work without model artifacts. Check-in saves advance practice, time jumps cannot duplicate nights, and resume, skip or replay never changes personal spaces. Returning users continue without repeating setup. |
| A3 | Two-step setup creates a durable profile without mandatory nickname or unsupported demographic collection. |
| A4 | Today gives one useful next action. Night log opens individual nights, routine progress opens from Today, and child screens have clear routes back. The guided demo explains that loop without replacing intuitive navigation. |
| A5 | Real uploads call the saved preprocessing and CRF, with useful validation errors and no refitting or label use. |
| A6 | Shuffled inputs preserve aligned predictions, recording boundaries remain separate, padding is excluded and predictions match the original path. |
| A7 | Independent hand calculations verify sleep, internal wake, stage durations and the all-wake case. |
| A8 | Tests cover equal night weighting, missing outcomes, unequal sizes, early or empty periods, median consistency and the sensitivity check. |
| A9 | Explicit participant selection, separate-space creation and restoration, duplicate imports, replacement and model-fingerprint handling prevent invalid comparisons. |
| A10 | Saves and participant spaces survive a fresh session. Global revisions protect saves and switches; deletion covers all local spaces; errors and portable restore are tested. |
| A11 | Goals, context, adherence, decisions and comparison snapshots survive saving. Changes update live results without rewriting past choices. History browsing leaves the active routine unchanged. |
| A12 | Interface tests and browser checks cover first use, demo, upload, real analysis, check-in, review and data controls. |
| A13 | Submitted files contain no original datasets, private workspace database, hidden labels, runtime cache or abandoned experiments. |

## Part III deliverables

| Brief requirement | Evidence to provide |
|---|---|
| Web app calling Part I CRF or Part II network | Actual CRF inference from compatible uploaded feature CSVs. |
| Agentic development | Final source, tests, README, SPEC and AGENTS under `app/`, with an accurate AI-use declaration. |
| Business value and creativity | A defined EEG-owner problem, decision workflow, competitor comparison, proposed partners and testable commercial assumptions. |
| Quality and reproducibility | Relevant passing tests, browser verification and documented local launch without paid services. |
| No embedded datasets | Generated, labelled demo examples and user-supplied real recordings. |
| Product brief, at most two pages | Separate PDF covering customer, problem, value, revenue hypothesis, SWOT, prospective partners and model use. |

The three-minute demonstration should show the value through the demo, then one real upload and inference path, its understandable output and saved return visit. Assignment recordings do not document a habit intervention; any demonstration routine assignments for them must be labelled illustrative.

Reference: FIT5149 S2 2026 Assessment 2, Sections 2.3, 4 and 5, and Appendix H. The local brief at `../tmp/reference_documents/FIT5149_S2_2026_Assessment_2.pdf` is a development reference, not a runtime dependency. Completion and verification claims belong in the README only after those checks have run.

## Free deployment and browser sessions

The local app keeps automatic SQLite saving. The hosted demonstration uses `app/cloud_entry.py` and separate temporary Streamlit session state, so visitors do not share participant spaces. Uploaded CSVs are processed on the hosting server. Refreshing, losing the session or restarting the server may clear progress; download a routine backup in Settings to keep it. No account, paid database or API key is required. This is a hosted prototype, not durable consumer accounts.

Run `python app/prepare_deployment.py` from the assignment root to build the allowlisted package in `tmp/deployment/nightjar`. Only that folder is published to the public GitHub repository `nightjar`. Original datasets, notebook, experiments, databases and caches are excluded. See [deployment instructions](DEPLOYMENT.md) for Python version, entry point, publishing and updating. Publication and the Linux cloud build remain unverified until the live service is checked.
