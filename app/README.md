# Nightjar

**Find a sleep routine worth keeping.**

[Open the live app](https://nightjar-sleep.streamlit.app/) · [GitHub source](https://github.com/EdwardJog/nightjar)

For marking, open the live app and choose **Explore the demo**. No installation is needed. The local launch below remains available.

Nightjar is a sleep experiment companion for people who already own an EEG recorder. It guides one manageable routine change, estimates sleep from compatible recordings with the saved Part I MLP-CRF, and compares the results with how the person felt in the morning.

The app opens with a welcome screen and guided demo. **Today** is your daily dashboard; **Night log** is your recording history. Open routine progress from Today and individual nights from the log. Settings stays separate from the daily flow. Local use saves automatically on this computer; the hosted demonstration keeps progress only in the current browser session.

The setup goal chooses the main comparison: morning restfulness, wake during sleep or estimated sleep duration. A live preview explains the effect before you create your space. It does not change the CRF predictions, and the other measures remain available.

The dashboard's **Inside your latest night** section shows estimated deep sleep, REM duration and time from first sleep to first deep sleep. Its date and one-recording label distinguish these from the routine comparison. **View sleep details** opens that exact night's cards and stage timeline, with **Back to Today** returning to the dashboard. The same details remain accessible through each night in Night log. The first-deep interval includes intervening wake. That interval is unavailable if the recording starts asleep or contains no deep sleep. It is not time to fall asleep after going to bed, and stage amounts are not targets to maximise.

## Run locally

Use the same Python environment as the assignment. From the project root:

```powershell
python -m pip install -r app/requirements.txt
cd app
python -m streamlit run main.py
```

Keep the terminal open. Open [http://127.0.0.1:8501](http://127.0.0.1:8501) in Chrome or another browser on the same computer. Use the address printed in the terminal if it differs.

If port 8501 is occupied, choose another port:

```powershell
python -m streamlit run main.py --server.port 8502
```

Open the printed address, normally [http://127.0.0.1:8502](http://127.0.0.1:8502). Stop the server with **Ctrl+C in its terminal**. Closing a browser tab does not stop the server or delete saved progress.

Starting inside `app/` loads `.streamlit/config.toml`, including the theme, local-only address, upload limit and disabled usage statistics. The author's Python executable is `C:/Users/edwar/anaconda3/python.exe`.

After updating Python modules, restart the server with Ctrl+C followed by the same launch command, then refresh the browser. A browser refresh alone can leave older imported modules in memory and produce a `cannot import name` error. Restarting preserves saved local spaces; an in-progress fictional demo starts again.

The recorded environment uses Streamlit 1.51.0, Plotly 6.3.0 and pytest 8.4.2, with the scientific-stack versions in the root requirements. Inference needs no paid service, API key, GPU, internet connection, notebook kernel or new training run.

## Required files

Keep the existing project structure:

```text
project/
  app/
    main.py
    dashboard.py
    routine_history.py
    demo_guide.py
    walkthrough.py
    walkthrough.js
    walkthrough.css
    upload_views.py
    night_views.py
    presentation.py
    theme.css
    cards.css
    journey.py
    experiments.py
    insights.py
    storage.py
    inference.py
    model_recovery.py
    tests/
    .streamlit/config.toml
    requirements.txt
    README.md
    SPEC.md
    AGENTS.md
  preprocessing.py
  features.py
  crf_model.py
  requirements.txt
  output/
    preprocessor.joblib
    final_mlp_crf.pt
```

Paths resolve from the source files. The app loads only these trusted model artifacts; users do not upload models. It does not read `submission.csv`, `crf_oof.csv`, the Bayesian network or the logistic baseline.

The runtime database is created automatically under `app/.local/`. It is private working data, not a required submitted file.

## First use

Every new browser session starts on Welcome. If you already have saved progress, choose **Continue to my space** to open Today; setup is not repeated. **Explore the demo** remains available, and **Exit demo** returns to Welcome. You can also return through **Settings → About → Back to welcome** without deleting anything.

1. Choose **Explore the demo** for guided practice using Alex's invented nights. Read each short explanation, then press **Show me** to highlight the real control or result. Add the example, save a check-in, build the comparison and save a choice. No file is uploaded or EEG analysed. The secondary **Skip intro and see Alex's status** button opens the completed example; **Replay practice** restarts only fictional data. Navigation away keeps your place with **Resume practice**.
2. Choose **Exit demo**, then **Create my space**. Enter an optional nickname, select the recording source and choose the outcome that matters to you. Back preserves these choices. Device choices are descriptive: they do not connect a headband or certify compatibility.
3. Setup returns to Today. Choose **Choose a routine**, then one card: a calmer last hour, a steadier wake-up, an earlier last coffee, or a quieter, darker room. Add an optional specific plan and select **Save plan and go to Today**. Later, browsing alternatives leaves the current routine active until you save a new plan.
4. **Today** brings together one next action and your calculated results: period averages, a trend, consistency, morning ratings and relevant context. Early or missing data gets a partial view instead of invented conclusions. First record normal nights; Today then offers **Start my change tonight**.
5. **Open routine progress** shows the comparison. **Night log** lists individual nights; open a dated row to see and edit that night. **View routine history** opens past routines without changing the one underway. Detail screens have a clear Back button. **Settings** contains profile changes, optional exports and deletion.

Welcome and the generated demo work without the saved model files. Those artifacts are checked when you enter your personal app, and are required for analysing real recordings. If the check fails, the recovery screen still offers **Retry model check**, **Back to welcome**, **Download routine backup** and confirmed deletion of all local spaces. It keeps old results and inference blocked.

Navigation stays available while scrolling. New screens open at the top; changing a field on the same screen keeps your place. Controls have hover, pressed and clearly visible keyboard-focus feedback. Comparison charts distinguish the periods by marker shape and line style as well as colour. Card groups have equal-width, equal-height rows and stack on phones without fixed heights. Brief screen transitions respect the system's reduced-motion preference.

The starting guide is five usual-routine nights followed by five nights trying the change. This is a manageable observation plan, not proof that five nights establish effectiveness. Earlier comparisons are available and labelled accordingly. Missing a night does not reset the experiment.

Starting the change records today's date. New nights dated before that count as **Before the change**; dates on or after it count as **With the change** unless you explicitly choose otherwise. Existing assignments are retained. Recording a changed-routine night also advances the guide, so Today follows what you have entered.

### A short demonstration

The practice has ten grouped steps. Its solid, bordered guide first dims the page and temporarily disables its controls. **Show me** restores the page, highlights the target and gives a brief action prompt. **Read this step again** reopens the explanation without resetting your work. The guide stays visible during desktop actions; on phones it stays in normal page flow and focus moves to the target. Skip and Exit remain available.

1. Meet Alex, whose busy evenings and wakeful nights prompted an experiment, then select **Start practice**.
2. Press **Show me** and use **Explore this routine** on the **A calmer last hour** card. This is the same four-card chooser used in your own space. Review the same plan screen, optionally make it specific, then **Save plan and go to Today**. From Today, choose **Log a night**.
3. Reveal **Use example recording**, then select Alex's participant and recording and add the night.
4. Reveal the normal check-in screen. Its fictional date is supplied; try 2 out of 5 or leave the rating unrecorded, then **Save check-in**.
5. See where **Edit night details** lives. Try correcting a note or context, or **Continue to my dashboard**.
6. Reveal the first night's dashboard, then **Add four more example nights**. The next explanation highlights **Start my change tonight**.
7. Reveal **Add five example nights with the change**. The practice uses its prepared calendar; in real use those recordings arrive on separate mornings.
8. Reveal Today's calculated differences, consistency and morning ratings, then **Explore Alex's sleep details**.
9. Find **Inside your latest night** on Today and press **View sleep details**. Read the deep/REM/timing cards and timeline, then **Review Alex's routine**.
10. Reveal and use the normal **Keep this routine** action to save the fictional choice. The completion message explains the continuing loop: keep tracking, try another change or revisit history.

Time jumps cannot add duplicate nights, and none of this practice is saved to your personal spaces. Detours keep the guide aligned with the example; removing the first practice night returns you to adding it instead of claiming it was saved. For a short presentation, use the practice or skip to the completed dashboard, then demonstrate real inference separately with a compatible upload. The fictional example does not demonstrate CRF accuracy or a successful real intervention.

The completed example has average wake during sleep of **45 minutes before** and **18 minutes with the change**, a difference of **−27 minutes**. Four of five changed nights improve on the starting median; one unusual night remains in the main comparison. Default morning ratings average **2.0 versus 4.2**. These results come from the generated stages and ratings through the normal calculations, and edits can change them. They illustrate how to read a result, not what a customer should expect.

To try the next morning, choose **Keep tracking**, then **Add another example night**. This adds one fictional follow-up using the last example's stage sequence, opens the normal check-in and leaves the rating unknown. The current result updates while the saved choice remains in history. **Open the example follow-up** reopens that same night instead of adding duplicates.

### Test with the assignment's real recordings

Use the original **`test.csv`**, not a submission CSV or a prediction export. It remains outside `app/` and must not be bundled in the implementation ZIP.

1. Create a personal space with **Compatible feature CSV** as the source. For a walkthrough without invented ratings, choose **Spend less time awake at night** or **Make more room for sleep** as the goal.
2. Choose a routine and save the plan. Press **Log a night** on Today, or **Add a night** in Night log. Select `test.csv`, choose participant **1**, and keep recordings **1** and **2** selected.
3. Press **Analyse & add nights**. The app cleans and transforms the measurements using the saved settings, then decodes each complete recording.
4. Open each recording from Night log, enter a different past **Night date**, leave restfulness as **Not recorded**, and select **Save check-in**. These dates are illustrative: the source file does not provide them.
5. Open **Edit night details** for each night. To demonstrate both sides of the comparison, assign one to **Before the change** and one to **With the change**. Leave adherence as **Not recorded** and add a note such as "Assignment demonstration; date and routine assignment are illustrative." Press **Save night details**. Do not invent feelings or circumstances.
6. Return to Today and choose **Open routine progress**. The result is an early descriptive two-night comparison, not evidence that the chosen habit helped.

The original `test.csv` is about 73.5 MiB and fits the parser's 100 MiB limit. Participant 1's two recordings contain 2,289 epochs in total. Adding them can take longer than the generated demo.

## Daily use and insight

Each morning, add the compatible export and open the resulting night. The daily check-in asks for its date and optional restfulness. It shows whether the night counts **Before the change** or **With the change** before you save. New nights use the change's start date, or the current routine phase if no date has been set; explicitly saved membership is retained. Correct the membership, record whether the plan happened, or add context through **Edit night details**. **Sleep stages** opens the optional chart. No download is required to return tomorrow.

| Result | Meaning |
|---|---|
| Estimated sleep | Number of predicted N1, N2, N3 and REM epochs multiplied by 0.5 minutes. |
| Estimated wake during sleep | Predicted W epochs between the first and last predicted sleep epochs, multiplied by 0.5 minutes. Unavailable if no sleep was predicted. |
| Morning restfulness | Optional self-rating from 1, not at all rested, to 5, very rested. |
| Main comparison | Changed-routine mean minus usual-routine mean, with every eligible night weighted equally. |
| Consistency | How many changed-routine nights fall on the goal-aligned side of the usual-routine median. |
| Variation | Sample standard deviation between nights; unavailable for a single observation. |
| Context check | A second comparison without flagged unusual nights or changed-routine nights when the plan was not followed. The all-night result remains primary. |
| Recording coverage | Average recorded length in each routine. Different start/end conditions can complicate a comparison; this is not time in bed or a sleep-efficiency score. |

Only dated, assigned nights enter comparisons. Missing outcomes have their own valid counts. The feelings-versus-recordings insight uses nights with both measures, reports those matching counts and identifies early or unavailable comparisons. The main results still use all eligible nights. Individual-night comparisons use earlier usual-routine nights, excluding the selected night itself.

A routine comparison offers **Keep logging nights** and **Keep this routine**. Keeping it saves a snapshot of the comparison behind that choice, including its date, outcome, counts, means and model identifiers. Today and routine progress then offer **Keep tracking**, **Try another change** and **View routine history**. Ten nights is a starting plan, not a limit.

Adding or editing nights updates the current comparison and reopens the choice for review. Its earlier snapshot remains in history instead of changing with the new results. History shows saved and current results separately; browsing it does not switch the active routine. Use **Make this my current routine** explicitly if you want to add nights to an earlier routine.

**Try another change**, also available through Settings, keeps the old routine and starts a new comparison with fresh starting nights. Old measurements are not reused automatically. Changing the profile goal applies to future routines; one underway keeps its chosen outcome. Settings also offers **Start the change early**. Missing check-ins remain visible as reminders without hiding a ready comparison. An all-wake recording stays in history but has no wake-during-sleep value to count toward that outcome.

Comparisons are descriptive. They do not establish causation, significance or treatment effectiveness. The model can miss brief stage changes, and no stage percentage is a personal target. The optional chart is a predicted sleep-stage timeline, not a raw EEG trace. The app does not estimate sleep debt, diagnose conditions or compute a clinical sleep-quality score.

## Compatible CSV format

The file must be UTF-8 and contain:

- `Subject_ID`, `Recording_ID` and `Epoch_ID`.
- All 59 original measurements named in the saved preprocessor. **Download column template** supplies their exact names as a header-only CSV.
- Optionally, a unique, non-missing `Row_ID`; otherwise the app generates `Upload_Row_ID`.

Each row is a 30-second epoch. Within each subject-recording pair, epochs must be consecutive integers starting at 1. Shuffled rows are accepted. Missing identifiers, duplicate headers, duplicate epoch keys and gaps are rejected before inference.

The established preprocessing handles malformed measurements, missing values and supported power reconstruction. A recording with no usable original measurements is rejected. Additional columns, supplied labels and calibration metadata are excluded. Dates come from the user, not recording IDs. Routine membership is visibly suggested and can be corrected before or after saving.

A workspace belongs to one participant. The upload always shows **Which participant is you?**, even for a single-person file. Choosing a different participant offers **Use a separate space**, or **Open this participant's saved space** if one exists. The current person's nights are retained; a new space copies the plan but no nights or conclusions. Return through **Settings → Profile → Other saved spaces → Open selected space**.

Identical imports are skipped; conflicting measurements require explicit replacement and fresh analysis. Each experiment uses one complete recording per night date. Replacement preserves its diary but invalidates affected results. Hover over or open **File requirements** above the uploader for the combined guide. Its button supports keyboard and touch; the panel includes a column-name template and closes with Escape. The template is not a complete recording.

Limits are 100 MiB per feature CSV, 100 CSV columns, 100,000 epochs per experiment and 10,000 epochs per recording. A portable experiment is limited to 150 MiB; the saved workspace is limited to 200 MiB. These are software resource limits. Streamlit shows a 150 MiB upload limit, while the CSV parser enforces its stricter 100 MiB limit.

## Saving, privacy and data controls

The default SQLite database is **`app/.local/nightjar.sqlite3`**. It stores one active workspace and any separately saved participant spaces, including profiles, experiments, required measurements, diary entries and trusted results. Browsers using this installation can access these spaces. Separating participants keeps comparisons valid; there is no sign-in or account privacy.

To choose another location, set the environment variable before launch. For example, from `app/` in PowerShell:

```powershell
$env:NIGHTJAR_DATA_DIR = "C:\path\to\private\nightjar-data"
python -m streamlit run main.py
```

The app creates `nightjar.sqlite3` inside that directory. It does not encrypt the database; access follows the computer's filesystem permissions. Uploaded measurements and notes are not sent to external services or logged by the application.

Changes save automatically. Creating or switching spaces preserves the previous space atomically. Global revision checks prevent stale tabs from overwriting changes or switching against a newer save. If saving fails, **Not saved yet** keeps the edits in that tab. Retrying a temporary save failure completes the intended navigation after saving; you can instead deliberately discard unsaved edits and reload. A participant-switch conflict also offers this reload route so the tab can use the latest saved space.

Under **Settings → Data & privacy**, select **Delete all profiles, recordings, experiments and decisions**, then **Delete all local spaces** to remove **all active and saved participant spaces** from this installation. Closing the browser keeps them. Exported copies, operating-system backups and copies elsewhere must be removed separately.

**Do not deploy this shared local store as a public multi-user app.** Public hosting needs authentication, isolated storage and retention controls first. The current configuration listens on the local computer only.

### Optional portable copies

Open **Settings → Data & privacy**. **Routine backup** downloads the active routine, and **Import as a separate experiment** restores an earlier copy.

| Download | Contents |
|---|---|
| `nightjar_experiment.json` | The active experiment's required measurements, diary, context, adherence, selected outcome and decision history, including saved comparison snapshots. This is one experiment, not a full profile backup. |
| `nightjar_nights.csv` | Per-night estimated measurements, ratings, context, adherence, notes and model fingerprint. |
| `nightjar_stages.csv` | Predicted stages, epoch identifiers and model fingerprint. |
| `nightjar_comparison.html` | A printable comparison, nightly information and calculation explanations. |

An imported JSON becomes a separate experiment for the same person. Import preserves measurements, check-ins and decision history, but discards predictions and both current and historical numerical comparison snapshots. These editable file contents are not trusted model results. Analyse the restored recordings to generate a new comparison; the original historical statistics cannot be recreated from changed data. Normal local autosave retains trusted results and snapshots, so reopening does not require reanalysis unless the model artifacts change.

HTML escapes user text. Free-text CSV cells that could be treated as formulas are prefixed with an apostrophe. Uploaded pickle, joblib and PyTorch objects are never accepted. Portable files contain private recording information; keep them accordingly.

## Source map

| File | Responsibility |
|---|---|
| `main.py` | Navigation, setup, routine actions and data controls. |
| `dashboard.py` | Calculated Today insights and partial-data views. |
| `routine_history.py` | Comparison snapshots and history views; resuming an earlier routine is explicit. |
| `demo_guide.py` | Hands-on fictional practice, progress, time jumps and replay. |
| `walkthrough.py`, `walkthrough.js`, `walkthrough.css` | Tutorial dimming, keyboard restrictions, target highlighting and cleanup. |
| `upload_views.py` | Real CSV uploads, participant selection and separate-space handling. |
| `night_views.py` | Dated night log, individual-night check-in, optional night details and stage view. |
| `presentation.py`, `theme.css`, `cards.css` | Reusable card grids, charts, formatting and responsive styling. |
| `journey.py` | Profile, routine library, experiment progression and generated demo. |
| `experiments.py` | Recording identity, diary, measurements, portable files and exports. |
| `insights.py` | Equal-night comparisons, consistency, context sensitivity and next-action text. |
| `storage.py` | Active and saved SQLite spaces, global revision checks and deletion. |
| `inference.py` | Input validation, trusted artifact loading and actual CRF inference. |
| `model_recovery.py` | Retry, portable backups and confirmed deletion when model files are unavailable, without displaying results. |

The model uses context on both sides of each epoch, so complete recordings are analysed offline. The adapter applies the existing root preprocessing and CRF functions without fitting anything on uploaded data. Model fingerprints invalidate saved predictions when the artifacts change.

## Tests and verification

From the project root:

```powershell
python -m pytest -q app/tests -p no:cacheprovider
```

Tests use generated fixtures, including actual model inference. Coverage includes input validation, fixed preprocessing, recording boundaries, alignment, hand-calculated summaries, missing outcomes, equal weighting, context sensitivity, diary and decision history, storage round trips and conflicts, demo isolation, safe exports and the interface flow.

Streamlit AppTest 1.51.0 does not expose a file-upload setter. Upload interface tests substitute the widget's returned bytes; this does not replace parsing or inference. Synthetic fixtures test software behaviour, not physiological accuracy.

The interface tests also use a local adapter for AppTest's stale controls after an in-script rerun. It removes only parsed widget nodes whose backend state no longer exists. A regression verifies that active edits and application errors remain visible. Installed Streamlit files are unchanged; browser checks exercise the actual continuous navigation.

**Earlier verification, 21 October 2026: all 143 tests passed in 77.88 seconds.** Coverage includes the consumer interface, Alex's story and explicit routine choice, optional guided night edits, all three setup goal previews, deep/REM duration and first-deep timing edge cases, saved comparisons, history, continuing after Keep, the fictional follow-up, matched-night insights, missing-model recovery, real inference, validation and persistence.

The dashboard-metric revision passed all 51 interface and demo tests in 110.70 seconds. These include the complete ten-step practice, latest-night routing, all-wake and already-asleep recordings, and returning to Today or Night detail according to where the details were opened. The actual review server was restarted and checked in-browser: the three measures are visible on Today, the link opens the correct night, and Back to Today works. At 390 × 844 the preview cards had equal dimensions and no horizontal overflow. Browser checks used only the fictional demo.

The shared routine-screen revision passed 38 interface checks and 12 demo/history checks. The latter run completed in 19.12 seconds. Checks cover all four cards, the normal plan editor, an optional custom plan, saving to Today, logging the first night, exploring another card without altering Alex's story, and keeping personal drafts separate. A fresh-process browser check followed this flow at 1440 × 1100. Both modes call the same chooser and plan-creation code; there is no separate simplified demo chooser.

The browser check completed the revised nine-step practice, including choosing Alex's routine, saving an optional note, returning to the guide and keeping the result. It found and fixed an unnecessary repeated explanation after leaving the editor; all nine demo regression tests then passed in 14.68 seconds. At 1440 × 1000, the three new stage cards had equal widths and heights. At 390 × 844 they stacked at equal widths without horizontal overflow, and the goal preview updated correctly. Finishing practice cleared the keyboard restrictions. QA used a separate temporary storage directory and did not change personal data.

The previous browser audit completed the seven-step guide, including reopening an explanation without losing an entered rating. Focus and scrolling worked at 1280 × 600 and 390 × 844 without horizontal overflow. Completing the guide removed highlighting and keyboard restrictions and revealed the continuing-use actions. At 1440 × 1000, dashboard metric and information cards had equal sibling dimensions. The history view remained readable at 320 × 740 without horizontal page overflow.

Adding the eleventh example night opened its normal check-in. History retained the saved 27-minute wake-time difference while the live result changed to 28.3 minutes. Starting a different routine created an empty starting period and kept the previous 11 nights in history. Viewing those earlier results and returning to Today left the new routine active.

Continuing beyond the starting target now shows a completed goal instead of an overfilled count such as “6 of 5”. Minute averages use readable rounding while calculations retain full precision. Returning from the demo reopened the saved personal space and cleared tutorial restrictions.

An earlier real-data parity check reproduced all **2,289** predictions for participant 1's two test recordings in the saved E2 submission. This navigation revision does not alter inference. The submission file was used only for verification, never as a runtime source. The model/preprocessor fingerprint remains `c30342747efd82a7e7b2d5115a2b44d3594015e40ccdd54c37a0627622880da3`.

Browser verification uses isolated databases and generated recordings, including real CRF inference. Viewport and keyboard checks are not tests on physical phones or a usability study. They establish software behaviour, not consumer-headband accuracy.

Development screenshots and generated browser fixtures belong in `tmp/app_qa/`, outside submitted app files. No original dataset is bundled under `app/`.

## Evidence, scope and submission

`SPEC.md` contains the product rationale, primary research links, competitor comparison, prospective partners, commercial hypotheses and Part III mapping. `AGENTS.md` records implementation and verification rules. General routine ideas follow [NIH healthy sleep habits](https://www.nhlbi.nih.gov/health/sleep-deprivation/healthy-sleep-habits); five nights per period is a product guide, not an evidence-based guarantee.

Muse and Earable Neuroscience are prospective partners. There is no device sync or validated hardware integration. A commercial version would need compatible extraction and evaluation on that device; the assignment results do not establish performance there.

For submission, keep source, tests, documentation and the existing trusted model artifacts. Exclude original datasets, `app/.local/`, any custom data directory, user exports, caches, development screenshots and abandoned experiments. `.gitignore` helps with Git but does not automatically filter a manually created ZIP.

The founder's product brief is a separate two-page PDF in the assignment root. It covers the customer, value, actual CRF use, competition, partner distribution, revenue hypotheses, SWOT and proposed validation pilot. Submit it separately from the implementation ZIP; it is not part of the public app package. Completed AI forms, `ai_use.txt` and the chat-history PDF accompany the assignment source in the implementation ZIP.

The required Moodle upload names are `<studentID>_ass2_notebook.pdf`, `<studentID>_ass2_impl.zip` and `<studentID>_ass2_brief.pdf`. The notebook source uses `<studentID>_ass2_notebook.ipynb`. Preserve module and model filenames so imports and artifact loading still work. The notebook PDF and product brief must be uploaded separately, outside the implementation ZIP. Original `train.csv` and `test.csv` are excluded: restore your supplied copies to the project root before rerunning the research notebook. The app's guided demo needs neither dataset; uploaded compatible features are processed with the supplied saved model.

## Free deployment and browser sessions

The local app keeps automatic SQLite saving. The hosted demonstration uses `app/cloud_entry.py` and separate temporary Streamlit session state, so visitors do not share participant spaces. Uploaded CSVs are processed on the hosting server. Refreshing, losing the session or restarting the server may clear progress; download a routine backup in Settings to keep it. No account, paid database or API key is required. This is a hosted prototype, not durable consumer accounts.

Run `python app/prepare_deployment.py` from the assignment root to build the allowlisted package in `tmp/deployment/nightjar`. Only that folder is published to the public GitHub repository `nightjar`. Original datasets, notebook, experiments, databases and caches are excluded. See [deployment instructions](DEPLOYMENT.md) for Python version, entry point, publishing and updating. The app is deployed and verified at https://nightjar-sleep.streamlit.app/.

### Deployment verification

Final submission recheck on 21 October 2026: all 151 app tests passed in 155.54 seconds. All 39 root, app and test Python files also passed syntax checks. This check used the unchanged application code and saved inference artifacts.

On 21 October 2026, all 151 tests passed (199.71 seconds), including isolated hosted visitors, local storage regression, demo flows and real inference with generated fixtures. The clean deployment package separately passed five inference and cloud-interface checks (18.40 seconds). Both test processes exited successfully; Windows sandbox temporary-directory cleanup emitted a permission warning after completion. Linux x86-64 / Python 3.13 dependency resolution succeeded using CPU-only PyTorch. Browser checks confirmed that a second tab starts empty while the first retains its fictional test profile, and that hosted saving notices render correctly. No personal SQLite file was used by the hosted preview.

The app-only source is published at https://github.com/EdwardJog/nightjar. Streamlit deployed successfully on Python 3.13.16 with torch 2.14.1+cpu. The live app completed setup, routine creation, upload and actual CRF inference. All 21 exported predictions for two generated QA recordings matched the local model exactly. A second visitor started with no personal workspace and opened the guided demo; the completed Alex dashboard also rendered. These are software checks, not clinical validation or a concurrent-load benchmark.
