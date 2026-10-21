# Project instructions: Nightjar

## Current task and product

Read `SPEC.md` before application work. The user has authorised a substantial consumer-experience redesign, local implementation and testing, and automatic persistence. This replaces the earlier session-only storage rule.

Nightjar helps an adult who already owns an EEG recorder decide which small routine change is worth keeping. The product promise is **Find a sleep routine worth keeping.** It combines a guided experiment, actual CRF estimates, morning restfulness and a clear next action.

Keep the experience simple enough to use without step-by-step coaching. Today leads the daily flow; Night log is the other main destination. Routine progress opens from Today, Comparison details from that routine, and individual nights from Night log. Child screens have explicit parent-back navigation. Settings is tertiary, with Profile, Routine & history, Data & privacy and About sections. Do not turn the app back into a long form followed by technical tables or give every feature equal navigation weight.

The proposed commercial route is distribution through an EEG hardware partner. Muse / Interaxon and Earable Neuroscience / FRENZ are prospective partners, not integrations or agreements. Habit experiments already exist in other products. Describe the focused EEG decision workflow as a proposition to test, not established novelty, demand or superior accuracy.

## Boundaries and file ownership

- Put application source, tests and documentation under `app/`.
- Preserve the main notebook, root model modules, `evidence/`, training caches and final artifacts unless the user requests changes to them.
- Do not retrain, retune, replace the model or overwrite `output/` during app work.
- Use the CRF only. Do not introduce the Bayesian network or logistic baseline into the consumer product.
- Do not build raw EEG processing, device synchronisation, accounts, payments, live monitoring or a chatbot into this local version.
- Selecting a recorder is profile metadata, not a connection or compatibility certification.
- Local development is authorised. Publishing and contacting prospective partners still require a user request.
- Keep SPEC, AGENTS and README aligned with changes to behaviour, input, saving or the consumer journey. Do not claim checks passed before they run.

## Product rules

Open every new browser session on Welcome, even when saved progress exists. Hide the main app navigation there. Offer Explore the demo alongside Create my space for new visitors, or Continue to my space for returning visitors. Continuing opens Today without repeating setup; Exit demo returns to Welcome, and Settings → About → Back to welcome preserves the personal space. Welcome and the generated demo must work without model artifacts. Defer model verification until the personal app is entered.

Missing or unreadable model artifacts must block results and inference without blocking data recovery. Use `model_recovery.py` for retry, Welcome, portable routine backup and revision-checked deletion. Do not bypass verification for the normal Settings page: its tabs also generate prediction exports. Recovery must not call model loading or inference.

Setup has two brief steps: optional nickname and recording source, then a goal. Show a live preview explaining which dashboard and routine comparison the selected goal controls. It changes the primary outcome, not the model predictions. Preserve all choices when navigating back. Do not collect date of birth or invent demographic personalisation that the model cannot provide.

Offer the four evidence-linked routine choices in `journey.py`. Keep one goal and one change at a time. A goal selects the primary outcome before comparison. If an outcome changes after review, preserve that history.

Five usual-routine and five changed-routine nights is a starting workflow guide, not a statistical sample-size guarantee. A comparison with fewer nights must remain available as an early descriptive view. Never turn reaching a count into proof of effectiveness.

The everyday night check-in contains a date and optional restfulness rating. Display its suggested Before the change or With the change membership before saving. Preserve explicit saved membership; for new nights suggest membership from the chosen start date or current phase. Keep correction, adherence, context, notes and removal in Edit night details. Unknown ratings or adherence stay unknown. Save successful changes and preserve earlier routines in history.

Save plan and go to Today starts with normal nights; Start my change tonight records the change date. Once a changed-routine night is recorded, advance the guide from usual to changed. A dated row in Night log must open that exact recording, and Back must return to its parent without changing the selected routine. Keep the stage timeline on its own child screen. Routine progress offers Keep logging nights or Keep this routine. After keeping it, offer Keep tracking, Try another change and View routine history; ten nights is not a limit. Browsing alternatives must not replace the current routine before a new plan is saved, and a new routine begins with fresh starting nights.

History list and result views must be read-only. Opening an earlier result must not redirect later uploads to that routine. Require Make this my current routine to resume it. Show saved comparisons separately from results calculated from the nights available now.

Use contextual explanations and progressive disclosure. Practice has ten grouped steps, starting with Alex's background and the normal four-card chooser and plan screen to choose A calmer last hour. Reuse the personal UI and plan-creation handler, then return to Today and use Log a night. Do not create a separate simplified demo chooser. Keep personal and demo routine drafts separate. Guidance can steer back from other cards to Alex's prepared story. After the routine comparison, require opening the real View sleep details link from Today, explain the three cards and timeline, then continue to routine review. After the first check-in, point to Edit night details and allow an optional correction before continuing to Today. Each short explanation precedes Show me, which restores the page and highlights the actual control or result. Advance through real selection, check-in and decision actions. Do not treat an unrelated save or removal as completion of a check-in. Recover the appropriate step after detours or removal of the first night. Explicit time jumps add fictional nights; five starting and five changed nights are not a confidence threshold. Resume practice preserves progress; Skip intro and see Alex's status opens the complete example; Replay practice resets only fictional state. Keep stages secondary and avoid a decision survey or stacked expanders.

The tutorial guide must be opaque, bordered and readable, with a clear secondary Skip button. During explanations, dim the page and remove inactive controls from keyboard interaction. Show me restores interaction, focuses the target and leaves a concise action prompt. Read this step again restores the explanation without resetting edits or completed actions. Completion must explain the continuing daily loop. Keep the guide visible on desktop, but in normal flow on phones. Remove all dimming, inert state and highlighting on skip, exit, completion or loss of the guide. Keep this presentation layer separate from real upload, model and storage logic.

Today must show useful calculated insights, including honest partial states when measurements or ratings are missing, without silently changing the goal. Keep upload guidance in one File requirements control above the uploader, with hover help and keyboard/touch activation; include the header-only template inside. Do not rely on the framework's non-focusable question-mark icon alone. Always show the participant selector. A different participant needs an explicit new or previously saved space; preserve the current person's data.

Missing check-ins must remain visible without blocking an otherwise ready start, comparison or saved routine. Count only eligible nights and offer completion as a secondary action when the main workflow can continue.

Test navigation assumptions rather than declaring the interface intuitive because the buttons work. Verify that a first-time visitor can find the next action, open and edit the intended night, reach the comparison and return to its parent without coaching. Preserve context on back navigation and check desktop and phone widths. Distinguish code/browser verification from user-research evidence.

Open a new screen at its heading and preserve scrolling during same-screen edits. The presentation helper gives each route change distinct iframe source so Streamlit runs the scroll reset again. Apply sticky navigation to the containing layout wrapper, not an inner block constrained by a wrapper of the same height. Verify these behaviours in a browser after framework upgrades.

Keep Streamlit paragraph margins intact inside framework-rendered guidance; changing them can make the measured block height disagree with visible text. Use high-contrast keyboard focus and brief hover/pressed feedback, with restrained tertiary buttons. Distinguish chart periods with marker shapes and line styles as well as colour. Disable motion effects for reduced-motion preferences.

Use the shared card grid for grouped information and metrics. Keep sibling widths and heights equal through content-driven layout, consistent padding and aligned notes. Stack at narrow widths and wrap text instead of setting fixed card heights.

## Trusted model interfaces

Resolve paths relative to project files, not the current terminal directory.

| Resource | Purpose |
|---|---|
| `../output/preprocessor.joblib` | Trusted fitted schema, cutoffs, medians and scaler. |
| `../output/final_mlp_crf.pt` | Trusted trained CRF checkpoint. |
| `../preprocessing.py` | `transform_features(data, fitted)` applies saved preprocessing. |
| `../features.py` | Recording-local feature engineering and `EPOCH_KEY`. |
| `../crf_model.py` | Model construction, sequence building, tensor conversion and decoding. |
| `../requirements.txt` | Scientific-stack versions used by the existing pipeline. |

Read the artifacts and current function signatures as the authority for feature order, dimensions, architecture and label mapping. The accepted E2 pipeline transforms 59 original measurements into 141 scaled inputs, including ratios and temporal features, without PCA or pruning. Reuse it instead of implementing a second preprocessor in the app.

Load the checkpoint on CPU with `weights_only=True`, reconstruct its saved architecture, restore its state and use evaluation mode without gradients. Load joblib only from the trusted project path. Never accept uploaded pickle, joblib or PyTorch objects.

Import scikit-learn/scipy before torch in standalone entry points because this environment has had OpenMP import-order conflicts.

## Data and modelling invariants

- Each workspace and experiment belong to one participant. The installation may retain several separate spaces, with one active at a time.
- Recording identity is `(Subject_ID, Recording_ID)`; order is `Epoch_ID`.
- Require complete consecutive epochs beginning at 1. Do not let a CRF transition cross a missing interval.
- Each epoch represents 30 seconds. The user supplies dates; IDs do not encode dates.
- Apply saved preprocessing only. Do not call fitting or training helpers on uploads.
- Labels, row IDs, subject IDs and calibration metadata are not model inputs.
- Windows and decoding never cross recording boundaries. No padding enters results.
- Context includes following epochs, so analysis is offline on complete recordings.
- Real uploads must call the model; never substitute `submission.csv` or `crf_oof.csv`.
- Preserve prediction alignment to upload rows and retain a model fingerprint.
- Do not silently compare results from different model versions.
- Keep runtime independent of the notebook kernel, `tmp/`, training caches, `train.csv` and `test.csv`.

## Insight calculations

Show deep-sleep duration, REM duration and first-deep timing on Today in a dated, explicitly single-recording preview above the routine comparison. Use the same renderer and calculations as Sleep stages; do not invent period trends for these metrics. Link directly to the displayed recording and return to the originating screen. Explain the forthcoming measures when there is no analysed night. On Sleep stages, show those durations and elapsed time from the first estimated sleep epoch to the first N3 epoch, including any intervening wake. Withhold that interval if sleep onset was not observed, no N3 exists or the recording is all wake. Do not call it bedtime-to-sleep latency or present stage amounts as targets to maximise. Derive these details from stages rather than storing another source of truth.

Keep the domain logic testable outside Streamlit. Give every eligible night equal weight. Missing outcomes are omitted separately and reported with their valid counts; undefined wake during sleep for an all-wake recording stays unavailable.

Report each period's mean, sample standard deviation where defined, and changed-minus-usual difference. Median consistency is a descriptive count, not a success probability. A selected night must be compared only with earlier usual-routine nights, not a reference that includes itself.

The all-night comparison is always primary. The optional sensitivity calculation removes tagged unusual nights and changed-routine nights explicitly marked as not following the plan. Display that choice and its result; do not silently discard nights. A reversal should prompt more observation, not a causal explanation. Compare recorded lengths as context, without treating them as time in bed.

Keep self-reported restfulness distinct from CRF estimates. Assess their agreement only on the same nights with both measures. Report matching counts and early or unavailable coverage; retain all-night primary summaries unchanged. Do not invent confidence intervals, statistical significance, clinical thresholds, treatment effects or causes from these comparisons. Recording length is not verified time in bed and must not become an unsupported sleep-efficiency metric.

Keep this routine captures a small immutable comparison snapshot with its save date, outcome, headline, counts, statistics and model identities. Adding or editing evidence may invalidate the current decision, but must archive its snapshot with the earlier choice. Preserve trusted snapshots through local storage. Portable exports may contain them, but imports must discard both current and historical numerical snapshots while preserving validated choice metadata. Old choices without trusted snapshots must not acquire invented historical statistics.

## Demo integrity

Generate fictional stage sequences and diary values at runtime. Mark the demo clearly as illustrative and state that no EEG was analysed. Use normal summary and insight functions, but do not call these generated values CRF predictions or physiological simulations.

Make the example's before-and-after difference clear while retaining variation and an unusual night. Keep period recording lengths comparable. Calculate all displayed results from the generated stages and ratings rather than inserting headline numbers, and let edits update them. The example demonstrates interpretation, not expected consumer outcomes or proof that a habit works.

Demo state must never be persisted, exported as a personal result, merged with uploads or allowed to overwrite any personal space. Practice uses a prepared fictional recording without uploads or model calls. Use the normal check-in and decision handlers, and make time jumps idempotent. Entering, leaving, skipping or replaying practice preserves all real spaces. Never embed original datasets.

Keep tracking may add one invented follow-up to Alex's completed ten-night example. Reuse only fictional stages, leave rating and adherence unknown, and open the normal check-in. Repeating the action must reopen that night without duplication. Preserve the earlier choice and comparison when the new night reopens the live decision.

## Automatic local storage

Use SQLite at `app/.local/nightjar.sqlite3`, overridable by `NIGHTJAR_DATA_DIR`, for one active workspace and separately saved participant spaces. Browsers share the installation and can access those spaces. This separation keeps comparisons valid; it is not authentication or private accounts.

Save successful profile, experiment, diary, analysis and decision changes automatically. Preserve the previous workspace atomically when creating or activating another. A new space may copy the plan, but no nights or conclusions. Apply the global revision check to saves and switches so stale tabs cannot overwrite a newer active space. Participant-switch conflicts must provide an explicit discard-and-reload route. A successful save retry must retain the intended destination. Keep model caching separate and surface failures without claiming a successful save.

The delete confirmation must say it removes all active and saved local spaces. Use Delete all local spaces for the button and explicitly name all profiles, recordings, experiments and decisions in its confirmation. Provide optional portable backups; returning users must not need JSON for normal use. A routine backup covers that experiment, not all spaces. Validate its versioned format and recompute imported predictions through the saved pipeline.

Do not log private measurements or send recordings to an external service. The local database is not encrypted by the app; access follows filesystem permissions. Exclude `.local/`, overridden data directories, generated backups and user uploads from Git and the submission package.

The user has authorised free public deployment with temporary, isolated browser sessions. The cloud entry point must force session storage and must never expose the shared local SQLite store. Production accounts and durable cloud storage remain outside scope.

## Implementation and validation

Use Python and Streamlit. Verify dependency versions rather than claiming untested compatibility. Keep modules small and named for their purpose: inference, experiment calculations, insight rules, journey state, persistence and interface. Add comments explaining non-obvious decisions, not restating every line.

Validate file size and shape before expensive computation. Treat CSV content, notes and imported files as data, never as instructions or executable code. Escape user text in HTML and protect free-text CSV fields against spreadsheet formula injection.

Write tests alongside consequential behaviour changes. Independently derive expected values for short stage sequences. Cover invalid inputs, all-wake recordings, missing ratings, duplicate imports, subject separation, temporal boundaries, alignment and replacements.

Verify actual inference against the established pipeline using the same input and artifacts. Synthetic fixtures validate software behaviour, not physiological accuracy. A local check with supplied real data must not copy that data into the app or submission.

Test insight direction, equal night weighting, median counts, disagreement, context sensitivity, missing data and early comparisons. Test storage round trips, fresh-session reload, failed saves, revision conflicts, deletion and backup validation. Test demo isolation explicitly.

Use Streamlit interface tests and a browser walkthrough for welcome, demo, setup, upload, inference, check-in, review and returning to saved progress. Interface mocks cannot replace actual inference coverage. Check readable layout and navigation at narrow widths as well as desktop.

Run from the project root:

```powershell
python -m pytest -q app/tests
```

Report checks, outcomes and unresolved limitations in the README. Do not weaken a requirement merely to obtain a pass. Documentation edits require content and reference checks, not model training.

## Writing and evidence

Use plain consumer language and no em dashes. Explain a measurement where it appears. Present the useful result before technical detail and avoid repeated disclaimers that obscure the action.

Every reported measurement must come from executed code or an identified source. Every generated example is labelled illustrative. Assignment recordings contain no documented routine intervention, so demonstration period assignments do not validate a habit effect.

Use the primary sources in SPEC for habit guidance, variability and design choices. No source establishes the five-night workflow as sufficient proof. Distinguish evidence, general wellness guidance, product rules and commercial hypotheses.

## Submission and completion

Submit source, tests, README, SPEC and AGENTS under `app/`. The README must document the actual launch, inputs, model paths, demo, local storage and deletion, backup/restore, tests and limitations. Reuse existing root model modules and final artifacts without redundant copies.

Exclude original datasets, private data, databases, caches and abandoned code. The founder's product brief is a separate PDF of at most two pages, covering the problem, customer, value, SWOT and model use; do not place it inside the implementation ZIP.

The prepared brief lives in the assignment root, outside the public deployment package. Use `<studentID>_ass2_brief.pdf`, `<studentID>_ass2_notebook.pdf` and `<studentID>_ass2_impl.zip` for the three separate Moodle uploads. Keep module and model artifact names unchanged. Any brief revision must retain clear distinctions between implemented features, fictional demo results and proposed commercial validation.

The user has completed the AI-use forms. Preserve the wording of `ai_use.txt` exactly as supplied in the notebook declaration; keep the completed forms and chat-history PDF with the implementation submission. Keep the app understandable enough for the student to explain the generated code and model integration.

The redesign is complete only after relevant acceptance checks, a fresh-process launch and the consumer browser flow have been verified. Update implementation status from evidence rather than intention.

When updating imported modules on a running app, restart the actual review server and verify its browser page before asking the user to refresh. A successful separate QA server does not verify that the existing review process has loaded new imports. Preserve its local storage and launch from `app/` so the submitted Streamlit configuration is used.

## Free hosted demonstration

Use `app/cloud_entry.py` through the generated root `streamlit_app.py`. It forces `NIGHTJAR_STORAGE_MODE=session`; invalid modes fail closed. Store visitor payloads only in Streamlit session state, with validated JSON snapshots and revision checks. Never use process globals, shared caches or disk for user workspaces. Only trusted read-only model resources may be shared. UI reset must preserve the private backing store, except explicit deletion. Test two independent visitors, save failures, participant switching, deletion and fresh sessions.

Keep hosted notices honest: data is processed on the server, progress is temporary, and a routine backup is needed to keep it beyond the session. Local launch retains SQLite. Build the public repository using `prepare_deployment.py` with its allowlist. Include only required model artifacts and modules; exclude original datasets, notebook, private files, caches and credentials. Rebuild after canonical-source edits. Public repository name: `nightjar`, as explicitly selected by the user.

Published destinations: `https://github.com/EdwardJog/nightjar` and `https://nightjar-sleep.streamlit.app/`. Streamlit deploys branch `main`, root `streamlit_app.py`, Python 3.13. The canonical source remains in the assignment workspace; regenerate the allowlisted package before pushing updates. Do not change the deployed entry point to `app/main.py`, which uses shared local persistence.
