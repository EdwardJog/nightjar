# Nightjar

[**Open Nightjar**](https://nightjar-sleep.streamlit.app/)

**Find a sleep routine worth keeping.** A guided sleep experiment companion using a saved MLP-CRF, with an interactive fictional walkthrough and real inference from compatible EEG feature CSVs.

Source: [EdwardJog/nightjar](https://github.com/EdwardJog/nightjar).

## Hosted demonstration

This repository is the small deployment package. The full assignment notebook, original datasets, personal database and training caches are excluded. The hosted app starts with **Explore the demo** or **Create my space**. A marker can explore the demo without uploading a file. For real inference, upload the assignment's compatible feature CSV through **Log a night** and choose a participant and recording. Raw EEG files are not supported.

Each Streamlit browser session has a separate temporary workspace. Other visitors cannot select or load that workspace through the app. Uploads are sent to the server for processing; the app does not deliberately write personal workspaces to disk or cache them globally. Refreshes, disconnects, inactivity, redeployment or server restarts can lose progress. Use **Settings → Data & privacy → Routine backup** before leaving if you want a portable copy. Each backup contains one routine, not all participant spaces. Imported predictions are recomputed.

This is a demonstration without accounts or durable cloud storage. It does not provide production security, uptime guarantees or a medical service. Free hosting may sleep when idle, so the first visitor may need to wait for it to wake.

## Deploy for free

1. Publish the contents of this folder as the public GitHub repository **nightjar**. Do not publish the parent assignment directory.
2. Sign into [Streamlit Community Cloud](https://share.streamlit.io/) with GitHub and create an app from that repository.
3. Select branch **main**, entry point **streamlit_app.py**, and **Python 3.13** in Advanced settings. No secrets, payment information, external database or API key are needed.
4. Deploy, wait for the build, then verify the interactive demo and one compatible upload. Open a second browser session to confirm it starts without the first visitor's personal space.
5. Put the resulting `https://…streamlit.app` link into the assignment handover. Keep the source ZIP and required assignment documents as well.

Dependency versions match the local scientific stack; PyTorch uses the official CPU wheel to avoid GPU packages. The live Linux build was verified on Python 3.13.16. Real CRF inference on 21 generated QA epochs matched the local model exactly; separate browser sessions and the demo were checked. This does not establish capacity under heavy concurrent use. Installation does not train a model.

## Run this deployment package locally

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Open the **Local URL** printed by Streamlit, normally `http://localhost:8501`. If you choose another port, use that printed URL. Stop with Ctrl+C in its terminal. This entry point always uses temporary sessions, even when run locally.

For persistent local use of this package:

```powershell
python -m streamlit run app/main.py
```

That entry point uses `app/.local/nightjar.sqlite3`. Browsers connected to the same local installation share its saved spaces. Do not expose that entry point on a public server. The cloud entry point explicitly disables disk storage.

## Contents and checks

- `app/`: interface, generated demo, inference integration, storage, tests and product documentation.
- `preprocessing.py`, `features.py`, `crf_model.py`: unchanged inference dependencies from Part I.
- `output/`: only the fitted preprocessor and trained CRF checkpoint.
- `deployment-manifest.json`: SHA-256 hashes of the allowlisted package files.

Developer checks: install `pytest==8.4.2`, then run `python -m pytest -q app/tests`. The tests use generated fixtures and the saved model, without requiring original assignment data. See `app/README.md` for recorded checks and full usage. See `app/SPEC.md` and `app/AGENTS.md` for the product and development rules. The deployment package contains no example participant data; the demo generates fictional stages.

To update the public app, edit the canonical assignment `app/` source, run `python app/prepare_deployment.py` from the assignment root, review `tmp/deployment/nightjar`, then commit and push that folder. The builder refuses unexpected files and preserves its `.git` metadata. Never copy uploads or the local database into it.
